#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator.py — 自主编排器

一件事：让看板上的卡**自己跑完**，不用人盯。

闭环（全自动）：
  找活 → 认领(原子) → 心跳 → 调引擎执行 → 提交(自动过 L1-L3)
    → 异会话复核 → PASS 则完成 / FAIL 则返工(自动重派)
    → 需要人拍板的转「拍板中」停下等人

纪律（对齐 AGENTS.md §1／§4 与 D2）：
  · 退出码权重 0 —— 只用 engines.Result.ok（读结构化回执）
  · 完成必须异会话复核 —— 执行者 session 与复核者 session 不同
  · 复核必须带凭据 —— 复核时把实测读数写进 evidence
  · 返工有上限 —— 超过 max_attempts 转「阻塞」，⛔ 不死循环
  · 引擎类动作不并行 —— 一期串行跑（本机引擎会抢资源）

用法：
  python tools/orchestrator.py run --engine opencode --seat w1 --max 5
  python tools/orchestrator.py run --engine opencode --seat w1 --dry-run
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B
import engines as E

ROOT = B.ROOT


def ts():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


def log(msg, kind="info"):
    mark = {"info": "·", "ok": "✓", "warn": "!", "err": "✗", "step": "→"}.get(kind, "·")
    print(f"{mark} {msg}")


def build_prompt(card: dict, cid: str) -> str:
    """把卡变成给 agent 的提示词。强调纪律，但不说废话。"""
    lines = [
        f"# 任务：{card.get('title','')}",
        "",
    ]
    if card.get("goal"):
        lines += [f"**目标**：{card['goal']}", ""]
    if card.get("territory"):
        lines += ["**可写领地**（只能改这些，其余一律只读）："]
        for t in card["territory"]:
            lines.append(f"- {t}")
        lines.append("")
    if card.get("deliverables"):
        lines += ["**必须产出**（路径要精确，缺一个就算没做完）："]
        for d in card["deliverables"]:
            lines.append(f"- `{d}`")
        lines.append("")
    if card.get("accept_patterns"):
        lines += ["**交付物里必须出现**（验收会逐条查，缺一个就不通过）："]
        for p in card["accept_patterns"]:
            lines.append(f"- `{p}`")
        lines.append("")
    lines += [
        "## 硬要求",
        "1. 只写上面列出的交付物路径，⛔ 不改其它文件。",
        "2. 交付物里**必须包含数字**（字节数、条数、行数都行）——反空跑闸会查。",
        "3. 中文强调用「」不用 ASCII 双引号。",
        "4. 做完只回一句话：改了什么 + 关键数字。不要贴全文。",
        "",
        f"卡片 ID：{cid}",
    ]
    return "\n".join(lines)


def review_prompt(card: dict, cid: str, submit: dict) -> str:
    """复核提示词：让另一个会话真的去查，而不是复述执行者的话。"""
    dl = card.get("deliverables", [])
    pats = card.get("accept_patterns", [])
    return "\n".join([
        f"# 复核任务：{card.get('title','')}",
        "",
        "你是**独立复核席**。执行者声称做完了，你要**亲自核实**，不是复述它的话。",
        "",
        "## 你要做的",
        "1. 逐个确认交付物**存在**且**字节>0**：",
        *[f"   - `{d}`" for d in dl],
        "2. 逐个确认这些内容**真的出现**在交付物里：",
        *[f"   - `{p}`" for p in pats],
        "3. **另找反例**：有没有明显缺项、占位符、空章节？",
        "",
        "## 回什么",
        "只回一行，格式严格如下：",
        "`VERDICT=pass` 或 `VERDICT=fail`",
        "下一行写 `EVIDENCE=<你实际看到的读数，必须有数字>`",
        "若 fail，再下一行写 `REASON=<缺什么>`",
        "",
        f"卡片 ID：{cid}",
    ])


