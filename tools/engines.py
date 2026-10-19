#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engines.py — 引擎适配器层（编排器的执行臂）

设计原则（来自 D2 §B.2 与本项目实测 E-11）：
  · 每个引擎一个版本化解析器，⛔ 不写「统一解析」
  · 退出码只作诊断提示，**权重 0**；判成败一律读结构化回执
  · 解析器只说三件事：①运行是否正常结束 ②异常原因 ③元数据
  · 解析器⛔ 不下「产物对不对」的结论（那是看板 L1-L3 的事）

实测状态（2026-10-19）：
  opencode   可用（必须带 --model，否则走免费池被 IP 封禁）
  qoderclicn 可用
  codex      当前不可用（RTOC 401）
  hermes     未测
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 各引擎默认模型（编排器会在卡未指定时用这个）
DEFAULT_MODELS = {
    "opencode": "opencode-go/deepseek-v4.1-flash",
    "qoderclicn": None,      # 用引擎自己的默认
    "codex": None,
    "hermes": None,
}

# 思考强度 → 各引擎的参数映射（None = 该引擎不支持显式设置）
EFFORT_MAP = {
    "opencode": {
        "low": None, "medium": None, "high": None, "max": None,
    },
    "qoderclicn": {
        "low": None, "medium": None, "high": None, "max": None,
    },
    "codex": {
        "low": None, "medium": None, "high": None, "max": None,
    },
    "hermes": {
        "low": None, "medium": None, "high": None, "max": None,
    },
}


class Result:
    """统一的执行结果。ok 只反映「引擎是否正常跑完」，不反映「活干得好不好」。"""

    def __init__(self, engine: str):
        self.engine = engine
        self.ok = False              # 引擎是否正常结束
        self.reason = ""             # 失败原因
        self.session_id = None
        self.model_used = None
        self.raw = ""                # 原始输出（存档）
        self.text = ""               # 模型的最终文本
        self.exit_code = None
        self.duration_ms = None
        self.parsed = {}             # 结构化字段

    def to_dict(self) -> dict:
        return {
            "engine": self.engine, "ok": self.ok, "reason": self.reason,
            "session_id": self.session_id, "model_used": self.model_used,
            "text": self.text[:8000], "exit_code": self.exit_code,
            "duration_ms": self.duration_ms, "parsed": self.parsed,
        }


def _which(engine: str):
    """Windows 上 npm 装的是 .cmd/.ps1，shutil.which 可能找不到。
    按 PATHEXT 逐个试。"""
    import shutil as _sh
    for name in (engine, engine + ".cmd", engine + ".bat", engine + ".exe", engine + ".ps1"):
        p = _sh.which(name)
        if p:
            return p
    return None


def available() -> dict:
    """探测本机有哪些引擎可用（只看可执行文件在不在，不探活）。"""
    out = {}
    for name in ("opencode", "qoderclicn", "codex", "hermes"):
        p = _which(name)
        out[name] = {"exe": p, "found": bool(p)}
    return out


def _exec(cmd, cwd, timeout, stdin_text=None):
    """执行命令。

    Windows 坑（实测两条）：
      1. npm 装的 .cmd **不能**被 subprocess 直接执行（WinError 2）。
      2. 经 shell=True 传中文参数会编码坏（「文件名、目录名或卷标语法不正确」）。
    解法：.cmd 用 `cmd /c` + **列表参数**（不经字符串拼接，中文原样传递）。
    """
    exe = cmd[0]
    real = _which(exe)
    argv = ([real] + list(cmd[1:])) if real else cmd
    if real and real.lower().endswith((".cmd", ".bat")):
        argv = ["cmd", "/c"] + argv
    # ⚠️ cwd 传 None 会触发 WinError 2（实测），必须落到具体目录
    cwd = cwd or os.getcwd()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           input=stdin_text, shell=False)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return None, "", f"超时（>{timeout}s）"
    except FileNotFoundError as e:
        return None, "", f"命令不存在：{e}"
    except OSError as e:
        return None, "", f"执行异常：{e}"
    except Exception as e:
        return None, "", f"执行异常：{e}"


def run(engine: str, prompt: str, cwd: str = None, model: str = None,
        effort: str = None, timeout: int = 1800, extra_args: list = None) -> Result:
    """跑一个引擎。返回 Result（含结构化回执解析结果）。"""
    engine = (engine or "").lower()
    if engine not in ("opencode", "qoderclicn", "codex", "hermes"):
        r = Result(engine)
        r.reason = f"未知引擎：{engine}"
        return r

    if not _which(engine):
        r = Result(engine)
        r.reason = f"引擎未安装：{engine}"
        return r

    model = model or DEFAULT_MODELS.get(engine)
    cwd = cwd or os.getcwd()

    if engine == "opencode":
        # 提示词走 stdin（命令行传中文经 .cmd 会编码坏，实测）
        cmd = ["opencode", "run", "--format", "json"]
        if model:
            cmd += ["--model", model]
        if extra_args:
            cmd += extra_args
        return _run_opencode(cmd, cwd, timeout, prompt)

    if engine == "qoderclicn":
        # -p 是布尔旗标，正文走 stdin
        cmd = ["qoderclicn", "-p", "-o", "json", "--no-session-persistence"]
        if extra_args:
            cmd += extra_args
        return _run_qoder(cmd, cwd, timeout, prompt)

    if engine == "codex":
        # 提示走 stdin，避免命令行引号问题
        cmd = ["codex", "exec", "--ephemeral", "--skip-git-repo-check",
               "--sandbox", "workspace-write", "-c", "approval_policy=never",
               "--json", "-"]
        if extra_args:
            cmd += extra_args
        return _run_codex(cmd, cwd, timeout, prompt)

    if engine == "hermes":
        cmd = ["hermes", "-z", prompt]
        if extra_args:
            cmd += extra_args
        return _run_hermes(cmd, cwd, timeout)

    r = Result(engine)
    r.reason = "未实现"
    return r


