#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_review_items.py — 结构化复核意见 + 收口刹车（2026-10-23）

为什么要有这条闸：
  自由文本意见没法对账——第三轮时谁也不知道「上一轮那几条改了没有」。
  现在意见带稳定 ID 与二值状态，于是可以机械地问三件事：
    ① 还有 open 的意见，⛔ 不许 PASS；
    ② 全标 fixed 却给 fail，⛔ 不许（自相矛盾）；
    ③ 同一条意见连续 3 轮没解决，⛔ 不再自动转圈（要 --force 或转阻塞）。

每条都配对照（正常情形必须仍然能过），否则就是「为了拦而拦」。
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

WORK = Path(tempfile.mkdtemp(prefix="rv-items-"))
REG = Path(tempfile.mkdtemp(prefix="rv-items-reg-"))
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


def edit(tag):
    time.sleep(0.4)
    (WORK / "out" / "a.md").write_text(
        f"# 交付物 {tag}\n这是一段足够长的正文，用来过 L1 的下限检查。改动 {tag}。\n",
        encoding="utf-8")


(WORK / "board").mkdir(parents=True, exist_ok=True)
(WORK / "out").mkdir(parents=True, exist_ok=True)
(WORK / "out" / "a.md").write_text("# 交付物\n这是一段足够长的正文，用来过 L1 的下限检查。\n",
                                   encoding="utf-8")

board("add", "--title", "意见对账", "--goal", "看意见能不能收敛", "--deliverable", "out/a.md")
rc, out = board("ls")
CID = [l.split()[0] for l in out.splitlines() if l.startswith("C")][0]

try:
    # 第 1 轮：T1 open / T2 fixed —— 不该出现「两轮未解决」的警告
    board("claim", CID, "--seat", "w1", "--engine", "opencode")
    edit("r1")
    board("submit", CID, "--seat", "w1")
    board("verify", CID, "--seat", "w1")
    rc, out = board("review", CID, "--seat", "w2", "--verdict", "fail",
                    "--evidence", "python -m pytest tests/a_test.py => 12 passed, 2 failed",
                    "--item", "T1:open:标题层级不对", "--item", "T2:fixed:错别字已改")
    ok("第 1 轮退回复核成功", rc == 0, out.strip().splitlines()[-1][:50] if out else "")
    ok("第 1 轮不该报「两轮未解决」", "上一轮就是 open" not in out, out.strip()[:40])

    # 第 2 轮：T1 仍然 open —— 必须报出来
    board("claim", CID, "--seat", "w3", "--engine", "opencode")
    edit("r2")
    board("submit", CID, "--seat", "w3")
    board("verify", CID, "--seat", "w3")
    rc, out = board("review", CID, "--seat", "w4", "--verdict", "fail",
                    "--evidence", "python -m pytest tests/a_test.py => 12 passed, 2 failed",
                    "--item", "T1:open:标题层级还是不对")
    ok("第 2 轮报出「上一轮就是 open」", rc == 0 and "上一轮就是 open" in out, out.strip()[:60])

    # 守卫①：还有 open 却给 PASS
    board("claim", CID, "--seat", "w5", "--engine", "opencode")
    edit("r3")
    board("submit", CID, "--seat", "w5")
    board("verify", CID, "--seat", "w5")
    rc, out = board("review", CID, "--seat", "w6", "--verdict", "pass",
                    "--evidence", "python -m pytest tests/a_test.py => 14 passed, 0 failed",
                    "--item", "T1:open:没改")
    ok("守卫①：带 open 意见不许 PASS", rc != 0 and "不能给 PASS" in out, out.strip()[:60])

    # 守卫②：全 fixed 却给 fail
    rc, out = board("review", CID, "--seat", "w6", "--verdict", "fail",
                    "--evidence", "python -m pytest tests/a_test.py => 14 passed, 0 failed",
                    "--item", "T1:fixed:改好了")
    ok("守卫②：全 fixed 不许给 fail", rc != 0 and "全部标成 fixed" in out, out.strip()[:60])

    # 闸③：第 3 轮仍是同一条 —— 必须先 --force 才放行
    rc, out = board("review", CID, "--seat", "w6", "--verdict", "fail",
                    "--evidence", "python -m pytest tests/a_test.py => 12 passed, 2 failed",
                    "--item", "T1:open:还是不对")
    ok("闸③：同一意见第 3 轮默认拦下", rc != 0 and "不再自动转圈" in out, out.strip()[:60])

    rc, out = board("review", CID, "--seat", "w6", "--verdict", "fail", "--force",
                    "--evidence", "python -m pytest tests/a_test.py => 12 passed, 2 failed",
                    "--item", "T1:open:还是不对")
    ok("闸③对照：带 --force 可以继续", rc == 0, out.strip().splitlines()[-1][:50] if out else "")

    # show 里能看见「第 N 轮 / 卡住」
    rc, out = board("show", CID)
    ok("show 显示轮次与卡住项", "卡住" in out and "两轮未解决" in out, out.strip()[:40])
finally:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(REG, ignore_errors=True)

print("\n" + "=" * 50)
if fails:
    print(f"✗ 未通过：{'、'.join(fails)}")
    sys.exit(1)
print("✓ 结构化意见 + 收口刹车：8 条全过（含 2 条对照）")
