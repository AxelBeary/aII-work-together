#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hard4.py — B 批：长上下文 / 跨文件一致性（目标：让弱模型真的会错）

三题的设计原则：
  · 种子仓库由生成器造（每个 300–800 行），**人读得懂、机器判得死**
  · 判据全部是「行为 + 结构」双查，不靠关键词
  · 每题配单条件变异体（规矩 24）

B01 跨文件签名变更：30 个调用点全部要改，漏一个就露馅
B02 循环依赖：必须重排结构，且 AST 上不许有环
B03 长文精确改写：700 行里 40 处要改、3 类不许动（同名标题/代码块/附录）
"""
from __future__ import annotations

import re
from pathlib import Path


def _read(d: Path, name: str) -> str:
    p = d / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ============ B01：svc 包，30 个调用点要透传 retries ============

B01_HANDLERS = 6
B01_CALLS_PER = 5


def _b01_seed() -> dict:
    files = {"svc/__init__.py": "", "svc/handlers/__init__.py": ""}
    files["svc/transport.py"] = (
        '"""传输层：把每次调用的参数记下来，测试靠它看有没有透传。"""\n\n'
        "CALLS = []\n\n\n"
        "def send(url, timeout, retries):\n"
        '    CALLS.append({"url": url, "timeout": timeout, "retries": retries})\n'
        '    return {"url": url, "timeout": timeout, "retries": retries}\n')
    files["svc/core.py"] = (
        "from svc.transport import send\n\n\n"
        "def fetch(url, timeout=5):\n"
        "    return send(url, timeout)\n")
    files["svc/config.py"] = (
        '"""重试次数来自环境变量 RETRIES，缺省 3。"""\n'
        "import os\n\n\n"
        "def cfg():\n"
        '    return int(os.environ.get("RETRIES", 3))\n')
    for i in range(1, B01_HANDLERS + 1):
        parts = ["from svc.core import fetch", "from svc.config import cfg"]
        for j in range(1, B01_CALLS_PER + 1):
            parts.append(f"def h{i:02d}_{j:02d}():\n"
                         f'    return fetch("https://example.com/{i}/{j}")\n')
        files[f"svc/handlers/h{i:02d}.py"] = "\n\n".join(parts) + "\n"
    files["app.py"] = (
        "from svc.handlers import h01, h02, h03, h04, h05, h06\n\n\n"
        "MODULES = [h01, h02, h03, h04, h05, h06]\n\n\n"
        "def main():\n"
        "    out = []\n"
        "    for m in MODULES:\n"
        "        for name in sorted(dir(m)):\n"
        "            if name.startswith(\"h\") and callable(getattr(m, name)):\n"
        "                out.append(getattr(m, name)())\n"
        "    return out\n")
    return files


def _b01_ok() -> dict:
    files = _b01_seed()
    files["svc/core.py"] = (
        "from svc.transport import send\n\n\n"
        "def fetch(url, timeout=5, retries=None):\n"
        "    return send(url, timeout, retries)\n")
    for i in range(1, B01_HANDLERS + 1):
        parts = ["from svc.core import fetch", "from svc.config import cfg"]
        for j in range(1, B01_CALLS_PER + 1):
            parts.append(f"def h{i:02d}_{j:02d}():\n"
                         f'    return fetch("https://example.com/{i}/{j}", retries=cfg())\n')
        files[f"svc/handlers/h{i:02d}.py"] = "\n\n".join(parts) + "\n"
    return files


def _check_b01(d: Path):
    import os
    import sys
    sys.path.insert(0, str(d))
    mods = []
    try:
        import importlib
        os.environ["RETRIES"] = "4"
        import svc.transport as T
        T.CALLS.clear()
        for i in range(1, B01_HANDLERS + 1):
            m = importlib.import_module(f"svc.handlers.h{i:02d}")
            mods.append(m)
            for j in range(1, B01_CALLS_PER + 1):
                getattr(m, f"h{i:02d}_{j:02d}")()
        n = len(T.CALLS)
        if n != B01_HANDLERS * B01_CALLS_PER:
            return False, f"调用次数 {n}，期望 {B01_HANDLERS * B01_CALLS_PER}（有调用点没走 fetch？）"
        bad = [c for c in T.CALLS if c["retries"] != 4]
        if bad:
            return False, f"有 {len(bad)} 个调用点没透传：{bad[0]}"
        if any(c["timeout"] != 5 for c in T.CALLS):
            return False, "timeout 被改了（应保持 5）"
        # 对照：环境变量没设时必须回到 config 的缺省 3（证明是 cfg() 在起作用，不是写死 4）
        del os.environ["RETRIES"]
        T.CALLS.clear()
        for i in range(1, B01_HANDLERS + 1):
            m = mods[i - 1]
            for j in range(1, B01_CALLS_PER + 1):
                getattr(m, f"h{i:02d}_{j:02d}")()
        if any(c["retries"] != 3 for c in T.CALLS):
            return False, f"无 RETRIES 时应走 cfg() 缺省 3，实际 {T.CALLS[0]}"
    except Exception as e:
        return False, f"导入/调用失败：{type(e).__name__}: {e}"
    finally:
        os.environ.pop("RETRIES", None)
        sys.path.remove(str(d))
        for k in [k for k in sys.modules if k == "svc" or k.startswith("svc.") or k == "app"]:
            sys.modules.pop(k, None)
    return True, "30 个调用点全透传；env=4/缺省 3 两种情形都对；timeout 未变"


# ============ B02：8 模块循环依赖，要拆开且行为不变 ============

B02_N = 8


def _b02_seed() -> dict:
    files = {"pkg/__init__.py": ""}
    for i in range(1, B02_N + 1):
        nxt = i % B02_N + 1
        files[f"pkg/m{i:02d}.py"] = (
            f"def f{i:02d}(x):\n"
            f"    from pkg.m{nxt:02d} import f{nxt:02d} as nxt\n"
            f"    if x <= 0:\n"
            f"        return {i}\n"
            f"    return nxt(x - 1) + {i}\n")
    files["pkg/entry.py"] = (
        "from pkg.m01 import f01\n\n\n"
        "def run(x):\n"
        "    return f01(x)\n")
    return files


def _b02_ok() -> dict:
    """把 8 个模块改成「模块 → chain」的单向依赖（chain 内部递归，不再跨模块 import）。"""
    files = {"pkg/__init__.py": ""}
    files["pkg/chain.py"] = (
        "N = 8\n\n\n"
        "def _step(i, x):\n"
        "    if x <= 0:\n"
        "        return i\n"
        "    return _step(i % N + 1, x - 1) + i\n\n\n"
        "def f(i, x):\n"
        "    return _step(i, x)\n")
    for i in range(1, B02_N + 1):
        files[f"pkg/m{i:02d}.py"] = (
            "from pkg.chain import f\n\n\n"
            f"def f{i:02d}(x):\n"
            f"    return f({i}, x)\n")
    files["pkg/entry.py"] = (
        "from pkg.m01 import f01\n\n\n"
        "def run(x):\n"
        "    return f01(x)\n")
    return files


def _check_b02(d: Path):
    import ast
    import sys
    # 1) 结构：所有模块的 import 图必须无环
    graph = {}
    for p in sorted((d / "pkg").glob("*.py")):
        if p.name == "__init__.py":
            continue
        mod = f"pkg.{p.stem}"
        deps = set()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            return False, f"{p.name} 语法错：{e}"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("pkg."):
                deps.add(node.module)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.startswith("pkg."):
                        deps.add(a.name)
        graph[mod] = deps
    # 找环
    seen, stack = set(), []

    def dfs(u):
        if u in stack:
            return stack[stack.index(u):] + [u]
        if u in seen:
            return None
        seen.add(u)
        stack.append(u)
        for v in graph.get(u, ()):
            c = dfs(v)
            if c:
                return c
        stack.pop()
        return None

    for node in graph:
        cyc = dfs(node)
        if cyc:
            return False, f"还有循环依赖：{' → '.join(cyc)}"

    # 2) 行为：run(0)=8、run(3)=8+7+6+5=26（链式递归的结果必须一模一样）
    sys.path.insert(0, str(d))
    try:
        import pkg.entry as E
        cases = [(0, 1), (1, 3), (3, 10)]
        for x, want in cases:
            got = E.run(x)
            if got != want:
                return False, f"run({x}) = {got}，期望 {want}（行为被改了）"
    except Exception as e:
        return False, f"导入/调用失败：{type(e).__name__}: {e}"
    finally:
        sys.path.remove(str(d))
        for k in [k for k in sys.modules if k == "pkg" or k.startswith("pkg.")]:
            sys.modules.pop(k, None)
    return True, "AST 无环 + run(0/1/3) 行为一致"


# ============ B03：700 行文档，40 处要改、3 类不许动 ============

B03_SECTIONS = 40
B03_APPENDIX_AT = 33          # 第 33 节起算附录
B03_CODE_AT = (5, 12, 21, 28)  # 这些节里有代码块，块里也有 TODO


def _b03_seed() -> dict:
    parts = ["# 规范（草稿）", ""]
    for i in range(1, B03_SECTIONS + 1):
        if i == B03_APPENDIX_AT:
            parts += ["## 附录", ""]
        parts += [f"### 第 {i} 节" if i < B03_APPENDIX_AT else f"#### 附 {i}", ""]
        parts += [f"本节说明第 {i} 节的行为约定，正文里带一处待办。", ""]
        parts += ["TODO: 补齐第 %d 节的边界用例。" % i, ""]
        if i in B03_CODE_AT:
            parts += ["```python", "# TODO: 这段在代码块里，不要动", "x = %d" % i, "```", ""]
    return {"spec.md": "\n".join(parts) + "\n"}


def _b03_ok() -> dict:
    text = _b03_seed()["spec.md"]
    out, in_code, in_appendix = [], False, False
    for ln in text.splitlines():
        if ln.startswith("```"):
            in_code = not in_code
            out.append(ln)
            continue
        if ln.strip() == "## 附录":
            in_appendix = True
            out.append(ln)
            continue
        if not in_code and not in_appendix and ln.startswith("TODO:"):
            out.append(ln.replace("TODO:", "DONE:", 1))
        else:
            out.append(ln)
    head = ["<!-- audited: 40 -->"] + out
    return {"spec.md": "\n".join(head) + "\n"}


def _check_b03(d: Path):
    text = _read(d, "spec.md")
    if not text:
        return False, "缺 spec.md"
    lines = text.splitlines()
    if not lines or lines[0].strip() != "<!-- audited: 40 -->":
        return False, f"首行应是 `<!-- audited: 40 -->`，实际 {lines[0][:50]!r}"
    in_code = in_appendix = False
    need_done = {i for i in range(1, B03_SECTIONS + 1) if i < B03_APPENDIX_AT}
    done_seen, todo_seen = set(), set()
    code_todo = 0
    appendix_todo = 0
    for ln in lines[1:]:
        if ln.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            if "TODO" in ln:
                code_todo += 1
            continue
        if ln.strip() == "## 附录":
            in_appendix = True
            continue
        m = re.match(r"DONE: 补齐第 (\d+) 节的边界用例。", ln)
        if m:
            done_seen.add(int(m.group(1)))
        m = re.match(r"TODO: 补齐第 (\d+) 节的边界用例。", ln)
        if m:
            if in_appendix:
                appendix_todo += 1          # 附录里本来就该留着
            else:
                todo_seen.add(int(m.group(1)))
    if code_todo != len(B03_CODE_AT):
        return False, f"代码块里的 TODO 应该原样保留 {len(B03_CODE_AT)} 处，实际 {code_todo} 处"
    missing = need_done - done_seen
    if missing:
        return False, f"该改没改：第 {sorted(missing)[:5]} 节"
    wrong = (done_seen - need_done)
    if wrong:
        return False, f"不该改却改了：第 {sorted(wrong)[:5]} 节（附录里的不许动）"
    if todo_seen:
        return False, f"还剩 TODO：第 {sorted(todo_seen)[:5]} 节"
    if appendix_todo != B03_SECTIONS - B03_APPENDIX_AT + 1:
        return False, (f"附录里的 TODO 应原样保留 {B03_SECTIONS - B03_APPENDIX_AT + 1} 处，"
                       f"实际 {appendix_todo} 处")
    return True, f"{len(need_done)} 处改对，代码块 {len(B03_CODE_AT)} 处未动，附录未动，页眉正确"


TASKS = [
    {"id": "B01", "cat": "longctx",
     "prompt": ("`svc/` 是个小服务：`svc/core.py` 的 `fetch(url, timeout=5)` 现在只传两个参数，"
                "`svc/transport.py` 的 `send(url, timeout, retries)` 需要第三个。\n"
                "请把 `fetch` 改成 `fetch(url, timeout=5, retries=None)`（retries 原样透传给 send），"
                "并让 **`svc/handlers/` 下 6 个文件里的 30 个调用点全部显式传 `retries=cfg()`**"
                "（`cfg()` 已在 `svc/config.py` 里，读环境变量 `RETRIES`，缺省 3）。\n"
                "⛔ 不许改 timeout 的默认值，⛔ 不许把 4 之类的常数写死。"),
     "seed": _b01_seed(), "ok": _b01_ok(), "bad": _b01_seed(), "check": _check_b01},
    {"id": "B02", "cat": "longctx",
     "prompt": ("`pkg/` 下 8 个模块 `m01..m08` 互相 import，形成了**循环依赖**"
                "（每个模块的函数体里 `from pkg.m<下一个> import ...`）。\n"
                "请把循环拆掉（可以抽公共模块、可以改成迭代，随你），但要满足两条：\n"
                "① 所有模块的 import 关系**无环**（静态分析能验）；\n"
                "② 行为一模一样：`pkg.entry.run(x)` 对 0、1、3 的返回值不许变。"),
     "seed": _b02_seed(), "ok": _b02_ok(), "bad": _b02_seed(), "check": _check_b02},
    {"id": "B03", "cat": "longctx",
     "prompt": ("`spec.md` 是一份 700 行左右的规范草稿。请完成三件事：\n"
                "① 在**文件第一行**插入 `<!-- audited: 40 -->`；\n"
                "② 把正文里所有 `TODO: 补齐第 N 节的边界用例。` 改成 `DONE: 补齐第 N 节的边界用例。`；\n"
                "③ **`## 附录` 之后的所有 TODO 保持原样**，**``` 代码块里的 TODO 也保持原样**。"),
     "seed": _b03_seed(), "ok": _b03_ok(), "bad": _b03_seed(), "check": _check_b03},
]

BY_ID = {t["id"]: t for t in TASKS}
