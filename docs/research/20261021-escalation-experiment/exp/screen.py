#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""screen.py — 筛题器：只跑弱模型，按「通过率 30–70% 带」筛出有区分度的题。

为什么要有它（2026-10-21 调研结论）：
  题库区分度是**前置条件**，不是实验变量。太易（>70%）与「两个模型都不会」（<30%）
  两端都没有信息量；只保留中间带，才能测出「升级到底救回了多少」。

用法：
  python screen.py --repeat 3                      # 全部题 × 3 次
  python screen.py --tasks N01,N02 --repeat 3
  python screen.py --repeat 3 --out runs/screen-1.json

输出：每题 pass/repeat、耗时中位数、花费；末尾给出 keep / too_easy / too_hard 三档。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import run_experiment as R      # noqa: E402

BAND_LO, BAND_HI = 0.30, 0.70


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    ids = ([x.strip() for x in a.tasks.split(",") if x.strip()]
           or [t["id"] for t in R.ALL_TASKS])
    out = Path(a.out) if a.out else HERE / "runs" / f"screen-{time.strftime('%Y%m%d-%H%M%S')}.json"

    print(f"筛题：{len(ids)} 题 × {a.repeat} 次（模型={R.WEAK}）→ {out}")
    rows = []
    for i, tid in enumerate(ids, 1):
        task = R.BY_ID[tid]
        passes, durs, cost = 0, [], 0.0
        for r in range(a.repeat):
            rec = R.run_task(task, "W", a.timeout)
            passes += 1 if rec["passed"] else 0
            durs.append(rec["duration_s"])
            cost += rec["cost_actual"] or 0.0
            print(f"  [{i}/{len(ids)}] {tid} 第{r + 1}次："
                  f"{'PASS' if rec['passed'] else 'FAIL'}  {rec['duration_s']}s  {rec['check'][:50]}")
        rate = passes / a.repeat
        tag = ("keep" if BAND_LO <= rate <= BAND_HI
               else ("too_easy" if rate > BAND_HI else "too_hard"))
        row = {"task": tid, "cat": task["cat"], "repeat": a.repeat, "passes": passes,
               "pass_rate": round(rate, 3),
               "dur_median_s": round(statistics.median(durs), 1),
               "dur_total_s": round(sum(durs), 1),
               "cost": round(cost, 6), "tag": tag}
        rows.append(row)
        print(f"  ⇒ {tid}: {passes}/{a.repeat} = {rate:.0%}  {tag}")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"weak": R.WEAK, "band": [BAND_LO, BAND_HI],
                               "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                               "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    keeps = [r for r in rows if r["tag"] == "keep"]
    print("\n| 题 | 通过 | 标签 | 中位耗时 |")
    print("|---|---|---|---|")
    for r in rows:
        print(f"| {r['task']} | {r['passes']}/{r['repeat']} | {r['tag']} | {r['dur_median_s']}s |")
    print(f"\n可进实验：{len(keeps)} of {len(rows)} 题"
          f"（{'、'.join(r['task'] for r in keeps) or '无'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
