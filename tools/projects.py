#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
projects.py — 多项目注册表（SQLite）与根目录解析

为什么注册表也用 SQLite（2026-10-20，团队场景）：
  · 原来存 ~/.allworktogether/projects.json，多进程同时登记会互相覆盖
  · 团队几十个项目、多人同时操作 ⇒ 必须事务化
  · 一个库 = 一个文件，好备份

设计边界：
  · 注册表**只记「项目在哪」**，不存卡片；删库不影响任何项目数据
  · 每个项目自己的卡片在它自己的 board/board.db 里（见 storage.py）
  · 注册表用 WAL，读多写少，几十个项目完全够

解析顺序（resolve_root）：
  1. 显式 --root / -C
  2. 环境变量 ABOARD_HOME
  3. 从当前目录向上找带 `board/board.db` 或 `board/cards` 的目录（像 git 找 .git）
  4. 都没有 → 用当前目录（首次使用会自动建 board/）
"""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

HOME_DIR = Path.home() / ".allworktogether"
REGISTRY_DB = HOME_DIR / "registry.db"
BOARD_DIRNAME = "board"
MARKER_DB = "board.db"
MARKER_LEGACY = "cards"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS projects (
  path       TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  workspace  TEXT,
  defaults   TEXT DEFAULT '{}',
  added_at   TEXT,
  added_by   TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
"""

_local = threading.local()


def _conn():
    """每线程一个连接（SQLite 连接不能跨线程共享）。"""
    c = getattr(_local, "conn", None)
    if c is None or getattr(_local, "path", None) != str(REGISTRY_DB):
        HOME_DIR.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(REGISTRY_DB), timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000")
        c.executescript(SCHEMA)
        _local.conn = c
        _local.path = str(REGISTRY_DB)
    return c


def _ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _row(r) -> dict:
    d = dict(r)
    try:
        d["defaults"] = json.loads(d.get("defaults") or "{}")
    except Exception:
        d["defaults"] = {}
    return d


# ---------- 注册表 ----------

def list_projects() -> list:
    rows = _conn().execute("SELECT * FROM projects ORDER BY name").fetchall()
    out = []
    for r in rows:
        p = _row(r)
        p["exists"] = Path(p["path"]).exists()
        out.append(p)
    return out


def add_project(path, name=None, defaults=None, workspace=None,
                added_by=None) -> dict:
    """登记一个项目（幂等，按路径）。"""
    path = Path(path).resolve()
    name = name or path.name
    ws = str(Path(workspace).resolve()) if workspace else str(path)
    c = _conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        row = c.execute("SELECT * FROM projects WHERE path=?", (str(path),)).fetchone()
        if row:
            cur = _row(row)
            newname = name or cur["name"]
            newws = ws if workspace else (cur.get("workspace") or str(path))
            ndef = dict(cur.get("defaults") or {})
            if defaults:
                ndef.update(defaults)
            c.execute("UPDATE projects SET name=?, workspace=?, defaults=? WHERE path=?",
                      (newname, newws, json.dumps(ndef, ensure_ascii=False), str(path)))
            c.execute("COMMIT")
            return {**cur, "name": newname, "workspace": newws, "defaults": ndef}
        # 名字冲突时自动加后缀
        base, n = name, 2
        while c.execute("SELECT 1 FROM projects WHERE name=?", (name,)).fetchone():
            name = f"{base}-{n}"
            n += 1
        c.execute(
            "INSERT INTO projects(path,name,workspace,defaults,added_at,added_by) "
            "VALUES(?,?,?,?,?,?)",
            (str(path), name, ws,
             json.dumps(defaults or {}, ensure_ascii=False),
             _ts(), added_by or os.environ.get("BOARD_USER") or "unknown"))
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise
    return {**{"path": str(path), "name": name, "workspace": ws,
               "defaults": defaults or {}}}


def remove_project(key: str) -> bool:
    c = _conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        n = c.execute(
            "DELETE FROM projects WHERE name=? OR path=?", (key, key)).rowcount
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise
    return n > 0


def find_project(key: str):
    r = _conn().execute(
        "SELECT * FROM projects WHERE name=? OR path=? LIMIT 1", (key, key)).fetchone()
    if not r:
        # 也接受「末尾路径相同」的相对写法
        for p in list_projects():
            if Path(p["path"]).name == key:
                return p
        return None
    return _row(r)


def project_defaults(path) -> dict:
    p = find_project(str(Path(path).resolve()))
    return (p or {}).get("defaults") or {}


def workspace_of(path) -> Path:
    p = find_project(str(Path(path).resolve()))
    if p and p.get("workspace"):
        ws = Path(p["workspace"])
        if ws.exists():
            return ws
    return Path(path).resolve()


def set_workspace(path, workspace) -> dict:
    path = Path(path).resolve()
    ws = Path(workspace).resolve()
    c = _conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        n = c.execute("UPDATE projects SET workspace=? WHERE path=?",
                      (str(ws), str(path))).rowcount
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise
    if not n:
        raise KeyError(f"项目未登记：{path}")
    return find_project(str(path))


# ---------- 根目录解析 ----------

def _walks_up_for_board(start: Path):
    cur = start.resolve()
    for _ in range(12):
        if (cur / BOARD_DIRNAME / MARKER_DB).exists():
            return cur
        if (cur / BOARD_DIRNAME / MARKER_LEGACY).exists():
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
    return board_path(root) / MARKER_LEGACY


def db_path(root) -> Path:
    return board_path(root) / MARKER_DB


def ensure_root(root) -> Path:
    """确保看板目录存在，并把项目登记进注册表（零配置核心）。"""
    root = Path(root).resolve()
    board_path(root).mkdir(parents=True, exist_ok=True)
    if not find_project(str(root)):
        add_project(root)
    return root


# ---------- 跨项目汇总（团队视角） ----------

def _summary_cache_file():
    return HOME_DIR / "summary-cache.json"


def project_summary(use_cache: bool = True, ttl_s: int = 15) -> list:
    """跨项目汇总：每个项目多少张卡、各状态多少。

    几十个项目时逐库打开会慢 ⇒ 加 15 秒磁盘缓存。
    """
    cf = _summary_cache_file()
    if use_cache and cf.exists():
        try:
            data = json.loads(cf.read_text(encoding="utf-8"))
            if time.time() - data.get("at", 0) < ttl_s:
                return data["projects"]
        except Exception:
            pass

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import board as B
    out = []
    for p in list_projects():
        if not p.get("exists"):
            out.append({**p, "cards": 0, "states": {}, "ok": False})
            continue
        old_root = B.ROOT
        try:
            B.set_root(p["path"])
            states = {}
            n = 0
            for cid in B.card_ids():
                n += 1
                st = B.replay(cid)["state"]
                states[st] = states.get(st, 0) + 1
            out.append({**p, "cards": n, "states": states, "ok": True})
        except Exception as e:
            out.append({**p, "cards": 0, "states": {}, "ok": False,
                        "error": str(e)[:120]})
        finally:
            B.set_root(old_root)

    try:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps({"at": time.time(), "projects": out},
                                 ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return out


if __name__ == "__main__":
    print(f"注册表：{REGISTRY_DB}")
    for p in list_projects():
        mark = "✓" if p["exists"] else "✗"
        print(f"  {mark} {p['name']:<20} {p['path']}")
