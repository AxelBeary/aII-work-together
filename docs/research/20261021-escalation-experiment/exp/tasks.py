#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tasks.py — 外问升级实验的题库（pilot 10 题）

每题四个要素：
  prompt   给 agent 的题面（工作目录＝临时沙箱）
  seed     初始文件（refactor 类需要）
  check    隐藏检查器：收一个目录，返回 (ok, 说明)。⛔ agent 看不到它
  ok/bad   已知正确解／已知错误解（用于「两把尺」：检查器必须双向都判对）

纪律：判真值只用这里的机器检查，不用 LLM 当裁判。
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _read(d: Path, name: str) -> str:
    p = d / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------- 事实类：答案唯一，精确匹配 ----------

def _exact(expected):
    def check(d: Path):
        got = _read(d, "answer.txt").strip()
        return (got == expected), f"期望 {expected!r}，实际 {got!r}"
    return check


FACTS = [
    ("F01", "数学：`math.gcd(84, 36)` 的值是多少？**只写这个整数**，存到 `answer.txt`（一行）。", "12"),
    ("F02", "Python：`bin(13)` 的返回值是什么？**只写返回的字符串**（含前缀），存到 `answer.txt`。", "0b1101"),
    ("F03", "Python：`''.join(sorted('cab'))` 的结果是什么？**只写这三个字母**，存到 `answer.txt`。", "abc"),
    ("F04", "Python：`datetime.date(2024, 2, 29).weekday()` 返回几？（周一=0）**只写这个整数**，存到 `answer.txt`。", "3"),
]


# ---------- 组合类：隐藏单测 ----------

