#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_regression.py — 回归库执行器

用法：
  python tests/run_regression.py            # 全跑
  python tests/run_regression.py --break    # 反向测试：故意改坏一条，必须被抓

设计：每条 case 在**独立临时卡**上执行，互不污染；跑完清理。
"""
import argparse
import json
import shutil
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import board as B          # noqa: E402
import resume as R         # noqa: E402

CASES = Path(__file__).resolve().parent / "regression" / "cases.json"
PREFIX = "RG-"


# ---------- 造卡工具 ----------

def new_card(cid, spec=None):
    d = B.CARDS / cid
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "artifacts").mkdir()
    (d / "evidence").mkdir()
    (d / "lease" / "active").mkdir(parents=True)
    spec = spec or {}
    B.jwrite(d / "card.json", {
        "id": cid, "title": f"regression {cid}", "goal": "", "territory": [],
        "deliverables": spec.get("deliverables", []),
        "accept_patterns": spec.get("accept", []),
        "human_gate": spec.get("human_gate", "none"),
        "created_at": "x", "created_by": "regression", "created_kind": "human",
        "irreversible": False,
        "engine": spec.get("engine", "any"),
        "model": spec.get("model", "any"),
        "effort": spec.get("effort", "any"),
    })
    B.append_event(cid, {"type": "created", "actor": "human", "seat": "regression"})
    return d


def cleanup():
    for d in B.CARDS.iterdir() if B.CARDS.exists() else []:
        if d.is_dir() and d.name.startswith(PREFIX):
            shutil.rmtree(d, ignore_errors=True)


# ---------- 各 kind 的处理 ----------

def k_concurrency(case, cid):
    new_card(cid)
    winners, lock = [], threading.Lock()

    def work(i):
        try:
            B.claim(cid, f"w{i}", "opencode")
            with lock:
                winners.append(i)
        except SystemExit:
            pass

    ts = [threading.Thread(target=work, args=(i,)) for i in range(case.get("threads", 12))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    leases = [x for x in (B.CARDS / cid / "lease" / "active").iterdir() if x.is_dir()]
    exp = case["expect"]
    ok = len(winners) <= exp["max_winners"] and len(leases) <= exp["max_leases"]
    return ok, f"winners={len(winners)} leases={len(leases)}"


def k_spec(case, cid, should_reject):
    new_card(cid, {"engine": case["card"].get("engine")})
    try:
        B.claim(cid, "w1", case["claim"].get("engine"),
                case["claim"].get("model"), case["claim"].get("effort"))
        rejected = False
    except SystemExit:
        rejected = True
    return rejected == should_reject, f"rejected={rejected}"

def k_gate(case, cid, kind):
    spec = {"deliverables": [], "accept": case.get("accept", [])}
    rel = None
    if kind == "gate_l1":
        if case.get("make_zero_byte"):
            rel = f"tests/regression/{cid}.md"
            p = ROOT / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")
            spec["deliverables"] = [rel]
        else:
            spec["deliverables"] = case.get("deliverables", [])
    elif kind == "gate_l2":
        rel = f"tests/regression/{cid}.json"
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{ this is not json", encoding="utf-8")
        spec["deliverables"] = [rel]
    elif kind == "gate_l3":
        rel = f"tests/regression/{cid}.md"
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(case.get("content", "hello 123"), encoding="utf-8")
        spec["deliverables"] = [rel]

    d = new_card(cid, spec)
    card = B.jread(d / "card.json")
    if kind == "gate_l1":
        passed, _, _ = B.gate_l1(cid, card)
    elif kind == "gate_l2":
        passed, _ = B.gate_l2(cid, card)
    else:
        passed, _, _ = B.gate_l3(cid, card)
    if rel:
        (ROOT / rel).unlink(missing_ok=True)
    return passed == case["expect"]["pass"], f"pass={passed}"


def k_review_same_seat(case, cid):
    d = new_card(cid)
    B.claim(cid, "same", "opencode")
    B.append_event(cid, {"type": "submit", "seat": "same", "gate": {"L1": True}})
    try:
        B.cmd_review(type("A", (), {"id": cid, "seat": "same", "verdict": "pass",
                                    "evidence": "x 1", "note": ""})())
        rejected = False
    except SystemExit:
        rejected = True
    return rejected == case["expect"]["rejected"], f"rejected={rejected}"


def k_review_gate_block(case, cid):
    d = new_card(cid)
    B.claim(cid, "w1", "opencode")
    B.append_event(cid, {"type": "submit", "seat": "w1", "gate": {"L1": True}})
    B.append_event(cid, {"type": "verify", "seat": "r1", "L1": False,
                         "problems": ["缺件：x"]})
    try:
        B.cmd_review(type("A", (), {"id": cid, "seat": "r1", "verdict": "pass",
                                    "evidence": "x 1", "note": ""})())
        rejected = False
    except SystemExit:
        rejected = True
    return rejected == case["expect"]["rejected"], f"rejected={rejected}"


def k_human_empty(case, cid):
    d = new_card(cid)
    B.claim(cid, "w1", "opencode")
    B.append_event(cid, {"type": "submit", "seat": "w1", "gate": {"L1": True}})
    B.append_event(cid, {"type": "verify", "seat": "r1"})
    B.append_event(cid, {"type": "review", "seat": "r1", "verdict": "pass",
                         "evidence": "1 ok"})
    B.append_event(cid, {"type": "request_human", "seat": "r1"})
    B.release(cid)
    tok = B.human_token()
    backup = tok.read_text(encoding="utf-8") if tok.exists() else None
    tok.write_text("", encoding="utf-8")
    ok_tok, _ = B._verify_human_token()
    if backup is not None:
        tok.write_text(backup, encoding="utf-8")
    else:
        tok.unlink(missing_ok=True)
    rejected = not ok_tok
    return rejected == case["expect"]["rejected"], f"rejected={rejected}"


def k_chain(case, cid):
    d = new_card(cid)
    ok_before, _ = B.verify_chain(cid)
    with (d / "journal.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"seq": 99, "type": "review", "seat": "x",
                            "verdict": "pass"}, ensure_ascii=False) + "\n")
    ok_after, why = B.verify_chain(cid)
    rejected = ok_before and not ok_after
    return rejected == case["expect"]["rejected"], f"chain_ok_after={ok_after}"


def k_state_rework(case, cid):
    d = new_card(cid)
    B.claim(cid, "w1", "opencode")
    B.append_event(cid, {"type": "submit", "seat": "w1", "gate": {"L1": True}})
    B.append_event(cid, {"type": "verify", "seat": "r1"})
    B.append_event(cid, {"type": "review", "seat": "r1", "verdict": "fail",
                         "evidence": "1 missing"})
    B.release(cid)
    st = B.replay(cid)
    return st["state"] == case["expect"]["state"], f"state={st['state']}"


def k_resume_skip(case, cid):
    d = new_card(cid)
    B.claim(cid, "w1", "opencode")
    B.append_event(cid, {"type": "submit", "seat": "w1", "gate": {"L1": True}})
    B.append_event(cid, {"type": "verify", "seat": "r1"})
    B.append_event(cid, {"type": "review", "seat": "r1", "verdict": "pass",
                         "evidence": "1 ok"})
    B.release(cid)
    st = B.replay(cid)
    action, _ = R.decide(st, cid)
    return action == case["expect"]["action"], f"action={action}"


def k_project_isolation(case, cid):
    """两个不同 root 各建一张同名卡，状态必须互不影响。"""
    import tempfile
    import projects as P
    a = Path(tempfile.mkdtemp(prefix="rg-iso-a-"))
    b = Path(tempfile.mkdtemp(prefix="rg-iso-b-"))
    old_root = B.ROOT
    try:
        B.set_root(a)
        new_card(cid)
        B.claim(cid, "wa", "opencode")
        st_a = B.replay(cid)["state"]

        B.set_root(b)
        # b 里根本没这张卡
        exists_in_b = (B.CARDS / cid).exists()
        st_b = None
        if exists_in_b:
            st_b = B.replay(cid)["state"]
    finally:
        B.set_root(old_root)
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)

    ok = (st_a == "进行中") and (not exists_in_b)
    return ok == case["expect"]["isolated"], \
        f"a={st_a} b_exists={exists_in_b}"


def k_defaults_inherit(case, cid):
    """项目默认值应被新卡继承。"""
    import projects as P
    reg = P._load_registry()
    entry = None
    for p in reg["projects"]:
        if Path(p["path"]).resolve() == B.ROOT.resolve():
            entry = p
            break
    if entry is None:
        entry = {"name": B.ROOT.name, "path": str(B.ROOT), "defaults": {}}
        reg["projects"].append(entry)
    old = dict(entry.get("defaults") or {})
    entry["defaults"] = {"engine": "opencode",
                         "model": "opencode-go/deepseek-v4.1-flash",
                         "effort": "high"}
    P._save_registry(reg)
    try:
        ns = type("A", (), {
            "id": cid, "title": "t", "goal": "", "territory": [],
            "deliverable": [], "accept": [], "human_gate": "none",
            "irreversible": False, "engine": "any", "model": "any",
            "effort": "any", "seat": "regression", "from_card": None,
        })()
        B.cmd_new(ns)
        card = B.jread(B.CARDS / cid / "card.json")
        got = (card["engine"], card["model"], card["effort"])
        want = ("opencode", "opencode-go/deepseek-v4.1-flash", "high")
        ok = got == want
    finally:
        entry["defaults"] = old
        P._save_registry(reg)
    return ok == case["expect"]["inherited"], f"got={got}"


def k_parallel_conflict(case, cid):
    """并行收工：主树已有不同内容时必须报冲突。"""
    import parallel as PL
    rel = f"tests/regression/{cid}-conflict.md"
    main = ROOT / rel
    main.parent.mkdir(parents=True, exist_ok=True)
    main.write_text("主树版本", encoding="utf-8")

    wt = ROOT / PL.WT_DIR / cid
    wt.mkdir(parents=True, exist_ok=True)
    (wt / rel).parent.mkdir(parents=True, exist_ok=True)
    (wt / rel).write_text("worktree 版本（不同）", encoding="utf-8")
    try:
        copied, conflicts = PL.collect(cid, [rel])
        got = bool(conflicts) and not copied
    finally:
        shutil.rmtree(wt, ignore_errors=True)
        main.unlink(missing_ok=True)
    return got == case["expect"]["conflict"], f"conflicts={bool(got)}"


def k_guard_illegal(case, cid):
    """非法转移：待认领 → 完成 必须被拒。"""
    new_card(cid)
    try:
        B.guard_transition(cid, "完成", "human")
        rejected = False
    except SystemExit:
        rejected = True
    return rejected == case["expect"]["rejected"], f"rejected={rejected}"


def k_guard_actor(case, cid):
    """越权：agent 不能把卡推到「拍板中→完成」这类人位。"""
    new_card(cid)
    B.claim(cid, "w1", "opencode")
    B.append_event(cid, {"type": "submit", "seat": "w1", "gate": {"L1": True}})
    B.append_event(cid, {"type": "request_human", "seat": "r1"})
    B.release(cid)
    st = B.replay(cid)
    try:
        # 卡在「拍板中」，agent 想自己推到「完成」
        B.guard_transition(cid, "完成", "agent")
        rejected = False
    except SystemExit:
        rejected = True
    return (rejected == case["expect"]["rejected"]), f"state={st['state']} rejected={rejected}"


def k_guard_holder(case, cid):
    """租约被回收后，旧执行者的提交必须被拒。"""
    new_card(cid)
    B.claim(cid, "old", "opencode")
    # 模拟：租约被回收，别人接手
    lease = B.active_lease(cid)
    B._reclaim_lease(cid, lease, reason="test")
    B.claim(cid, "new", "opencode")
    try:
        B.guard_holder(cid, "old")      # 旧执行者回来提交
        rejected = False
    except SystemExit:
        rejected = True
    return rejected == case["expect"]["rejected"], f"rejected={rejected}"


def k_parallel_edit(case, cid):
    """并行改已有文件：不应误判冲突。"""
    import parallel as PL
    rel = f"tests/regression/{cid}-edit.md"
    dst = B.WORKSPACE / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("原始内容 1", encoding="utf-8")

    wt = B.WORKSPACE / PL.WT_DIR / cid
    wt.mkdir(parents=True, exist_ok=True)
    # 基线在 create() 时记录；这里模拟已记录基线
    base = PL.WORKSPACE_BASELINE_DIR if hasattr(PL, "WORKSPACE_BASELINE_DIR") else None
    (B.WORKSPACE / PL.WT_DIR / f"{cid}.baseline.json").write_text(
        json.dumps({rel: PL._hash(dst)}, ensure_ascii=False), encoding="utf-8")

    (wt / rel).parent.mkdir(parents=True, exist_ok=True)
    (wt / rel).write_text("改后的内容 2", encoding="utf-8")
    try:
        copied, conflicts = PL.collect(cid, [rel])
        got_c = bool(conflicts)
        got_copied = bool(copied)
        final = dst.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(wt, ignore_errors=True)
        (B.WORKSPACE / PL.WT_DIR / f"{cid}.baseline.json").unlink(missing_ok=True)
        dst.unlink(missing_ok=True)

    ok = (got_c == case["expect"]["conflict"]
          and got_copied == case["expect"]["copied"]
          and final == "改后的内容 2")
    return ok, f"conflict={got_c} copied={got_copied} final={final[:12]!r}"


def k_journal_lock(case, cid):
    """并发写 journal：哈希链必须完整，无分叉。"""
    new_card(cid)
    n = case["expect"]["n"]

    def worker(i):
        try:
            B.append_event(cid, {"type": "probe", "seat": f"w{i}"})
        except SystemExit:
            pass

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    ok_chain, why = B.verify_chain(cid)
    seqs = [e["seq"] for e in B.load_journal(cid)]
    ok = ok_chain and len(seqs) == len(set(seqs)) and len(seqs) >= n
    return ok == case["expect"]["chain_ok"], \
        f"chain_ok={ok_chain} events={len(seqs)} unique_seq={len(set(seqs))}"


HANDLERS = {
    "concurrency": k_concurrency,
    "spec_mismatch": lambda c, i: k_spec(c, i, True),
    "spec_match": lambda c, i: k_spec(c, i, False),
    "gate_l1": lambda c, i: k_gate(c, i, "gate_l1"),
    "gate_l2": lambda c, i: k_gate(c, i, "gate_l2"),
    "gate_l3": lambda c, i: k_gate(c, i, "gate_l3"),
    "review_same_seat": k_review_same_seat,
    "review_gate_block": k_review_gate_block,
    "human_empty_token": k_human_empty,
    "chain_insert": k_chain,
    "state_rework": k_state_rework,
    "resume_skip_done": k_resume_skip,
    "project_isolation": k_project_isolation,
    "defaults_inherit": k_defaults_inherit,
    "parallel_conflict": k_parallel_conflict,
    "guard_illegal_transition": k_guard_illegal,
    "guard_actor": k_guard_actor,
    "guard_holder_epoch": k_guard_holder,
    "parallel_edit_file": k_parallel_edit,
    "journal_lock": k_journal_lock,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="brk", action="store_true",
                    help="反向测试：故意改坏一处代码，回归库必须抓到")
    a = ap.parse_args()

    spec = json.loads(CASES.read_text(encoding="utf-8"))
    cases = spec["cases"]
    cleanup()

    # 反向测试＝真故障注入：把闸门改坏，回归库必须红
    if a.brk:
        print("  [--break] 注入故障：gate_l3 恒返回 PASS（改坏一处）")
        B.gate_l3 = lambda cid, card: (True, [], [])

    passed, failed = 0, []
    for case in cases:
        cid = f"{PREFIX}{case['id']}"
        handler = HANDLERS.get(case["kind"])
        if not handler:
            failed.append((case["id"], f"未知 kind={case['kind']}"))
            continue
        try:
            ok, detail = handler(case, cid)
        except SystemExit as e:
            ok, detail = False, f"意外退出：{e}"
        except Exception as e:
            ok, detail = False, f"异常：{type(e).__name__}: {e}"

        if ok:
            passed += 1
            print(f"  ✓ {case['id']:<5} {case['desc'][:44]:<46} {detail}")
        else:
            failed.append((case["id"], detail))
            print(f"  ✗ {case['id']:<5} {case['desc'][:44]:<46} {detail}")

    cleanup()

    print()
    print(f"共 {len(cases)} 条，通过 {passed}，失败 {len(failed)}")

    # 反空跑
    if len(cases) < 10:
        print("✗ 反空跑失败：用例少于 10 条")
        return 1

    if a.brk:
        if failed:
            print(f"✓ 反向测试通过：注入故障后被抓住（{failed[0][0]}）")
            return 0
        print("✗ 反向测试失败：代码改坏了却没抓到 —— 回归库是瞎的")
        return 1

    if failed:
        for cid, d in failed:
            print(f"  · {cid}: {d}")
        return 1
    print("PASS：回归库全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
