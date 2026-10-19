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
import threading
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


def _rework_context(cid: str) -> str:
    """把上一次被打回的原因抽出来，附给下一轮执行者。

    ⚠️ 2026-10-20：此前人写的驳回意见/复核理由**到不了** execagent，
    返工等于重来一遍。现在显式带回。
    """
    reasons = []
    for ev in B.load_journal(cid):
        t = ev.get("type")
        if t == "review" and ev.get("verdict") != "pass":
            why = (ev.get("note") or "").strip() or (ev.get("evidence") or "").strip()
            if why:
                reasons.append(f"- 复核席打回（{ev.get('seat')}）：{why[:300]}")
        elif t == "human" and ev.get("decision") != "approve":
            why = (ev.get("note") or "").strip()
            reasons.append(f"- **人驳回**（{ev.get('who')}）：{why[:300] or '（未写理由）'}")
        elif t == "block":
            why = (ev.get("reason") or "").strip()
            if why and ev.get("seat") != "system":
                reasons.append(f"- 阻塞原因：{why[:200]}")
    if not reasons:
        return ""
    return ("\n## ⚠️ 上一轮为什么没过（必须针对性修掉，别重做一遍）\n"
            + "\n".join(reasons[-4:]) + "\n")


def build_prompt(card: dict, cid: str) -> str:
    """把卡变成给 agent 的提示词。强调纪律，但不说废话。"""
    lines = [
        f"# 任务：{card.get('title','')}",
        "",
    ]
    if card.get("goal"):
        lines += [f"**目标**：{card['goal']}", ""]
    rework = _rework_context(cid)
    if rework:
        lines += [rework, ""]
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
        "2. 交付物必须有实质内容（机器会量字节/行数），⛔ 不要用占位符或空壳凑数。",
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
        "## 只在这一个目录里找",
        "当前工作目录就是这张卡的工作区，交付物路径**相对它解析**。",
        "⛔ **不要整盘搜索**（`dir /s`、`Get-ChildItem -Recurse E:\\` 这类）：",
        "   实测会吃满一个核、每秒几万次目录查询，拖慢整台机器。",
        "⛔ 找不到就**直接判 fail 并说明找不到**，不要扩大搜索范围。",
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
            dry: bool = False, panel: list = None, use_worktree: bool = False,
            consult_spec: str = None) -> str:
    """跑完一张卡的全流程。返回最终状态。"""
    card = B.get_card(cid)

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
    # 工作区：项目注册表里设的 workspace（默认＝项目根）
    work_dir = str(B.WORKSPACE)
    if use_worktree:
        import parallel as PL
        try:
            wt = PL.create(cid, card.get("deliverables", []))
            work_dir = str(wt)
            log(f"用独立 worktree：{wt.name}（源自 {B.WORKSPACE.name}）", "step")
        except Exception as e:
            log(f"worktree 建不起来，退回工作区：{e}", "warn")

    log(f"调 {engine}（模型 {model or '默认'}）…", "step")
    # ⚠️ 引擎最长可跑 1800s，而租约 600s 超时 ⇒ 必须后台持续心跳，否则卡被抢走
    hb_stop = threading.Event()

    def _hb_loop():
        while not hb_stop.wait(B.HB_INTERVAL):
            try:
                B.heartbeat(cid, seat)
            except SystemExit:
                return          # 租约已丢，停止（提交时会被 guard_holder 拦下）
            except Exception:
                pass

    hb_thread = threading.Thread(target=_hb_loop, daemon=True)
    hb_thread.start()
    t0 = time.time()
    try:
        res = E.run(engine, prompt, cwd=work_dir, model=model, effort=effort)
    finally:
        hb_stop.set()
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

    # 记用量（token + 缓存 + 花费）。引擎没报就标 available=False，⛔ 不记成 0
    B.append_event(cid, {"type": "usage", "seat": seat, "engine": engine,
                         "model": res.model_used or model,
                         "usage": res.usage, "duration_ms": int(dur * 1000)})
    if res.usage.get("available"):
        u = res.usage
        log(f"用量：入 {u['input']:,} 出 {u['output']:,} "
            f"缓存 {u['cache_read'] + u['cache_write']:,} ${u['cost']:.4f}", "info")
    else:
        log("用量：引擎未报告（标未知）", "warn")

    if not res.ok:
        B.append_event(cid, {"type": "block", "actor": "system", "seat": "system",
                             "reason": f"引擎失败：{res.reason}"[:300]})
        B.release(cid)
        log(f"引擎未正常结束：{res.reason[:120]}", "err")
        return "engine-failed"

    # ---- 点对点评审（可选）：B 初稿 → B1/B2 独立提意见 → B 自己改一轮 ----
    # 评审席只准看：consult.py 会在评审前后逐字节比对交付物，被改了就按原字节恢复并记违规
    if consult_spec:
        hb2_stop = threading.Event()

        def _hb2():
            while not hb2_stop.wait(B.HB_INTERVAL):
                try:
                    B.heartbeat(cid, seat)
                except SystemExit:
                    return
                except Exception:
                    pass

        threading.Thread(target=_hb2, daemon=True).start()
        try:
            import consult as CN
            reviewers = CN.parse_reviewers(consult_spec)
            files = [str(Path(work_dir) / d) for d in card.get("deliverables", [])]
            log(f"派 {len(reviewers)} 席评审："
                f"{' / '.join(r['seat'] + '@' + (r['model'] or r['engine']) for r in reviewers)}",
                "step")
            cres = CN.consult(cid, card.get("goal") or "请评审这份产出", reviewers,
                              files=files, cwd=work_dir)
            print(cres["packet"])
            if cres["violations"]:
                log("评审席动了文件（已恢复原字节）：" + "；".join(cres["violations"])[:160], "err")
            needs = [r for r in cres["replies"]
                     if r.get("ok") and r.get("verdict") != "pass"]
            if needs:
                log(f"{len(needs)} 席认为要改 → {seat} 按意见再改一轮", "step")
                fix_prompt = (
                    f"你上一轮的产出收到 {len(needs)} 份独立评审意见（见下）。\n"
                    "请只针对你认同的问题修改文件：不要整篇重写，不要解释，改完就停。\n"
                    "不认同的意见不用改——但不要因为不认同就把文件改坏。\n\n"
                    + cres["packet"]
                )
                t1 = time.time()
                try:
                    r2 = E.run(engine, fix_prompt, cwd=work_dir, model=model, effort=effort)
                    log(f"修改轮 ok={r2.ok} 用时 {time.time() - t1:.0f}s",
                        "ok" if r2.ok else "err")
                    B.append_event(cid, {"type": "usage", "seat": seat, "engine": engine,
                                         "model": r2.model_used or model,
                                         "usage": r2.usage, "phase": "consult-fix"})
                except Exception as e:
                    log(f"修改轮失败（保留初稿继续走）：{e}", "warn")
        except Exception as e:
            log(f"评审阶段出错（不影响提交）：{e}", "warn")
            B.append_event(cid, {"type": "consult_error", "actor": "system",
                                 "detail": str(e)[:300]})
        finally:
            hb2_stop.set()

    # ---- 提交（自动过 L1-L3）----
    # 先确认租约还在自己手上且没被回收重置（长任务安全）
    try:
        B.guard_holder(cid, seat)
    except SystemExit:
        log("租约已丢（执行期间被回收），放弃提交以免覆盖别人的活", "err")
        return "lease-lost"

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
                          cwd=work_dir, model=model, effort=effort)
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
        # ⚠️ 必须用这张卡的工作区，不是脚本所在项目：
        # 复核席跑错目录会找不到交付物，然后自己去整盘搜（实测把 C: 和 E: 全扫了一遍）
        rres = E.run(engine, rprompt, cwd=work_dir, model=model, effort=effort)
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
        for d in B.card_refs():
            if not d.is_dir():
                continue
            try:
                st = B.replay(d.name)
                card = B.get_card(d.name)
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
                              a.dry_run, a.panel, True, a.consult): t for t in targets}
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
                                            use_worktree=False,
                                            consult_spec=a.consult)))
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


