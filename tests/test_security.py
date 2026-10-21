#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_security.py — 安全加固的反向测试（2026-10-21 安全扫描 F-01…F-23）

每条都问「入侵/误用的那条路，现在还通不通」；配非零对照（正常用法必须仍然通过）。
全部在临时项目里跑，不碰真实看板。

跑法：python tests/test_security.py
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOLS = ROOT / "tools"
SANDBOX = Path(tempfile.mkdtemp(prefix="aboard-sec-"))
REG = SANDBOX / "reg"
PROJ = SANDBOX / "demo"
PORT = 8795

env = dict(os.environ)
env["ABOARD_REGISTRY_DIR"] = str(REG)
env["BOARD_HUMAN_HOME"] = str(SANDBOX / "human")
env["PYTHONIOENCODING"] = "utf-8"
env.pop("ABOARD_SEAT", None)
os.environ["ABOARD_REGISTRY_DIR"] = str(REG)
os.environ["BOARD_HUMAN_HOME"] = env["BOARD_HUMAN_HOME"]
sys.path.insert(0, str(TOOLS))

fails = []


def ok(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


def board(*args, proj=None):
    p = subprocess.run([sys.executable, str(TOOLS / "board.py"),
                        "-C", str(proj or PROJ)] + list(args),
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def http(path, body=None, token=True, host=None):
    url = f"http://127.0.0.1:{PORT}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if data is not None and token:
        tok = (ROOT / "board" / "ui-server.tok").read_text(encoding="utf-8").strip()
        headers["X-Board-Token"] = tok
    if host:
        headers["Host"] = host
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def t_http_csrf():
    print("\n--- 1. HTTP：跨站写入 / Host 伪造 ---")
    code, body = http("/api/card", {"project": str(PROJ), "title": "csrf 卡"}, token=False)
    ok("不带会话令牌的 POST 被拒（403）", code == 403, f"{code} {body[:60]}")

    code, body = http("/api/card", {"project": str(PROJ), "title": "csrf 卡"},
                      host="evil.example.com")
    ok("Host 不是回环地址被拒（DNS rebinding）", code == 403, f"{code} {body[:60]}")

    code, body = http("/api/state")
    ok("对照：正常 GET 仍然通（200）", code == 200 and "current" in body, f"{code}")


def t_path_traversal():
    print("\n--- 2. 卡号直通路径 ---")
    code, body = http("/api/card", {"id": r"..\..\pwn", "title": "穿越卡"})
    ok("HTTP 建卡：卡号带 .. 被拒", code == 400 and "卡号" in body, f"{code} {body[:60]}")

    rc, out = board("rm", r"..\..\pwn", "--yes")
    ok("CLI 删卡：卡号带 .. 被拒", rc != 0 and "卡号" in out, f"rc={rc} {out[:60]}")

    code, body = http("/api/card/log?id=..%5C..%5Cx")
    ok("日志接口：卡号带 .. 被拒", code == 400 and "卡号" in body,
       f"{code} {body[:60]}")


def t_term_allowlist():
    print("\n--- 3. 内置终端白名单 ---")
    import term
    for bad in (r"py tools/cli.py rm C1 --yes", "board rm C1 --yes",
                "board publish --seat x", "board doctor --fix",
                r"py ..\..\evil.py"):
        try:
            term.plan(bad)
            ok(f"拒绝「{bad}」", False)
        except ValueError:
            ok(f"拒绝「{bad}」", True)
    argv, _ = term.plan("board ls")
    ok("对照：board ls 仍然放行", argv[-1] == "ls", str(argv[-2:]))
    argv, _ = term.plan("py tools/check.py --quick")
    ok("对照：py tools/check.py 仍然放行", "check.py" in argv[1], str(argv[1]))


def t_engine_cmd_injection():
    print("\n--- 4. cmd /c 命令拼接 ---")
    import engines
    # 找一个真实存在的 .cmd（npm 装的那些）；没有就跳过注入部分，只验对照
    real = engines._which("opencode") or engines._which("qoderclicn")
    if real and real.lower().endswith((".cmd", ".bat")):
        rc, out, err = engines._exec([real, "--model", "x&calc"], cwd=str(SANDBOX),
                                     timeout=10)
        ok("含 & 的参数被拒（不经 cmd /c）", rc is None and ("元字符" in err or "拒绝" in err),
           err[:60])
    else:
        print(f"  [SKIP] 本机没有 .cmd 形态的引擎（{real}）")
    rc, out, err = engines._exec([sys.executable, "-c", "print('hi')"], cwd=str(SANDBOX),
                                 timeout=20)
    ok("对照：普通可执行仍然能跑", rc == 0 and "hi" in out, f"rc={rc}")


def t_deliverable_escape():
    print("\n--- 5. 交付物路径越界 ---")
    import board as B
    B.set_root(str(PROJ))
    for bad in (r"C:\Windows\win.ini", r"..\..\etc\passwd", r"out\..\..\x.txt"):
        try:
            B.deliverable_path(bad)
            ok(f"拒绝越界交付物「{bad}」", False)
        except ValueError:
            ok(f"拒绝越界交付物「{bad}」", True)
    (PROJ / "out").mkdir(parents=True, exist_ok=True)
    (PROJ / "out" / "ok.txt").write_text("正常交付物内容，长度够。", encoding="utf-8")
    p = B.deliverable_path("out/ok.txt")
    ok("对照：工作区内相对路径仍然解析", p.exists(), str(p))


def t_store_upsert_and_dup():
    print("\n--- 6. 卡片写入：不再 REPLACE 清历史 / 建卡原子判重 ---")
    import board as B
    B.set_root(str(PROJ))
    B.create_card({"id": "SEC1", "title": "一", "engine": "any", "model": "any",
                   "effort": "any", "human_gate": "none", "deliverables": []})
    B.append_event("SEC1", {"type": "note", "text": "重要历史"})
    n1 = len(B.load_journal("SEC1"))
    card = B.get_card("SEC1")
    card["title"] = "改标题"
    B._store().save_card(card)
    n2 = len(B.load_journal("SEC1"))
    ok("save_card 不再删行（事件流还在）", n2 == n1 and n1 > 0, f"{n1} → {n2}")
    try:
        B.create_card({"id": "SEC1", "title": "重复"})
        ok("同号建卡被拒", False)
    except ValueError as e:
        ok("同号建卡被拒", "已存在" in str(e), str(e)[:40])


def t_audit_lease_mismatch():
    print("\n--- 7. 审计：状态与租约互证 ---")
    rc, out = board("claim", "SEC1", "--seat", "t1")
    ok("对照：能认领", rc == 0, out.strip()[:40])
    con = sqlite3.connect(str(PROJ / "board" / "board.db"))
    con.execute("DELETE FROM leases WHERE card_id='SEC1'")     # 模拟手改库
    con.commit()
    con.close()
    rc, out = board("audit")
    ok("删掉租约行 → audit 报红（退出码 2）", rc == 2 and "没有租约" in out,
       f"rc={rc} {out.strip()[:70]}")


def t_leak_in_reports():
    print("\n--- 8. 错误回包不带家目录 ---")
    import server
    msg = server._safe_msg(Exception(f"缺文件：{Path.home()}\\secret.txt"))
    ok("回包把家目录换成 ~", str(Path.home()) not in msg and "~" in msg, msg[:50])


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)
    PROJ.mkdir(parents=True)
    import projects as P
    P.add_project(PROJ)
    rc, out = board("init")
    assert rc == 0, out

    srv = subprocess.Popen(
        [sys.executable, str(TOOLS / "server.py"), "--port", str(PORT)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                if http("/api/state")[0] == 200:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        t_http_csrf()
        t_path_traversal()
        t_term_allowlist()
        t_engine_cmd_injection()
        t_deliverable_escape()
        t_store_upsert_and_dup()
        t_audit_lease_mismatch()
        t_leak_in_reports()
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except Exception:
            srv.kill()
        shutil.rmtree(SANDBOX, ignore_errors=True)

    print(f"\n{'=' * 50}")
    if fails:
        print(f"✗ 未通过：{'、'.join(fails)}")
        return 1
    print("✓ 安全反向测试全过（每条都配了「正常用法仍然通」的对照）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
