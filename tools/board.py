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


# ---------- 命令 ----------

def cmd_init(a):
    CARDS.mkdir(parents=True, exist_ok=True)
    ok(f"看板已初始化：{BOARD}")


def cmd_new(a):
    CARDS.mkdir(parents=True, exist_ok=True)
    # 继承项目默认值：没指定就自动填，省掉手打模型名
    import projects as P
    defaults = P.project_defaults(ROOT) or {}
    eng = a.engine if a.engine and a.engine != "any" else defaults.get("engine", "any")
    mdl = a.model if a.model and a.model != "any" else defaults.get("model", "any")
    eft = a.effort if a.effort and a.effort != "any" else defaults.get("effort", "any")
    cid = a.id or f"C{datetime.now().strftime('%m%d')}-{uuid.uuid4().hex[:4]}"
    d = CARDS / cid
    if d.exists():
        die(f"卡片已存在：{cid}")
    d.mkdir(parents=True)
    (d / "artifacts").mkdir()
    (d / "evidence").mkdir()
    (d / "lease" / "active").mkdir(parents=True)
    card = {
        "id": cid, "title": a.title, "goal": a.goal or "",
        "territory": a.territory or [], "deliverables": a.deliverable or [],
        "accept_patterns": a.accept or [],
        "human_gate": a.human_gate,
        # —— 执行规格：谁来干、用什么模型、思考多深 ——
        "engine": eng,
        "model": mdl,
        "effort": eft,
        "created_at": ts(),
        "created_by": a.seat or "human",
        "created_kind": "agent" if a.seat and a.seat != "human" else "human",
        "irreversible": bool(a.irreversible),
        "source_card": getattr(a, "from_card", None),
    }
    jwrite(d / "card.json", card)
    append_event(cid, {"type": "created", "actor": card["created_kind"],
                       "seat": card["created_by"], "title": a.title,
                       "engine": card["engine"], "model": card["model"],
                       "effort": card["effort"], "human_gate": a.human_gate,
                       "from_card": card["source_card"]})
    who = "AI 发布" if card["created_kind"] == "agent" else "人建"
    ok(f"{who} {cid}：{a.title}")
    spec = []
    if card["engine"] != "any":
        spec.append(f"引擎={card['engine']}")
    if card["model"] != "any":
        spec.append(f"模型={card['model']}")
    if card["effort"] != "any":
        spec.append(f"思考={card['effort']}")
    if spec:
        print(f"  执行规格：{' / '.join(spec)}")
    print(f"  {d}")


def cmd_publish(a):
    """AI 发布任务入口。与 new 同源，但强制留发布者身份。"""
    if not a.seat or a.seat == "human":
        die("publish 必须带 --seat（你是哪个 agent）—— 发布者身份不可匿名")
    ns = argparse.Namespace(**vars(a))
    ns.seat = a.seat
    cmd_new(ns)
    ok(f"已登记发布者：{a.seat}（created_kind=agent）")


def cmd_ready(a):
    """agent 找活干：列出「待认领」且与我的引擎/模型/思考强度匹配的卡。"""
    if not CARDS.exists():
        print("（看板为空）")
        return
    hits = []
    for d in sorted(CARDS.iterdir()):
        if not d.is_dir():
            continue
        try:
            st = replay(d.name)
            card = jread(d / "card.json")
        except Exception:
            continue
        if st["state"] not in ("待认领", "阻塞"):
            continue
        miss = _match_miss(card, a.engine, a.model, a.effort)
        if miss:
            continue
        hits.append((st, card))
    if not hits:
        print(f"（没有匹配的活：引擎={a.engine or 'any'} 模型={a.model or 'any'} "
              f"思考={a.effort or 'any'}）")
        return
    print(f"{'ID':<12} {'引擎':<12} {'模型':<32} {'思考':<7} {'标题'}")
    print("-" * 92)
    for st, card in hits:
        print(f"{st['id']:<12} {card.get('engine','any'):<12} "
              f"{card.get('model','any'):<32} {card.get('effort','any'):<7} "
              f"{st['title'][:28]}")
    print(f"\n共 {len(hits)} 张可接")


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


