#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check.py — 一条命令跑完全部自检

用法：
  python tools/check.py          # 全部检查（改完代码就跑这个）
  python tools/check.py --quick  # 跳过会真调模型的检查

包含 16 道闸（下面 5 组是分类，具体条数以运行时输出为准）：
  1. 语法        所有 .py 都能 parse
  2. 回归        23 条冻结行为
  3. 反向测试    故意改坏一处必须被抓住
  4. 断点续跑    杀了能接、不重做
  5. 体检+审计   无残留、无绕过痕迹
"""
import argparse
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(name, cmd, expect_rc=0):
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    ok = (p.returncode == expect_rc)
    tail = [l for l in out.strip().splitlines() if l.strip()][-2:]
    print(f"  {'✓' if ok else '✗'} {name:<12} " + " ｜ ".join(t.strip()[:60] for t in tail))
    return ok, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="跳过真调模型的检查")
    ap.add_argument("--perf", action="store_true",
                    help="额外跑规模压测（造 1200 张卡，约 1 分钟；机器忙时别开）")
    a = ap.parse_args()

    print("=" * 70)
    print("全量自检")
    print("=" * 70)

    fails = []

    # 1 语法
    bad = []
    for p in list((ROOT / "tools").rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        try:
            ast.parse(p.read_text(encoding="utf-8"))
        except Exception as e:
            bad.append(f"{p.name}: {e}")
    print(f"  {'✓' if not bad else '✗'} {'语法':<12} " +
          (f"{len(list((ROOT/'tools').rglob('*.py'))) + len(list((ROOT/'tests').rglob('*.py')))} 个文件" if not bad else bad[0][:60]))
    if bad:
        fails.append("语法")

    # 1b 子命令烟测：每条 --help 都要能起来（抓「导入漏了 / 参数写坏」）
    subs = ["init", "project", "open", "add", "new", "publish", "ready", "ls",
            "show", "claim", "budget", "beat", "block", "submit", "verify", "review",
            "human", "token", "reclaim", "audit", "doctor", "html", "overview",
            "inbox", "all", "stats", "cost", "rm", "msg"]
    smoke_bad = []
    for s in subs:
        p = subprocess.run([PY, "tools/board.py", s, "--help"], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if p.returncode != 0:
            smoke_bad.append(s)
    print(f"  {'✓' if not smoke_bad else '✗'} {'子命令烟测':<10} "
          + (f"{len(subs)} 条" if not smoke_bad else f"失败：{smoke_bad[:5]}"))
    if smoke_bad:
        fails.append("子命令烟测")

    # 1c 界面 JS 语法（整页脚本一个错字就白屏；有 node 才查，没有就跳过）
    import re
    import shutil as _sh
    node = _sh.which("node")
    if node:
        html = (ROOT / "tools" / "ui.html").read_text(encoding="utf-8")
        m = re.search(r"<script>(.*?)</script>", html, re.S)
        if not m:
            print(f"  ✗ {'界面语法':<10} 找不到 script 块")
            fails.append("界面语法")
        else:
            tmp = ROOT / "board" / "_ui_check.js"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(m.group(1), encoding="utf-8")
            p = subprocess.run([node, "--check", str(tmp)], capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            tmp.unlink(missing_ok=True)
            okjs = p.returncode == 0
            print(f"  {'✓' if okjs else '✗'} {'界面语法':<10} " +
                  (f"{len(m.group(1))} 字符" if okjs else (p.stderr or "")[:60]))
            if not okjs:
                fails.append("界面语法")
    else:
        print(f"  - {'界面语法':<10} 没装 node，跳过")

    # 2 回归
    ok, _ = run("回归库", [PY, "tests/run_regression.py"])
    if not ok:
        fails.append("回归库")

    # 3 反向测试
    ok, _ = run("反向测试", [PY, "tests/run_regression.py", "--break"])
    if not ok:
        fails.append("反向测试")

    # 4 断点续跑
    ok, _ = run("断点续跑", [PY, "tests/test_resume.py"])
    if not ok:
        fails.append("断点续跑")

    # 4b 多项目（几十个项目同用是第一需求，单项目回归覆盖不到）
    ok, _ = run("多项目", [PY, "tests/test_multiproject.py"])
    if not ok:
        fails.append("多项目")

    # 4c 界面并发隔离（实测过：不锁会把卡建到别的项目）
    ok, _ = run("并发隔离", [PY, "tests/test_ui_concurrency.py"])
    if not ok:
        fails.append("并发隔离")

    # 4d 接口形状契约（托盘/界面都靠这些字段，改后端不能静默弄坏它们）
    ok, _ = run("接口契约", [PY, "tests/test_ui_api.py"])
    if not ok:
        fails.append("接口契约")

    # 4e 点对点评审（评审席只准看、不准改；空材料必须报错）
    ok, _ = run("点对点评审", [PY, "tests/test_consult.py"])
    if not ok:
        fails.append("点对点评审")

    # 4f 跨会话留言（append-only、唤醒不假报成功、不重发）
    ok, _ = run("留言", [PY, "tests/test_messages.py"])
    if not ok:
        fails.append("留言")

    # 4g 租约竞态/提交闸/回收/终端白名单/L1 旧文件/旧布局迁移（专测异常路径）
    ok, _ = run("租约竞态", [PY, "tests/test_lease_race.py"])
    if not ok:
        fails.append("租约竞态")

    # 4h 预算刹车/依赖/错误分级/刹车权限/拍板 diff（B 批，反空跑对照齐全）
    ok, _ = run("预算与依赖", [PY, "tests/test_budget_deps.py"])
    if not ok:
        fails.append("预算与依赖")

    # 4i 安全加固反向（2026-10-21 安全扫描 F-01…F-23：CSRF/Host/卡号路径/终端白名单/
    #    cmd 注入/交付物越界/REPLACE 清历史/审计互证/错误回包脱敏）
    ok, _ = run("安全反向", [PY, "tests/test_security.py"])
    if not ok:
        fails.append("安全反向")

    # 4j 结构化复核意见 + 收口刹车（2026-10-23）：带 open 意见不许 PASS、
    #    全 fixed 不许 FAIL、同一意见第 3 轮默认拦下（--force 才放行）
    ok, _ = run("意见对账", [PY, "tests/test_review_items.py"])
    if not ok:
        fails.append("意见对账")

    # 4k 外部门禁 L4（2026-10-23）：卡上声明的 check_cmd 在提交时必跑；
    #    只对人建的卡生效；非零/超时/起不来 一律不过
    ok, _ = run("外部门禁", [PY, "tests/test_check_cmd.py"])
    if not ok:
        fails.append("外部门禁")

    # 4l 批量建卡（2026-10-23）：幂等 / dry-run / check_cmd 准入 / 部分失败不静默
    ok, _ = run("批量建卡", [PY, "tests/test_batch.py"])
    if not ok:
        fails.append("批量建卡")

    # 4m 重试编排（2026-10-23）：额度制（默认 3 次返工）、用完不静默、--force 才加且留痕
    ok, _ = run("重试编排", [PY, "tests/test_retry.py"])
    if not ok:
        fails.append("重试编排")

    # 5 体检 + 审计
    ok, out = run("审计", [PY, "tools/board.py", "audit"])
    if not ok:
        fails.append("审计")
    ok2, out2 = run("体检", [PY, "tools/board.py", "doctor"])
    if not ok2:
        fails.append("体检")

    # 6（可选）真跑
    if not a.quick:
        ok, _ = run("辩论（真跑）", [PY, "tests/test_debate.py"])
        if not ok:
            fails.append("辩论")

    # 7（可选）规模压测：几十个项目时界面还跟不跟得上
    # 规模刻意轻量（20×15）：重规模会把用户机器拖慢（见 ENVIRONMENT.md E-25）
    if a.perf:
        ok, _ = run("规模压测", [PY, "tests/bench_scale.py"])
        if not ok:
            fails.append("规模压测")

    print("=" * 70)
    if fails:
        print(f"✗ 未通过：{'、'.join(fails)}")
        return 1
    print("✓ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
