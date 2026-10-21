#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hard3.py — 长上下文 2 题（文件 ≥100 行、多文件联动、带回归检查）

为什么加这两题：pilot 里小模型把「小文件小改动」做满了，剩下的难度在
**「改动一处不能碰坏另外 40 处」**与**「有陷阱的批量编辑」**，这正是长上下文才有的错。
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(d: Path, name: str) -> str:
    p = d / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------- L01：40 个处理器 + 新增一个 + JPY 规则（回归 40 条） ----------

N_TYPES = 40


def _l01_seed() -> dict:
    hs = []
    for i in range(N_TYPES):
        rate = 1 + i / 100
        hs.append(f"def t{i:02d}(amount):\n    return round(amount * {rate:.2f}, 2)\n")
    reg = "REGISTRY = {\n" + "".join(f'    "t{i:02d}": t{i:02d},\n' for i in range(N_TYPES)) + "}\n"
    handlers = ('"""费率处理器：每种类型一个函数，费率 = 1 + 序号 %。"""\n\n'
                + "\n\n".join(hs) + "\n\n" + reg)
    pipeline = ('from handlers import REGISTRY\n\n\n'
                "def process(rec):\n"
                '    fn = REGISTRY.get(rec["type"])\n'
                "    if fn is None:\n"
                '        raise KeyError(rec["type"])\n'
                '    return fn(rec["amount"])\n\n\n'
                "def process_all(recs):\n"
                "    return [process(r) for r in recs]\n")
    main = ("from pipeline import process_all\n\n\n"
            "def run(recs):\n"
            "    return process_all(recs)\n\n\n"
            'if __name__ == "__main__":\n'
            "    print(run([]))\n")
    return {"handlers.py": handlers, "pipeline.py": pipeline, "main.py": main}


def _l01_ok() -> dict:
    seed = _l01_seed()
    handlers = seed["handlers.py"].replace(
        "\n\nREGISTRY = {",
        "\n\ndef t40(amount):\n    return round(amount * 1.40, 2)\n\n\nREGISTRY = {")
    handlers = handlers.replace('    "t39": t39,\n}', '    "t39": t39,\n    "t40": t40,\n}')
    pipeline = seed["pipeline.py"].replace(
        "    return fn(rec[\"amount\"])\n",
        "    out = fn(rec[\"amount\"])\n"
        "    if rec.get(\"currency\") == \"JPY\":\n"
        "        return int(out + 0.5) if out >= 0 else -int(-out + 0.5)\n"
        "    return out\n")
    return {"handlers.py": handlers, "pipeline.py": pipeline, "main.py": seed["main.py"]}


def _check_l01(d: Path):
    import sys
    for f in ("handlers.py", "pipeline.py", "main.py"):
        if not (d / f).exists():
            return False, f"缺 {f}"
    sys.path.insert(0, str(d))
    try:
        import pipeline
        from handlers import REGISTRY
        if "t40" not in REGISTRY:
            return False, "REGISTRY 里没有 t40"
        if abs(REGISTRY["t40"](100) - 140.0) > 1e-9:
            return False, f"t40(100) = {REGISTRY['t40'](100)}，期望 140"
        for i in range(N_TYPES):
            got = pipeline.process({"type": f"t{i:02d}", "amount": 100})
            want = round(100 * (1 + i / 100), 2)
            if abs(got - want) > 1e-9:
                return False, f"回归失败：t{i:02d} 从 {want} 变成 {got}"
        if abs(pipeline.process({"type": "t40", "amount": 250}) - 350.0) > 1e-9:
            return False, "t40 常规金额不对"
        jpy = pipeline.process({"type": "t40", "amount": 100, "currency": "JPY"})
        if jpy != 140 or not isinstance(jpy, int):
            return False, f"JPY 应返回 int 140，实际 {jpy!r}"
        jpy2 = pipeline.process({"type": "t11", "amount": 100.4, "currency": "JPY"})
        if jpy2 != 111:
            return False, f"JPY 100.4×1.11={100.4 * 1.11:.2f} 应舍到 111，实际 {jpy2!r}"
        other = pipeline.process({"type": "t11", "amount": 100.4, "currency": "USD"})
        if abs(other - round(100.4 * 1.11, 2)) > 1e-9:
            return False, f"USD 不应被整数化，实际 {other!r}"
    except Exception as e:
        return False, f"导入/调用失败：{type(e).__name__}: {e}"
    finally:
        sys.path.remove(str(d))
        for k in ("handlers", "pipeline", "main"):
            sys.modules.pop(k, None)
    return True, "t40 + JPY 规则 + 40 条回归全过"


