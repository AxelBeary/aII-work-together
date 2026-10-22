#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — 看板命令层

核心在 `board.py`。这里只放命令与参数解析。
⚠️ 一律通过 `B.xxx` 访问核心（含 ROOT/WORKSPACE/CARDS 这些**可变全局**，
   直接 import 名字会拿到切换项目前的旧值）。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B                        # noqa: E402


def _board_cmd() -> str:
    """提示里要人复制的 board 命令：装了 PATH 就用 `board`，否则给绝对路径。

    ⚠️ 2026-10-21：本项目支持「当文件夹装进工作区」，那种装法下 `board` 不在 PATH，
       照抄提示会报「命令不存在」。提示必须永远可复制即用。
    """
    import shutil
    if shutil.which("board") or shutil.which("board.cmd"):
        return "board"
    return f'python "{Path(__file__).resolve().parent / "board.py"}"'


def _orch_cmd() -> str:
    """同上：orchestrator.py 的提示命令（始终绝对路径——别的项目里也复制即用）。"""
    import shutil
    if shutil.which("orch"):
        return "orch"
    p = (Path(__file__).resolve().parent / "orchestrator.py")
    return f'python "{p}"'

# ---------- 命令 ----------

def cmd_init(a):
    B._store()          # 建库
    B.ok(f"看板已初始化：{B.BOARD / 'board.db'}")


def _created_kind(a) -> str:
    """谁是建卡人：`--seat human` 必须过人令牌才配叫「人建的」（安全扫描 F-18）。"""
    seat = (getattr(a, "seat", None) or "").strip()
    if not seat or seat == "human":
        if seat == "human":
            ok_tok, why = _verify_human_token(getattr(a, "who", None))
            if not ok_tok:
                B.die("`--seat human` 需要人令牌（否则任何人自称一句就是「人建的」）：\n" + why)
        return "human"
    return "agent"


def cmd_do(a):
    """一句话建卡并立刻跑一轮：把「add → run」合成一步。

    2026-10-23 加：新手最常卡在「建完卡不知道下一步跑什么」。
    这条命令只说一句话，建卡、跑、报结果一条龙；`--no-run` 只建不跑。
    """
    import subprocess
    text = (getattr(a, "text", "") or "").strip()
    if not text:
        B.die('要做什么？例如：board do "给 README 加一段常见问题"')
    cid = f"C{datetime.now().strftime('%m%d')}-{uuid.uuid4().hex[:4]}"
    ns = argparse.Namespace(
        id=cid, title=text[:60], goal=(a.goal or text),
        territory=None, deliverable=getattr(a, "deliverable", None), accept=None,
        human_gate=getattr(a, "human_gate", "none"),
        engine=getattr(a, "engine", "any"), model=getattr(a, "model", None),
        effort="any", irreversible=False, seat=None,
        max_cost=None, max_minutes=None, who=None,
        check_cmd=getattr(a, "check_cmd", None),
    )
    cmd_new(ns)
    if getattr(a, "no_run", False):
        print(f"\n  下一步：{_orch_cmd()} run --cards {cid}")
        return
    print(f"\n  跑一轮（{cid}）…")
    cmd = [sys.executable, str(Path(__file__).resolve().parent / "orchestrator.py"),
           "-C", str(B.ROOT),
           "run", "--cards", cid, "--seat", getattr(a, "seat", "auto-worker")]
    if getattr(a, "engine", "any") not in (None, "", "any"):
        cmd += ["--engine", a.engine]
    if getattr(a, "model", None):
        cmd += ["--model", a.model]
    rc = subprocess.call(cmd, cwd=str(Path.cwd()))
    st = B.replay(cid)
    state = st.get("state")
    print(f"\n  结果：{cid} → {state}")
    if state == "拍板中":
        print(f"  下一步：{_board_cmd()} human {cid} --decision approve")
    elif state in ("待验收", "核验中"):
        print(f"  下一步：{_board_cmd()} verify {cid} --seat <复核席>")
    elif state == "待返工":
        print(f"  打回了 —— 看原因：{_board_cmd()} show {cid}")
    elif state == "阻塞":
        print(f"  卡住了 —— 看原因：{_board_cmd()} show {cid}")
    elif rc != 0:
        print(f"  ⚠ 编排器退出码 {rc}，看上面输出或 {_board_cmd()} show {cid}")


def cmd_new(a):
    # 继承项目默认值：没指定就自动填，省掉手打模型名
    import projects as P
    defaults = P.project_defaults(B.ROOT) or {}
    eng = a.engine if a.engine and a.engine != "any" else defaults.get("engine", "any")
    mdl = a.model if a.model and a.model != "any" else defaults.get("model", "any")
    eft = a.effort if a.effort and a.effort != "any" else defaults.get("effort", "any")
    cid = a.id or f"C{datetime.now().strftime('%m%d')}-{uuid.uuid4().hex[:4]}"
    if B.get_card(cid):
        B.die(f"卡片已存在：{cid}")
    # 预算从命令行来的是字符串，先归一成数字（none/不限 → None）；
    # 没带参数则继承项目默认值（D-016 补充：默认值不设＝不限）
    mc = _parse_limit(getattr(a, "max_cost", None), float)
    mm = _parse_limit(getattr(a, "max_minutes", None), int)
    if mc is None and defaults.get("max_cost_usd") not in (None, "", "none"):
        mc = float(defaults["max_cost_usd"])
    if mm is None and defaults.get("max_minutes") not in (None, "", "none"):
        mm = int(defaults["max_minutes"])
    card = {
        "id": cid, "title": a.title, "goal": a.goal or "",
        "territory": a.territory or [], "deliverables": a.deliverable or [],
        "accept_patterns": a.accept or [],
        "human_gate": a.human_gate,
        # —— 执行规格：谁来干、用什么模型、思考多深 ——
        "engine": eng,
        "model": mdl,
        "effort": eft,
        "created_at": B.ts(),
        "created_by": a.seat or "human",
        "created_kind": _created_kind(a),
        "irreversible": bool(a.irreversible),
        "check_cmd": (getattr(a, "check_cmd", None) or "").strip(),
        "source_card": getattr(a, "from_card", None),
        # —— 预算与依赖（D-016 / B 批）——
        "max_cost_usd": None if mc == "none" else mc,
        "max_minutes": None if mm == "none" else mm,
        "blocked_by": getattr(a, "blocked_by", None) or [],
        # 外问升级（D-023）：返工到阈值后换更强模型；⛔ 触发靠次数，不靠自评
        "escalate_model": getattr(a, "escalate_model", None),
        "escalate_after": getattr(a, "escalate_after", 2),
    }
    B.create_card(card)
    B.append_event(cid, {"type": "created", "actor": card["created_kind"],
                       "seat": card["created_by"], "title": a.title,
                       "engine": card["engine"], "model": card["model"],
                       "effort": card["effort"], "human_gate": a.human_gate,
                       "from_card": card["source_card"]})
    who = "AI 发布" if card["created_kind"] == "agent" else "人建"
    B.ok(f"{who} {cid}：{a.title}")
    spec = []
    if card["engine"] != "any":
        spec.append(f"引擎={card['engine']}")
    if card["model"] != "any":
        spec.append(f"模型={card['model']}")
    if card["effort"] != "any":
        spec.append(f"思考={card['effort']}")
    if spec:
        print(f"  执行规格：{' / '.join(spec)}")
    if card["max_cost_usd"] is not None or card["max_minutes"] is not None:
        lim = []
        if card["max_cost_usd"] is not None:
            lim.append(f"${card['max_cost_usd']:.2f}")
        if card["max_minutes"] is not None:
            lim.append(f"{card['max_minutes']} 分钟")
        print(f"  预算：{' / '.join(lim)}（超了会停下转阻塞）")
    if card["blocked_by"]:
        print(f"  依赖：{'、'.join(card['blocked_by'])}（没完成就不接）")


def cmd_publish(a):
    """AI 发布任务入口。与 new 同源，但强制留发布者身份。"""
    if not a.seat or a.seat == "human":
        B.die("publish 必须带 --seat（你是哪个 agent）—— 发布者身份不可匿名")
    ns = argparse.Namespace(**vars(a))
    ns.seat = a.seat
    cmd_new(ns)
    B.ok(f"已登记发布者：{a.seat}（created_kind=agent）")


def cmd_ready(a):
    """agent 找活干：列出「待认领」且与我的引擎/模型/思考强度匹配的卡。"""
    if not B.card_ids():
        print("（看板为空）")
        return
    hits = []
    for d in B.card_refs():
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
            card = B.get_card(d.name)
        except Exception:
            continue
        if st["state"] not in ("待认领", "阻塞"):
            continue
        miss = B._match_miss(card, a.engine, a.model, a.effort)
        if miss:
            continue
        hits.append((st, card))
    if not hits:
        print(f"（没有匹配的活：引擎={a.engine or 'any'} 模型={a.model or 'any'} "
              f"思考={a.effort or 'any'}）")
        return
    print(f"{'ID':<12} {'引擎':<12} {'模型':<32} {'思考':<7} {'标题'}")
    print("-" * 92)
    for st, card in hits:
        print(f"{st['id']:<12} {card.get('engine','any'):<12} "
              f"{card.get('model','any'):<32} {card.get('effort','any'):<7} "
              f"{st['title'][:28]}")
    print(f"\n共 {len(hits)} 张可接")


def cmd_ls(a):
    if not B.card_ids():
        print("（看板为空，先 board.py new）")
        return
    rows = []
    for d in B.card_refs():
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
        except Exception:
            continue
        if a.state and st["state"] != a.state:
            continue
        rows.append(st)
    if not rows:
        print("（无匹配卡片）")
        return
    order = {s: i for i, s in enumerate(B.STATES)}
    rows.sort(key=lambda r: (order.get(r["state"], 99), r["id"]))
    print(f"{'ID':<12} {'状态':<7} {'持有':<9} {'引擎':<10} {'模型':<22} {'思考':<6} {'标题'}")
    print("-" * 108)
    for r in rows:
        hold = B.holder_of(r["id"], r) or "-"
        mdl = (r.get("model") or "any")
        mdl = "-" if mdl == "any" else mdl
        print(f"{r['id']:<12} {r['state']:<7} {hold:<9} "
              f"{r.get('engine') or 'any':<10} {mdl[:20]:<22} "
              f"{r.get('effort') or 'any':<6} {(r.get('title') or '')[:26]}")
    print(f"\n共 {len(rows)} 张")