def _check_intervals(d: Path):
    import importlib.util
    p = d / "intervals.py"
    if not p.exists():
        return False, "缺 intervals.py"
    spec = importlib.util.spec_from_file_location("iv", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    cases = [
        ([], []),
        ([[1, 3], [2, 6], [8, 10], [15, 18]], [[1, 6], [8, 10], [15, 18]]),
        ([[1, 4], [4, 5]], [[1, 5]]),
        ([[5, 6], [1, 2]], [[1, 2], [5, 6]]),
        ([[1, 10], [2, 3]], [[1, 10]]),
    ]
    for src, want in cases:
        try:
            got = m.merge([list(x) for x in src])
        except Exception as e:
            return False, f"merge({src}) 抛 {type(e).__name__}: {e}"
        if [list(x) for x in got] != want:
            return False, f"merge({src}) = {got}，期望 {want}"
    return True, "5 组用例全过"


def _check_slug(d: Path):
    import importlib.util
    p = d / "slug.py"
    if not p.exists():
        return False, "缺 slug.py"
    spec = importlib.util.spec_from_file_location("slug", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    cases = [("Hello, World!", "hello-world"),
             ("  A__B  ", "a-b"),
             ("已经", ""),
             ("x1 y2", "x1-y2"),
             ("--a--b--", "a-b")]
    for src, want in cases:
        try:
            got = m.slugify(src)
        except Exception as e:
            return False, f"slugify({src!r}) 抛 {type(e).__name__}: {e}"
        if got != want:
            return False, f"slugify({src!r}) = {got!r}，期望 {want!r}"
    return True, "5 组用例全过"


def _check_duration(d: Path):
    import importlib.util
    p = d / "dur.py"
    if not p.exists():
        return False, "缺 dur.py"
    spec = importlib.util.spec_from_file_location("dur", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    cases = [("1h30m", 5400), ("45s", 45), ("2m", 120), ("1h", 3600), ("1h2m3s", 3723)]
    for src, want in cases:
        try:
            got = m.parse_duration(src)
        except Exception as e:
            return False, f"parse_duration({src!r}) 抛 {type(e).__name__}: {e}"
        if got != want:
            return False, f"parse_duration({src!r}) = {got}，期望 {want}"
    try:
        m.parse_duration("abc")
        return False, "parse_duration('abc') 应该抛 ValueError，但没抛"
    except ValueError:
        pass
    except Exception as e:
        return False, f"parse_duration('abc') 抛了 {type(e).__name__}，要求是 ValueError"
    return True, "6 组用例全过"


# ---------- 高爆炸半径：跨文件改动 ----------

H_SEED = {
    "mod.py": "def old_name(x):\n    return x * 2\n",
    "app.py": "from mod import old_name\n\n\ndef run():\n    return old_name(21)\n",
}
H_OK = {
    "mod.py": "def new_name(x):\n    return x * 2\n",
    "app.py": "from mod import new_name\n\n\ndef run():\n    return new_name(21)\n",
}
H_BAD = {
    "mod.py": "def new_name(x):\n    return x * 2\n",
    "app.py": "from mod import old_name\n\n\ndef run():\n    return old_name(21)\n",
}


def _check_rename(d: Path):
    if any("old_name" in _read(d, f) for f in ("mod.py", "app.py")):
        return False, "旧名 old_name 还残留在文件里"
    for f in ("mod.py", "app.py"):
        if not (d / f).exists():
            return False, f"缺 {f}"
    import sys
    sys.path.insert(0, str(d))
    try:
        import app
        import mod
        if not hasattr(mod, "new_name"):
            return False, "mod.py 里没有 new_name"
        out = app.run()
    except Exception as e:
        return False, f"导入/调用失败：{type(e).__name__}: {e}"
    finally:
        sys.path.remove(str(d))
        for k in ("app", "mod"):
            sys.modules.pop(k, None)
    return (out == 42), f"app.run() = {out}，期望 42"


CFG_SEED = {"settings.json": json.dumps({
    "app": {"name": "demo", "debug": True, "retries": 3},
    "jobs": [{"id": 1, "debug": True}, {"id": 2, "debug": False}],
    "debug": True,
}, ensure_ascii=False, indent=2) + "\n"}
CFG_WANT = {
    "app": {"name": "demo", "debug": False, "retries": 3},
    "jobs": [{"id": 1, "debug": False}, {"id": 2, "debug": False}],
    "debug": False,
}


def _check_config(d: Path):
    p = d / "settings.json"
    if not p.exists():
        return False, "缺 settings.json"
    try:
        got = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"JSON 解析失败：{e}"
    if got != CFG_WANT:
        return False, f"内容不符：{json.dumps(got, ensure_ascii=False)[:120]}"
    return True, "三处 debug 全为 false，其它键未变"


MOV_SEED = {
    "a.py": "def helper(x):\n    return x + 1\n\n\ndef main():\n    return helper(1)\n",
    "b.py": "from a import helper\n\n\ndef twice():\n    return helper(helper(0))\n",
}
MOV_OK = {
    "util.py": "def helper(x):\n    return x + 1\n",
    "a.py": "from util import helper\n\n\ndef main():\n    return helper(1)\n",
    "b.py": "from util import helper\n\n\ndef twice():\n    return helper(helper(0))\n",
}
MOV_BAD = {
    "util.py": "def helper(x):\n    return x + 1\n",
    "a.py": "def helper(x):\n    return x + 1\n\n\ndef main():\n    return helper(1)\n",
    "b.py": "from a import helper\n\n\ndef twice():\n    return helper(helper(0))\n",
}


def _check_move(d: Path):
    if not (d / "util.py").exists():
        return False, "缺 util.py"
    a_src = _read(d, "a.py")
    if re.search(r"^def\s+helper\b", a_src, re.M):
        return False, "a.py 里还留着 helper 的定义（应已移到 util.py）"
    import sys
    sys.path.insert(0, str(d))
    try:
        import util
        if not hasattr(util, "helper"):
            return False, "util.py 里没有 helper"
        try:
            import a as a_mod
            if a_mod.main() != 2:
                return False, f"a.main() = {a_mod.main()}，期望 2"
            import b as b_mod
            if b_mod.twice() != 2:
                return False, f"b.twice() = {b_mod.twice()}，期望 2"
        except Exception as e:
            return False, f"导入/调用失败：{type(e).__name__}: {e}"
    finally:
        sys.path.remove(str(d))
        for k in ("util", "a", "b"):
            sys.modules.pop(k, None)
    return True, "helper 已移入 util，a/b 行为不变"


TASKS = []

for tid, prompt, expected in FACTS:
    TASKS.append({
        "id": tid, "cat": "fact", "prompt": prompt,
        "seed": {}, "ok": {"answer.txt": expected + "\n"},
        "bad": {"answer.txt": "wrong\n"}, "check": _exact(expected),
    })

TASKS += [
    {"id": "C01", "cat": "compose",
     "prompt": ("写 `intervals.py`，实现 `merge(intervals)`：输入若干闭区间 `[a, b]`，"
                "合并所有重叠或相邻（`next.start <= cur.end`）的区间，返回按起点升序的列表；"
                "空输入返回空列表；不要修改输入。"),
     "seed": {},
     "ok": {"intervals.py": "def merge(xs):\n    out = []\n    for a, b in sorted([list(x) for x in xs]):\n        if out and a <= out[-1][1]:\n            out[-1][1] = max(out[-1][1], b)\n        else:\n            out.append([a, b])\n    return out\n"},
     "bad": {"intervals.py": "def merge(xs):\n    return [list(x) for x in xs]\n"},
     "check": _check_intervals},
    {"id": "C02", "cat": "compose",
     "prompt": ("写 `slug.py`，实现 `slugify(text)`：转小写；只保留 `a-z0-9`，其它字符变 `-`；"
                "连续 `-` 合并成一个；去掉首尾 `-`；非 ASCII 字母按「其它字符」处理。"),
     "seed": {},
     "ok": {"slug.py": "import re\n\n\ndef slugify(text):\n    s = re.sub(r'[^a-z0-9]+', '-', str(text).lower())\n    return s.strip('-')\n"},
     "bad": {"slug.py": "def slugify(text):\n    return str(text).lower().replace(' ', '-')\n"},
     "check": _check_slug},
    {"id": "C03", "cat": "compose",
     "prompt": ("写 `dur.py`，实现 `parse_duration(s)`：把 `1h30m`、`45s`、`2m`、`1h2m3s` 这类"
                "时长转成秒（整数）；非法输入（如 `abc`）抛 `ValueError`。"),
     "seed": {},
     "ok": {"dur.py": "import re\n\n\ndef parse_duration(s):\n    parts = re.findall(r'(\\d+)([hms])', str(s))\n    if not parts or ''.join(n + u for n, u in parts) != str(s):\n        raise ValueError(s)\n    mul = {'h': 3600, 'm': 60, 's': 1}\n    return sum(int(n) * mul[u] for n, u in parts)\n"},
     "bad": {"dur.py": "def parse_duration(s):\n    return int(str(s).rstrip('s') or 0)\n"},
     "check": _check_duration},
    {"id": "H01", "cat": "blast",
     "prompt": ("把 `old_name` 这个函数在**所有文件**里改名为 `new_name`（定义、导入、调用都要改），"
                "行为保持不变：`app.run()` 必须仍然返回 42。"),
     "seed": H_SEED, "ok": H_OK, "bad": H_BAD, "check": _check_rename},
    {"id": "H02", "cat": "blast",
     "prompt": ("`settings.json` 里所有 `\"debug\": true` 都要改成 `false`（包括嵌套对象和数组里的），"
                "其它键与结构一个都不许动。"),
     "seed": CFG_SEED, "ok": {"settings.json": json.dumps(CFG_WANT, ensure_ascii=False, indent=2) + "\n"},
     "bad": {"settings.json": CFG_SEED["settings.json"]}, "check": _check_config},
    {"id": "H03", "cat": "blast",
     "prompt": ("把 `a.py` 里的函数 `helper` 移到新文件 `util.py`，并让 `a.py`、`b.py` 都改成从 "
                "`util` 导入；行为不变（`a.main()` 返回 2，`b.twice()` 返回 2）。"),
     "seed": MOV_SEED, "ok": MOV_OK, "bad": MOV_BAD, "check": _check_move},
]

BY_ID = {t["id"]: t for t in TASKS}

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 4 and sys.argv[1] == "--check":
        t = BY_ID[sys.argv[2]]
        ok_, why = t["check"](Path(sys.argv[3]))
        print(("PASS " if ok_ else "FAIL ") + why)
        sys.exit(0 if ok_ else 1)
    if len(sys.argv) >= 2 and sys.argv[1] == "--list":
        for t in TASKS:
            print(t["id"], t["cat"])
        sys.exit(0)
    print("用法：python tasks.py --list | --check <id> <dir>")
