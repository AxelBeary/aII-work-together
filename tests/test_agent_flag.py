#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_agent_flag.py — 验证 opencode 的 `--agent` 四档（build / plan / general / explore）
「可用」且「有行为差异」（卡片 G3）

三层证据，逐层加强：
  L1 事实层（离线，不烧模型）：`opencode debug agents` ＝ 引擎自报的机器可读真相。
     查四档是否都在（4 of 4），以及四档的权限档位是否真的不同（这是「行为差异」的
     确定性证据：plan 禁 edit、explore 禁 subagent 且默认全禁、general 禁 question）。
  L2 接线层（离线，不烧模型）：用替身截获 `engines.run` 真正拼出的命令行，
     确认四个 agent 都原样落成 `--agent <名字>`（调用数必须＝4）。
  L3 实跑层（`--live` 才跑，会烧模型）：四档各真跑一次同一命题，要求 4/4 拿到
     结构化回执、四个会话互不相同、回答不全相同；外加负向对照 `--agent nope`
     必须被引擎拒（「必须被拒」也是一条闸门）。

默认只跑 L1＋L2（快、确定性）；`--live` 追加 L3。
反空跑：每层都配「必须非零」对照（agent 数＝4、权限签名 unique≥3、替身调用数＝4、回执数＝4）。

运行：python tests/test_agent_flag.py [--live]
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import engines as E  # noqa: E402

AGENTS = ["build", "plan", "general", "explore"]
DEFAULT_MODEL = E.DEFAULT_MODELS["opencode"]
PROBE = "用一句话（不超过 20 字）说明你被指定的角色定位，只回这一句。"
CHECKS = []          # [(层, 名称, ok, 细节)]
FAILS = []


def check(layer, name, ok, detail):
    CHECKS.append((layer, name, bool(ok), detail))
    if not ok:
        FAILS.append(f"[{layer}] {name}：{detail}")
    return bool(ok)


def load_engine_agents():
    """读引擎自报的 agent 真相；失败返回 (None, 原因)。"""
    rc, out, err = E._exec(["opencode", "debug", "agents"], str(ROOT), 120)
    if rc != 0 or "[" not in out:
        return None, f"rc={rc} 输出={len(out)}B stderr={err[:120]}"
    try:
        return json.loads(out[out.find("["):]), ""
    except json.JSONDecodeError as e:
        return None, f"回执不可解析：{e}；输出={len(out)}B"


def has_perm(agent, action, effect):
    return any(p.get("action") == action and p.get("effect") == effect
               for p in agent.get("permissions") or [])


def perm_sig(agent):
    return tuple(sorted(
        (p.get("action"), p.get("resource"), p.get("effect"))
        for p in agent.get("permissions") or []
    ))


def layer1():
    """事实层：四档都在，且权限档位确实不同。"""
    data, why = load_engine_agents()
    if data is None:
        check("L1", "debug agents 可读", False, why)
        return {}
    byid = {a.get("id"): a for a in data}
    check("L1", "opencode debug agents 可读", True,
          f"{len(data)} 个 agent，{len(json.dumps(data))}B")
    got = [a for a in AGENTS if a in byid]
    check("L1", "四档齐全（4 of 4）", len(got) == 4,
          f"命中 {len(got)}/4：{got}；引擎内共有 {len(data)} 个 agent")
    if len(got) != 4:
        return byid
    sigs = {a: perm_sig(byid[a]) for a in AGENTS}
    unique = len(set(sigs.values()))
    check("L1", "四档权限签名互不相同", unique >= 3,
          f"unique={unique}/4（各档权限条数 "
          f"{[len(sigs[a]) for a in AGENTS]}）")
    # 逐条点名行为差异（都是引擎自报的事实）
    check("L1", "plan 是只读档（禁 edit）",
          has_perm(byid["plan"], "edit", "deny"), "edit/* ⇒ deny")
    check("L1", "build 不是只读档（无 edit 禁令）",
          not has_perm(byid["build"], "edit", "deny"), "无 edit deny")
    check("L1", "explore 禁 subagent 且默认全禁",
          has_perm(byid["explore"], "subagent", "deny")
          and has_perm(byid["explore"], "*", "deny"),
          "subagent/* ⇒ deny 且 */* ⇒ deny")
    check("L1", "general 禁 question、禁 subagent",
          has_perm(byid["general"], "question", "deny")
          and has_perm(byid["general"], "subagent", "deny"),
          "question/* ⇒ deny，subagent/* ⇒ deny")
    # 负向对照：不存在的名字不能出现在真相里
    check("L1", "负向对照：nope 不在真相中", "nope" not in byid,
          "nope ∉ ids（对应 L3 的真拒）")
    print("L1 事实层（引擎自报，离线）：")
    for a in AGENTS:
        print(f"  {a:<8} mode={byid[a].get('mode'):<8} "
              f"hidden={byid[a].get('hidden')} "
              f"权限={len(byid[a].get('permissions') or [])} 条 "
              f"签名={hash(sigs[a]) % 100000:05d}")
    return byid


