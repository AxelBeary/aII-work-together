#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_experiment.py — 外问升级实验的执行器（pilot）

四臂：
  W  弱模型单干
  G  强模型单干
  M  弱模型 →（自评 CONF<阈值）→ 强模型
  S  弱模型 →（隐藏检查器判失败，即「机器闸红」）→ 强模型

判真值：`tasks.py` 里的隐藏检查器，在**独立子进程**里跑（避免模块污染）。
⛔ 不用 LLM 当裁判。

用法：
  python run_experiment.py --validate                 # 只验检查器（两把尺，不花钱）
  python run_experiment.py --arms W,G,S,M --tasks F01,C01,H01 --limit 3
  python run_experiment.py --arms W,G --out runs/pilot.jsonl
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                     # 仓库根
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import engines as E                        # noqa: E402
import hard as HX                          # noqa: E402
import hard2 as HX2                        # noqa: E402
import hard3 as HX3                        # noqa: E402
import hard4 as HX4                        # noqa: E402
import tasks as T                          # noqa: E402
import variants as VA                      # noqa: E402

ALL_TASKS = T.TASKS + HX.TASKS + HX2.TASKS + HX3.TASKS + HX4.TASKS
BY_ID = {t["id"]: t for t in ALL_TASKS}

WEAK = "opencode-go/minimax-m3.1-flash-free"
STRONG = "opencode-go/deepseek-v4.1-flash"
ENGINE = "opencode"
CONF_THRESHOLD = 70

PROMPT_SUFFIX = (
    "\n\n当前目录就是你的工作目录：只读写这里的文件，不要访问目录外的内容。"
    "完成后用一两句话说明你写了什么。"
)
CONF_INSTRUCTION = (
    "\n\n最后**单独一行**输出 `CONF: <0-100>`，表示你对自己答案正确的把握（不要写别的）。"
)


def build_workdir(task: dict, overlay: dict | None = None) -> Path:
    d = Path(tempfile.mkdtemp(prefix=f"exp-{task['id']}-"))
    for name, content in (task.get("seed") or {}).items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    for name, content in (overlay or {}).items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return d


