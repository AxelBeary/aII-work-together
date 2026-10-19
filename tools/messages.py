#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
messages.py — 跨会话留言（吸收 open-cross-session 的语义，不是照搬它的传输）

为什么需要它：
  我们的引擎模型是「起进程 → 等结果 → 进程退出」，会话本身不常驻，
  所以「一个 agent 想跟另一个 agent 说句话」此前只能靠人转述，或者写进卡里等它下次看。
  这正是 HANDOFF §五 #6 记着的那唯一没做的协作维度。

抄的是**语义**（这四条是 ocs 真正的价值）：
  1. append-only + 单调 seq：留言只增不改，`--reply-to <seq>` 在任何会话里都可寻址
  2. `wake: HELD`：唤不醒就说唤不醒，⛔ 绝不把「存下了」说成「送到了」
  3. 退出码分档：0 已投递 / 2 已存但没唤醒 / 3 没成（没写进去）
  4. 一律**不重发**：按 seq 查，而不是靠重试把重复留言灌进去

换掉的是**传输**：
  ocs 依赖常驻会话的唤醒通道（Claude socket / Codex IPC）；我们没有常驻会话，
  但我们的引擎支持 `--session <id>` 续接 —— 这就是我们的唤醒通道：
  「唤醒」＝**拿记录下来的 sessionID 续一次会话，把留言作为新一轮输入喂进去**，
  它答完的内容自动作为 reply 留言回来（`kind=answer`，`reply_to` 指回原 seq）。
  没有 sessionID（或该引擎不支持续接）时，如实记 HELD，退出码 2。

诚实边界：
  · 只保证「留言按 seq 存住了」；对方到底看没看，只能靠它自己 ack/inbox
  · 续接失败（会话不存在/引擎换了）记 FAILED，不假装已读
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# 唤醒状态：⛔ 只有 DELIVERED 代表对方真的回了话
ST_DISPATCHED = "DISPATCHED"   # 已交给引擎，结果待回
ST_DELIVERED = "DELIVERED"     # 引擎答完，回复已作为留言写入
ST_HELD = "HELD"               # 存下了但唤不醒（没有可续的会话）
ST_FAILED = "FAILED"           # 试过，失败

EXIT_OK = 0
EXIT_HELD = 2
EXIT_ERROR = 3


def send(store, sender, recipient, body, kind="note", reply_to=None, meta=None):
    """写一条留言。返回消息 dict（含 seq）。"""
    if not (body or "").strip():
        raise ValueError("留言正文不能为空")
    if not (recipient or "").strip():
        raise ValueError("收件人不能空（--to）")
    if reply_to is not None:
        if not store.message(int(reply_to)):
            raise ValueError(f"要回复的留言不存在：#{reply_to}")
    return store.append_message(sender, recipient, body, kind=kind,
                                reply_to=int(reply_to) if reply_to else None,
                                meta=meta or {})


def thread(store, seq):
    """把一条留言的整条线拉出来（早于它的根 + 它的所有回复）。"""
    root = store.message(int(seq))
    if not root:
        return []
    # 顺着 reply_to 找根
    while root.get("reply_to"):
        up = store.message(root["reply_to"])
        if not up:
            break
        root = up
    out = [root]
    frontier = [root["seq"]]
    seen = {root["seq"]}
    while frontier:
        kids = []
        for s in frontier:
            kids.extend(store.messages(reply_to=s, limit=200))
        nxt = []
        for k in sorted(kids, key=lambda m: m["seq"]):
            if k["seq"] in seen:
                continue
            seen.add(k["seq"])
            out.append(k)
            nxt.append(k["seq"])
        frontier = nxt
    return out


def inbox(store, reader, limit=50, ack=False, only_unread=True):
    """收件箱。only_unread=False 时列全部。

    返回 (未读列表, 总条数)。ack=True 时把这批标成已读（追加到 msg_reads）。
    """
    msgs = store.messages(to=reader, limit=500)
    read = store.read_seqs(reader)
    picked = [m for m in msgs if (m["seq"] not in read)] if only_unread else msgs
    picked = picked[:limit]
    if ack:
        for m in picked:
            store.mark_read(m["seq"], reader)
    return picked, len(msgs)


