#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_debate.py — 专家团「辩论」流程的契约测试（卡片 G2）

验证三件事，每条都配一个必须非零的对照：
  1. 正反方拿到**两个不同的会话**（独立立论，不串台）
  2. 第 2 轮反驳**确实看到了对方原文**（且没把自己的话当对方观点）
  3. 裁决环节拿到全部 4 条发言，裁决文本含可核对数字

引擎调用用本地假件替身，不联网、不烧模型；本测试只管「接线对不对」，
不判断模型观点好不好（那要人工看实跑记录）。

运行：python tests/test_debate.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import engines as E          # noqa: E402
import experts               # noqa: E402

PRO, CON, JUDGE = "architect", "skeptic", "lead"

PRO_OPENING = "正方立论：共享看板应强制异会话复核，共 3 条理由。"
CON_OPENING = "反方立论：强制异会话复核会拖慢交付，共 2 条理由。"
PRO_REBUTTAL = "正方反驳：反方忽略 1 个事实——复核只占 12% 时延。"
CON_REBUTTAL = "反方反驳：正方高估收益，实测返工率只降 4 个百分点。"
VERDICT = "裁决：正方略胜（依据 3 条，置信 0.7）。"


class FakeEngine:
    """记录每次调用，按角色/会话返回可预测的文本。"""

    def __init__(self):
        self.calls = []

    def _result(self, text, session_id):
        r = E.Result("fake")
        r.ok = True
        r.text = text
        r.session_id = session_id
        r.parsed = {"fake": True}
        return r

    def run(self, engine, prompt, **kw):
        sid = kw.get("session_id")
        self.calls.append({"n": len(self.calls) + 1, "prompt": prompt,
                           "session_id": sid})

        if sid == "sess-pro-1":
            return self._result(PRO_REBUTTAL, sid)
        if sid == "sess-con-1":
            return self._result(CON_REBUTTAL, sid)

        pro_name = experts.get(PRO)["name"]
        con_name = experts.get(CON)["name"]
        if f"# 角色：{pro_name}" in prompt:
            return self._result(PRO_OPENING, "sess-pro-1")
        if f"# 角色：{con_name}" in prompt:
            return self._result(CON_OPENING, "sess-con-1")
        return self._result(VERDICT, "sess-judge-1")


def main():
    fake = FakeEngine()
    real_run = experts.E.run
    experts.E.run = fake.run
    try:
        transcript = experts.debate(
            "共享看板是否强制异会话复核",
            PRO, CON, context="看板已实现 L1-L3 闸门", rounds=2,
        )

        turns = "\n".join(
            f"[{i + 1}] {t['name']}：{t['text']}"
            for i, t in enumerate(transcript)
        )
        verdict_prompt = (
            f"下面是两方辩论的 {len(transcript)} 条发言。"
            "请给出裁决：判定胜负、列出依据条数、给 0-1 的置信度。\n"
            + turns
        )
        verdict = experts.ask(JUDGE, verdict_prompt)
    finally:
        experts.E.run = real_run

    pro_sid = transcript[0]["session_id"] if transcript else None
    con_sid = transcript[1]["session_id"] if len(transcript) > 1 else None

    pro_atk = fake.calls[2]["prompt"] if len(fake.calls) > 2 else ""
    con_atk = fake.calls[3]["prompt"] if len(fake.calls) > 3 else ""

    seen = sum(1 for t in transcript if t["text"] in verdict_prompt)
    digits = re.findall(r"\d+", verdict.get("text") or "")
    all_sids = {t["session_id"] for t in transcript if t["session_id"]}
    all_sids.add(verdict.get("session_id"))

    print("辩论回放：")
    for i, t in enumerate(transcript, 1):
        print(f"  [{i}] {t['name']:<8} session={t['session_id']} "
              f"ok={t['ok']} chars={len(t['text'])}")
    print(f"  裁决：session={verdict.get('session_id')} "
          f"文本={verdict.get('text')}")

    fails = []
    checks = []

    # 1. 两方独立会话（非空且不同）
    ok1 = bool(pro_sid) and bool(con_sid) and pro_sid != con_sid
    checks.append(("独立会话", ok1, f"{pro_sid} / {con_sid}"))
    if not ok1:
        fails.append("正反方没有拿到两个不同的会话")

    # 2. 第 2 轮看到对方原文，且没看错人
    ok2a = CON_OPENING in pro_atk and PRO_OPENING not in pro_atk
    ok2b = PRO_OPENING in con_atk and CON_OPENING not in con_atk
    checks.append(("正方反驳引用反方", ok2a, f"命中={CON_OPENING in pro_atk}"))
    checks.append(("反方反驳引用正方", ok2b, f"命中={PRO_OPENING in con_atk}"))
    if not ok2a:
        fails.append("正方反驳没拿到反方原文，或错把自己的话当对方观点")
    if not ok2b:
        fails.append("反方反驳没拿到正方原文，或错把自己的话当对方观点")

    # 3. 裁决拿到全部发言，且含数字
    ok3a = seen == len(transcript) == 4
    ok3b = bool(digits) and "裁决" in (verdict.get("text") or "")
    checks.append(("裁决看到全部发言", ok3a, f"{seen} of {len(transcript)}"))
    checks.append(("裁决含数字", ok3b, f"数字={digits}"))
    if not ok3a:
        fails.append("裁决环节没有拿到全部 4 条发言")
    if not ok3b:
        fails.append("裁决文本缺数字或不是裁决")

    # 4. 裁决席独立（3 个会话互不相同）
    ok4 = len(all_sids) == 3
    checks.append(("三个独立会话", ok4, f"unique={len(all_sids)}"))
    if not ok4:
        fails.append("裁决席与辩论席共用了会话")

    # 反空跑：假件必须真被调了 5 次（2 立论 + 2 反驳 + 1 裁决）
    ok5 = len(fake.calls) == 5
    checks.append(("引擎调用数", ok5, f"{len(fake.calls)}（必须 5）"))
    if not ok5:
        fails.append(f"引擎调用数异常：{len(fake.calls)}")

    print("\n判据：")
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<12} {detail}")

    total = len(transcript) + len(fake.calls) + len(all_sids)
    print(f"\n反空跑对照：发言+调用+会话 = {total}（必须 > 0）")
    if total == 0:
        fails.append("计数器可能坏了（总量为 0）")

    print()
    if fails:
        print("FAIL：")
        for f in fails:
            print(f"  · {f}")
        return 1
    print("PASS：辩论三条判据全过（4 条发言 / 5 次调用 / 3 个独立会话）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
