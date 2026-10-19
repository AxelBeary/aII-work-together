# gate_l3 改动前留档（2026-10-20）

用途：复核席做代码级前后对照（全局规则 17：改造闸门前先留档旧件）。

当时 HEAD 的提交：d64c95f

```python
def gate_l3(cid: str, card: dict) -> tuple:
    """L3 内容闸门：派工单声明的必含项逐条断言 + 反空跑。"""
    problems, checks = [], []
    patterns = card.get("accept_patterns", [])
    text_cache = {}
    TEXTY = (".md", ".txt", ".py", ".json", ".yaml", ".yml", ".html", ".css", ".js", ".ts")
    for item in card.get("deliverables", []):
        rel = item if isinstance(item, str) else item.get("path")
        p = (WORKSPACE / rel) if not Path(rel).is_absolute() else Path(rel)
        if p.exists() and p.suffix.lower() in TEXTY:
            try:
                text_cache[rel] = p.read_text(encoding="utf-8")
            except Exception:
                pass
    for pat in patterns:
        hit = any(re.search(pat, t) for t in text_cache.values())
        checks.append({"pattern": pat, "hit": hit})
        if not hit:
            problems.append(f"必含项未命中：{pat}")
    # 反空跑（**无条件**执行）：交付物里必须有数字，否则视为空跑。
    # 例外：卡显式写 allow_no_numbers=true（如纯文字设计稿）。
    if text_cache and not card.get("allow_no_numbers"):
        has_num = any(re.search(r"\d", t) for t in text_cache.values())
        checks.append({"pattern": "<非零计数>", "hit": has_num})
        if not has_num:
            problems.append("反空跑失败：交付物里没有任何数字（若确实不需要数字，"
                            "在卡上设 allow_no_numbers=true）")
    return (len(problems) == 0), problems, checks
```
