#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hard2.py — 难度轴补充 6 题（机械精确类：格式化/舍入/Unicode/多规则转换/解析/稳定性）

设计原则：**判真值必须是机械的**（精确串、精确结构、稳定序），不引入主观评分。
这 6 题盯的是小模型最容易「看起来对、其实差一点」的地方。
"""
from __future__ import annotations

import json
from pathlib import Path


def _read(d: Path, name: str) -> str:
    p = d / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ---------- N01：读 CSV 出严格格式报告 ----------

N01_SEED = {
    "data/sales.csv": (
        "id,sku,qty,price\n"
        "1,A,2,10.00\n"
        "2,B,1,5.50\n"
        "1,A,2,10.00\n"
        "3,C,3,2.50\n"
        "4,D,1,19.99\n"),
}
N01_OK = {"report.md": "rows=4\nunits=7\nrevenue=52.99\ntop=A\n"}
N01_BAD = {"report.md": "rows=5\nunits=9\nrevenue=65.99\ntop=A\n"}


def _check_n01(d: Path):
    got = _read(d, "report.md")
    want = N01_OK["report.md"]
    if got.strip() != want.strip():
        return False, f"报告不符：拿到 {got.strip()[:120]!r}"
    return True, "四行严格一致"


# ---------- N02：四舍五入（half away from zero） ----------

N02_SEED = {}


def _check_n02(d: Path):
    import importlib.util
    p = d / "rounding.py"
    if not p.exists():
        return False, "缺 rounding.py"
    spec = importlib.util.spec_from_file_location("rounding", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    cases = [(2.675, 2, 2.68), (1.005, 2, 1.01), (0.5, 0, 1.0),
             (2.5, 0, 3.0), (-2.675, 2, -2.68), (1.4999, 2, 1.5)]
    for x, n, want in cases:
        try:
            got = m.round_half_up(x, n)
        except Exception as e:
            return False, f"round_half_up({x}, {n}) 抛 {type(e).__name__}: {e}"
        if abs(float(got) - want) > 1e-9:
            return False, f"round_half_up({x}, {n}) = {got}，期望 {want}"
    return True, "6 组（含 2.675/1.005/负数）全过"


# ---------- N03：Unicode 归一化 ----------

N03_SEED = {}


def _check_n03(d: Path):
    import importlib.util
    p = d / "norm.py"
    if not p.exists():
        return False, "缺 norm.py"
    spec = importlib.util.spec_from_file_location("normname", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    cases = [
        ("Ｈｅｌｌｏ　Ｗｏｒｌｄ", "Hello World"),
        ("A\u200bB", "AB"),
        ("A\u00a0B", "A B"),
        ("  a   b ", "a b"),
        ("①", "1"),
    ]
    for src, want in cases:
        try:
            got = m.normalize_name(src)
        except Exception as e:
            return False, f"normalize_name({src!r}) 抛 {type(e).__name__}: {e}"
        if got != want:
            return False, f"normalize_name({src!r}) = {got!r}，期望 {want!r}"
    return True, "5 组（全角/零宽/NBSP/连空白/圈号）全过"


# ---------- N04：多规则 JSON 转换 ----------

N04_ROWS = [
    {"id": 3, "name": "beta", "created": 1704153600, "amount_cents": 1999, "status": "paid"},
    {"id": 1, "name": "alpha", "created": 1704153600, "amount_cents": 500, "status": "paid"},
    {"id": 2, "name": "gamma", "created": 1704240000, "amount_cents": 1234, "status": "void"},
    {"id": 4, "name": "delta", "created": 1703980800, "amount_cents": 999, "status": "paid"},
]
N04_WANT = {
    "count": 3,
    "items": [
        {"id": 4, "name": "delta", "created": "2023-12-31", "amount": "9.99", "status": "paid"},
        {"id": 1, "name": "alpha", "created": "2024-01-02", "amount": "5.00", "status": "paid"},
        {"id": 3, "name": "beta", "created": "2024-01-02", "amount": "19.99", "status": "paid"},
    ],
}
N04_SEED = {"data/orders.json": json.dumps(N04_ROWS, ensure_ascii=False, indent=2) + "\n"}
N04_OK = {"result.json": json.dumps(N04_WANT, ensure_ascii=False, indent=2) + "\n"}
N04_BAD = {"result.json": json.dumps({"count": 4, "items": N04_ROWS}, ensure_ascii=False) + "\n"}


def _check_n04(d: Path):
    p = d / "result.json"
    if not p.exists():
        return False, "缺 result.json"
    try:
        got = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"JSON 解析失败：{e}"
    if got != N04_WANT:
        return False, f"内容不符：{json.dumps(got, ensure_ascii=False)[:180]}"
    return True, "7 条规则全对（丢 void/日期/金额/排序/计数/改名）"


# ---------- N05：日志行解析 ----------

N05_SEED = {}


def _check_n05(d: Path):
    import importlib.util
    p = d / "parse_log.py"
    if not p.exists():
        return False, "缺 parse_log.py"
    spec = importlib.util.spec_from_file_location("parselog", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    line1 = ('203.0.113.9 - - [10/Oct/2024:13:55:36 +0000] '
             '"GET /a/b?c=1 HTTP/1.1" 200 1234')
    line2 = ('198.51.100.7 - - [10/Oct/2024:13:55:37 +0000] '
             '"POST /submit HTTP/1.1" 404 -')
    want1 = {"ip": "203.0.113.9", "method": "GET", "path": "/a/b?c=1",
             "status": 200, "bytes": 1234}
    want2 = {"ip": "198.51.100.7", "method": "POST", "path": "/submit",
             "status": 404, "bytes": None}
    for line, want in ((line1, want1), (line2, want2)):
        try:
            got = m.parse_line(line)
        except Exception as e:
            return False, f"parse_line 抛 {type(e).__name__}: {e}"
        if not isinstance(got, dict):
            return False, f"parse_line 返回 {type(got).__name__}，要求 dict"
        for k, v in want.items():
            if got.get(k) != v:
                return False, f"{k} = {got.get(k)!r}，期望 {v!r}"
    return True, "两条（含 '-' 字节）全对"


# ---------- N06：稳定 top-k ----------

N06_SEED = {}


def _check_n06(d: Path):
    import importlib.util
    p = d / "topk.py"
    if not p.exists():
        return False, "缺 topk.py"
    spec = importlib.util.spec_from_file_location("topk", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception as e:
        return False, f"导入失败：{type(e).__name__}: {e}"
    items = [("a", 1), ("b", 3), ("c", 2), ("d", 3), ("e", 1)]
    try:
        got = m.top_k(items, 3, key=lambda t: t[1])
    except Exception as e:
        return False, f"top_k 抛 {type(e).__name__}: {e}"
    if list(got) != [("b", 3), ("d", 3), ("c", 2)]:
        return False, f"top_k = {got}，期望 [('b',3),('d',3),('c',2)]（同值保原序）"
    if list(m.top_k(items, 0, key=lambda t: t[1])) != []:
        return False, "k=0 应返回 []"
    if len(list(m.top_k(items, 99, key=lambda t: t[1]))) != 5:
        return False, "k>len 应返回全部"
    return True, "稳定性/k=0/k>len 全过"


TASKS = [
    {"id": "N01", "cat": "mechanical",
     "prompt": ("读 `data/sales.csv`（列：id,sku,qty,price），生成 `report.md`，**只输出下面四行**，"
                "不要标题、代码块、任何多余文字：\n"
                "```\nrows=<行数>\nunits=<qty 合计>\nrevenue=<qty*price 合计，两位小数>\ntop=<revenue 最大的 sku>\n```\n"
                "去重规则：`id` 相同的行只保留**第一次出现**的那行。"),
     "seed": N01_SEED, "ok": N01_OK, "bad": N01_BAD, "check": _check_n01},
    {"id": "N02", "cat": "mechanical",
     "prompt": ("写 `rounding.py`，实现 `round_half_up(x, n)`：按 **half away from zero** 舍入到 n 位小数"
                "（`2.675`→`2.68`、`1.005`→`1.01`、`-2.675`→`-2.68`），返回 float。⛔ 不要用内建 round 了事。"),
     "seed": N02_SEED,
     "ok": {"rounding.py": ("from decimal import Decimal, ROUND_HALF_UP\n\n\n"
                            "def round_half_up(x, n):\n"
                            "    q = Decimal(1).scaleb(-n)\n"
                            "    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))\n")},
     "bad": {"rounding.py": "def round_half_up(x, n):\n    return round(x, n)\n"},
     "check": _check_n02},
    {"id": "N03", "cat": "mechanical",
     "prompt": ("写 `norm.py`，实现 `normalize_name(s)`：① 删除零宽字符（U+200B/200C/200D/FEFF）；"
                "② 做 NFKC 归一化（全角→半角、①→1）；③ 把连续空白（含 NBSP U+00A0）合并成一个普通空格；"
                "④ 去首尾空白；**不改变大小写**。"),
     "seed": N03_SEED,
     "ok": {"norm.py": ("import re\nimport unicodedata\n\n"
                        "ZW = dict.fromkeys(map(ord, '\\u200b\\u200c\\u200d\\ufeff'))\n\n\n"
                        "def normalize_name(s):\n"
                        "    s = str(s).translate(ZW)\n"
                        "    s = unicodedata.normalize('NFKC', s)\n"
                        "    s = re.sub(r'\\s+', ' ', s)\n"
                        "    return s.strip()\n")},
     "bad": {"norm.py": "def normalize_name(s):\n    return str(s).strip()\n"},
     "check": _check_n03},
    {"id": "N04", "cat": "mechanical",
     "prompt": ("读 `data/orders.json`（数组），生成 `result.json`：\n"
                "① 丢掉 `status == \"void\"` 的记录；② `amount_cents` 改成 `amount`（元，**字符串**，两位小数，如 `\"5.00\"`）；"
                "③ `created`（epoch 秒）改成 UTC 日期字符串 `YYYY-MM-DD`；④ 按 `created` 升序、同日期按 `id` 升序；"
                "⑤ 输出对象 `{\"count\": <条数>, \"items\": [...]}`；⑥ **其余字段原样保留**（`status` 等都要留）；"
                "⑦ 输出 2 空格缩进 JSON。"),
     "seed": N04_SEED, "ok": N04_OK, "bad": N04_BAD, "check": _check_n04},
    {"id": "N05", "cat": "mechanical",
     "prompt": ("写 `parse_log.py`，实现 `parse_line(line)` → dict，键为 `ip`(str)、`method`(str)、`path`(str)、"
                "`status`(int)、`bytes`(int，原始是 `-` 时为 None)。输入是标准 nginx access log 一行，"
                "例如：\n`203.0.113.9 - - [10/Oct/2024:13:55:36 +0000] \"GET /a/b?c=1 HTTP/1.1\" 200 1234`"),
     "seed": N05_SEED,
     "ok": {"parse_log.py": ("import re\n\n"
                             "PAT = re.compile(r'^(\\S+) \\S+ \\S+ \\[[^\\]]*\\] \"(\\S+) (\\S+) [^\"]*\" (\\d{3}) (\\S+)')\n\n\n"
                             "def parse_line(line):\n"
                             "    m = PAT.match(str(line).strip())\n"
                             "    if not m:\n"
                             "        raise ValueError(line)\n"
                             "    ip, method, path, status, nbytes = m.groups()\n"
                             "    return {'ip': ip, 'method': method, 'path': path,\n"
                             "            'status': int(status),\n"
                             "            'bytes': None if nbytes == '-' else int(nbytes)}\n")},
     "bad": {"parse_log.py": ("def parse_line(line):\n"
                              "    p = str(line).split()\n"
                              "    return {'ip': p[0], 'method': p[5], 'path': p[6],\n"
                              "            'status': int(p[8]), 'bytes': int(p[9])}\n")},
     "check": _check_n05},
    {"id": "N06", "cat": "mechanical",
     "prompt": ("写 `topk.py`，实现 `top_k(items, k, key)`：按 `key(item)` **降序**返回前 k 个；"
                "**同 key 必须保持原有相对顺序**（稳定）；`k <= 0` 返回 `[]`；`k > len(items)` 返回全部。"
                "返回 list，不修改输入。"),
     "seed": N06_SEED,
     "ok": {"topk.py": ("def top_k(items, k, key=lambda x: x):\n"
                        "    if k <= 0:\n"
                        "        return []\n"
                        "    idx = sorted(range(len(items)), key=lambda i: (-key(items[i]), i))\n"
                        "    return [items[i] for i in idx[:k]]\n")},
     "bad": {"topk.py": ("def top_k(items, k, key=lambda x: x):\n"
                         "    return sorted(items, key=key)[::-1][:k] if k > 0 else []\n")},
     "check": _check_n06},
]

BY_ID = {t["id"]: t for t in TASKS}


# ---------- 第三把尺：期望值由独立实现从种子数据算出来 ----------
# 由来（2026-10-21 筛题实测）：N04 连续两次判「模型错」，其实是我手写的期望错了；
# 「两把尺」（正解绿/错解红）抓不到作者自洽的错误。凡**可计算**的题，期望值必须算，不许手写。

def _oracle_n01(seed: dict) -> str:
    import csv
    import io
    rows = list(csv.DictReader(io.StringIO(seed["data/sales.csv"])))
    seen, uniq = set(), []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        uniq.append(r)
    units = sum(int(r["qty"]) for r in uniq)
    rev = sum(int(r["qty"]) * float(r["price"]) for r in uniq)
    top = max(uniq, key=lambda r: int(r["qty"]) * float(r["price"]))["sku"]
    return f"rows={len(uniq)}\nunits={units}\nrevenue={rev:.2f}\ntop={top}\n"


def _oracle_n04(seed: dict) -> str:
    import datetime as _dt
    rows = json.loads(seed["data/orders.json"])
    items = []
    for r in rows:
        if r["status"] == "void":
            continue
        items.append({
            "id": r["id"], "name": r["name"],
            "created": _dt.datetime.fromtimestamp(r["created"], _dt.timezone.utc).strftime("%Y-%m-%d"),
            "amount": f"{r['amount_cents'] / 100:.2f}",
            "status": r["status"],
        })
    items.sort(key=lambda x: (x["created"], x["id"]))
    return json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=2) + "\n"


ORACLES = {
    "N01": (_oracle_n01, "report.md"),
    "N04": (_oracle_n04, "result.json"),
}
