#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_batch.py — 批量建卡（2026-10-23）

给 AI 调用的硬要求，逐条测：
  ① `--dry-run` 不写盘（但要把计划打出来）
  ② 真建按 JSON 建出 N 张
  ③ **幂等**：同一个 `key` 再跑一次必须跳过，不重复建
  ④ `check_cmd` 过准入：`rm -rf /` 这种必须拒（只允许 python 跑已存在的脚本）
  ⑤ 部分失败不许静默：坏项报错、好项照建、退出码 1
  ⑥ `--json` 输出形状稳定（ok/created/skipped/errors）
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
BOARD = ROOT / "tools" / "board.py"

WORK = Path(tempfile.mkdtemp(prefix="batch-"))
REG = Path(tempfile.mkdtemp(prefix="batch-reg-"))
env = dict(os.environ)
env["ABOARD_REGISTRY_DIR"] = str(REG)
env["PYTHONIOENCODING"] = "utf-8"
env.pop("ABOARD_SEAT", None)

fails = []


def ok(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


def board(*args, stdin=None):
    p = subprocess.run([sys.executable, str(BOARD), "-C", str(WORK)] + list(args),
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", input=stdin)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def count():
    rc, out = board("ls")
    return sum(1 for l in out.splitlines() if l.startswith("C"))


try:
    (WORK / "board").mkdir(parents=True, exist_ok=True)
    plan = {"cards": [
        {"key": "k1", "title": "甲", "goal": "a"},
        {"key": "k2", "title": "乙", "goal": "b"},
    ]}
    raw = json.dumps(plan, ensure_ascii=False)

    # ① dry-run
    rc, out = board("add-batch", "--dry-run", "--json", stdin=raw)
    ok("dry-run 不写盘", count() == 0 and rc == 0, f"卡数={count()} rc={rc}")
    ok("dry-run 仍给出计划", "k1" in out and "dry_run" in out, out.strip()[:60])

    # ② 真建
    rc, out = board("add-batch", stdin=raw)
    ok("按 JSON 建出 2 张", count() == 2 and rc == 0, f"卡数={count()}")

    # ③ 幂等
    rc, out = board("add-batch", "--json", stdin=raw)
    d = json.loads(out.strip().splitlines()[-1])
    ok("同 key 再跑：全跳过、不重复建", count() == 2 and len(d["skipped"]) == 2
       and len(d["created"]) == 0, f"卡数={count()} skipped={len(d['skipped'])}")

    # ④ check_cmd 准入
    bad = json.dumps({"cards": [{"title": "坏闸门", "key": "k3", "check_cmd": "rm -rf /"}]},
                     ensure_ascii=False)
    rc, out = board("add-batch", "--json", stdin=bad)
    ok("任意 shell 命令被拒（只允许 python 跑脚本）",
       rc == 1 and "未过准入" in out, out.strip()[:80])

    gate = WORK / "gate_ok.py"
    gate.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    good = json.dumps({"cards": [{
        "title": "好闸门", "key": "k4",
        "check_cmd": f'python "{gate}"'}]}, ensure_ascii=False)
    rc, out = board("add-batch", "--json", stdin=good)
    ok("对照：python 跑工作区内的脚本可以过", rc == 0 and '"created"' in out, out.strip()[:80])

    # ⑤ 部分失败不许静默
    mixed = json.dumps({"cards": [
        {"title": "好的", "key": "k5"},
        {"goal": "缺标题"},
    ]}, ensure_ascii=False)
    rc, out = board("add-batch", "--json", stdin=mixed)
    d = json.loads(out.strip().splitlines()[-1])
    ok("部分失败：好项照建、坏项报错、退出码 1",
       rc == 1 and len(d["created"]) == 1 and len(d["errors"]) == 1, out.strip()[:80])

    # ⑥ json 形状
    ok("--json 形状稳定（ok/created/skipped/errors）",
       set(d) == {"ok", "created", "skipped", "errors"}, str(sorted(d)))
finally:
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(REG, ignore_errors=True)

print("\n" + "=" * 50)
if fails:
    print(f"✗ 未通过：{'、'.join(fails)}")
    sys.exit(1)
print("✓ 批量建卡：7 条全过（含 dry-run/幂等/准入/部分失败）")
