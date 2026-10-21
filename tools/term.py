#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
term.py — 窗口内置终端（供网页界面调用，不是给外部程序的 shell）

为什么要它（2026-10-20 用户要求「终端也融合到一个窗口」）：
  看板是 CLI 驱动的：跑一轮、自检、看状态都是命令。以前要么另开一个黑窗口，
  要么在浏览器里干等着不知道后台发生了啥。这个模块让界面里能直接跑那几条命令并看输出。

⛔ 安全边界（这是硬约束，不是建议）：
  · **白名单**，不是黑名单：只认 board / orch / check / py <tools|tests 下的脚本> / 几条只读 git
  · **不经过 shell**：命令按空格切，直接 Popen 数组形式 ⇒ 管道、重定向、`&&` 全部无效
  · **一次只跑一条**：并发跑引擎类命令会互抢资源（ENVIRONMENT 里有实证）
  · 破坏性动作（rm / human 拍板）**不在白名单里**：拍板走界面自己的令牌接口
"""
import os
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "board" / "term.log"
MAX_LINES = 3000

_LOCK = threading.Lock()
_STATE = {
    "lines": deque(maxlen=MAX_LINES),
    "n": 0,              # 最后一条的行号（单调）
    "running": False,
    "cmd": None,
    "started": None,
    "rc": None,
    "proc": None,
}

# ---------- 白名单 ----------

DENY_SUB = {"rm", "human"}          # 删卡要人明确点头；拍板走令牌接口
# 内置终端只放行这些 board 子命令（安全扫描 F-03：白名单，不再是「除两个词全放行」）
BOARD_ALLOW = {"ls", "show", "stats", "ready", "cost", "audit", "doctor",
               "inbox", "all", "overview", "html", "msg", "budget", "project"}
BOARD_DENY = DENY_SUB | {"publish", "--fix", "--yes"}
SHELL_META = set("|&;><$`^()%\n\r\t")

def _split(cmd):
    """按空格切，支持简单引号；不处理任何 shell 语法。"""
    out, cur, quote = [], "", None
    for ch in cmd.strip():
        if quote:
            if ch == quote:
                quote = None
            else:
                cur += ch
        elif ch in "\"'":
            quote = ch
        elif ch.isspace():
            if cur:
                out.append(cur)
                cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def plan(cmd: str):
    """把一条人写的命令翻成 argv。返回 (argv, 说明) 或抛 ValueError。

    ⛔ 只认这些形状，别的一律拒——拒的时候要告诉人「能跑什么」。
    """
    cmd = (cmd or "").strip()
    if not cmd:
        raise ValueError("命令是空的")
    bad = SHELL_META & set(cmd)
    if bad:
        raise ValueError(f"不支持 shell 语法（{' '.join(sorted(bad))}）：这里不是 shell，"
                         "只会把命令按空格切开直接执行")
    toks = _split(cmd)
    if not toks:
        raise ValueError("命令是空的")
    head, rest = toks[0].lower(), toks[1:]

    if head == "board":
        # ⚠️ 2026-10-21 改（安全扫描 F-03）：旧实现「board 全放行，只挡 rm/human」，
        #    于是 `board budget --seat human`、`py tools/cli.py rm` 都能绕过。
        #    现在改**白名单**：只放行下列只读/低危子命令。
        denied = [t for t in rest if t.lower() in BOARD_DENY]
        if denied:
            raise ValueError(f"「board {denied[0]}」不在白名单里（破坏性动作请用界面按钮或自己开终端）")
        sub = next((t for t in rest if t in BOARD_ALLOW), None)
        if sub is None:
            raise ValueError("内置终端只放行只读子命令：" + " / ".join(sorted(BOARD_ALLOW)))
        return [sys.executable, str(ROOT / "tools" / "board.py")] + rest, "看板命令"

    if head == "orch":
        return [sys.executable, str(ROOT / "tools" / "orchestrator.py")] + rest, "自主编排"

    if head in ("check", "自检"):
        return [sys.executable, str(ROOT / "tools" / "check.py")] + rest, "自检"

    if head in ("py", "python"):
        if not rest:
            raise ValueError("py 后面要跟脚本路径")
        target = (ROOT / rest[0]).resolve()
        # ⚠️ 2026-10-21 改（安全扫描 F-03）：旧实现放行 tools/ 下**任何**脚本，
        #    于是 `py tools/cli.py rm C1 --yes` 直接绕过白名单。现在只认真枚举的脚本：
        #    tools/check.py，以及 tests/ 下的 test_*.py。
        ok_script = False
        try:
            target.relative_to((ROOT / "tools").resolve())
            ok_script = target.name == "check.py"
        except ValueError:
            try:
                target.relative_to((ROOT / "tests").resolve())
                ok_script = target.name.startswith("test_") and target.suffix == ".py"
            except ValueError:
                ok_script = False
        if not ok_script:
            raise ValueError("py 只允许跑 tools/check.py 与 tests/test_*.py")
        if not target.exists():
            raise ValueError(f"脚本不存在：{target}")
        return [sys.executable, str(target)] + rest[1:], "脚本"

    if head == "git":
        allowed = {"status", "log", "diff", "show", "branch"}
        if not rest or rest[0] not in allowed:
            raise ValueError("git 只允许 status / log / diff / show / branch（只读）")
        return ["git"] + rest, "git（只读）"

    raise ValueError(f"「{toks[0]}」不在白名单里。能跑：board（只读子命令）/ orch / "
                     f"check / py tools/check.py / py tests/test_*.py / git status|log|diff")


# ---------- 执行 ----------

def _emit(text, kind="out"):
    with _LOCK:
        _STATE["n"] += 1
        _STATE["lines"].append({"n": _STATE["n"], "text": text, "kind": kind})
        _write_log(text)


def _write_log(text):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        # 简单轮转：>5MB 时留一份 .1（安全扫描 F-22：日志原先只增不减）
        try:
            if LOG.exists() and LOG.stat().st_size > 5 * 1024 * 1024:
                bak = LOG.with_suffix(".log.1")
                if bak.exists():
                    bak.unlink()
                LOG.replace(bak)
        except Exception as e:
            print(f"⚠ 终端日志轮转失败：{e}", file=sys.stderr)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception as e:
        # ⚠️ 2026-10-21 修（安全扫描 F-15）：写不进日志要可见（原先静默 pass），
        #    否则事后复盘时会以为「这条路没人跑过」。
        print(f"⚠ 终端日志写不进（{LOG}）：{e}", file=sys.stderr)


def state():
    with _LOCK:
        return {
            "running": _STATE["running"],
            "cmd": _STATE["cmd"],
            "started": _STATE["started"],
            "rc": _STATE["rc"],
            "next": _STATE["n"] + 1,
        }


def tail(since=0, limit=500):
    with _LOCK:
        rows = [l for l in _STATE["lines"] if l["n"] > int(since)]
        rows = rows[-int(limit):]
        st = {
            "running": _STATE["running"],
            "cmd": _STATE["cmd"],
            "started": _STATE["started"],
            "rc": _STATE["rc"],
            "next": (_STATE["lines"][-1]["n"] + 1) if _STATE["lines"] else 1,
        }
    return {"lines": rows, **st}


def clear():
    with _LOCK:
        _STATE["lines"].clear()


def run(cmd, cwd=None):
    """起一条命令（用外部进程跑，输出流进环形缓冲）。返回 (ok, 说明)。"""
    try:
        argv, kind = plan(cmd)
    except ValueError as e:
        return False, str(e)
    with _LOCK:
        if _STATE["running"]:
            return False, f"上一条还在跑：{_STATE['cmd']}"
        _STATE["running"] = True
        _STATE["cmd"] = cmd
        _STATE["started"] = datetime.now().strftime("%H:%M:%S")
        _STATE["rc"] = None
        # 每次新命令前打个分隔，长日志里能分清哪段是谁的
        _STATE["n"] += 1
        _STATE["lines"].append({"n": _STATE["n"], "kind": "head",
                                "text": f"$ {cmd}"})

    def worker():
        rc = None
        try:
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"
            p = subprocess.Popen(argv, cwd=cwd or str(ROOT), env=env,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace",
                                 bufsize=1,
                                 stdin=subprocess.DEVNULL)
            with _LOCK:
                _STATE["proc"] = p
            for line in p.stdout:
                _emit(line.rstrip())
            rc = p.wait()
        except Exception as e:                        # noqa: BLE001
            _emit(f"✗ 起不来：{type(e).__name__}: {e}", kind="err")
            rc = -1
        finally:
            _emit(f"[结束 退出码={rc}]",
                  kind="ok" if rc == 0 else "err")
            with _LOCK:
                _STATE["running"] = False
                _STATE["rc"] = rc
                _STATE["proc"] = None

    t = threading.Thread(target=worker, daemon=True, name=f"term-{_STATE['n']}")
    t.start()
    return True, kind


def stop():
    with _LOCK:
        p = _STATE["proc"]
    if not p:
        return False
    try:
        # ⚠️ 2026-10-21 修（安全扫描 F-22）：旧实现只 `p.kill()` 直接子进程，
        #    它下面拉起的引擎（node/opencode）会变孤儿继续吃 CPU 与额度。
        #    Windows 用 taskkill /T 杀整棵树；其它平台退化为 killpg（拿得到 pgid 时）。
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
        else:
            try:
                os.killpg(os.getpgid(p.pid), 9)
            except Exception:
                p.kill()
        try:
            p.wait(timeout=5)
        except Exception:
            pass
        return True
    except Exception as e:
        _emit(f"⚠ 停止失败：{type(e).__name__}: {e}", kind="err")
        return False


if __name__ == "__main__":
    # 手跑自检：python tools/term.py "board stats"
    ok, why = run(" ".join(sys.argv[1:]) or "board stats")
    print(("✓ " if ok else "✗ ") + why)
    while state()["running"]:
        time.sleep(0.2)
    for l in tail(0)["lines"]:
        print(l["text"])
