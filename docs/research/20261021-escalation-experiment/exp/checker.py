#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""checker.py — 隐藏检查器的独立入口（子进程跑，避免模块污染）

用法：python checker.py <题号> <工作目录>
退出码 0=PASS，1=FAIL
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hard as H      # noqa: E402
import hard2 as H2    # noqa: E402
import tasks as T     # noqa: E402

BY = {t["id"]: t for t in (T.TASKS + H.TASKS + H2.TASKS)}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法：python checker.py <题号> <目录>")
        sys.exit(2)
    tid, d = sys.argv[1], Path(sys.argv[2])
    task = BY.get(tid)
    if not task:
        print(f"FAIL 未知题号 {tid}")
        sys.exit(2)
    ok, why = task["check"](d)
    print(("PASS " if ok else "FAIL ") + why)
    sys.exit(0 if ok else 1)