def cmd_ls(a):
    if not CARDS.exists():
        print("（看板为空，先 board.py new）")
        return
    rows = []
    for d in sorted(CARDS.iterdir()):
        if not d.is_dir():
            continue
        try:
            st = replay(d.name)
        except Exception:
            continue
        if a.state and st["state"] != a.state:
            continue
        rows.append(st)
    if not rows:
        print("（无匹配卡片）")
        return
    order = {s: i for i, s in enumerate(STATES)}
    rows.sort(key=lambda r: (order.get(r["state"], 99), r["id"]))
    print(f"{'ID':<12} {'状态':<7} {'持有':<9} {'引擎':<10} {'模型':<22} {'思考':<6} {'标题'}")
    print("-" * 108)
    for r in rows:
        hold = r["holder"] or "-"
        mdl = (r["model"] if r["model"] != "any" else "-")[:20]
        print(f"{r['id']:<12} {r['state']:<7} {hold:<9} "
              f"{r['engine']:<10} {mdl:<22} {r['effort']:<6} {r['title'][:26]}")
    print(f"\n共 {len(rows)} 张")


def cmd_show(a):
    st = replay(a.id)
    card = jread(card_dir(a.id) / "card.json")
    print(f"\n【{st['id']}】{st['title']}")
    print(f"  状态    {st['state']}")
    print(f"  持有    {st['holder'] or '-'}")
    print(f"  引擎    {st['engine']}")
    print(f"  模型    {st['model']}")
    print(f"  思考    {st['effort']}")
    if st["holder"]:
        print(f"  实跑    {st['holder_model'] or '?'} / 思考 {st['holder_effort'] or '?'}")
    print(f"  发布    {st['created_by']}（{st['created_kind']}）")
    print(f"  人闸    {st['gate']}")
    print(f"  返工    {st['rework']} 次")
    if st["blocked_reason"]:
        print(f"  阻塞    {st['blocked_reason']}")
    if card.get("goal"):
        print(f"  目标    {card['goal']}")
    if card.get("territory"):
        print(f"  领地    {', '.join(card['territory'])}")
    if card.get("deliverables"):
        print(f"  交付    {', '.join(card['deliverables'])}")
    if st["submit"]:
        print(f"  提交    {st['submit'].get('note','')}")
    if st["review"]:
        print(f"  复核    {st['review'].get('verdict')} by {st['review'].get('seat')}")
    print(f"  事件    {st['events']} 条")
    if a.events:
        print("\n  事件流：")
        for ev in load_journal(a.id):
            print(f"    {ev['seq']:>3} {ev['at'][11:19]} {ev['type']:<14} {ev.get('seat','')}")


def cmd_claim(a):
    claim(a.id, a.seat, a.engine, a.model, a.effort)
    ok(f"认领成功：{a.id} → {a.seat}")
    print(f"  引擎={a.engine} 模型={a.model or 'any'} 思考={a.effort or 'any'}")
    print(f"  ⚠ 每 {HB_INTERVAL}s 内至少跑一次 beat，否则 {LEASE_TTL}s 后被回收")


def guard_transition(cid: str, to_state: str, actor: str):
    """状态转移守卫：不在白名单里的一律拒绝。

    ⚠️ 2026-10-20 修：TRANSITIONS 此前只是「定义」，从未被调用
    （opus 评审指出：任何状态下追加一条 human 事件都能直接变「完成」）。
    """
    st = replay(cid)
    frm = st["state"]
    if frm == to_state:
        return
    rule = TRANSITIONS.get((frm, to_state))
    if rule is None:
        die(f"非法状态转移：「{frm}」→「{to_state}」不在白名单里\n"
            f"  合法去向：{_legal_from(frm)}")
    if actor not in rule["actor"]:
        die(f"越权：{actor} 不能把卡从「{frm}」推进到「{to_state}」\n"
            f"  该转移只允许：{'/'.join(sorted(rule['actor']))}")


def _legal_from(state: str) -> str:
    outs = [t for (f, t) in TRANSITIONS if f == state]
    return "、".join(outs) if outs else "（无，是终态）"


def guard_holder(cid: str, seat: str):
    """确认你是当前租约持有者，且 epoch 未被回收重置。

    防的是：长任务执行中租约超时被别人回收接手，旧执行者回来提交，
    把别人的活覆盖掉（opus 评审指出）。
    """
    lease = active_lease(cid)
    if not lease:
        die("你没有活跃租约（可能已被回收）")
    owner = _lease_owner(lease)
    if owner.get("seat") != seat:
        die(f"卡片已归 {owner.get('seat')}（你的租约已被回收）")
    st = replay(cid)
    return st.get("epoch", 0)


def _lease_epoch(lease) -> int:
    try:
        return int(_lease_owner(lease).get("epoch", 0))
    except Exception:
        return 0


def cmd_beat(a):
    heartbeat(a.id, a.seat)


def cmd_block(a):
    guard_transition(a.id, "阻塞", "agent")
    st = replay(a.id)
    if st["holder"] != a.seat:
        die(f"你不是持有者（当前 {st['holder']}）")
    append_event(a.id, {"type": "block", "actor": "agent", "seat": a.seat, "reason": a.reason})
    ok(f"已阻塞：{a.reason}")


