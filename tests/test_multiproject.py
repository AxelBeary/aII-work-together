#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_multiproject.py — 多项目（几十个）压测

为什么单独有这个测：主回归库只覆盖了单项目。
「几十个项目同时使用」是这个项目的第一需求，却一直没有被真正压过。

覆盖：
  P1  批量建 12 个项目，注册表全部登记成功
  P2  每个项目各建 3 张卡，互不串扰
  P3  跨项目汇总（project_summary）数量对得上
  P4  从子目录向上找到正确的项目根
  P5  重名冲突必须被明确拒绝（而不是静默覆盖）
  P6  注册表并发写（8 线程同时登记）不丢条目
  P7  删掉一个项目只影响它自己
  P8  反空跑对照：故意查一个不存在的项目必须查不到

跑法：
    python tests/test_multiproject.py
退出码 0＝全过，1＝有失败。
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))

# ⚠️ 必须在 import projects 之前设好，否则会写到真实注册表
_SANDBOX = Path(tempfile.mkdtemp(prefix="aboard-test-"))
os.environ["ABOARD_REGISTRY_DIR"] = str(_SANDBOX / "registry-home")

import board as B          # noqa: E402
import projects as P       # noqa: E402

N_PROJECTS = 12
CARDS_EACH = 3

results = []


def check(name, fn):
    try:
        detail = fn()
        results.append((name, True, detail or ""))
        print(f"  [PASS] {name}  {detail or ''}")
    except Exception as e:
        results.append((name, False, str(e)))
        print(f"  [FAIL] {name}  {e}")
        traceback.print_exc()


def _new_card(root: Path, cid: str, title: str):
    """在指定项目里建一张卡（不碰全局 root）。"""
    prev_root, prev_ws = B.ROOT, B.WORKSPACE
    try:
        B.set_root(root)
        B.set_workspace(root)
        B.create_card({
            "id": cid, "title": title, "goal": "压测", "territory": [],
            "deliverables": [], "accept_patterns": [], "human_gate": "none",
            "engine": "any", "model": "any", "effort": "any",
            "created_at": B.ts(), "created_by": "probe", "created_kind": "human",
            "irreversible": False, "source_card": None,
        })
    finally:
        B.set_root(prev_root)
        B.set_workspace(prev_ws)