def cmd_show(a):
    st = B.replay(a.id)
    card = B.get_card(a.id)
    print(f"\n【{st['id']}】{st['title']}")
    print(f"  状态    {st['state']}")
    tier = B.evidence_tier(a.id, st)
    tier_note = {"VERIFIED": "机器闸 L1-L3 全过（可复核工件）",
                 "AUDITED-UNGROUNDED": "仅复核席表态（同家族复核，不算验证）",
                 "UNVERIFIED": "尚无机器验证"}[tier]
    print(f"  证据    {tier} —— {tier_note}")
    print(f"  持有    {B.holder_of(a.id, st) or '-'}")
    print(f"  引擎    {st['engine']}")
    print(f"  模型    {st['model']}")
    print(f"  思考    {st['effort']}")
    if st["holder"]:
        print(f"  实跑    {st['holder_model'] or '?'} / 思考 {st['holder_effort'] or '?'}")
    print(f"  发布    {st['created_by']}（{st['created_kind']}）")
    print(f"  人闸    {st['gate']}")
    print(f"  返工    {st['rework']} 次")
    if st["blocked_reason"]:
        print(f"  阻塞    {st['blocked_reason']}")
    b = B.budget_status(a.id, card)
    if b["max_cost"] is not None or b["max_minutes"] is not None:
        lim = []
        if b["max_cost"] is not None:
            lim.append(f"${float(b['max_cost']):.2f}")
        if b["max_minutes"] is not None:
            lim.append(f"{int(b['max_minutes'])} 分钟")
        mark = "  ⚠ 已超" if b["over"] else ""
        print(f"  预算    已花 ${b['cost']:.4f} / {b['minutes']} 分钟"
              f"（上限 {' / '.join(lim)}）{mark}")
    elif b["cost"] or b["minutes"]:
        print(f"  用量    已花 ${b['cost']:.4f} / {b['minutes']} 分钟（未设上限）")
    if b["unknown_runs"]:
        print(f"          ⚠ 有 {b['unknown_runs']} 次引擎没报用量（那部分费用未知）")
    if card.get("blocked_by"):
        deps = []
        for dep in card["blocked_by"]:
            dst = B.replay(str(dep))["state"] if B.get_card(str(dep)) else "不存在"
            deps.append(f"{dep}（{dst}）")
        print(f"  依赖    {'、'.join(deps)}")
    if card.get("goal"):
        print(f"  目标    {card['goal']}")
    if card.get("territory"):
        print(f"  领地    {', '.join(card['territory'])}")
    if card.get("deliverables"):
        print(f"  交付    {', '.join(card['deliverables'])}")
    if st["submit"]:
        print(f"  提交    {st['submit'].get('note','')}")
    if st["review"]:
        print(f"  复核    {st['review'].get('verdict')} by {st['review'].get('seat')}"
              f"（第 {st['review'].get('round') or 1} 轮）")
        items = st["review"].get("items") or []
        if items:
            opens = [i for i in items if i.get("state") == "open"]
            stuck = set(st["review"].get("stuck") or [])
            print(f"  意见    {len(items)} 条，未关闭 {len(opens)} 条"
                  + (f"，其中卡住 {len(stuck)} 条" if stuck else ""))
            for i in items[:8]:
                mark = "✗" if i.get("state") == "open" else "✓"
                flag = " ← 两轮未解决" if i.get("id") in stuck else ""
                print(f"     {mark} {i.get('id')}  {i.get('text','')[:60]}{flag}")
    diff = B.diff_vs_baseline(a.id, card)
    if diff:
        print("  改动（认领前 → 现在）：")
        for d in diff:
            bf, af = d["before"], d["after"]
            left = f"{bf['bytes']}B" if bf.get("exists") else "-"
            right = f"{af['bytes']}B" if af.get("exists") else "-"
            print(f"    {d['status']:<3} {d['path']}  {left} → {right}")
    print(f"  事件    {st['events']} 条")
    if a.events:
        print("\n  事件流：")
        for ev in B.load_journal(a.id):
            print(f"    {ev['seq']:>3} {ev['at'][11:19]} {ev['type']:<14} {ev.get('seat','')}")


def cmd_claim(a):
    B.claim(a.id, a.seat, a.engine, a.model, a.effort)
    B.ok(f"认领成功：{a.id} → {a.seat}")
    print(f"  引擎={a.engine} 模型={a.model or 'any'} 思考={a.effort or 'any'}")
    ep = _lease_epoch(B.active_lease(a.id))
    print(f"  租约 epoch={ep}（beat/submit 带 --epoch {ep}：被回收后旧进程就写不进了）")
    print(f"  ⚠ 每 {B.HB_INTERVAL}s 内至少跑一次 beat，否则 {B.LEASE_TTL}s 后被回收")


def _parse_limit(v, cast):
    """解析预算上限：数字 / none＝取消上限。"""
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("none", "off", "unlimited", "不限"):
        return "none"
    try:
        return cast(float(s))
    except ValueError:
        B.die(f"预算上限要写数字或 none，收到：{v}")


def cmd_budget(a):
    """看／改单卡预算与依赖（D-016）。

    红线：**收紧随便改，放宽只能人来。**
    预算是防跑飞的刹车；执行席要是能自己松刹车，这条防线就等于没有。
    「不限 → 有限」算收紧（可以）；「有限 → 更大/不限」算放宽（要 `--seat human`）。
    """
    card = B.require_card(a.id)
    seat = (getattr(a, "seat", None) or "").strip()
    is_human = seat == "human"
    new_cost = _parse_limit(getattr(a, "max_cost", None), float)
    new_min = _parse_limit(getattr(a, "max_minutes", None), int)
    new_deps = getattr(a, "blocked_by", None)
    drop_deps = getattr(a, "unblock", False)

    changes, loose = [], []
    if new_cost is not None:
        old = card.get("max_cost_usd")
        val = None if new_cost == "none" else float(new_cost)
        if val is None or (old is not None and val > float(old)):
            loose.append(f"花费上限 {old} → {val if val is not None else '不限'}")
        changes.append(("max_cost_usd", val))
    if new_min is not None:
        old = card.get("max_minutes")
        val = None if new_min == "none" else int(new_min)
        if val is None or (old is not None and val > int(old)):
            loose.append(f"时长上限 {old} → {val if val is not None else '不限'}")
        changes.append(("max_minutes", val))
    if new_deps is not None:
        changes.append(("blocked_by", list(new_deps)))
    if drop_deps:
        loose.append("清空依赖")
        changes.append(("blocked_by", []))

    if not changes:
        b = B.budget_status(a.id, card)
        print(f"\n【{a.id}】{card.get('title', '')}")
        print(f"  已花    ${b['cost']:.4f} / {b['minutes']} 分钟"
              f"（{b['unknown_runs']} 次未报用量）")
        print(f"  上限    花费 {b['max_cost'] if b['max_cost'] is not None else '不限'} / "
              f"时长 {b['max_minutes'] if b['max_minutes'] is not None else '不限'}"
              f"{'  ⚠ 已超' if b['over'] else ''}")
        if card.get("blocked_by"):
            print(f"  依赖    {'、'.join(card['blocked_by'])}")
        return

    if loose:
        # ⚠️ 2026-10-21 修（安全扫描 F-07）：旧判据只有 `--seat human` 这个字符串，
        #    等于任何 agent 写一个词就能松刹车。现在两把都要：
        #    ① 自报 human；② 过人令牌（与人拍板同一把）。
        if not is_human:
            B.die("放宽预算/去掉依赖只能人来做（要 --seat human ＋ 人令牌）：\n  - "
                  + "\n  - ".join(loose))
        ok_tok, why = _verify_human_token(getattr(a, "who", None))
        if not ok_tok:
            B.die("放宽预算/去掉依赖只能人来做（要人令牌，--seat human 不再算数）：\n  - "
                  + "\n  - ".join(loose) + "\n" + why)
    merged = {k: v for k, v in card.items() if k != "meta"}
    for k, v in changes:
        merged[k] = v
    B._store().save_card(merged)
    B.append_event(a.id, {"type": "budget_set", "actor": "human" if is_human else "agent",
                          "seat": seat or "agent",
                          "max_cost_usd": merged.get("max_cost_usd"),
                          "max_minutes": merged.get("max_minutes"),
                          "blocked_by": merged.get("blocked_by") or [],
                          "note": "；".join(loose) if loose else "收紧/改依赖"})
    B.ok(f"已更新 {a.id} 的预算/依赖")
    for k, v in changes:
        print(f"  {k} = {v if v is not None else '不限'}")


def guard_transition(cid: str, to_state: str, actor: str):
    """状态转移守卫：不在白名单里的一律拒绝。

    ⚠️ 2026-10-20 修：B.TRANSITIONS 此前只是「定义」，从未被调用
    （opus 评审指出：任何状态下追加一条 human 事件都能直接变「完成」）。
    """
    st = B.replay(cid)
    frm = st["state"]
    if frm == to_state:
        return
    rule = B.TRANSITIONS.get((frm, to_state))
    if rule is None:
        B.die(f"非法状态转移：「{frm}」→「{to_state}」不在白名单里\n"
            f"  合法去向：{_legal_from(frm)}")
    if actor not in rule["actor"]:
        B.die(f"越权：{actor} 不能把卡从「{frm}」推进到「{to_state}」\n"
            f"  该转移只允许：{'/'.join(sorted(rule['actor']))}")


def _legal_from(state: str) -> str:
    outs = [t for (f, t) in B.TRANSITIONS if f == state]
    return "、".join(outs) if outs else "（无，是终态）"


def guard_holder(cid: str, seat: str, epoch: int = None):
    """确认你是当前租约持有者，且（可选）epoch 与租约一致。

    防的是：长任务执行中租约超时被别人回收接手，旧执行者回来提交，
    把别人的活覆盖掉（opus 评审指出）。
    ⚠️ 2026-10-21：参数 epoch 是可选的**栅栏**；不带时行为与旧版一致（向后兼容），
       但同席位换代那种情况只有带 epoch 才拦得住（编排调研指出 epoch 一直是死字段）。
    """
    lease = B.active_lease(cid)
    if not lease:
        B.die("你没有活跃租约（可能已被回收）")
    owner = B._lease_owner(lease)
    if owner.get("seat") != seat:
        B.die(f"卡片已归 {owner.get('seat')}（你的租约已被回收）")
    # 栅栏（2026-10-21，编排调研指出的洞）：同席位被回收后重新认领会换代。
    # epoch 是唯一能区分「同一席位的前后两代」的东西——不比它，旧执行者照样能提交。
    if epoch is not None:
        cur = _lease_epoch(lease)
        if int(epoch) != cur:
            B.die(f"租约已换代：当前 epoch={cur}，你带的是 {epoch}"
                  f"（你那一代已被回收，⛔ 不要再写）")
    st = B.replay(cid)
    return st.get("epoch", 0)


def _lease_epoch(lease) -> int:
    try:
        return int(B._lease_owner(lease).get("epoch", 0))
    except Exception:
        return 0


def cmd_beat(a):
    B.heartbeat(a.id, a.seat, epoch=getattr(a, "epoch", None))


def cmd_block(a):
    guard_transition(a.id, "阻塞", "agent")
    st = B.replay(a.id)
    if st["holder"] != a.seat:
        B.die(f"你不是持有者（当前 {st['holder']}）")
    B.append_event(a.id, {"type": "block", "actor": "agent", "seat": a.seat, "reason": a.reason})
    B.ok(f"已阻塞：{a.reason}")