# ---------- L02：批量改标题，代码块里的不许动（陷阱） ----------

MARK_HEAD = "## "
CODE_LINE = "## 这是代码块里的行，不要改"
TRAP_AT = (7, 19, 31)


def _l02_seed() -> dict:
    parts = []
    for i in range(1, 41):
        parts.append(f"## 第 {i} 节\n\n这里是第 {i} 节的正文，包含一些说明文字。\n")
        if i in TRAP_AT:
            parts.append("```markdown\n" + CODE_LINE + "\n```\n")
    return {"notes.md": "\n".join(parts)}


def _l02_ok() -> dict:
    lines = _l02_seed()["notes.md"].splitlines()
    out, in_code = [], False
    for ln in lines:
        if ln.startswith("```"):
            in_code = not in_code
            out.append(ln)
            continue
        if not in_code and ln.startswith("## "):
            out.append("### " + ln[3:])
        else:
            out.append(ln)
    out.append("")
    out.append("<!-- sections: 40 -->")
    return {"notes.md": "\n".join(out) + "\n"}


def _check_l02(d: Path):
    got = _read(d, "notes.md")
    if not got:
        return False, "缺 notes.md"
    lines = got.splitlines()
    in_code, heads, trap_seen, trap_broken = False, 0, 0, 0
    for ln in lines:
        if ln.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            if ln.strip() == CODE_LINE:
                trap_seen += 1
            elif ln.strip().startswith("### ") and "这是代码块里的行" in ln:
                trap_broken += 1
            continue
        if ln.startswith("### "):
            heads += 1
        elif ln.startswith("## "):
            return False, f"还有没改的二级标题：{ln[:40]}"
    if trap_broken:
        return False, "代码块里的行被改了（陷阱触发）"
    if trap_seen != 3:
        return False, f"代码块里原样保留的行只有 {trap_seen} 处，期望 3 处"
    if heads != 40:
        return False, f"三级标题 {heads} 个，期望 40 个"
    if not re.search(r"<!--\s*sections:\s*40\s*-->", got):
        return False, "缺末尾 `<!-- sections: 40 -->` 或数字不对"
    return True, "40 个标题改对、3 处代码块未动、页脚正确"


TASKS = [
    {"id": "L01", "cat": "longctx",
     "prompt": ("这个目录里是一个费率处理器小项目（`handlers.py` 有 40 个类型 `t00`–`t39` 与 `REGISTRY`，"
                "`pipeline.py` 负责调用）。请完成两件事，并保证**现有 40 种类型的行为一个都不变**：\n"
                "① 新增类型 `t40`（费率 1.40），并注册进 `REGISTRY`；\n"
                "② 修改 `pipeline.process`：当 `rec` 里有 `currency == \"JPY\"` 时，结果四舍五入成**整数**"
                "（`int` 类型），其它币种保持原样。"),
     "seed": _l01_seed(), "ok": _l01_ok(), "bad": _l01_seed(), "check": _check_l01},
    {"id": "L02", "cat": "longctx",
     "prompt": ("`notes.md` 里有 40 个二级标题（`## ` 开头）。请把**真正的二级标题**全部改成三级"
                "（`### `），但**代码块（``` 包起来的部分）里的内容一个字都不许动**；"
                "全部改完后，在文件**末尾**追加一行 `<!-- sections: 40 -->`。"),
     "seed": _l02_seed(), "ok": _l02_ok(), "bad": _l02_seed(), "check": _check_l02},
]

BY_ID = {t["id"]: t for t in TASKS}
