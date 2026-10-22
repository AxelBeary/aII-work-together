#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_check_cmd.py — L4 外部门禁（2026-10-23）

卡上可以声明一条 `check_cmd`，提交时必跑：
  · 退出码 0 ⇒ L4 过；非 0 ⇒ 不过（问题里带退出码，事件里存输出尾部）
  · **只对人建的卡生效**（防 agent 建卡借机执行任意命令）
  · 超时 / 起不来 都判不过（不许静默放行）

为什么是它：翻译的 verify.py、代码的 pytest、文档的 lint 都不该由看板重写，
但必须在提交那一刻跑过 —— 否则复核席拿到的是没验过的件。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BOARD = ROOT / "tools" / "board.py"

WORK = Path(tempfile.mkdtemp(prefix="l4-"))
REG = Path(tempfile.mkdtemp(prefix="l4-reg-"))
env = dict(os.environ)
env["ABOARD_REGISTRY_DIR"] = str(REG)
env["PYTHONIOENCODING"] = "utf-8"
env.pop("ABOARD_SEAT", None)

fails = []


def ok(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


def board(*args):
    p = subprocess.run([sys.executable, str(BOARD), "-C", str(WORK)] + list(args),
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def make_card(title, check_cmd, as_agent=False):
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / "a.md").write_text(
        "# 交付物\n这是一段足够长的正文，用来过 L1 的下限检查。\n", encoding="utf-8")
    args = ["add", "--title", title, "--goal", "g", "--deliverable", "out/a.md"]
    if check_cmd:
        args += ["--check-cmd", check_cmd]
    if as_agent:
        args += ["--seat", "agent-x"]
    rc, out = board(*args)
    import re as _re
    m = _re.search(r"C\d{4}-[0-9a-f]{4}", out)
    if not m:
        raise SystemExit(f"建卡失败：{out[:200]}")
    return m.group(0)


def submit(cid, seat):
    board("claim", cid, "--seat", seat, "--engine", "opencode")
    time.sleep(0.4)
    (WORK / "out" / "a.md").write_text(
        f"# 交付物 {seat}\n这是一段足够长的正文，用来过 L1 的下限检查。改动 {seat}。\n",
        encoding="utf-8")
    return board("submit", cid, "--seat", seat)


try:
    # ① 闸门通过
    cid = make_card("L4 通过", "exit 0")
    rc, out = submit(cid, "w1")
    ok("check_cmd 退出 0 ⇒ 提交放行", rc == 0 and "待验收" in out, out.strip()[-60:])

    # ② 闸门失败
    cid = make_card("L4 失败", "echo GATE-BAD && exit 1")
    rc, out = submit(cid, "w2")
    ok("check_cmd 退出 1 ⇒ 提交被拦", "闸门未过" in out and "check_cmd" in out, out.strip()[-80:])
    ok("失败时把命令输出带出来", "GATE-BAD" in out, out.strip()[-120:])

    # ③ 对照：不声明 check_cmd 的卡，行为与以前一样
    cid = make_card("L4 未声明", None)
    rc, out = submit(cid, "w3")
    ok("对照：没声明 check_cmd 照常放行", rc == 0 and "待验收" in out, out.strip()[-40:])

    # ④ agent 建的卡：任意 shell 命令拒跑（只允许 python 跑已存在的脚本）
    cid = make_card("L4 agent 卡", "echo SHOULD-NOT-RUN", as_agent=True)
    rc, out = submit(cid, "w4")
    ok("agent 建卡带任意 shell 命令 ⇒ 拒绝", "未过准入" in out, out.strip()[-80:])
    ok("对照：确实没执行那条命令", "SHOULD-NOT-RUN" not in out, out.strip()[-60:])

    # ⑤ 对照：agent 建卡 + 合规的 python 脚本闸门 ⇒ 放行（这是批量建卡的正常形态）
    gate = WORK / "gate_ok.py"
    gate.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    cid = make_card("L4 agent 合规闸门", f'python "{gate}"', as_agent=True)
    rc, out = submit(cid, "w5")
    ok("对照：agent 卡用合规脚本闸门照常放行", "待验收" in out, out.strip()[-50:])
finally:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(REG, ignore_errors=True)

print("\n" + "=" * 50)
if fails:
    print(f"✗ 未通过：{'、'.join(fails)}")
    sys.exit(1)
print("✓ L4 外部门禁：5 条全过（含 2 条对照）")
