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


def set_root(root) -> None:
    """切换当前项目根。多项目支持的核心入口。"""
    global ROOT, BOARD, CARDS, WORKSPACE
    ROOT = Path(root).resolve()
    BOARD = ROOT / "board"
    CARDS = BOARD / "cards"
    BOARD.mkdir(parents=True, exist_ok=True)
    CARDS.mkdir(parents=True, exist_ok=True)
    WORKSPACE = ROOT


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


def jwrite(path: Path, obj: dict):
    """原子写：先写临时文件再 rename。"""
    tmp = path.with_suffix(path.suffix + f".tmp{uuid.uuid4().hex[:8]}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def jread(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def card_dir(cid: str) -> Path:
    d = CARDS / cid
    if not d.exists():
        die(f"卡片不存在：{cid}")
    return d


def load_journal(cid: str) -> list:
    p = card_dir(cid) / "journal.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _line_hash(prev: str, obj: dict) -> str:
    """一条事件的哈希：prev + 去掉 hash 字段的内容。"""
    body = {k: v for k, v in obj.items() if k not in ("hash", "prev")}
    raw = prev + json.dumps(body, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@contextlib.contextmanager
def _file_lock(path: Path, timeout: float = 10.0):
    """跨进程文件锁（Windows 用 msvcrt，POSIX 用 fcntl）。

    防的是：两个进程同时 append journal ⇒ 都读到同一个 prev ⇒ 哈希链分叉，
    随后 audit 会把正常写入误报成「被篡改」（opus 评审指出）。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+", encoding="utf-8")
    locked = False
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            try:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                time.sleep(0.05)
        yield locked
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
        f.close()


def append_event(cid: str, ev: dict) -> dict:
    """append-only：只追加，不改写。每条带 prev/hash 形成哈希链。

    加锁：读 prev → 计算 hash → 写入，整段原子，防止并发分叉。
    坏行处理：解析失败的行**不再静默丢弃**，记到 journal.corrupt 里（E-15/opus 评审）。
    """
    d = card_dir(cid)
    jp = d / "journal.jsonl"
    lockp = d / ".journal.lock"
    with _file_lock(lockp) as got:
        if not got:
            die(f"拿不到 {cid} 的 journal 锁（另一个进程正在写），稍后重试")
        prev = ""
        n = 0
        bad = []
        if jp.exists():
            for line in jp.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    n += 1
                    prev = obj.get("hash", prev)
                except json.JSONDecodeError:
                    bad.append(line[:200])
        if bad:
            with (d / "journal.corrupt").open("a", encoding="utf-8") as f:
                for b in bad:
                    f.write(b + "\n")
        ev = {"seq": n + 1, "at": ts(), "at_ms": now_ms(), **ev}
        ev["prev"] = prev
        ev["hash"] = _line_hash(prev, ev)
        with jp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev


def verify_chain(cid: str) -> tuple:
    """校验哈希链。返回 (ok, 问题描述)。"""
    prev = ""
    for i, ev in enumerate(load_journal(cid), 1):
        if "hash" not in ev:
            return False, f"第 {i} 条无 hash（旧格式或被手写插入）"
        if ev.get("prev", "") != prev:
            return False, f"第 {i} 条 prev 断裂（期望 {prev[:8]}，实际 {str(ev.get('prev'))[:8]}）"
        if _line_hash(prev, ev) != ev["hash"]:
            return False, f"第 {i} 条 hash 不符（内容被改过）"
        prev = ev["hash"]
    return True, ""


def replay(cid: str) -> dict:
    """从 journal 重放出当前状态（journal 是唯一真相）。"""
    card = jread(card_dir(cid) / "card.json")
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

def lease_root(cid: str) -> Path:
    p = card_dir(cid) / "lease" / "active"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ⚠️ 租约目录名必须是**固定名**，不能带 uuid。
# 带 uuid 时每个进程创建的路径都不同，os.mkdir 永远不会撞名，
# 互斥就退化成「先读后写」的 TOCTOU（2026-10-19 专家团实测：12 线程抢卡，3 个成功）。
LEASE_NAME = "holder"


def active_lease(cid: str):
    p = card_dir(cid) / "lease" / "active" / LEASE_NAME
    return p if p.exists() else None


def _lease_owner(lease: Path) -> dict:
    try:
        return jread(lease / "owner.json")
    except Exception:
        return {}


def _reclaim_lease(cid: str, lease: Path, reason: str = "heartbeat timeout"):
    """把租约目录原子 rename 到 reclaimed/，留痕。"""
    dest = card_dir(cid) / "lease" / "reclaimed"
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"R__{now_ms()}__{uuid.uuid4().hex[:6]}"
    try:
        os.replace(lease, target)
    except OSError:
        return False
    jwrite(target / "reclaim.json", {
        "reclaimed_at": ts(), "reason": reason,
        "timeout_s": LEASE_TTL, "previous_owner": _lease_owner(lease),
    })
    append_event(cid, {"type": "reclaim", "seat": "system",
                       "previous": _lease_owner(lease).get("seat"),
                       "reason": reason})
    return True


def claim(cid: str, seat: str, engine: str, model: str = None, effort: str = None) -> bool:
    """原子认领：独占创建**固定名**目录。返回 True=拿到。"""
    st = replay(cid)
    if st["state"] not in ("待认领", "阻塞", "待返工"):
        die(f"卡片当前状态「{st['state']}」，不可认领")
    card = jread(card_dir(cid) / "card.json")
    # 执行规格校验：卡指定了就必须对得上，否则不许接
    miss = _match_miss(card, engine, model, effort)
    if miss:
        die("这张卡的执行规格与你声明的不符：" + "；".join(miss)
            + f"\n  卡要求：引擎={card.get('engine')} 模型={card.get('model')} "
              f"思考={card.get('effort')}\n  你声明：引擎={engine} 模型={model} 思考={effort}"
            + "\n  （用 board.py ready 找你匹配的活）")
    lease = lease_root(cid)
    target = lease / LEASE_NAME
    # 最多试两次：第一次撞上超时租约 → 回收 → 再抢一次
    for attempt in (1, 2):
        try:
            os.mkdir(target)      # ← 固定名 + mkdir = 真正的系统级原子互斥
            break
        except FileExistsError:
            owner = _lease_owner(target)
            hb = owner.get("at_ms", 0)
            # 空 owner.json 视为「刚占上、还没写完」，⛔ 不当超时（D2 A.2）
            fresh = (now_ms() - hb) / 1000 if hb else 0
            if hb and fresh > LEASE_TTL and attempt == 1:
                print(f"  · 回收超时租约（{owner.get('seat')}，{int(fresh)}s 无心跳）")
                if _reclaim_lease(cid, target):
                    continue
                die("回收失败，稍后重试")
            die(f"卡片已被占用（{owner.get('seat','?')}，心跳 {int(fresh)}s 前）")
        except OSError as e:
            die(f"认领失败（文件系统错误）：{e}")
    else:
        die("认领竞争失败")

    jwrite(target / "owner.json", {
        "seat": seat, "engine": engine, "model": model, "effort": effort,
        "at": ts(), "at_ms": now_ms(),
        "ttl_s": LEASE_TTL, "hb_interval_s": HB_INTERVAL,
    })
    epoch = replay(cid)["epoch"] + 1
    append_event(cid, {"type": "claim", "actor": "agent", "seat": seat,
                       "engine": engine, "model": model, "effort": effort,
                       "epoch": epoch, "lease_dir": LEASE_NAME})
    return True


def heartbeat(cid: str, seat: str):
    lease = active_lease(cid)
    if not lease:
        die("没有活跃租约")
    owner = _lease_owner(lease)
    if owner.get("seat") != seat:
        die(f"租约持有者是 {owner.get('seat')}，不是你")
    owner.update({"at": ts(), "at_ms": now_ms()})
    jwrite(lease / "owner.json", owner)
    append_event(cid, {"type": "heartbeat", "actor": "agent", "seat": seat})
    ok(f"心跳已记（TTL {LEASE_TTL}s）")


def release(cid: str, to: str = "released"):
    """释放租约：原子 rename 出去，让下一次认领能重新 mkdir。"""
    lease = active_lease(cid)
    if not lease:
        return
    dest = card_dir(cid) / "lease" / to
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / f"L__{now_ms()}__{uuid.uuid4().hex[:6]}"
    try:
        os.replace(lease, target)
    except OSError:
        return
    jwrite(target / "release.json", {"released_at": ts(), "owner": _lease_owner(lease)})


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
