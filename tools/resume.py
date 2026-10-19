#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resume.py — 断点续跑

核心洞察：**journal 是 append-only 的唯一真相，重放即得准确状态。**
所以「续跑」不需要额外的进度文件——扫描每张卡的状态，决定从哪一步接上。

状态 → 动作映射：
  待认领 / 待返工        → RUN      从执行开始
  进行中 + 有活跃租约     → SKIP     别人在干，⛔ 别抢
  进行中 + 租约超时       → RECLAIM_RUN  回收后重跑
  进行中 + 无租约         → RECLAIM_RUN  上次崩了，重跑
  待验收                → REVIEW   已干完，直接复核（⛔ 不重做）
  核验中                → CONCLUDE 复核中途崩了，补结论
  拍板中 / 完成 / 已取消  → SKIP

设计要点：
  · execute_fn / review_fn 由调用方注入 ⇒ 生产用真引擎，测试用桩
  · ⛔ 绝不重做「待验收」及之后的卡——那是最容易丢进度的地方
  · 每次动作写 journal，续跑本身也可被续跑

用法：
  python tools/resume.py plan            # 只看要做什么
  python tools/resume.py run             # 真跑
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B

# 动作常量
RUN = "RUN"
REVIEW = "REVIEW"
CONCLUDE = "CONCLUDE"
RECLAIM_RUN = "RECLAIM_RUN"
SKIP = "SKIP"


def _lease_age_s(cid: str):
    """活跃租约多久没心跳了。无租约返回 None。"""
    lease = B.active_lease(cid)
    if not lease:
        return None
    owner = B._lease_owner(lease)
    hb = owner.get("at_ms", 0)
    if not hb:
        return 0          # 刚创建、还没写 owner
    return (B.now_ms() - hb) / 1000


def decide(st: dict, cid: str) -> tuple:
    """根据重放状态决定动作。返回 (action, reason)。"""
    state = st["state"]

    if state in ("待认领", "待返工"):
        return RUN, f"状态「{state}」，从执行开始"

    if state == "进行中":
        age = _lease_age_s(cid)
        if age is None:
            return RECLAIM_RUN, "进行中但无活跃租约（上次崩了）→ 重跑"
        if age > B.LEASE_TTL:
            return RECLAIM_RUN, f"租约 {int(age)}s 无心跳（>{B.LEASE_TTL}s）→ 回收重跑"
        return SKIP, f"别人正在干（{st['holder']}，{int(age)}s 前心跳）"

    if state == "待验收":
        return REVIEW, "已交付，直接复核（⛔ 不重做）"

    if state == "核验中":
        return CONCLUDE, "复核中途崩了，补结论"

    if state in ("拍板中", "完成", "已取消"):
        return SKIP, f"终态/等人「{state}」，无需续跑"

    if state == "阻塞":
        return SKIP, "阻塞中，等人处理"

    return SKIP, f"未知状态「{state}」"


def scan() -> list:
    """扫描全部卡，给出续跑计划。"""
    out = []
    if not B.CARDS.exists():
        return out
    for d in sorted(B.CARDS.iterdir()):
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
            card = B.jread(d / "card.json")
        except Exception as e:
            out.append({"id": d.name, "title": "?", "state": "?",
                        "action": SKIP, "reason": f"卡片损坏：{e}"})
            continue
        action, reason = decide(st, d.name)
        out.append({
            "id": d.name, "title": st["title"], "state": st["state"],
            "action": action, "reason": reason, "card": card, "st": st,
        })
    return out


def plan_lines(plan: list) -> list:
    lines = []
    for p in plan:
        lines.append(f"{p['id']:<10} {p['state']:<8} {p['action']:<12} {p['reason']}")
    return lines


def resume(execute_fn, review_fn, conclude_fn=None, dry: bool = False,
           only: list = None) -> list:
    """按计划续跑。

    execute_fn(card, cid) -> str   （返回 "ok"/"fail"/...）
    review_fn(card, cid)  -> str
    conclude_fn(card, cid)-> str
    """
    results = []
    for p in scan():
        if only and p["id"] not in only:
            continue
        act, cid = p["action"], p["id"]
        if act == SKIP:
            results.append((cid, "skip", p["reason"]))
            continue
        if dry:
            results.append((cid, "dry", f"{act}: {p['reason']}"))
            continue

        if act == RECLAIM_RUN:
            lease = B.active_lease(cid)
            if lease:
                B._reclaim_lease(cid, lease, reason=p["reason"])
            B.release(cid)
            act = RUN

        if act == RUN:
            results.append((cid, "run", execute_fn(p["card"], cid)))
        elif act == REVIEW:
            results.append((cid, "review", review_fn(p["card"], cid)))
        elif act == CONCLUDE:
            fn = conclude_fn or review_fn
            results.append((cid, "conclude", fn(p["card"], cid)))
    return results


def cmd_plan(a):
    plan = scan()
    if not plan:
        print("（看板为空）")
        return
    print(f"{'ID':<10} {'状态':<8} {'动作':<12} 原因")
    print("-" * 78)
    for line in plan_lines(plan):
        print(line)
    todo = [p for p in plan if p["action"] != SKIP]
    print(f"\n共 {len(plan)} 张，需要动作 {len(todo)} 张，可跳过 {len(plan)-len(todo)} 张")


def cmd_run(a):
    import orchestrator as O

    def execute_fn(card, cid):
        return O.run_one(cid, a.engine, a.seat, a.model, a.effort, False)

    def review_fn(card, cid):
        return O.run_one(cid, a.engine, a.seat, a.model, a.effort, False)

    res = resume(execute_fn, review_fn, dry=a.dry_run)
    print()
    for cid, act, outcome in res:
        print(f"  {cid:<10} {act:<8} {outcome}")
    if not res:
        print("  （无可续跑项）")


def main():
    p = argparse.ArgumentParser(prog="resume", description="断点续跑")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("plan", help="只看续跑计划")
    s.set_defaults(f=cmd_plan)

    s = sub.add_parser("run", help="执行续跑")
    s.add_argument("--engine", default="opencode")
    s.add_argument("--model", default=None)
    s.add_argument("--seat", default="resume-w")
    s.add_argument("--effort", default=None)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(f=cmd_run)

    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
