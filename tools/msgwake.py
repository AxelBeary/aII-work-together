#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
msgwake.py — 唤醒工作者（由 messages.wake 起成独立进程，没人手工跑它）

干什么：
  1. 取一条留言（--seq）
  2. 用它记录下来的 sessionID 续一次会话，把留言内容作为新一轮输入
  3. 把对方的回答**写成一条回复留言**（kind=answer，reply_to=原 seq）
  4. 唤醒状态如实记：DELIVERED / FAILED（⛔ 不写假成功）

为什么要独立进程：
  发送方不该被「对方要跑 3 分钟」卡住；而且续会话的进程一旦父进程退出就得能自己活着。
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    ap = argparse.ArgumentParser(description="唤醒一条留言（内部使用）")
    ap.add_argument("--db", required=True, help="项目 board.db 路径")
    ap.add_argument("--seq", type=int, required=True)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--model")
    ap.add_argument("--effort")
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    import storage
    import messages as M
    import engines as E

    store = storage.Store(a.db, Path(a.db).parent / "evidence")
    msg = store.message(a.seq)
    if not msg:
        print(f"✗ 留言不存在：#{a.seq}")
        return M.EXIT_ERROR

    me = msg["recipient"]
    peer = msg["sender"]
    body = (msg.get("body") or "").strip()
    thread_hint = f"（这是对 #{msg['reply_to']} 的回复）" if msg.get("reply_to") else ""

    prompt = (
        f"【跨会话留言 · 来自 {peer}{thread_hint}】\n"
        f"{body}\n\n"
        f"你要做的：直接回应上面的内容。\n"
        f"你的这段回答会被自动存成一条回复留言（#{a.seq} 的回复）传给 {peer}，"
        f"所以不要再复述任务、不要写「收到」。\n"
        f"如果你需要把结论落成卡或文件，按项目 AGENTS.md 的规矩做。\n"
        f"工作目录：{a.cwd}"
    )

    print(f"→ 唤醒 {a.engine} 会话 {a.session[:20]}…（留言 #{a.seq}，来自 {peer}）")
    r = E.run(a.engine, prompt, cwd=a.cwd, model=a.model or None,
              effort=a.effort or None, timeout=a.timeout, session_id=a.session)

    if r.ok and (r.text or "").strip():
        reply = store.append_message(
            sender=me, recipient=peer, body=r.text.strip(), kind="answer",
            reply_to=a.seq,
            meta={"engine": a.engine, "model": r.model_used,
                  "session_id": r.session_id or a.session,
                  "usage": r.usage, "by": "msgwake"})
        store.record_wake(a.seq, M.ST_DELIVERED,
                          f"答完，回复存为 #{reply['seq']}（{len(r.text)} 字）")
        print(f"✓ 已回复：#{reply['seq']} → {peer}")
        return M.EXIT_OK

    why = r.reason or ("引擎跑完但没有文本输出" if r.ok else "引擎失败")
    store.record_wake(a.seq, M.ST_FAILED, why)
    print(f"✗ 唤醒失败：{why}")
    if r.raw:
        store.append_message(sender=me, recipient=peer, kind="note",
                             body=f"[唤醒失败] {why}\n\n原始输出（截断）：\n{r.raw[:1500]}",
                             reply_to=a.seq,
                             meta={"engine": a.engine, "by": "msgwake"})
    return M.EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