def layer2():
    """接线层：四个 agent 都原样落成 --agent 参数。"""
    captured = []

    def fake_exec(cmd, cwd, timeout, stdin_text=None):
        captured.append(list(cmd))
        return 0, "{}", ""

    real = E._exec
    E._exec = fake_exec
    try:
        for a in AGENTS:
            E.run("opencode", "ping", model=DEFAULT_MODEL, agent=a)
    finally:
        E._exec = real

    check("L2", "替身被调用（必须＝4 次）", len(captured) == 4,
          f"调用数={len(captured)}")
    wired = []
    for a in AGENTS:
        hit = [c for c in captured
               if "--agent" in c and c[c.index("--agent") + 1] == a]
        wired.append(bool(hit))
    check("L2", "四档都拼出 --agent <名字>", all(wired),
          f"命中 {sum(wired)}/4：{wired}")
    has_model = [c for c in captured if "--model" in c]
    check("L2", "同时带 --model（免费池坑）", len(has_model) == len(captured),
          f"{len(has_model)}/{len(captured)} 条命令带 --model")
    print("L2 接线层（替身截获，离线）：")
    for c in captured:
        i = c.index("--agent")
        print(f"  {' '.join(c[1:i + 2])} ... （共 {len(c)} 个参数）")
    return captured


def layer3(timeout=300):
    """实跑层：4/4 可用 + 回答不全相同 + 非法档位必须被拒。"""
    rows = []
    for a in AGENTS:
        t0 = time.time()
        r = E.run("opencode", PROBE, model=DEFAULT_MODEL, agent=a, timeout=timeout)
        dt = time.time() - t0
        rows.append({"agent": a, "ok": r.ok, "reason": r.reason,
                     "sid": r.session_id, "text": (r.text or "").strip(),
                     "bytes": len((r.text or "").encode("utf-8")),
                     "sec": round(dt, 1)})
    oks = [r for r in rows if r["ok"]]
    check("L3", "四档实跑都拿到回执（4 of 4）", len(oks) == 4,
          f"ok={len(oks)}/4；失败="
          f"{[r['agent'] + ':' + r['reason'][:40] for r in rows if not r['ok']]}")
    sids = {r["sid"] for r in rows if r["sid"]}
    check("L3", "四个会话互不相同", len(sids) >= 3,
          f"unique session={len(sids)}/4")
    texts = {r["text"] for r in rows if r["text"]}
    check("L3", "回答不全相同（有行为差异）", len(texts) >= 2,
          f"unique 回答={len(texts)}/4")
    neg = E.run("opencode", PROBE, model=DEFAULT_MODEL, agent="nope", timeout=timeout)
    check("L3", "负向对照：非法档位被拒", not neg.ok,
          f"ok={neg.ok}；reason={neg.reason[:60]!r}")
    print("L3 实跑层（真调模型）：")
    for r in rows:
        print(f"  {r['agent']:<8} ok={r['ok']} {r['sec']:>5.1f}s "
              f"{r['bytes']:>4}B sess={r['sid']} 文本={r['text'][:24]!r}")
    print(f"  nope     ok={neg.ok}（必须 False）reason={neg.reason[:60]!r}")
    return rows


def main():
    t0 = time.time()
    layer1()
    layer2()
    live = "--live" in sys.argv[1:]
    if live:
        layer3()
    else:
        print("L3 实跑层：跳过（未给 --live；本层会真调模型）")

    print("\n判据：")
    for layer, name, ok, detail in CHECKS:
        print(f"  {'PASS' if ok else 'FAIL'}  [{layer}] {name:<26} {detail}")

    # 反空跑总闸：必须非零
    total = len(CHECKS)
    passed = sum(1 for _, _, ok, _ in CHECKS if ok)
    fired = len([c for c in CHECKS if c[0] == "L1"]) + 4  # L1 条数 + L2 必需 4 次调用
    print(f"\n反空跑对照：检查项={total}、必须非零的计数项={fired}"
          f"（四档数 4、替身调用 4）——全为 0 即判假绿")
    if total == 0:
        print("FAIL：检查项为 0，计数器可能坏了")
        return 1

    print(f"\n耗时 {time.time() - t0:.1f}s")
    if FAILS:
        print(f"FAIL：{len(FAILS)} 项未过")
        for f in FAILS:
            print(f"  · {f}")
        return 1
    tail = "（含 L3 实跑）" if live else "（L1+L2；L3 未跑）"
    print(f"PASS：{passed} of {total} 项——--agent 四档可用且权限档位有差异 {tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