def wake(store, seq, engine=None, model=None, session=None, cwd=None,
         effort=None, timeout=1800, force=False):
    """唤醒：拿 sessionID 续一次会话，把留言喂进去。

    返回 (state, detail)。state ∈ {DISPATCHED, HELD, FAILED}

    ⛔ 不重发（ocs 的核心语义）：已经回复过、或刚投递出去的，一律拒绝重发，
       除非显式 force=True。重复唤醒＝对方答两遍，实测会多出一条重复回复。
    """
    msg = store.message(int(seq))
    if not msg:
        return ST_FAILED, f"留言不存在：#{seq}"
    last = store.last_wake(seq)
    if last and not force:
        if last["state"] == ST_DELIVERED:
            return ST_HELD, (f"#{seq} 已经回复过（{last['at'][:19]}）；"
                             "要再问一次请新发一条，⛔ 不重发")
        if last["state"] == ST_DISPATCHED:
            import time as _t
            age = (_t.time() * 1000 - (last.get("at_ms") or 0)) / 1000
            if age < 1800:
                return ST_HELD, (f"#{seq} 三十五分钟内已投递过一次"
                                 f"（{int(age)}s 前），⛔ 不重发；"
                                 f"要看结果：board msg states {seq}")
    meta = dict(msg.get("meta") or {})
    engine = engine or meta.get("wake_engine") or ""
    model = model or meta.get("wake_model") or ""
    session = session or meta.get("wake_session") or ""
    cwd = cwd or meta.get("wake_cwd") or str(HERE.parent)

    if not engine:
        detail = "没有指定引擎（发送时没带 --wake-engine，或这条只是留言）"
        store.record_wake(seq, ST_HELD, detail)
        return ST_HELD, detail
    if not session:
        detail = (f"没有可续接的会话 ID（{engine} 的会话在进程退出后就断了）"
                  "⇒ 只能等对方自己 board msg inbox 来取")
        store.record_wake(seq, ST_HELD, detail)
        return ST_HELD, detail

    # 起一个独立进程去续会话：父进程立刻返回，不阻塞发送者
    try:
        import engines as E
        if engine not in ("opencode", "qoderclicn", "codex", "hermes"):
            raise ValueError(f"未知引擎：{engine}")
        if not E._which(engine):
            raise ValueError(f"引擎未安装：{engine}")
        py = sys.executable or "python"
        args = [py, str(HERE / "msgwake.py"), "--db", str(store.path),
                "--seq", str(seq),
                "--engine", engine, "--session", session,
                "--cwd", cwd, "--timeout", str(int(timeout))]
        if model:
            args += ["--model", model]
        if effort:
            args += ["--effort", effort]
        kwargs = {"cwd": cwd, "stdin": subprocess.DEVNULL,
                  "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                  "close_fds": True}
        if os.name == "nt":
            kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED | NEW_PROCESS_GROUP
        subprocess.Popen(args, **kwargs)
        detail = f"已投递给 {engine} 会话 {session[:16]}…，它的回复会作为 #{seq} 的回复留言回来"
        store.record_wake(seq, ST_DISPATCHED, detail)
        return ST_DISPATCHED, detail
    except Exception as e:                       # noqa: BLE001
        detail = f"投递失败：{type(e).__name__}: {e}"
        store.record_wake(seq, ST_FAILED, detail)
        return ST_FAILED, detail


def fmt(msg, reader=None, read_seqs=None):
    """一行人话。"""
    seq = msg["seq"]
    # ● 只对「收件人就是当前身份」且还没 ack 的留言有意义
    unread = " "
    if read_seqs is not None and msg.get("recipient") == reader and seq not in read_seqs:
        unread = "●"
    kind = msg.get("kind") or "note"
    tag = {"note": "", "ask": "?", "answer": "↩", "wake": "!"}.get(kind, kind)
    reply = f" ↳#{msg['reply_to']}" if msg.get("reply_to") else ""
    body = (msg.get("body") or "").replace("\r", "")
    if len(body) > 200:
        body = body[:200] + "…"
    head = f"{unread}#{seq:<4} {msg['at'][:19] if msg.get('at') else ''} {msg['sender']}→{msg['recipient']}{reply} {tag}".rstrip()
    return head + "\n      " + body.replace("\n", "\n      ")


def dumps(msg):
    return json.dumps(msg, ensure_ascii=False)
