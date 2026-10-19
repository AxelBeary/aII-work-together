#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
consult.py — 点对点评审：B 干完活，找 B1/B2 独立提意见，B 自己改

为什么不是「聊天室」：
  · 聊天室没有结束条件，会一直对话烧钱；这里一次评审有明确的输入输出
  · 翻译/写作最怕术语串味：评审席**只准看、不准改**，写权只属于卡主
  · 每条意见都落成卡片事件 + 磁盘证据，事后能查「当时凭什么这么定」

评审席可以是不同的引擎/提供商（真正的异构意见）：
  --by "b1:opencode:claudecodesale/claude-opus-5-5,b2:qoderclicn:"

安全约束（实测必要）：
  评审开始前给每个交付文件拍字节快照；结束后逐字节比对。
  只要有一个文件被改动 ⇒ 立刻从快照恢复原字节 + 记为 VIOLATION。
  理由是评审席拿的是完整文件内容，模型完全可能「顺手改一下」。

对外接口：
  consult(card_id, question, reviewers, files=None, role="generic", ...)
    -> {"replies": [...], "packet": str, "violations": [...]}
"""
import hashlib
import json
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B          # noqa: E402
import engines as E        # noqa: E402

MAX_INLINE_BYTES = 60000        # 超过这个大小就不内联全文，只给路径 + 摘要
DEFAULT_TIMEOUT = 900

# 评审席人格：决定「从哪个角度挑毛病」
PERSONAS = {
    "generic": (
        "你是独立评审。你的唯一职责是找出问题并给出可执行的修改建议。"
        "你**不要修改任何文件**，也不要输出完整重写稿；只说明「哪一处、为什么、改什么」。"
    ),
    "native": (
        "你是英文母语读者兼编辑，负责最终读感。"
        "标尺是：母语读者会不会这样写。有翻译腔本身就算缺陷。"
        "你**不要修改任何文件**；只指出具体位置、说明为什么不自然、给出你建议的说法。"
    ),
    "term": (
        "你是术语与一致性审校。检查：同一概念是否前后同一说法、"
        "是否符合给定术语/称呼、语域（正式/口语）是否在整段里保持一致。"
        "你**不要修改任何文件**；只列出不一致处与建议用词。"
    ),
    "faithful": (
        "你是逐句对照审校。检查：是否漏译、是否增译、是否把限定词/时态/人称改掉了、"
        "数字与专有名词是否准确。你**不要修改任何文件**；只列问题清单。"
    ),
}

REPLY_FORMAT = """\
请严格按这个格式回答（不要在格式之外加寒暄）：