def parse_review(text: str) -> tuple:
    """解析复核回执。返回 (verdict, evidence, reason)。"""
    verdict, evidence, reason = None, "", ""
    for line in text.splitlines():
        s = line.strip().strip("`")
        if s.upper().startswith("VERDICT="):
            v = s.split("=", 1)[1].strip().lower()
            verdict = "pass" if v.startswith("pass") else "fail" if v.startswith("fail") else None
        elif s.upper().startswith("EVIDENCE="):
            evidence = s.split("=", 1)[1].strip()
        elif s.upper().startswith("REASON="):
            reason = s.split("=", 1)[1].strip()
    return verdict, evidence, reason


def run_one(cid: str, engine: str, seat: str, model: str, effort: str,
            dry: bool = False, panel: list = None, use_worktree: bool = False) -> str:
    """跑完一张卡的全流程。返回最终状态。"""
    card = B.jread(B.card_dir(cid) / "card.json")

    # ---- 认领 ----
    if not dry:
        try:
            B.claim(cid, seat, engine, model, effort)
        except SystemExit:
            return "claim-failed"
        log(f"认领 {cid} → {seat}", "ok")
    else:
        log(f"[dry] 会认领 {cid}", "step")

    # ---- 执行 ----
    prompt = build_prompt(card, cid)
    if dry:
        log(f"[dry] 会给 {engine} 发 {len(prompt)} 字符的提示", "step")
        return "dry"

    # 并行模式：在独立 worktree 里跑，避免踩别人的文件
    work_dir = str(ROOT)
    if use_worktree:
        import parallel as PL
        try:
            wt = PL.create(cid)
            work_dir = str(wt)
            log(f"用独立 worktree：{wt.name}", "step")
        except Exception as e:
            log(f"worktree 建不起来，退回主树：{e}", "warn")

    log(f"调 {engine}（模型 {model or '默认'}）…", "step")
    t0 = time.time()
    res = E.run(engine, prompt, cwd=work_dir, model=model, effort=effort)
    dur = time.time() - t0
    log(f"{engine} 返回 ok={res.ok} 用时 {dur:.0f}s", "ok" if res.ok else "err")

    # 收工：把 worktree 里的交付物拷回主树
    if use_worktree:
        import parallel as PL
        copied, conflicts = PL.collect(cid, card.get("deliverables", []))
        if copied:
            log(f"拷回 {len(copied)} 个交付物", "ok")
        if conflicts:
            B.append_event(cid, {"type": "block", "actor": "system", "seat": "system",
                                 "reason": "并行冲突：" + "；".join(conflicts)[:200]})
            PL.remove(cid)
            B.release(cid)
            log(f"交付物冲突，判阻塞：{conflicts[0][:80]}", "err")
            return "conflict"
        PL.remove(cid)

    # 存档原始回执（证据）
    ev_dir = B.card_dir(cid) / "evidence"
    ev_dir.mkdir(exist_ok=True)
    (ev_dir / f"run__{seat}__{uuid.uuid4().hex[:6]}.json").write_text(
        json.dumps(res.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    if not res.ok:
        B.append_event(cid, {"type": "block", "actor": "system", "seat": "system",
                             "reason": f"引擎失败：{res.reason}"[:300]})
        B.release(cid)
        log(f"引擎未正常结束：{res.reason[:120]}", "err")
        return "engine-failed"

    # ---- 提交（自动过 L1-L3）----
    ns = argparse.Namespace(id=cid, seat=seat, note=f"{engine}/{model or 'default'}")
    B.cmd_submit(ns)
    st = B.replay(cid)
    if st["state"] != "待验收":
        B.release(cid)
        log(f"闸门未过 → {st['state']}", "err")
        return "gate-failed"

    # ---- 复核（必须异会话）----
    # 单席模式：换 seat + 独立会话跑一次
    # 专家团模式：多个视角各看一遍，取最严（任一 FAIL 即 FAIL）
    rseat = f"rev-{uuid.uuid4().hex[:4]}"
    rprompt = review_prompt(card, cid, st["submit"] or {})

    if panel:
        import experts
        log(f"派专家团复核（{'/'.join(panel)}）…", "step")
        votes = []
        for ex in panel:
            res_i = E.run(engine, experts.build_prompt(ex, rprompt),
                          cwd=str(ROOT), model=model, effort=effort)
            (ev_dir / f"panel__{ex}__{uuid.uuid4().hex[:6]}.json").write_text(
                json.dumps(res_i.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8")
            v, evd, rsn = parse_review(res_i.text) if res_i.ok else ("fail", "", res_i.reason)
            votes.append({"expert": ex, "ok": res_i.ok, "verdict": v,
                          "evidence": evd, "reason": rsn})
            log(f"  {ex}: {v or '不可解析'}", "ok" if v == "pass" else "warn")
        # 取最严：任一 fail 即 fail；全部 pass 才 pass
        verdict = "pass" if all(v["verdict"] == "pass" for v in votes) and votes else "fail"
        evidence = " | ".join(f"{v['expert']}:{v['evidence'][:80]}" for v in votes)
        reason = "；".join(f"{v['expert']}:{v['reason']}" for v in votes if v["reason"])
        B.append_event(cid, {"type": "panel_review", "actor": "review",
                             "seat": rseat, "votes": votes})
        rres_ok = True
    else:
        log(f"派复核席 {rseat} 独立核验…", "step")
        rres = E.run(engine, rprompt, cwd=str(ROOT), model=model, effort=effort)
        (ev_dir / f"review__{rseat}__{uuid.uuid4().hex[:6]}.json").write_text(
            json.dumps(rres.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        if not rres.ok:
            B.append_event(cid, {"type": "block", "actor": "system", "seat": "system",
                                 "reason": f"复核引擎失败：{rres.reason}"[:300]})
            B.release(cid)
            log(f"复核引擎失败：{rres.reason[:120]}", "err")
            return "review-engine-failed"
        verdict, evidence, reason = parse_review(rres.text)
    if not verdict:
        # 复核没给结构化结论 → 保守判 fail
        verdict, evidence = "fail", f"复核未给出可解析结论；原文={rres.text[:120]}"
        reason = "复核回执不可解析"

    # 复核凭据兜底：没数字就补上机器读数（反空跑）
    if not re.search(r"\d", evidence or ""):
        ok1, p1, r1 = B.gate_l1(cid, card)
        nums = "; ".join(f"{x['path']}={x.get('bytes','?')}B" for x in r1)
        evidence = (evidence + " | 机器读数：" + nums).strip(" |")

    # ---- 记复核结论（⚠️ 必须真跑闸门，⛔ 不许写死 True）----
    g1, p1, r1 = B.gate_l1(cid, card)
    g2, p2 = B.gate_l2(cid, card)
    g3, p3, _ = B.gate_l3(cid, card)
    B.append_event(cid, {"type": "verify", "actor": "review", "seat": rseat,
                         "L1": g1, "L2": g2, "L3": g3,
                         "problems": p1 + p2 + p3})
    if not (g1 and g2 and g3):
        B.append_event(cid, {"type": "review", "actor": "review", "seat": rseat,
                             "verdict": "fail", "evidence": evidence,
                             "note": "机器闸未过：" + "；".join((p1 + p2 + p3)[:3]),
                             "evidence_ok": True})
        B.release(cid)
        log(f"{cid} 机器闸未过 → 待返工", "err")
        return "gate-failed"
    B.append_event(cid, {"type": "review", "actor": "review", "seat": rseat,
                         "verdict": verdict, "note": reason,
                         "evidence": evidence, "evidence_ok": True})
    st = B.replay(cid)

    if st["gate"] in ("both", "before_done") and verdict == "pass":
        B.append_event(cid, {"type": "request_human", "actor": "review", "seat": rseat})
        B.release(cid)
        log(f"{cid} 复核通过 → 拍板中（等人）", "warn")
        return "awaiting-human"

    if verdict == "pass":
        B.release(cid)
        log(f"{cid} 完成", "ok")
        return "done"

    # ---- 返工 ----
    B.release(cid)
    attempts = count_attempts(cid)
    if attempts >= 3:
        B.append_event(cid, {"type": "block", "actor": "system", "seat": "system",
                             "reason": f"返工 {attempts} 次仍不过，转阻塞等人"})
        log(f"{cid} 返工 {attempts} 次 → 阻塞", "err")
        return "blocked-after-retries"
    log(f"{cid} 复核 FAIL（{reason[:60]}）→ 待返工（第 {attempts+1} 次）", "warn")
    return "rework"


def count_attempts(cid: str) -> int:
    n = 0
    for ev in B.load_journal(cid):
        if ev.get("type") == "review" and ev.get("verdict") != "pass":
            n += 1
    return n


def cmd_run(a):
    log(f"编排器启动：引擎={a.engine} 席={a.seat} 上限={a.max} 次"
        + (f" 并行={a.parallel}" if a.parallel > 1 else ""), "step")
    if a.engine == "opencode" and not a.model:
        a.model = E.DEFAULT_MODELS.get("opencode")
        log(f"opencode 未指定模型 → 用默认 {a.model}", "warn")

    results = []

    def pick(limit):
        """挑最多 limit 张能接的卡（精确匹配优先）。"""
        cand = []
        for d in sorted(B.CARDS.iterdir()) if B.CARDS.exists() else []:
            if not d.is_dir():
                continue
            try:
                st = B.replay(d.name)
                card = B.jread(d / "card.json")
            except Exception:
                continue
            if st["state"] not in ("待认领", "阻塞", "待返工"):
                continue
            if B._match_miss(card, a.engine, a.model, a.effort):
                continue
            score = 0
            if card.get("engine", "any") == a.engine:
                score += 2
            if a.model and card.get("model", "any") == a.model:
                score += 1
            if a.effort and card.get("effort", "any") == a.effort:
                score += 1
            cand.append((score, d.name))
        cand.sort(reverse=True)
        return [c for _, c in cand[:limit]]

    if a.parallel > 1:
        # ---- 并行模式：每卡一个 worktree，同时跑 ----
        from concurrent.futures import ThreadPoolExecutor, as_completed
        targets = pick(a.max)
        if not targets:
            log("没有可接的卡，收工", "ok")
            return 0
        log(f"并行跑 {len(targets)} 张：{', '.join(targets)}", "step")
        with ThreadPoolExecutor(max_workers=min(a.parallel, len(targets))) as ex:
            futs = {ex.submit(run_one, t, a.engine, a.seat, a.model, a.effort,
                              a.dry_run, a.panel, True): t for t in targets}
            for f in as_completed(futs):
                t = futs[f]
                try:
                    results.append((t, f.result()))
                except Exception as e:
                    results.append((t, f"error: {e}"))
    else:
        rounds = 0
        while rounds < a.max:
            rounds += 1
            t = pick(1)
            if not t:
                log("没有可接的卡，收工", "ok")
                break
            target = t[0]
            log(f"[{rounds}/{a.max}] 处理 {target}", "step")
            results.append((target, run_one(target, a.engine, a.seat, a.model,
                                            a.effort, a.dry_run, panel=a.panel,
                                            use_worktree=False)))
            if a.dry_run:
                break

    print()
    log("=== 本轮汇总 ===", "step")
    for cid, oc in results:
        print(f"  {cid:<14} {oc}")
    if not results:
        print("  （没有处理任何卡）")

    # 收工：必须报度量（AGENTS.md §7 第 4 条）
    try:
        _append_ledger(a, results)
    except Exception as e:
        log(f"度量台账写入失败：{e}", "warn")

    try:
        B.cmd_html(argparse.Namespace())
        log("看板已刷新", "ok")
    except Exception as e:
        log(f"看板刷新失败：{e}", "warn")

    return 0


def _append_ledger(a, results):
    """把本轮派工追加到 DELEGATION-LEDGER.md（治理收工动作）。"""
    path = ROOT / "docs" / "governance" / "DELEGATION-LEDGER.md"
    if not path.exists():
        return
    ok_n = sum(1 for _, o in results if o == "done")
    line = (f"| {datetime.now().strftime('%Y-%m-%d')} | 自动编排 | "
            f"内派（{a.engine}/{a.model or 'default'}） | "
            f"{'成' if ok_n else '部分'} {ok_n}/{len(results)} | "
            f"{len(results)} | 0 | 否 | "
            f"{'；'.join(f'{c}={o}' for c, o in results)[:120]} |")
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    log("度量台账已追加", "ok")


def cmd_status(a):
    """一眼看编排状态。"""
    if not B.CARDS.exists():
        print("（看板为空）")
        return
    by = {}
    for d in sorted(B.CARDS.iterdir()):
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
        except Exception:
            continue
        by.setdefault(st["state"], []).append(st["id"])
    for s in B.STATES:
        if s in by:
            print(f"{s:<8} {len(by[s]):>3}  {' '.join(by[s][:8])}")
    total = sum(len(v) for v in by.values())
    print(f"\n共 {total} 张")


def cmd_resume(a):
    """断点续跑：按 journal 状态决定从哪一步接。"""
    import resume as R

    plan = R.scan()
    todo = [p for p in plan if p["action"] != R.SKIP]
    log(f"续跑计划：共 {len(plan)} 张，需动作 {len(todo)} 张", "step")
    for p in plan:
        mark = {"RUN": "→", "REVIEW": "✓", "CONCLUDE": "✓",
                "RECLAIM_RUN": "↻", "SKIP": "·"}.get(p["action"], "?")
        log(f"  {mark} {p['id']:<10} {p['state']:<8} {p['reason']}", "info")

    if not todo:
        log("没有需要续跑的卡", "ok")
        return

    def execute_fn(card, cid):
        return run_one(cid, a.engine, a.seat, a.model, a.effort, False)

    def review_fn(card, cid):
        return run_one(cid, a.engine, a.seat, a.model, a.effort, False)

    res = R.resume(execute_fn, review_fn, dry=a.dry_run)
    print()
    for cid, act, outcome in res:
        print(f"  {cid:<10} {act:<10} {outcome}")


def main():
    p = argparse.ArgumentParser(prog="orchestrator", description="自主编排器")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="跑一轮（自动认领→执行→复核→返工）")
    s.add_argument("--engine", default="opencode")
    s.add_argument("--seat", default="auto-worker")
    s.add_argument("--model", default=None)
    s.add_argument("--effort", default=None)
    s.add_argument("--max", type=int, default=5, help="最多处理几张卡")
    s.add_argument("--parallel", type=int, default=1,
                   help="并行数（>1 时每卡一个 git worktree）；建议 2-3，引擎会抢资源")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--panel", nargs="*", default=None,
                   help="专家团复核（如 --panel security skeptic simplifier）；不给=单席复核")
    s.set_defaults(f=cmd_run)

    s = sub.add_parser("status", help="看编排状态")
    s.set_defaults(f=cmd_status)

    s = sub.add_parser("resume", help="断点续跑（按 journal 状态接上）")
    s.add_argument("--engine", default="opencode")
    s.add_argument("--model", default=None)
    s.add_argument("--seat", default="resume-w")
    s.add_argument("--effort", default=None)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(f=cmd_resume)

    s = sub.add_parser("probe", help="探测本机引擎可用性")
    s.set_defaults(f=lambda a: [print(f"{k:<12} {'FOUND' if v['found'] else 'MISSING'}")
                                for k, v in E.available().items()])

    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
