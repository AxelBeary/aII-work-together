#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_consult.py — 点对点评审的确定性闸门（不调模型）

C1 评审席解析：模型名带 `/` 不能被切坏
C2 dry-run：要落 consult_request 事件，但不产生任何回复事件
C3 防改文件：评审席动了文件 ⇒ 必须按原字节恢复并报违规（这是核心安全约束）
C4 意见合成：packet 要能把「几席、什么结论、几条意见」说清楚
C5 反空跑：给一个不存在的文件，必须明确报错而不是静默评出一个"pass"

跑法：python tests/test_consult.py
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent / "tools"
sys.path.insert(0, str(TOOLS))

_SB = Path(tempfile.mkdtemp(prefix="aboard-consult-"))
os.environ["ABOARD_REGISTRY_DIR"] = str(_SB / "reg")

import board as B          # noqa: E402
import consult as C        # noqa: E402

results = []


def check(name, fn):
    try:
        detail = fn()
        results.append((name, True))
        print(f"  [PASS] {name}  {detail or ''}")
    except Exception as e:
        results.append((name, False))
        print(f"  [FAIL] {name}  {e}")


def main():
    proj = _SB / "proj"
    proj.mkdir(parents=True)
    B.set_root(proj)
    B.set_workspace(proj)

    art = proj / "ch01.md"
    art.write_text("她推开门，雨声一下子涌了进来。\n", encoding="utf-8")

    B.create_card({
        "id": "T1", "title": "第一章中译英", "goal": "本地化优先",
        "territory": ["ch01.md"], "deliverables": ["ch01.md"],
        "accept_patterns": ["雨声"], "human_gate": "none",
        "engine": "any", "model": "any", "effort": "any",
        "created_at": B.ts(), "created_by": "test", "created_kind": "human",
        "irreversible": False, "source_card": None,
    })
    B.append_event("T1", {"type": "created", "actor": "human", "seat": "test"})

    # ---------- C1 ----------
    def c1():
        rs = C.parse_reviewers(
            "b1:opencode:claudecodesale/claude-opus-5-5,b2:qoderclicn:,b3")
        assert len(rs) == 3, len(rs)
        assert rs[0]["model"] == "claudecodesale/claude-opus-5-5", rs[0]
        assert rs[1]["engine"] == "qoderclicn" and rs[1]["model"] is None, rs[1]
        assert rs[2]["engine"] == "opencode", rs[2]
        return "3 席解析正确，provider/model 没被切坏"
    check("C1 评审席解析", c1)

    # ---------- C2 ----------
    def c2():
        before = len(B.load_journal("T1"))
        res = C.consult("T1", "请评审", C.parse_reviewers("b1:opencode:"),
                        dry_run=True)
        after = B.load_journal("T1")
        assert res["dry_run"] is True
        assert len(after) == before + 1, f"事件数 {before}->{len(after)}"
        assert after[-1]["type"] == "consult_request", after[-1]["type"]
        assert not [e for e in after if e["type"] == "consult_reply"]
        assert "只输出意见" in res["prompt"], "提示词里没写禁令"
        return "只落 request，无 reply"
    check("C2 dry-run", c2)

    # ---------- C3 ----------
    def c3():
        snap = C.snapshot(["ch01.md"])
        original = art.read_bytes()
        art.write_text("评审席手贱改的内容\n", encoding="utf-8")
        bad = C.check_and_restore(snap)
        assert bad, "改了文件却没报违规"
        assert art.read_bytes() == original, "原字节没恢复"
        # 再验一次：没改就不能误报
        assert C.check_and_restore(snap) == [], "没改却报违规"
        return "改动被抓 + 原字节恢复 + 不改时不误报"
    check("C3 防改文件", c3)

    # ---------- C4 ----------
    def c4():
        fake = [
            {"seat": "b1", "engine": "opencode", "model_used": "m1", "ok": True,
             "verdict": "needs-work", "seconds": 3.2,
             "problems": ["第2句｜太直译｜改成 …"]},
            {"seat": "b2", "engine": "qoderclicn", "model_used": "m2", "ok": True,
             "verdict": "pass", "seconds": 1.1, "problems": []},
        ]
        p = C.render_packet(fake, ["ch01.md"], [])
        assert "b1" in p and "b2" in p
        assert "needs-work" in p and "太直译" in p
        assert "逐条判断" in p
        return "两席结论与意见都在"
    check("C4 意见合成", c4)

    # ---------- C5 ----------
    def c5():
        try:
            C.consult("T1", "评审", C.parse_reviewers("b1:opencode:"),
                      files=["不存在的文件.md"], dry_run=True)
        except ValueError as e:
            assert "没有可评审的文件" in str(e) or "不存在" in str(e), str(e)
            return f"被拒：{str(e)[:30]}"
        raise AssertionError("给不存在的文件竟然通过了")
    check("C5 空材料必须报错", c5)

    ok = sum(1 for _, p in results if p)
    print(f"\n{'=' * 60}")
    print(f"点对点评审：{ok} of {len(results)} 通过")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        shutil.rmtree(_SB, ignore_errors=True)
    sys.exit(rc)