def cmd_submit(a):
    # ⚠️ 2026-10-20 修：以前只比 replay 里的 holder，而租约表可能已经被回收
    #    ⇒ 旧持有者照样能提交（Q1 复核复现：退出码 0、L1-L3 全过）。
    guard_holder(a.id, a.seat, getattr(a, "epoch", None))
    card = B.get_card(a.id)
    # 提交即跑 L1-L3
    ok1, p1, r1 = B.gate_l1(a.id, card)
    ok2, p2 = B.gate_l2(a.id, card)
    ok3, p3, c3 = B.gate_l3(a.id, card)
    ok4, p4, out4 = B.gate_l4(a.id, card)
    problems = p1 + p2 + p3 + p4
    verdict = "pass" if (ok1 and ok2 and ok3 and ok4) else "fail"
    B.append_event(a.id, {
        "type": "submit", "actor": "agent", "seat": a.seat, "note": a.note or "",
        "pid": os.getpid(),
        "epoch": _lease_epoch(B.active_lease(a.id)),
        "gate": {"L1": ok1, "L2": ok2, "L3": ok3, "L4": ok4,
                 "problems": problems, "files": r1,
                 "check_tail": (out4 or "")[-800:]},
        "exit_code_note": "退出码不参与判定（权重 0）",
    })
    if verdict == "pass":
        B.ok("L1-L3 全过 → 待验收")
        for r in r1:
            print(f"  {r['path']}  {r.get('bytes','?')}B  sha8={r.get('sha8','-')}")
    else:
        print("✗ 闸门未过，已记录但不进「待验收」：")
        for p in problems:
            print(f"  · {p}")
        B.append_event(a.id, {"type": "block", "actor": "system", "seat": "system",
                            "reason": "闸门未过：" + "；".join(problems[:3])})


def cmd_verify(a):
    guard_transition(a.id, "核验中", "review")
    st = B.replay(a.id)
    if st["state"] != "待验收":
        B.die(f"当前状态「{st['state']}」，需先 submit")
    card = B.get_card(a.id)
    ok1, p1, r1 = B.gate_l1(a.id, card)
    ok2, p2 = B.gate_l2(a.id, card)
    ok3, p3, c3 = B.gate_l3(a.id, card)
    B.append_event(a.id, {"type": "verify", "actor": "review", "seat": a.seat or "review",
                        "L1": ok1, "L2": ok2, "L3": ok3,
                        "problems": p1 + p2 + p3})
    print(f"L1 产物存在  {'PASS' if ok1 else 'FAIL'}")
    print(f"L2 形制      {'PASS' if ok2 else 'FAIL'}")
    print(f"L3 内容闸门  {'PASS' if ok3 else 'FAIL'}")
    for p in p1 + p2 + p3:
        print(f"  · {p}")
    B.ok("已进「核验中」，待复核席给结论")


def cmd_consult(a):
    """点对点评审：找 B1/B2 独立提意见（只准看、不准改）。"""
    import consult as C
    reviewers = C.parse_reviewers(a.by)
    res = C.consult(a.id, a.q, reviewers,
                    files=a.file or None, role=a.role, round_no=a.round,
                    parallel=a.parallel, timeout=a.timeout, dry_run=a.dry_run)
    if a.dry_run:
        print(res["prompt"])
        return
    print(res["packet"])
    if res["violations"]:
        B.die("评审席改动了文件（已按原字节恢复）—— 这次评审作废，重跑")
    fails = [r for r in res["replies"] if not r["ok"]]
    if fails and len(fails) == len(res["replies"]):
        B.die("所有评审席都调用失败，检查引擎/模型名")
    B.ok(f"评审完成：{len(res['replies'])} 席（{len(fails)} 席失败）")
    print("\n下一步：按意见改完后，正常走 submit → review 就行。")


def _review_items(a) -> list:
    """解析复核意见：`--item ID:open|fixed:说明`（可重复）或 `--items-file`。

    为什么要结构化：自由文本没法对账——第三轮时复核席不知道「上一轮那 5 条改没改」，
    执行席也不知道自己漏了哪条。ID 稳定、状态二值，才能算「还剩几条」「哪条卡住了」。
    """
    items = []
    if getattr(a, "items_file", None):
        try:
            data = json.loads(Path(a.items_file).read_text(encoding="utf-8"))
        except Exception as e:
            B.die(f"--items-file 读不了：{e}")
        if not isinstance(data, list):
            B.die("--items-file 必须是 JSON 数组")
        for it in data:
            if not isinstance(it, dict) or "id" not in it:
                B.die("--items-file 里每条都要有 id")
            state = str(it.get("state") or "open").lower()
            if state not in ("open", "fixed"):
                B.die(f"意见 {it['id']} 的状态只能是 open/fixed，收到 {state}")
            items.append({"id": str(it["id"]), "state": state,
                          "text": str(it.get("text") or "")[:300]})
    for raw in getattr(a, "item", []) or []:
        parts = str(raw).split(":", 2)
        if len(parts) < 2:
            B.die(f"--item 要写成 ID:open|fixed:说明，收到 {raw!r}")
        iid, state = parts[0].strip(), parts[1].strip().lower()
        if not iid:
            B.die("--item 的 ID 不能为空")
        if state not in ("open", "fixed"):
            B.die(f"意见 {iid} 的状态只能是 open/fixed，收到 {state}")
        items.append({"id": iid, "state": state,
                      "text": (parts[2].strip() if len(parts) > 2 else "")[:300]})
    # 同一 ID 出现两次：后写的算数（允许先列旧的 fixed 再列新的 open）
    dedup = {}
    for it in items:
        dedup[it["id"]] = it
    return list(dedup.values())


def cmd_review(a):
    st = B.replay(a.id)
    # ⚠️ 2026-10-21：旧代码允许从「待验收」直接复核，但状态机白名单里没有
    #    待验收 → 完成/拍板中，于是报一句看不懂的「非法状态转移」。
    #    真实流程是：submit → 待验收 → verify（机器闸）→ 核验中 → review。
    if st["state"] == "待验收":
        B.die("这张卡还在「待验收」：先跑 `board verify "
              f"{a.id} --seat {a.seat}` 过机器闸，进「核验中」后再给复核结论。")
    if st["state"] != "核验中":
        B.die(f"当前状态「{st['state']}」，只有「核验中」的卡能复核")
    guard_transition(a.id, "完成" if a.verdict == "pass" else "待返工", "review")
    # 红线①（加固）：机器闸未过就不许给 PASS
    last_verify = None
    for ev in B.load_journal(a.id):
        if ev.get("type") == "verify":
            last_verify = ev
    if a.verdict == "pass" and last_verify and last_verify.get("problems"):
        B.die("机器闸有未解决问题，⛔ 不许直接给 PASS：\n  "
            + "\n  ".join(str(p) for p in last_verify["problems"][:5])
            + "\n  先修好再复核，或给 --verdict fail")
    # 红线①：复核席不得是执行者
    executor = (st["submit"] or {}).get("seat") or st["holder"]
    if a.seat == executor:
        B.die(f"复核席不得是执行席本人（{executor}）—— 红线①：完成必须异会话")
    # 红线①（加固）：复核必须留下可复跑的凭据 —— 声明自己跑了什么、看到什么
    if not a.evidence:
        B.die("复核必须带 --evidence（你实际跑过的命令与其读数）。"
            "空口 PASS 不可入正档 —— 见 AGENTS.md §1.2 反空跑")
    ev_ok, ev_why = _check_evidence(a.evidence)
    if not ev_ok:
        B.die(f"复核凭据不合格：{ev_why}")
    # ---- 结构化意见（2026-10-23）：能算「还剩几条」「哪条连续两轮没解决」----
    items = _review_items(a)
    open_items = [i for i in items if i["state"] == "open"]
    if items and a.verdict == "pass" and open_items:
        B.die(f"还有 {len(open_items)} 条未关闭的意见，⛔ 不能给 PASS："
              + "、".join(i["id"] for i in open_items[:8])
              + "\n  （确实不用改了就把它们标成 fixed 再 PASS）")
    if items and a.verdict == "fail" and not open_items:
        B.die("意见全部标成 fixed 却给了 fail —— 该给 pass，或者把还没解决的标成 open")
    prev_open, review_rounds = set(), 0
    for ev in B.load_journal(a.id):
        if ev.get("type") == "review":
            review_rounds += 1
            prev_open = {str(i.get("id")) for i in (ev.get("items") or [])
                         if i.get("state") == "open"}
    stuck = sorted({i["id"] for i in open_items} & prev_open)
    if stuck:
        print(f"  ⚠ 这几条上一轮就是 open：{'、'.join(stuck[:6])}"
              f"（第 {review_rounds + 1} 轮仍未解决）")
        print("     建议：换更强的模型再来一轮，或直接报阻塞等人决定 —— 别让同一句意见转第三圈。")
        # 收口刹车（2026-10-23）：同一条意见连续 3 轮没解决，大概率不是「再改改」能解决的。
        # 想继续转必须显式 --force，让「无限转」变成一个要人签字的选择。
        if review_rounds + 1 >= 3 and not getattr(a, "force", False):
            B.die(f"同一条意见已连续 {review_rounds + 1} 轮未解决，⛔ 不再自动转圈。\n"
                  "  二选一：\n"
                  f"    ① 报阻塞等人决定：{_board_cmd()} block {a.id} --seat {a.seat} "
                  "--reason \"同一意见三轮未解决\"\n"
                  f"    ② 确实还要再来一轮：加 --force（会在记录里留下痕迹）")
    if st["gate"] in ("both", "before_done") and a.verdict == "pass":
        B.append_event(a.id, {"type": "review", "actor": "review", "seat": a.seat,
                            "verdict": a.verdict, "note": a.note or "",
                            "evidence": a.evidence, "evidence_ok": True,
                            "items": items, "stuck": stuck, "round": review_rounds + 1,
                            "forced": bool(getattr(a, "force", False)),
                            "pid": os.getpid()})
        B.append_event(a.id, {"type": "request_human", "actor": "review", "seat": a.seat})
        B.release(a.id)
        B.ok("复核通过 → 已转「拍板中」，等人拍板")
        return
    B.append_event(a.id, {"type": "review", "actor": "review", "seat": a.seat,
                        "verdict": a.verdict, "note": a.note or "",
                        "evidence": a.evidence, "evidence_ok": True,
                        "items": items, "stuck": stuck, "round": review_rounds + 1,
                        "forced": bool(getattr(a, "force", False))})
    if a.verdict == "pass":
        B.release(a.id)
        B.ok("复核 PASS → 完成")
    else:
        B.release(a.id)
        B.ok("复核 FAIL → 打回「进行中」")


def _check_evidence(ev: str) -> tuple:
    """复核凭据的最低可判标准（2026-10-21 收紧，安全扫描 F-23）。

    旧判据「≥12 字符 + 一个标识符 + 一个数字」，`a1 3` 就能过。现在要求：
      ① 至少 24 字符；② 有像命令的片段（带参数或路径）；
      ③ 有数字；④ 三样里至少两样是「命令 + 数字」，且不含填空式占位词。
    """
    s = (ev or "").strip()
    if len(s) < 24:
        return False, "凭据太短（<24 字符），写清「跑了什么命令 + 看到什么数字」"
    low = s.lower()
    for bad in ("todo", "tbd", "同上", "见上", "xxx", "待补"):
        if bad in low:
            return False, f"凭据里有占位词「{bad}」——要可复跑的真实读数"
    has_cmd = bool(re.search(r"[A-Za-z_][\w\.\-]*(\.py|\.cmd|\.exe)?[\s]+[-\w/]", s)) \
        or bool(re.search(r"[A-Za-z0-9_\-/\\]+\.(py|md|json|log|txt)\b", s))
    has_num = bool(re.search(r"\d", s))
    if not (has_cmd and has_num):
        return False, "凭据要有「命令/文件」和「数字读数」两段（例：`python tools/check.py` → 16 道全绿）"
    return True, ""


def _human_home() -> Path:
    """人令牌/登记文件的存放根：默认家目录，可用 BOARD_HUMAN_HOME 隔离（测试用）。"""
    h = os.environ.get("BOARD_HUMAN_HOME")
    return Path(h) if h else Path.home()


