#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — 看板页渲染（单项目 + 多项目总览）

两种视图：
  render_project(root)  → 单个项目的看板页（board/board.html）
  render_all()          → 跨项目总览（~/.aII-work-together/overview.html）

设计原则：
  · 纯静态 HTML，零依赖、零服务器；双击即看，30 秒自动刷新
  · 深色、低对比、信息密度高——单人长时间盯着看不累
  · 每个项目一个色标，一眼分清
"""
import json
from datetime import datetime
from pathlib import Path

COLS = ["待认领", "进行中", "待返工", "阻塞", "待验收", "核验中", "拍板中", "完成"]

CSS = """
:root{--bg:#0f1115;--fg:#e6e8eb;--mut:#8b929e;--card:#191c22;--line:#2a2f38;--acc:#4a9eff;
--ok:#3fb950;--warn:#d29922;--err:#f85149}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.55 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{padding:16px 24px;border-bottom:1px solid var(--line);
display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:600}
.sub{color:var(--mut);font-size:12px}
.nav{margin-left:auto;display:flex;gap:10px;font-size:12px}
.nav a{color:var(--acc);text-decoration:none}
.board{display:flex;gap:12px;padding:16px 24px;overflow-x:auto;align-items:flex-start}
.col{flex:0 0 250px;background:#14161b;border:1px solid var(--line);border-radius:10px}
.ch{padding:10px 13px;font-weight:600;font-size:13px;border-bottom:1px solid var(--line);
display:flex;justify-content:space-between;align-items:center}
.cn{color:var(--mut);font-weight:400;font-size:12px}
.cb{padding:9px;display:flex;flex-direction:column;gap:8px;min-height:36px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 11px}
.id{font-size:11px;color:var(--acc);font-family:ui-monospace,Consolas,monospace}
.title{font-weight:600;margin:3px 0 5px;font-size:13px}
.goal{color:var(--mut);font-size:12px;margin-bottom:5px}
.blk{color:var(--warn);font-size:12px;margin-bottom:5px}
.meta{display:flex;gap:6px;flex-wrap:wrap;font-size:11px;color:var(--mut);align-items:center}
.hold{background:#1e3a5f;color:#8cc4ff;padding:1px 7px;border-radius:20px}
.gate{background:#5f3a1e;color:#ffc98c;padding:1px 7px;border-radius:20px}
.rw{background:#5f1e1e;color:#ff9c9c;padding:1px 7px;border-radius:20px}
.aib{background:#1e5f3a;color:#8cffb4;padding:1px 6px;border-radius:20px;font-size:10px}
.spec{display:flex;gap:4px;flex-wrap:wrap;margin:4px 0}
.eng,.mdl,.eff{background:#2a2f38;color:#a9b4c4;padding:1px 6px;border-radius:4px;
font-size:10px;font-family:ui-monospace,Consolas,monospace}
.empty{color:#3a4048;text-align:center;padding:10px;font-size:12px}
footer{padding:12px 24px;color:var(--mut);font-size:11px;border-top:1px solid var(--line)}
/* 总览 */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;padding:20px 24px}
.pcard{background:#14161b;border:1px solid var(--line);border-radius:10px;padding:14px;
border-left:3px solid var(--acc)}
.pname{font-weight:600;font-size:14px;margin-bottom:2px}
.ppath{color:var(--mut);font-size:11px;font-family:ui-monospace,Consolas,monospace;
word-break:break-all;margin-bottom:10px}
.bars{display:flex;flex-direction:column;gap:4px}
.bar{display:flex;align-items:center;gap:8px;font-size:11px}
.bl{width:52px;color:var(--mut)}
.bt{flex:1;height:6px;background:#22262e;border-radius:4px;overflow:hidden}
.bf{height:100%;border-radius:4px}
.bn{width:26px;text-align:right;color:var(--mut)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}
"""


def _card_html(c):
    hold = f"<span class=hold>{_esc(c['holder'])}</span>" if c.get("holder") else ""
    gate = "<span class=gate>人闸</span>" if c.get("gate") in ("both", "before_done") else ""
    rw = f"<span class=rw>返工 {c['rework']}</span>" if c.get("rework") else ""
    goal = f"<div class=goal>{_esc(c.get('goal', ''))[:110]}</div>" if c.get("goal") else ""
    blk = f"<div class=blk>{_esc(c.get('blocked_reason') or '')[:80]}</div>" \
        if c.get("blocked_reason") else ""
    spec = []
    if c.get("engine", "any") != "any":
        spec.append(f"<span class=eng>{_esc(c['engine'])}</span>")
    if c.get("model", "any") != "any":
        spec.append(f"<span class=mdl>{_esc(c['model'].split('/')[-1])}</span>")
    if c.get("effort", "any") != "any":
        spec.append(f"<span class=eff>{_esc(c['effort'])}</span>")
    spec_html = f"<div class=spec>{''.join(spec)}</div>" if spec else ""
    ai = "<span class=aib>AI</span>" if c.get("created_kind") == "agent" else ""
    dl = "".join(f"<li>{_esc(x if isinstance(x, str) else x.get('path'))}</li>"
                 for x in (c.get("deliverables") or [])[:3])
    dls = f"<ul class=dl>{dl}</ul>" if dl else ""
    return (f"<div class=card><div class=id>{_esc(c['id'])} {ai}</div>"
            f"<div class=title>{_esc(c['title'])}</div>{spec_html}{goal}{blk}{dls}"
            f"<div class=meta>{hold}{gate}{rw}"
            f"<span class=ev>{c.get('events', 0)} 事件</span></div></div>")


def _esc(s):
    # 2026-10-21（安全扫描 F-17）：补单双引号，供未来在属性位复用；⛔ 别只转 &<>。
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def render_project(cards: list, title: str, out_path: Path,
                   project_name: str = "", has_overview: bool = False) -> Path:
    by = {c: [x for x in cards if x.get("state") == c] for c in COLS}
    body = ""
    for col in COLS:
        items = by[col]
        if not items and col in ("核验中", "拍板中"):
            continue
        inner = "".join(_card_html(c) for c in items) or "<div class=empty>—</div>"
        body += (f"<div class=col><div class=ch>{col}"
                 f"<span class=cn>{len(items)}</span></div>"
                 f"<div class=cb>{inner}</div></div>")
    nav = ""
    if has_overview:
        nav = ('<div class=nav><a href="file:///' +
               str(Path.home() / ".aII-work-together" / "overview.html").replace("\\", "/") +
               '">全部项目 →</a></div>')
    html = f"""<!doctype html><html lang=zh><meta charset=utf-8>
<title>{_esc(title)}</title><meta http-equiv=refresh content=30>
<style>{CSS}</style>
<header><h1>{_esc(project_name or title)}</h1>
<span class=sub>{len(cards)} 张卡 · 30s 自动刷新</span>{nav}</header>
<div class=board>{body}</div>
<footer>生成于 {_now()} ｜ 真相源：board/cards/*/journal.jsonl</footer>
</html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


# 状态配色（总览用）
STATE_COLOR = {
    "待认领": "#4a9eff", "进行中": "#d29922", "待返工": "#f85149",
    "阻塞": "#8b949e", "待验收": "#a371f7", "核验中": "#3fb950",
    "拍板中": "#db6d28", "完成": "#2ea043", "已取消": "#484f58",
}


def render_all(projects: list, out_path: Path) -> Path:
    """跨项目总览。projects = [{name, path, cards, states, exists}]"""
    total_cards = sum(p.get("cards", 0) for p in projects)
    total_done = sum(p.get("states", {}).get("完成", 0) for p in projects)
    blocks = ""
    for p in projects:
        if not p.get("exists"):
            blocks += (f"<div class=pcard style='border-left-color:{STATE_COLOR['已取消']}'>"
                       f"<div class=pname>✗ {_esc(p['name'])}</div>"
                       f"<div class=ppath>{_esc(p['path'])}（目录不存在）</div></div>")
            continue
        bars = ""
        for st in COLS:
            n = p.get("states", {}).get(st, 0)
            if not n:
                continue
            pct = n / max(p["cards"], 1) * 100
            bars += (f"<div class=bar><span class=bl>{st}</span>"
                     f"<span class=bt><span class=bf style='width:{pct:.0f}%;"
                     f"background:{STATE_COLOR.get(st, '#4a9eff')}'></span></span>"
                     f"<span class=bn>{n}</span></div>")
        link = (Path(p["path"]) / "board" / "board.html").as_uri()
        blocks += (f"<div class=pcard><div class=pname>"
                   f"<span class=dot style='background:{STATE_COLOR.get('进行中')}'></span>"
                   f"<a href='{link}' style='color:inherit;text-decoration:none'>"
                   f"{_esc(p['name'])}</a></div>"
                   f"<div class=ppath>{_esc(p['path'])}</div>"
                   f"<div class=bars>{bars or '<span class=empty>暂无卡片</span>'}</div>"
                   f"</div>")
    html = f"""<!doctype html><html lang=zh><meta charset=utf-8>
<title>全部项目</title><meta http-equiv=refresh content=30>
<style>{CSS}</style>
<header><h1>全部项目</h1>
<span class=sub>{len(projects)} 个项目 · {total_cards} 张卡 · 完成 {total_done}</span></header>
<div class=grid>{blocks}</div>
<footer>生成于 {_now()} ｜ 注册表：~/.aII-work-together/projects.json</footer>
</html>"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
