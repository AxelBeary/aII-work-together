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
import hard4 as H4

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


# ---------- B 批变异体 ----------


def _b01_literal() -> dict:
    """正解 + 把所有调用点改成写死 4（env 换成别的值时不跟着变）。"""
    files = H4._b01_ok()
    for i in range(1, H4.B01_HANDLERS + 1):
        parts = ["from svc.core import fetch", "from svc.config import cfg"]
        for j in range(1, H4.B01_CALLS_PER + 1):
            parts.append(f"def h{i:02d}_{j:02d}():\n"
                         f'    return fetch("https://example.com/{i}/{j}", retries=4)\n')
        files[f"svc/handlers/h{i:02d}.py"] = "\n\n".join(parts) + "\n"
    return files


def _b02_constant() -> dict:
    """环没了，但行为被改成一律返回 8。"""
    files = H4._b02_ok()
    files["pkg/chain.py"] = "N = 8\n\n\ndef f(i, x):\n    return 8\n"
    return files


def _b03_appendix() -> dict:
    """正解 + 把附录里的 TODO 也改了。"""
    text = H4._b03_ok()["spec.md"]
    out, in_app = [], False
    for ln in text.splitlines():
        if ln.strip() == "## 附录":
            in_app = True
            out.append(ln)
            continue
        out.append(ln.replace("TODO:", "DONE:", 1) if in_app and ln.startswith("TODO:") else ln)
    return {"spec.md": "\n".join(out) + "\n"}


def _b03_code() -> dict:
    """正解 + 把代码块里的 TODO 也改了。"""
    text = H4._b03_ok()["spec.md"]
    out, in_code = [], False
    for ln in text.splitlines():
        if ln.startswith("```"):
            in_code = not in_code
            out.append(ln)
            continue
        out.append(ln.replace("TODO", "DONE") if in_code else ln)
    return {"spec.md": "\n".join(out) + "\n"}


VARIANTS = {
    "C01": [("相邻区间不合并", C01_V1)],    "C04": [("不认 \"\" 转义", C04_V1)],
    "N02": [("改用银行家舍入", N02_V1)],
    "N04": [("不丢 void 记录", _n04_v1())],
    "L01": [("旧类型 t39 被顺手改费率", _l01_v1())],
    "L02": [("代码块里的行也被改", _l02_v1())],
    # ---- 第二批（2026-10-22）：把「格式/边界」类判据也各破一条 ----
    "N01": [("只把 top 写错", {"report.md": "rows=4\nunits=7\nrevenue=52.99\ntop=B\n"})],
    "C02": [("连续分隔符不合并", {"slug.py": (
        "import re\n\n\n"
        "def slugify(text):\n"
        "    s = re.sub(r'[^a-z0-9]', '-', str(text).lower())\n"
        "    return s.strip('-')\n")})],
    "C05": [("零单位不省略（60s 写成 1m 0s）", {"fmt.py": (
        "def fmt_duration(seconds):\n"
        "    n = int(seconds)\n"
        "    if n < 0:\n"
        "        raise ValueError(seconds)\n"
        "    h, rem = divmod(n, 3600)\n"
        "    m, s = divmod(rem, 60)\n"
        "    parts = []\n"
        "    if h:\n"
        "        parts.append(f'{h}h')\n"
        "    if m:\n"
        "        parts.append(f'{m}m')\n"
        "    if h or m or True:\n"
        "        parts.append(f'{s}s')\n"
        "    return ' '.join(parts) if parts else '0s'\n")})],
    "N05": [("'-' 不转成 None（原样返回字符串）", {"parse_log.py": (
        "import re\n\n"
        "PAT = re.compile(r'^(\\S+) \\S+ \\S+ \\[[^\\]]*\\] \"(\\S+) (\\S+) [^\"]*\" (\\d{3}) (\\S+)')\n\n\n"
        "def parse_line(line):\n"
        "    m = PAT.match(str(line).strip())\n"
        "    if not m:\n"
        "        raise ValueError(line)\n"
        "    ip, method, path, status, nbytes = m.groups()\n"
        "    return {'ip': ip, 'method': method, 'path': path, 'status': int(status),\n"
        "            'bytes': nbytes if nbytes == '-' else int(nbytes)}\n")})],
    "H06": [("改名字段没做（仍叫 code）", {"merged.json": (
        '[{"id": 3, "ts": 150, "code": "a", "price": 9},\n'
        ' {"id": 1, "ts": 300, "code": "b2", "price": 7}]\n')})],
    # H05 是三处独立 bug：按规矩 24，每一处各登记一个变异点（「ok 减去这一条」，
    # ⛔ 不是「seed 加上这一条」——后者会被前面的断言先拦下，后面的条件其实没被验证过）
    "H05": [
        ("只有可变默认参数没修", {"stats.py": (
            "def add(items, x, acc=[]):\n"
            "    acc.append(x)\n"
            "    return acc\n\n\n"
            "def mean(xs):\n"
            "    xs = list(xs)\n"
            "    return (sum(xs) / len(xs)) if xs else None\n\n\n"
            "def approx(a, b):\n"
            "    return abs(a - b) <= 1e-9\n")}),
        ("只有 mean 空列表没修（返回 0）", {"stats.py": (
            "def add(items, x, acc=None):\n"
            "    acc = [] if acc is None else acc\n"
            "    acc.append(x)\n"
            "    return acc\n\n\n"
            "def mean(xs):\n"
            "    xs = list(xs)\n"
            "    return (sum(xs) / len(xs)) if xs else 0\n\n\n"
            "def approx(a, b):\n"
            "    return abs(a - b) <= 1e-9\n")}),
        ("只有浮点比较没修", {"stats.py": (
            "def add(items, x, acc=None):\n"
            "    acc = [] if acc is None else acc\n"
            "    acc.append(x)\n"
            "    return acc\n\n\n"
            "def mean(xs):\n"
            "    xs = list(xs)\n"
            "    return (sum(xs) / len(xs)) if xs else None\n\n\n"
            "def approx(a, b):\n"
            "    return a == b\n")}),
    ],
    # ---- B 批（2026-10-22）：每题各破一条独立条件 ----
    "B01": [("调用点写死常数 4（不读 cfg）", _b01_literal())],
    "B02": [("无环了但行为被改（恒返回 8）", _b02_constant())],
    "B03": [("附录里的 TODO 也改了", _b03_appendix()),
            ("代码块里的 TODO 也改了", _b03_code())],
}