def human_token(who: str = None) -> Path:
    """人 token 放看板目录之外。

    多人场景：每人一个 token（按 who 区分），互不顶替。
    """
    who = (who or os.environ.get("BOARD_USER") or "").strip()
    if who and who not in ("owner", "human"):
        safe = re.sub(r"[^\w\-.]", "_", who)[:40]
        return _human_home() / f".board-human-{safe}.tok"
    return _human_home() / ".board-human.tok"


def human_token_sha(who: str = None) -> Path:
    """令牌哈希登记（只存哈希，推不出原令牌）。按人分开，**按用户**而非按项目。

    ⚠️ 2026-10-21 改（安全扫描 F-16）：登记文件原先放在 `board/` 里 ⇒ 每建一个新项目
       都要重新登记一次，等于鼓励「随手再登记一份」。现在统一放家目录。
    """
    who = (who or os.environ.get("BOARD_USER") or "").strip()
    if who and who not in ("owner", "human"):
        safe = re.sub(r"[^\w\-.]", "_", who)[:40]
        return _human_home() / f".board-human-{safe}.sha"
    return _human_home() / ".board-human.sha"


def _verify_human_token(who: str = None) -> tuple:
    """校验人令牌。返回 (ok, 原因)。

    防线（诚实标注：这是**提高门槛**，不是绝对强制，见 AGENTS.md §4.1）：
      1. 令牌必须存在且内容非空（⛔ 0 字节放行）
      2. 内容长度 ≥ 16
      3. 与首次登记时存的 sha256 一致（换令牌 = 留痕）
      4. 多人：不同 who 用不同令牌文件，互不顶替
    """
    tok = human_token(who)
    if not tok.exists():
        return False, (f"缺人令牌：{tok}\n"
                       f"  创建：Set-Content -Path \"{tok}\" "
                       f"-Value \"<你自己定的长串>\" -NoNewline")
    try:
        content = tok.read_text(encoding="utf-8").strip()
    except Exception as e:
        return False, f"人令牌读不了：{e}"
    if not content:
        return False, "人令牌是空的 —— ⛔ 空文件不算令牌（这是本条防线要防的）"
    if len(content) < 16:
        return False, f"人令牌太短（{len(content)} < 16 字符）—— 换一个长一点的"
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    reg = human_token_sha(who)
    if not reg.exists():
        # 老布局（登记文件在 board/ 里）→ 一次性迁到家目录，避免「换个项目就失效」。
        who_s = (who or os.environ.get("BOARD_USER") or "").strip()
        suffix = ("-" + re.sub(r"[^\w\-.]", "_", who_s)[:40]) \
            if who_s and who_s not in ("owner", "human") else ""
        legacy = B.BOARD / f".human-token{suffix}.sha"
        if legacy.exists():
            try:
                reg.write_text(legacy.read_text(encoding="utf-8").strip(),
                               encoding="utf-8")
            except Exception as e:
                print(f"⚠ 旧令牌登记迁移失败：{e}", file=sys.stderr)
    if not reg.exists():
        # ⚠️ 2026-10-21 修（安全扫描 F-16）：旧实现「首次无登记即放行」——
        #    等于任何人放一个 ≥16 字符的文件就能当人。现在必须先显式登记：
        #    `board token --init --who <who>`（只存哈希）。
        return False, ("令牌未登记（首次使用）：请在你自己的终端跑一次 "
                       f"`board token --init --who {who or 'owner'}`")
    try:
        expected = reg.read_text(encoding="utf-8").strip()
    except Exception:
        return False, "令牌登记文件读不了"
    if sha != expected:
        return False, ("人令牌已变更（与登记哈希不符）。"
                       "若这是你本人换的，删掉登记文件重新登记；否则是有人动了令牌")
    return True, ""


def cmd_human(a):
    # 红线②：唯一能推进人位的入口
    guard_transition(a.id, "完成" if a.decision == "approve" else "待返工", "human")
    ok_tok, why = _verify_human_token(a.who)
    if not ok_tok:
        B.die(why)
    st = B.replay(a.id)
    if st["state"] != "拍板中":
        B.die(f"当前状态「{st['state']}」，只有「拍板中」的卡需要人拍")
    B.append_event(a.id, {"type": "human", "actor": "human", "who": a.who or "owner",
                        "decision": a.decision, "note": a.note or ""})
    B.ok(f"人已{a.decision}：{a.id}")

def cmd_token(a):
    """人令牌登记：把当前令牌的 sha256 写进登记文件（只存哈希）。"""
    if not a.init:
        B.die("用法：board token --init [--who <who>]（把当前令牌登记为基准哈希）")
    tok = human_token(a.who)
    if not tok.exists():
        B.die(f"缺令牌文件：{tok}\n"
              f'  先自己建：Set-Content -Path "{tok}" -Value "<你自己定的长串>" -NoNewline')
    try:
        content = tok.read_text(encoding="utf-8").strip()
    except Exception as e:
        B.die(f"令牌读不了：{e}")
    if len(content) < 16:
        B.die(f"令牌太短（{len(content)} < 16 字符）—— 换一个长一点的")
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    reg = human_token_sha(a.who)
    reg.write_text(sha, encoding="utf-8")
    B.ok(f"已登记人令牌（who={a.who or 'owner'}，只存哈希）")


def cmd_reclaim(a):
    """回收超时租约（走库，不走早已不存在的 lease/active 目录）。

    ⚠️ 2026-10-20 修：旧实现遍历 `cards/<id>/lease/active/`，那是文件时代的布局，
       SQLite 版里这个目录从来不存在 ⇒ 永远 0 命中，却照样打印「✓ 回收完成：0 个」，
       而 `doctor` 同时报「超时未回收」——两把尺互相打架（Q1 复核复现）。
    """
    st = B._store()
    rows = st.expired_leases()
    if not rows:
        print("✓ 没有超时租约（无可回收）")
        return
    n = 0
    for r in rows:
        cur = B._reclaim_lease(r["card_id"], reason=f"心跳超时 {r['age_s']}s")
        if cur:
            n += 1
            print(f"  · 回收 {r['card_id']}：{cur.get('seat')}（{r['age_s']}s 无心跳）")
    print(f"回收 {n} of {len(rows)}（口径＝租约条数）")
    if n != len(rows):
        B.die("有租约没回收成功（并发改写？）——再跑一次 board reclaim")


