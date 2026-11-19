#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fold.py — 事件折叠：把 append-only 事件流折叠成可读的对象

为什么单独一个文件（2026-11-19，D-033）：
  内核唯一真相是事件流。comments / executions / checklist / 分支 / 软删除
  都不是表里的列，而是**由事件折叠出来的投影**。
  把它和 board.py 的 replay（卡片状态机）分开，是因为两者关注点不同：
    · replay  只关心「卡在哪个状态」——状态机
    · fold    只关心「卡上挂了哪些东西」——内容投影
  合在一起会变成 600 行的巨型函数，改一处就得全文重读。

设计约束（与 storage.py 一致）：
  · 纯函数，不碰 I/O —— 调用方把 events 传进来
  · 只读事件，绝不写回（写是 append_event 的事）
  · 折叠顺序 = seq 顺序；后到的事件覆盖先到的（同 id 的更新语义）

⛔ 这里**不做权限判断**，也不改状态。权限在 cli 的 guard_*，状态在 replay。
"""
from datetime import datetime, timezone


def _now_iso():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


# ---------------------------------------------------------------- 评论

def fold_comments(events):
    """折叠评论。`comment` 追加，`comment-delivered` 标记已投递。

    返回 list，按事件顺序（先写的在前）。
    """
    out, index = [], {}
    for ev in events:
        k = ev.get("type")
        if k == "comment":
            cid = ev.get("comment_id") or ("c-%s" % ev.get("seq"))
            item = {
                "id": cid,
                "body": ev.get("body", ""),
                "author": ev.get("actor", "agent"),
                "seat": ev.get("seat"),
                "at": ev.get("at"),
                "at_ms": ev.get("at_ms"),
                "thread_id": ev.get("thread_id"),
                "system_key": ev.get("system_key"),
                "system_params": ev.get("system_params"),
                "delivered_at": None,
                "delivered_execution": None,
            }
            if cid not in index:          # 同一 id 只认第一次（append-only）
                index[cid] = item
                out.append(item)
        elif k == "comment-delivered":
            target = index.get(ev.get("comment_id"))
            if target is not None:
                target["delivered_at"] = ev.get("at")
                target["delivered_execution"] = ev.get("execution_id")
    return out


# ---------------------------------------------------------------- 执行记录

def fold_executions(events):
    """折叠执行记录。open 建，activity 更新，close 结算。"""
    out, index = [], {}
    for ev in events:
        k = ev.get("type")
        if k == "execution-open":
            eid = ev.get("execution_id") or ("e-%s" % ev.get("seq"))
            if eid in index:
                continue
            item = {
                "id": eid,
                "state": "running",
                "outcome": "running",
                "session": ev.get("session_id"),
                "trigger": ev.get("trigger", "manual"),
                "seat": ev.get("seat"),
                "started_at": ev.get("at"),
                "started_ms": ev.get("at_ms"),
                "last_activity_at": ev.get("at"),
                "ended_at": None,
                "error": None,
                "report": None,
            }
            index[eid] = item
            out.append(item)
        elif k == "execution-activity":
            item = index.get(ev.get("execution_id"))
            if item is not None and item["outcome"] == "running":
                item["last_activity_at"] = ev.get("at")
        elif k == "execution-close":
            item = index.get(ev.get("execution_id"))
            if item is None:
                continue
            item["outcome"] = ev.get("outcome", "succeeded")
            item["state"] = item["outcome"]
            item["ended_at"] = ev.get("at")
            if ev.get("error"):
                item["error"] = ev["error"]
            if ev.get("report") is not None:
                item["report"] = ev["report"]
        elif k == "execution-report":
            item = index.get(ev.get("execution_id"))
            if item is not None:
                item["report"] = ev.get("report")
    return out


def running_execution(events):
    """当前仍在跑的执行记录（没有则 None）。"""
    live = [e for e in fold_executions(events) if e["outcome"] == "running"]
    return live[-1] if live else None


# ---------------------------------------------------------------- 验收清单

def fold_checklist(events):
    """折叠验收清单（DoD）。"""
    out, index = [], {}
    for ev in events:
        k = ev.get("type")
        if k == "checklist-add":
            item_id = ev.get("item_id") or ("k-%s" % ev.get("seq"))
            if item_id in index:
                continue
            item = {
                "id": item_id,
                "text": ev.get("text", ""),
                "checked": False,
                "checked_by": None,
                "checked_at": None,
                "note": None,
            }
            index[item_id] = item
            out.append(item)
        elif k in ("checklist-check", "checklist-uncheck"):
            item = index.get(ev.get("item_id"))
            if item is None:
                continue
            on = k == "checklist-check"
            item["checked"] = on
            item["checked_by"] = ev.get("seat") if on else None
            item["checked_at"] = ev.get("at") if on else None
            if on and ev.get("note"):
                item["note"] = ev["note"]
    return out


# ---------------------------------------------------------------- 分支 / 软删除

def fold_branches(events):
    """折叠分支名（worktree 隔离用）。最后一次设置为准。"""
    out = {}
    for ev in events:
        if ev.get("type") == "branch-set":
            repo = ev.get("repo", "")
            branch = ev.get("branch")
            if branch:
                out[repo] = branch
            else:
                out.pop(repo, None)
    return out


def fold_trash(events):
    """折叠软删除。返回 (trashed_at, restored_at)。"""
    trashed = restored = None
    for ev in events:
        if ev.get("type") == "trash":
            trashed, restored = ev.get("at"), None
        elif ev.get("type") == "restore":
            restored = ev.get("at")
    if trashed and restored is None:
        return trashed, None
    return None, restored


def is_trashed(events):
    """这张卡现在是否处于软删除状态。"""
    return fold_trash(events)[0] is not None


# ---------------------------------------------------------------- 汇总

def fold_all(events):
    """一次性折叠出全部投影。"""
    trashed_at, restored_at = fold_trash(events)
    return {
        "comments": fold_comments(events),
        "executions": fold_executions(events),
        "checklist": fold_checklist(events),
        "branches": fold_branches(events),
        "trashed_at": trashed_at,
        "restored_at": restored_at,
        "running_execution": running_execution(events),
        "last_seq": events[-1]["seq"] if events else 0,
    }