VERDICT: pass 或 needs-work
PROBLEMS:
- 位置｜问题｜建议（每行一条，最多 12 条）
OK:
- 一句话说明哪些地方你认为不需要改
"""


# ---------- 评审席规格解析 ----------

def parse_reviewers(spec: str) -> list:
    """把 "b1:opencode:claudecodesale/claude-opus-5-5@native,b2:qoderclicn:" 解析成列表。

    格式：seat[:engine[:model[:effort]]][@role]，逗号分隔。
    模型名里可以有 `/`（provider/model），所以只按 `:` 切，最多 4 段。
    """
    out = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        role = None
        if "@" in part:
            part, role = part.rsplit("@", 1)
            role = role.strip() or None
            if role and role not in PERSONAS:
                raise ValueError(f"未知的评审角色：{role}（可选：{'/'.join(PERSONAS)}）")
        bits = part.split(":", 3)
        seat = bits[0].strip()
        if not seat:
            raise ValueError(f"评审席没名字：{part!r}")
        out.append({
            "seat": seat,
            "engine": (bits[1].strip() if len(bits) > 1 and bits[1].strip() else "opencode"),
            "model": (bits[2].strip() if len(bits) > 2 and bits[2].strip() else None),
            "effort": (bits[3].strip() if len(bits) > 3 and bits[3].strip() else None),
            "role": role,
        })
    if not out:
        raise ValueError("至少要有一个评审席（--by b1:opencode:…）")
    return out


# ---------- 快照（防止评审席改文件） ----------

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot(files: list) -> dict:
    snap = {}
    for f in files:
        p = Path(f)
        if not p.is_absolute():
            p = Path(B.WORKSPACE) / p
        if p.is_file():
            data = p.read_bytes()
            snap[str(p)] = {"bytes": data, "sha": _sha(data), "len": len(data)}
        else:
            snap[str(p)] = {"bytes": None, "sha": None, "len": 0}
    return snap


def check_and_restore(snap: dict) -> list:
    """比对并恢复被改动的文件；返回违规清单。"""
    bad = []
    for path, rec in snap.items():
        p = Path(path)
        if rec["bytes"] is None:
            if p.exists():
                bad.append(f"{p.name}：评审期间被新建（评审席不该写文件）")
            continue
        now = p.read_bytes() if p.exists() else b""
        if _sha(now) != rec["sha"]:
            p.write_bytes(rec["bytes"])          # 用我们手里的原字节恢复
            bad.append(f"{p.name}：评审期间被改动，已恢复原字节")
    return bad


# ---------- 提示词 ----------

def _material(files: list) -> str:
    chunks = []
    for f in files:
        p = Path(f)
        if not p.is_absolute():
            p = Path(B.WORKSPACE) / p
        if not p.is_file():
            chunks.append(f"### {f}\n（文件不存在）")
            continue
        data = p.read_bytes()
        if len(data) > MAX_INLINE_BYTES:
            chunks.append(
                f"### {p}\n（{len(data)} 字节，过大未内联；请直接读这个文件：{p}）")
        else:
            text = data.decode("utf-8", errors="replace")
            chunks.append(f"### {p}\n```\n{text}\n```")
    return "\n\n".join(chunks)


def build_prompt(card: dict, question: str, files: list,
                 role: str = "generic", round_no: int = 1) -> str:
    persona = PERSONAS.get(role, PERSONAS["generic"])
    parts = [
        persona,
        "",
        "## 背景",
        f"- 任务：{card.get('title','')}",
    ]
    if card.get("goal"):
        parts.append(f"- 目标：{card['goal']}")
    if card.get("accept_patterns"):
        parts.append(f"- 验收要求：{'；'.join(card['accept_patterns'])}")
    if question:
        parts += ["", "## 这一轮要你回答的问题", question]
    parts += ["", "## 材料", _material(files)]
    parts += ["", "## 输出格式", REPLY_FORMAT]
    parts += [
        "",
        "再次强调：**只输出意见，不要改文件，不要给完整重写稿。**",
        "材料已经完整贴在上面了，**不要去磁盘上到处找文件**，更不要整盘搜索"
        "（`dir /s`、`Get-ChildItem -Recurse E:\\` 这类会吃满 CPU，拖慢整台机器）。",
        f"（第 {round_no} 轮评审）",
    ]
    return "\n".join(parts)


def parse_reply(text: str) -> dict:
    verdict = None
    m = re.search(r"VERDICT\s*[:：]\s*([A-Za-z\-]+)", text or "")
    if m:
        v = m.group(1).lower()
        verdict = "pass" if v.startswith("pass") else "needs-work"
    problems = []
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("- ") and len(s) > 3:
            problems.append(s[2:].strip())
        if len(problems) >= 12:
            break
    return {"verdict": verdict, "problems": problems}


# ---------- 主流程 ----------

def consult(card_id: str, question: str, reviewers: list, files: list = None,
            role: str = "generic", round_no: int = 1,
            parallel: int = 3, timeout: int = DEFAULT_TIMEOUT,
            dry_run: bool = False, cwd: str = None) -> dict:
    card = B.require_card(card_id)
    base = Path(cwd or B.WORKSPACE)
    files = list(files or card.get("deliverables") or [])
    if not files:
        raise ValueError("没有可评审的文件：卡里没有 deliverables，也没给 --file")
    # 路径必须先验存在：否则评审席会对着「文件不存在」空评一轮，还给出一个看似正常的结论
    resolved, missing = [], []
    for f in files:
        p = Path(f) if Path(f).is_absolute() else base / f
        (resolved if p.is_file() else missing).append(str(p))
    if missing:
        raise ValueError(f"这些文件不存在，拒绝空评：{', '.join(missing)}")
    files = resolved

    snap = snapshot(files)
    # 每个评审席可以有自己的角度（b1@native, b2@faithful）；没写就用统一 role
    for rv in reviewers:
        rv["role"] = rv.get("role") or role
    prompt = build_prompt(card, question, files, role=role, round_no=round_no)

    B.append_event(card_id, {
        "type": "consult_request", "actor": "agent",
        "question": question, "role": role, "round": round_no,
        "reviewers": reviewers,
        "files": [{"path": k, "sha": v["sha"], "len": v["len"]}
                  for k, v in snap.items()],
    })

    if dry_run:
        return {"dry_run": True, "prompt": prompt, "reviewers": reviewers,
                "replies": [], "violations": [], "packet": "（dry-run，未调用任何模型）"}

    def _one(rv):
        t0 = time.time()
        p = build_prompt(card, question, files, role=rv["role"], round_no=round_no)
        res = E.run(rv["engine"], p, cwd=str(base),
                    model=rv.get("model"), effort=rv.get("effort"),
                    timeout=timeout)
        dt = time.time() - t0
        parsed = parse_reply(res.text or "")
        return {
            "seat": rv["seat"], "engine": rv["engine"], "model": rv.get("model"),
            "role": rv["role"], "ok": bool(res.ok), "reason": res.reason,
            "verdict": parsed["verdict"], "problems": parsed["problems"],
            "text": res.text or "", "seconds": round(dt, 1),
            "model_used": res.model_used or rv.get("model"),
            "session_id": res.session_id,
        }

    replies = []
    try:
        with ThreadPoolExecutor(max_workers=max(1, min(parallel, len(reviewers)))) as ex:
            futs = [ex.submit(_one, rv) for rv in reviewers]
            for f in futs:
                try:
                    replies.append(f.result())
                except Exception as e:
                    replies.append({"seat": "?", "ok": False, "reason": str(e),
                                    "text": "", "verdict": None, "problems": []})
    finally:
        # 无论成功失败都要比对文件：评审席不该改任何东西
        violations = check_and_restore(snap)

    ev_dir = Path(B.BOARD) / "evidence" / card_id
    ev_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%m%d-%H%M%S")
    for r in replies:
        r["violation"] = bool(violations)
        if r.get("text"):
            f = ev_dir / f"consult-{stamp}-{r['seat']}.md"
            f.write_text(
                f"# 评审：{r['seat']}（{r.get('model_used') or r['engine']}）\n\n"
                f"- 结论：{r.get('verdict')}\n- 耗时：{r.get('seconds')}s\n"
                f"- 是否违约改文件：{'是' if violations else '否'}\n\n"
                f"## 原文\n\n{r['text']}\n", encoding="utf-8")
            r["evidence"] = str(f)
        B.append_event(card_id, {
            "type": "consult_reply", "actor": "agent", "seat": r["seat"],
            "engine": r["engine"], "model": r.get("model_used"),
            "ok": r["ok"], "verdict": r.get("verdict"),
            "problems": len(r.get("problems") or []),
            "sha": _sha((r.get("text") or "").encode("utf-8"))[:16],
            "evidence": r.get("evidence"),
            "violation": r["violation"],
        })

    if violations:
        B.append_event(card_id, {"type": "consult_violation", "actor": "system",
                                 "detail": violations})
    return {"replies": replies, "violations": violations,
            "packet": render_packet(replies, files, violations)}


def render_packet(replies: list, files: list, violations: list) -> str:
    """把多份意见合成一段人话，给卡主（B）照着改。"""
    lines = []
    if violations:
        lines.append("⚠️ 评审席改了文件，已恢复原字节：")
        lines += [f"  - {v}" for v in violations]
        lines.append("")
    for r in replies:
        head = f"── {r['seat']}｜{r.get('model_used') or r['engine']}"
        if not r["ok"]:
            lines.append(f"{head}｜**调用失败**：{r.get('reason')}")
            continue
        v = r.get("verdict") or "未表态"
        lines.append(f"{head}｜{v}｜{r.get('seconds')}s｜{len(r.get('problems') or [])} 条意见")
        for p in (r.get("problems") or []):
            lines.append(f"  - {p}")
        lines.append("")
    verdicts = [r.get("verdict") for r in replies if r.get("ok")]
    if verdicts and all(v == "pass" for v in verdicts):
        lines.append("全部评审席都认为可以过 —— 你别急着改，先自己抽查两处。")
    elif verdicts:
        lines.append("有评审席提了意见：逐条判断，认同的改，不认同的**在提交凭据里写明为什么不改**。")
    lines.append(f"\n材料：{len(files)} 个文件；评审席：{len(replies)} 个")
    return "\n".join(lines)


if __name__ == "__main__":
    print(__doc__)