def cmd_submit(a):
    st = replay(a.id)
    if st["holder"] != a.seat:
        die(f"你不是持有者（当前 {st['holder']}）")
    card = jread(card_dir(a.id) / "card.json")
    # 提交即跑 L1-L3
    ok1, p1, r1 = gate_l1(a.id, card)
    ok2, p2 = gate_l2(a.id, card)
    ok3, p3, c3 = gate_l3(a.id, card)
    problems = p1 + p2 + p3
    verdict = "pass" if (ok1 and ok2 and ok3) else "fail"
    append_event(a.id, {
        "type": "submit", "actor": "agent", "seat": a.seat, "note": a.note or "",
        "gate": {"L1": ok1, "L2": ok2, "L3": ok3, "problems": problems, "files": r1},
        "exit_code_note": "退出码不参与判定（权重 0）",
    })
    if verdict == "pass":
        ok("L1-L3 全过 → 待验收")
        for r in r1:
            print(f"  {r['path']}  {r.get('bytes','?')}B  sha8={r.get('sha8','-')}")
    else:
        print("✗ 闸门未过，已记录但不进「待验收」：")
        for p in problems:
            print(f"  · {p}")
        append_event(a.id, {"type": "block", "actor": "system", "seat": "system",
                            "reason": "闸门未过：" + "；".join(problems[:3])})


def cmd_verify(a):
    guard_transition(a.id, "核验中", "review")
    st = replay(a.id)
    if st["state"] != "待验收":
        die(f"当前状态「{st['state']}」，需先 submit")
    card = jread(card_dir(a.id) / "card.json")
    ok1, p1, r1 = gate_l1(a.id, card)
    ok2, p2 = gate_l2(a.id, card)
    ok3, p3, c3 = gate_l3(a.id, card)
    append_event(a.id, {"type": "verify", "actor": "review", "seat": a.seat or "review",
                        "L1": ok1, "L2": ok2, "L3": ok3,
                        "problems": p1 + p2 + p3})
    print(f"L1 产物存在  {'PASS' if ok1 else 'FAIL'}")
    print(f"L2 形制      {'PASS' if ok2 else 'FAIL'}")
    print(f"L3 内容闸门  {'PASS' if ok3 else 'FAIL'}")
    for p in p1 + p2 + p3:
        print(f"  · {p}")
    ok("已进「核验中」，待复核席给结论")


def cmd_review(a):
    guard_transition(a.id, "完成" if a.verdict == "pass" else "待返工", "review")
    st = replay(a.id)
    if st["state"] not in ("核验中", "待验收"):
        die(f"当前状态「{st['state']}」，不可复核")
    # 红线①（加固）：机器闸未过就不许给 PASS
    last_verify = None
    for ev in load_journal(a.id):
        if ev.get("type") == "verify":
            last_verify = ev
    if a.verdict == "pass" and last_verify and last_verify.get("problems"):
        die("机器闸有未解决问题，⛔ 不许直接给 PASS：\n  "
            + "\n  ".join(str(p) for p in last_verify["problems"][:5])
            + "\n  先修好再复核，或给 --verdict fail")
    # 红线①：复核席不得是执行者
    executor = (st["submit"] or {}).get("seat") or st["holder"]
    if a.seat == executor:
        die(f"复核席不得是执行席本人（{executor}）—— 红线①：完成必须异会话")
    # 红线①（加固）：复核必须留下可复跑的凭据 —— 声明自己跑了什么、看到什么
    if not a.evidence:
        die("复核必须带 --evidence（你实际跑过的命令与其读数）。"
            "空口 PASS 不可入正档 —— 见 AGENTS.md §1.2 反空跑")
    ev_ok, ev_why = _check_evidence(a.evidence)
    if not ev_ok:
        die(f"复核凭据不合格：{ev_why}")
    if st["gate"] in ("both", "before_done") and a.verdict == "pass":
        append_event(a.id, {"type": "review", "actor": "review", "seat": a.seat,
                            "verdict": a.verdict, "note": a.note or "",
                            "evidence": a.evidence, "evidence_ok": True})
        append_event(a.id, {"type": "request_human", "actor": "review", "seat": a.seat})
        release(a.id)
        ok("复核通过 → 已转「拍板中」，等人拍板")
        return
    append_event(a.id, {"type": "review", "actor": "review", "seat": a.seat,
                        "verdict": a.verdict, "note": a.note or "",
                        "evidence": a.evidence, "evidence_ok": True})
    if a.verdict == "pass":
        release(a.id)
        ok("复核 PASS → 完成")
    else:
        release(a.id)
        ok("复核 FAIL → 打回「进行中」")


