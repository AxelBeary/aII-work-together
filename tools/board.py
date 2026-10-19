#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
board.py — 多 agent 共享看板（单文件，零依赖，Python 3.9+）

设计依据：docs/design/20261019-architecture-deepdive/
  D1 卡片模型与状态机 / D2 租约与验收判据 / 98_架构总图

三条红线在本工具里的落点：
  ① 状态即证据 —— 进「完成」必须过 L1-L3 机器闸 + L4 异会话复核；退出码权重 0
  ② 人的拍板位 —— 出「拍板中」只能由 human 命令（需 token），agent 命令无此子命令路径
  ③ 认领即租约 —— 认领 = 原子独占创建目录（os.mkdir），系统级互斥，非先读后写

用法（人只需记 3 条）：
  python tools/board.py ls
  python tools/board.py show <id>
  python tools/board.py html          # 生成看板页，双击即可看
"""
import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "board"
CARDS = BOARD / "cards"
# agent 干活的地方（交付物路径相对它解析）。默认＝项目根，可由项目注册表的 workspace 覆盖。
WORKSPACE = ROOT
_STORE = None          # 当前项目的 Store（惰性建）
_STORE_LOCK = None     # 建连接的锁


def set_root(root) -> None:
    """切换当前项目根。多项目支持的核心入口。"""
    global ROOT, BOARD, CARDS, WORKSPACE, _STORE
    ROOT = Path(root).resolve()
    BOARD = ROOT / "board"
    CARDS = BOARD / "cards"
    BOARD.mkdir(parents=True, exist_ok=True)
    CARDS.mkdir(parents=True, exist_ok=True)
    WORKSPACE = ROOT
    _STORE = None            # 切项目必须丢弃旧连接
    migrate_if_needed()


def migrate_if_needed(verbose: bool = False) -> int:
    """首次把旧「文件即卡」布局迁进 SQLite（幂等，不删旧文件）。"""
    legacy = ROOT / "board" / "cards"
    if not legacy.exists():
        return 0
    if not any(d.is_dir() for d in legacy.iterdir()):
        return 0
    st = _store()
    if st.stats()["cards"] > 0:
        return 0
    import storage
    n = storage.migrate_from_files(legacy, st)
    if n:
        _stamp_migration_done(n)
    return n


def _stamp_migration_done(n: int):
    try:
        f = BOARD / "MIGRATED.txt"
        f.write_text(
            f"已把 {n} 张卡从 board/cards/ 迁入 board/board.db（{ts()}）\n"
            "旧文件保留作对照，可直接删除：board/cards/\n",
            encoding="utf-8")
    except Exception:
        pass


def set_workspace(ws) -> None:
    """指定 agent 干活的工作区（交付物路径相对于它解析）。"""
    global WORKSPACE
    WORKSPACE = Path(ws).resolve()

# 租约参数（D2 A.5）
LEASE_TTL = 600          # 秒，10 分钟无心跳视为超时
HB_INTERVAL = 120        # 秒，建议心跳间隔

STATES = ["待认领", "进行中", "待返工", "阻塞", "待验收", "核验中", "拍板中", "完成", "已取消"]

# 转移白名单：谁可以触发。agent = 执行席，review = 复核席，human = 人，system = 工具
TRANSITIONS = {
    ("待认领", "进行中"):   {"actor": {"agent"}},
    ("待返工", "进行中"):   {"actor": {"agent"}},
    ("进行中", "阻塞"):     {"actor": {"agent"}},
    ("阻塞", "进行中"):     {"actor": {"agent"}},
    ("进行中", "待验收"):   {"actor": {"agent"}},          # submit
    ("待验收", "核验中"):   {"actor": {"review"}},
    ("核验中", "完成"):     {"actor": {"review"}},          # 但需 human gate 时此边不可达
    ("核验中", "待返工"):   {"actor": {"review"}},          # 打回
    ("待验收", "拍板中"):   {"actor": {"agent", "review"}},  # 请求拍板
    ("拍板中", "完成"):     {"actor": {"human"}},
    ("拍板中", "待返工"):   {"actor": {"human"}},
    ("待认领", "已取消"):   {"actor": {"human"}},
    ("进行中", "已取消"):   {"actor": {"human"}},
    ("待返工", "已取消"):   {"actor": {"human"}},
    ("待验收", "已取消"):   {"actor": {"human"}},
}


# ---------- 基础 ----------

def now_ms() -> int:
    return int(time.time() * 1000)


def ts() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def die(msg: str, code: int = 1):
    print(f"✗ {msg}")
    sys.exit(code)


def ok(msg: str):
    print(f"✓ {msg}")


def _store():
    """取当前项目的库（惰性建连，随 set_root 切换）。

    ⚠️ 必须加锁：并发首次调用会同时看到 _STORE is None ⇒ 造出多个 Store 实例，
       各自带一把锁 ⇒ 互斥失效。
       2026-10-20 实测：12 线程首次并发调用造出 12 个实例，导致 2 个 agent 同时认领成功。
    """
    global _STORE, _STORE_LOCK
    if _STORE_LOCK is None:
        import threading as _t
        _STORE_LOCK = _t.Lock()
    with _STORE_LOCK:
        if _STORE is None or Path(_STORE.path) != (BOARD / "board.db"):
            import storage
            _STORE = storage.Store(BOARD / "board.db", BOARD / "evidence")
        return _STORE


def close_store():
    global _STORE
    if _STORE is not None:
        _STORE.close()
        _STORE = None


def jwrite(path, obj):
    """兼容旧接口：仍可原子写 JSON 文件（现在只用于非权威的小件）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    import uuid as _u
    tmp = path.with_suffix(path.suffix + f".tmp{_u.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def jread(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def card_dir(cid: str) -> Path:
    """卡片作用域的文件目录（证据等）。权威数据在库里，不在这些文件里。"""
    d = _store().evidence_path(cid)
    return d


def get_card(cid: str):
    """取卡片契约（库）。找不到返回 None。"""
    return _store().get_card(cid)


def require_card(cid: str):
    c = get_card(cid)
    if not c:
        die(f"卡片不存在：{cid}")
    return c


def all_cards():
    return _store().all_cards()


def card_ids():
    """所有卡号（有序）。替代遍历 CARDS 目录。"""
    return [c["id"] for c in _store().all_cards()]


class CardRef:
    """轻量卡引用：兼容 `for d in ...: d.name` 与 `d / 'xxx'` 的老写法。"""
    __slots__ = ("name",)

    def __init__(self, cid):
        self.name = cid

    def __truediv__(self, other):
        return card_dir(self.name) / other

    def exists(self):
        return get_card(self.name) is not None

    def is_dir(self):
        return self.exists()

    def relative_to(self, other):
        return Path(self.name)


def card_refs():
    return [CardRef(c) for c in card_ids()]


def card_ref(cid):
    return CardRef(cid)


def create_card(card: dict):
    """建卡（统一入口，CLI 与测试都用它）。

    ⚠️ 必须先查后写、且在同一个串行区内完成，否则并发建同号卡会互相覆盖
    （存储层用的是 INSERT OR REPLACE，覆盖是静默的）。
    """
    cid = card.get("id")
    if get_card(cid) is not None:
        raise ValueError(f"卡片已存在：{cid}")
    _store().save_card(card)
    return card


def load_journal(cid: str):
    return _store().events(cid)


def append_event(cid: str, ev: dict) -> dict:
    """append-only；哈希链与串行化由存储层事务保证。"""
    if get_card(cid) is None:
        die(f"卡片不存在：{cid}")
    return _store().append_event(cid, ev)


def verify_chain(cid: str):
    return _store().verify_chain(cid)


def replay(cid: str):
    """从事件流重放出当前状态（事件流＝唯一真相）。"""
    card = require_card(cid)
    st = {
        "id": cid,
        "title": card.get("title", cid),
        "state": "待认领",
        "holder": None,
        "epoch": 0,
        "claim_at": None,
        "heartbeat_at": None,
        "lease_dir": None,
        "submit": None,
        "review": None,
        "human": None,
        "blocked_reason": None,
        "rework": 0,
        "events": 0,
        "gate": card.get("human_gate", "none"),
        "engine": card.get("engine", "any"),
        "model": card.get("model", "any"),
        "effort": card.get("effort", "any"),
        "created_by": card.get("created_by", "human"),
        "created_kind": card.get("created_kind", "human"),
        "holder_model": None,
        "holder_effort": None,
    }
    for ev in load_journal(cid):
        st["events"] += 1
        k = ev.get("type")
        if k == "claim":
            st.update(state="进行中", holder=ev.get("seat"), epoch=ev.get("epoch", 0),
                      claim_at=ev.get("at_ms"), heartbeat_at=ev.get("at_ms"),
                      lease_dir=ev.get("lease_dir"), blocked_reason=None,
                      holder_model=ev.get("model"), holder_effort=ev.get("effort"))
        elif k == "heartbeat":
            if ev.get("seat") == st["holder"]:
                st["heartbeat_at"] = ev.get("at_ms")
        elif k == "submit":
            st.update(state="待验收", submit=ev)
        elif k == "verify":
            st["state"] = "核验中"
        elif k == "review":
            st["review"] = ev
            st["state"] = "完成" if ev.get("verdict") == "pass" else "待返工"
            if ev.get("verdict") != "pass":
                st["rework"] += 1
                st["holder"] = None
                st["lease_dir"] = None
        elif k == "block":
            st.update(state="阻塞", blocked_reason=ev.get("reason"))
        elif k == "unblock":
            st["state"] = "进行中"
            st["blocked_reason"] = None
        elif k == "human":
            st["human"] = ev
            st["state"] = "完成" if ev.get("decision") == "approve" else "待返工"
            if ev.get("decision") != "approve":
                st["rework"] += 1
                st["holder"] = None
                st["lease_dir"] = None
        elif k == "request_human":
            st["state"] = "拍板中"
        elif k == "reclaim":
            st.update(state="待认领", holder=None, lease_dir=None)
        elif k == "cancel":
            st["state"] = "已取消"
    return st


# ---------- 租约（红线③）----------

LEASE_NAME = "holder"      # 兼容旧值；库版已不用目录名做互斥


def active_lease(cid: str):
    """有活跃租约则返回持有者信息 dict，否则 None。"""
    return _store().get_lease(cid)


def _lease_owner(lease):
    """兼容旧签名：lease 现在就是持有者 dict。"""
    return lease or {}


def _reclaim_lease(cid: str, lease=None, reason: str = "heartbeat timeout"):
    cur = _store().reclaim(cid, reason=reason)
    if cur:
        append_event(cid, {"type": "reclaim", "seat": "system",
                           "previous": cur.get("seat"), "reason": reason})
        return True
    return False


def claim(cid: str, seat: str, engine: str, model: str = None, effort: str = None) -> bool:
    """原子认领（库里 PRIMARY KEY 保证互斥）。"""
    st = replay(cid)
    if st["state"] not in ("待认领", "阻塞", "待返工"):
        die(f"卡片当前状态「{st['state']}」，不可认领")
    card = require_card(cid)
    miss = _match_miss(card, engine, model, effort)
    if miss:
        die("这张卡的执行规格与你声明的不符：" + "；".join(miss)
            + f"\n  卡要求：引擎={card.get('engine')} 模型={card.get('model')} "
              f"思考={card.get('effort')}\n  你声明：引擎={engine} 模型={model} 思考={effort}"
            + "\n  （用 board.py ready 找你匹配的活）")
    epoch = st.get("epoch", 0) + 1
    okc, why = _store().try_claim(cid, seat, engine, model, effort,
                                  epoch=epoch, ttl_s=LEASE_TTL)
    if not okc:
        die(why)
    append_event(cid, {"type": "claim", "actor": "agent", "seat": seat,
                       "engine": engine, "model": model, "effort": effort,
                       "epoch": epoch, "lease_dir": LEASE_NAME})
    return True


def heartbeat(cid: str, seat: str):
    cur = _store().get_lease(cid)
    if not cur:
        die("没有活跃租约")
    if cur.get("seat") != seat:
        die(f"租约持有者是 {cur.get('seat')}，不是你")
    _store().touch_lease(cid, seat)
    append_event(cid, {"type": "heartbeat", "actor": "agent", "seat": seat})
    ok(f"心跳已记（TTL {LEASE_TTL}s）")


def release(cid: str, to: str = "released"):
    cur = _store().release_lease(cid, kind=to)
    return cur


# ---------- 闸门（红线①）----------

def sha8(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def gate_l1(cid: str, card: dict) -> tuple:
    """L1 产物存在性：文件在、字节>0、mtime 在认领窗口内。"""
    st = replay(cid)
    problems, results = [], []
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        p = (WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
        if not p.exists():
            problems.append(f"缺件：{rel}")
            results.append({"path": rel, "exists": False})
            continue
        size = p.stat().st_size
        if size == 0:
            problems.append(f"零字节：{rel}")
        results.append({"path": rel, "exists": True, "bytes": size, "sha8": sha8(p)})
    return (len(problems) == 0), problems, results


def gate_l2(cid: str, card: dict) -> tuple:
    """L2 形制：编码与可解析性。"""
    problems = []
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        p = (WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
        if not p.exists():
            continue
        raw = p.read_bytes()
        if p.suffix == ".json":
            try:
                json.loads(raw.decode("utf-8"))
            except Exception:
                problems.append(f"JSON 不可解析：{rel}")
        if p.suffix in (".md", ".txt", ".py"):
            if b"\x00" in raw:
                problems.append(f"含零字节：{rel}")
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"非 UTF-8：{rel}")
    return (len(problems) == 0), problems


def gate_l3(cid: str, card: dict) -> tuple:
    """L3 内容闸门：派工单声明的必含项逐条断言 + 反空跑。"""
    problems, checks = [], []
    patterns = card.get("accept_patterns", [])
    text_cache = {}
    TEXTY = (".md", ".txt", ".py", ".json", ".yaml", ".yml", ".html", ".css", ".js", ".ts")
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        p = (WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
        if p.exists() and p.suffix.lower() in TEXTY:
            try:
                text_cache[rel] = p.read_text(encoding="utf-8")
            except Exception:
                pass
    for pat in patterns:
        hit = any(re.search(pat, t) for t in text_cache.values())
        checks.append({"pattern": pat, "hit": hit})
        if not hit:
            problems.append(f"必含项未命中：{pat}")
    # 反空跑（**无条件**执行）：交付物里必须有数字，否则视为空跑。
    # 例外：卡显式写 allow_no_numbers=true（如纯文字设计稿）。
    if text_cache and not card.get("allow_no_numbers"):
        has_num = any(re.search(r"\d", t) for t in text_cache.values())
        checks.append({"pattern": "<非零计数>", "hit": has_num})
        if not has_num:
            problems.append("反空跑失败：交付物里没有任何数字（若确实不需要数字，"
                            "在卡上设 allow_no_numbers=true）")
    return (len(problems) == 0), problems, checks



def _match_miss(card: dict, engine, model, effort) -> list:
    """返回不匹配项列表；空＝匹配。'any' 表示卡不限定。"""
    miss = []
    ce, cm, cf = card.get("engine", "any"), card.get("model", "any"), card.get("effort", "any")
    if ce != "any" and engine and engine != ce:
        miss.append(f"引擎需 {ce}")
    if cm != "any" and model and model != cm:
        miss.append(f"模型需 {cm}")
    if cf != "any" and effort and effort != cf:
        miss.append(f"思考强度需 {cf}")
    return miss


def __getattr__(name):
    """让 `board.cmd_new` 这类用法仍可用（命令在 cli.py）。"""
    try:
        import cli as _cli
        return getattr(_cli, name)
    except (ImportError, AttributeError):
        raise AttributeError(name)


if __name__ == "__main__":
    import cli as _cli
    _cli.main()
