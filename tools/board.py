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

import fold as _fold            # 事件折叠（D-033）：comments/executions/checklist 投影
fold = _fold

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
    # ⚠️ 2026-10-21 修（安全扫描 F-11）：旧写法只 `_STORE = None`，SQLite 连接
    #    留在 threading.local 里没人关；总览每 15 秒逐项目切一次 ⇒ 句柄只涨不落，
    #    Windows 上还会让 board.db 被「看不见的读者」占着。切之前先关本线程连接。
    if _STORE is not None:
        try:
            _STORE.close()
        except Exception as e:
            print(f"⚠ 切换项目时关闭旧库失败（{e}）——继续，但句柄可能残留", file=sys.stderr)
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
    # 2026-11-19（D-036）面板要用的三条人类边：
    ("阻塞", "待认领"):     {"actor": {"human"}},   # 清僵尸阻塞，放回池子
    ("待返工", "待认领"):   {"actor": {"human"}},   # 人决定重排
    ("待验收", "待返工"):   {"actor": {"human"}},   # 人不等复核，直接打回
    # 执行失败回退（A6）：不是 review，不计返工次数
    ("进行中", "待返工"):   {"actor": {"agent", "system"}},
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


CARD_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def check_card_id(cid):
    """卡号白名单。

    ⚠️ 2026-10-21 修（安全扫描 F-02）：卡号会直接进文件路径
       （`board/evidence/<卡号>/run.log`、`board/cards/<卡号>`、`.worktrees/<卡号>`），
       而 HTTP 建卡与 `--id` 都不校验。`..\\..\\x` 能在任意目录 mkdir，
       配合 `rm` 的 rmtree 就是删任意目录。这里一次性钉死形状。
    """
    cid = (cid or "").strip()
    if not CARD_ID_RE.match(cid):
        die(f"卡号不合法：{cid!r}（只允许 A-Z a-z 0-9 _ - ，长度 1–64）")
    return cid