def _check_evidence(ev: str) -> tuple:
    """复核凭据的最低可判标准：必须含命令、含数字读数。"""
    if len(ev.strip()) < 12:
        return False, "凭据太短（<12 字符），看不出你跑了什么"
    if not re.search(r"[A-Za-z_][\w\.\-]*", ev):
        return False, "凭据里没有可识别的命令/字段名"
    if not re.search(r"\d", ev):
        return False, "凭据里没有任何数字读数 —— 反空跑要求有非零计数"
    return True, ""


def human_token() -> Path:
    """人 token 放在看板目录之外，agent 指令里明令不碰。"""
    return Path.home() / ".board-human.tok"


def human_token_sha() -> Path:
    """令牌哈希存在看板里。只存哈希 ⇒ 读到它推不出原令牌。"""
    return BOARD / ".human-token.sha"


def _verify_human_token() -> tuple:
    """校验人令牌。返回 (ok, 原因)。

    防线（诚实标注：这是**提高门槛**，不是绝对强制，见 AGENTS.md §4.1）：
      1. 令牌文件必须存在且内容非空（⛔ 0 字节放行）
      2. 内容长度 ≥ 16（⛔ 一眼能猜的短串）
      3. 与首次登记时存的 sha256 一致（换令牌 = 留痕）
    """
    tok = human_token()
    if not tok.exists():
        return False, f"缺人令牌。首次使用请创建：{tok}（内容随意，⛔ 不要给 agent）"
    try:
        content = tok.read_text(encoding="utf-8").strip()
    except Exception as e:
        return False, f"人令牌读不了：{e}"
    if not content:
        return False, "人令牌是空的 —— ⛔ 空文件不算令牌（这是本条防线要防的）"
    if len(content) < 16:
        return False, f"人令牌太短（{len(content)} < 16 字符）—— 换一个长一点的"
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    reg = human_token_sha()
    if not reg.exists():
        return True, ""          # 首次登记，下方写入
    try:
        expected = reg.read_text(encoding="utf-8").strip()
    except Exception:
        return False, "令牌登记文件读不了"
    if sha != expected:
        return False, ("人令牌已变更（与登记哈希不符）。"
                       "若这是你本人换的，删掉 board/.human-token.sha 重新登记；否则是有人动了令牌")
    return True, ""


def cmd_human(a):
    # 红线②：唯一能推进人位的入口
    guard_transition(a.id, "完成" if a.decision == "approve" else "待返工", "human")
    ok_tok, why = _verify_human_token()
    if not ok_tok:
        die(why)
    # 首次登记令牌哈希（只存哈希，推不出原值）
    if not human_token_sha().exists():
        content = human_token().read_text(encoding="utf-8").strip()
        human_token_sha().write_text(
            hashlib.sha256(content.encode("utf-8")).hexdigest(), encoding="utf-8")
        print(f"  · 已登记人令牌哈希 → {human_token_sha()}")
    st = replay(a.id)
    if st["state"] != "拍板中":
        die(f"当前状态「{st['state']}」，只有「拍板中」的卡需要人拍")
    append_event(a.id, {"type": "human", "actor": "human", "who": a.who or "owner",
                        "decision": a.decision, "note": a.note or ""})
    ok(f"人已{a.decision}：{a.id}")

def cmd_reclaim(a):
    n = 0
    for d in CARDS.iterdir() if CARDS.exists() else []:
        if not d.is_dir():
            continue
        lease = d / "lease" / "active"
        if not lease.exists():
            continue
        for old in list(lease.iterdir()):
            if not old.is_dir():
                continue
            try:
                hb = jread(old / "owner.json").get("at_ms", 0)
            except Exception:
                hb = 0
            age = (now_ms() - hb) / 1000
            if age > LEASE_TTL:
                dest = d / "lease" / "reclaimed"
                dest.mkdir(parents=True, exist_ok=True)
                try:
                    os.replace(old, dest / old.name)
                except OSError:
                    continue
                jwrite(dest / old.name / "reclaim.json",
                       {"reclaimed_at": ts(), "reason": "heartbeat timeout",
                        "timeout_s": LEASE_TTL, "previous_owner": old.name})
                append_event(d.name, {"type": "reclaim", "seat": "system",
                                      "previous": old.name, "age_s": int(age)})
                print(f"  · 回收 {d.name}：{old.name}（{int(age)}s 无心跳）")
                n += 1
    ok(f"回收完成：{n} 个")


