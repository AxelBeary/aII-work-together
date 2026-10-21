#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_budget_deps.py — B 批（预算 / 错误分级 / 依赖 / 拍板 diff）的反向测试

这条闸专测「刹车有没有真踩下去」，因为顺利路径全绿不代表刹车有效：
  1. 超预算的卡**必须停下转阻塞**，并把花了多少写进原因（⛔ 不许静默继续）
  2. 依赖没完成 → 认领被拒；编排器**跳过**且不消耗尝试
  3. 可重试失败（限流/超时/网络）自动退避重试；不可重试（鉴权/参数）**一次就停**
  4. 放宽预算/去掉依赖只能人来做（执行席不能自己松刹车）
  5. 拍板的人能在 `board show` 里看到「认领前 → 现在」的改动

每条都配了非零对照（比如「没超预算时必须能认领」「可重试必须真的重试过」）。

跑法：python tests/test_budget_deps.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOLS = ROOT / "tools"
SANDBOX = Path(tempfile.mkdtemp(prefix="aboard-budget-"))
REG = SANDBOX / "reg"

env = dict(os.environ)
env["ABOARD_REGISTRY_DIR"] = str(REG)
env["PYTHONIOENCODING"] = "utf-8"
env.pop("ABOARD_SEAT", None)
os.environ["BOARD_HUMAN_HOME"] = str(SANDBOX / "human")
env["BOARD_HUMAN_HOME"] = os.environ["BOARD_HUMAN_HOME"]
sys.path.insert(0, str(TOOLS))
os.environ["ABOARD_REGISTRY_DIR"] = str(REG)

fails = []


