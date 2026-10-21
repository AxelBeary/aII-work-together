#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze.py — 把 runs/*.jsonl 聚合成实验表（含升级归因与误升级率）。

用法：
  python analyze.py                       # 读 runs/ 下全部 jsonl
  python analyze.py runs/a.jsonl runs/b.jsonl
  python analyze.py --md                  # 直接出 Markdown 表（贴进报告用）
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("W", "G", "M", "S", "V")


def load(paths):
    rows = []
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pct(a, b):
    return f"{100.0 * a / b:.0f}%" if b else "—"


def summarize(rows, md=False):
    by = collections.defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)

    print("| 臂 | n | 通过 | 升级 | 真收益 | 白升(本来对) | 升了也没用 | 花费 | 墙钟中位 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for arm in ARMS:
        rs = by.get(arm) or []
        if not rs:
            continue
        n = len(rs)
        p = sum(1 for r in rs if r["passed"])
        tri = sum(1 for r in rs if r.get("triggered"))
        t = sum(1 for r in rs if r.get("outcome") == "escalated_true")
        w = sum(1 for r in rs if r.get("outcome") == "escalated_waste_unneeded")
        bad = sum(1 for r in rs if r.get("outcome") == "escalated_ineffective")
        cost = sum(r.get("cost_actual", r.get("cost") or 0) for r in rs)
        med = statistics.median(r["duration_s"] for r in rs)
        print(f"| {arm} | {n} | {p}/{n} ({pct(p, n)}) | {tri} | {t} | {w} | {bad} | "
              f"${cost:.4f} | {med:.0f}s |")

    print("\n**触发器质量**")
    for arm in ("M", "S"):
        rs = by.get(arm) or []
        tri = [r for r in rs if r.get("triggered")]
        if not tri:
            print(f"- {arm}：0 次触发（无法评估）")
            continue
        waste = sum(1 for r in tri if r.get("outcome") == "escalated_waste_unneeded")
        good = sum(1 for r in tri if r.get("outcome") == "escalated_true")
        dead = sum(1 for r in tri if r.get("outcome") == "escalated_ineffective")
        print(f"- {arm}：触发 {len(tri)} 次；真收益 {good}；白升 {waste}（{pct(waste, len(tri))}）；"
              f"升了也没用 {dead}；**误升级率 = {pct(waste, len(tri))}**")

    v = by.get("V") or []
    if v:
        fixed = sum(1 for r in v if r.get("selfcheck_fixed"))
        broke = sum(1 for r in v if r.get("first_passed") and not r["passed"])
        print(f"\n**V 臂（弱＋自检一轮，不升级）**：{len(v)} 次；自检修好 {fixed}；"
              f"自检**改坏** {broke}（这个数比修好的更重要）")

    miss = sum(1 for r in rows if r.get("conf_missing"))
    if miss:
        print(f"\n⚠️ conf 缺失（判无效样本，未计入升级）：{miss} 条")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--md", action="store_true")
    a = ap.parse_args()
    paths = a.files or sorted(glob.glob(str(HERE / "runs" / "*.jsonl")))
    rows = load(paths)
    if not rows:
        print("没有记录")
        return 1
    print(f"# 记录 {len(rows)} 条，来自 {len(paths)} 个文件\n")
    summarize(rows, a.md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
