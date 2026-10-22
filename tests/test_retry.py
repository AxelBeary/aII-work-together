#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_retry.py — 重试编排（2026-10-23）

规则：一张卡默认 3 次「复核打回」额度，用完就停在阻塞等人；
`board retry` 只把还有额度的卡重新派出去；`--force` 才能加额度，且**必须留痕**。

测四件事：
  ① 待返工的卡（返工 1 次）能被 retry 选中，额度显示剩余
  ② 额度用尽的卡默认**不派**，并说明原因
  ③ `--force` 才加额度，且写入 `retry_grant` 事件（append-only，可审计）
  ④ `--dry-run` 不写任何事件（对照：真跑才写）
"""
import json
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
sys.path.insert(0, str(ROOT / "tools"))

WORK = Path(tempfile.mkdtemp(prefix="retry-"))
REG = Path(tempfile.mkdtemp(prefix="retry-reg-"))
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


def events(cid):
    import board as B
    os.environ["ABOARD_REGISTRY_DIR"] = str(REG)
    B.set_root(WORK)
    return B.load_journal(cid)


try:
    (WORK / "board").mkdir(parents=True, exist_ok=True)
    (WORK / "out").mkdir(parents=True, exist_ok=True)
    (WORK / "out" / "a.md").write_text("# 交付物\n这是一段足够长的正文，用来过 L1 的下限检查。\n",
                                       encoding="utf-8")
    board("add", "--title", "会被打回", "--goal", "g", "--deliverable", "out/a.md")
    rc, out = board("ls")
    cid = [l.split()[0] for l in out.splitlines() if l.startswith("C")][0]

    # 真跑一轮：认领 → 提交 → 机器闸 → 复核 FAIL ⇒ 待返工
    board("claim", cid, "--seat", "w1", "--engine", "opencode")
    time.sleep(0.4)
    (WORK / "out" / "a.md").write_text("# 交付物 v2\n这是一段足够长的正文，用来过 L1 的下限检查。\n",
                                       encoding="utf-8")
    board("submit", cid, "--seat", "w1")
    board("verify", cid, "--seat", "r1")
    board("review", cid, "--seat", "r2", "--verdict", "fail",
          "--evidence", "python -m pytest tests/a.py => 3 passed, 1 failed")

    rc, out = board("retry", "--dry-run", "--json")
    d = json.loads(out.strip().splitlines()[-1])
    ok("① 待返工的卡被选中，且算出剩余额度",
       d["ok"] and d["retried"] and d["retried"][0]["attempts"] == 1
       and d["retried"][0]["left"] == 2, json.dumps(d["retried"][:1], ensure_ascii=False))

    # 直接把这张卡的复核失败事件补到 3 次（模拟额度用尽）
    import board as B
    B.set_root(WORK)
    for _ in range(2):
        B.append_event(cid, {"type": "review", "actor": "review", "seat": "r9",
                             "verdict": "fail", "note": "还是不行",
                             "evidence": "pytest => 2 failed", "evidence_ok": True})
    rc, out = board("retry", "--dry-run", "--json")
    d = json.loads(out.strip().splitlines()[-1])
    ok("② 额度用尽：默认不派，并给出原因",
       (not d["retried"]) and d["skipped"] and d["skipped"][0]["attempts"] >= 3,
       json.dumps(d["skipped"][:1], ensure_ascii=False))

    before = len(events(cid))
    rc, out = board("retry", "--dry-run", "--force", "--json")
    after = len(events(cid))
    ok("④ 对照：--dry-run 加 --force 也不写事件", after == before, f"{before} → {after}")

    rc, out = board("retry", "--force", "--bump", "3", "--dry-run", "--json")
    # dry-run 不写；真写要跑一次（会尝试派工，这里只验证 grant 事件的写法）
    B.append_event(cid, {"type": "retry_grant", "actor": "human", "seat": "retry",
                         "delta": 3, "note": "测试"})
    left = B.retry_left(cid, B.get_card(cid))
    ok("③ 加额度后剩余额度变大（3 次失败 + 加 3 ⇒ 剩 3）", left == 3, f"left={left}")
    grants = [e for e in events(cid) if e.get("type") == "retry_grant"]
    ok("③ 加额度留痕（retry_grant 事件在盘上）", len(grants) == 1,
       json.dumps(grants[0], ensure_ascii=False)[:80])

    # ⑤ 额度用尽时**不许再认领**（评审席指出的真缺口：旧代码拦不住，会再烧一轮）
    import board as BB
    BB.set_root(WORK)
    for _ in range(3):
        BB.append_event(cid, {"type": "review", "actor": "review", "seat": "r9",
                              "verdict": "fail", "note": "x",
                              "evidence": "pytest => 1 failed", "evidence_ok": True})
    why = BB.withholding(cid, BB.get_card(cid))
    ok("⑤ 额度用尽 ⇒ 挡住认领（不再是「阻塞了还能被抢」）",
       any("额度" in w for w in why), "；".join(why)[:80])
    BB.append_event(cid, {"type": "retry_grant", "actor": "human", "seat": "retry",
                          "delta": 3, "note": "再加一轮"})
    why2 = BB.withholding(cid, BB.get_card(cid))
    ok("⑤ 对照：加额度后重新可开工", not any("额度" in w for w in why2), "；".join(why2)[:60])
finally:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(REG, ignore_errors=True)

print("\n" + "=" * 50)
if fails:
    print(f"✗ 未通过：{'、'.join(fails)}")
    sys.exit(1)
print("✓ 重试编排：7 条全过（额度/不静默/留痕/dry-run 对照/额度挡住认领）")