def cmd_audit(a):
    """检测绕过 CLI 直接改文件的行为。"""
    issues = []
    for d in sorted(CARDS.iterdir()) if CARDS.exists() else []:
        if not d.is_dir():
            continue
        # 0) 哈希链校验（整份重写/插入/改内容都会断链）
        chain_ok, chain_why = verify_chain(d.name)
        if not chain_ok:
            issues.append(f"{d.name}: 哈希链断裂 ← {chain_why}")
        try:
            st = replay(d.name)
        except Exception as e:
            issues.append(f"{d.name}: journal 无法重放（{e}）")
            continue
        card = jread(d / "card.json")
        # 1) 完成但没有复核记录
        if st["state"] == "完成" and not st["review"]:
            issues.append(f"{d.name}: 状态=完成 但无复核记录")
        # 2) 完成但复核席==执行席
        if st["review"] and st["submit"]:
            if st["review"].get("seat") == st["submit"].get("seat"):
                issues.append(f"{d.name}: 复核席与执行席同一人")
        # 2b) 复核无凭据（疑似手写 journal 绕过 CLI）—— 红线①的可判形制
        if st["review"] and not st["review"].get("evidence"):
            issues.append(f"{d.name}: 复核记录缺 evidence 字段 ← 疑似绕过 CLI 手写 journal")
        # 2c) 提交记录缺闸门读数（同上）
        if st["submit"] and "gate" not in st["submit"]:
            issues.append(f"{d.name}: 提交记录缺 gate 读数 ← 疑似绕过 CLI")
        # 3) 人闸卡在完成但无人拍板
        if st["state"] == "完成" and st["gate"] in ("both", "before_done") and not st["human"]:
            issues.append(f"{d.name}: 人闸卡已「完成」但无人工记录 ← 疑似绕过")
        # 4) 活跃租约 >1
        lease = d / "lease" / "active"
        if lease.exists():
            act = [x for x in lease.iterdir() if x.is_dir()]
            if len(act) > 1:
                issues.append(f"{d.name}: 活跃租约 {len(act)} 个（应 ≤1）")
        # 4b) 租约目录名必须是固定名（旧版带 uuid 的会破坏原子性）
        if lease.exists():
            for x in lease.iterdir():
                if x.is_dir() and x.name != LEASE_NAME:
                    issues.append(f"{d.name}: 租约目录名非固定名「{x.name}」← 旧版残留，原子性不成立")
        # 5) 交付物缺失但已提交
        if st["state"] in ("待验收", "核验中", "完成"):
            for item in card.get("deliverables", []):
                rel = item if isinstance(item, str) else item.get("path")
                p = (WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
                if not p.exists():
                    issues.append(f"{d.name}: 交付物已丢 {rel}")
    if issues:
        print(f"✗ 发现 {len(issues)} 个问题：")
        for i in issues:
            print(f"  · {i}")
        sys.exit(2)
    ok("审计通过：无绕过痕迹")


def cmd_html(a):
    """生成静态看板页（单项目）。双击即可看。"""
    import render as RD
    cards = []
    for d in sorted(CARDS.iterdir()) if CARDS.exists() else []:
        if not d.is_dir():
            continue
        try:
            st = replay(d.name)
            card = jread(d / "card.json")
        except Exception:
            continue
        st["goal"] = card.get("goal", "")
        st["deliverables"] = card.get("deliverables", [])
        cards.append(st)

    out = BOARD / "board.html"
    name = ROOT.name
    RD.render_project(cards, f"看板 · {name}", out, project_name=name,
                      has_overview=True)
    ok(f"看板已生成：{out}")
    print(f"  共 {len(cards)} 张卡")
    return out


def cmd_overview(a):
    """跨项目总览页。"""
    import render as RD
    import projects as P
    out = Path.home() / ".allworktogether" / "overview.html"
    ps = P.project_summary()
    RD.render_all(ps, out)
    ok(f"总览已生成：{out}")
    for p in ps:
        print(f"  {p['name']:<20} {p.get('cards', 0):>3} 张")


def cmd_project(a):
    """项目管理：add / ls / rm / default。"""
    import projects as P
    if a.action == "ls":
        ps = P.list_projects()
        if not ps:
            print("（还没有登记任何项目）")
            print(f"  注册表：{P.REGISTRY}")
            return
        print(f"{'':2} {'项目':<20} {'卡片':>4}  {'默认引擎/模型':<38} 路径")
        print("-" * 96)
        for p in ps:
            mark = "✓" if p["exists"] else "✗"
            cp = P.cards_path(p["path"])
            n = len([d for d in cp.iterdir() if d.is_dir()]) if cp.exists() else 0
            d = p.get("defaults") or {}
            spec = f"{d.get('engine','—')}/{d.get('model','—')}"
            print(f"{mark:2} {p['name']:<20} {n:>4}  {spec:<38} {p['path']}")
        print(f"\n共 {len(ps)} 个项目 ｜ 注册表：{P.REGISTRY}")
        return

    if a.action == "add":
        target = a.path or str(Path.cwd())
        entry = P.add_project(target, a.name)
        P.ensure_root(Path(entry["path"]))
        ok(f"已登记：{entry['name']} → {entry['path']}")
        return

    if a.action == "rm":
        if not a.name:
            die("需要 --name（或路径）")
        if P.remove_project(a.name):
            ok(f"已移除登记：{a.name}（⛔ 磁盘数据未动）")
        else:
            die(f"没找到：{a.name}")
        return

    if a.action == "default":
        entry = P.add_project(ROOT)
        d = entry.setdefault("defaults", {})
        if a.engine:
            d["engine"] = a.engine
        if a.model:
            d["model"] = a.model
        if a.effort:
            d["effort"] = a.effort
        # 写回
        reg = P._load_registry()
        for p in reg["projects"]:
            if Path(p["path"]).resolve() == ROOT.resolve():
                p["defaults"] = d
                if getattr(a, "workspace", None):
                    ws = Path(a.workspace)
                    if not ws.exists():
                        die(f"工作区不存在：{ws}")
                    p["workspace"] = str(ws.resolve())
        P._save_registry(reg)
        wsd = P.workspace_of(ROOT)
        ok(f"本项目默认值：引擎={d.get('engine','—')} 模型={d.get('model','—')} "
           f"思考={d.get('effort','—')}")
        print(f"  工作区：{wsd}")
        return


def cmd_bare(a):
    """不带子命令时：给一个能直接用的面板，而不是报错。"""
    print(f"📋 {ROOT.name}")
    print(f"   {ROOT}\n")

    if not CARDS.exists() or not any(d.is_dir() for d in CARDS.iterdir()):
        print("   还没有任何卡。\n")
        print("   下一步：")
        print("     board add --title \"要做什么\" --goal \"具体目标\"")
        print("     board project default --engine opencode "
              "--model opencode-go/deepseek-v4.1-flash")
        return

    counts = {}
    total = 0
    for d in CARDS.iterdir():
        if not d.is_dir():
            continue
        try:
            st = replay(d.name)
        except Exception:
            continue
        total += 1
        counts[st["state"]] = counts.get(st["state"], 0) + 1

    order = ["待认领", "进行中", "待返工", "阻塞", "待验收", "核验中", "拍板中", "完成"]
    bits = [f"{s} {counts[s]}" for s in order if counts.get(s)]
    print(f"   {total} 张卡：  " + " ｜ ".join(bits))

    # 最该做的事
    if counts.get("拍板中"):
        print(f"\n   ⚠ {counts['拍板中']} 张等你拍板：board human <卡号> --decision approve")
    if counts.get("待认领") or counts.get("待返工"):
        print("\n   下一步：board open --show 看板  或  "
              "python tools/orchestrator.py run --max 5 让它自己跑")
    elif counts.get("完成") == total:
        print("\n   全部完成 🎉   下一步：board add 建新卡")
    print()


def cmd_stats(a):
    """各状态几张、完成率。"""
    if not CARDS.exists():
        print("（看板为空）")
        return
    counts, total = {}, 0
    for d in CARDS.iterdir():
        if not d.is_dir():
            continue
        try:
            st = replay(d.name)
        except Exception:
            continue
        total += 1
        counts[st["state"]] = counts.get(st["state"], 0) + 1
    print(f"项目：{ROOT.name}  （{ROOT}）")
    if a.workspace:
        print(f"工作区：{WORKSPACE}")
    print(f"共 {total} 张卡\n")
    for s in STATES:
        n = counts.get(s, 0)
        if n:
            print(f"  {s:<6} {n:>3}  {'█' * min(n, 30)}")
    if total:
        done = counts.get("完成", 0)
        print(f"\n完成率 {done}/{total} = {done / total * 100:.0f}%")


def cmd_cost(a):
    """用量统计：token + 缓存 + 花费。只统计引擎真的报了数的（⛔ 不假装 0）。"""
    if not CARDS.exists():
        print("（看板为空）")
        return

    def newagg():
        return {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0,
                "cache_write": 0, "cost": 0.0, "calls": 0, "unavailable": 0}

    total = newagg()
    by_card, by_model = {}, {}

    for d in sorted(CARDS.iterdir()):
        if not d.is_dir():
            continue
        for ev in load_journal(d.name):
            if ev.get("type") != "usage":
                continue
            u = ev.get("usage") or {}
            key_card = d.name
            key_model = ev.get("model") or ev.get("engine") or "?"
            for bucket, key in ((by_card, key_card), (by_model, key_model)):
                a_ = bucket.setdefault(key, newagg())
                if not u.get("available"):
                    a_["unavailable"] += 1
                    a_["calls"] += 1
                    continue
                for f in ("input", "output", "reasoning", "cache_read", "cache_write"):
                    a_[f] += int(u.get(f) or 0)
                a_["cost"] += float(u.get("cost") or 0)
                a_["calls"] += 1
            if u.get("available"):
                for f in ("input", "output", "reasoning", "cache_read", "cache_write"):
                    total[f] += int(u.get(f) or 0)
                total["cost"] += float(u.get("cost") or 0)
                total["calls"] += 1
            else:
                total["unavailable"] += 1
                total["calls"] += 1

    def line(label, a_):
        cache = a_["cache_read"] + a_["cache_write"]
        return (f"{label:<22} {a_['calls']:>4} 次  "
                f"入 {a_['input']:>9,}  出 {a_['output']:>8,}  "
                f"缓存 {cache:>9,}  花费 ${a_['cost']:.4f}")

    print(f"项目：{ROOT.name}")
    print()
    if not total["calls"]:
        print("  还没有用量记录（跑过编排器后才有）")
        return
    print(line("合计", total))
    if total["unavailable"]:
        print(f"  ⚠ {total['unavailable']} 次调用引擎没报用量（已标『未知』，未计入 0）")
    print()
    print("按模型：")
    for k, v in sorted(by_model.items(), key=lambda x: -x[1]["input"]):
        print("  " + line(k[-40:], v))
    if a.per_card:
        print()
        print("按卡片：")
        for k, v in sorted(by_card.items(), key=lambda x: -x[1]["input"]):
            print("  " + line(k, v))


def cmd_open(a):
    """打开/刷新看板页。最常用的一条命令。"""
    cmd_html(a)
    out = BOARD / "board.html"
    print(f"\n  {out}")
    if a.show:
        try:
            import webbrowser
            webbrowser.open(out.as_uri())
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(
        prog="board",
        description="单人用的多 agent 编排看板（多项目）",
        epilog="最常用：board ls ｜ board open ｜ board add --title ... ｜ board human <卡号>")
    p.add_argument("-C", "--root", help="指定项目目录（默认从当前目录向上找）")
    p.add_argument("-p", "--project", help="按注册表里的项目名切换")
    sub = p.add_subparsers(dest="cmd", required=False)

    s = sub.add_parser("init", help="初始化看板")
    s.set_defaults(f=cmd_init)

    s = sub.add_parser("project", help="项目管理：add / ls / rm / default")
    s.add_argument("action", choices=["add", "ls", "rm", "default"])
    s.add_argument("path", nargs="?")
    s.add_argument("--name")
    s.add_argument("--engine")
    s.add_argument("--model")
    s.add_argument("--effort")
    s.add_argument("--workspace", help="指定 agent 干活的工作区（默认＝项目根）")
    s.set_defaults(f=cmd_project)

    s = sub.add_parser("stats", help="一眼看数字")
    s.add_argument("--workspace", action="store_true", help="同时显示工作区")
    s.set_defaults(f=cmd_stats)

    s = sub.add_parser("cost", help="用量统计（token/缓存/花费）")
    s.add_argument("--per-card", action="store_true", help="按卡片细分")
    s.set_defaults(f=cmd_cost)

    s = sub.add_parser("open", help="生成并打开看板页（最常用）")
    s.add_argument("--show", action="store_true", help="生成后自动用浏览器打开")
    s.set_defaults(f=cmd_open)

    s = sub.add_parser("add", help="建卡（人建，等价于 new）")
    s.add_argument("--title", required=True)
    s.add_argument("--goal")
    s.add_argument("--territory", nargs="*", help="可写领地（路径）")
    s.add_argument("--deliverable", nargs="*", help="交付物路径")
    s.add_argument("--accept", nargs="*", help="L3 必含项（正则）")
    s.add_argument("--human-gate", default="none",
                   choices=["none", "before_done", "both"], help="人闸档位")
    s.add_argument("--irreversible", action="store_true", help="不可逆动作类（建议强制人闸）")
    s.add_argument("--engine", default="any",
                   help="指定 agent 框架：codex/opencode/qoderclicn/hermes/any")
    s.add_argument("--model", default="any", help="指定模型（如 deepseek-v4.1-flash）")
    s.add_argument("--effort", default="any",
                   help="思考强度：low/medium/high/max/any")
    s.add_argument("--id")
    s.add_argument("--seat")
    s.set_defaults(f=cmd_new)

    # new 是 add 的别名（保持旧脚本可用）
    s = sub.add_parser("new", help="建卡（add 的别名）")
    s.add_argument("--title", required=True)
    s.add_argument("--goal")
    s.add_argument("--territory", nargs="*")
    s.add_argument("--deliverable", nargs="*")
    s.add_argument("--accept", nargs="*")
    s.add_argument("--human-gate", default="none",
                   choices=["none", "before_done", "both"])
    s.add_argument("--irreversible", action="store_true")
    s.add_argument("--engine", default="any")
    s.add_argument("--model", default="any")
    s.add_argument("--effort", default="any")
    s.add_argument("--id")
    s.add_argument("--seat")
    s.set_defaults(f=cmd_new)

    s = sub.add_parser("publish", help="AI 发布任务（必须带 --seat）")
    s.add_argument("--title", required=True)
    s.add_argument("--goal")
    s.add_argument("--territory", nargs="*")
    s.add_argument("--deliverable", nargs="*")
    s.add_argument("--accept", nargs="*")
    s.add_argument("--human-gate", default="none",
                   choices=["none", "before_done", "both"])
    s.add_argument("--irreversible", action="store_true")
    s.add_argument("--engine", default="any")
    s.add_argument("--model", default="any")
    s.add_argument("--effort", default="any")
    s.add_argument("--id")
    s.add_argument("--seat", required=True, help="发布者身份（不可匿名）")
    s.add_argument("--from-card", help="由哪张卡派生")
    s.set_defaults(f=cmd_publish)

    s = sub.add_parser("ready", help="找我能干的活（按引擎/模型/思考强度匹配）")
    s.add_argument("--engine", default=None)
    s.add_argument("--model", default=None)
    s.add_argument("--effort", default=None)
    s.set_defaults(f=cmd_ready)

    s = sub.add_parser("ls", help="列卡")
    s.add_argument("--state")
    s.set_defaults(f=cmd_ls)

    s = sub.add_parser("show", help="看一张卡")
    s.add_argument("id")
    s.add_argument("--events", action="store_true")
    s.set_defaults(f=cmd_show)

    s = sub.add_parser("claim", help="认领（原子 + 规格匹配）")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--engine", default="any")
    s.add_argument("--model", default=None)
    s.add_argument("--effort", default=None)
    s.set_defaults(f=cmd_claim)

    s = sub.add_parser("beat", help="心跳")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.set_defaults(f=cmd_beat)

    s = sub.add_parser("block", help="报阻塞")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(f=cmd_block)

    s = sub.add_parser("submit", help="提交（自动跑 L1-L3）")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--note")
    s.set_defaults(f=cmd_submit)

    s = sub.add_parser("verify", help="复核席跑机器闸")
    s.add_argument("id")
    s.add_argument("--seat")
    s.set_defaults(f=cmd_verify)

    s = sub.add_parser("review", help="复核结论（必须异会话 + 带凭据）")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--verdict", required=True, choices=["pass", "fail"])
    s.add_argument("--evidence", required=True,
                   help="你实际跑的命令与读数（必须有数字，反空跑）")
    s.add_argument("--note")
    s.set_defaults(f=cmd_review)

    s = sub.add_parser("human", help="人拍板（需 token）")
    s.add_argument("id")
    s.add_argument("--decision", required=True, choices=["approve", "reject"])
    s.add_argument("--who")
    s.add_argument("--note")
    s.set_defaults(f=cmd_human)

    s = sub.add_parser("reclaim", help="回收超时租约")
    s.set_defaults(f=cmd_reclaim)

    s = sub.add_parser("audit", help="查绕过痕迹")
    s.set_defaults(f=cmd_audit)

    s = sub.add_parser("html", help="生成看板页")
    s.set_defaults(f=cmd_html)

    s = sub.add_parser("overview", help="跨项目总览页")
    s.set_defaults(f=cmd_overview)

    a = p.parse_args()

    # 多项目解析：--root > --project > 自动向上找 > 当前目录
    import projects as P
    if a.project:
        entry = P.find_project(a.project)
        if not entry:
            die(f"没找到项目「{a.project}」。用 board project ls 看已登记的")
        if not Path(entry["path"]).exists():
            die(f"项目目录不存在：{entry['path']}")
        root = Path(entry["path"])
    else:
        root = P.resolve_root(a.root)

    set_root(root)
    P.ensure_root(root)
    # 项目工作区：注册表里设了就切过去（agent 在这里干活）
    set_workspace(P.workspace_of(root))
    if not a.cmd:
        return cmd_bare(a)
    a.f(a)


if __name__ == "__main__":
    main()
