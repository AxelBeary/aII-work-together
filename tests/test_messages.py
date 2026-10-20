#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_messages.py — 跨会话留言的闸（吸收 ocs 的那四条语义）

钉住的四件事：
  1. append-only + 单调 seq：留言只增不改，已读另记一张表
  2. reply_to 可寻址、thread 能把整条线拉出来
  3. inbox 只列新留言，标已读之后不再重复弹（ack 幂等）
  4. ⛔ 唤不醒就说唤不醒：没会话 ＝ HELD ＋ 退出码 2；已回复过的不重发

反向测试：⚠️ 每条「0」都必须配一条「必须非零」的对照，
          否则「没有未读」可能只是计数器坏了而不是真读了。

跑法：python tests/test_messages.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SANDBOX = Path(tempfile.mkdtemp(prefix="aboard-msg-"))
PROJ = SANDBOX / "demo"

fails = []


def ok(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


def board(*args, expect=0):
    env = dict(os.environ)
    env["ABOARD_REGISTRY_DIR"] = str(SANDBOX / "reg")
    env["PYTHONIOENCODING"] = "utf-8"
    env["ABOARD_SEAT"] = "tester"
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "board.py"),
                        "-C", str(PROJ)] + list(args),
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def msg_json(*args, expect=0):
    rc, out = board(*args, "--json")
    try:
        return rc, json.loads(out.strip().splitlines()[-1])
    except Exception:
        return rc, None


def main():
    PROJ.mkdir(parents=True)
    board("init")

    # 1 顺序号单调：两条留言拿到的号必须递增
    rc, m1 = msg_json("msg", "send", "--to", "w1", "--body", "第一句",
                      "--from", "b1")
    rc2, m2 = msg_json("msg", "send", "--to", "w1", "--body", "第二句",
                       "--from", "b1")
    ok("发两条留言都成功", rc == 0 and rc2 == 0 and m1 and m2,
       f"rc={rc},{rc2}")
    ok("seq 单调递增", m1 and m2 and m2["seq"] == m1["seq"] + 1,
       f"{m1 and m1['seq']} → {m2 and m2['seq']}")

    # 2 回复可寻址
    rc, m3 = msg_json("msg", "send", "--to", "b1", "--body", "回你的第一句",
                      "--from", "w1", "--reply-to", str(m1["seq"]),
                      "--kind", "answer")
    ok("回复记下了 reply_to", rc == 0 and m3 and m3["reply_to"] == m1["seq"],
       f"reply_to={m3 and m3.get('reply_to')}")

    rc, out = board("msg", "thread", str(m1["seq"]))
    ok("thread 把整条线拉出来（2 条）", rc == 0 and out.count("#") >= 2,
       f"{out.count('#')} 处编号")

    # 3 收件箱只列新的；标已读后不重复弹
    rc, out = board("msg", "inbox", "--as", "w1")
    ok("w1 第一次收件箱有 2 条", "2 条新" in out, out.strip().splitlines()[0][:40])
    rc, out = board("msg", "inbox", "--as", "w1")
    ok("w1 第二次收件箱空了（已读生效）", "没有新留言" in out,
       out.strip().splitlines()[0][:40])
    # ⚠️ 对照：b1 还有 1 条未读（证明「空」不是计数器坏了）
    rc, out = board("msg", "inbox", "--as", "b1")
    ok("对照：b1 仍有 1 条新（空不是假绿）", "1 条新" in out,
       out.strip().splitlines()[0][:40])

    # 3b --json --wake：整个输出必须是一个 JSON 对象（Q1 #9 修的就是这里夹人话）
    pj = subprocess.run([sys.executable, str(ROOT / "tools" / "board.py"),
                         "-C", str(PROJ), "msg", "send", "--to", "w1",
                         "--body", "唤醒测试", "--from", "b1", "--json",
                         "--wake", "--wake-engine", "opencode"],
                        cwd=str(ROOT), env=dict(os.environ, **{
                            "ABOARD_REGISTRY_DIR": str(SANDBOX / "reg"),
                            "PYTHONIOENCODING": "utf-8", "ABOARD_SEAT": "tester"}),
                        capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    raw = (pj.stdout or "").strip()
    parsed = None
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    ok("--json --wake 整体是一个 JSON（不夹人话）", parsed is not None,
       raw[:70].replace("\n", "⏎"))
    ok("唤醒结果在 JSON 的 wake 字段里，且退出码分档",
       isinstance(parsed, dict) and isinstance(parsed.get("wake"), dict)
       and parsed["wake"].get("state") in ("HELD", "FAILED", "SENT", "DISPATCHED")
       and pj.returncode in (0, 2, 3),
       f"rc={pj.returncode} wake={parsed and parsed.get('wake')}")

    # 4 append-only：已读不写 messages 表，只往 msg_reads 追加
    sys.path.insert(0, str(ROOT / "tools"))
    import storage
    st = storage.Store(PROJ / "board" / "board.db", PROJ / "board" / "evidence")
    before = len(st.messages(limit=999))
    board("msg", "ack", str(m1["seq"]), "--as", "w1")     # 再 ack 一次
    after = len(st.messages(limit=999))
    ok("已读不改留言表（append-only）", before == after and after >= 4,
       f"{before} → {after}")
    reads = st.reads("w1")
    ok("msg_reads 里 w1 有 2 条已读", len(reads) == 2, f"{len(reads)} 条")
    ok("ack 幂等（重复 ack 不涨行）", st.mark_read(m1["seq"], "w1") is False)

    # 5 唤不醒就如实说：没会话 ＝ HELD ＋ 退出码 2
    rc, out = board("msg", "send", "--to", "w2", "--body", "唤醒试试",
                    "--from", "b1", "--wake")
    ok("没会话的唤醒＝HELD 且退出码 2", rc == 2 and "HELD" in out,
       f"rc={rc} {out.strip().splitlines()[-1][:50]}")
    seq_held = st.messages(to="w2", limit=1)[0]["seq"]
    ok("HELD 也留了唤醒记录", (st.last_wake(seq_held) or {}).get("state") == "HELD",
       str(st.last_wake(seq_held)))

    # 6 不重发：已回复过的一律拒绝
    import messages as M
    st.record_wake(seq_held, M.ST_DELIVERED, "测试里手动记成已回复")
    state, detail = M.wake(st, seq_held, engine="opencode", session="ses_x")
    ok("已回复过的不重发", state == M.ST_HELD and "不重发" in detail, detail[:50])
    walks = [w for w in st.wakes(seq_held)]
    ok("拒绝重发时没有新增投递记录", len(walks) == 2, f"{len(walks)} 条唤醒记录")

    # 7 空正文必须被拒（别让空留言进历史）
    rc, out = board("msg", "send", "--to", "w1", "--body", "   ")
    ok("空正文被拒", rc != 0, f"rc={rc}")

    print(f"\n{'=' * 50}")
    if fails:
        print(f"✗ 未通过：{'、'.join(fails)}")
        return 1
    print(f"✓ 留言闸全过（{len(st.messages(limit=999))} 条留言、"
          f"{len(st.wakes())} 条唤醒记录）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(SANDBOX, ignore_errors=True)