def main():
    print(f"沙箱：{_SANDBOX}")
    print(f"注册表：{P.REGISTRY_DB}")
    assert str(P.REGISTRY_DB).startswith(str(_SANDBOX)), "注册表没被隔离，停止"

    roots = []
    for i in range(N_PROJECTS):
        d = _SANDBOX / f"proj{i:02d}"
        d.mkdir(parents=True)
        roots.append(d)

    # ---------- P1 ----------
    def p1():
        for d in roots:
            P.add_project(d, name=f"proj{d.name[-2:]}")
        got = P.list_projects()
        assert len(got) == N_PROJECTS, f"期望 {N_PROJECTS} 个项目，实得 {len(got)}"
        return f"{len(got)} 个项目"
    check("P1 批量注册 12 个项目", p1)

    # ---------- P2 ----------
    def p2():
        for i, d in enumerate(roots):
            for j in range(CARDS_EACH):
                _new_card(d, f"P{i:02d}-{j}", f"项目{i} 的第{j}张卡")
        total = 0
        for d in roots:
            prev = B.ROOT
            try:
                B.set_root(d)
                ids = B.card_ids()
            finally:
                B.set_root(prev)
            assert len(ids) == CARDS_EACH, f"{d.name} 有 {len(ids)} 张卡"
            total += len(ids)
        return f"{total} 张卡"
    check("P2 每项目各建 3 张卡", p2)

    # ---------- P3 ----------
    def p3():
        rows = P.project_summary(use_cache=False)
        assert len(rows) == N_PROJECTS, f"汇总只有 {len(rows)} 个项目"
        bad = [r for r in rows if r.get("cards", 0) != CARDS_EACH]
        assert not bad, f"{len(bad)} 个项目卡数不对：{[r['name'] for r in bad][:3]}"
        return f"汇总 {len(rows)} 项，每项 {CARDS_EACH} 卡"
    check("P3 跨项目汇总数量正确", p3)

    # ---------- P4 ----------
    def p4():
        deep = roots[3] / "a" / "b" / "c"
        deep.mkdir(parents=True)
        cwd = os.getcwd()
        try:
            os.chdir(deep)
            found = P.resolve_root()
        finally:
            os.chdir(cwd)
        assert found.resolve() == roots[3].resolve(), f"找到的是 {found}"
        return f"从 a/b/c 找到 {found.name}"
    check("P4 子目录向上找到项目根", p4)

    # ---------- P5 ----------
    def p5():
        clash = _SANDBOX / "clash"
        clash.mkdir()
        got = P.add_project(clash, name="proj00")      # 与已有名字冲突
        assert got["name"] != "proj00", f"重名没处理，直接用了 {got['name']}"
        # 原来那个项目必须还指向自己，没被顶掉
        orig = P.find_project("proj00")
        assert orig and orig["path"].endswith("proj00"), f"原项目被顶掉了：{orig}"
        # 返回的名字必须真的在注册表里查得到
        assert P.find_project(got["name"]), f"返回 {got['name']} 但查不到"
        return f"重名自动改叫 {got['name']}，原项目不受影响"
    check("P5 项目重名要改名且不顶掉原项目", p5)

    # ---------- P6 ----------
    def p6():
        conc = [_SANDBOX / f"conc{i}" for i in range(8)]
        for d in conc:
            d.mkdir()
        errs = []

        def worker(d):
            try:
                P.add_project(d, name=f"conc_{d.name}")
            except Exception as e:
                errs.append(f"{d.name}: {e}")

        ts = [threading.Thread(target=worker, args=(d,)) for d in conc]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        got = {p["path"] for p in P.list_projects()}
        missing = [d for d in conc if str(d.resolve()) not in got]
        assert not errs, f"并发报错 {errs[:2]}"
        assert not missing, f"丢了 {len(missing)} 条"
        return f"8 线程并发，一条不丢"
    check("P6 注册表并发写不丢条目", p6)

    # ---------- P7 ----------
    def p7():
        victim = roots[0]
        P.remove_project(str(victim))
        assert not P.find_project(str(victim)), "注册表里还在"
        assert (victim / "board" / "board.db").exists(), "项目数据被误删"
        return "只掉注册，数据留着"
    check("P7 删项目不影响数据", p7)

    # ---------- P8 ----------
    def p8():
        assert P.find_project("不存在的项目xyz") is None, "竟然查到了"
        assert P.find_project(str(_SANDBOX / "nope")) is None, "路径竟然查到了"
        return "两个不存在的都查不到"
    check("P8 反空跑：查不存在的必须查不到", p8)

    # ---------- P9 ----------
    def p9():
        prev_root, prev_ws = B.ROOT, B.WORKSPACE
        marker = _SANDBOX / "my-workspace"
        marker.mkdir(exist_ok=True)
        try:
            B.set_root(roots[1])
            B.set_workspace(marker)
            P.project_summary(use_cache=False)      # 遍历全部项目
            ws = B.WORKSPACE
        finally:
            B.set_root(prev_root)
            B.set_workspace(prev_ws)
        assert Path(ws).resolve() == marker.resolve(), \
            f"汇总后工作区被改成了 {ws}（应为 {marker}）"
        return "遍历完全部项目，工作区没被带跑"
    check("P9 跨项目汇总不能改掉调用方工作区", p9)

    # ---------- 汇总 ----------
    ok = sum(1 for _, p, _ in results if p)
    print(f"\n{'=' * 60}")
    print(f"多项目压测：{ok} of {len(results)} 通过")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        shutil.rmtree(_SANDBOX, ignore_errors=True)
    sys.exit(rc)
