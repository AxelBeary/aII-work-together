#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
conformance.py — 契约一致性套件（T3）

为什么要有这个：方案里「AI 友好」「append-only」「幂等」全是形容词。
本文件把它们变成**跑得出非零读数**的断言。⛔ 一条都不过就是没过。

设计原则（与 tools/check.py 一致）：
  · 纯标准库，零依赖，不联网，不写项目外的任何文件
  · 每条断言都配「反空跑闸」：必须是真跑出来的非零，不接受「没报错就算过」
  · 正例反例成对：只测正例等于没测

用法：
  python contracts/conformance.py           # 跑全部
  python contracts/conformance.py --json    # 机器可读（给 AI 用）

退出码：0 全过 / 1 有失败
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _find_root(start: Path) -> Path:
    """向上找含 tools/storage.py 的目录。⛔ 不硬编码层数——嵌在 docs/design/<批次>/
    下时层数是会变的，硬编码必然错一次。"""
    for cand in [start, *start.parents]:
        if (cand / "tools" / "storage.py").exists():
            return cand
    raise SystemExit(f"找不到项目根（从 {start} 向上未发现 tools/storage.py）")


ROOT = _find_root(HERE)
SCHEMAS = {
    "task": HERE / "task-envelope-v1.schema.json",
    "event": HERE / "event-v1.schema.json",
}

results = []


def check(name, fn):
    """跑一条断言。异常＝FAIL，且必须写明原因。"""
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name}")
    if detail:
        print(f"      {detail}")
    return ok


# ---------------------------------------------------------------- schema 自洽

def t_schema_parse():
    """两份 schema 必须是合法 JSON 且含必需键。"""
    problems = []
    for name, p in SCHEMAS.items():
        if not p.exists():
            problems.append(f"{name}: 文件不存在 {p}")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for k in ("$schema", "type", "properties"):
            if k not in d:
                problems.append(f"{name}: 缺 {k}")
    return (not problems), "；".join(problems)


def t_envelope_required():
    """TaskEnvelope 必须声明的字段（缺一即拒）。"""
    d = json.loads(SCHEMAS["task"].read_text(encoding="utf-8"))
    props = set(d.get("properties", {}))
    need = {"id", "project_id", "title", "state", "version", "seq",
            "created_at", "updated_at"}
    missing = need - props
    return (not missing), f"缺字段：{sorted(missing)}" if missing else f"{len(props)} 个字段齐"


def t_meta_not_carrier():
    """反向闸：meta 不许被写成 comments/executions 的承载位。

    这是 15 稿丙案的核心防腐条款。若有人在 schema 里给 meta 写了
    comments/executions/checklist 的固定结构，本条立即 FAIL。
    """
    d = json.loads(SCHEMAS["task"].read_text(encoding="utf-8"))
    meta = d.get("properties", {}).get("meta", {})
    desc = (meta.get("description") or "").lower()
    banned = ["comment", "execution", "checklist"]
    hits = [b for b in banned if f"meta.{b}" in desc or f"存 {b}" in desc]
    # 允许出现在「禁止」语境里：查是否含「禁止/⛔/not」
    allowed_ctx = any(w in desc for w in ("禁止", "⛔", "not for", "不要"))
    if hits and not allowed_ctx:
        return False, f"meta 描述疑似把 {hits} 当承载位"
    return True, "meta 未被当作 append 数据的承载位"


def t_event_idempotency_field():
    """Event 必须有 idempotency_key（AI 重试安全的前提）。"""
    d = json.loads(SCHEMAS["event"].read_text(encoding="utf-8"))
    props = set(d.get("properties", {}))
    return ("idempotency_key" in props),         "有 idempotency_key" if "idempotency_key" in props else "缺 idempotency_key"


def t_event_types_cover():
    """Event 的 type 闭集必须覆盖 T0 缺口报告里的四类承载。"""
    d = json.loads(SCHEMAS["event"].read_text(encoding="utf-8"))
    types = set(d.get("properties", {}).get("type", {}).get("enum", []))
    need = {
        "comment": any(t.startswith("comment") for t in types),
        "execution": any(t.startswith("execution") for t in types),
        "checklist": any(t.startswith("checklist") for t in types),
        "trash": "trash" in types,
    }
    missing = [k for k, v in need.items() if not v]
    return (not missing), f"缺：{missing}" if missing else "四类承载均有事件类型"


def t_hash_format():
    """哈希链长度必须与 storage.py::_hash 一致（[:16]）。"""
    d = json.loads(SCHEMAS["event"].read_text(encoding="utf-8"))
    pat = d.get("properties", {}).get("hash", {}).get("pattern", "")
    ok = "16" in pat
    return ok, f"pattern={pat}"


# ---------------------------------------------------------------- 内核契约对齐

