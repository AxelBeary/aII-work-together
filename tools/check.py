#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check.py — 一条命令跑完全部自检

用法：
  python tools/check.py          # 全部检查（改完代码就跑这个）
  python tools/check.py --quick  # 跳过会真调模型的检查

包含五道闸：
  1. 语法        所有 .py 都能 parse
  2. 回归        23 条冻结行为
  3. 反向测试    故意改坏一处必须被抓住
  4. 断点续跑    杀了能接、不重做
  5. 体检+审计   无残留、无绕过痕迹
"""
import argparse
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(name, cmd, expect_rc=0):
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    ok = (p.returncode == expect_rc)
    tail = [l for l in out.strip().splitlines() if l.strip()][-2:]
    print(f"  {'✓' if ok else '✗'} {name:<12} " + " ｜ ".join(t.strip()[:60] for t in tail))
    return ok, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="跳过真调模型的检查")
    a = ap.parse_args()

    print("=" * 70)
    print("全量自检")
    print("=" * 70)

    fails = []

    # 1 语法
    bad = []
    for p in list((ROOT / "tools").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        try:
            ast.parse(p.read_text(encoding="utf-8"))
        except Exception as e:
            bad.append(f"{p.name}: {e}")
    print(f"  {'✓' if not bad else '✗'} {'语法':<12} " +
          (f"{len(list((ROOT/'tools').rglob('*.py'))) + len(list((ROOT/'tests').rglob('*.py')))} 个文件" if not bad else bad[0][:60]))
    if bad:
        fails.append("语法")

    # 2 回归
    ok, _ = run("回归库", [PY, "tests/run_regression.py"])
    if not ok:
        fails.append("回归库")

    # 3 反向测试
    ok, _ = run("反向测试", [PY, "tests/run_regression.py", "--break"])
    if not ok:
        fails.append("反向测试")

    # 4 断点续跑
    ok, _ = run("断点续跑", [PY, "tests/test_resume.py"])
    if not ok:
        fails.append("断点续跑")

    # 5 体检 + 审计
    ok, out = run("审计", [PY, "tools/board.py", "audit"])
    if not ok:
        fails.append("审计")
    ok2, out2 = run("体检", [PY, "tools/board.py", "doctor"])
    if not ok2:
        fails.append("体检")

    # 6（可选）真跑
    if not a.quick:
        ok, _ = run("辩论（真跑）", [PY, "tests/test_debate.py"])
        if not ok:
            fails.append("辩论")

    print("=" * 70)
    if fails:
        print(f"✗ 未通过：{'、'.join(fails)}")
        return 1
    print("✓ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