def _run_opencode(cmd, cwd, timeout, prompt=None) -> Result:
    r = Result("opencode")
    rc, out, err = _exec(cmd, cwd, timeout, stdin_text=prompt)
    r.exit_code = rc
    r.raw = out
    # 逐行解析 JSONL：成功要见 type:"text"，失败看 type:"error"
    texts, errors, sid = [], [], None
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        sid = ev.get("sessionID") or sid
        if t == "text":
            part = ev.get("part") or {}
            if part.get("text"):
                texts.append(part["text"])
        elif t == "error":
            e = ev.get("error") or {}
            msg = e.get("message") or json.dumps(e, ensure_ascii=False)[:300]
            errors.append(msg)
    r.session_id = sid
    r.model_used = cmd[cmd.index("--model") + 1] if "--model" in cmd else None
    r.text = "\n".join(texts)
    if errors and not texts:
        r.ok = False
        r.reason = errors[0][:300]
    elif errors:
        r.ok = True          # 有过错误但最终出了文本（如重试后成功）
        r.reason = "有告警：" + errors[0][:200]
    elif texts:
        r.ok = True
    else:
        r.ok = False
        r.reason = "无 text 事件（可能空跑）" + (f"；stderr={err[:200]}" if err else "")
    r.parsed = {"text_events": len(texts), "error_events": len(errors)}
    return r


def _run_qoder(cmd, cwd, timeout, prompt=None) -> Result:
    r = Result("qoderclicn")
    rc, out, err = _exec(cmd, cwd, timeout, stdin_text=prompt)
    r.exit_code = rc
    r.raw = out
    # 顶层是单个 JSON 对象
    try:
        obj = json.loads(out.strip())
    except json.JSONDecodeError:
        # 可能有多行，取最后一行能解析的
        obj = None
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
    if not obj:
        r.ok = False
        r.reason = f"回执不可解析；stderr={err[:200]}"
        return r
    r.session_id = obj.get("session_id")
    r.duration_ms = obj.get("duration_ms")
    r.text = obj.get("result") or ""
    is_error = obj.get("is_error")
    subtype = obj.get("subtype")
    mu = obj.get("modelUsage") or {}
    r.model_used = ",".join(mu.keys()) if mu else None
    # 判据：is_error 优先；subtype 会谎报，只作参考
    if is_error is True:
        r.ok = False
        r.reason = f"is_error=true；subtype={subtype}"
    elif is_error is False:
        r.ok = True
    else:
        r.ok = False
        r.reason = f"回执缺 is_error 字段（不可判）；subtype={subtype}"
    # 模型回落检测
    if "qfmodel" in mu or "auto" in str(mu).lower():
        r.parsed["model_fallback_suspect"] = True
    r.parsed.update({"is_error": is_error, "subtype": subtype,
                     "num_turns": obj.get("num_turns")})
    return r


def _run_codex(cmd, cwd, timeout, prompt) -> Result:
    r = Result("codex")
    rc, out, err = _exec(cmd, cwd, timeout, stdin_text=prompt)
    r.exit_code = rc
    r.raw = out
    completed, failed, texts, tid = False, None, [], None
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        if t == "thread.started":
            tid = ev.get("thread_id")
        elif t == "turn.completed":
            completed = True
        elif t == "turn.failed":
            failed = (ev.get("error") or {}).get("message", "turn.failed")
        elif t == "item.completed":
            item = ev.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                texts.append(item["text"])
    r.session_id = tid
    r.text = "\n".join(texts)
    # 判据：必须见 turn.completed；只有 thread.started 不算
    if failed:
        r.ok = False
        r.reason = str(failed)[:300]
    elif completed:
        r.ok = True
    else:
        r.ok = False
        r.reason = "未见 turn.completed（不可判为成功）"
    r.parsed = {"completed": completed, "failed": bool(failed)}
    return r


def _run_hermes(cmd, cwd, timeout) -> Result:
    r = Result("hermes")
    rc, out, err = _exec(cmd, cwd, timeout)
    r.exit_code = rc
    r.raw = out
    r.text = out.strip()
    # Hermes 运行期错误也可能 RC=0；无结构化回执时只能保守判
    low = (out + err).lower()
    if any(k in low for k in ("error", "failed", "exception", "traceback")):
        r.ok = False
        r.reason = "输出含错误关键词（无结构化回执，保守判失败）"
    elif out.strip():
        r.ok = True
        r.parsed["note"] = "无结构化回执，仅按非空输出判定"
    else:
        r.ok = False
        r.reason = "空输出"
    return r


if __name__ == "__main__":
    # 自测：探测本机引擎
    for k, v in available().items():
        print(f"{k:<12} {'FOUND' if v['found'] else 'MISSING'}  {v['exe'] or ''}")
