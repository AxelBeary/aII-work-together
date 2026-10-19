#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench_scale.py — 几十个项目时的界面响应速度

为什么单独测：网页每 5 秒自动刷新一次，刷新打的是 /api/state + /api/cards。
几十个项目、几千张卡时如果这两条要几秒，界面就是摆设。

口径：开一个隔离注册表，造 N 个项目 × M 张卡（每张带几条事件），
     起真服务器，对每个接口跑 3 次取中位数。

跑法：
    python tests/bench_scale.py            # 默认 20 项目 × 15 卡
    python tests/bench_scale.py 40 25      # 自定义规模
"""
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOLS = ROOT / "tools"
PORT = 8792
SANDBOX = Path(tempfile.mkdtemp(prefix="aboard-bench-"))
REG = SANDBOX / "reg"

sys.path.insert(0, str(TOOLS))
os.environ["ABOARD_REGISTRY_DIR"] = str(REG)
import board as B          # noqa: E402
import projects as P       # noqa: E402


def build(n_projects, n_cards):
    roots = []
    for i in range(n_projects):
        d = SANDBOX / f"p{i:02d}"
        d.mkdir(parents=True)
        roots.append(d)
        P.add_project(d)
        prev_root, prev_ws = B.ROOT, B.WORKSPACE
        try:
            B.set_root(d)
            B.set_workspace(d)
            for j in range(n_cards):
                cid = f"P{i:02d}-{j:03d}"
                B.create_card({
                    "id": cid, "title": f"项目{i} 卡{j}", "goal": "压测用的目标描述",
                    "territory": [], "deliverables": [], "accept_patterns": [],
                    "human_gate": "none", "engine": "opencode",
                    "model": "opencode-go/deepseek-v4.1-flash", "effort": "any",
                    "created_at": B.ts(), "created_by": "bench",
                    "created_kind": "human", "irreversible": False,
                    "source_card": None,
                })
                B.append_event(cid, {"type": "created", "actor": "human",
                                     "seat": "bench", "title": f"卡{j}"})
                B.append_event(cid, {"type": "note", "note": "一条普通记录"})
                B.append_event(cid, {"type": "usage", "usage": {
                    "available": True, "input": 1200, "output": 300,
                    "cache_read": 800, "cache_write": 100, "cost": 0.0021}})
        finally:
            B.set_root(prev_root)
            B.set_workspace(prev_ws)
    return roots


def timed_get(url, n=3):
    times = []
    body = None
    for _ in range(n):
        t0 = time.perf_counter()
        with urllib.request.urlopen(url, timeout=120) as r:
            body = r.read()
        times.append((time.perf_counter() - t0) * 1000)
    return statistics.median(times), len(body), times


def main():
    n_projects = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    n_cards = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    print(f"造数据：{n_projects} 个项目 × {n_cards} 张卡 …")
    t0 = time.perf_counter()
    roots = build(n_projects, n_cards)
    print(f"  建完用了 {time.perf_counter() - t0:.1f}s")

    env = dict(os.environ)
    env["ABOARD_REGISTRY_DIR"] = str(REG)
    env["PYTHONIOENCODING"] = "utf-8"
    srv = subprocess.Popen(
        [sys.executable, str(TOOLS / "server.py"), "--port", str(PORT)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{PORT}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/state", timeout=60).read()
                break
            except Exception:
                time.sleep(0.25)

        cur = roots[0].name
        cases = [
            ("首页刷新：项目列表", f"{base}/api/state?project={cur}"),
            ("看板列表：当前项目全部卡", f"{base}/api/cards?project={cur}"),
            ("用量汇总", f"{base}/api/cost?project={cur}"),
            ("单卡详情", f"{base}/api/card?project={cur}&id=P00-000"),
        ]
        print(f"\n{'接口':<28}{'中位数':>10}{'响应体':>12}")
        print("-" * 52)
        worst = 0
        for name, url in cases:
            ms, size, runs = timed_get(url)
            worst = max(worst, ms)
            print(f"{name:<28}{ms:>8.0f}ms{size/1024:>10.0f}KB")

        # 冷缓存：删掉汇总缓存，等 TTL 过期再打一次（这才是每 15 秒一次的真成本）
        cache = REG / "summary-cache.json"
        if cache.exists():
            cache.unlink()
        time.sleep(16)
        cold, _, cold_runs = timed_get(f"{base}/api/state?project={cur}", n=3)
        print("-" * 52)
        print(f"{'首页刷新（缓存过期那一下）':<28}{cold:>8.0f}ms")
        print(f"  三次实测：{' / '.join(f'{x:.0f}ms' for x in cold_runs)}")

        print("-" * 52)
        print(f"最慢一条：{worst:.0f}ms")
        if worst > 2000:
            print("✗ 太慢：自动刷新会明显卡顿（阈值 2000ms）")
            return 1
        if worst > 800:
            print("⚠ 偏慢：能忍，但刷新时会有可感停顿（阈值 800ms）")
            return 0
        print("✓ 流畅（<800ms）")
        return 0
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:
            srv.kill()
        shutil.rmtree(SANDBOX, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
