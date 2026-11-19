#!/usr/bin/env python3
"""自动派工守护进程（参考编排器，不属于内核账本）—— 2026-11-20，D-043。

定位（遵守 D-042）：
  · 它**调用**看板：ready / events / claim / submit 都由执行方走内核命令；
  · 它**不是**内核的一部分：删掉它，看板照常工作；
  · 它不决定「派给谁」：adapter 自己决定（CLI / BBFF / HTTP）。

用法：
  python tools/autodispatch.py run --adapter cli --apply
  python tools/autodispatch.py run --adapter cmd --cmd "..." --apply
  python tools/autodispatch.py run --adapter http --url http://127.0.0.1:9001/dispatch --apply
  python tools/autodispatch.py once --adapter cli --apply

安全默认：
  · 不加 --apply 只打印「会派什么」，不动卡；
  · 单实例锁（同一项目同时只跑一个调度器）；
  · 同一张卡 15 分钟内不会被重复派（dispatch-start 未配 dispatch-end 视为在飞）。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import board as B  # noqa: E402

IN_FLIGHT_MS = 15 * 60 * 1000


def now_ms():
    return int(time.time() * 1000)


def _ready(limit=5):
    """只读：拿可开工的卡（含阻塞列表）。"""
    rows = []
    for cid in B.card_ids():
        st = B.replay(cid)
        if st["state"] not in ("待认领", "待返工"):
            continue
        evs = B.load_journal(cid)
        if B.fold.is_trashed(evs):
            continue
        card = B.get_card(cid) or {}
        blocked = B.withholding(cid, card)
        if blocked:
            continue
        rows.append({"id": cid, "title": st["title"], "state": st["state"]})
        if len(rows) >= limit:
            break
    return rows


def _last_events(cid, n=8):
    return B.load_journal(cid)[-n:]


def _in_flight(cid):
    """在飞或刚派过：dispatch-start 未收口，或 dispatch-end 后卡还是可派状态。"""
    for ev in reversed(_last_events(cid, 12)):
        t = ev.get("type")
        if t in ("submit", "reclaim"):
            return False
        if t == "dispatch-end":
            # 派完还是「待认领/待返工」⇒ 执行方没接住，冷却 10 分钟再试，避免每轮重派
            return (now_ms() - int(ev.get("at_ms") or 0)) < 10 * 60 * 1000
        if t == "dispatch-start":
            return (now_ms() - int(ev.get("at_ms") or 0)) < IN_FLIGHT_MS
    return False


def _mark(cid, typ, **kw):
    ev = {"type": typ, "actor": "system", "adapter": kw.pop("adapter", None),
          "at_ms": now_ms(), "idempotency_key": "dispatch:%s:%s:%s" % (
              cid, typ, kw.pop("run_id"))}
    ev.update(kw)
    B.append_event(cid, {k: v for k, v in ev.items() if v is not None})


def _run_cli(card):
    cmd = [sys.executable, os.path.join(HERE, "orchestrator.py"), "run", "--max", "1"]
    return subprocess.run(cmd, cwd=B.ROOT, capture_output=True, text=True, timeout=1800)


def _run_cmd(card, cmd):
    env = dict(os.environ)
    env.update({"BOARD_CARD": card["id"], "BOARD_TITLE": card["title"]})
    return subprocess.run(cmd, shell=True, cwd=B.ROOT, env=env,
                          capture_output=True, text=True, timeout=1800)


def _run_http(card, url):
    body = json.dumps({"card": card, "project": str(B.ROOT)}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return type("R", (), {"returncode": 0 if r.status < 400 else 1,
                              "stdout": r.read().decode("utf-8", "replace")[:500],
                              "stderr": ""})()


def dispatch_one(card, args):
    run_id = "%d" % (now_ms() // 1000)
    _mark(card["id"], "dispatch-start", adapter=args.adapter, run_id=run_id)
    t0 = time.time()
    try:
        if args.adapter == "cli":
            r = _run_cli(card)
        elif args.adapter == "cmd":
            r = _run_cmd(card, args.command)
        else:
            r = _run_http(card, args.url)
        rc, out, err = r.returncode, (r.stdout or "")[-500:], (r.stderr or "")[-500:]
    except Exception as e:  # 超时/起不来都要留痕
        rc, out, err = 124, "", str(e)[:500]
    _mark(card["id"], "dispatch-end", adapter=args.adapter, run_id=run_id,
          rc=rc, seconds=round(time.time() - t0, 1), output=out, error=err)
    return rc


def cmd_run(args):
    lock = os.path.join(B.ROOT, "board", ".autodispatch.lock")
    if os.path.exists(lock):
        try:
            pid = int(open(lock, encoding="utf-8").read().strip() or 0)
        except Exception:
            pid = 0
        if pid and os.path.exists("/proc/%d" % pid) and pid != os.getpid():
            print("已有调度器在跑（pid %d），退出" % pid)
            return 2
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    open(lock, "w", encoding="utf-8").write(str(os.getpid()))
    try:
        while True:
            todo = _ready(args.limit)
            if not todo:
                if args.once:
                    print("没有可派工的卡")
                    return 0
                time.sleep(args.interval)
                continue
            dispatched = 0
            for card in todo:
                if _in_flight(card["id"]):
                    print("跳过（在飞）：%s" % card["id"])
                    continue
                print("[%s] 派工 %s %s → %s" % (
                    datetime.now().strftime("%H:%M:%S"), card["id"],
                    card["title"], args.adapter))
                if args.apply:
                    rc = dispatch_one(card, args)
                    print("  ↔ 返回 %s" % rc)
                dispatched += 1
                if args.once:
                    return 0 if (not args.apply or rc == 0) else 1
            if args.once:
                print("没有可派工（其余在飞或在回收站）")
                return 0
            time.sleep(args.interval)
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


def cmd_once(args):
    args.once = True
    args.interval = 0
    args.limit = args.limit or 1
    return cmd_run(args)


def main():
    ap = argparse.ArgumentParser(description="自动派工守护（调看板，不进账本）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "once"):
        s = sub.add_parser(name)
        s.add_argument("--adapter", choices=("cli", "cmd", "http"), default="cli")
        s.add_argument("--command", help="adapter=cmd 时执行的命令")
        s.add_argument("--url", help="adapter=http 时的 POST 地址")
        s.add_argument("--interval", type=int, default=20)
        s.add_argument("--limit", type=int, default=3)
        s.add_argument("--apply", action="store_true", help="真派；不加只打印")
    a = ap.parse_args()
    a.once = (a.cmd == "once")
    if a.once:
        a.interval = 0
    if a.adapter == "cmd" and not a.command:
        print("adapter=cmd 需要 --command")
        return 2
    if a.adapter == "http" and not a.url:
        print("adapter=http 需要 --url")
        return 2
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