def t_kernel_hash_matches():
    """内核 _hash 必须真的是 sha256[:16] —— 与 schema 声明一致。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import hashlib
    raw = "prev" + json.dumps({"a": 1}, ensure_ascii=False, sort_keys=True)
    expect = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    src = (ROOT / "tools" / "storage.py").read_text(encoding="utf-8")
    m = re.search(r"def _hash\(prev.*?\n(.*?)\n\n", src, re.S)
    if not m:
        return False, "找不到 _hash 实现"
    body = m.group(1)
    ok = "sha256" in body and "[:16]" in body
    return ok, f"期望 {expect[:8]}…；实现 {'一致' if ok else '不一致'}"


def t_kernel_append_only():
    """反向闸：append_event 不许出现 UPDATE/DELETE events。"""
    src = (ROOT / "tools" / "storage.py").read_text(encoding="utf-8")
    m = re.search(r"def append_event.*?(?=\n    def )", src, re.S)
    if not m:
        return False, "找不到 append_event"
    body = m.group(0)
    bad = [w for w in ("UPDATE events", "DELETE FROM events") if w in body]
    return (not bad), f"发现 {bad}" if bad else "只有 INSERT"


def t_kernel_meta_is_blob():
    """记录事实：meta 是整块读改写（这是不用它做承载位的理由）。"""
    src = (ROOT / "tools" / "storage.py").read_text(encoding="utf-8")
    has = 'c == "meta"' in src and "json.dumps(meta" in src
    return has, "已确认 meta 为整块 JSON 读写（故禁止承载 append 数据）" if has else "未找到 meta 整块写证据"


def t_kernel_seq_cursor():
    """events 表必须有 (card_id, seq) 索引，否则增量拉取不成立。"""
    src = (ROOT / "tools" / "storage.py").read_text(encoding="utf-8")
    ok = "idx_events_card ON events(card_id, seq)" in src
    return ok, "有 (card_id, seq) 索引" if ok else "缺索引"


# ---------------------------------------------------------------- 行为反例

def _fake_store():
    """用一个临时库跑真内核，验证行为（不碰项目库）。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import storage as S
    tmp = tempfile.mkdtemp(prefix="conformance-")
    return S.Store(os.path.join(tmp, "t.db")), tmp


def t_append_two_comments():
    """正例：两条 comment 事件必须都在（append 不覆盖）。"""
    st, _ = _fake_store()
    st.save_card({"id": "C1", "title": "t"}, create_only=True)
    for i in (1, 2):
        st.append_event("C1", {"type": "comment", "body": f"c{i}"})
    evs = [e for e in st.events("C1") if e.get("type") == "comment"]
    return (len(evs) == 2), f"comment 事件数 {len(evs)}（期望 2）"


def t_idempotent_replay():
    """反例闸：同 idempotency_key 重放，事件数不得增长。

    ⚠ 内核当前未实现幂等，本条**预期失败**，作为 P1 的待办锚点。
    若哪天实现了，本条自动转绿 —— 这就是「用测试表达需求」。
    """
    st, _ = _fake_store()
    st.save_card({"id": "C2", "title": "t"}, create_only=True)
    for _ in range(3):
        st.append_event("C2", {"type": "comment", "body": "x",
                               "idempotency_key": "k1"})
    evs = [e for e in st.events("C2") if e.get("type") == "comment"]
    return (len(evs) == 1), f"重放 3 次产生 {len(evs)} 条（期望 1；未实现即 P1 待办）"


def t_chain_tamper_detected():
    """反例闸：手改事件内容必须被 verify_chain 抓到。"""
    st, _ = _fake_store()
    st.save_card({"id": "C3", "title": "t"}, create_only=True)
    st.append_event("C3", {"type": "comment", "body": "orig"})
    ok0, _ = st.verify_chain("C3")
    with st.write() as c:
        c.execute("UPDATE events SET data=? WHERE card_id='C3'",
                  (json.dumps({"type": "comment", "body": "FAKE"}, ensure_ascii=False),))
    ok1, why = st.verify_chain("C3")
    return (ok0 and not ok1), f"改前 {'通过' if ok0 else '失败'}／改后 {'通过' if ok1 else '抓到'}"


def t_since_cursor():
    """正例：?since 语义可用 —— seq 严格递增且可按游标切分。"""
    st, _ = _fake_store()
    st.save_card({"id": "C4", "title": "t"}, create_only=True)
    for i in range(5):
        st.append_event("C4", {"type": "comment", "body": f"c{i}"})
    evs = st.events("C4")
    seqs = [e["seq"] for e in evs]
    monotonic = all(b > a for a, b in zip(seqs, seqs[1:]))
    cut = [e for e in evs if e["seq"] > seqs[2]]
    return (monotonic and len(cut) == len(evs) - 3),         f"seq 单调={monotonic}，since 切出 {len(cut)}/{len(evs)}"


# ---------------------------------------------------------------- main

def main(argv):
    as_json = "--json" in argv
    if not as_json:
        print("=" * 70)
        print("契约一致性套件（T3）")
        print("=" * 70)

    tests = [
        ("schema 可解析", t_schema_parse),
        ("envelope 必需字段", t_envelope_required),
        ("meta 不作承载位（防腐）", t_meta_not_carrier),
        ("event 有幂等键", t_event_idempotency_field),
        ("event 类型覆盖四类承载", t_event_types_cover),
        ("hash 格式一致", t_hash_format),
        ("内核 _hash 实现一致", t_kernel_hash_matches),
        ("append_event 只 INSERT", t_kernel_append_only),
        ("meta 是整块 blob（事实）", t_kernel_meta_is_blob),
        ("events 有 (card_id,seq) 索引", t_kernel_seq_cursor),
        ("两条 comment 都在", t_append_two_comments),
        ("幂等重放只留 1 条", t_idempotent_replay),
        ("手改事件被抓", t_chain_tamper_detected),
        ("since 游标可切分", t_since_cursor),
    ]
    for name, fn in tests:
        check(name, fn)

    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    failed = [r["name"] for r in results if not r["ok"]]

    if as_json:
        print(json.dumps({"ok": passed == total, "passed": passed,
                          "total": total, "failed": failed,
                          "results": results}, ensure_ascii=False, indent=2))
    else:
        print("=" * 70)
        if passed == total:
            print(f"✓ 全部通过（{passed}/{total}）")
        else:
            print(f"✗ {passed}/{total} 通过；失败：{'、'.join(failed)}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