def card_dir(cid: str) -> Path:
    """卡片作用域的文件目录（证据等）。权威数据在库里，不在这些文件里。"""
    d = _store().evidence_path(check_card_id(cid))
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

    ⚠️ 2026-10-21 修（安全扫描 F-13）：旧写法「先查后写」只在单进程内有效，
       两个进程同时建同号卡会互相覆盖（存储层 INSERT OR REPLACE 是静默覆盖）。
       现在靠主键冲突判重：纯 INSERT 撞键 → IntegrityError → 「卡片已存在」。
    """
    cid = check_card_id(card.get("id"))
    card["id"] = cid
    try:
        _store().save_card(card, create_only=True)
    except Exception as e:
        msg = str(e).lower()
        if "unique" in msg or "primary key" in msg or "constraint" in msg:
            raise ValueError(f"卡片已存在：{cid}")
        raise
    return card


def load_journal(cid: str):
    return _store().events(cid)


RETRY_BASE = 3      # 一张卡默认允许几次「复核打回」；超了转阻塞等人


def attempts(cid: str, events: list = None) -> int:
    """这张卡被复核打回过几次（返工次数）。"""
    n = 0
    for ev in (events if events is not None else load_journal(cid)):
        if ev.get("type") == "review" and ev.get("verdict") != "pass":
            n += 1
    return n


def retry_granted(events: list) -> int:
    """人工显式加过的返工额度（append-only，不进卡字段，可审计）。"""
    return sum(int(e.get("delta") or 0) for e in events if e.get("type") == "retry_grant")


def retry_limit(cid: str, card: dict, events: list = None) -> int:
    evs = events if events is not None else load_journal(cid)
    try:
        budget = int((card or {}).get("retry_budget") or 0)
    except (TypeError, ValueError):
        budget = 0
    return RETRY_BASE + budget + retry_granted(evs)


def retry_left(cid: str, card: dict, events: list = None) -> int:
    """还剩几次返工额度。"""
    evs = events if events is not None else load_journal(cid)
    return retry_limit(cid, card, evs) - attempts(cid, evs)


def append_event(cid: str, ev: dict) -> dict:
    """append-only；哈希链与串行化由存储层事务保证。"""
    if get_card(cid) is None:
        die(f"卡片不存在：{cid}")
    return _store().append_event(cid, ev)


def verify_chain(cid: str):
    return _store().verify_chain(cid)


def holder_of(cid: str, st: dict = None):
    """当前**真实**持有者：事件流说有 ＋ 库里租约还在；否则 None。

    ⚠️ 2026-10-21 修：`replay` 只看事件流，而 `release` 原先不写事件 ⇒
       闸门失败/回收后 `board show` 与界面仍显示「持有：某人」，与 `leases` 表打架。
       （现在 release 会写事件；这里再按库交叉验一次，兜住历史卡片。）
    """
    st = st if st is not None else replay(cid)
    if not st.get("holder"):
        return None
    return st["holder"] if _store().get_lease(cid) else None


def evidence_tier(cid: str, st: dict = None) -> str:
    """这张卡当前能对外写到的**最高证据层级**（2026-10-21，外部研究落地）。

    依据：同一表征家族内的「复核/自审」不产生认识论增益（盲集继承），
    只有**非语言的检查产物**才算验证。所以：

      VERIFIED            —— 机器闸 L1/L2/L3 全过（字节/哈希/断言命中/退出码是可复核的工件）
      AUDITED-UNGROUNDED  —— 只有复核席的表态（同家族复核＝第二枚章，不是验证）
      UNVERIFIED          —— 两者都没有

    ⛔ 别把「复核通过」说成「已验证」——这是本项目最容易被自己糊弄的一句话。
    """
    st = st if st is not None else replay(cid)
    last_verify = None
    for ev in load_journal(cid):
        if ev.get("type") == "verify":
            last_verify = ev
    gate_ok = bool(last_verify) and bool(
        last_verify.get("L1") and last_verify.get("L2") and last_verify.get("L3"))
    if gate_ok:
        return "VERIFIED"
    if st.get("review"):
        return "AUDITED-UNGROUNDED"
    return "UNVERIFIED"


def replay(cid: str, events=None):
    """从事件流重放出当前状态（事件流＝唯一真相）。

    events 允许调用方传入已读好的事件流，避免同一份日志被扫两遍
    （列表页每张卡都要重放一次，重复扫描会翻倍）。
    """
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
    for ev in (load_journal(cid) if events is None else events):
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
        elif k == "release":
            # 释放即清持有者（seat 为空＝无条件释放）
            if not ev.get("seat") or ev.get("seat") == st["holder"]:
                st.update(holder=None, lease_dir=None, heartbeat_at=None)
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
        elif k == "edit":
            st["edit"] = ev
            st["version"] = ev.get("version")
        elif k == "move":
            st["state"] = ev.get("to") or st["state"]
        elif k == "revert":
            st["state"] = "待返工"
            st["revert"] = ev
            st["holder"] = None
            st["lease_dir"] = None
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
    """回收并留痕。返回被回收的租约 dict（没有则 None）。"""
    cur = _store().reclaim(cid, reason=reason)
    if cur:
        append_event(cid, {"type": "reclaim", "seat": "system",
                           "previous": cur.get("seat"), "reason": reason})
        return cur
    return None


def claim(cid: str, seat: str, engine: str, model: str = None, effort: str = None) -> bool:
    """原子认领（库里 PRIMARY KEY 保证互斥）。"""
    st = replay(cid)
    if st["state"] not in ("待认领", "阻塞", "待返工"):
        die(f"卡片当前状态「{st['state']}」，不可认领")
    card = require_card(cid)
    # ⚠️ 依赖与预算两条闸放在「认领」这一层，而不是只在编排器里：
    #    编排器只是**一个**调用方；直接 `board claim` 的 agent 也必须被挡住，
    #    否则规则只在一个入口生效＝形同没有（D-016）。
    blocked = withholding(cid, card)
    if blocked:
        die("这张卡现在不能开工：\n  - " + "\n  - ".join(blocked))
    miss = _match_miss(card, engine, model, effort)
    if miss:
        die("这张卡的执行规格与你声明的不符：" + "；".join(miss)
            + f"\n  卡要求：引擎={card.get('engine')} 模型={card.get('model')} "
              f"思考={card.get('effort')}\n  你声明：引擎={engine} 模型={model} 思考={effort}"
            + "\n  （用 board.py ready 找你匹配的活）")
    epoch = st.get("epoch", 0) + 1
    okc, why = _store().try_claim(
        cid, seat, engine, model, effort, epoch=epoch, ttl_s=LEASE_TTL,
        # 认领时若顺手回收了超时租约，也要在**事件流**里留痕
        # （否则表和事件流各说一套：Q1 复核指出的第三个洞）
        on_reclaim=lambda old: append_event(cid, {
            "type": "reclaim", "seat": "system",
            "previous": old.get("seat"),
            "reason": "心跳超时（认领时自动回收）"}))
    if not okc:
        die(why)
    append_event(cid, {"type": "claim", "actor": "agent", "seat": seat,
                       "engine": engine, "model": model, "effort": effort,
                       "epoch": epoch, "lease_dir": LEASE_NAME,
                       "pid": os.getpid(),
                       # 幂等（D-038）：同一 (卡, 席位, 代次) 重试只落一条 claim
                       "idempotency_key": _idem("claim", cid, seat, epoch)})
    # B4：认领时给交付物拍快照（「before」），之后拍板的人不用自己跑 git diff
    append_event(cid, {"type": "baseline", "actor": "system", "seat": seat,
                       "files": _snapshot_deliverables(card),
                       "idempotency_key": _idem("baseline", cid, seat, epoch)})
    return True


def heartbeat(cid: str, seat: str, epoch: int = None):
    cur = _store().get_lease(cid)
    if not cur:
        die("没有活跃租约")
    if cur.get("seat") != seat:
        die(f"租约持有者是 {cur.get('seat')}，不是你")
    # 栅栏：同席位被回收后重新认领会换 epoch（2026-10-21，编排调研指出 epoch 一直是死字段）
    if epoch is not None and int(epoch) != int(cur.get("epoch") or 0):
        die(f"租约已换代：当前 epoch={cur.get('epoch')}，你带的是 {epoch}"
            f"（你那一代已被回收，⛔ 不要再写）")
    if not _store().touch_lease(cid, seat, epoch):
        die("续心跳失败：租约在你读完之后换代了（栅栏拦下）")
    append_event(cid, {"type": "heartbeat", "actor": "agent", "seat": seat,
                       "epoch": int(cur.get("epoch") or 0)})
    ok(f"心跳已记（TTL {LEASE_TTL}s）")


def release(cid: str, to: str = "released", seat: str = None):
    """释放租约。带 `seat` 时只释放自己的（CAS），防止误删别人刚抢到的。

    ⚠️ 2026-10-21 修：释放后补一条 `release` 事件——否则 `replay` 只看 `claim`，
       `board show`/界面会一直显示「持有：某人」（实测：闸门失败转阻塞后仍显示旧持有者，
       而库里租约已经空了，两把尺打架）。
    """
    cur = _store().release_lease(cid, kind=to, seat=seat)
    if cur:
        append_event(cid, {"type": "release", "actor": "agent",
                           "seat": cur.get("seat"), "kind": to})
    return cur


# ---------- 闸门（红线①）----------

def sha8(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def deliverable_path(item) -> Path:
    """把卡片上的交付物路径解析进工作区；绝对路径与 `..` 一律拒。

    ⚠️ 2026-10-21 修（安全扫描 F-14）：旧写法允许绝对路径与 `..`，
       于是 L1/L2/L3 会去 stat／读工作区外的任意文件（存在性/大小/哈希外泄），
       并行收集会往任意路径写，`consult` 还会把文件内容贴进提示词外发给模型。
    """
    rel = item if isinstance(item, str) else (item or {}).get("path")
    s = str(rel or "").strip()
    if not s:
        raise ValueError("交付物路径是空的")
    if Path(s).is_absolute() or Path(s.replace("\\", "/")).is_absolute():
        raise ValueError(f"交付物只允许相对路径：{s}")
    full = (WORKSPACE / s).resolve()
    try:
        full.relative_to(Path(WORKSPACE).resolve())
    except ValueError:
        raise ValueError(f"交付物跑出工作区：{s}")
    return full


def gate_l1(cid: str, card: dict) -> tuple:
    """L1 产物存在性：文件在、字节>0、**mtime 不早于认领时刻**。

    ⚠️ 2026-10-20 修：docstring 一直写着「mtime 在认领窗口内」，代码却没查——
       于是 agent 拿一个三天前的旧文件顶交付物也能过（Q1 复核复现）。
       现在真查：交付物 mtime 必须 ≥ 最后一次 claim 事件的时间（留 5 秒时钟容差）。
    """
    st = replay(cid)
    claims = [e for e in load_journal(cid) if e.get("type") == "claim"]
    claim_ms = claims[-1].get("at_ms") if claims else 0
    problems, results = [], []
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        try:
            p = deliverable_path(item)
        except ValueError as e:
            problems.append(str(e))
            results.append({"path": rel, "exists": False, "rejected": True})
            continue
        if not p.exists():
            problems.append(f"缺件：{rel}")
            results.append({"path": rel, "exists": False})
            continue
        stat = p.stat()
        size = stat.st_size
        mtime_ms = int(stat.st_mtime * 1000)
        stale = bool(claim_ms and mtime_ms < claim_ms - 5000)
        if size == 0:
            problems.append(f"零字节：{rel}")
        if stale:
            age_min = (claim_ms - mtime_ms) / 60000.0
            problems.append(f"旧文件：{rel} 的 mtime 比认领早 {age_min:.1f} 分钟（像是没动过）")
        results.append({"path": rel, "exists": True, "bytes": size,
                        "sha8": sha8(p), "mtime_ms": mtime_ms,
                        "stale": stale})
    return (len(problems) == 0), problems, results


def gate_l2(cid: str, card: dict) -> tuple:
    """L2 形制：编码与可解析性。"""
    problems = []
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        try:
            p = deliverable_path(item)
        except ValueError as e:
            problems.append(str(e))
            continue
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


MIN_NONSPACE = 20      # 反空跑：交付物至少要有这么多非空白字符，否则视为空壳


def gate_l3(cid: str, card: dict) -> tuple:
    """L3 内容闸门：派工单声明的必含项逐条断言 + 反空跑。"""
    problems, checks = [], []
    patterns = card.get("accept_patterns", [])
    text_cache = {}
    TEXTY = (".md", ".txt", ".py", ".json", ".yaml", ".yml", ".html", ".css", ".js", ".ts")
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        try:
            p = deliverable_path(item)
        except ValueError as e:
            problems.append(str(e))
            continue
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
    # 反空跑（**无条件**执行）：交付物不能是空壳。
    # ⚠️ 2026-10-20 改（甲方案）：原来要求「交付物里必须有数字」，
    #   结果翻译类任务把统计注释写进了正文（实测两席评审都点出这是污染）。
    #   现在改成**机器测**：字节数 / 行数 / 非空白字符数由闸门自己算，
    #   数字进 checks（证据），不再要求写进产物。
    # 例外：卡显式写 allow_no_numbers=true（允许极短产物，如单行占位文案）。
    if text_cache and not card.get("allow_no_numbers"):
        total_ns = sum(len(re.sub(r"\s", "", t)) for t in text_cache.values())
        total_bytes = sum(len(t.encode("utf-8")) for t in text_cache.values())
        total_lines = sum(t.count("\n") + (1 if t and not t.endswith("\n") else 0)
                          for t in text_cache.values())
        ok_nonempty = total_ns >= MIN_NONSPACE
        checks.append({"pattern": "<非空壳>", "hit": ok_nonempty,
                       "bytes": total_bytes, "lines": total_lines,
                       "nonspace": total_ns, "min": MIN_NONSPACE})
        if not ok_nonempty:
            problems.append(
                f"反空跑失败：交付物内容太少（{total_ns} 个非空白字符 / {total_bytes} 字节，"
                f"至少 {MIN_NONSPACE} 个）——疑似空壳或占位符")
    return (len(problems) == 0), problems, checks



# ---------- 预算 / 依赖 / 改动对照（B 批，2026-10-20）----------

DONE_STATES = ("完成", "已取消")


def validate_check_cmd(cmd: str) -> tuple:
    """外部闸门命令的准入：只允许「用 python 跑一个已存在的脚本」，不允许任意 shell。

    为什么收这么紧：`check_cmd` 会在提交时自动执行。放开 shell 就等于「谁能在卡上写一行，
    谁就能在别人提交时执行任意命令」。限制成 python 脚本后，能力边界就清楚了：
    闸门脚本必须是磁盘上真有、且在可信根（工作区 / 技能目录）里的文件。

    返回 (ok, 原因)。
    """
    import shlex
    s = (cmd or "").strip()
    if not s:
        return False, "空命令"
    if re.search(r"[;&|><`$]", s):
        return False, "命令里出现 shell 元字符（; & | > < ` $）"
    try:
        parts = [p.strip('"').strip("'") for p in shlex.split(s, posix=False)]
    except ValueError as e:
        return False, f"命令解析失败：{e}"
    if not parts:
        return False, "空命令"
    exe = parts[0].lower()
    if not (exe.endswith("python") or exe.endswith("python.exe") or exe.endswith("py")
            or exe.endswith("py.exe")):
        return False, "只允许用 python/py 跑脚本"
    script = next((p for p in parts[1:] if p.lower().endswith(".py")), None)
    if not script:
        return False, "没找到 .py 脚本"
    sp = Path(script)
    if not sp.is_absolute():
        sp = (WORKSPACE or ROOT) / sp
    if not sp.exists():
        return False, f"脚本不存在：{sp}"
    try:
        sp.resolve().relative_to((WORKSPACE or ROOT).resolve())
    except ValueError:
        # 工作区之外：只允许技能目录下的脚本
        try:
            sp.resolve().relative_to((Path.home() / ".agents" / "skills").resolve())
        except ValueError:
            return False, f"脚本不在工作区或技能目录内：{sp}"
    return True, ""


def gate_l4(cid: str, card: dict) -> tuple:
    """L4 外部门禁：卡上声明的 `check_cmd`（2026-10-23）。

    为什么要有：翻译、单测、lint 这些「专业闸门」不归看板管，但必须**在提交时跑**，
    否则复核席拿到的是没验过的件。卡带一条命令，提交时执行，非零即不过。

    准入（见 `validate_check_cmd`）：只允许「python 跑一个已存在的脚本」。
    人建的卡可以例外跑任意命令（人自己为后果负责）；agent 建的卡必须过准入。
    返回 (ok, problems, 输出尾部)。
    """
    import subprocess
    cmd = str(card.get("check_cmd") or "").strip()
    if not cmd:
        return True, [], ""
    human = card.get("created_kind") == "human"
    if not human:
        good, why = validate_check_cmd(cmd)
        if not good:
            return False, [f"check_cmd 未过准入：{why}"], ""
    cwd = str(WORKSPACE if WORKSPACE else ROOT)
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        return False, [f"check_cmd 超时 600s：{cmd}"], ""
    except Exception as e:
        return False, [f"check_cmd 起不来：{type(e).__name__}: {e}"], ""
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    tail = out[-1500:]
    if p.returncode != 0:
        return False, [f"check_cmd 退出码 {p.returncode}：{cmd}"], tail
    return True, [], tail


def budget_status(cid: str, card: dict = None, events: list = None) -> dict:
    """算这张卡「已经花了多少」和「上限是多少」。

    口径（写死，别再各算各的）：
      · 花费 = 所有 usage 事件里引擎**真报了**的 cost 之和（没报的不当 0，标 unknown）
      · 时长 = 所有 usage 事件的 duration_ms 之和（含复核/评审各阶段；
              另给 `minutes_exec` 只算「执行」阶段，看读数用）
    超限判定：任一项 **≥** 上限即超（2026-10-21 改：原来是 `>`，
    于是「已花 0.0500 / 上限 0.05」不算超，下一轮还能整轮跑完才停）。
    """
    card = card if card is not None else get_card(cid)
    events = events if events is not None else load_journal(cid)
    cost, ms, ms_exec, unknown = 0.0, 0, 0, 0
    for ev in events:
        if ev.get("type") != "usage":
            continue
        u = ev.get("usage") or {}
        if u.get("available"):
            cost += float(u.get("cost") or 0)
        else:
            unknown += 1
        d = int(ev.get("duration_ms") or 0)
        ms += d
        if str(ev.get("phase") or "").startswith("执行"):
            ms_exec += d
    max_cost = card.get("max_cost_usd")
    max_min = card.get("max_minutes")
    over = []
    if max_cost is not None and cost >= float(max_cost):
        over.append(f"花费 ${cost:.4f} 超过上限 ${float(max_cost):.2f}")
    if max_min is not None and ms / 60000.0 >= float(max_min):
        over.append(f"引擎时长 {ms / 60000.0:.1f} 分钟已达上限 {int(max_min)} 分钟")
    return {"cost": round(cost, 4), "minutes": round(ms / 60000.0, 1),
            "minutes_exec": round(ms_exec / 60000.0, 1),
            "max_cost": max_cost, "max_minutes": max_min,
            "unknown_runs": unknown, "over": bool(over), "reasons": over}


def withholding(cid: str, card: dict = None) -> list:
    """这张卡现在**能不能开工**：返回挡住它的原因（空＝能开工）。

    依赖未完成 → 「依赖 C1（进行中）」；预算已超 → 上限原因。
    ⚠️ 只看「已完成/已取消」以外的状态都算没完成——包括「完成」以外的所有状态，
       宁可不接，也不要抢跑（抢跑的代价是拿半截上游产出做出错的活）。
    """
    card = card if card is not None else get_card(cid)
    out = []
    for dep in card.get("blocked_by") or []:
        dep = str(dep)
        if not get_card(dep):
            out.append(f"依赖 {dep} 不存在")
            continue
        dst = replay(dep)["state"]
        if dst not in DONE_STATES:
            out.append(f"依赖 {dep} 还没完成（{dst}）")
    b = budget_status(cid, card)
    out.extend(b["reasons"])
    # 返工额度（2026-10-23，评审席裁定）：额度用尽就**不许再认领**。
    # 旧行为：额度用完只由编排器写一条 block 事件，但 `claim` 允许认领「阻塞」、
    # `pick()` 也把阻塞算可接 ⇒ 下一轮照样烧一整轮引擎，再阻塞一次，等于没闸。
    try:
        if retry_left(cid, card) <= 0:
            out.append(f"返工额度已用尽（已返工 {attempts(cid)} 次）；"
                       f"要再试：board retry --force")
    except Exception:
        pass
    return out


def diff_vs_baseline(cid: str, card: dict = None) -> list:
    """交付物「认领前 → 现在」的对照（B4：拍板的人不用自己跑 git diff）。

    基线来自 claim 时记的 baseline 事件；没有基线（旧卡/人直接提交）就全标「无基线」。
    """
    card = card if card is not None else get_card(cid)
    base = None
    for ev in load_journal(cid):
        if ev.get("type") == "baseline":
            base = {f["path"]: f for f in ev.get("files", [])}
    out = []
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        try:
            p = deliverable_path(item)
        except ValueError:
            out.append({"path": rel, "status": "越界", "before": None,
                        "after": {"exists": False, "bytes": 0, "sha8": None}})
            continue
        after = {"exists": p.exists(), "bytes": 0, "sha8": None}
        if p.exists():
            after = {"exists": True, "bytes": p.stat().st_size, "sha8": sha8(p)}
        b = (base or {}).get(rel)
        if b is None:
            status = "新件" if after["exists"] else "缺件"
            before = {"exists": False, "bytes": 0, "sha8": None}
        else:
            before = {"exists": b.get("exists"), "bytes": b.get("bytes", 0),
                      "sha8": b.get("sha8")}
            if not after["exists"]:
                status = "没了"
            elif not before["exists"]:
                status = "新增"
            elif before["sha8"] == after["sha8"]:
                status = "没动"
            else:
                status = "改了"
        out.append({"path": rel, "status": status, "before": before, "after": after})
    return out


def _snapshot_deliverables(card: dict) -> list:
    """认领时给交付物拍个快照（B4 的「before」）。"""
    files = []
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        try:
            p = deliverable_path(item)
        except ValueError:
            files.append({"path": rel, "exists": False, "bytes": 0, "sha8": None,
                          "rejected": True})
            continue
        if p.exists():
            files.append({"path": rel, "exists": True, "bytes": p.stat().st_size,
                          "sha8": sha8(p), "mtime_ms": int(p.stat().st_mtime * 1000)})
        else:
            files.append({"path": rel, "exists": False, "bytes": 0, "sha8": None})
    return files


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





# ---------- 卡字段编辑 / 人类移动 / 执行回退（2026-11-19，D-036）----------
#
# 这三条是 DSH 面板可用的最后三块拼图（T0 缺口 A1/A2/A6）。
# 共同约束：
#   · 都走事件流（edit / move / revert），⛔ 不直接改状态列
#   · 都支持 if_version 乐观并发（version 在 cards 表，随每次编辑 +1）
#   · 都只改白名单字段，⛔ 不允许任意 key 落库

EDITABLE_FIELDS = (
    "title", "goal", "territory", "deliverables", "accept_patterns",
    "human_gate", "engine", "model", "effort", "irreversible",
    "allow_no_numbers", "check_cmd", "max_cost_usd", "max_minutes",
    "blocked_by", "source_card",
)


def _check_transition(frm, to, actor):
    """状态转移守卫（内核版）。⛔ 不用 die，抛 ValueError 让调用方决定输出形态。"""
    if frm == to:
        return True, "no-op"
    rule = TRANSITIONS.get((frm, to))
    if rule is None:
        outs = [t for (f, t) in TRANSITIONS if f == frm]
        raise ValueError("非法状态转移：「%s」→「%s」（合法去向：%s）"
                         % (frm, to, "、".join(outs) if outs else "无，是终态"))
    if actor not in rule["actor"]:
        raise ValueError("越权：%s 不能把卡从「%s」推进到「%s」（只允许 %s）"
                         % (actor, frm, to, "/".join(sorted(rule["actor"]))))
    return True, "ok"


def edit_card(cid, fields, if_version=None, actor="human"):
    """改卡字段（白名单）。返回 (card, changed)。

    `if_version` 给了就必须与当前 version 相等，否则抛 ValueError——
    这是面板并发编辑的乐观锁（对应 taskboard 的 versionGuard）。
    """
    card = require_card(cid)
    if not isinstance(fields, dict) or not fields:
        raise ValueError("没有要改的字段")
    unknown = [k for k in fields if k not in EDITABLE_FIELDS]
    if unknown:
        raise ValueError("不允许改这些字段：%s（可改：%s）"
                         % ("、".join(unknown), "、".join(EDITABLE_FIELDS)))
    cur_ver = int(card.get("version") or 1)
    if if_version is not None and int(if_version) != cur_ver:
        raise ValueError("版本冲突：当前 version=%s，你带的是 %s（先 board show 重读）"
                         % (cur_ver, if_version))
    changed = {}
    for k, v in fields.items():
        if card.get(k) != v:
            changed[k] = {"from": card.get(k), "to": v}
            card[k] = v
    if not changed:
        return card, {}
    card["version"] = cur_ver + 1
    _store().save_card(card)
    append_event(cid, {"type": "edit", "actor": actor,
                       "version": card["version"], "changed": changed,
                       "idempotency_key": _idem("edit", cid, cur_ver,
                                                json.dumps(changed, sort_keys=True,
                                                           ensure_ascii=False))})
    return card, changed


def move_card(cid, to_state, actor="human", reason=None, if_version=None):
    """移动卡状态（人类/复核席）。`agent` 的常规路径仍走 claim/submit。

    为什么要单开一条命令：面板上人可以直接把卡拖到「已取消」「待返工」，
    这些边状态机允许，但没有一条 CLI 命令能触发（以前只能靠手改库）。
    """
    card = require_card(cid)
    st = replay(cid)
    if st["state"] == to_state:      # 同状态：幂等返回，⛔ 不写事件
        return {"id": cid, "from": st["state"], "to": to_state, "noop": True}
    _check_transition(st["state"], to_state, actor)
    if if_version is not None and int(if_version) != int(card.get("version") or 1):
        raise ValueError("版本冲突：当前 version=%s，你带的是 %s"
                         % (card.get("version"), if_version))
    ev = {"type": "move", "actor": actor, "to": to_state,
          "idempotency_key": _idem("move", cid, st["state"], to_state, reason or "")}
    if reason:
        ev["reason"] = str(reason)[:300]
    append_event(cid, ev)
    # 取消＝同时放掉租约，别留僵尸占卡（与 api_bulk 的 cancel 行为一致）
    if to_state == "已取消":
        release(cid)
    return {"id": cid, "from": st["state"], "to": to_state}


def revert_card(cid, reason, actor="system", seat=None):
    """执行失败/中断时把卡退回「待返工」。对应 T0 缺口 A6。

    ⛔ 这不是 review：不计返工次数、不需要复核凭据。
    它只是把卡从「进行中」放回池子，并释放租约。
    """
    card = require_card(cid)
    st = replay(cid)
    # ⚠️ 必须显式要求「进行中」：`_check_transition` 对同状态返回 no-op，
    #    于是「待返工」上再 revert 一次会被静默放行（2026-11-19 实测踩到）。
    if st["state"] != "进行中":
        raise ValueError("只有「进行中」的卡能回退，当前是「%s」" % st["state"])
    ev = {"type": "revert", "actor": actor,
          "reason": str(reason or "")[:500],
          "idempotency_key": _idem("revert", cid, st["state"], reason or "")}
    if seat:
        ev["seat"] = seat
    append_event(cid, ev)
    release(cid)
    return {"id": cid, "from": st["state"], "to": "待返工"}


# ---------- 事件流写入命令（2026-11-19，D-033）----------
#
# 这些是**内核的正式写命令**：把 comments / executions / checklist / 软删除
# 这类 append 型数据写进事件流，再由 fold 折叠出来。
#
# 为什么不放 cli：cli 只做参数解析与人话输出；判据与写入口必须在核心里，
# 否则服务器、MCP、面板各自实现一遍就会长出四套语义。

def _idem(prefix, *parts):
    """生成幂等键。同 (卡, 键) 重放只落一条事件。"""
    raw = "|".join(str(p) for p in parts if p not in (None, ""))
    return "%s:%s" % (prefix, hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16])


def add_comment(cid, body, actor="agent", seat=None, thread_id=None,
                comment_id=None, system_key=None, system_params=None,
                idempotency_key=None):
    """追加一条评论。返回事件。

    幂等：不传 `idempotency_key` 时按 (卡, 作者, 正文) 生成——
    agent 超时重试重发同一句不会出现两条。要发两条一样的话，显式给不同 key。
    """
    require_card(cid)
    body = (body or "").strip()
    if not body:
        raise ValueError("评论内容不能为空")
    key = idempotency_key or _idem("comment", cid, actor, seat, body)
    ev = {"type": "comment", "actor": actor, "body": body,
          "thread_id": thread_id or (seat or actor),
          "idempotency_key": key}
    if seat:
        ev["seat"] = seat
    if comment_id:
        ev["comment_id"] = comment_id
    if system_key:
        ev["system_key"] = system_key
    if system_params:
        ev["system_params"] = system_params
    return append_event(cid, ev)


def mark_comment_delivered(cid, comment_id, execution_id, idempotency_key=None):
    """标记评论已投递到某个执行。"""
    require_card(cid)
    return append_event(cid, {
        "type": "comment-delivered", "actor": "system",
        "comment_id": comment_id, "execution_id": execution_id,
        "idempotency_key": idempotency_key or _idem("cdel", cid, comment_id, execution_id),
    })


def open_execution(cid, seat=None, session_id=None, trigger="manual",
                   execution_id=None, idempotency_key=None):
    """开一条执行记录。已有在跑的同类执行时拒绝（一个会话同时只跑一件事）。"""
    require_card(cid)
    evs = load_journal(cid)
    if fold.running_execution(evs) is not None:
        raise ValueError("这张卡已有正在执行的记录；先 execution_close 再开新的")
    eid = execution_id or ("e-%s-%s" % (now_ms(), uuid.uuid4().hex[:6]))
    ev = {"type": "execution-open", "actor": "agent",
          "execution_id": eid, "trigger": trigger,
          "idempotency_key": idempotency_key or _idem("eopen", cid, eid)}
    if seat:
        ev["seat"] = seat
    if session_id:
        ev["session_id"] = session_id
    append_event(cid, ev)
    return eid


def touch_execution(cid, execution_id, idempotency_key=None):
    """记一次活动（心跳语义）。"""
    require_card(cid)
    return append_event(cid, {
        "type": "execution-activity", "actor": "agent",
        "execution_id": execution_id,
        "idempotency_key": idempotency_key or _idem("eact", cid, execution_id, now_ms()),
    })


def close_execution(cid, execution_id, outcome="succeeded", error=None,
                    report=None, idempotency_key=None):
    """结算一条执行记录。outcome: succeeded / failed / cancelled。"""
    require_card(cid)
    if outcome not in ("succeeded", "failed", "cancelled"):
        raise ValueError("outcome 只能是 succeeded / failed / cancelled，收到：%s" % outcome)
    ev = {"type": "execution-close", "actor": "agent",
          "execution_id": execution_id, "outcome": outcome,
          "idempotency_key": idempotency_key or _idem("eclose", cid, execution_id)}
    if error:
        ev["error"] = str(error)[:500]
    if report is not None:
        ev["report"] = report
    return append_event(cid, ev)


def attach_report(cid, execution_id, report, idempotency_key=None):
    """给执行记录附结构化报告（摘要/改动文件/自验/产物/风险）。"""
    require_card(cid)
    return append_event(cid, {
        "type": "execution-report", "actor": "agent",
        "execution_id": execution_id, "report": report,
        "idempotency_key": idempotency_key or _idem("ereport", cid, execution_id),
    })


def add_checklist(cid, text, item_id=None, seat=None, idempotency_key=None):
    """给验收清单加一项。"""
    require_card(cid)
    text = (text or "").strip()
    if not text:
        raise ValueError("清单项内容不能为空")
    kid = item_id or ("k-%s" % uuid.uuid4().hex[:8])
    ev = {"type": "checklist-add", "actor": "agent", "item_id": kid, "text": text,
          "idempotency_key": idempotency_key or _idem("kadd", cid, text)}
    if seat:
        ev["seat"] = seat
    append_event(cid, ev)
    return kid


def check_item(cid, item_id, checked=True, note=None, seat=None,
               idempotency_key=None):
    """勾选/取消勾选验收项。"""
    require_card(cid)
    evs = load_journal(cid)
    known = {i["id"] for i in fold.fold_checklist(evs)}
    if item_id not in known:
        raise ValueError("没有这一项：%s（现有 %s 项）" % (item_id, len(known)))
    ev = {"type": "checklist-check" if checked else "checklist-uncheck",
          "actor": "agent", "item_id": item_id,
          "idempotency_key": idempotency_key or _idem(
              "kchk" if checked else "kunchk", cid, item_id, seat)}
    if note:
        ev["note"] = str(note)[:400]
    if seat:
        ev["seat"] = seat
    return append_event(cid, ev)


def set_branch(cid, branch, repo="", idempotency_key=None):
    """记录 worktree 分支名（repo 为空＝根仓库）。branch 为空表示清除。"""
    require_card(cid)
    return append_event(cid, {
        "type": "branch-set", "actor": "agent", "repo": repo, "branch": branch,
        "idempotency_key": idempotency_key or _idem("branch", cid, repo, branch),
    })


def trash_card(cid, actor="human", reason=None, idempotency_key=None):
    """软删除（进回收站）。⛔ 不物理删除，事件流仍在。"""
    require_card(cid)
    evs = load_journal(cid)
    if fold.is_trashed(evs):
        return {"ok": True, "already": True, "trashed_at": fold.fold_trash(evs)[0]}
    ev = {"type": "trash", "actor": actor, "idempotency_key": idempotency_key or _idem("trash", cid)}
    if reason:
        ev["reason"] = str(reason)[:300]
    append_event(cid, ev)
    return {"ok": True, "already": False}


def restore_card(cid, actor="human", idempotency_key=None):
    """从回收站恢复。"""
    require_card(cid)
    return append_event(cid, {
        "type": "restore", "actor": actor,
        "idempotency_key": idempotency_key or _idem("restore", cid, now_ms()),
    })


def card_view(cid, since=None):
    """一张卡的完整视图：卡片字段 + 状态机 + 折叠投影 + 事件游标。

    面板、MCP、CLI 都用这一个函数取详情——**只有一个真相源**。
    `since` 给定时不返回全量投影（省带宽），只返回增量事件。
    """
    card = require_card(cid)
    evs = load_journal(cid)
    st = replay(cid, evs)
    out = {
        "id": cid,
        "state": st["state"],
        "holder": st["holder"],
        "epoch": st["epoch"],
        "seq": evs[-1]["seq"] if evs else 0,
        "version": int(card.get("version") or 1),
        "events": len(evs),
        "card": card,
    }
    if since is None:
        out.update(fold.fold_all(evs))
    else:
        out["events_delta"] = [e for e in evs if e["seq"] > int(since)]
        out["seq"] = evs[-1]["seq"] if evs else 0
    return out


# ---------- 调度：五语义（2026-11-19，D-037）----------
#
# 为什么内核要有调度（而不是留在面板插件里）：
#   DSH 停掉时，定时任务仍要能触发；否则「晚上跑一批」这件事就绑死在 GUI 上。
# 五语义（对应 T0 缺口 A9，删 scheduler.ts 的前置条件）：
#   ① 一次性任务触发后归一为「普通卡」，⛔ 不留有壳无触发的幽灵
#   ② 错过窗口要留痕（事件 + 评论），⛔ 不静默丢
#   ③ 死 cron 自动停用并留痕
#   ④ 依赖/预算不满足时窗口作废并留痕
#   ⑤ 触发失败（状态不对/卡不在）也留痕，不吞

MISS_GRACE_MS = 3600 * 1000        # 超过 1 小时没跑＝错过窗口


def _parse_every(spec: str) -> int:
    """把 30s / 10m / 2h / 1d 解析成毫秒。"""
    s = str(spec or "").strip().lower()
    if not s:
        raise ValueError("every 需要时长，如 30m / 2h / 1d")
    mult = {"s": 1000, "m": 60 * 1000, "h": 3600 * 1000, "d": 24 * 3600 * 1000}
    unit = s[-1]
    if unit not in mult:
        raise ValueError("时长单位只能是 s/m/h/d，收到：%s" % spec)
    try:
        n = float(s[:-1])
    except ValueError:
        raise ValueError("时长数值不合法：%s" % spec)
    if n <= 0:
        raise ValueError("时长必须大于 0")
    return int(n * mult[unit])


def _cron_field(spec: str, lo: int, hi: int) -> set:
    """解析单个 cron 字段：* / */n / a-b / a,b / 数字。"""
    out = set()
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
            if step <= 0:
                raise ValueError("cron 步长必须 > 0")
        if part in ("*", ""):
            a, b = lo, hi
        elif "-" in part:
            a_s, b_s = part.split("-", 1)
            a, b = int(a_s), int(b_s)
        else:
            a = b = int(part)
        if a < lo or b > hi or a > b:
            raise ValueError("cron 值越界：%s（允许 %s-%s）" % (part, lo, hi))
        out.update(range(a, b + 1, step))
    if not out:
        raise ValueError("cron 字段为空")
    return out


def _cron_next(expr: str, after_ms: int, max_days: int = 31):
    """算下一次触发时刻（毫秒）。最多向后找 max_days 天，找不到返回 None。

    ⚠️ 逐分钟扫描而不是字段跳跃：简单、可读、不会因夏令时/月长算错。
       代价是 31 天上限（44640 次迭代，实测几十毫秒）。
    """
    fields = str(expr).split()
    if len(fields) != 5:
        raise ValueError("cron 要 5 个字段：分 时 日 月 周，收到 %d 个" % len(fields))
    mins = _cron_field(fields[0], 0, 59)
    hours = _cron_field(fields[1], 0, 23)
    doms = _cron_field(fields[2], 1, 31)
    months = _cron_field(fields[3], 1, 12)
    dows = _cron_field(fields[4], 0, 6)
    t = (int(after_ms) // 60000 + 1) * 60000      # 下一分钟整
    limit = t + max_days * 24 * 3600 * 1000
    while t <= limit:
        dt = datetime.fromtimestamp(t / 1000.0)
        if (dt.minute in mins and dt.hour in hours and dt.day in doms
                and dt.month in months and (dt.weekday() + 1) % 7 in dows):
            return t
        t += 60000
    return None


def _next_fire(kind: str, spec: str, after_ms: int):
    if kind == "every":
        return int(after_ms) + _parse_every(spec)
    if kind == "cron":
        return _cron_next(spec, after_ms)
    if kind == "once":
        try:
            dt = datetime.fromisoformat(str(spec))
        except ValueError:
            raise ValueError("once 的时间格式要 ISO，如 2026-11-20T09:00")
        return int(dt.timestamp() * 1000)
    raise ValueError("kind 只能是 once / cron / every")


def set_schedule(cid, kind, spec, by="human", after_ms=None):
    """给卡设/改一条调度。返回 (kind, spec, next_ms)。"""
    require_card(cid)
    now = after_ms if after_ms is not None else now_ms()
    nxt = _next_fire(kind, spec, now)
    if nxt is None:
        raise ValueError("这个 cron 在未来 %d 天内没有触发点，拒绝写入" % 31)
    _store().schedule_upsert(cid, kind, str(spec), nxt, by=by)
    append_event(cid, {"type": "schedule-set", "actor": by, "kind": kind,
                       "spec": str(spec), "next_ms": nxt,
                       "idempotency_key": _idem("sched-set", cid, kind, spec, nxt)})
    return kind, str(spec), nxt


def clear_schedule(cid, by="human"):
    n = _store().schedule_delete(cid)
    if n:
        append_event(cid, {"type": "schedule-clear", "actor": by,
                           "idempotency_key": _idem("sched-clear", cid, now_ms())})
    return n


def tick(now=None):
    """触发到点的调度。返回逐条结果（给 CLI/JSON 用）。

    ⛔ 只发事件，不改卡状态：真正开工仍走 claim（租约红线）。
    """
    now = now if now is not None else now_ms()
    out = []
    for s in _store().schedules_due(now):
        cid = s["card_id"]
        card = get_card(cid)
        base = {"card": cid, "kind": s["kind"], "spec": s["spec"],
                "due_ms": s["next_ms"]}
        if card is None:
            _store().schedule_delete(cid)
            out.append({**base, "result": "card-gone", "note": "卡已不存在，调度删除"})
            continue
        st = replay(cid)
        missed = bool(now - int(s["next_ms"]) > MISS_GRACE_MS)
        reason = None
        if fold.is_trashed(load_journal(cid)):
            reason = "卡在回收站"
        elif st["state"] not in ("待认领", "待返工"):
            reason = "状态「%s」不可开工" % st["state"]
        else:
            blocked = withholding(cid, card)
            if blocked:
                reason = "；".join(blocked)
        if reason:
            # 语义②④⑤：任何跳过都留痕，⛔ 不静默
            append_event(cid, {
                "type": "schedule-skipped", "actor": "system",
                "reason": reason, "missed": missed,
                "due_ms": int(s["next_ms"]),
                "idempotency_key": _idem("sched-skip", cid, int(s["next_ms"]))})
            if s["kind"] != "every":
                add_comment(cid, "[系统] 定时到点但未执行：%s。" % reason,
                            actor="system", system_key="sys.schedSkip",
                            idempotency_key=_idem("sched-skip-c", cid, int(s["next_ms"])))
            out.append({**base, "result": "skipped", "reason": reason, "missed": missed})
        else:
            # 语义①：一次性触发后归一为普通卡（删调度）；周期则推进
            append_event(cid, {
                "type": "schedule-due", "actor": "system",
                "missed": missed, "due_ms": int(s["next_ms"]),
                "idempotency_key": _idem("sched-due", cid, int(s["next_ms"]))})
            if missed:
                add_comment(cid, "[系统] 定时窗口已错过（超过 1 小时），本次仍触发。",
                            actor="system", system_key="sys.schedMissed",
                            idempotency_key=_idem("sched-missed", cid, int(s["next_ms"])))
            out.append({**base, "result": "due", "missed": missed})
        # 推进或消费
        if s["kind"] == "once":
            _store().schedule_delete(cid)          # ① 不留幽灵
        else:
            try:
                nxt = _next_fire(s["kind"], s["spec"], now)
            except ValueError:
                nxt = None
            if nxt is None:
                _store().schedule_delete(cid)      # ③ 死 cron 停用
                append_event(cid, {"type": "schedule-dead", "actor": "system",
                                   "spec": s["spec"],
                                   "idempotency_key": _idem("sched-dead", cid, now)})
                add_comment(cid, "[系统] 定时表达式未来 31 天无触发点，已停用。",
                            actor="system", system_key="sys.schedDead")
                out[-1]["result"] = out[-1].get("result", "") + "+dead"
            else:
                _store().schedule_advance(cid, nxt, missed=1 if missed else 0)
    return out


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