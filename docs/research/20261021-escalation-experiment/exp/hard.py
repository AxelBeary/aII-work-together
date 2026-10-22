#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hard.py — 难度加码 5 题（校准用：目标是弱模型通过率 ≤60%）

沿用 tasks.py 的同一套结构（prompt/seed/check/ok/bad），由 run_experiment 合并加载。
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _read(d: Path, name: str) -> str:
    p = d / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------- C04：CSV 行解析（引号/转义/空字段） ----------

CSV_OK = r'''def parse_csv_line(line):
    out, cur, i, inq = [], "", 0, False
    s = str(line)
    while i < len(s):
        ch = s[i]
        if inq:
            if ch == '"':
                if i + 1 < len(s) and s[i + 1] == '"':
                    cur += '"'
                    i += 2
                    continue
                inq = False
                i += 1
                continue
            cur += ch
            i += 1
            continue
        if ch == '"':
            inq = True
            i += 1
            continue
        if ch == ',':
            out.append(cur)
            cur = ""
            i += 1
            continue
        cur += ch
        i += 1
    out.append(cur)
    return out
'''


def _check_csv(d: Path):
    import importlib.util
    p = d / "csvline.py"
    if not p.exists():
        return False, "缺 csvline.py"
    spec = importlib.util.spec_from_file_location("csvline", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    cases = [
        ("a,b,c", ["a", "b", "c"]),
        ('a,"b,c",d', ["a", "b,c", "d"]),
        ('"a""b",c', ['a"b', "c"]),
        (",", ["", ""]),
        ('""', [""]),
        ('"a,b"', ["a,b"]),
        ("a,", ["a", ""]),
        ('" spaced "', [" spaced "]),
    ]
    for src, want in cases:
        try:
            got = m.parse_csv_line(src)
        except Exception as e:
            return False, f"parse_csv_line({src!r}) 抛 {type(e).__name__}: {e}"
        if list(got) != want:
            return False, f"parse_csv_line({src!r}) = {got}，期望 {want}"
    return True, "8 组用例全过"


# ---------- C05：时长格式化 ----------

FMT_OK = r'''def fmt_duration(seconds):
    n = int(seconds)
    if n < 0:
        raise ValueError(seconds)
    h, rem = divmod(n, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s:
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"
'''


def _check_fmt(d: Path):
    import importlib.util
    p = d / "fmt.py"
    if not p.exists():
        return False, "缺 fmt.py"
    spec = importlib.util.spec_from_file_location("fmt", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    cases = [(0, "0s"), (45, "45s"), (60, "1m"), (3661, "1h 1m 1s"),
             (7200, "2h"), (90, "1m 30s"), (360000, "100h")]
    for src, want in cases:
        try:
            got = m.fmt_duration(src)
        except Exception as e:
            return False, f"fmt_duration({src}) 抛 {type(e).__name__}: {e}"
        if got != want:
            return False, f"fmt_duration({src}) = {got!r}，期望 {want!r}"
    try:
        m.fmt_duration(-1)
        return False, "fmt_duration(-1) 应抛 ValueError"
    except ValueError:
        pass
    except Exception as e:
        return False, f"fmt_duration(-1) 抛了 {type(e).__name__}，要求 ValueError"
    return True, "8 组用例全过"


# ---------- H04：跨 4 文件改名 + 参数注入 ----------

X_SEED = {
    "core.py": "class Engine:\n    def run(self, x):\n        return x * 2\n",
    "plugins/a.py": ("from core import Engine\n\n\n"
                     "def make():\n    return Engine()\n\n\n"
                     "def go(e, x):\n    return e.run(x)\n"),
    "plugins/b.py": ("from core import Engine\n\n\n"
                     "def twice(e, x):\n    return e.run(e.run(x))\n"),
    "app.py": ("from core import Engine\nfrom plugins.a import go\n\n\n"
               "def main():\n    e = Engine()\n    return go(e, 21)\n"),
}
X_BAD = dict(X_SEED)
X_OK = {
    "core.py": "class EngineCore:\n    def run(self, x, timeout=30):\n        return x * 2\n",
    "plugins/a.py": ("from core import EngineCore\n\n\n"
                     "def make():\n    return EngineCore()\n\n\n"
                     "def go(e, x, timeout=30):\n    return e.run(x, timeout=timeout)\n"),
    "plugins/b.py": ("from core import EngineCore\n\n\n"
                     "def twice(e, x, timeout=30):\n    return e.run(e.run(x, timeout=timeout), timeout=timeout)\n"),
    "app.py": ("from core import EngineCore\nfrom plugins.a import go\n\n\n"
               "def main(timeout=30):\n    e = EngineCore()\n    return go(e, 21, timeout=timeout)\n"),
}


def _check_xfiles(d: Path):
    for f in ("core.py", "plugins/a.py", "plugins/b.py", "app.py"):
        if not (d / f).exists():
            return False, f"缺 {f}"
    for f in ("core.py", "plugins/a.py", "plugins/b.py", "app.py"):
        src = _read(d, f)
        if re.search(r"\bEngine\b", src):
            return False, f"{f} 里还有裸的 Engine（应改成 EngineCore）"
    import sys
    sys.path.insert(0, str(d))
    try:
        import app
        import core
        if not hasattr(core, "EngineCore"):
            return False, "core.py 里没有 EngineCore"
        if app.main() != 42:
            return False, f"app.main() = {app.main()}，期望 42"
        out = core.EngineCore().run(2, timeout=5)
        if out != 4:
            return False, f"EngineCore().run(2, timeout=5) = {out}，期望 4"
    except Exception as e:
        return False, f"导入/调用失败：{type(e).__name__}: {e}"
    finally:
        sys.path.remove(str(d))
        for k in ("app", "core", "plugins", "plugins.a", "plugins.b"):
            sys.modules.pop(k, None)
    return True, "四文件改净，行为不变"


# ---------- H05：修三个 bug ----------

BUG_SEED = {
    "stats.py": (
        "def add(items, x, acc=[]):\n"
        "    acc.append(x)\n"
        "    return acc\n\n\n"
        "def mean(xs):\n"
        "    return sum(xs) / len(xs)\n\n\n"
        "def approx(a, b):\n"
        "    return a == b\n"),
}
BUG_OK = {
    "stats.py": (
        "def add(items, x, acc=None):\n"
        "    acc = [] if acc is None else acc\n"
        "    acc.append(x)\n"
        "    return acc\n\n\n"
        "def mean(xs):\n"
        "    xs = list(xs)\n"
        "    return (sum(xs) / len(xs)) if xs else None\n\n\n"
        "def approx(a, b):\n"
        "    return abs(a - b) <= 1e-9\n"),
}


def _check_bugs(d: Path):
    import importlib.util
    p = d / "stats.py"
    if not p.exists():
        return False, "缺 stats.py"
    spec = importlib.util.spec_from_file_location("stats", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    try:
        r1 = m.add([], 1)
        r2 = m.add([], 2)
        if r1 != [1] or r2 != [2]:
            return False, f"可变默认参数没修：add([],1)={r1} add([],2)={r2}"
        empty = m.mean([])
        if empty is not None:
            return False, f"mean([]) 应返回 None，实际 {empty!r}"
        if abs(m.mean([1, 2, 3]) - 2.0) > 1e-9:
            return False, "mean([1,2,3]) 应为 2.0"
        if not m.approx(0.1 + 0.2, 0.3):
            return False, "approx(0.1+0.2, 0.3) 应为 True"
        if m.approx(1.0, 1.1):
            return False, "approx(1.0, 1.1) 应为 False"
    except Exception as e:
        # 崩溃也算失败，但要说清是哪一类（否则和「答案错」混在一起）
        return False, f"调用抛 {type(e).__name__}: {e}"
    return True, "三处 bug 全修，边界用例通过"


# ---------- H06：多文件 JSON 合并 ----------

M_A = [{"id": 1, "ts": 100, "code": "b", "price": 5},
       {"id": 2, "ts": 200, "code": "a", "price": -1}]
M_B = [{"id": 1, "ts": 300, "code": "b2", "price": 7},
       {"id": 3, "ts": 150, "code": "a", "price": 9}]
M_C = [{"id": 3, "ts": 100, "code": "a0", "price": 3}]
M_WANT = [{"id": 3, "ts": 150, "sku": "a", "price": 9},
          {"id": 1, "ts": 300, "sku": "b2", "price": 7}]

M_SEED = {"data/a.json": json.dumps(M_A, ensure_ascii=False),
          "data/b.json": json.dumps(M_B, ensure_ascii=False),
          "data/c.json": json.dumps(M_C, ensure_ascii=False)}
M_OK = {"merged.json": json.dumps(M_WANT, ensure_ascii=False, indent=2) + "\n"}
M_BAD = {"merged.json": json.dumps(M_A + M_B + M_C, ensure_ascii=False) + "\n"}


def _check_merge(d: Path):
    p = d / "merged.json"
    if not p.exists():
        return False, "缺 merged.json"
    try:
        got = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"JSON 解析失败：{e}"
    if got != M_WANT:
        return False, f"内容不符（拿到 {len(got)} 条）：{json.dumps(got, ensure_ascii=False)[:160]}"
    return True, "去重/改名/过滤/排序全对"


TASKS = [
    {"id": "C04", "cat": "compose",
     "prompt": ("写 `csvline.py`，实现 `parse_csv_line(line)`：按逗号切字段；字段可用双引号包起来，"
                "引号内的逗号是字面量；引号内 `\"\"` 表示一个 `\"`；不做 trim。返回字段列表。"),
     "seed": {}, "ok": {"csvline.py": CSV_OK},
     "bad": {"csvline.py": "def parse_csv_line(line):\n    return str(line).split(',')\n"},
     "check": _check_csv},
    {"id": "C05", "cat": "compose",
     "prompt": ("写 `fmt.py`，实现 `fmt_duration(seconds)` → 人读字符串：超过 60 秒用 `1m 30s` 这种形式，"
                "整小时用 `2h`；为零的单位省略；0 → `0s`；负数抛 `ValueError`。不设「天」单位。"),
     "seed": {}, "ok": {"fmt.py": FMT_OK},
     "bad": {"fmt.py": "def fmt_duration(s):\n    return f'{s}s'\n"},
     "check": _check_fmt},
    {"id": "H04", "cat": "blast",
     "prompt": ("把 `core.py` 的类 `Engine` 改名为 `EngineCore`，并给 `run` 加一个 `timeout=30` 参数"
                "（当前实现可以忽略它）。`plugins/a.py`、`plugins/b.py`、`app.py` 的所有引用与调用点都要跟着改，"
                "把 timeout 透传下去；`app.main()` 必须仍返回 42。"),
     "seed": X_SEED, "ok": X_OK, "bad": X_BAD, "check": _check_xfiles},
    {"id": "H05", "cat": "blast",
     "prompt": ("`stats.py` 里有三个 bug，请修好，不要改函数名："
                "① `add` 的可变默认参数导致多次调用累积；"
                "② `mean([])` 会崩（应返回 `None`）；"
                "③ `approx` 用 `==` 比较浮点（应容忍 1e-9）。"),
     "seed": BUG_SEED, "ok": BUG_OK, "bad": BUG_SEED, "check": _check_bugs},
    {"id": "H06", "cat": "blast",
     "prompt": ("把 `data/a.json`、`data/b.json`、`data/c.json` 合并成 `merged.json`："
                "按 `id` 去重、保留 `ts` 最大的那条；把字段 `code` 改名为 `sku`；"
                "丢掉 `price < 0` 的记录；按 `sku` 升序排列；只输出最后的结果数组。"),
     "seed": M_SEED, "ok": M_OK, "bad": M_BAD, "check": _check_merge},
]

BY_ID = {t["id"]: t for t in TASKS}