def cmd_run_all(a):
    """跨项目跑一轮：团队几十个项目，一次扫完。"""
    import projects as P
    ps = [p for p in P.list_projects() if p.get("exists")]
    if a.only:
        ps = [p for p in ps if p["name"] in a.only]
    log(f"跨项目编排：{len(ps)} 个项目", "step")

    old_root = B.ROOT
    total = []
    try:
        for p in ps:
            B.set_root(p["path"])
            B.set_workspace(P.workspace_of(p["path"]))
            # 只挑「有活」的项目，别空跑
            todo = [cid for cid in B.card_ids()
                    if B.replay(cid)["state"] in ("待认领", "待返工", "阻塞")]
            if not todo:
                continue
            log(f"[{p['name']}] {len(todo)} 张待跑", "step")
            ns = argparse.Namespace(engine=a.engine, seat=a.seat,
                                    model=a.model, effort=a.effort,
                                    max=a.max, parallel=a.parallel,
                                    dry_run=a.dry_run, panel=a.panel)
            try:
                cmd_run(ns)
                total.append((p["name"], "ok"))
            except SystemExit:
                total.append((p["name"], "skipped"))
    finally:
        B.set_root(old_root)

    print()
    log(f"跨项目完成：{len(total)} 个项目有活", "ok")
    for name, st in total:
        print(f"  {name:<24} {st}")


def cmd_status(a):
    """一眼看编排状态。"""
    if not B.card_ids():
        print("（看板为空）")
        return
    by = {}
    for d in B.card_refs():
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
    p.add_argument("-C", "--root", help="指定项目目录（默认用脚本所在项目）")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="跑一轮（自动认领→执行→复核→返工）")
    s.add_argument("--engine", default="opencode")
    s.add_argument("--seat", default="auto-worker")
    s.add_argument("--model", default=None)
    s.add_argument("--effort", default=None)
    s.add_argument("--max", type=int, default=5, help="最多处理几张卡")
    s.add_argument("--consult", default=None,
                   help='点对点评审席（初稿→评审→再改一轮）：'
                        '"b1:opencode:claudecodesale/claude-opus-5-5,b2:qoderclicn:"')
    s.add_argument("--parallel", type=int, default=1,
                   help="并行数（>1 时每卡一个 git worktree）；建议 2-3，引擎会抢资源")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--panel", nargs="*", default=None,
                   help="专家团复核（如 --panel security skeptic simplifier）；不给=单席复核")
    s.set_defaults(f=cmd_run)

    s = sub.add_parser("status", help="看编排状态")
    s.set_defaults(f=cmd_status)

    s = sub.add_parser("run-all", help="🌐 跨项目跑一轮（团队视角）")
    s.add_argument("--engine", default="opencode")
    s.add_argument("--seat", default="auto-worker")
    s.add_argument("--model", default=None)
    s.add_argument("--effort", default=None)
    s.add_argument("--max", type=int, default=3, help="每个项目最多跑几张")
    s.add_argument("--parallel", type=int, default=1)
    s.add_argument("--panel", nargs="*", default=None)
    s.add_argument("--only", nargs="*", default=None, help="只跑指定项目")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(f=cmd_run_all)

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
    if getattr(a, "root", None):
        import projects as P
        B.set_root(Path(a.root).resolve())
        B.set_workspace(P.workspace_of(Path(a.root).resolve()))
    a.f(a)


if __name__ == "__main__":
    main()
