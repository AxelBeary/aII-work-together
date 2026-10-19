#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ui_api.py — 网页界面接口的「形状契约」

为什么要有：托盘那个「永远是 0 张」的毛病，就是因为它以为 /api/state 里有卡片数据。
接口字段一旦被当契约用，就必须有测试钉住，否则改后端会静默弄坏另一个程序。

这个测只造几张卡，跑得很快，进 check.py 常规闸。

跑法：python tests/test_ui_api.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PORT = 8793
SANDBOX = Path(tempfile.mkdtemp(prefix="aboard-api-"))
REG = SANDBOX / "reg"
PROJ = SANDBOX / "demo"


def call(path, body=None, expect=200):
    url = f"http://127.0.0.1:{PORT}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


fails = []


def ok(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


def main():
    PROJ.mkdir(parents=True)
    os.environ["ABOARD_REGISTRY_DIR"] = str(REG)
    sys.path.insert(0, str(ROOT / "tools"))
    import projects as P
    P.add_project(PROJ)

    env = dict(os.environ)
    env["ABOARD_REGISTRY_DIR"] = str(REG)
    env["PYTHONIOENCODING"] = "utf-8"
    srv = subprocess.Popen(
        [sys.executable, str(ROOT / "tools" / "server.py"), "--port", str(PORT)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):
            try:
                call("/api/state")
                break
            except Exception:
                time.sleep(0.25)

        # 1 建卡
        code, r = call("/api/card", {"project": str(PROJ), "id": "D-001",
                                     "title": "契约测试卡", "goal": "钉住接口形状"})
        ok("建卡返回 ok", code == 200 and r.get("ok"), f"HTTP {code}")

        # 2 首页：只有项目信息，不该夹带卡片数据
        code, st = call(f"/api/state?project={PROJ}")
        ok("/api/state 有 current/projects",
           code == 200 and "current" in st and isinstance(st.get("projects"), list))
        ok("/api/state 不夹带卡片（托盘曾因此显示 0 张）",
           "counts" not in st and "total" not in st,
           f"keys={sorted(st.keys())}")

        # 3 卡片列表：托盘与界面都靠它数数
        code, cl = call(f"/api/cards?project={PROJ}")
        cards = cl.get("cards", [])
        ok("/api/cards 有 id 与 state",
           code == 200 and len(cards) == 1
           and cards[0]["id"] == "D-001" and cards[0]["state"] == "待认领",
           f"{len(cards)} 张")
        ok("/api/cards 带用量字段（界面要显示花费）",
           "usage" in cards[0] and "cost" in cards[0]["usage"])
        ok("/api/cards 带评审摘要（几席、改后剩几条未改）",
           isinstance(cards[0].get("consult"), dict)
           and "seats" in cards[0]["consult"]
           and "unfixed" in cards[0]["consult"],
           f"consult={cards[0].get('consult')}")

        # 4 单卡详情带事件流
        code, one = call(f"/api/card?project={PROJ}&id=D-001")
        ok("/api/card 带经过（events）",
           code == 200 and isinstance(one.get("events"), list) and len(one["events"]) >= 1,
           f"{len(one.get('events', []))} 条")

        # 5 用量汇总
        code, cost = call(f"/api/cost?project={PROJ}")
        tot = cost.get("total", {})
        ok("/api/cost 有 total 且字段齐全",
           code == 200 and {"input", "output", "cost", "calls"} <= set(tot),
           f"calls={tot.get('calls')}")

        # 6 错误要能看懂（人话）
        code, err = call("/api/cards?project=" + urllib.parse.quote("不存在的项目"))
        ok("查不存在的项目返回 400 + 人话", code == 400 and "没找到项目" in err.get("error", ""),
           err.get("error", "")[:40])

        # 7 重号建卡必须被拒（不能静默覆盖）
        code, err = call("/api/card", {"project": str(PROJ), "id": "D-001",
                                       "title": "同名覆盖尝试"})
        ok("重号建卡被拒", code == 400 and "已存在" in err.get("error", ""),
           err.get("error", "")[:40])
        code, cl = call(f"/api/cards?project={PROJ}")
        ok("被拒后原来那张没被改掉",
           cl["cards"][0]["title"] == "契约测试卡", cl["cards"][0]["title"])

        # 8 全部项目总览
        P2 = SANDBOX / "demo2"
        P2.mkdir()
        P.add_project(P2)
        call("/api/card", {"project": str(P2), "id": "E-001",
                           "title": "第二个项目的卡", "goal": ""})
        code, st2 = call("/api/state?project=__all__")
        ok("/api/state 支持总览模式", code == 200, f"HTTP {code}")
        code, allc = call("/api/cards?project=__all__")
        got = allc.get("cards", [])
        ok("总览把两个项目的卡都汇齐", len(got) == 2, f"{len(got)} 张")
        ok("总览每张卡带项目名与项目路径",
           all(c.get("project") and c.get("project_path") for c in got),
           "、".join(sorted({c.get("project", "?") for c in got})))
        ok("总览不串项目",
           {c["id"]: c["project"] for c in got}
           == {"D-001": "demo", "E-001": "demo2"},
           str({c["id"]: c["project"] for c in got}))

        print(f"\n{'=' * 50}")
        if fails:
            print(f"✗ 未通过：{'、'.join(fails)}")
            return 1
        print("✓ 接口形状契约全部通过")
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
