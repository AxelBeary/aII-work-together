#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server.py — 本地网页界面（零依赖，只用标准库）

设计取舍：
  · 只监听 127.0.0.1 —— 不对外暴露，别人访问不到
  · 零依赖：http.server + 手写 JSON 接口，⛔ 不引 Flask/FastAPI
  · 页面是单文件 HTML（内联 CSS/JS），不需要构建步骤
  · 所有写操作都走 board.py 的同一套函数 ⇒ 红线不会因为「多了个界面」而绕开

接口（全部本地）：
  GET  /api/state?project=      项目列表 + 当前项目概况
  GET  /api/cards?project=      卡片列表（含用量/门禁摘要）
  GET  /api/card?project=&id=   单卡详情 + 事件流
  GET  /api/cost?project=       用量汇总
  POST /api/card                建卡
  POST /api/human               人拍板（approve/reject）
  POST /api/run                 跑一轮编排（后台子进程）
  GET  /api/run/log             看运行输出

启动：python tools/server.py [--port 8777] [--open]
"""
import argparse
import json
import os
import secrets
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B          # noqa: E402
import projects as P       # noqa: E402

UI = Path(__file__).resolve().parent / "ui.html"

# 跨项目总览用的伪项目名（不是真目录）
ALL_PROJECTS = "__all__"

# 后端自证（给外壳比对用）：进程号和「这份代码的 mtime」
_STARTED_AT = time.strftime("%Y-%m-%d %H:%M:%S")
_CODE_MTIME = int(Path(__file__).stat().st_mtime)

_run_lock = threading.Lock()
_run_state = {"running": False, "project": None, "started": None}
_run_log_path = ROOT / "board" / "ui-run.log"

# ---------- 安全边界（2026-10-21 安全扫描 F-01／F-12）----------
# 「只监听 127.0.0.1」挡不住三件事：本机任意进程、用户浏览器里的任意网页
# （localhost 是网页可写的目标）、DNS rebinding（Host 头不校验）。
# 因此：
#   · 每个请求的 Host 必须是回环地址（挡 rebinding）；
#   · 所有写接口（POST）必须带页面注入的会话令牌（挡跨站「简单请求」CSRF）；
#   · 请求体上限 1MB、读超时 10s、池满回 503（挡慢连接把界面占死）。
_TOKEN = secrets.token_urlsafe(24)
_TOKEN_FILE = ROOT / "board" / "ui-server.tok"
_MAX_BODY = 1 << 20
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _safe_msg(e) -> str:
    """回给客户端的错误文案：去掉家目录绝对路径（安全扫描 F-16）。"""
    s = str(e)
    home = str(Path.home())
    if home and home in s:
        s = s.replace(home, "~")
    return s[:300]


def _host_ok(host_header: str) -> bool:
    h = (host_header or "").strip().lower()
    if h.startswith("["):                 # [::1]:8777
        h = h.split("]")[0] + "]"
    else:
        h = h.split(":")[0]
    return h in _LOCAL_HOSTS

# ⚠️ 所有看板访问必须在这个锁里做。
# 原因：board.py 的项目根是模块级全局（B.set_root），而这里是一请求一线程。
# 不锁的后果是实测过的——两个项目并发建卡会互相串（卡建到别的项目、同号静默覆盖）。
# 单人本地界面，串行化完全够用；要真并发得把项目根改成上下文变量，那是另一件事。
_BOARD_LOCK = threading.RLock()


# ---------- 数据整形 ----------

def _log_bytes(cid: str) -> int:
    try:
        p = B.card_dir(cid) / "run.log"
        return p.stat().st_size if p.exists() else 0
    except Exception:
        return 0


def _card_view(cid: str, light: bool = False) -> dict | None:
    try:
        events = B.load_journal(cid)      # 一份日志只读一次，重放也复用它
        st = B.replay(cid, events=events)
        card = B.get_card(cid) or {}
    except SystemExit:
        return None
    usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
             "cost": 0.0, "available": False}
    submit = st.get("submit") or {}
    seats, unfixed = [], None
    for ev in events:
        t = ev.get("type")
        if t == "usage" and not light:
            u = ev.get("usage") or {}
            if u.get("available"):
                usage["available"] = True
                for k in ("input", "output", "cache_read", "cache_write"):
                    usage[k] += int(u.get(k) or 0)
                usage["cost"] += float(u.get("cost") or 0)
        elif t == "consult_reply":
            seats.append({"seat": ev.get("seat"),
                          "model": (ev.get("model") or "").split("/")[-1],
                          "verdict": ev.get("verdict"),
                          "problems": ev.get("problems") or 0})
        elif t == "consult_verify":
            if ev.get("unfixed") is not None:
                unfixed = (unfixed or 0) + int(ev["unfixed"])
            elif unfixed is None:
                unfixed = -1          # 有席位说不清 ⇒ 未知，不当作 0
    return {
        "id": cid,
        "title": st["title"],
        "state": st["state"],
        "log_bytes": _log_bytes(cid),
        "holder": st["holder"],
        "engine": st["engine"],
        "model": st["model"],
        "effort": st["effort"],
        "goal": card.get("goal", ""),
        "territory": card.get("territory", []),
        "deliverables": card.get("deliverables", []),
        "human_gate": st["gate"],
        "rework": st["rework"],
        "created_kind": st["created_kind"],
        "events": st["events"],
        # 最后活动时刻（毫秒）：界面用来标「3 小时前动过」，一眼看出哪张卡在僵尸
        "last_at": (events[-1].get("at_ms") if events else None),
        "blocked_reason": st.get("blocked_reason"),
        "budget": B.budget_status(cid, card, events),
        # 列表页不逐卡算 sha（会反复读文件）；详情页才给 before/after
        "diff": [] if light else B.diff_vs_baseline(cid, card),
        "blocked_by": card.get("blocked_by") or [],
        "gate_ok": not (submit.get("gate", {}) or {}).get("problems"),
        "gate_problems": (submit.get("gate", {}) or {}).get("problems", []),
        "review_verdict": (st.get("review") or {}).get("verdict"),
        "consult": {"seats": seats, "unfixed": unfixed},
        "review_seat": (st.get("review") or {}).get("seat"),
        "review_evidence": (st.get("review") or {}).get("evidence"),
        "usage": usage,
    }


def _resolve(project: str | None) -> Path:
    if project:
        p = P.find_project(project)
        if not p:
            raise ValueError(f"没找到项目：{project}")
        return Path(p["path"])
    return P.resolve_root(None)


def _switch(project: str | None) -> Path:
    root = _resolve(project)
    # 同一个项目连续来的请求是绝大多数：没变就别再 set_root
    # （set_root 每次都要 mkdir + 检查旧数据迁移，跟数据量无关的纯开销）
    if B.ROOT == root:
        return root
    B.set_root(root)
    B.set_workspace(P.workspace_of(root))
    return root


# ---------- 接口实现 ----------

def api_state(q):
    """首页只需要「项目列表 + 当前项目是谁」。

    ⚠️ 这里刻意不算各状态的张数：那个数字前端手里已经有（它就是靠 /api/cards 渲染的），
    后端再算一遍等于把每张卡的事件流重放一次，纯属白烧 CPU，还会和卡片列表短暂不一致。
    """
    ps = P.project_summary()
    projects = [{"name": p["name"], "path": p["path"],
                 "cards": p.get("cards", 0),
                 "states": p.get("states", {}),
                 "ok": p.get("ok", False)} for p in ps]
    project = q.get("project", [None])[0]
    if project == ALL_PROJECTS:
        root = P.resolve_root(None)      # 总览模式不切项目，路径仅用于显示
    else:
        root = _switch(project)
    return {
        "current": root.name,
        "current_path": str(root),
        "workspace": str(B.WORKSPACE),
        "projects": projects,
        # 让外壳能认出「这个后端是不是老代码」（E-31：旧进程配新页面＝接口 not found）
        "server": {"pid": os.getpid(), "started": _STARTED_AT,
                   "code_mtime": int(_CODE_MTIME)},
    }


def api_alert(q):
    """桌面壳用的极简告警行（壳不做 JSON 解析，只按字符切）。

    只报两类：**需要人拍板**的、**失败/超预算/返工到顶**的。
    ⛔ 不许把「跑完了、没待拍板」也报上来——那种通知是噪音，用户会直接关掉通知，
       连带把真警报一起关掉（这条比「通知少一点」严重得多）。
    """
    project = q.get("project", [None])[0]
    if project == ALL_PROJECTS:
        project = None
    # ⚠️ 必须**无条件**切：B.ROOT 是模块级全局，不切就会读到「上一个请求的项目」。
    #    实测 2026-10-20：不切时壳收到的永远是工具自己那 5 张卡（needs= 恒为空）。
    _switch(project)
    needs, failed = [], []
    for cid in B.card_ids():
        try:
            st = B.replay(cid)
        except Exception:
            continue
        if st["state"] == "拍板中":
            needs.append(cid)
        elif st["state"] == "阻塞":
            r = st.get("blocked_reason") or ""
            # ⚠️ 2026-10-21 修（安全扫描 F-23）：旧关键词只有三个中文词，
            #    「engine returned no text / 依赖不存在 / 租约丢失」全都静默不报。
            low = r.lower()
            if any(k in r for k in ("失败", "超预算", "返工", "异常", "超时", "租约")) \
                    or any(k in low for k in ("error", "fail", "timeout", "engine")):
                failed.append(cid)
    return "needs=" + ",".join(needs) + "|failed=" + ",".join(failed)


def api_cards(q):
    project = q.get("project", [None])[0]
    if project == ALL_PROJECTS:
        return {"all": True, "cards": _all_cards()}
    _switch(project)
    out = []
    for cid in B.card_ids():
        v = _card_view(cid)
        if v:
            out.append(v)
    return {"cards": out}


def _all_cards():
    """把所有项目的卡汇到一张板上（跨项目总览）。

    刻意用 light 模式：总览只要「谁、什么状态」，不要每张卡的用量明细，
    否则几十个项目几千张卡会把界面拖死。
    """
    out = []
    prev_root, prev_ws = B.ROOT, B.WORKSPACE
    try:
        for p in P.list_projects():
            if not p.get("exists"):
                continue
            root = Path(p["path"])
            try:
                B.set_root(root)
                B.set_workspace(P.workspace_of(root))
                for cid in B.card_ids():
                    v = _card_view(cid, light=True)
                    if v:
                        v["project"] = p["name"]
                        v["project_path"] = p["path"]
                        out.append(v)
            except Exception:
                continue          # 某个项目库坏了不能拖垮整个总览
    finally:
        B.set_root(prev_root)
        B.set_workspace(prev_ws)
    return out


def api_card(q):
    _switch(q.get("project", [None])[0])
    cid = q.get("id", [None])[0]
    if not cid:
        raise ValueError("缺 id")
    v = _card_view(cid)
    if not v:
        raise ValueError(f"卡片不存在：{cid}")
    events = []
    for ev in B.load_journal(cid):
        events.append({
            "seq": ev.get("seq"), "at": ev.get("at"), "type": ev.get("type"),
            "seat": ev.get("seat"), "verdict": ev.get("verdict"),
            "note": ev.get("note") or ev.get("reason") or "",
            "evidence": ev.get("evidence"),
        })
    v["events"] = events
    return v


def api_cost(q):
    _switch(q.get("project", [None])[0])
    total = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
             "cost": 0.0, "calls": 0, "unknown": 0}
    by_card = {}
    for cid in B.card_ids():
        c = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
             "cost": 0.0, "calls": 0}
        for ev in B.load_journal(cid):
            if ev.get("type") != "usage":
                continue
            u = ev.get("usage") or {}
            c["calls"] += 1
            total["calls"] += 1
            if not u.get("available"):
                total["unknown"] += 1
                continue
            for k in ("input", "output", "cache_read", "cache_write"):
                c[k] += int(u.get(k) or 0)
                total[k] += int(u.get(k) or 0)
            c["cost"] += float(u.get("cost") or 0)
            total["cost"] += float(u.get("cost") or 0)
        if c["calls"]:
            by_card[cid] = c
    return {"total": total, "by_card": by_card}


def _budget_field(body, defaults, key, cast):
    """界面留空 → 继承项目默认值；项目也没设 → 不限（None）。"""
    v = body.get(key)
    if v is None or v == "":
        dv = (defaults or {}).get(key)
        if dv in (None, "", "none"):
            return None
        return cast(float(dv))
    try:
        return cast(float(v))
    except (TypeError, ValueError):
        raise ValueError(f"预算要写数字或留空，收到：{v}")


def api_create(body):
    root = _switch(body.get("project"))
    title = (body.get("title") or "").strip()
    if not title:
        raise ValueError("标题不能为空")
    defaults = P.project_defaults(root) or {}
    cid = body.get("id") or f"C{time.strftime('%m%d')}-{os.urandom(2).hex()}"
    # ⚠️ 2026-10-21 修（安全扫描 F-02）：卡号会进文件路径（evidence/<卡号>、.worktrees/<卡号>），
    #    这里和 CLI 用同一把尺；⛔ 不合法就拒，别等 mkdir 出花样。
    if not B.CARD_ID_RE.match(str(cid)):
        raise ValueError(f"卡号不合法：{cid!r}（只允许 A-Z a-z 0-9 _ - ，长度 1–64）")
    if B.get_card(cid):
        raise ValueError(f"卡片已存在：{cid}")
    card = {
        "id": cid,
        "title": title,
        "goal": (body.get("goal") or "").strip(),
        "territory": body.get("territory") or [],
        "deliverables": body.get("deliverables") or [],
        "accept_patterns": body.get("accept") or [],
        "human_gate": body.get("human_gate") or "none",
        "engine": body.get("engine") or defaults.get("engine", "any"),
        "model": body.get("model") or defaults.get("model", "any"),
        "effort": body.get("effort") or defaults.get("effort", "any"),
        "created_at": B.ts(),
        "created_by": body.get("who") or "human",
        "created_kind": "human",
        "irreversible": bool(body.get("irreversible")),
        "source_card": None,
        "max_cost_usd": _budget_field(body, defaults, "max_cost_usd", float),
        "max_minutes": _budget_field(body, defaults, "max_minutes", int),
        "blocked_by": body.get("blocked_by") or [],
    }
    B.create_card(card)
    B.append_event(cid, {"type": "created", "actor": "human",
                         "seat": card["created_by"], "title": title,
                         "engine": card["engine"], "model": card["model"],
                         "effort": card["effort"],
                         "human_gate": card["human_gate"],
                         "via": "ui"})
    P.invalidate_summary_cache()      # 让下拉框里的项目张数立刻更新
    return {"ok": True, "id": cid}


def api_human(body):
    root = _switch(body.get("project"))
    cid = body.get("id")
    decision = body.get("decision")
    if not cid or decision not in ("approve", "reject"):
        raise ValueError("参数不对")
    who = (body.get("who") or "owner").strip()
    ok_tok, why = _verify_token(who)
    if not ok_tok:
        # ⚠️ 2026-10-21 修（安全扫描 F-16）：不再「首次自动登记」（等于谁放个文件谁就是人），
        #    也不把家目录路径回显给 HTTP 调用方（只写本机后端日志）。
        print(f"⚠ 人令牌校验失败（who={who}）：{why}", file=sys.stderr)
        raise PermissionError("人令牌校验未通过：先在本机终端跑 board token --init")
    cur = B.replay(cid)["state"]
    if cur != "拍板中":
        raise ValueError(f"当前状态「{cur}」，只有「拍板中」的卡需要拍板")
    if decision == "reject" and not (body.get("note") or "").strip():
        raise ValueError("驳回必须写理由 —— 否则下一轮 agent 不知道要改什么")
    B.append_event(cid, {"type": "human", "actor": "human", "who": who,
                         "decision": decision, "note": (body.get("note") or "").strip()})
    P.invalidate_summary_cache()
    return {"ok": True, "state": B.replay(cid)["state"]}


def _verify_token(who):
    import cli as C
    return C._verify_human_token(who)


def api_run(body):
    root = _switch(body.get("project"))
    return _start_run(root, body)


def _start_run(root, body, cards=None):
    """起一轮编排（后台子进程）。cards 给了就只跑这几张（界面「选中后跑一轮」）。"""
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("已经有一轮在跑了，等它结束")
    try:
        if _run_state["running"]:
            raise RuntimeError("已经有一轮在跑了")
        # ⚠️ 2026-10-21 修（安全扫描 F-10）：参数必须在置 running 之前校验完。
        #    旧实现先置 running=True 再 int(body["max"])，一个 "abc" 就让 except
        #    只放锁不复位 ⇒ 之后每次「跑一轮」都撞「已经有一轮在跑了」，直到重启后端。
        try:
            n = int(body.get("max") or 3)
        except (TypeError, ValueError):
            raise ValueError("max 必须是整数")
        n = max(1, min(n, 200))
        cards = [str(c) for c in (cards or []) if str(c).strip()]
        _run_state.update(running=True, project=str(root),
                          started=time.strftime("%H:%M:%S"))
        _run_log_path.parent.mkdir(parents=True, exist_ok=True)
        _run_log_path.write_text("", encoding="utf-8")
        if cards:
            n = max(n, len(cards))
        engine = body.get("engine") or "opencode"
        model = body.get("model") or ""
        cmd = [sys.executable, str(Path(__file__).resolve().parent / "orchestrator.py"),
               "-C", str(root),
               "run", "--max", str(n), "--engine", engine]
        if model:
            cmd += ["--model", model]
        if cards:
            cmd += ["--cards", ",".join(cards)]

        def _worker():
            try:
                with _run_log_path.open("a", encoding="utf-8") as f:
                    p = subprocess.Popen(cmd, cwd=str(root), stdout=f,
                                         stderr=subprocess.STDOUT, text=True)
                    p.wait()
            finally:
                _run_state["running"] = False
                _run_lock.release()

        threading.Thread(target=_worker, daemon=True).start()
        return {"ok": True, "started": _run_state["started"]}
    except Exception:
        _run_state.update(running=False, project=None, started=None)
        _run_lock.release()
        raise


def api_bulk(body):
    """多选后的批量动作（界面「选中 N 张」那一排按钮）。

    ⚠️ 只做两个动作，理由：
      · run   —— 是 agent 侧动作，不越过人闸；
      · cancel —— 「已取消」按状态机只允许 human，所以**必须带令牌**，和拍板同一把钥匙。
        ⛔ 不做「批量删除」：删卡是不可逆动作，只能一张一张来（`board rm` 还要 --yes）。
    """
    root = _switch(body.get("project"))
    ids = [str(x).strip() for x in (body.get("ids") or []) if str(x).strip()]
    if not ids:
        raise ValueError("没选卡")
    act = body.get("action")
    if act == "run":
        return _start_run(root, dict(body, max=len(ids)), cards=ids)
    if act == "cancel":
        who = (body.get("who") or "owner").strip()
        ok_tok, why = _verify_token(who)
        if not ok_tok:
            raise PermissionError(why)
        done, skipped = [], []
        for cid in ids:
            if not B.get_card(cid):
                skipped.append(f"{cid}（不存在）")
                continue
            st = B.replay(cid)
            if (st["state"], "已取消") not in B.TRANSITIONS:
                skipped.append(f"{cid}（{st['state']} 不能取消）")
                continue
            B.append_event(cid, {"type": "cancel", "actor": "human", "who": who})
            B.release(cid)         # 有租约就放掉，别留僵尸占卡
            done.append(cid)
        P.invalidate_summary_cache()
        return {"ok": True, "cancelled": done, "skipped": skipped}
    raise ValueError("action 只能是 run / cancel")


def api_card_log(q):
    """一点一点读某张卡的运行日志（界面在卡片里看实时输出）。

    since＝已经拿到的字节数；返回新增部分 + 文件总长 + 是否还在跑。
    文件被重写（新一轮开跑清空）时 size 会变小，前端据此清屏重来。
    """
    _switch(q.get("project", [None])[0])
    cid = q.get("id", [None])[0]
    if not cid:
        raise ValueError("缺 id")
    if not B.CARD_ID_RE.match(str(cid)):
        raise ValueError(f"卡号不合法：{cid!r}")
    try:
        since = int(q.get("since", ["0"])[0] or 0)
    except ValueError:
        since = 0
    p = B.card_dir(cid) / "run.log"
    if not p.exists():
        return {"size": 0, "log": "", "running": False}
    # ⚠️ 2026-10-21 改（安全扫描 F-22）：不再整文件 read_bytes 再切 20KB，
    #    改为 seek(since) 只读增量；首次（since=0）也只取尾部 20KB。
    size = p.stat().st_size
    start = since if 0 <= since <= size else 0
    if start == 0 and size > 20000:
        start = size - 20000
    with p.open("rb") as f:
        f.seek(start)
        data = f.read()
    chunk = data.decode("utf-8", "replace")
    st = B.replay(cid)
    return {"size": size, "log": chunk[-20000:],
            "running": st["state"] in ("进行中", "核验中")}


def api_run_log(q):
    if _run_log_path.exists():
        return {"running": _run_state["running"],
                "log": _run_log_path.read_text(encoding="utf-8", errors="replace")[-20000:]}
    return {"running": _run_state["running"], "log": ""}


# ---------- 留言 + 内置终端（窗口里直接能用的两条）----------

def api_messages(q):
    """留言列表 + 某个身份还有多少未读。"""
    _switch(q.get("project", [None])[0])
    import messages as M
    st = B._store()
    to = q.get("to", [None])[0]
    who = q.get("as", [None])[0]
    limit = int(q.get("limit", ["50"])[0])
    msgs = st.messages(to=to, limit=limit)
    read = st.read_seqs(who) if who else set()
    out = []
    for m in msgs:
        d = {k: m.get(k) for k in ("seq", "at", "sender", "recipient",
                                   "kind", "body", "reply_to")}
        d["unread"] = bool(who and m["recipient"] == who and m["seq"] not in read)
        w = st.last_wake(m["seq"])
        d["wake"] = (w or {}).get("state")
        out.append(d)
    counts = {}
    for m in st.messages(limit=2000):
        counts[m["recipient"]] = counts.get(m["recipient"], 0) + 1
    unread = {who2: len([m for m in st.messages(limit=2000)
                         if m["recipient"] == who2
                         and m["seq"] not in st.read_seqs(who2)])
              for who2 in counts}
    return {"messages": out, "unread": unread, "total": sum(counts.values())}


def api_message_send(body):
    _switch(body.get("project"))
    import messages as M
    st = B._store()
    msg = M.send(st, body.get("from") or "human", body.get("to") or "",
                 body.get("body") or "", kind=body.get("kind") or "note",
                 reply_to=body.get("reply_to") or None)
    return {"ok": True, "message": msg}


def api_message_ack(body):
    _switch(body.get("project"))
    st = B._store()
    seq = int(body.get("seq") or 0)
    if not st.message(seq):
        raise ValueError(f"留言不存在：#{seq}")
    fresh = st.mark_read(seq, body.get("as") or "human")
    return {"ok": True, "fresh": fresh}


def api_term_tail(q):
    import term
    since = int(q.get("since", ["0"])[0])
    return term.tail(since)


def api_term_run(body):
    import term
    project = body.get("project")
    cwd = None
    if project:
        cwd = str(_resolve(project))
    ok, detail = term.run(body.get("cmd") or "", cwd=cwd)
    if not ok:
        raise ValueError(detail)
    return {"ok": True, "kind": detail, "state": term.state()}


def api_term_stop(body):
    import term
    return {"ok": term.stop()}


# ---------- HTTP ----------

class PoolHTTPServer(ThreadingHTTPServer):
    """固定线程池的 HTTP 服务器。

    为什么不用默认的「一请求一线程」：数据库连接都是 thread-local 的，
    线程一换，连接就得重建、建表语句还得重跑一遍（实测每请求白烧约 4ms，
    两个库就是 8ms，而一条请求总共才 20-30ms）。
    线程池让线程复用 ⇒ 连接复用 ⇒ 这笔开销只付一次。
    """

    pool_size = 4
    max_backlog = 32          # 排队上限：满了直接 503，别让页面无限等（安全扫描 F-12）

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pool = ThreadPoolExecutor(max_workers=self.pool_size,
                                        thread_name_prefix="board-ui")
        self._slots = threading.BoundedSemaphore(self.pool_size + self.max_backlog)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\n"
                                b"Content-Length: 0\r\nConnection: close\r\n\r\n")
            except Exception:
                pass
            finally:
                try:
                    request.close()
                except Exception:
                    pass
            return

        def _run():
            try:
                self.process_request_thread(request, client_address)
            finally:
                self._slots.release()

        self._pool.submit(_run)

    def server_close(self):
        try:
            self._pool.shutdown(wait=False, cancel_futures=True)
        except TypeError:            # Python 3.8 没有 cancel_futures
            self._pool.shutdown(wait=False)
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    server_version = "aII-work-together-ui/1.0"
    timeout = 10          # 读超时：慢连接不许把线程池占死（安全扫描 F-12）

    def log_message(self, fmt, *args):
        pass          # 安静：不往控制台刷访问日志

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if "text/html" in ctype:
            # CSP：页面自带内联脚本（单文件），所以 script 仍放开 inline；
            # 但禁掉外部源、禁 frame、禁 object —— 至少堵住「外链脚本」与「被嵌框」。
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                             "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                             "connect-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _host_allowed(self) -> bool:
        if _host_ok(self.headers.get("Host")):
            return True
        self._json({"error": "非本地 Host（已拒绝，防 DNS rebinding）"}, 403)
        return False

    def do_GET(self):
        if not self._host_allowed():
            return
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            if not UI.exists():
                return self._send(500, "ui.html 缺失", "text/plain; charset=utf-8")
            html = UI.read_text(encoding="utf-8")
            # 会话令牌注入页面（同源页面才读得到；跨站页面读不到 → 拿不到写权限）
            html = html.replace('<meta name="board-token" content="">',
                                f'<meta name="board-token" content="{_TOKEN}">')
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if u.path in ("/favicon.ico", "/assets/board.png"):
            f = ROOT / "assets" / ("board.ico" if u.path == "/favicon.ico" else "board.png")
            if f.exists():
                ctype = "image/x-icon" if f.suffix == ".ico" else "image/png"
                return self._send(200, f.read_bytes(), ctype)
            return self._send(404, "", "text/plain; charset=utf-8")
        if u.path == "/api/alert":
            # 纯文本一行，壳里直接 StartWith/IndexOf，不用 JSON 解析
            try:
                with _BOARD_LOCK:
                    body = api_alert(q)
            except Exception as e:
                # ⚠️ 2026-10-21 修（安全扫描 F-23）：出错不再回 HTTP 200 的 "error=…"，
                #    否则壳按 needs=/failed= 切字符串会把它当「无事发生」（E-35 的近亲）。
                print(f"⚠ /api/alert 失败：{e}", file=sys.stderr)
                return self._send(500, b"error=1", "text/plain; charset=utf-8")
            return self._send(200, body.encode("utf-8"), "text/plain; charset=utf-8")
        routes = {
            "/api/state": api_state,
            "/api/cards": api_cards,
            "/api/card": api_card,
            "/api/card/log": api_card_log,
            "/api/cost": api_cost,
            "/api/run/log": api_run_log,
            "/api/messages": api_messages,
            "/api/term/tail": api_term_tail,
        }
        fn = routes.get(u.path)
        if not fn:
            return self._json({"error": "not found"}, 404)
        try:
            with _BOARD_LOCK:
                self._json(fn(q))
        except SystemExit:
            self._json({"error": "内部操作失败（详见控制台）"}, 500)
        except Exception as e:
            self._json({"error": _safe_msg(e)}, 400)

    def do_POST(self):
        if not self._host_allowed():
            return
        # 写接口必须带页面注入的会话令牌：跨站页面拿不到它（CORS 简单请求不触发预检，
        # 但自定义头不在简单请求允许的头里 ⇒ 想带就要预检 ⇒ 我们没有 ACAO ⇒ 被浏览器拦）。
        if (self.headers.get("X-Board-Token") or "") != _TOKEN:
            return self._json({"error": "缺少/错误的会话令牌（跨站写入已拒绝）"}, 403)
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json({"error": "Content-Length 不合法"}, 400)
        if n > _MAX_BODY:
            return self._json({"error": f"请求体太大（{n} > {_MAX_BODY}）"}, 413)
        u = urlparse(self.path)
        raw = self.rfile.read(n).decode("utf-8", "replace") if n else "{}"
        try:
            body = json.loads(raw)
        except Exception:
            return self._json({"error": "请求体不是 JSON"}, 400)
        routes = {"/api/card": api_create, "/api/human": api_human,
                  "/api/run": api_run, "/api/bulk": api_bulk,
                  "/api/messages": api_message_send,
                  "/api/messages/ack": api_message_ack,
                  "/api/term/run": api_term_run,
                  "/api/term/stop": api_term_stop}
        fn = routes.get(u.path)
        if not fn:
            return self._json({"error": "not found"}, 404)
        try:
            with _BOARD_LOCK:
                self._json(fn(body))
        except PermissionError as e:
            self._json({"error": _safe_msg(e)}, 403)
        except SystemExit:
            self._json({"error": "操作被拒绝（详见控制台）"}, 400)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": _safe_msg(e)}, 400)


def main():
    ap = argparse.ArgumentParser(description="本地看板界面")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--workers", type=int, default=4,
                    help="线程池大小；0＝老行为（一请求一线程，仅供压测对照）")
    ap.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    a = ap.parse_args()

    if not UI.exists():
        print(f"✗ 缺界面文件：{UI}")
        return 1

    # 把会话令牌写到本地文件：壳/托盘要读它（它们不是页面，拿不到注入的 meta）。
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(_TOKEN, encoding="utf-8")
    except Exception as e:
        print(f"⚠ 令牌文件写不了（壳可能连不上）：{e}")

    if a.workers <= 0:
        srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    else:
        PoolHTTPServer.pool_size = a.workers
        srv = PoolHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"✓ 看板界面：{url}")
    print(f"  只在本机可访问（127.0.0.1），关掉这个窗口就停了")
    if a.open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
