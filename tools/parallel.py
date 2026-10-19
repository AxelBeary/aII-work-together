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
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import board as B  # noqa: E402

WT_DIR = ".worktrees"


def git(*args, cwd=None):
    p = subprocess.run(["git"] + list(args), cwd=str(cwd or ROOT),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def is_git_repo(path=None) -> bool:
    rc, _, _ = git("rev-parse", "--is-inside-work-tree", cwd=path or ROOT)
    return rc == 0


def has_commits() -> bool:
    rc, _, _ = git("rev-parse", "--verify", "HEAD")
    return rc == 0


def create(cid: str) -> Path:
    """给一张卡建 worktree。返回路径。"""
    base = ROOT / WT_DIR
    base.mkdir(parents=True, exist_ok=True)
    wt = base / cid
    if wt.exists():
        return wt
    if not is_git_repo() or not has_commits():
        # 没有 git 也能跑：退化成普通目录副本（隔离性弱一点，但仍不互相踩）
        shutil.copytree(ROOT, wt, ignore=shutil.ignore_patterns(
            ".git", ".worktrees", "board", "__pycache__", "*.pyc"))
        return wt
    rc, out, err = git("worktree", "add", "--detach", str(wt), "HEAD")
    if rc != 0:
        raise RuntimeError(f"worktree 创建失败：{err.strip()[:200]}")
    return wt


def remove(cid: str):
    wt = ROOT / WT_DIR / cid
    if not wt.exists():
        return
    if is_git_repo() and has_commits():
        git("worktree", "remove", "--force", str(wt))
    if wt.exists():
        shutil.rmtree(wt, ignore_errors=True)


def collect(cid: str, deliverables: list) -> tuple:
    """把 worktree 里的交付物拷回主树。返回 (copied, conflicts)。"""
    wt = ROOT / WT_DIR / cid
    copied, conflicts = [], []
    for d in deliverables:
        rel = d if isinstance(d, str) else d.get("path")
        src = wt / rel
        dst = ROOT / rel
        if not src.exists():
            continue
        # 冲突检测：主树已存在且内容不同 ⇒ 说明别人已写
        if dst.exists():
            if dst.read_bytes() != src.read_bytes():
                conflicts.append(f"{rel}（主树已有不同内容）")
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    return copied, conflicts


def status() -> list:
    """列出当前所有 worktree。"""
    base = ROOT / WT_DIR
    if not base.exists():
        return []
    return [{"card": d.name, "path": str(d), "exists": d.exists()}
            for d in sorted(base.iterdir()) if d.is_dir()]


def cleanup_all():
    base = ROOT / WT_DIR
    if not base.exists():
        return
    for d in list(base.iterdir()):
        if d.is_dir():
            remove(d.name)


if __name__ == "__main__":
    print(f"git repo: {is_git_repo()}  有提交: {has_commits()}")
    for w in status():
        print(f"  {w['card']:<14} {w['path']}")