def ok(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


def board(proj, *args, env_extra=None):
    e = dict(env)
    if env_extra:
        e.update(env_extra)
    p = subprocess.run([sys.executable, str(TOOLS / "board.py"), "-C", str(proj)] + list(args),
                       cwd=str(ROOT), env=e, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def orch(proj, *args):
    p = subprocess.run([sys.executable, str(TOOLS / "orchestrator.py"), "-C", str(proj)] + list(args),
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fresh_proj(name):
    p = SANDBOX / name
    (p / "board").mkdir(parents=True, exist_ok=True)
    (p / "out").mkdir(exist_ok=True)
    return p


def add(proj, *args):
    rc, out = board(proj, "add", *args)
    assert rc == 0, out
    m = re.search(r"(C\d{4}-[0-9a-f]{4}|C[A-Z]+-\d+)", out)
    assert m, out
    return m.group(1)


def inject_usage(cid, cost, minutes=1.0, available=True, project=None):
    """往卡里塞一条 usage 事件（用真库、真哈希链，不走裸 SQL）。"""
    import board as B
    if project:
        B.set_root(str(project))
    B.append_event(cid, {"type": "usage", "seat": "w1", "engine": "opencode",
                         "model": "fake", "duration_ms": int(minutes * 60000),
                         "usage": {"input": 1, "output": 1, "cache_read": 0,
                                   "cache_write": 0, "cost": cost,
                                   "cost_currency": "USD", "available": available}})


# ---------- 1. 预算：超了必须停 ----------
def test_budget_stop():
    proj = fresh_proj("budget")
    cid = add(proj, "--title", "超预算卡", "--goal", "x",
              "--deliverable", "out/a.txt", "--max-cost", "0.5", "--max-minutes", "30")
    rc, out = board(proj, "show", cid)
    ok("建卡时预算写进了卡里", "0.50" in out and "30 分钟" in out, out.strip().splitlines()[0])

    inject_usage(cid, 0.75, 5.0, project=proj)
    rc, out = board(proj, "claim", cid, "--seat", "w1")
    ok("超预算的卡认领被拒", rc != 0, f"rc={rc}")
    ok("拒绝理由把「花了多少/上限多少」写清楚了",
       "0.7500" in out and "0.50" in out and "超过上限" in out, out.strip()[:80])

    rc, out = board(proj, "show", cid)
    ok("board show 标出已超", "已超" in out, out.strip()[:60])

    # 对照：同样花了 0.75，但上限 5.0 → 必须能认领（证明拒绝来自预算，不是别的原因）
    cid2 = add(proj, "--title", "够花的卡", "--goal", "x",
               "--deliverable", "out/b.txt", "--max-cost", "5")
    inject_usage(cid2, 0.75, 5.0, project=proj)
    rc, out = board(proj, "claim", cid2, "--seat", "w1")
    ok("对照：没超预算的卡能正常认领", rc == 0, f"rc={rc} {out.strip()[:50]}")

    # 时长上限也要能刹车（别只测钱）
    cid3 = add(proj, "--title", "超时卡", "--goal", "x",
               "--deliverable", "out/c.txt", "--max-minutes", "10")
    inject_usage(cid3, 0.01, 11.0, project=proj)
    rc, out = board(proj, "claim", cid3, "--seat", "w2")
    ok("超时长的卡也认领被拒", rc != 0 and "分钟" in out, f"rc={rc} {out.strip()[:60]}")


# ---------- 2. 依赖：没完成不许接，编排器跳过 ----------
def test_deps():
    proj = fresh_proj("deps")
    a = add(proj, "--title", "上游卡", "--goal", "x", "--deliverable", "out/up.txt",
            "--id", "CUP-1")
    b = add(proj, "--title", "下游卡", "--goal", "x", "--deliverable", "out/down.txt",
            "--id", "CDN-1", "--blocked-by", "CUP-1")
    rc, out = board(proj, "claim", b, "--seat", "w1")
    ok("依赖没完成 → 认领被拒", rc != 0 and "依赖" in out, f"rc={rc} {out.strip()[:70]}")

    # 编排器：只有一张依赖未完成的卡 → 跳过，不接
    rc, out = orch(proj, "run", "--engine", "opencode", "--seat", "w1",
                   "--max", "2", "--dry-run")
    ok("编排器跳过依赖未完成的卡", "跳过" in out, out.strip()[:60])
    ok("跳过之后真没接它（没出现「处理 CDN-1」）",
       "处理 CDN-1" not in out, out.strip()[-90:])

    # 让上游真完成：认领 → 写交付物 → submit → 异会话 review pass
    rc, out = board(proj, "claim", a, "--seat", "w1")
    assert rc == 0, out
    (proj / "out" / "up.txt").write_text("上游交付物正文，长度足够过 L1 的反空跑要求。",
                                         encoding="utf-8")
    rc, out = board(proj, "submit", a, "--seat", "w1")
    assert rc == 0 and "L1-L3 全过" in out, out
    rc, out = board(proj, "verify", a, "--seat", "rev1")
    assert rc == 0, out
    rc, out = board(proj, "review", a, "--seat", "rev1", "--verdict", "pass",
                    "--evidence",
                    "python tools/board.py verify → L1/L2/L3 全过，交付物 61 字节")
    assert rc == 0, out
    rc, out = board(proj, "show", a)
    ok("上游卡真的到「完成」", "完成" in out, out.splitlines()[1].strip() if len(out.splitlines()) > 1 else "")

    rc, out = board(proj, "claim", b, "--seat", "w2")
    ok("对照：上游完成后下游能认领", rc == 0, f"rc={rc} {out.strip()[:60]}")


# ---------- 3. 错误分级 + 重试策略 ----------
def test_error_class():
    import engines as E
    import orchestrator as O

    cases = [("超时（>1800s）", "retryable"), ("rate limit exceeded (429)", "retryable"),
             ("fetch failed", "retryable"), ("529 overloaded", "retryable"),
             ("401 unauthorized", "fatal"), ("api key invalid", "fatal"),
             ("未知引擎：foo", "fatal"), ("context length exceeded", "fatal"),
             ("something weird happened", "unknown")]
    bad = [f"{r}→{E.classify(r)['class']}" for r, want in cases
           if E.classify(r)["class"] != want]
    ok(f"{len(cases)} 条失败原因分类正确", not bad, f"判错：{bad}")

    # 可重试：连续两次超时，第三次成功 → 必须真的试了 3 次
    calls = {"n": 0}

    def fake_retry(engine, prompt, cwd=None, model=None, effort=None, timeout=None, **kw):
        calls["n"] += 1
        r = E.Result(engine)
        if calls["n"] < 3:
            r.ok, r.reason, r.exit_code = False, "超时（>1800s）", None
        else:
            r.ok, r.text = True, "done"
        return r

    plain_retry = O.RETRY_DELAYS
    real_run = E.run
    try:
        O.RETRY_DELAYS = (0, 0)
        E.run = fake_retry
        res, cls = O.run_engine_guarded("opencode", "p", str(SANDBOX), None, None, 60)
        ok("可重试失败会退避重试，第 3 次成功", res.ok and calls["n"] == 3,
           f"试了 {calls['n']} 次")

        calls["n"] = 0

        def fake_fatal(engine, prompt, cwd=None, model=None, effort=None, timeout=None, **kw):
            calls["n"] += 1
            r = E.Result(engine)
            r.ok, r.reason = False, "401 unauthorized"
            return r

        E.run = fake_fatal
        res, cls = O.run_engine_guarded("opencode", "p", str(SANDBOX), None, None, 60)
        ok("不可重试失败只试 1 次就停（不烧钱）", not res.ok and calls["n"] == 1,
           f"试了 {calls['n']} 次，分类={cls['class']}")

        calls["n"] = 0

        def fake_unknown(engine, prompt, cwd=None, model=None, effort=None, timeout=None, **kw):
            calls["n"] += 1
            r = E.Result(engine)
            r.ok, r.reason = False, "说不清的回执"
            return r

        E.run = fake_unknown
        res, cls = O.run_engine_guarded("opencode", "p", str(SANDBOX), None, None, 60)
        ok("判不准的失败不盲试（按不可重试处理）", not res.ok and calls["n"] == 1,
           f"试了 {calls['n']} 次")
    finally:
        E.run = real_run
        O.RETRY_DELAYS = plain_retry


# ---------- 4. 刹车只能人松 ----------
def test_budget_owner_rule():
    proj = fresh_proj("owner")
    cid = add(proj, "--title", "刹车卡", "--goal", "x", "--deliverable", "out/e.txt",
              "--max-cost", "1.0")
    rc, out = board(proj, "budget", cid, "--max-cost", "5.0", "--seat", "w1")
    ok("执行席不能自己放宽预算", rc != 0 and "human" in out, f"rc={rc} {out.strip()[:60]}")

    # 自称 human 但本机没有可用人令牌（隔离的 HOME 里没有令牌/登记）→ 仍然拒
    rc, out = board(proj, "budget", cid, "--max-cost", "5.0", "--seat", "human",
                    env_extra={"BOARD_HUMAN_HOME": str(SANDBOX / "nohome")})
    ok("只写 --seat human 不再算数（要人令牌）",
       rc != 0 and ("令牌" in out or "token" in out.lower()), f"rc={rc} {out.strip()[:60]}")

    rc, out = board(proj, "budget", cid, "--max-cost", "5.0", "--seat", "human",
                    "--who", "owner")
    ok("人可以把上限放宽", rc == 0, f"rc={rc} {out.strip()[:60]}")
    rc, out = board(proj, "show", cid)
    ok("放宽真的写进了卡里", "5.00" in out, out.strip()[:40])

    rc, out = board(proj, "budget", cid, "--max-cost", "0.2", "--seat", "w1")
    ok("对照：收紧（放宽的反面）执行席可以做", rc == 0, f"rc={rc}")

    rc, out = board(proj, "budget", cid, "--unblock", "--seat", "w1")
    ok("执行席不能自己去掉依赖", rc != 0, f"rc={rc} {out.strip()[:50]}")


# ---------- 5. 拍板 diff ----------
def test_diff():
    proj = fresh_proj("diff")
    (proj / "out" / "d.txt").write_text("这是认领之前就有的旧内容，长度足够过闸门。", encoding="utf-8")
    cid = add(proj, "--title", "改动卡", "--goal", "x", "--deliverable", "out/d.txt")
    rc, out = board(proj, "claim", cid, "--seat", "w1")
    assert rc == 0, out
    (proj / "out" / "d.txt").write_text(
        "这是认领之后写的新内容，长度同样足够过闸门，而且字节数不一样。", encoding="utf-8")
    rc, out = board(proj, "show", cid)
    ok("board show 能看出「改了」", "改动" in out and "改了" in out, out.strip()[-80:])
    ok("before/after 字节都列出来了", "→" in out, "")

    import board as B
    B.set_root(str(proj))
    diff = B.diff_vs_baseline(cid)
    d0 = diff[0]
    ok("基线是认领前的（不是提交后的）",
       d0["before"]["bytes"] > 0 and d0["before"]["sha8"] != d0["after"]["sha8"],
       f"{d0['before']['bytes']}B → {d0['after']['bytes']}B")


# ---------- 6. 提醒只报「需要人」和「失败」 ----------
def test_alert_line():
    import board as B
    import server as S
    proj = fresh_proj("alert")
    B.set_root(str(proj))
    a = add(proj, "--title", "待人卡", "--goal", "x")
    b = add(proj, "--title", "卡住卡", "--goal", "x")
    c = add(proj, "--title", "普通卡", "--goal", "x")
    B.append_event(a, {"type": "request_human", "actor": "review", "seat": "r1"})
    B.append_event(b, {"type": "block", "actor": "system", "seat": "system",
                       "reason": "引擎失败[retryable]：超时｜跑太久"})
    line = S.api_alert({"project": [proj.name]})
    ok("拍板中的卡会提醒", a in line and line.startswith("needs="), line)
    ok("卡住的卡会提醒", b in line, line)
    ok("对照：普通卡不提醒（不然人会关掉通知）", c not in line, line)

    # 反向：全局根被切到别的项目后，按项目名查询必须能切回来
    # （实测踩过：不切根时壳永远读到工具自己那 5 张卡，needs= 恒空）
    B.set_root(str(SANDBOX / "diff"))
    line2 = S.api_alert({"project": [proj.name]})
    ok("按项目名查询会切根（不会读到上一个项目的卡）",
       a in line2 and b in line2, line2)


# ---------- 7. 项目默认预算：设了就继承，单卡可覆盖，不设＝不限 ----------
def test_project_default_budget():
    proj = fresh_proj("defaults")
    rc, out = board(proj, "project", "default", "--max-cost", "1.5", "--max-minutes", "20")
    ok("项目默认预算设得进", rc == 0 and "1.50" in out, out.strip()[:70])

    a = add(proj, "--title", "继承默认", "--goal", "x", "--deliverable", "out/p.txt")
    rc, out = board(proj, "show", a)
    ok("新卡继承项目默认（没写 = 不限变成 1.50 / 20 分钟）",
       "1.50" in out and "20 分钟" in out, out.strip()[:60])

    b = add(proj, "--title", "单卡覆盖", "--goal", "x", "--deliverable", "out/q.txt",
            "--max-cost", "0.2")
    rc, out = board(proj, "show", b)
    ok("单卡写的预算优先于项目默认", "0.20" in out, out.strip()[:60])

    rc, out = board(proj, "project", "default", "--max-cost", "none")
    c = add(proj, "--title", "取消默认后", "--goal", "x", "--deliverable", "out/r.txt")
    rc, out = board(proj, "show", c)
    ok("取消默认后新卡不限花费（但仍继承时长 20 分钟）",
       "未设上限" not in out and "0.50" not in out and "20 分钟" in out,
       out.strip()[:60])


# ---------- 8. 多选批量：参数校验 / 人闸 / 只动选中的 ----------
def test_bulk():
    import board as B
    import server as S
    proj = fresh_proj("bulk")
    B.set_root(str(proj))
    a = add(proj, "--title", "批量取消", "--goal", "x")
    b = add(proj, "--title", "保留不动", "--goal", "x")

    for body, label in (({"ids": []}, "空选择"),
                        ({"ids": [a], "action": "rm"}, "非法动作")):
        try:
            S.api_bulk(dict(body, project=proj.name))
            ok(f"{label}要被拒", False)
        except ValueError:
            ok(f"{label}要被拒", True)

    # 人闸：没有令牌不能批量取消
    try:
        S.api_bulk({"project": proj.name, "ids": [a], "action": "cancel",
                    "who": "no-such-seat"})
        ok("没有令牌不能批量取消", False)
    except PermissionError:
        ok("没有令牌不能批量取消", True)

    # 有令牌：只动选中的那张
    import cli as C
    old = os.environ.get("USERPROFILE")
    os.environ["USERPROFILE"] = str(SANDBOX / "home")
    try:
        (SANDBOX / "home").mkdir(parents=True, exist_ok=True)
        tok = C.human_token("owner")
        # 必须写「已登记过的那个令牌」：现在换内容会被判「令牌已变更」（F-16 之后不再首次放行）
        tok.write_text("test-token-0123456789abcdef", encoding="utf-8")
        r = S.api_bulk({"project": proj.name, "ids": [a], "action": "cancel",
                        "who": "owner"})
    finally:
        if old is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = old

    ok("有令牌能批量取消选中的那张", r.get("cancelled") == [a], str(r))
    ok("对照：没选中的那张没被动", B.replay(b)["state"] == "待认领",
       B.replay(b)["state"])
    ok("取消留痕是人做的（actor=human）",
       any(ev.get("type") == "cancel" and ev.get("actor") == "human"
           for ev in B.load_journal(a)), "")


def init_human():
    """人令牌：测试用隔离的 HOME 目录，并显式登记（安全扫描 F-16 之后不再自动登记）。"""
    h = Path(os.environ["BOARD_HUMAN_HOME"])
    h.mkdir(parents=True, exist_ok=True)
    (h / ".board-human.tok").write_text("test-token-0123456789abcdef", encoding="utf-8")
    rc, out = board(SANDBOX, "token", "--init", "--who", "owner")
    assert rc == 0, out


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)
    init_human()
    try:
        for fn in (test_budget_stop, test_deps, test_error_class,
                   test_budget_owner_rule, test_diff, test_alert_line,
                   test_project_default_budget, test_bulk):
            print(f"\n--- {fn.__name__} ---")
            fn()
        print(f"\n{'=' * 50}")
        if fails:
            print(f"✗ 未通过：{'、'.join(fails)}")
            return 1
        print("✓ 预算/依赖/错误分级/刹车权限/拍板 diff/提醒/默认预算/批量 八组反向测试全过")
        return 0
    finally:
        shutil.rmtree(SANDBOX, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