def cmd_audit(a):
    """检测绕过 CLI 直接改库/改日志的行为。

    ⚠️ 2026-10-21 修（外部评审抓到的**假绿**，见 docs/research/20261021-peer-review-lead）：
       租约类判据原先读 `board/cards/<id>/lease/active` 目录，而租约早已迁到
       SQLite `leases` 表 ⇒ 新架构下这两个目录**永远不存在**，判据恒 0 命中。
       现在：租约一律读库，并新增「状态与租约互相印证」两条；旧目录只在真的存在时兜底。
    """
    issues = []
    audited = 0
    for cid in B.card_ids():
        audited += 1
        d = B.card_ref(cid)
        # 0) 哈希链校验（整份重写/插入/改内容都会断链）
        chain_ok, chain_why = B.verify_chain(cid)
        if not chain_ok:
            issues.append(f"{cid}: 哈希链断裂 ← {chain_why}")
        try:
            st = B.replay(cid)
        except Exception as e:
            issues.append(f"{cid}: journal 无法重放（{e}）")
            continue
        card = B.get_card(cid) or {}
        # 1) 完成但没有复核记录
        if st["state"] == "完成" and not st["review"]:
            issues.append(f"{cid}: 状态=完成 但无复核记录")
        # 2) 完成但复核席==执行席
        if st["review"] and st["submit"]:
            if st["review"].get("seat") == st["submit"].get("seat"):
                issues.append(f"{cid}: 复核席与执行席同一人")
        # 2b) 复核无凭据（疑似手写 journal 绕过 CLI）—— 红线①的可判形制
        if st["review"] and not st["review"].get("evidence"):
            issues.append(f"{cid}: 复核记录缺 evidence 字段 ← 疑似绕过 CLI 手写 journal")
        # 2c) 提交记录缺闸门读数（同上）
        if st["submit"] and "gate" not in st["submit"]:
            issues.append(f"{cid}: 提交记录缺 gate 读数 ← 疑似绕过 CLI")
        # 3) 人闸卡在完成但无人拍板
        if st["state"] == "完成" and st["gate"] in ("both", "before_done") and not st["human"]:
            issues.append(f"{cid}: 人闸卡已「完成」但无人工记录 ← 疑似绕过")
        # 4) 租约以库为准：状态与租约必须互相印证（手改库/手写 journal 会露馅）
        lease_row = B._store().get_lease(cid)
        if st["state"] == "进行中" and not lease_row:
            issues.append(f"{cid}: 状态=进行中 但库里没有租约 ← 疑似手改状态")
        if lease_row and st["state"] in ("待认领", "待返工", "完成", "已取消"):
            issues.append(f"{cid}: 有租约（{lease_row.get('seat')}）但状态={st['state']}"
                          f" ← 疑似手改状态")
        # 4c) 换代后仍有旧代写入（2026-10-21，编排调研指出 epoch 一直是死字段）
        #     判据：某事件的 epoch 小于该卡已出现过的最大 claim epoch ⇒ 旧代写过盘
        try:
            max_ep, stale = 0, []
            for ev in B.load_journal(cid):
                if ev.get("type") == "claim":
                    max_ep = max(max_ep, int(ev.get("epoch") or 0))
                elif ev.get("type") in ("heartbeat", "submit", "review"):
                    ep = ev.get("epoch")
                    if ep is not None and int(ep) < max_ep:
                        stale.append(f"{ev.get('type')}@{ev.get('seat')} epoch={ep}")
            if stale:
                issues.append(f"{cid}: 换代后仍有旧代写入（{len(stale)} 条，"
                              f"如 {stale[0]}）← 栅栏没生效或被绕过")
        except Exception as e:
            issues.append(f"{cid}: epoch 对账失败（{e}）")
        # 4b) 旧版租约目录：只在真的存在时兜底（库版不写目录）
        legacy = d / "lease" / "active"
        if legacy.exists():
            act = [x for x in legacy.iterdir() if x.is_dir()]
            if len(act) > 1:
                issues.append(f"{cid}: 旧版租约目录 {len(act)} 个（应 ≤1）")
            for x in act:
                if x.name != B.LEASE_NAME:
                    issues.append(f"{cid}: 旧版租约目录名非固定名「{x.name}」← 原子性不成立")
        # 5) 交付物缺失但已提交
        if st["state"] in ("待验收", "核验中", "完成"):
            for item in card.get("deliverables", []):
                rel = item if isinstance(item, str) else item.get("path")
                p = (B.WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
                if not p.exists():
                    issues.append(f"{cid}: 交付物已丢 {rel}")
    if issues:
        print(f"✗ 发现 {len(issues)} 个问题：")
        for i in issues:
            print(f"  · {i}")
        sys.exit(2)
    B.ok(f"审计通过：{audited} 张卡全查（库内卡 + 租约表），无绕过痕迹")


def cmd_html(a):
    """生成静态看板页（单项目）。双击即可看。"""
    import render as RD
    cards = []
    for d in B.card_refs():
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
            card = B.get_card(d.name)
        except Exception:
            continue
        st["goal"] = card.get("goal", "")
        st["deliverables"] = card.get("deliverables", [])
        cards.append(st)

    out = B.BOARD / "board.html"
    name = B.ROOT.name
    RD.render_project(cards, f"看板 · {name}", out, project_name=name,
                      has_overview=True)
    B.ok(f"看板已生成：{out}")
    print(f"  共 {len(cards)} 张卡")
    return out


def cmd_overview(a):
    """跨项目总览页。"""
    import render as RD
    import projects as P
    out = Path.home() / ".aII-work-together" / "overview.html"
    ps = P.project_summary()
    RD.render_all(ps, out)
    B.ok(f"总览已生成：{out}")
    for p in ps:
        print(f"  {p['name']:<20} {p.get('cards', 0):>3} 张")


def cmd_project(a):
    """项目管理：add / ls / rm / default。"""
    import projects as P
    if a.action == "ls":
        ps = P.list_projects()
        if not ps:
            print("（还没有登记任何项目）")
            print(f"  注册表：{P.REGISTRY_DB}")
            return
        print(f"{'':2} {'项目':<20} {'卡片':>4}  {'默认引擎/模型':<38} 路径")
        print("-" * 96)
        for p in ps:
            mark = "✓" if p["exists"] else "✗"
            cp = P.cards_path(p["path"])
            n = len([d for d in cp.iterdir() if d.is_dir()]) if cp.exists() else 0
            d = p.get("defaults") or {}
            spec = f"{d.get('engine','—')}/{d.get('model','—')}"
            print(f"{mark:2} {p['name']:<20} {n:>4}  {spec:<38} {p['path']}")
        print(f"\n共 {len(ps)} 个项目 ｜ 注册表：{P.REGISTRY_DB}")
        return

    if a.action == "add":
        target = a.path or str(Path.cwd())
        entry = P.add_project(target, a.name)
        P.ensure_root(Path(entry["path"]))
        B.ok(f"已登记：{entry['name']} → {entry['path']}")
        return

    if a.action == "rm":
        if not a.name:
            B.die("需要 --name（或路径）")
        if P.remove_project(a.name):
            B.ok(f"已移除登记：{a.name}（⛔ 磁盘数据未动）")
        else:
            B.die(f"没找到：{a.name}")
        return

    if a.action == "default":
        entry = P.add_project(B.ROOT)
        d = entry.setdefault("defaults", {})
        if a.engine:
            d["engine"] = a.engine
        if a.model:
            d["model"] = a.model
        if a.effort:
            d["effort"] = a.effort
        # 预算默认值（D-016 补充）：不设＝新卡不限；设了则新卡自动继承，仍可单卡覆盖
        for key, raw, cast in (("max_cost_usd", getattr(a, "max_cost", None), float),
                               ("max_minutes", getattr(a, "max_minutes", None), int)):
            v = _parse_limit(raw, cast)
            if v is None:
                continue                 # 没带这个参数＝不动
            if v == "none":
                d.pop(key, None)         # 明确取消
            else:
                d[key] = v
        # 写回
        ws = getattr(a, "workspace", None)
        if ws:
            wp = Path(ws)
            if not wp.exists():
                B.die(f"工作区不存在：{wp}")
        P.add_project(B.ROOT, defaults=d, workspace=ws)
        wsd = P.workspace_of(B.ROOT)
        B.ok(f"本项目默认值：引擎={d.get('engine','—')} 模型={d.get('model','—')} "
           f"思考={d.get('effort','—')}")
        bc = d.get("max_cost_usd")
        bm = d.get("max_minutes")
        if bc is not None or bm is not None:
            print(f"  新卡预算：{('$%.2f' % float(bc)) if bc is not None else '不限'}"
                  f" / {(str(int(bm)) + ' 分钟') if bm is not None else '不限'}")
        print(f"  工作区：{wsd}")
        return


def cmd_bare(a):
    """不带子命令时：给一个能直接用的面板，而不是报错。

    2026-10-23 改：从「状态计数表」换成「三行人话 + 一条最该做的命令」——
    非程序员看不出「待验收 2」是什么意思，但看得懂「2 张等你拍板」。
    """
    print(f"📋 {B.ROOT.name}")
    print(f"   {B.ROOT}\n")

    if not B.card_ids():
        print("   还没有任何卡。\n")
        print("   下一步：")
        print(f"     {_board_cmd()} add --title \"要做什么\" --goal \"具体目标\"")
        print(f"     {_board_cmd()} project default --engine opencode "
              "--model opencode-go/deepseek-v4.1-flash")
        return

    rows = {"human": [], "doing": [], "blocked": [], "doing_bad": [], "todo": []}
    counts = {}
    total = 0
    for d in B.card_refs():
        if not d.is_dir():
            continue
        cid = d.name
        try:
            st = B.replay(cid)
            card = B.get_card(cid) or {}
        except Exception:
            continue
        total += 1
        counts[st.get("state")] = counts.get(st.get("state"), 0) + 1
        title = (card.get("title") or "").strip()[:22] or "(无标题)"
        state = st.get("state")
        if state == "拍板中":
            rows["human"].append(f"{cid} {title}")
        elif state == "进行中":
            who = st.get("holder") or "?"
            mins = int((B.budget_status(cid, card).get("minutes") or 0))
            rows["doing"].append(f"{cid} {title}（{who} · {mins} 分钟）")
        elif state == "阻塞":
            why = (st.get("blocked_reason") or "").strip()[:26]
            rows["blocked"].append(f"{cid} {title}（{why or '未写原因'}）")
        elif state == "待返工":
            rows["doing_bad"].append(f"{cid} {title}")
        elif state == "待认领":
            rows["todo"].append(f"{cid} {title}")

    order = ["待认领", "进行中", "待返工", "阻塞", "待验收", "核验中", "拍板中", "完成"]
    bits = [f"{s} {counts[s]}" for s in order if counts.get(s)]
    print(f"   {total} 张：  " + " ｜ ".join(bits) + "\n")

    def _w(s: str) -> int:
        """显示宽度：中日韩字符算 2 列（否则标签永远对不齐）。"""
        return sum(2 if ord(ch) > 127 else 1 for ch in s)

    def line(label, items, limit=2):
        if not items:
            return
        head = "、".join(items[:limit])
        more = f" 等 {len(items)} 张" if len(items) > limit else ""
        print("   " + label + " " * max(0, 10 - _w(label)) + f"{head}{more}")

    line("等你拍板", rows["human"])
    line("正在做  ", rows["doing"])
    line("卡住了  ", rows["blocked"])
    line("要返工  ", rows["doing_bad"])
    line("还没人接", rows["todo"])

    # 只给一条「最该做的」；其余放一行短提示，不铺命令墙
    if rows["human"]:
        first = rows["human"][0].split()[0]
        print(f"\n   → 最该做的：{_board_cmd()} human {first} --decision approve")
        print(f"     先看样子：{_board_cmd()} show {first}")
    elif rows["blocked"]:
        first = rows["blocked"][0].split()[0]
        print(f"\n   → 先解开卡住的那张：{_board_cmd()} show {first}")
    elif rows["doing_bad"] or rows["todo"]:
        print(f"\n   → 让它自己跑：{_orch_cmd()} run --max 5")
    elif total and not (rows["doing"] or rows["blocked"]):
        print("\n   → 全部完成 🎉 下一步："
              f"{_board_cmd()} add --title \"要做什么\" --goal \"什么样算做完\"")
    print(f"\n   看板：{_board_cmd()} open --show ｜ 留言：{_board_cmd()} inbox"
          f" ｜ 说明：{_board_cmd()} help")
    print()


def cmd_stats(a):
    """各状态几张、完成率。"""
    if not B.card_ids():
        print("（看板为空）")
        return
    counts, total = {}, 0
    for d in B.card_refs():
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
        except Exception:
            continue
        total += 1
        counts[st["state"]] = counts.get(st["state"], 0) + 1
    print(f"项目：{B.ROOT.name}  （{B.ROOT}）")
    if a.workspace:
        print(f"工作区：{B.WORKSPACE}")
    print(f"共 {total} 张卡\n")
    for s in B.STATES:
        n = counts.get(s, 0)
        if n:
            print(f"  {s:<6} {n:>3}  {'█' * min(n, 30)}")
    if total:
        done = counts.get("完成", 0)
        print(f"\n完成率 {done}/{total} = {done / total * 100:.0f}%")


def cmd_cost(a):
    """用量统计：token + 缓存 + 花费。只统计引擎真的报了数的（⛔ 不假装 0）。"""
    if not B.card_ids():
        print("（看板为空）")
        return

    def newagg():
        return {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0,
                "cache_write": 0, "cost": 0.0, "calls": 0, "unavailable": 0}

    total = newagg()
    by_card, by_model = {}, {}

    for d in B.card_refs():
        if not d.is_dir():
            continue
        for ev in B.load_journal(d.name):
            if ev.get("type") != "usage":
                continue
            u = ev.get("usage") or {}
            key_card = d.name
            key_model = ev.get("model") or ev.get("engine") or "?"
            for bucket, key in ((by_card, key_card), (by_model, key_model)):
                a_ = bucket.setdefault(key, newagg())
                if not u.get("available"):
                    a_["unavailable"] += 1
                    a_["calls"] += 1
                    continue
                for f in ("input", "output", "reasoning", "cache_read", "cache_write"):
                    a_[f] += int(u.get(f) or 0)
                a_["cost"] += float(u.get("cost") or 0)
                a_["calls"] += 1
            if u.get("available"):
                for f in ("input", "output", "reasoning", "cache_read", "cache_write"):
                    total[f] += int(u.get(f) or 0)
                total["cost"] += float(u.get("cost") or 0)
                total["calls"] += 1
            else:
                total["unavailable"] += 1
                total["calls"] += 1

    def line(label, a_):
        cache = a_["cache_read"] + a_["cache_write"]
        return (f"{label:<22} {a_['calls']:>4} 次  "
                f"入 {a_['input']:>9,}  出 {a_['output']:>8,}  "
                f"缓存 {cache:>9,}  花费 ${a_['cost']:.4f}")

    print(f"项目：{B.ROOT.name}")
    print()
    if not total["calls"]:
        print("  还没有用量记录（跑过编排器后才有）")
        return
    print(line("合计", total))
    if total["unavailable"]:
        print(f"  ⚠ {total['unavailable']} 次调用引擎没报用量（已标『未知』，未计入 0）")
    print()
    print("按模型：")
    for k, v in sorted(by_model.items(), key=lambda x: -x[1]["input"]):
        print("  " + line(k[-40:], v))
    if a.per_card:
        print()
        print("按卡片：")
        for k, v in sorted(by_card.items(), key=lambda x: -x[1]["input"]):
            print("  " + line(k, v))


def cmd_inbox(a):
    """拍板收件箱：只列等你处理的卡，用人话说清 + 给可复制命令。

    设计（依据 opus 评审建议）：
      · 一次最多列 3 张（人的带宽），其余折叠成一行提示
      · 每张给：做了什么 / 证据数字 / 花费 / 建议 / 一行命令
      · 驳回必须带理由，理由会传回下一轮返工
    """
    if not B.card_ids():
        print("（看板为空）")
        return
    waiting = []
    for d in B.card_refs():
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
            card = B.get_card(d.name)
        except Exception:
            continue
        if st["state"] == "拍板中":
            waiting.append((st, card))

    if not waiting:
        # 没有待拍板，给一句正面的
        print("✓ 没有待你拍板的卡")
        pending = []
        for d in B.card_refs():
            if not d.is_dir():
                continue
            try:
                s = B.replay(d.name)["state"]
            except Exception:
                continue
            if s in ("待认领", "待返工", "进行中"):
                pending.append(d.name)
        if pending:
            print(f"  但有 {len(pending)} 张在跑或待跑：{' '.join(pending[:6])}")
            print("  让它自己跑：" + _orch_cmd() + " run --max 5")
        return

    limit = a.limit
    print(f"\n📥 待你拍板：{len(waiting)} 张\n")

    for i, (st, card) in enumerate(waiting[:limit], 1):
        cid = st["id"]
        ev = _inbox_evidence(cid)
        print(f"{'─' * 66}")
        print(f"[{i}] {cid}  {st['title']}")
        print(f"{'─' * 66}")

        if card.get("goal"):
            print(f"  目标    {card['goal'][:70]}")

        # 做了什么
        sub = st.get("submit") or {}
        if sub.get("note"):
            print(f"  执行    {sub['note'][:70]}")

        # 交付物 + 证据数字
        files = ev.get("files") or []
        if files:
            print("  产出    " + "；".join(
                f"{f['path']}({f.get('bytes', '?')}B)" for f in files[:3]))

        # 门禁
        gate = sub.get("gate") or {}
        gmark = "✓" if not gate.get("problems") else "✗"
        print(f"  门禁    {gmark} L1-L3 "
              f"{'全过' if not gate.get('problems') else '有未决问题'}")

        # 复核
        rev = st.get("review") or {}
        if rev:
            print(f"  复核    {rev.get('verdict')} by {rev.get('seat')}")
            if rev.get("evidence"):
                print(f"  凭据    {str(rev['evidence'])[:66]}")

        # 花费
        u = ev.get("usage") or {}
        if u.get("available"):
            print(f"  花费    ${u.get('cost', 0):.4f}  "
                  f"（入 {u.get('input', 0):,} / 出 {u.get('output', 0):,}）")
        elif u:
            print("  花费    引擎未报用量")

        # 建议
        rec, why = _inbox_recommend(st, gate, rev)
        print(f"\n  建议    {rec} —— {why}")
        print(f"  批准    {_board_cmd()} human {cid} --decision approve --who owner")
        print(f"  驳回    {_board_cmd()} human {cid} --decision reject --who owner "
              f"--note \"要改什么\"")

    rest = len(waiting) - limit
    if rest > 0:
        print(f"\n（还有 {rest} 张未列；一次只看 {limit} 张，处理完再跑一次 inbox）")
    print()


def _inbox_evidence(cid: str) -> dict:
    """从 journal 抽出给上面用的证据数字。"""
    out = {"files": [], "usage": {}}
    for ev in B.load_journal(cid):
        if ev.get("type") == "submit":
            gate = ev.get("gate") or {}
            out["files"] = gate.get("files") or []
            out["exit_note"] = ev.get("exit_code_note")
        elif ev.get("type") == "usage":
            u = ev.get("usage") or {}
            agg = out.setdefault("usage_all", {"input": 0, "output": 0, "cost": 0.0,
                                               "available": False})
            if u.get("available"):
                agg["input"] += int(u.get("input") or 0)
                agg["output"] += int(u.get("output") or 0)
                agg["cost"] += float(u.get("cost") or 0)
                agg["available"] = True
    if out.get("usage_all"):
        out["usage"] = out["usage_all"]
    return out


def _inbox_recommend(st: dict, gate: dict, rev: dict) -> tuple:
    """给一句建议 + 理由。⛔ 不替人下结论，只把判断依据摆出来。"""
    probs = gate.get("problems") or []
    if probs:
        return "驳回", f"门禁有未决问题（{probs[0][:40]}）"
    if rev.get("verdict") != "pass":
        return "驳回", "复核未通过"
    if not (rev.get("evidence") or "").strip():
        return "先别批", "复核没留凭据，建议自己看一眼产出"
    return "批准", "门禁全过 + 异会话复核通过且有凭据"


def cmd_doctor(a):
    """项目体检 + 安全清理。让『保持整洁』可复跑，不靠人记。"""
    import projects as P
    findings = []          # (级别, 描述, 可自动修?)
    fixable = []

    # 1) 注册表指向不存在的项目
    for p in P.list_projects():
        if not Path(p["path"]).exists():
            findings.append(("✗", f"注册表里的项目不存在：{p['name']} → {p['path']}", True))
            fixable.append(("registry", p))

    # 2) 卡片逐张查
    n_cards = 0
    for d in B.card_refs():
        if not d.is_dir():
            continue
        n_cards += 1
        cid = d.name

        # 2.1 哈希链
        ok_chain, why = B.verify_chain(cid)
        if not ok_chain:
            findings.append(("✗", f"{cid}: 哈希链有问题 —— {why}", False))

        # 2.2 坏行日志
        if (d / "journal.corrupt").exists():
            findings.append(("!", f"{cid}: 有 journal.corrupt（曾出现坏行）", False))

        # 2.3 残留/超时租约
        lease = B.active_lease(cid)
        if lease:
            owner = B._lease_owner(lease)
            age = (B.now_ms() - owner.get("at_ms", 0)) / 1000 if owner.get("at_ms") else 0
            st = B.replay(cid)
            if st["state"] in ("完成", "已取消"):
                findings.append(("!", f"{cid}: 已完成却还有活跃租约", True))
                fixable.append(("lease", cid))
            elif age > B.LEASE_TTL:
                findings.append(("!", f"{cid}: 租约 {int(age)}s 无心跳（超时未回收）", True))
                fixable.append(("lease", cid))

        # 2.4 旧格式租约目录名（破坏原子性）
        lroot = d / "lease" / "active"
        if lroot.exists():
            for x in lroot.iterdir():
                if x.is_dir() and x.name != B.LEASE_NAME:
                    findings.append(("✗", f"{cid}: 旧式租约目录「{x.name}」"
                                          f"（原子性不成立，需人工确认）", False))

        # 2.5 完成但交付物丢了
        try:
            st = B.replay(cid)
            card = B.get_card(d.name)
        except Exception:
            findings.append(("✗", f"{cid}: card.json 读不了", False))
            continue
        if st["state"] == "完成":
            for item in card.get("deliverables", []):
                rel = item if isinstance(item, str) else item.get("path")
                p = (B.WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
                if not p.exists():
                    findings.append(("!", f"{cid}: 已完成但交付物丢了 {rel}", False))

        # 2.6 证据层级：完成卡若只有「复核席表态」，不算已验证（D-023）
        if st["state"] == "完成":
            try:
                tier = B.evidence_tier(cid, st)
            except Exception:
                tier = "UNVERIFIED"
            if tier == "AUDITED-UNGROUNDED":
                findings.append(("!", f"{cid}: 完成但证据层级＝AUDITED-UNGROUNDED"
                                      f"（只有复核表态、没有机器闸；⛔ 对外不得称「已验证」）", False))
            elif tier == "UNVERIFIED":
                findings.append(("!", f"{cid}: 完成但证据层级＝UNVERIFIED（无机器证据）", False))

        # 2.7 租约与事件流对账：活跃租约的持有者必须是最后一次 claim 的席位
        lease2 = B.active_lease(cid)
        if lease2:
            holder = (B._lease_owner(lease2) or {}).get("seat")
            claims = [e.get("seat") for e in B.load_journal(cid) if e.get("type") == "claim"]
            if claims and holder and claims[-1] != holder:
                findings.append(("✗", f"{cid}: 租约持有者「{holder}」≠ 最后一次认领「{claims[-1]}」"
                                      f"（库与事件流对不上）", False))

    # 3) 孤立 worktree
    wt_base = B.WORKSPACE / ".worktrees"
    if wt_base.exists():
        for w in wt_base.iterdir():
            if w.is_dir():
                cid = w.name
                d = B.card_ref(cid)
                if not d.exists():
                    findings.append(("!", f"孤立 worktree：{cid}（卡片已不存在）", True))
                    fixable.append(("worktree", cid))
                else:
                    try:
                        if B.replay(cid)["state"] in ("完成", "已取消"):
                            findings.append(("!", f"残留 worktree：{cid}（卡已完成）", True))
                            fixable.append(("worktree", cid))
                    except Exception:
                        pass
            elif w.name.endswith(".baseline.json"):
                pass

    # 4) 输出
    print(f"项目：{B.ROOT.name}")
    print(f"工作区：{B.WORKSPACE}")
    print(f"卡片：{n_cards} 张\n")

    if not findings:
        print("✓ 体检干净，没有发现问题")
        return

    for lvl, desc, can in findings:
        tag = "（可自动修）" if can else "（需人工看）"
        print(f"  {lvl} {desc} {tag if can else ''}")

    auto = [f for f in findings if f[2]]
    print(f"\n共 {len(findings)} 项，其中 {len(auto)} 项可自动修")

    if a.fix:
        if not auto:
            print("没有可自动修的项")
            return
        print("\n开始清理：")
        done = 0
        for kind, obj in fixable:
            try:
                if kind == "worktree":
                    import parallel as PL
                    PL.remove(obj)
                    print(f"  · 删除 worktree：{obj}")
                elif kind == "lease":
                    lease = B.active_lease(obj)
                    if lease:
                        B._reclaim_lease(obj, lease, reason="doctor 清理")
                        print(f"  · 回收租约：{obj}")
                elif kind == "registry":
                    P.remove_project(obj["name"])
                    print(f"  · 移除注册表条目：{obj['name']}")
                done += 1
            except Exception as e:
                print(f"  ✗ {kind} {obj}: {e}")
        print(f"\n已清理 {done} 项")
    else:
        print("\n加 --fix 自动清理可修项")


def cmd_rm(a):
    """删卡（人类操作，需 --yes）。⛔ 只删本项目的卡，不碰交付物文件。"""
    a.id = B.check_card_id(a.id)     # ⚠️ 卡号进路径（rmtree），先钉死形状（安全扫描 F-02）
    card = B.get_card(a.id)
    if not card:
        B.die(f"卡片不存在：{a.id}")
    if not a.yes:
        print(f"要删：{a.id}  {card.get('title')}")
        print(f"  加 --yes 确认。⛔ 交付物文件不会被删除")
        return
    st = B._store()
    with st.write() as c:
        c.execute("DELETE FROM events WHERE card_id=?", (a.id,))
        c.execute("DELETE FROM leases WHERE card_id=?", (a.id,))
        c.execute("DELETE FROM cards WHERE id=?", (a.id,))
    ev = st.evidence_dir / a.id
    if ev.exists():
        import shutil as _sh
        _sh.rmtree(ev, ignore_errors=True)
    B.ok(f"已删除：{a.id}")


def cmd_all(a):
    """跨项目总览（团队视角）：一眼看几十个项目的状态。"""
    import projects as P
    ps = P.project_summary(use_cache=not a.refresh)
    if not ps:
        print("（还没有登记任何项目）")
        print(f"  注册表：{P.REGISTRY_DB}")
        return

    order = ["待认领", "进行中", "待返工", "阻塞", "待验收", "核验中", "拍板中", "完成"]
    tot = {"cards": 0}
    print(f"{'项目':<22} {'卡':>4}  " + " ".join(f"{s[:2]:>3}" for s in order))
    print("-" * 78)
    for p in sorted(ps, key=lambda x: x["name"]):
        st = p.get("states") or {}
        cells = " ".join(f"{st.get(s,0):>3}" for s in order)
        mark = "" if p.get("ok") else "  ⚠"
        print(f"{p['name'][:20]:<22} {p.get('cards',0):>4}  {cells}{mark}")
        tot["cards"] += p.get("cards", 0)
        for s in order:
            tot[s] = tot.get(s, 0) + st.get(s, 0)
    print("-" * 78)
    print(f"{'合计':<22} {tot['cards']:>4}  " + " ".join(f"{tot.get(s,0):>3}" for s in order))
    print(f"\n共 {len(ps)} 个项目 ｜ 注册表：{P.REGISTRY_DB}")
    if tot.get("拍板中"):
        print(f"⚠ {tot['拍板中']} 张等你拍板：{_board_cmd()} inbox --all")


def cmd_inbox_all(a):
    """跨项目收件箱：把所有项目里等你拍板的卡汇总。"""
    import projects as P
    old_root = B.ROOT
    rows = []
    try:
        for p in P.list_projects():
            if not p.get("exists"):
                continue
            B.set_root(p["path"])
            for cid in B.card_ids():
                st = B.replay(cid)
                if st["state"] == "拍板中":
                    rows.append((p["name"], cid, st, B.get_card(cid)))
    finally:
        B.set_root(old_root)

    if not rows:
        print("✓ 所有项目都没有待你拍板的卡")
        return
    print(f"\n📥 全部项目待拍板：{len(rows)} 张\n")
    for i, (pname, cid, st, card) in enumerate(rows[:a.limit], 1):
        print(f"{'─'*62}")
        print(f"[{i}] {pname} / {cid}  {st['title']}")
        print(f"    目标  {(card or {}).get('goal','')[:60]}")
        print(f"    批准  {_board_cmd()} -p {pname} human {cid} --decision approve --who owner")
        print(f"    驳回  {_board_cmd()} -p {pname} human {cid} --decision reject --who owner --note \"...\"")
    rest = len(rows) - a.limit
    if rest > 0:
        print(f"\n（还有 {rest} 张未列；--limit 调整）")


def cmd_open(a):
    """打开/刷新看板页。最常用的一条命令。"""
    cmd_html(a)
    out = B.BOARD / "board.html"
    print(f"\n  {out}")
    if a.show:
        try:
            import webbrowser
            webbrowser.open(out.as_uri())
        except Exception:
            pass


# ---------- 跨会话留言（吸收 ocs 语义）----------

def _seat_default():
    return (os.environ.get("ABOARD_SEAT") or "").strip() or "human"


def cmd_msg(a):
    """跨会话留言：send / ls / inbox / ack / thread / wake。"""
    import messages as M

    st = B._store()
    sender = (a.sender or "").strip() or _seat_default()
    act = a.action

    if act == "send":
        body = a.body or ""
        if body == "-":
            body = sys.stdin.read()
        if not body.strip():
            B.die("正文空了（--body \"...\" 或 --body - 从标准输入读）")
        meta = {}
        if a.wake:
            for k, v in (("wake_engine", a.wake_engine),
                         ("wake_model", a.wake_model),
                         ("wake_session", a.wake_session)):
                if v:
                    meta[k] = v
            meta["wake_cwd"] = str(B.WORKSPACE)
        try:
            msg = M.send(st, sender, a.to, body, kind=a.kind,
                         reply_to=a.reply_to, meta=meta)
        except ValueError as e:
            B.die(str(e))
        if not a.wake:
            if a.json:
                print(M.dumps(msg))
            else:
                B.ok(f"已存为 #{msg['seq']}：{sender} → {a.to}"
                     + (f"（回复 #{a.reply_to}）" if a.reply_to else ""))
            return 0
        state, detail = M.wake(st, msg["seq"], engine=a.wake_engine,
                               model=a.wake_model, session=a.wake_session,
                               force=a.force)
        if a.json:
            # ⚠️ 2026-10-20 修（Q1 #9）：以前 --json --wake 会先打一段 JSON、再打一行「唤醒：…」，
            #    调用方 json.loads 直接炸。现在**整个输出是一个 JSON 对象**，唤醒结果放 wake 字段。
            out = dict(msg)
            out["wake"] = {"state": state, "detail": detail}
            print(json.dumps(out, ensure_ascii=False))
        else:
            B.ok(f"已存为 #{msg['seq']}：{sender} → {a.to}"
                 + (f"（回复 #{a.reply_to}）" if a.reply_to else ""))
            print(f"  唤醒：{state} ｜ {detail}")
        if state == M.ST_DISPATCHED:
            return 0
        return M.EXIT_HELD if state == M.ST_HELD else M.EXIT_ERROR

    if act == "ls":
        msgs = st.messages(to=a.to, frm=a.sender, limit=a.limit, since=a.since)
        if a.json:
            print(json.dumps(msgs, ensure_ascii=False))
            return 0
        if not msgs:
            print("（没有留言）")
            return 0
        read = st.read_seqs(a.as_seat) if a.as_seat else None
        for m in msgs:
            print(M.fmt(m, reader=a.as_seat, read_seqs=read))
        return 0

    if act == "inbox":
        me = a.as_seat or _seat_default()
        picked, total = M.inbox(st, me, limit=a.limit, ack=not a.no_ack,
                               only_unread=not a.all)
        if a.json:
            print(json.dumps({"as": me, "unread": picked, "total": total},
                             ensure_ascii=False))
            return 0
        if not picked:
            if not a.quiet:
                print(f"✓ {me} 没有新留言（共 {total} 条）")
            return 0
        print(f"📬 {me} 的留言：{len(picked)} 条新（共 {total} 条）")
        for m in picked:
            print(f"{'─'*60}")
            print(M.fmt(m))
        if not a.no_ack:
            print(f"\n（已标记为已读：{len(picked)} 条）")
        return 0

    if act == "ack":
        me = a.as_seat or _seat_default()
        if not a.seq:
            B.die("ack 要给留言号：board msg ack 12")
        m = st.message(int(a.seq))
        if not m:
            B.die(f"留言不存在：#{a.seq}")
        fresh = st.mark_read(int(a.seq), me)
        B.ok(f"#{a.seq} 已标记为 {me} 已读" + ("" if fresh else "（本来就已读）"))
        return 0

    if act == "thread":
        line = M.thread(st, int(a.seq or 0))
        if not line:
            B.die(f"留言不存在：#{a.seq}")
        for m in line:
            print(M.fmt(m))
            print()
        return 0

    if act == "wake":
        if not a.seq:
            B.die("wake 要给留言号：board msg wake 12")
        state, detail = M.wake(st, int(a.seq), engine=a.wake_engine,
                               model=a.wake_model, session=a.wake_session,
                               force=a.force)
        print(f"  唤醒：{state} ｜ {detail}")
        return 0 if state == M.ST_DISPATCHED else (
            M.EXIT_HELD if state == M.ST_HELD else M.EXIT_ERROR)

    if act == "states":
        rows = st.wakes(int(a.seq) if a.seq else None)
        if not rows:
            print("（还没有唤醒记录）")
        for r in rows:
            print(f"#{r['seq']:<4} {r['state']:<10} {r['at'][:19]}  {r['detail'][:70]}")
        return 0

    B.die(f"未知动作：{act}")


def main():
    p = argparse.ArgumentParser(
        prog="board",
        description="单人用的多 agent 编排看板（多项目）",
        epilog="最常用：board ls ｜ board open ｜ board add --title ... ｜ board human <卡号>")
    p.add_argument("-C", "--root", help="指定项目目录（默认从当前目录向上找）")
    p.add_argument("-p", "--project", help="按注册表里的项目名切换")
    sub = p.add_subparsers(dest="cmd", required=False)

    s = sub.add_parser("init", help="初始化看板")
    s.set_defaults(f=cmd_init)

    s = sub.add_parser("project", help="项目管理：add / ls / rm / default")
    s.add_argument("action", choices=["add", "ls", "rm", "default"])
    s.add_argument("path", nargs="?")
    s.add_argument("--name")
    s.add_argument("--engine")
    s.add_argument("--model")
    s.add_argument("--effort")
    s.add_argument("--max-cost", dest="max_cost", type=str, default=None,
                   help="新卡默认花费上限（美元）；none＝取消默认")
    s.add_argument("--max-minutes", dest="max_minutes", type=str, default=None,
                   help="新卡默认时长上限（分钟）；none＝取消默认")
    s.add_argument("--workspace", help="指定 agent 干活的工作区（默认＝项目根）")
    s.set_defaults(f=cmd_project)

    s = sub.add_parser("stats", help="一眼看数字")
    s.add_argument("--workspace", action="store_true", help="同时显示工作区")
    s.set_defaults(f=cmd_stats)

    s = sub.add_parser("rm", help="删卡（需 --yes）")
    s.add_argument("id")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(f=cmd_rm)

    s = sub.add_parser("cost", help="用量统计（token/缓存/花费）")
    s.add_argument("--per-card", action="store_true", help="按卡片细分")
    s.set_defaults(f=cmd_cost)

    s = sub.add_parser("open", help="生成并打开看板页（最常用）")
    s.add_argument("--show", action="store_true", help="生成后自动用浏览器打开")
    s.set_defaults(f=cmd_open)

    s = sub.add_parser("do", help="一句话建卡并立刻跑（add + run 合成一步）")
    s.add_argument("text", help='要做的事，例如 "把第 3 章译成英文"')
    s.add_argument("--goal", help="什么样算做完（默认就用上面那句话）")
    s.add_argument("--deliverable", nargs="*", help="交付物路径")
    s.add_argument("--human-gate", default="none",
                   choices=["none", "before_done", "both"], help="人闸档位")
    s.add_argument("--engine", default="any",
                   help="指定 agent 框架：codex/opencode/qoderclicn/hermes/any")
    s.add_argument("--model", default=None)
    s.add_argument("--seat", default="auto-worker")
    s.add_argument("--check-cmd",
                   help="提交时必跑的外部闸门命令（非零即不过）；只对人建的卡生效")
    s.add_argument("--no-run", action="store_true", help="只建卡，不立刻跑")
    s.set_defaults(f=cmd_do)

    s = sub.add_parser("add", help="建卡（人建，等价于 new）")
    s.add_argument("--title", required=True)
    s.add_argument("--goal")
    s.add_argument("--territory", nargs="*", help="可写领地（路径）")
    s.add_argument("--deliverable", nargs="*", help="交付物路径")
    s.add_argument("--accept", nargs="*", help="L3 必含项（正则）")
    s.add_argument("--human-gate", default="none",
                   choices=["none", "before_done", "both"], help="人闸档位")
    s.add_argument("--irreversible", action="store_true", help="不可逆动作类（建议强制人闸）")
    s.add_argument("--engine", default="any",
                   help="指定 agent 框架：codex/opencode/qoderclicn/hermes/any")
    s.add_argument("--model", default="any", help="指定模型（如 deepseek-v4.1-flash）")
    s.add_argument("--effort", default="any",
                   help="思考强度：low/medium/high/max/any")
    s.add_argument("--check-cmd",
                   help="提交时必跑的外部闸门命令（非零即不过）；只对人建的卡生效")
    s.add_argument("--max-cost", dest="max_cost", type=str, default=None,
                   help="单卡花费上限（美元，如 2.0）；超了编排器停下转阻塞")
    s.add_argument("--max-minutes", dest="max_minutes", type=str, default=None,
                   help="单卡引擎时长上限（分钟）；超了停下转阻塞")
    s.add_argument("--blocked-by", dest="blocked_by", nargs="*", default=None,
                   help="卡间依赖：这些卡没完成之前不许接")
    s.add_argument("--escalate-model", dest="escalate_model", default=None,
                   help="返工到阈值后换这个更强模型（外问升级；⛔ 不是让它自己判断）")
    s.add_argument("--escalate-after", dest="escalate_after", type=int, default=2,
                   help="第几次复核失败后升级模型（默认 2）")
    s.add_argument("--id")
    s.add_argument("--seat")
    s.set_defaults(f=cmd_new)

    # new 是 add 的别名（保持旧脚本可用）
    s = sub.add_parser("new", help="建卡（add 的别名）")
    s.add_argument("--title", required=True)
    s.add_argument("--goal")
    s.add_argument("--territory", nargs="*")
    s.add_argument("--deliverable", nargs="*")
    s.add_argument("--accept", nargs="*")
    s.add_argument("--human-gate", default="none",
                   choices=["none", "before_done", "both"])
    s.add_argument("--irreversible", action="store_true")
    s.add_argument("--engine", default="any")
    s.add_argument("--model", default="any")
    s.add_argument("--effort", default="any")
    s.add_argument("--max-cost", dest="max_cost", type=str, default=None)
    s.add_argument("--max-minutes", dest="max_minutes", type=str, default=None)
    s.add_argument("--blocked-by", dest="blocked_by", nargs="*", default=None)
    s.add_argument("--escalate-model", dest="escalate_model", default=None)
    s.add_argument("--escalate-after", dest="escalate_after", type=int, default=2)
    s.add_argument("--id")
    s.add_argument("--seat")
    s.set_defaults(f=cmd_new)

    s = sub.add_parser("publish", help="AI 发布任务（必须带 --seat）")
    s.add_argument("--title", required=True)
    s.add_argument("--goal")
    s.add_argument("--territory", nargs="*")
    s.add_argument("--deliverable", nargs="*")
    s.add_argument("--accept", nargs="*")
    s.add_argument("--human-gate", default="none",
                   choices=["none", "before_done", "both"])
    s.add_argument("--irreversible", action="store_true")
    s.add_argument("--engine", default="any")
    s.add_argument("--model", default="any")
    s.add_argument("--effort", default="any")
    s.add_argument("--max-cost", dest="max_cost", type=str, default=None)
    s.add_argument("--max-minutes", dest="max_minutes", type=str, default=None)
    s.add_argument("--blocked-by", dest="blocked_by", nargs="*", default=None)
    s.add_argument("--id")
    s.add_argument("--seat", required=True, help="发布者身份（不可匿名）")
    s.add_argument("--from-card", help="由哪张卡派生")
    s.set_defaults(f=cmd_publish)

    s = sub.add_parser("ready", help="找我能干的活（按引擎/模型/思考强度匹配）")
    s.add_argument("--engine", default=None)
    s.add_argument("--model", default=None)
    s.add_argument("--effort", default=None)
    s.set_defaults(f=cmd_ready)

    s = sub.add_parser("ls", help="列卡")
    s.add_argument("--state")
    s.set_defaults(f=cmd_ls)

    s = sub.add_parser("show", help="看一张卡")
    s.add_argument("id")
    s.add_argument("--events", action="store_true")
    s.set_defaults(f=cmd_show)

    s = sub.add_parser("claim", help="认领（原子 + 规格匹配）")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--engine", default="any")
    s.add_argument("--model", default=None)
    s.add_argument("--effort", default=None)
    s.set_defaults(f=cmd_claim)

    s = sub.add_parser("budget", help="看/改单卡预算与依赖（放宽只能人来做）")
    s.add_argument("id")
    s.add_argument("--max-cost", dest="max_cost", type=str, default=None,
                   help="花费上限（美元）；none＝取消上限（仅 human）")
    s.add_argument("--max-minutes", dest="max_minutes", type=str, default=None,
                   help="引擎时长上限（分钟）；none＝取消上限（仅 human）")
    s.add_argument("--blocked-by", dest="blocked_by", nargs="*", default=None)
    s.add_argument("--unblock", action="store_true", help="清空依赖（要人令牌）")
    s.add_argument("--seat", default=None, help="席位名（⛔ 单写 human 不再等于「人」）")
    s.add_argument("--who", default=None, help="人令牌对应的 who（放宽/去依赖时要）")
    s.set_defaults(f=cmd_budget)

    s = sub.add_parser("beat", help="心跳")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--epoch", type=int, default=None,
                   help="租约编号（认领时打印）；带了就做栅栏校验")
    s.set_defaults(f=cmd_beat)

    s = sub.add_parser("block", help="报阻塞")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(f=cmd_block)

    s = sub.add_parser("submit", help="提交（自动跑 L1-L3）")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--note")
    s.add_argument("--epoch", type=int, default=None,
                   help="租约编号（认领时打印）；带了就做栅栏校验，防止被回收后旧进程写回")
    s.set_defaults(f=cmd_submit)

    s = sub.add_parser("verify", help="复核席跑机器闸")
    s.add_argument("id")
    s.add_argument("--seat")
    s.set_defaults(f=cmd_verify)

    s = sub.add_parser("consult", help="点对点评审：B1/B2 独立提意见（只准看、不准改）")
    s.add_argument("id")
    s.add_argument("--by", required=True,
                   help='评审席，逗号分隔：seat[:engine[:model[:effort]]]，'
                        '如 "b1:opencode:claudecodesale/claude-opus-5-5,b2:qoderclicn:"')
    s.add_argument("--q", default="", help="这一轮要评审席回答什么")
    s.add_argument("--role", default="generic",
                   choices=["generic", "native", "term", "faithful"],
                   help="评审角度：通用/母语读感/术语一致/逐句对照")
    s.add_argument("--file", action="append", help="评审哪些文件（默认用卡里的 deliverables）")
    s.add_argument("--round", type=int, default=1)
    s.add_argument("--parallel", type=int, default=3)
    s.add_argument("--timeout", type=int, default=900)
    s.add_argument("--dry-run", action="store_true", help="只打印提示词，不调模型")
    s.set_defaults(f=cmd_consult)

    s = sub.add_parser("review", help="复核结论（必须异会话 + 带凭据）")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--verdict", required=True, choices=["pass", "fail"])
    s.add_argument("--evidence", required=True,
                   help="你实际跑的命令与读数（必须有数字，反空跑）")
    s.add_argument("--note")
    s.add_argument("--item", action="append", default=[], metavar="ID:open|fixed:说明",
                   help="逐条意见（可重复）：ID 是稳定编号，下一轮复核要按同一 ID 回报状态")
    s.add_argument("--items-file",
                   help="意见 JSON 文件：[{\"id\":\"T1\",\"state\":\"open\",\"text\":\"…\"}]")
    s.add_argument("--force", action="store_true",
                   help="同一条意见连续 3 轮未解决时，显式允许再转一轮（会记进事件）")
    s.set_defaults(f=cmd_review)

    s = sub.add_parser("human", help="人拍板（需 token）")
    s.add_argument("id")
    s.add_argument("--decision", required=True, choices=["approve", "reject"])
    s.add_argument("--who")
    s.add_argument("--note")
    s.set_defaults(f=cmd_human)

    s = sub.add_parser("token", help="人令牌登记（首用必做；只存哈希）")
    s.add_argument("--init", action="store_true", help="把当前令牌登记为基准哈希")
    s.add_argument("--who", default=None)
    s.set_defaults(f=cmd_token)

    s = sub.add_parser("reclaim", help="回收超时租约")
    s.set_defaults(f=cmd_reclaim)

    s = sub.add_parser("audit", help="查绕过痕迹")
    s.set_defaults(f=cmd_audit)

    s = sub.add_parser("doctor", help="🩺 体检 + 安全清理")
    s.add_argument("--fix", action="store_true", help="自动清理可修项")
    s.set_defaults(f=cmd_doctor)

    s = sub.add_parser("html", help="生成看板页")
    s.set_defaults(f=cmd_html)

    s = sub.add_parser("overview", help="跨项目总览页")
    s.set_defaults(f=cmd_overview)

    s = sub.add_parser("inbox", help="📥 拍板收件箱（只看等你处理的）")
    s.add_argument("--limit", type=int, default=3, help="一次最多列几张（默认 3）")
    s.add_argument("--all", action="store_true", help="汇总所有项目")
    s.set_defaults(f=cmd_inbox)

    s = sub.add_parser("all", help="🌐 跨项目总览（团队视角）")
    s.add_argument("--refresh", action="store_true", help="跳过缓存重新扫描")
    s.set_defaults(f=cmd_all)

    s = sub.add_parser("msg", help="💬 跨会话留言（send/ls/inbox/ack/thread/wake）")
    s.add_argument("action", choices=["send", "ls", "inbox", "ack", "thread",
                                      "wake", "states"])
    s.add_argument("seq", nargs="?", help="留言号（ack/thread/wake/states 用）")
    s.add_argument("--to", help="收件人（席号/会话名/human）")
    s.add_argument("--body", help="正文；写 - 则从标准输入读")
    s.add_argument("--from", dest="sender", help="发件人（默认取 ABOARD_SEAT 或 human）")
    s.add_argument("--as", dest="as_seat", help="以谁的身份收/标已读（inbox/ack/ls）")
    s.add_argument("--reply-to", type=int, help="回复哪一条（留言号）")
    s.add_argument("--kind", default="note", choices=["note", "ask", "answer", "wake"])
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--since", type=int, help="只看比这个号新的")
    s.add_argument("--all", action="store_true", help="inbox 连已读一起列")
    s.add_argument("--no-ack", action="store_true", help="inbox 只读不标已读")
    s.add_argument("--quiet", action="store_true", help="inbox 没新留言时不吭声")
    s.add_argument("--json", action="store_true", help="机器可读输出")
    s.add_argument("--wake", action="store_true",
                   help="存完立刻唤醒对方（需要 --wake-session）")
    s.add_argument("--wake-engine", help="唤醒用哪个引擎（opencode/qoderclicn/…）")
    s.add_argument("--wake-model", help="唤醒用哪个模型")
    s.add_argument("--wake-session", help="唤醒要续接的会话 ID")
    s.add_argument("--force", action="store_true", help="wake 允许重发（默认不重发）")
    s.set_defaults(f=cmd_msg)

    a = p.parse_args()

    # 多项目解析：--root > --project > 自动向上找 > 当前目录
    import projects as P
    if a.project:
        entry = P.find_project(a.project)
        if not entry:
            B.die(f"没找到项目「{a.project}」。用 board project ls 看已登记的")
        if not Path(entry["path"]).exists():
            B.die(f"项目目录不存在：{entry['path']}")
        root = Path(entry["path"])
    else:
        root = P.resolve_root(a.root)

    B.set_root(root)
    P.ensure_root(root)
    # 项目工作区：注册表里设了就切过去（agent 在这里干活）
    B.set_workspace(P.workspace_of(root))
    if not a.cmd:
        return cmd_bare(a)
    if a.cmd == "inbox" and getattr(a, "all", False):
        return cmd_inbox_all(a)
    rc = a.f(a)
    if isinstance(rc, int) and rc:      # 留言的退出码分档：0/2/3（见 messages.py）
        sys.exit(rc)


if __name__ == "__main__":
    main()