def check(task: dict, workdir: Path) -> tuple:
    """隐藏检查器，独立子进程跑。"""
    p = subprocess.run(
        [sys.executable, str(HERE / "checker.py"), task["id"], str(workdir)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    out = (p.stdout or "").strip() or (p.stderr or "").strip()
    return p.returncode == 0, out[:200]


def validate() -> int:
    """两把尺：已知正确解必须 PASS，已知错误解必须 FAIL。"""
    bad = 0
    for t in ALL_TASKS:
        d_ok = build_workdir(t, t["ok"])
        ok1, why1 = check(t, d_ok)
        d_bad = build_workdir(t, t["bad"])
        ok2, why2 = check(t, d_bad)
        shutil.rmtree(d_ok, ignore_errors=True)
        shutil.rmtree(d_bad, ignore_errors=True)
        good = ok1 and not ok2
        print(f"  [{'PASS' if good else 'FAIL'}] {t['id']:<4} 正解→{ok1} 错解→{ok2}  "
              f"{why1 if ok1 else '（正解被判错：' + why1 + '）'}")
        if not good:
            bad += 1
    # 第三把尺（2026-10-21 加）：可计算题的期望值必须由独立实现从种子算出，
    # 否则「正解/错解」都是作者一个人写的，错得自洽，两把尺照样全绿（N04 实测连错两次）。
    for tid, (fn, fname) in getattr(HX2, "ORACLES", {}).items():
        t = BY_ID.get(tid)
        if not t:
            continue
        want = fn(t["seed"]).strip()
        got = (t["ok"].get(fname) or "").strip()
        good = want == got
        print(f"  [{'PASS' if good else 'FAIL'}] {tid:<4} 第三把尺：独立实现算出的期望 vs 手写期望")
        if not good:
            print(f"      算出：{want[:160]!r}")
            print(f"      手写：{got[:160]!r}")
            bad += 1

    # 单条件变异体（规矩 24/28）：每个变异体只破一条条件，检查器必须各自挂掉
    var_bad = 0
    for tid, vs in getattr(VA, "VARIANTS", {}).items():
        t = BY_ID.get(tid)
        if not t:
            continue
        for name, overlay in vs:
            d = build_workdir(t, overlay)
            okv, whyv = check(t, d)
            shutil.rmtree(d, ignore_errors=True)
            good = not okv
            print(f"  [{'PASS' if good else 'FAIL'}] {tid:<4} 单条件变异：{name} → 检查器必须判错")
            if not good:
                print(f"      检查器放行了这条缺陷：{whyv}")
                var_bad += 1

    print(f"\n检查器自检：{len(ALL_TASKS) - bad} of {len(ALL_TASKS)} 通过；"
          f"单条件变异体 {var_bad} 条未被抓住（应为 0）")
    return 0 if (bad == 0 and var_bad == 0) else 1


def parse_conf(text: str):
    import re
    m = re.findall(r"CONF\s*[:：]\s*(\d{1,3})", text or "")
    if not m:
        return None
    try:
        return max(0, min(100, int(m[-1])))
    except ValueError:
        return None


def run_once(task: dict, model: str, workdir: Path, timeout: int,
             conf: bool = False) -> dict:
    prompt = task["prompt"] + PROMPT_SUFFIX + (CONF_INSTRUCTION if conf else "")
    t0 = time.time()
    res = E.run(ENGINE, prompt, cwd=str(workdir), model=model, timeout=timeout)
    dt = time.time() - t0
    u = res.usage or {}
    return {
        "ok": res.ok, "reason": (res.reason or "")[:200],
        "text": res.text or "", "duration_s": round(dt, 1),
        "cost": float(u.get("cost") or 0) if u.get("available") else None,
        "tokens": int(u.get("input") or 0) + int(u.get("output") or 0),
        "model_used": res.model_used or model,
    }


SELFCHECK_PROMPT = (
    "\n\n你刚才在这个目录里完成了上面的任务。现在**逐条复核**你的产物："
    "对照每一条要求检查细节（边界值、命名、格式、是否漏改），发现错误就直接改正文件。"
    "复核完用一两句话说明：发现了什么、改了什么（没发现也照实说）。"
)


def run_selfcheck(task: dict, workdir: Path, timeout: int, model: str) -> dict:
    prompt = task["prompt"] + PROMPT_SUFFIX + SELFCHECK_PROMPT
    t0 = time.time()
    res = E.run(ENGINE, prompt, cwd=str(workdir), model=model, timeout=timeout)
    dt = time.time() - t0
    u = res.usage or {}
    return {
        "ok": res.ok, "reason": (res.reason or "")[:200],
        "text": res.text or "", "duration_s": round(dt, 1),
        "cost": float(u.get("cost") or 0) if u.get("available") else None,
        "tokens": int(u.get("input") or 0) + int(u.get("output") or 0),
        "model_used": res.model_used or model, "role": "selfcheck",
    }


def run_task(task: dict, arm: str, timeout: int) -> dict:
    """五臂：W 弱单干 / G 强单干 / M 自评触发 / S 结构触发 / V 弱＋自检不升级。

    V 臂的意义：把「验证的成本」与「升级的收益」拆开——它永远自检一次、永不升级。
    """
    wd = build_workdir(task)
    rec = {"task": task["id"], "cat": task["cat"], "arm": arm,
           "escalated": False, "trigger": "none", "steps": []}
    try:
        first_model = STRONG if arm == "G" else WEAK
        first = run_once(task, first_model, wd, timeout, conf=(arm == "M"))
        rec["steps"].append({"role": "answer", "model": first_model,
                             **{k: v for k, v in first.items() if k != "text"}})
        passed, why = check(task, wd)
        rec.update(passed=passed, first_passed=passed, check=why)
        cost = first["cost"] or 0.0
        dur = first["duration_s"]

        if arm == "V":
            rev = run_selfcheck(task, wd, timeout, WEAK)
            rec["steps"].append({k: v for k, v in rev.items() if k != "text"})
            passed, why = check(task, wd)
            rec.update(passed=passed, check=why)
            cost += rev["cost"] or 0.0
            dur += rev["duration_s"]
            rec["selfcheck_fixed"] = bool(passed and not rec["first_passed"])

        if arm in ("M", "S"):
            escalate = False
            if arm == "S":
                if not passed:
                    escalate = True
                    rec["trigger"] = "structural:checker-fail"
            else:
                conf = parse_conf(first["text"])
                rec["conf"] = conf
                if conf is None:
                    # 「信号缺失」不是「低置信」：记无效样本，⛔ 不拿它当升级理由
                    # （pilot 实测：把缺失当低置信会 10/10 误升级，多花 $0.04）
                    rec["conf_missing"] = True
                    rec["invalid"] = True
                elif conf < CONF_THRESHOLD:
                    escalate = True
                    rec["trigger"] = f"metacognitive:conf={conf}"
            if escalate:
                rec["escalated"] = True
                second = run_once(task, STRONG, wd, timeout)
                rec["steps"].append({"role": "escalated", "model": STRONG,
                                     **{k: v for k, v in second.items() if k != "text"}})
                passed2, why2 = check(task, wd)
                rec.update(passed=passed2, check=why2)
                cost += second["cost"] or 0.0
                dur += second["duration_s"]

        rec["cost"] = round(cost, 6)          # 兼容旧记录
        rec["duration_s"] = round(dur, 1)
        # 成本双记（调研建议）：真实扣费 + 口径来源；墙钟单独记
        rec["cost_actual"] = round(cost, 6)
        rec["cost_source"] = "free" if cost == 0 else "paid"
        rec["cost_equiv"] = None               # 价目表未取，⛔ 不编折算价
        rec["wall_clock_s"] = round(dur, 1)
        rec["triggered"] = bool(rec["escalated"])

        # 升级归因三态：真收益 / 白升（本来就对）/ 升了也没用
        if arm in ("M", "S"):
            if rec["escalated"]:
                if rec["passed"] and not rec["first_passed"]:
                    rec["outcome"] = "escalated_true"
                elif rec["passed"]:
                    rec["outcome"] = "escalated_waste_unneeded"
                else:
                    rec["outcome"] = "escalated_ineffective"
            else:
                rec["outcome"] = "no_escalation_pass" if rec["passed"] else "no_escalation_fail"
        else:
            rec["outcome"] = "pass" if rec["passed"] else "fail"
        return rec
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true", help="只验检查器，不调模型")
    ap.add_argument("--arms", default="W,G,S,M")
    ap.add_argument("--tasks", default="", help="逗号分隔的题号；空＝全部")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    if a.validate:
        return validate()

    ids = [x.strip() for x in a.tasks.split(",") if x.strip()] or [t["id"] for t in ALL_TASKS]
    if a.limit:
        ids = ids[:a.limit]
    arms = [x.strip().upper() for x in a.arms.split(",") if x.strip()]
    out = Path(a.out) if a.out else HERE / "runs" / f"run-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"臂={arms} 题={ids} 弱={WEAK} 强={STRONG} 输出={out}")
    n = 0
    for tid in ids:
        task = BY_ID[tid]
        for arm in arms:
            rec = run_task(task, arm, a.timeout)
            rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
            flag = "PASS" if rec["passed"] else "FAIL"
            print(f"  [{n}] {tid:<4} {arm}  {flag}  {rec['outcome']:<24} "
                  f"cost=${rec['cost']:.4f}  {rec['duration_s']}s  {rec['check'][:50]}")
    print(f"\n完成 {n} 次运行 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
