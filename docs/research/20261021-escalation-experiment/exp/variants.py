#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""variants.py — 检查器的「单条件变异体」（全局规矩 24/28 在实验判据上的落地）

为什么要有它：
  `bad`（已知错误解）只证明「检查器对**一整份烂答案**有区分力」；
  它证明不了**每一条独立条件**都被真的检查了——很可能某条条件从来没生效，
  而 bad 恰好因为另一条条件挂掉。规矩 24 的说法是：**每个自由度的变异点各自打一次，
  每一次都必须各自挂掉自检**。

用法：由 `run_experiment.py --validate` 自动跑（不调模型，纯本地）。

纪律：
  - 每个变异体**只破一条**条件，其它全部正确。
  - 反控夹具不许「一次性全假」：一条变异体只让**单个子条件**为假。
"""
from __future__ import annotations

import json

import hard2 as H2
import hard3 as H3

# ---------- C01：只破「相邻区间合并」（a <= end vs a < end） ----------

C01_V1 = {
    "intervals.py": (
        "def merge(xs):\n"
        "    out = []\n"
        "    for a, b in sorted([list(x) for x in xs]):\n"
        "        if out and a < out[-1][1]:\n"          # ← 唯一缺陷：相邻不合并
        "            out[-1][1] = max(out[-1][1], b)\n"
        "        else:\n"
        "            out.append([a, b])\n"
        "    return out\n"),
}

# ---------- C04：只破 `""` 转义（其余引号/逗号逻辑都对） ----------

C04_V1 = {
    "csvline.py": (
        "def parse_csv_line(line):\n"
        "    out, cur, inq, i, s = [], '', False, 0, str(line)\n"
        "    while i < len(s):\n"
        "        ch = s[i]\n"
        "        if ch == '\"':\n"
        "            inq = not inq\n"                    # ← 唯一缺陷：不认 ""
        "            i += 1\n"
        "            continue\n"
        "        if ch == ',' and not inq:\n"
        "            out.append(cur)\n"
        "            cur = ''\n"
        "            i += 1\n"
        "            continue\n"
        "        cur += ch\n"
        "        i += 1\n"
        "    out.append(cur)\n"
        "    return out\n"),
}

# ---------- N02：只破「half away from zero」（换成银行家舍入） ----------

N02_V1 = {
    "rounding.py": (
        "from decimal import Decimal, ROUND_HALF_EVEN\n\n\n"
        "def round_half_up(x, n):\n"
        "    q = Decimal(1).scaleb(-n)\n"
        "    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_EVEN))\n"),
}

# ---------- N04：只破「丢掉 void」 ----------


def _n04_v1() -> dict:
    rows = json.loads(H2.N04_SEED["data/orders.json"])
    items = []
    for r in rows:                                   # ← 唯一缺陷：不丢 void
        items.append({
            "id": r["id"], "name": r["name"],
            "created": __import__("datetime").datetime.fromtimestamp(
                r["created"], __import__("datetime").timezone.utc).strftime("%Y-%m-%d"),
            "amount": f"{r['amount_cents'] / 100:.2f}",
            "status": r["status"],
        })
    items.sort(key=lambda x: (x["created"], x["id"]))
    return {"result.json": json.dumps({"count": len(items), "items": items},
                                      ensure_ascii=False, indent=2) + "\n"}


# ---------- L01：只破「旧类型回归」（t39 费率被顺手改了） ----------


def _l01_v1() -> dict:
    seed = H3._l01_seed()
    handlers = seed["handlers.py"].replace(
        "\n\nREGISTRY = {",
        "\n\ndef t40(amount):\n    return round(amount * 1.40, 2)\n\n\nREGISTRY = {")
    handlers = handlers.replace('    "t39": t39,\n}', '    "t39": t39,\n    "t40": t40,\n}')
    # ← 唯一缺陷：把 t39 的费率从 1.39 改成 1.40（43 处里只动这一处）
    handlers = handlers.replace("def t39(amount):\n    return round(amount * 1.39, 2)",
                                "def t39(amount):\n    return round(amount * 1.40, 2)")
    pipeline = seed["pipeline.py"].replace(
        '    return fn(rec["amount"])\n',
        '    out = fn(rec["amount"])\n'
        '    if rec.get("currency") == "JPY":\n'
        '        return int(out + 0.5) if out >= 0 else -int(-out + 0.5)\n'
        '    return out\n')
    return {"handlers.py": handlers, "pipeline.py": pipeline, "main.py": seed["main.py"]}


# ---------- L02：只破「代码块里的行不许动」 ----------


def _l02_v1() -> dict:
    lines = H3._l02_seed()["notes.md"].splitlines()
    out, in_code = [], False
    for ln in lines:
        if ln.startswith("```"):
            in_code = not in_code
            out.append(ln)
            continue
        if ln.startswith("## "):                       # ← 唯一缺陷：不分代码块，全改
            out.append("### " + ln[3:])
        else:
            out.append(ln)
    out += ["", "<!-- sections: 40 -->"]
    return {"notes.md": "\n".join(out) + "\n"}


VARIANTS = {
    "C01": [("相邻区间不合并", C01_V1)],
    "C04": [("不认 \"\" 转义", C04_V1)],
    "N02": [("改用银行家舍入", N02_V1)],
    "N04": [("不丢 void 记录", _n04_v1())],
    "L01": [("旧类型 t39 被顺手改费率", _l01_v1())],
    "L02": [("代码块里的行也被改", _l02_v1())],
}
