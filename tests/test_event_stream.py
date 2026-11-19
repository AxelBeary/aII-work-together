#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_event_stream.py — 事件流闸（第 21 道闸）

测什么（D-033 丙案）：
  comments / executions / checklist / 软删除全部走事件流，由 fold 折叠；
  幂等键让 agent 可以无脑重试；seq 作增量游标。

⛔ 反空跑：每条都配反例。只测「写进去了」等于没测——要测「重复写不进去」
   「改坏了能抓到」「删了能恢复」。
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

import storage as S          # noqa: E402
import fold as F             # noqa: E402

PASS, FAIL = [], []


def ck(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    # detail 一律转字符串：调用方传 dict/list 时不该让测试自己崩（2026-11-19 踩过）
    detail = str(detail) if detail != "" else ""
    print(("  PASS " if cond else "  FAIL ") + name + ((" ｜ " + detail) if detail else ""))


def fresh():
    d = tempfile.mkdtemp(prefix="es-")
    st = S.Store(os.path.join(d, "t.db"))
    st.save_card({"id": "C1", "title": "t"}, create_only=True)
    return st


# ---------------------------------------------------------------- 幂等

def t_idem_same_key():
    """同 idempotency_key 重放：只有 1 条事件，且第二次标 replayed。"""
    st = fresh()
    e1 = st.append_event("C1", {"type": "comment", "body": "x", "idempotency_key": "k1"})
    e2 = st.append_event("C1", {"type": "comment", "body": "x", "idempotency_key": "k1"})
    cks = [e for e in st.events("C1") if e.get("type") == "comment"]
    ck("同 key 重放只留 1 条", len(cks) == 1,
       "实际 %d 条；replayed=%s" % (len(cks), e2.get("replayed")))
    ck("重放返回原 seq", e1["seq"] == e2["seq"], "seq %s vs %s" % (e1["seq"], e2["seq"]))


def t_idem_diff_key():
    """对照：不同 key 必须写 2 条（⛔ 别把「去重」做成「吞掉正常写」）。"""
    st = fresh()
    st.append_event("C1", {"type": "comment", "body": "x", "idempotency_key": "k1"})
    st.append_event("C1", {"type": "comment", "body": "x", "idempotency_key": "k2"})
    cks = [e for e in st.events("C1") if e.get("type") == "comment"]
    ck("不同 key 写 2 条（对照）", len(cks) == 2, "实际 %d 条" % len(cks))


def t_idem_no_key():
    """不给 key：正常写 2 条（老调用方行为不变）。"""
    st = fresh()
    st.append_event("C1", {"type": "comment", "body": "x"})
    st.append_event("C1", {"type": "comment", "body": "x"})
    cks = [e for e in st.events("C1") if e.get("type") == "comment"]
    ck("无 key 照常写 2 条", len(cks) == 2, "实际 %d 条" % len(cks))


# ---------------------------------------------------------------- 游标

def t_since_cursor():
    st = fresh()
    for i in range(5):
        st.append_event("C1", {"type": "comment", "body": "c%d" % i})
    allv = st.events("C1")
    part = st.events("C1", since=allv[2]["seq"])
    ck("since 切分正确", len(part) == len(allv) - 3,
       "全 %d，since 后 %d" % (len(allv), len(part)))
    ck("since 不重不漏", part[0]["seq"] > allv[2]["seq"])


def t_last_seq():
    st = fresh()
    ck("空卡 last_seq=0", st.last_seq("C1") == 0)
    e = st.append_event("C1", {"type": "comment", "body": "x"})
    ck("last_seq 跟上", st.last_seq("C1") == e["seq"])


# ---------------------------------------------------------------- 折叠

def t_fold_comments():
    evs = [
        {"seq": 1, "type": "comment", "comment_id": "c1", "body": "a", "actor": "agent"},
        {"seq": 2, "type": "comment", "comment_id": "c2", "body": "b", "actor": "human"},
        {"seq": 3, "type": "comment-delivered", "comment_id": "c1", "execution_id": "e9"},
    ]
    cs = F.fold_comments(evs)
    ck("折叠出 2 条评论", len(cs) == 2, "实际 %d" % len(cs))
    ck("投递标记生效", cs[0]["delivered_execution"] == "e9")
    ck("未投递的仍为 None", cs[1]["delivered_at"] is None)


def t_fold_executions():
    evs = [
        {"seq": 1, "type": "execution-open", "execution_id": "e1", "trigger": "manual"},
        {"seq": 2, "type": "execution-activity", "execution_id": "e1"},
        {"seq": 3, "type": "execution-close", "execution_id": "e1",
         "outcome": "failed", "error": "boom"},
    ]
    es = F.fold_executions(evs)
    ck("折叠出 1 条执行", len(es) == 1)
    ck("结算后状态为 failed", es[0]["outcome"] == "failed", es[0]["outcome"])
    ck("错误被记下", es[0]["error"] == "boom")
    ck("running 为 None", F.running_execution(evs) is None)


def t_fold_running():
    """反例：只有 open 没有 close ⇒ 必须算「在跑」。"""
    evs = [{"seq": 1, "type": "execution-open", "execution_id": "e1"}]
    r = F.running_execution(evs)
    ck("未结算算在跑", r is not None and r["id"] == "e1")


def t_fold_checklist():
    evs = [
        {"seq": 1, "type": "checklist-add", "item_id": "k1", "text": "能跑"},
        {"seq": 2, "type": "checklist-check", "item_id": "k1", "seat": "w1"},
        {"seq": 3, "type": "checklist-add", "item_id": "k2", "text": "能验"},
    ]
    ks = F.fold_checklist(evs)
    ck("清单 2 项", len(ks) == 2)
    ck("第一项已勾", ks[0]["checked"] and ks[0]["checked_by"] == "w1")
    ck("第二项未勾", not ks[1]["checked"])


def t_fold_trash():
    evs = [{"seq": 1, "type": "trash", "at": "T1"}]
    ck("软删除被识别", F.is_trashed(evs))
    evs2 = evs + [{"seq": 2, "type": "restore", "at": "T2"}]
    ck("恢复后不再是删除态", not F.is_trashed(evs2))


# ---------------------------------------------------------------- 哈希链

def t_chain_intact():
    st = fresh()
    for i in range(3):
        st.append_event("C1", {"type": "comment", "body": "c%d" % i})
    ok, why = st.verify_chain("C1")
    ck("正常链校验通过", ok, why)


def t_chain_tamper():
    """反例：手改内容必须被抓到。"""
    st = fresh()
    st.append_event("C1", {"type": "comment", "body": "orig"})
    with st.write() as c:
        c.execute("UPDATE events SET data=? WHERE card_id='C1'",
                  (json.dumps({"type": "comment", "body": "FAKE"}, ensure_ascii=False),))
    ok, why = st.verify_chain("C1")
    ck("手改被抓", not ok, why)


def t_idem_not_in_hash():
    """idem_key 是索引元数据，不该进内容哈希 —— 有 key 的链也要能验过。"""
    st = fresh()
    st.append_event("C1", {"type": "comment", "body": "a", "idempotency_key": "k1"})
    st.append_event("C1", {"type": "comment", "body": "b", "idempotency_key": "k2"})
    ok, why = st.verify_chain("C1")
    ck("带幂等键的链仍通过", ok, why)


# ---------------------------------------------------------------- 老库迁移

def t_old_db_migration():
    """反例闸：老库（events 无 idem_key）必须能平滑升级，⛔ 不能启动即崩。"""
    import sqlite3
    d = tempfile.mkdtemp(prefix="old-")
    db = os.path.join(d, "old.db")
    c = sqlite3.connect(db)
    c.executescript(
        "CREATE TABLE cards(id TEXT PRIMARY KEY,title TEXT);"
        "CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, card_id TEXT,"
        "at TEXT, at_ms INTEGER, type TEXT, data TEXT, prev TEXT, hash TEXT);")
    c.commit()
    c.close()
    try:
        st = S.Store(db)
        cols = [r[1] for r in st._read_conn().execute("PRAGMA table_info(events)")]
        ck("老库补出 idem_key 列", "idem_key" in cols, str(cols))
    except Exception as e:
        ck("老库补出 idem_key 列", False, "%s: %s" % (type(e).__name__, e))


# ---------------------------------------------------------------- CLI 端到端

def _board(args, cwd):
    env = dict(os.environ)
    env["ABOARD_REGISTRY_DIR"] = os.path.join(cwd, ".reg")
    return subprocess.run([sys.executable, str(ROOT / "tools" / "board.py")] + args,
                          cwd=cwd, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def t_cli_e2e():
    """真跑 CLI：建卡 → 评论幂等 → 清单 → 执行 → 增量 → 软删除。"""
    d = tempfile.mkdtemp(prefix="cli-")
    r = _board(["init"], d)
    if r.returncode != 0:
        ck("CLI init", False, (r.stderr or r.stdout)[-200:])
        return
    r = _board(["add", "--title", "E2E"], d)
    lines = [l for l in (r.stdout or "").splitlines() if "建" in l]
    import re
    m = re.search(r"(C[0-9A-Za-z-]+)", r.stdout or "")
    if not m:
        ck("CLI 建卡", False, (r.stdout or "")[-200:])
        return
    cid = m.group(1)
    # 幂等：同句两次
    _board(["comment", cid, "同一句", "--json"], d)
    _board(["comment", cid, "同一句", "--json"], d)
    r = _board(["comment", cid, "--json"], d)
    try:
        n = json.loads(r.stdout)["value"]["count"]
    except Exception:
        n = -1
    ck("CLI 评论幂等（同句只 1 条）", n == 1, "实际 %s" % n)

    # 清单
    r = _board(["checklist", cid, "add", "--text", "能跑", "--json"], d)
    try:
        kid = json.loads(r.stdout)["value"]["item"]
    except Exception:
        kid = None
    ck("CLI 清单 add", kid is not None)
    if kid:
        _board(["checklist", cid, "check", "--item", kid, "--json"], d)
        r = _board(["checklist", cid, "ls", "--json"], d)
        try:
            v = json.loads(r.stdout)["value"]
            ck("CLI 清单勾选生效", v["done"] == 1, str(v))
        except Exception as e:
            ck("CLI 清单勾选生效", False, str(e))

    # 执行
    r = _board(["exec", cid, "open", "--json"], d)
    try:
        eid = json.loads(r.stdout)["value"]["execution"]
    except Exception:
        eid = None
    ck("CLI 执行 open", eid is not None)
    if eid:
        _board(["exec", cid, "close", "--execution", eid, "--json"], d)
        r = _board(["exec", cid, "ls", "--json"], d)
        try:
            ex = json.loads(r.stdout)["value"]["executions"]
            ck("CLI 执行结算", ex and ex[0]["outcome"] == "succeeded", str(ex))
        except Exception as e:
            ck("CLI 执行结算", False, str(e))

    # 增量
    r = _board(["events", cid, "--json"], d)
    try:
        total = json.loads(r.stdout)["value"]["count"]
    except Exception:
        total = 0
    r = _board(["events", cid, "--since", "2", "--json"], d)
    try:
        part = json.loads(r.stdout)["value"]["count"]
    except Exception:
        part = -1
    ck("CLI 增量拉取更少", 0 <= part < total, "全 %s / 增量 %s" % (total, part))

    # 软删除 + 恢复
    r = _board(["trash", cid, "--json"], d)
    try:
        ck("CLI 软删除", json.loads(r.stdout)["ok"] is True)
    except Exception:
        ck("CLI 软删除", False, (r.stdout or "")[-150:])
    r = _board(["trash", cid, "--restore", "--json"], d)
    try:
        ck("CLI 恢复", json.loads(r.stdout)["value"]["restored"] is True)
    except Exception:
        ck("CLI 恢复", False, (r.stdout or "")[-150:])


def t_cli_json_error():
    """反例：不存在的卡必须给结构化错误（不是崩、不是人话乱码）。"""
    d = tempfile.mkdtemp(prefix="err-")
    _board(["init"], d)
    r = _board(["comment", "NOSUCH", "x", "--json"], d)
    try:
        o = json.loads(r.stdout)
        ok = (o.get("ok") is False and o["error"]["code"] == "not_found")
    except Exception:
        ok = False
    ck("不存在卡返回 not_found", ok, (r.stdout or "")[:150])
    ck("失败退出码非 0", r.returncode != 0, "code=%s" % r.returncode)



# ---------------------------------------------------------------- 编辑/移动/回退
#
# 这几条走**真 CLI 子进程**：内核的 set_root 会改全局状态，同进程里连测会互相污染。
# 子进程还顺带验证了「用户真敲这条命令能不能用」。

def _mkcard(d, title="测试"):
    r = _board(["add", "--title", title, "--json"], d)
    return json.loads(r.stdout)["value"]["id"]


def t_edit_version_guard():
    """反例：带旧 version 编辑必须被拒（乐观锁）。"""
    d = tempfile.mkdtemp(prefix="ed-")
    _board(["init"], d)
    cid = _mkcard(d)
    r = _board(["edit", cid, "--title", "新标题", "--json"], d)
    v = json.loads(r.stdout)["value"]["version"]
    ck("edit 正常递增 version", v == 2, "version=%s" % v)
    r = _board(["edit", cid, "--title", "再改", "--if-version", "1", "--json"], d)
    o = json.loads(r.stdout)
    ck("edit 旧 version 被拒", o["ok"] is False and o["error"]["code"] == "version_conflict",
       o.get("error", {}).get("code"))
    ck("版本冲突可重试", o["error"]["retryable"] is True)


def t_edit_no_fields():
    """反例：不给任何字段必须被拒（不是静默成功）。"""
    d = tempfile.mkdtemp(prefix="ed2-")
    _board(["init"], d)
    cid = _mkcard(d)
    r = _board(["edit", cid, "--json"], d)
    o = json.loads(r.stdout)
    ck("edit 无字段被拒", o["ok"] is False and o["error"]["code"] == "invalid_input")


def t_move_guard():
    """反例：非法转移拒绝；合法转移生效；同状态 no-op。"""
    d = tempfile.mkdtemp(prefix="mv-")
    _board(["init"], d)
    cid = _mkcard(d)
    r = _board(["move", cid, "--to", "完成", "--json"], d)
    o = json.loads(r.stdout)
    ck("move 非法转移被拒",
       o["ok"] is False and o["error"]["code"] == "invalid_transition",
       o.get("error", {}).get("code"))
    r = _board(["move", cid, "--to", "已取消", "--json"], d)
    o = json.loads(r.stdout)
    ck("move 到已取消", o["ok"] and o["value"]["to"] == "已取消")
    r = _board(["move", cid, "--to", "已取消", "--json"], d)
    o = json.loads(r.stdout)
    ck("move 同状态 no-op", o["ok"] and o["value"].get("noop") is True)


def t_revert_only_in_progress():
    """反例：非「进行中」不能 revert；进行中可退且释放租约。"""
    d = tempfile.mkdtemp(prefix="rv-")
    _board(["init"], d)
    cid = _mkcard(d)
    r = _board(["revert", cid, "--reason", "x", "--json"], d)
    o = json.loads(r.stdout)
    ck("revert 非进行中被拒", o["ok"] is False, o.get("error", {}).get("code"))
    _board(["claim", cid, "--seat", "w1", "--engine", "opencode"], d)
    r = _board(["revert", cid, "--reason", "引擎崩了", "--json"], d)
    o = json.loads(r.stdout)
    ck("revert 进行中→待返工", o["ok"] and o["value"]["to"] == "待返工", str(o.get("value")))
    r = _board(["show", cid], d)
    holds = [l for l in r.stdout.splitlines() if "持有" in l]
    ck("revert 后不再显示持有者", any(("持有    -" in l) or ("持有    None" in l) for l in holds),
       str(holds))
    r = _board(["revert", cid, "--reason", "再来", "--json"], d)
    o = json.loads(r.stdout)
    ck("revert 二次被拒", o["ok"] is False)


def t_json_purity():
    """反例：--json 输出必须能直接被 json.loads（混人话会崩）。"""
    d = tempfile.mkdtemp(prefix="js-")
    _board(["init"], d)
    r = _board(["add", "--title", "纯JSON", "--json"], d)
    try:
        json.loads(r.stdout)
        ck("add --json 输出纯净", True)
    except Exception as e:
        ck("add --json 输出纯净", False, "%s" % type(e).__name__)



# ---------------------------------------------------------------- 调度（D-037）

def t_sched_once_consumed():
    """① 一次性触发后调度消失（⛔ 不留幽灵）。"""
    d = tempfile.mkdtemp(prefix="sc1-")
    _board(["init"], d)
    cid = _mkcard(d)
    # 过去时间 = 立刻到点
    r = _board(["schedule", cid, "--at", "2020-01-01T00:00", "--json"], d)
    o = json.loads(r.stdout)
    ck("once 设定成功", o["ok"], o.get("error"))
    r = _board(["tick", "--json"], d)
    o = json.loads(r.stdout)
    ck("once 被触发", o["value"]["fired"] == 1, str(o["value"]))
    r = _board(["schedules", "--json"], d)
    ck("once 触发后调度清空", json.loads(r.stdout)["value"]["count"] == 0)
    r = _board(["events", cid, "--json"], d)
    types = [e["type"] for e in json.loads(r.stdout)["value"]["events"]]
    ck("留下 schedule-due 事件", "schedule-due" in types, str(types))


def t_sched_missed_marks():
    """② 错过窗口必须留痕（事件 missed + 系统评论）。"""
    d = tempfile.mkdtemp(prefix="sc2-")
    _board(["init"], d)
    cid = _mkcard(d)
    _board(["schedule", cid, "--at", "2020-01-01T00:00", "--json"], d)
    _board(["tick", "--json"], d)
    r = _board(["events", cid, "--json"], d)
    evs = json.loads(r.stdout)["value"]["events"]
    due = [e for e in evs if e["type"] == "schedule-due"]
    ck("due 事件标 missed", bool(due) and due[0].get("missed") is True)
    ck("错过有系统评论", any(e["type"] == "comment" for e in evs))


def t_sched_dead_cron_rejected():
    """③ 死 cron 拒绝写入（不制造永不触发的调度）。"""
    d = tempfile.mkdtemp(prefix="sc3-")
    _board(["init"], d)
    cid = _mkcard(d)
    r = _board(["schedule", cid, "--cron", "0 0 31 2 *", "--json"], d)
    o = json.loads(r.stdout)
    ck("死 cron 被拒", o["ok"] is False and o["error"]["code"] == "invalid_input",
       o.get("error", {}).get("message"))
    r = _board(["schedules", "--json"], d)
    ck("被拒后没有留下调度", json.loads(r.stdout)["value"]["count"] == 0)


def t_sched_skip_when_blocked():
    """④ 依赖不满足：窗口跳过并留痕。"""
    d = tempfile.mkdtemp(prefix="sc4-")
    _board(["init"], d)
    a = _mkcard(d, "被阻塞")
    b = _mkcard(d, "依赖")
    _board(["edit", a, "--blocked-by", b, "--json"], d)
    _board(["schedule", a, "--at", "2020-01-01T00:00", "--json"], d)
    r = _board(["tick", "--json"], d)
    items = json.loads(r.stdout)["value"]["items"]
    ck("依赖不满足被跳过", items and items[0]["result"] == "skipped",
       str(items))
    r = _board(["events", a, "--json"], d)
    types = [e["type"] for e in json.loads(r.stdout)["value"]["events"]]
    ck("跳过留了事件", "schedule-skipped" in types, str(types))


def t_sched_skip_when_in_progress():
    """⑤ 状态不可开工：跳过而不是硬跑。"""
    d = tempfile.mkdtemp(prefix="sc5-")
    _board(["init"], d)
    cid = _mkcard(d)
    _board(["claim", cid, "--seat", "w1", "--engine", "opencode"], d)
    _board(["schedule", cid, "--at", "2020-01-01T00:00", "--json"], d)
    r = _board(["tick", "--json"], d)
    items = json.loads(r.stdout)["value"]["items"]
    ck("进行中的卡不重复触发", items and items[0]["result"] == "skipped",
       str(items))


def t_claim_submit_idempotent():
    """D-038：claim/submit 重放不产生重复事件。"""
    d = tempfile.mkdtemp(prefix="idem-")
    _board(["init"], d)
    cid = _mkcard(d)
    _board(["claim", cid, "--seat", "w1", "--engine", "opencode"], d)
    _board(["beat", cid, "--seat", "w1"], d)
    _board(["submit", cid, "--seat", "w1"], d)
    _board(["submit", cid, "--seat", "w1"], d)
    r = _board(["events", cid, "--json"], d)
    evs = json.loads(r.stdout)["value"]["events"]
    claims = [e for e in evs if e["type"] == "claim"]
    submits = [e for e in evs if e["type"] == "submit"]
    ck("claim 只 1 条", len(claims) == 1, "实际 %d" % len(claims))
    ck("重复 submit 只 1 条", len(submits) == 1, "实际 %d" % len(submits))




def main():
    print("=" * 70)
    print("事件流闸（第 21 道）")
    print("=" * 70)
    cases = [
        ("幂等：同 key", t_idem_same_key),
        ("幂等：不同 key（对照）", t_idem_diff_key),
        ("幂等：无 key（对照）", t_idem_no_key),
        ("游标：since", t_since_cursor),
        ("游标：last_seq", t_last_seq),
        ("折叠：评论", t_fold_comments),
        ("折叠：执行", t_fold_executions),
        ("折叠：在跑判定", t_fold_running),
        ("折叠：清单", t_fold_checklist),
        ("折叠：软删除", t_fold_trash),
        ("链：正常通过", t_chain_intact),
        ("链：手改被抓（反例）", t_chain_tamper),
        ("链：幂等键不进哈希", t_idem_not_in_hash),
        ("迁移：老库升级（反例）", t_old_db_migration),
        ("CLI：端到端", t_cli_e2e),
        ("CLI：结构化错误（反例）", t_cli_json_error),
        ("编辑：版本乐观锁（反例）", t_edit_version_guard),
        ("编辑：无字段被拒（反例）", t_edit_no_fields),
        ("移动：转移守卫（反例）", t_move_guard),
        ("回退：只在进行中（反例）", t_revert_only_in_progress),
        ("CLI：--json 输出纯净（反例）", t_json_purity),
        ("调度：once 消费（反例）", t_sched_once_consumed),
        ("调度：错过留痕（反例）", t_sched_missed_marks),
        ("调度：死 cron 拒绝（反例）", t_sched_dead_cron_rejected),
        ("调度：依赖跳过（反例）", t_sched_skip_when_blocked),
        ("调度：进行中跳过（反例）", t_sched_skip_when_in_progress),
        ("幂等：claim/submit（反例）", t_claim_submit_idempotent),
    ]
    for name, fn in cases:
        try:
            fn()
        except Exception as e:
            ck(name, False, "%s: %s" % (type(e).__name__, e))
    print("=" * 70)
    total = len(PASS) + len(FAIL)
    if FAIL:
        print("✗ %d/%d 通过；失败：%s" % (len(PASS), total, "、".join(FAIL)))
        return 1
    print("✓ 事件流闸全过（%d 条断言）" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
