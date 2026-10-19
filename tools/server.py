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
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
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

_run_lock = threading.Lock()
_run_state = {"running": False, "project": None, "started": None}
_run_log_path = ROOT / "board" / "ui-run.log"

# ⚠️ 所有看板访问必须在这个锁里做。
# 原因：board.py 的项目根是模块级全局（B.set_root），而这里是一请求一线程。
# 不锁的后果是实测过的——两个项目并发建卡会互相串（卡建到别的项目、同号静默覆盖）。
# 单人本地界面，串行化完全够用；要真并发得把项目根改成上下文变量，那是另一件事。
_BOARD_LOCK = threading.RLock()


# ---------- 数据整形 ----------

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
    if not light:
        for ev in events:
            if ev.get("type") == "usage":
                u = ev.get("usage") or {}
                if u.get("available"):
                    usage["available"] = True
                    for k in ("input", "output", "cache_read", "cache_write"):
                        usage[k] += int(u.get(k) or 0)
                    usage["cost"] += float(u.get("cost") or 0)
    return {
        "id": cid,
        "title": st["title"],
        "state": st["state"],
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
        "blocked_reason": st.get("blocked_reason"),
        "gate_ok": not (submit.get("gate", {}) or {}).get("problems"),
        "gate_problems": (submit.get("gate", {}) or {}).get("problems", []),
        "review_verdict": (st.get("review") or {}).get("verdict"),
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
    }


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


def api_create(body):
    root = _switch(body.get("project"))
    title = (body.get("title") or "").strip()
    if not title:
        raise ValueError("标题不能为空")
    defaults = P.project_defaults(root) or {}
    cid = body.get("id") or f"C{time.strftime('%m%d')}-{os.urandom(2).hex()}"
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
    }
    B.create_card(card)
    B.append_event(cid, {"type": "created", "actor": "human",
                         "seat": card["created_by"], "title": title,
                         "engine": card["engine"], "model": card["model"],
                         "effort": card["effort"],
                         "human_gate": card["human_gate"]})
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
        raise PermissionError(why)
    _register_token(who)
    cur = B.replay(cid)["state"]
    if cur != "拍板中":
        raise ValueError(f"当前状态「{cur}」，只有「拍板中」的卡需要拍板")
    if decision == "reject" and not (body.get("note") or "").strip():
        raise ValueError("驳回必须写理由 —— 否则下一轮 agent 不知道要改什么")
    B.append_event(cid, {"type": "human", "actor": "human", "who": who,
                         "decision": decision, "note": (body.get("note") or "").strip()})
    return {"ok": True, "state": B.replay(cid)["state"]}


def _verify_token(who):
    import cli as C
    return C._verify_human_token(who)


def _register_token(who):
    import hashlib
    import cli as C
    reg = C.human_token_sha(who)
    if reg.exists():
        return
    content = C.human_token(who).read_text(encoding="utf-8").strip()
    reg.write_text(hashlib.sha256(content.encode("utf-8")).hexdigest(),
                   encoding="utf-8")


def api_run(body):
    root = _switch(body.get("project"))
    if not _run_lock.acquire(blocking=False):
        raise RuntimeError("已经有一轮在跑了，等它结束")
    try:
        if _run_state["running"]:
            raise RuntimeError("已经有一轮在跑了")
        _run_state.update(running=True, project=str(root),
                          started=time.strftime("%H:%M:%S"))
        _run_log_path.parent.mkdir(parents=True, exist_ok=True)
        _run_log_path.write_text("", encoding="utf-8")
        n = int(body.get("max") or 3)
        engine = body.get("engine") or "opencode"
        model = body.get("model") or ""
        cmd = [sys.executable, str(Path(__file__).resolve().parent / "orchestrator.py"),
               "-C", str(root),
               "run", "--max", str(n), "--engine", engine]
        if model:
            cmd += ["--model", model]

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
        _run_lock.release()
        raise


def api_run_log(q):
    if _run_log_path.exists():
        return {"running": _run_state["running"],
                "log": _run_log_path.read_text(encoding="utf-8", errors="replace")[-20000:]}
    return {"running": _run_state["running"], "log": ""}


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "allworktogether-ui/1.0"

    def log_message(self, fmt, *args):
        pass          # 安静：不往控制台刷访问日志

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            if not UI.exists():
                return self._send(500, "ui.html 缺失", "text/plain; charset=utf-8")
            return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
        routes = {
            "/api/state": api_state,
            "/api/cards": api_cards,
            "/api/card": api_card,
            "/api/cost": api_cost,
            "/api/run/log": api_run_log,
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
            self._json({"error": str(e)}, 400)

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8") if n else "{}"
        try:
            body = json.loads(raw)
        except Exception:
            return self._json({"error": "请求体不是 JSON"}, 400)
        routes = {"/api/card": api_create, "/api/human": api_human, "/api/run": api_run}
        fn = routes.get(u.path)
        if not fn:
            return self._json({"error": "not found"}, 404)
        try:
            with _BOARD_LOCK:
                self._json(fn(body))
        except PermissionError as e:
            self._json({"error": str(e)}, 403)
        except SystemExit:
            self._json({"error": "操作被拒绝（详见控制台）"}, 400)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 400)


def main():
    ap = argparse.ArgumentParser(description="本地看板界面")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    a = ap.parse_args()

    if not UI.exists():
        print(f"✗ 缺界面文件：{UI}")
        return 1

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
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
