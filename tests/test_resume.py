#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_resume.py — 断点续跑的反向测试

证明三件事（每条都是「必须非零」的对照）：
  1. 已完成卡 → 续跑**不重做**（执行计数必须为 0）
  2. 进行中但租约超时 → 续跑**回收并重跑**（计数必须为 1）
  3. 待验收 → 续跑**直接复核、不重做**（执行计数 0，复核计数 1）

运行：python tests/test_resume.py
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import board as B          # noqa: E402
import resume as R         # noqa: E402

COUNTER = ROOT / "tests" / ".resume_counter.json"


def _reset_counter():
    COUNTER.write_text(json.dumps({"exec": {}, "review": {}}), encoding="utf-8")


def _bump(kind, cid):
    c = json.loads(COUNTER.read_text(encoding="utf-8"))
    c[kind][cid] = c[kind].get(cid, 0) + 1
    COUNTER.write_text(json.dumps(c), encoding="utf-8")


def _make_card(cid, state):
    """造一张卡并推到指定状态。"""
    d = B.CARDS / cid
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "artifacts").mkdir()
    (d / "evidence").mkdir()
    (d / "lease" / "active").mkdir(parents=True)
    B.jwrite(d / "card.json", {
        "id": cid, "title": f"test {cid}", "goal": "", "territory": [],
        "deliverables": [], "accept_patterns": [], "human_gate": "none",
        "created_at": "x", "created_by": "test", "created_kind": "human",
        "irreversible": False, "engine": "any", "model": "any", "effort": "any",
    })
    B.append_event(cid, {"type": "created", "actor": "human", "seat": "test"})

    if state == "完成":
        B.claim(cid, "w1", "fake")
        B.append_event(cid, {"type": "submit", "seat": "w1", "gate": {"L1": True}})
        B.append_event(cid, {"type": "verify", "seat": "r1"})
        B.append_event(cid, {"type": "review", "seat": "r1", "verdict": "pass",
                             "evidence": "1 file ok"})
        B.release(cid)

    elif state == "待验收":
        B.claim(cid, "w1", "fake")
        B.append_event(cid, {"type": "submit", "seat": "w1", "gate": {"L1": True}})
        B.release(cid)

    elif state == "进行中":
        B.claim(cid, "w1", "fake")
        # 手工把心跳时间改老，模拟崩溃
        lease = B.active_lease(cid)
        owner = B._lease_owner(lease)
        owner["at_ms"] = B.now_ms() - (B.LEASE_TTL + 60) * 1000
        B.jwrite(lease / "owner.json", owner)
    return cid


def main():
    _reset_counter()
    # 清掉上次的测试卡
    for cid in ("RT-DONE", "RT-STALE", "RT-REVIEW"):
        d = B.CARDS / cid
        if d.exists():
            shutil.rmtree(d)

    _make_card("RT-DONE", "完成")
    _make_card("RT-STALE", "进行中")
    _make_card("RT-REVIEW", "待验收")

    def fake_execute(card, cid):
        _bump("exec", cid)
        B.claim(cid, "resume-w", "fake")
        B.append_event(cid, {"type": "submit", "seat": "resume-w",
                             "gate": {"L1": True}})
        return "ok"

    def fake_review(card, cid):
        _bump("review", cid)
        B.append_event(cid, {"type": "verify", "seat": "resume-r"})
        B.append_event(cid, {"type": "review", "seat": "resume-r",
                             "verdict": "pass", "evidence": "1 ok"})
        B.release(cid)
        return "pass"

    results = R.resume(fake_execute, fake_review,
                       only=["RT-DONE", "RT-STALE", "RT-REVIEW"])
    c = json.loads(COUNTER.read_text(encoding="utf-8"))

    print("续跑结果：")
    for cid, act, out in results:
        if cid.startswith("RT-"):
            print(f"  {cid:<12} {act:<10} {out}")

    fails = []

    # 1 已完成卡不许重做
    n = c["exec"].get("RT-DONE", 0)
    print(f"\n1. 已完成卡被重做次数 = {n}  (必须 0)")
    if n != 0:
        fails.append("已完成卡被重做了")

    # 2 超时卡必须被回收并重跑
    n = c["exec"].get("RT-STALE", 0)
    print(f"2. 超时卡被重跑次数   = {n}  (必须 1)")
    if n != 1:
        fails.append("超时卡没被重跑")

    # 3 待验收卡必须只复核、不重做
    ne = c["exec"].get("RT-REVIEW", 0)
    nr = c["review"].get("RT-REVIEW", 0)
    print(f"3. 待验收卡：重做 {ne}（必须 0）/ 复核 {nr}（必须 1）")
    if ne != 0 or nr != 1:
        fails.append("待验收卡的续跑行为不对")

    # 反向对照：确认计数工具不是永远为 0
    total = sum(c["exec"].values()) + sum(c["review"].values())
    print(f"\n反空跑对照：计数总和 = {total}  (必须 > 0，否则说明计数器坏了)")
    if total == 0:
        fails.append("计数器可能坏了（总和为 0）")

    print()
    if fails:
        print("FAIL：")
        for f in fails:
            print(f"  · {f}")
        return 1
    print("PASS：断点续跑三条判据全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
