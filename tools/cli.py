#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — 看板命令层

核心在 `board.py`。这里只放命令与参数解析。
⚠️ 一律通过 `B.xxx` 访问核心（含 ROOT/WORKSPACE/CARDS 这些**可变全局**，
   直接 import 名字会拿到切换项目前的旧值）。
"""
import argparse
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B                        # noqa: E402

# ---------- 命令 ----------

def cmd_init(a):
    B.CARDS.mkdir(parents=True, exist_ok=True)
    B.ok(f"看板已初始化：{B.BOARD}")


def cmd_new(a):
    B.CARDS.mkdir(parents=True, exist_ok=True)
    # 继承项目默认值：没指定就自动填，省掉手打模型名
    import projects as P
    defaults = P.project_defaults(B.ROOT) or {}
    eng = a.engine if a.engine and a.engine != "any" else defaults.get("engine", "any")
    mdl = a.model if a.model and a.model != "any" else defaults.get("model", "any")
    eft = a.effort if a.effort and a.effort != "any" else defaults.get("effort", "any")
    cid = a.id or f"C{datetime.now().strftime('%m%d')}-{uuid.uuid4().hex[:4]}"
    d = B.CARDS / cid
    if d.exists():
        B.die(f"卡片已存在：{cid}")
    d.mkdir(parents=True)
    (d / "artifacts").mkdir()
    (d / "evidence").mkdir()
    (d / "lease" / "active").mkdir(parents=True)
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
        "created_kind": "agent" if a.seat and a.seat != "human" else "human",
        "irreversible": bool(a.irreversible),
        "source_card": getattr(a, "from_card", None),
    }
    B.jwrite(d / "card.json", card)
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
    print(f"  {d}")


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
    if not B.CARDS.exists():
        print("（看板为空）")
        return
    hits = []
    for d in sorted(B.CARDS.iterdir()):
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
            card = B.jread(d / "card.json")
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
    if not B.CARDS.exists():
        print("（看板为空，先 board.py new）")
        return
    rows = []
    for d in sorted(B.CARDS.iterdir()):
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
        hold = r["holder"] or "-"
        mdl = (r["model"] if r["model"] != "any" else "-")[:20]
        print(f"{r['id']:<12} {r['state']:<7} {hold:<9} "
              f"{r['engine']:<10} {mdl:<22} {r['effort']:<6} {r['title'][:26]}")
    print(f"\n共 {len(rows)} 张")


def cmd_show(a):
    st = B.replay(a.id)
    card = B.jread(B.card_dir(a.id) / "card.json")
    print(f"\n【{st['id']}】{st['title']}")
    print(f"  状态    {st['state']}")
    print(f"  持有    {st['holder'] or '-'}")
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
    if card.get("goal"):
        print(f"  目标    {card['goal']}")
    if card.get("territory"):
        print(f"  领地    {', '.join(card['territory'])}")
    if card.get("deliverables"):
        print(f"  交付    {', '.join(card['deliverables'])}")
    if st["submit"]:
        print(f"  提交    {st['submit'].get('note','')}")
    if st["review"]:
        print(f"  复核    {st['review'].get('verdict')} by {st['review'].get('seat')}")
    print(f"  事件    {st['events']} 条")
    if a.events:
        print("\n  事件流：")
        for ev in B.load_journal(a.id):
            print(f"    {ev['seq']:>3} {ev['at'][11:19]} {ev['type']:<14} {ev.get('seat','')}")


def cmd_claim(a):
    B.claim(a.id, a.seat, a.engine, a.model, a.effort)
    B.ok(f"认领成功：{a.id} → {a.seat}")
    print(f"  引擎={a.engine} 模型={a.model or 'any'} 思考={a.effort or 'any'}")
    print(f"  ⚠ 每 {B.HB_INTERVAL}s 内至少跑一次 beat，否则 {B.LEASE_TTL}s 后被回收")


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


def guard_holder(cid: str, seat: str):
    """确认你是当前租约持有者，且 epoch 未被回收重置。

    防的是：长任务执行中租约超时被别人回收接手，旧执行者回来提交，
    把别人的活覆盖掉（opus 评审指出）。
    """
    lease = B.active_lease(cid)
    if not lease:
        B.die("你没有活跃租约（可能已被回收）")
    owner = B._lease_owner(lease)
    if owner.get("seat") != seat:
        B.die(f"卡片已归 {owner.get('seat')}（你的租约已被回收）")
    st = B.replay(cid)
    return st.get("epoch", 0)


def _lease_epoch(lease) -> int:
    try:
        return int(B._lease_owner(lease).get("epoch", 0))
    except Exception:
        return 0


def cmd_beat(a):
    B.heartbeat(a.id, a.seat)


def cmd_block(a):
    guard_transition(a.id, "阻塞", "agent")
    st = B.replay(a.id)
    if st["holder"] != a.seat:
        B.die(f"你不是持有者（当前 {st['holder']}）")
    B.append_event(a.id, {"type": "block", "actor": "agent", "seat": a.seat, "reason": a.reason})
    B.ok(f"已阻塞：{a.reason}")


def cmd_submit(a):
    st = B.replay(a.id)
    if st["holder"] != a.seat:
        B.die(f"你不是持有者（当前 {st['holder']}）")
    card = B.jread(B.card_dir(a.id) / "card.json")
    # 提交即跑 L1-L3
    ok1, p1, r1 = B.gate_l1(a.id, card)
    ok2, p2 = B.gate_l2(a.id, card)
    ok3, p3, c3 = B.gate_l3(a.id, card)
    problems = p1 + p2 + p3
    verdict = "pass" if (ok1 and ok2 and ok3) else "fail"
    B.append_event(a.id, {
        "type": "submit", "actor": "agent", "seat": a.seat, "note": a.note or "",
        "gate": {"L1": ok1, "L2": ok2, "L3": ok3, "problems": problems, "files": r1},
        "exit_code_note": "退出码不参与判定（权重 0）",
    })
    if verdict == "pass":
        B.ok("L1-L3 全过 → 待验收")
        for r in r1:
            print(f"  {r['path']}  {r.get('bytes','?')}B  B.sha8={r.get('B.sha8','-')}")
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
    card = B.jread(B.card_dir(a.id) / "card.json")
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


def cmd_review(a):
    guard_transition(a.id, "完成" if a.verdict == "pass" else "待返工", "review")
    st = B.replay(a.id)
    if st["state"] not in ("核验中", "待验收"):
        B.die(f"当前状态「{st['state']}」，不可复核")
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
    if st["gate"] in ("both", "before_done") and a.verdict == "pass":
        B.append_event(a.id, {"type": "review", "actor": "review", "seat": a.seat,
                            "verdict": a.verdict, "note": a.note or "",
                            "evidence": a.evidence, "evidence_ok": True})
        B.append_event(a.id, {"type": "request_human", "actor": "review", "seat": a.seat})
        B.release(a.id)
        B.ok("复核通过 → 已转「拍板中」，等人拍板")
        return
    B.append_event(a.id, {"type": "review", "actor": "review", "seat": a.seat,
                        "verdict": a.verdict, "note": a.note or "",
                        "evidence": a.evidence, "evidence_ok": True})
    if a.verdict == "pass":
        B.release(a.id)
        B.ok("复核 PASS → 完成")
    else:
        B.release(a.id)
        B.ok("复核 FAIL → 打回「进行中」")


def _check_evidence(ev: str) -> tuple:
    """复核凭据的最低可判标准：必须含命令、含数字读数。"""
    if len(ev.strip()) < 12:
        return False, "凭据太短（<12 字符），看不出你跑了什么"
    if not re.search(r"[A-Za-z_][\w\.\-]*", ev):
        return False, "凭据里没有可识别的命令/字段名"
    if not re.search(r"\d", ev):
        return False, "凭据里没有任何数字读数 —— 反空跑要求有非零计数"
    return True, ""


def human_token() -> Path:
    """人 token 放在看板目录之外，agent 指令里明令不碰。"""
    return Path.home() / ".board-human.tok"


def human_token_sha() -> Path:
    """令牌哈希存在看板里。只存哈希 ⇒ 读到它推不出原令牌。"""
    return B.BOARD / ".human-token.sha"


def _verify_human_token() -> tuple:
    """校验人令牌。返回 (B.ok, 原因)。

    防线（诚实标注：这是**提高门槛**，不是绝对强制，见 AGENTS.md §4.1）：
      1. 令牌文件必须存在且内容非空（⛔ 0 字节放行）
      2. 内容长度 ≥ 16（⛔ 一眼能猜的短串）
      3. 与首次登记时存的 sha256 一致（换令牌 = 留痕）
    """
    tok = human_token()
    if not tok.exists():
        return False, f"缺人令牌。首次使用请创建：{tok}（内容随意，⛔ 不要给 agent）"
    try:
        content = tok.read_text(encoding="utf-8").strip()
    except Exception as e:
        return False, f"人令牌读不了：{e}"
    if not content:
        return False, "人令牌是空的 —— ⛔ 空文件不算令牌（这是本条防线要防的）"
    if len(content) < 16:
        return False, f"人令牌太短（{len(content)} < 16 字符）—— 换一个长一点的"
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    reg = human_token_sha()
    if not reg.exists():
        return True, ""          # 首次登记，下方写入
    try:
        expected = reg.read_text(encoding="utf-8").strip()
    except Exception:
        return False, "令牌登记文件读不了"
    if sha != expected:
        return False, ("人令牌已变更（与登记哈希不符）。"
                       "若这是你本人换的，删掉 board/.human-token.sha 重新登记；否则是有人动了令牌")
    return True, ""


def cmd_human(a):
    # 红线②：唯一能推进人位的入口
    guard_transition(a.id, "完成" if a.decision == "approve" else "待返工", "human")
    ok_tok, why = _verify_human_token()
    if not ok_tok:
        B.die(why)
    # 首次登记令牌哈希（只存哈希，推不出原值）
    if not human_token_sha().exists():
        content = human_token().read_text(encoding="utf-8").strip()
        human_token_sha().write_text(
            hashlib.sha256(content.encode("utf-8")).hexdigest(), encoding="utf-8")
        print(f"  · 已登记人令牌哈希 → {human_token_sha()}")
    st = B.replay(a.id)
    if st["state"] != "拍板中":
        B.die(f"当前状态「{st['state']}」，只有「拍板中」的卡需要人拍")
    B.append_event(a.id, {"type": "human", "actor": "human", "who": a.who or "owner",
                        "decision": a.decision, "note": a.note or ""})
    B.ok(f"人已{a.decision}：{a.id}")

def cmd_reclaim(a):
    n = 0
    for d in B.CARDS.iterdir() if B.CARDS.exists() else []:
        if not d.is_dir():
            continue
        lease = d / "lease" / "active"
        if not lease.exists():
            continue
        for old in list(lease.iterdir()):
            if not old.is_dir():
                continue
            try:
                hb = B.jread(old / "owner.json").get("at_ms", 0)
            except Exception:
                hb = 0
            age = (B.now_ms() - hb) / 1000
            if age > B.LEASE_TTL:
                dest = d / "lease" / "reclaimed"
                dest.mkdir(parents=True, exist_ok=True)
                try:
                    os.replace(old, dest / old.name)
                except OSError:
                    continue
                B.jwrite(dest / old.name / "reclaim.json",
                       {"reclaimed_at": B.ts(), "reason": "B.heartbeat timeout",
                        "timeout_s": B.LEASE_TTL, "previous_owner": old.name})
                B.append_event(d.name, {"type": "reclaim", "seat": "system",
                                      "previous": old.name, "age_s": int(age)})
                print(f"  · 回收 {d.name}：{old.name}（{int(age)}s 无心跳）")
                n += 1
    B.ok(f"回收完成：{n} 个")


def cmd_audit(a):
    """检测绕过 CLI 直接改文件的行为。"""
    issues = []
    for d in sorted(B.CARDS.iterdir()) if B.CARDS.exists() else []:
        if not d.is_dir():
            continue
        # 0) 哈希链校验（整份重写/插入/改内容都会断链）
        chain_ok, chain_why = B.verify_chain(d.name)
        if not chain_ok:
            issues.append(f"{d.name}: 哈希链断裂 ← {chain_why}")
        try:
            st = B.replay(d.name)
        except Exception as e:
            issues.append(f"{d.name}: journal 无法重放（{e}）")
            continue
        card = B.jread(d / "card.json")
        # 1) 完成但没有复核记录
        if st["state"] == "完成" and not st["review"]:
            issues.append(f"{d.name}: 状态=完成 但无复核记录")
        # 2) 完成但复核席==执行席
        if st["review"] and st["submit"]:
            if st["review"].get("seat") == st["submit"].get("seat"):
                issues.append(f"{d.name}: 复核席与执行席同一人")
        # 2b) 复核无凭据（疑似手写 journal 绕过 CLI）—— 红线①的可判形制
        if st["review"] and not st["review"].get("evidence"):
            issues.append(f"{d.name}: 复核记录缺 evidence 字段 ← 疑似绕过 CLI 手写 journal")
        # 2c) 提交记录缺闸门读数（同上）
        if st["submit"] and "gate" not in st["submit"]:
            issues.append(f"{d.name}: 提交记录缺 gate 读数 ← 疑似绕过 CLI")
        # 3) 人闸卡在完成但无人拍板
        if st["state"] == "完成" and st["gate"] in ("both", "before_done") and not st["human"]:
            issues.append(f"{d.name}: 人闸卡已「完成」但无人工记录 ← 疑似绕过")
        # 4) 活跃租约 >1
        lease = d / "lease" / "active"
        if lease.exists():
            act = [x for x in lease.iterdir() if x.is_dir()]
            if len(act) > 1:
                issues.append(f"{d.name}: 活跃租约 {len(act)} 个（应 ≤1）")
        # 4b) 租约目录名必须是固定名（旧版带 uuid 的会破坏原子性）
        if lease.exists():
            for x in lease.iterdir():
                if x.is_dir() and x.name != B.LEASE_NAME:
                    issues.append(f"{d.name}: 租约目录名非固定名「{x.name}」← 旧版残留，原子性不成立")
        # 5) 交付物缺失但已提交
        if st["state"] in ("待验收", "核验中", "完成"):
            for item in card.get("deliverables", []):
                rel = item if isinstance(item, str) else item.get("path")
                p = (B.WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
                if not p.exists():
                    issues.append(f"{d.name}: 交付物已丢 {rel}")
    if issues:
        print(f"✗ 发现 {len(issues)} 个问题：")
        for i in issues:
            print(f"  · {i}")
        sys.exit(2)
    B.ok("审计通过：无绕过痕迹")


def cmd_html(a):
    """生成静态看板页（单项目）。双击即可看。"""
    import render as RD
    cards = []
    for d in sorted(B.CARDS.iterdir()) if B.CARDS.exists() else []:
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
            card = B.jread(d / "card.json")
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
    out = Path.home() / ".allworktogether" / "overview.html"
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
            print(f"  注册表：{P.REGISTRY}")
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
        print(f"\n共 {len(ps)} 个项目 ｜ 注册表：{P.REGISTRY}")
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
        # 写回
        reg = P._load_registry()
        for p in reg["projects"]:
            if Path(p["path"]).resolve() == B.ROOT.resolve():
                p["defaults"] = d
                if getattr(a, "workspace", None):
                    ws = Path(a.workspace)
                    if not ws.exists():
                        B.die(f"工作区不存在：{ws}")
                    p["workspace"] = str(ws.resolve())
        P._save_registry(reg)
        wsd = P.workspace_of(B.ROOT)
        B.ok(f"本项目默认值：引擎={d.get('engine','—')} 模型={d.get('model','—')} "
           f"思考={d.get('effort','—')}")
        print(f"  工作区：{wsd}")
        return


def cmd_bare(a):
    """不带子命令时：给一个能直接用的面板，而不是报错。"""
    print(f"📋 {B.ROOT.name}")
    print(f"   {B.ROOT}\n")

    if not B.CARDS.exists() or not any(d.is_dir() for d in B.CARDS.iterdir()):
        print("   还没有任何卡。\n")
        print("   下一步：")
        print("     board add --title \"要做什么\" --goal \"具体目标\"")
        print("     board project default --engine opencode "
              "--model opencode-go/deepseek-v4.1-flash")
        return

    counts = {}
    total = 0
    for d in B.CARDS.iterdir():
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
        except Exception:
            continue
        total += 1
        counts[st["state"]] = counts.get(st["state"], 0) + 1

    order = ["待认领", "进行中", "待返工", "阻塞", "待验收", "核验中", "拍板中", "完成"]
    bits = [f"{s} {counts[s]}" for s in order if counts.get(s)]
    print(f"   {total} 张卡：  " + " ｜ ".join(bits))

    # 最该做的事
    if counts.get("拍板中"):
        print(f"\n   ⚠ {counts['拍板中']} 张等你拍板：board human <卡号> --decision approve")
    if counts.get("待认领") or counts.get("待返工"):
        print("\n   下一步：board open --show 看板  或  "
              "python tools/orchestrator.py run --max 5 让它自己跑")
    elif counts.get("完成") == total:
        print("\n   全部完成 🎉   下一步：board add 建新卡")
    print()


def cmd_stats(a):
    """各状态几张、完成率。"""
    if not B.CARDS.exists():
        print("（看板为空）")
        return
    counts, total = {}, 0
    for d in B.CARDS.iterdir():
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
    if not B.CARDS.exists():
        print("（看板为空）")
        return

    def newagg():
        return {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0,
                "cache_write": 0, "cost": 0.0, "calls": 0, "unavailable": 0}

    total = newagg()
    by_card, by_model = {}, {}

    for d in sorted(B.CARDS.iterdir()):
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
    if not B.CARDS.exists():
        print("（看板为空）")
        return
    waiting = []
    for d in sorted(B.CARDS.iterdir()):
        if not d.is_dir():
            continue
        try:
            st = B.replay(d.name)
            card = B.jread(d / "card.json")
        except Exception:
            continue
        if st["state"] == "拍板中":
            waiting.append((st, card))

    if not waiting:
        # 没有待拍板，给一句正面的
        print("✓ 没有待你拍板的卡")
        pending = []
        for d in sorted(B.CARDS.iterdir()):
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
            print("  让它自己跑：python tools/orchestrator.py run --max 5")
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
        print(f"  批准    board human {cid} --decision approve --who owner")
        print(f"  驳回    board human {cid} --decision reject --who owner "
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
    for d in sorted(B.CARDS.iterdir()) if B.CARDS.exists() else []:
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
            card = B.jread(d / "card.json")
        except Exception:
            findings.append(("✗", f"{cid}: card.json 读不了", False))
            continue
        if st["state"] == "完成":
            for item in card.get("deliverables", []):
                rel = item if isinstance(item, str) else item.get("path")
                p = (B.WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
                if not p.exists():
                    findings.append(("!", f"{cid}: 已完成但交付物丢了 {rel}", False))

    # 3) 孤立 worktree
    wt_base = B.WORKSPACE / ".worktrees"
    if wt_base.exists():
        for w in wt_base.iterdir():
            if w.is_dir():
                cid = w.name
                d = B.CARDS / cid
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
    s.add_argument("--workspace", help="指定 agent 干活的工作区（默认＝项目根）")
    s.set_defaults(f=cmd_project)

    s = sub.add_parser("stats", help="一眼看数字")
    s.add_argument("--workspace", action="store_true", help="同时显示工作区")
    s.set_defaults(f=cmd_stats)

    s = sub.add_parser("cost", help="用量统计（token/缓存/花费）")
    s.add_argument("--per-card", action="store_true", help="按卡片细分")
    s.set_defaults(f=cmd_cost)

    s = sub.add_parser("open", help="生成并打开看板页（最常用）")
    s.add_argument("--show", action="store_true", help="生成后自动用浏览器打开")
    s.set_defaults(f=cmd_open)

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

    s = sub.add_parser("B.claim", help="认领（原子 + 规格匹配）")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--engine", default="any")
    s.add_argument("--model", default=None)
    s.add_argument("--effort", default=None)
    s.set_defaults(f=cmd_claim)

    s = sub.add_parser("beat", help="心跳")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
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
    s.set_defaults(f=cmd_submit)

    s = sub.add_parser("verify", help="复核席跑机器闸")
    s.add_argument("id")
    s.add_argument("--seat")
    s.set_defaults(f=cmd_verify)

    s = sub.add_parser("review", help="复核结论（必须异会话 + 带凭据）")
    s.add_argument("id")
    s.add_argument("--seat", required=True)
    s.add_argument("--verdict", required=True, choices=["pass", "fail"])
    s.add_argument("--evidence", required=True,
                   help="你实际跑的命令与读数（必须有数字，反空跑）")
    s.add_argument("--note")
    s.set_defaults(f=cmd_review)

    s = sub.add_parser("human", help="人拍板（需 token）")
    s.add_argument("id")
    s.add_argument("--decision", required=True, choices=["approve", "reject"])
    s.add_argument("--who")
    s.add_argument("--note")
    s.set_defaults(f=cmd_human)

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
    s.set_defaults(f=cmd_inbox)

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
    a.f(a)


if __name__ == "__main__":
    main()