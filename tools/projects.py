#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
projects.py — 多项目注册表与根目录解析

设计取舍（2026-10-19）：
  · **数据跟项目走**：每个项目根目录下有一个 `board/`，卡片、日志、看板页都在里面。
    ⇒ 可 git、可搬、可单独备份，不需要中央数据库。
  · **全局只存「项目在哪」**：`~/.allworktogether/projects.json` 记 name→path。
    ⇒ 删掉注册表不影响任何项目的实际数据。
  · **零配置**：在任意目录跑 `board`，自动把当前目录识别为项目（首次自动登记）。

解析顺序（resolve_root）：
  1. 显式 --root / -C
  2. 环境变量 ABOARD_HOME
  3. 从当前目录向上找带 `board/cards/` 的目录（像 git 找 .git）
  4. 都没有 → 用当前目录（首次使用会自动建 board/）

为什么向上找：在子目录里也能用，不用 cd 回项目根。
"""
import json
import os
import time
from pathlib import Path

REGISTRY = Path.home() / ".allworktogether" / "projects.json"
BOARD_DIRNAME = "board"
MARKER = "cards"          # board/cards 存在 ⇒ 认定这里是看板根


# ---------- 注册表 ----------

def _load_registry() -> dict:
    if not REGISTRY.exists():
        return {"projects": []}
    try:
        d = json.loads(REGISTRY.read_text(encoding="utf-8"))
        d.setdefault("projects", [])
        return d
    except Exception:
        return {"projects": []}


def _save_registry(d: dict):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, REGISTRY)


def list_projects() -> list:
    """返回所有已登记且**仍然存在**的项目。"""
    out = []
    for p in _load_registry()["projects"]:
        path = Path(p["path"])
        p = dict(p)
        p["exists"] = path.exists()
        out.append(p)
    return out


def add_project(path, name=None, defaults=None, workspace=None) -> dict:
    """登记一个项目（幂等）。

    path      = 项目根（看板数据 board/ 放这里）
    workspace = agent 干活的地方（默认＝项目根；可以是子目录，甚至另一个仓）
    """
    path = Path(path).resolve()
    d = _load_registry()
    for p in d["projects"]:
        if Path(p["path"]).resolve() == path:
            if name:
                p["name"] = name
            if defaults:
                p.setdefault("defaults", {}).update(defaults)
            if workspace:
                p["workspace"] = str(Path(workspace).resolve())
            _save_registry(d)
            return p
    entry = {
        "name": name or path.name,
        "path": str(path),
        "workspace": str(Path(workspace).resolve()) if workspace else str(path),
        "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "defaults": defaults or {},
    }
    d["projects"].append(entry)
    _save_registry(d)
    return entry


def workspace_of(path) -> Path:
    """项目的工作区。没设就＝项目根。"""
    p = find_project(str(Path(path).resolve()))
    if p and p.get("workspace"):
        ws = Path(p["workspace"])
        if ws.exists():
            return ws
    return Path(path).resolve()


def set_workspace(path, workspace) -> dict:
    """改某个项目的工作区。"""
    path = Path(path).resolve()
    ws = Path(workspace).resolve()
    d = _load_registry()
    for p in d["projects"]:
        if Path(p["path"]).resolve() == path:
            p["workspace"] = str(ws)
            _save_registry(d)
            return p
    raise KeyError(f"项目未登记：{path}")


def remove_project(key: str) -> bool:
    """按名字或路径移除登记（⛔ 不删磁盘数据）。"""
    d = _load_registry()
    before = len(d["projects"])
    d["projects"] = [
        p for p in d["projects"]
        if not (p["name"] == key or Path(p["path"]).resolve() == Path(key).resolve()
                if "/" in key or "\\" in key else p["name"] == key)
    ]
    if len(d["projects"]) != before:
        _save_registry(d)
        return True
    return False


def find_project(key: str):
    for p in _load_registry()["projects"]:
        if p["name"] == key:
            return p
    for p in _load_registry()["projects"]:
        if Path(p["path"]).resolve() == Path(key).resolve():
            return p
    return None


def project_defaults(path) -> dict:
    """项目级默认引擎/模型/思考强度（卡片没写 any 时用）。"""
    p = find_project(str(Path(path).resolve()))
    if p:
        return p.get("defaults") or {}
    return {}


# ---------- 根目录解析 ----------

def _walks_up_for_board(start: Path):
    cur = start.resolve()
    for _ in range(12):
        if (cur / BOARD_DIRNAME / MARKER).exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def resolve_root(explicit=None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("ABOARD_HOME")
    if env:
        return Path(env).resolve()
    found = _walks_up_for_board(Path.cwd())
    if found:
        return found
    return Path.cwd().resolve()


def board_path(root) -> Path:
    return Path(root) / BOARD_DIRNAME


def cards_path(root) -> Path:
    return board_path(root) / MARKER


def ensure_root(root) -> Path:
    """确保看板目录存在，并把项目登记进注册表。"""
    root = Path(root).resolve()
    cards_path(root).mkdir(parents=True, exist_ok=True)
    # 自动登记（零配置的核心）
    if not find_project(str(root)):
        add_project(root)
    return root


def project_summary() -> list:
    """跨项目汇总：每个项目多少张卡、各状态多少。"""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    out = []
    for p in list_projects():
        if not p["exists"]:
            out.append({**p, "cards": 0, "states": {}, "ok": False})
            continue
        cp = cards_path(p["path"])
        states = {}
        n = 0
        if cp.exists():
            for d in cp.iterdir():
                if not d.is_dir():
                    continue
                n += 1
                try:
                    import board as B
                    old = B.ROOT
                    B.set_root(Path(p["path"]))
                    st = B.replay(d.name)["state"]
                    B.set_root(old)
                    states[st] = states.get(st, 0) + 1
                except Exception:
                    states["?"] = states.get("?", 0) + 1
        out.append({**p, "cards": n, "states": states, "ok": True})
    return out


if __name__ == "__main__":
    print(f"注册表：{REGISTRY}")
    for p in list_projects():
        mark = "✓" if p["exists"] else "✗"
        print(f"  {mark} {p['name']:<20} {p['path']}")
