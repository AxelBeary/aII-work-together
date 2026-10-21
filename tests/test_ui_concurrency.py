#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ui_concurrency.py — 网页界面多项目并发安全

怀疑的 bug：
  server.py 的每个接口都靠 `B.set_root(...)` 切全局状态，
  而 ThreadingHTTPServer 是「一请求一线程」。
  ⇒ 两个标签页指向不同项目时，A 的请求可能用上 B 的项目根。

这个测试用真 HTTP 并发打两个项目，检查有没有卡被建丢/建错地方。
失败＝真 bug（会把卡写进别的项目），必须修。

跑法：python tests/test_ui_concurrency.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PORT = 8791
SANDBOX = Path(tempfile.mkdtemp(prefix="aboard-ui-"))
REG = SANDBOX / "reg"
PROJS = [SANDBOX / "alpha", SANDBOX / "beta"]
PER_PROJECT = 25


def _token():
    p = ROOT / "board" / "ui-server.tok"
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def post(url, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "X-Board-Token": _token()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    for p in PROJS:
        p.mkdir(parents=True)
    env = dict(os.environ)
    env["ABOARD_REGISTRY_DIR"] = str(REG)
    env["PYTHONIOENCODING"] = "utf-8"

    # 先在同一个注册表里登记两个项目（否则接口按路径找不到）
    os.environ["ABOARD_REGISTRY_DIR"] = str(REG)
    sys.path.insert(0, str(ROOT / "tools"))
    import projects as P
    for p in PROJS:
        P.add_project(p)

    srv = subprocess.Popen(
        [sys.executable, str(ROOT / "tools" / "server.py"), "--port", str(PORT)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{PORT}"
    try:
        for _ in range(40):
            try:
                get(base + "/api/state")
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("[FAIL] 服务器起不来")
            return 1

        # 登记两个项目（各建一张预热卡，用显式编号免得和统计口径混淆）
        for p in PROJS:
            post(base + "/api/card",
                 {"project": str(p), "id": f"{p.name.upper()}-WARM",
                  "title": "warmup", "goal": ""})

        errors = []

        def worker(proj, n):
            for i in range(n):
                cid = f"{proj.name.upper()}-{i:03d}"
                try:
                    post(base + "/api/card", {
                        "project": str(proj), "id": cid,
                        "title": f"{proj.name} 的卡 {i}", "goal": "并发压测",
                    })
                except Exception as e:
                    errors.append(f"{cid}: {e}")

        ts = []
        for p in PROJS:
            ts.append(threading.Thread(target=worker, args=(p, PER_PROJECT)))
        # 再多加几个读线程，模拟「另一个标签页在刷新」
        for _ in range(4):
            ts.append(threading.Thread(
                target=lambda: [get(base + "/api/cards?project=" + str(PROJS[0]))
                                for _ in range(20)]))
        for t in ts:
            t.start()
        for t in ts:
            t.join()

        problems = []
        if errors:
            problems.append(f"{len(errors)} 次建卡失败：{errors[:2]}")

        # 每个项目里必须只有自己的卡
        for p in PROJS:
            cards = get(base + "/api/cards?project=" + str(p))["cards"]
            ids = {c["id"] for c in cards}
            prefix = p.name.upper() + "-"
            mine = {i for i in ids if i.startswith(prefix)}
            foreign = ids - mine
            if foreign:
                problems.append(f"{p.name} 里混进了别人的卡：{sorted(foreign)[:4]}")
            if len(mine) != PER_PROJECT + 1:      # +1 预热卡
                problems.append(f"{p.name} 只有 {len(mine)} 张自己的卡"
                                f"（期望 {PER_PROJECT + 1}）")

        print(f"每个项目建了 {PER_PROJECT} 张，两项目并发 + 4 个读线程")
        if problems:
            print("\n[FAIL] 发现跨项目污染：")
            for x in problems:
                print("  -", x)
            return 1
        print("[PASS] 没有串项目，一张都没丢")
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
