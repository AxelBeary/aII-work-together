#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parallel.py — 并行执行（每卡一个 git worktree）

为什么需要：多个 agent 同时改同一个仓库会互相踩文件。
解法：每张卡在**独立 git worktree** 里干活，互不干扰；收工时只把
      该卡的交付物拷回主树，并检测「两张卡改了同一个文件」的冲突。

设计要求（对齐 AGENTS.md §1.5「一个路径一个写者」）：
  · 同一张卡永远只有一个 worktree
  · 收工时**逐文件**拷贝，⛔ 不做整树合并
  · 两卡交付物路径重叠 ⇒ 后到的判 BLOCKED，留痕，⛔ 不静默覆盖

⚠️ 引擎类动作不进并行区（AGENTS.md §3）：这里并行的是**独立 worktree**，
   引擎本身在自己目录里跑，不共享状态。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B  # noqa: E402

WT_DIR = ".worktrees"


def git(*args, cwd=None):
    p = subprocess.run(["git"] + list(args), cwd=str(cwd or B.WORKSPACE),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def is_git_repo(path=None) -> bool:
    rc, _, _ = git("rev-parse", "--is-inside-work-tree", cwd=path or B.WORKSPACE)
    return rc == 0


def has_commits(path=None) -> bool:
    rc, _, _ = git("rev-parse", "--verify", "HEAD", cwd=path or B.WORKSPACE)
    return rc == 0


def create(cid: str, deliverables: list = None) -> Path:
    """给一张卡建 worktree（基于项目工作区）。返回路径。

    同时记录**基线**：交付物在主工作区当前的 hash。
    收工时用它区分「我改了旧文件」与「别人动了同一个文件」。
    """
    ws = B.WORKSPACE
    base = ws / WT_DIR
    base.mkdir(parents=True, exist_ok=True)
    wt = base / cid
    if not wt.exists():
        if not is_git_repo(ws) or not has_commits(ws):
            # 没有 git 也能跑：退化成普通目录副本（隔离性弱一点，但仍不互相踩）
            shutil.copytree(ws, wt, ignore=shutil.ignore_patterns(
                ".git", ".worktrees", "board", "__pycache__", "*.pyc"))
        else:
            rc, out, err = git("worktree", "add", "--detach", str(wt), "HEAD", cwd=ws)
            if rc != 0:
                raise RuntimeError(f"worktree 创建失败：{err.strip()[:200]}")

    # 记基线（谁在我开工前就有的内容，不算冲突）
    baseline = {}
    for d in (deliverables or []):
        rel = d if isinstance(d, str) else d.get("path")
        p = ws / rel
        if p.exists():
            try:
                baseline[rel] = _hash(p)
            except Exception:
                pass
    if baseline:
        (base / f"{cid}.baseline.json").write_text(
            json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
    return wt


def _hash(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _load_baseline(cid: str) -> dict:
    f = B.WORKSPACE / WT_DIR / f"{cid}.baseline.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def remove(cid: str):
    ws = B.WORKSPACE
    wt = ws / WT_DIR / cid
    if wt.exists():
        if is_git_repo(ws) and has_commits(ws):
            git("worktree", "remove", "--force", str(wt), cwd=ws)
        if wt.exists():
            shutil.rmtree(wt, ignore_errors=True)
    (ws / WT_DIR / f"{cid}.baseline.json").unlink(missing_ok=True)


def collect(cid: str, deliverables: list) -> tuple:
    """把 worktree 里的交付物拷回工作区。返回 (copied, conflicts)。

    冲突判据（2026-10-20 修正）：
      ⛔ 旧判据「工作区已有该文件且内容不同」⇒ 所有**修改已有文件**的卡都被误判冲突。
      ✅ 新判据：对比**基线**——只有「我开工后被别人改过」才算冲突。
         我自己改的（工作区内容 == 基线）直接覆盖，这是正常的改文件。
    """
    ws = B.WORKSPACE
    wt = ws / WT_DIR / cid
    baseline = _load_baseline(cid)
    copied, conflicts = [], []
    for d in deliverables:
        rel = d if isinstance(d, str) else d.get("path")
        src = wt / rel
        dst = ws / rel
        if not src.exists():
            continue
        if dst.exists():
            now = _hash(dst)
            base_hash = baseline.get(rel)
            if base_hash is None:
                # 开工时没有 → 现在有了，说明别人在我干活期间建的
                conflicts.append(f"{rel}（我开工后别人新建了这个文件）")
                continue
            if now != base_hash:
                # 别人在我干活期间改过 → 真冲突
                conflicts.append(f"{rel}（我干活期间别人改过它）")
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    return copied, conflicts


def status() -> list:
    """列出当前所有 worktree。"""
    base = B.WORKSPACE / WT_DIR
    if not base.exists():
        return []
    return [{"card": d.name, "path": str(d), "exists": d.exists()}
            for d in sorted(base.iterdir()) if d.is_dir()]


def cleanup_all():
    base = B.WORKSPACE / WT_DIR
    if not base.exists():
        return
    for d in list(base.iterdir()):
        if d.is_dir():
            remove(d.name)


if __name__ == "__main__":
    print(f"工作区: {B.WORKSPACE}")
    print(f"git repo: {is_git_repo()}  有提交: {has_commits()}")
    for w in status():
        print(f"  {w['card']:<14} {w['path']}")
