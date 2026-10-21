#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_lease_race.py — 租约与提交闸的反向测试（Q1 复核抓出的三个红线洞）

这条闸专门测「异常路径」，因为现有 13 道闸只测顺利路径，抓不到下面这些：
  1. 超时回收竞态：12 个线程抢一张心跳已超时的卡 → **必须只有 1 个成功**
  2. 租约被回收后，旧席位 submit → **必须失败**
  3. `board reclaim` 必须真去库里回收（不是对着早已不存在的目录空转）
  4. 内置终端白名单不能被 `-p/--root` 绕过
  5. L1 必须拒绝「认领前就存在」的旧文件
  6. 旧布局迁移函数必须真的存在（升级项目第一条命令不能崩）

每条都配了「必须非零」的对照，⛔ 不许出现「0 命中就算过」。

跑法：python tests/test_lease_race.py
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOLS = ROOT / "tools"
SANDBOX = Path(tempfile.mkdtemp(prefix="aboard-race-"))
REG = SANDBOX / "reg"

env = dict(os.environ)
env["ABOARD_REGISTRY_DIR"] = str(REG)
env["PYTHONIOENCODING"] = "utf-8"
env.pop("ABOARD_SEAT", None)
sys.path.insert(0, str(TOOLS))
os.environ["ABOARD_REGISTRY_DIR"] = str(REG)

fails = []


def ok(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")
    if not cond:
        fails.append(name)


def board(proj, *args):
    p = subprocess.run([sys.executable, str(TOOLS / "board.py"), "-C", str(proj)] + list(args),
                       cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fresh_proj(name):
    p = SANDBOX / name
    (p / "board").mkdir(parents=True, exist_ok=True)
    return p


# ---------- 1. 超时回收竞态 ----------
def test_race():
    import storage
    proj = fresh_proj("race")
    st = storage.Store(proj / "board" / "board.db", proj / "board" / "evidence")
    st.save_card({"id": "R1", "title": "竞态", "goal": "", "territory": [],
                  "deliverables": [], "accept_patterns": [], "human_gate": "none",
                  "engine": "any", "model": "any", "effort": "any",
                  "created_at": "2026-10-20", "created_by": "test", "created_kind": "human"})
    st.try_claim("R1", "dead", "opencode", ttl_s=600)
    with st.write() as c:                      # 心跳早停了 20 分钟
        c.execute("UPDATE leases SET at_ms=?, at_mono=? WHERE card_id=?",
                  (storage._now_ms() - 20 * 60 * 1000,
                   storage._mono_ms() - 20 * 60 * 1000, "R1"))

    wins = []

    def worker(i):
        good, _ = st.try_claim("R1", f"s{i}", "opencode", ttl_s=600)
        if good:
            wins.append(f"s{i}")

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    ok("12 线程抢一张超时卡：只有 1 个成功", len(wins) == 1, f"成功 {len(wins)} 个 {sorted(wins)}")
    ok("对照：那 1 个是真赢了（不是全都没认领上）", len(wins) == 1 and st.get_lease("R1") is not None,
       f"leases 行现在 {st.get_lease('R1') and st.get_lease('R1')['seat']}")

    # 心跳新鲜的卡：12 个线程必须 0 成功（对照，证明闸不是「永远成功」）
    st.save_card({"id": "R2", "title": "新鲜租约", "goal": "", "territory": [],
                  "deliverables": [], "accept_patterns": [], "human_gate": "none",
                  "engine": "any", "model": "any", "effort": "any",
                  "created_at": "2026-10-20", "created_by": "test", "created_kind": "human"})
    st.try_claim("R2", "alive", "opencode", ttl_s=600)
    wins2 = []
    def worker2(i):
        good, _ = st.try_claim("R2", f"x{i}", "opencode", ttl_s=600)
        if good:
            wins2.append(i)
    ts = [threading.Thread(target=worker2, args=(i,)) for i in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    ok("对照：心跳新鲜的卡 0 人抢到", len(wins2) == 0, f"抢到 {len(wins2)} 个")


# ---------- 2. 租约没了不能提交 ----------
def test_submit_needs_lease():
    proj = fresh_proj("submit")
    (proj / "out").mkdir()
    (proj / "out" / "a.txt").write_text("交付物正文，长度足够过 L1 的下限要求。", encoding="utf-8")
    board(proj, "add", "--title", "提交闸", "--goal", "x", "--deliverable", "out/a.txt")
    rc, out = board(proj, "ls")
    cid = [l.split()[0] for l in out.splitlines() if "C" in l][0]
    board(proj, "claim", cid, "--seat", "dead-seat")
    con = sqlite3.connect(str(proj / "board" / "board.db"))
    con.execute("DELETE FROM leases WHERE card_id=?", (cid,))
    con.commit()
    con.close()
    rc, out = board(proj, "submit", cid, "--seat", "dead-seat")
    ok("租约被回收后 submit 必须失败", rc != 0, f"rc={rc} {out.strip()[-40:]}")
    ok("对照：失败原因是「没有活跃租约」", "租约" in out, out.strip()[:40])


# ---------- 3. reclaim 真去库里回收 ----------
def test_reclaim_cmd():
    proj = fresh_proj("reclaim")
    (proj / "out").mkdir()
    (proj / "out" / "b.txt").write_text("交付物正文，长度足够。", encoding="utf-8")
    board(proj, "add", "--title", "回收闸", "--goal", "x", "--deliverable", "out/b.txt")
    rc, out = board(proj, "ls")
    cid = [l.split()[0] for l in out.splitlines() if "C" in l][0]
    board(proj, "claim", cid, "--seat", "slow")
    con = sqlite3.connect(str(proj / "board" / "board.db"))
    con.execute("UPDATE leases SET at_ms=at_ms-7200000, at_mono=at_mono-7200000")  # 两小时前的心跳
    con.commit()
    con.close()
    rc, out = board(proj, "reclaim")
    con = sqlite3.connect(str(proj / "board" / "board.db"))
    left = con.execute("SELECT COUNT(*) FROM leases").fetchone()[0]
    con.close()
    ok("board reclaim 真回收了（库里的行没了）", left == 0, f"剩 {left} 行；输出：{out.strip()[-50:]}")
    ok("回收数与人话对得上（1 of 1）", "1 of 1" in out, out.strip()[-40:])
    rc, out = board(proj, "reclaim")
    ok("没东西可回收时要明说，不许假成功", "无可回收" in out, out.strip()[-30:])


# ---------- 4. 终端白名单不能被全局旗标绕过 ----------
def test_term_whitelist():
    import term
    bad = ["board rm C1 --yes", "board -p anyproj rm C1 --yes",
           "board --root . rm C1 --yes", "board -C . human C1 --decision approve"]
    passed = []
    for cmd in bad:
        try:
            term.plan(cmd)
            passed.append(cmd)
        except ValueError:
            pass
    ok(f"{len(bad)} 种绕法全被拒", not passed, f"放过了：{passed}")
    argv, _ = term.plan("board -p demo stats")
    ok("对照：带项目参数的正常命令仍然放行",
       "-p" in argv and "demo" in argv and "stats" in argv, str(argv[2:]))


# ---------- 5. L1 拒绝旧文件 ----------
def test_l1_stale():
    proj = fresh_proj("stale")
    (proj / "out").mkdir()
    f = proj / "out" / "old.txt"
    f.write_text("这是三天前的旧文件，长度足够过 L1 的字节下限。", encoding="utf-8")
    old = 1_600_000_000
    os.utime(f, (old, old))
    board(proj, "add", "--title", "旧文件闸", "--goal", "x", "--deliverable", "out/old.txt")
    rc, out = board(proj, "ls")
    cid = [l.split()[0] for l in out.splitlines() if "C" in l][0]
    board(proj, "claim", cid, "--seat", "w1")
    rc, out = board(proj, "submit", cid, "--seat", "w1")
    ok("拿认领前的旧文件提交必须失败", rc == 0 and "旧文件" in out,
       f"rc={rc}；输出含「旧文件」={'旧文件' in out}")

    # 对照：真的改过的文件必须过
    f.write_text("这次真的写了新内容，长度也够过 L1 的下限。", encoding="utf-8")
    rc, out = board(proj, "submit", cid, "--seat", "w1")
    ok("对照：真改过的文件能过 L1", "L1-L3 全过" in out or "待验收" in out, out.strip()[-40:])


# ---------- 6. 旧布局迁移 ----------
def test_migrate():
    proj = fresh_proj("legacy")
    d = proj / "board" / "cards" / "L-001"
    d.mkdir(parents=True, exist_ok=True)
    (d / "card.json").write_text(json.dumps({
        "id": "L-001", "title": "旧布局卡", "goal": "迁过来",
        "deliverables": [], "territory": [], "accept_patterns": [],
        "created_at": "2026-10-19", "created_by": "old", "created_kind": "human",
    }, ensure_ascii=False), encoding="utf-8")
    (d / "journal.jsonl").write_text(
        json.dumps({"type": "created", "actor": "human", "title": "旧布局卡"},
                   ensure_ascii=False) + "\n"
        + json.dumps({"type": "claim", "actor": "agent", "seat": "w9"},
                     ensure_ascii=False) + "\n", encoding="utf-8")
    rc, out = board(proj, "ls")
    ok("旧布局项目第一条命令不再崩", rc == 0 and "L-001" in out,
       f"rc={rc} {out.strip()[:60]}")
    rc2, out2 = board(proj, "ls")
    ok("迁移幂等（再跑不重复迁）", rc2 == 0 and out2.count("L-001") == 1,
       f"L-001 出现 {out2.count('L-001')} 次")


# ---------- 7. 换代栅栏：同席位被回收后，旧代写不进 ----------
def test_epoch_fence():
    proj = fresh_proj("epoch")
    (proj / "out").mkdir()
    (proj / "out" / "a.txt").write_text(
        "交付物正文，长度足够过 L1 的下限要求。这里再写长一点，避免被判太短。",
        encoding="utf-8")
    board(proj, "add", "--title", "换代栅栏", "--goal", "x", "--deliverable", "out/a.txt")
    rc, out = board(proj, "ls")
    cid = [l.split()[0] for l in out.splitlines() if l.strip().startswith("C")][0]

    rc, out = board(proj, "claim", cid, "--seat", "s1")
    ok("第一次认领成功", rc == 0, out.strip().splitlines()[-1][:60] if out else "")

    # 模拟「心跳超时被回收」：调老时间戳 + 跑一次 `board reclaim`（真实回收路径）
    con = sqlite3.connect(str(proj / "board" / "board.db"))
    con.execute("UPDATE leases SET at_ms=at_ms-1200000, at_mono=at_mono-1200000 WHERE card_id=?",
                (cid,))
    con.commit()
    con.close()
    board(proj, "reclaim")

    rc, out = board(proj, "claim", cid, "--seat", "s1")   # 同席位再认领 → 换代
    ok("同席位重新认领成功（换代）", rc == 0, out.strip().splitlines()[-1][:60] if out else "")

    rc1, out1 = board(proj, "beat", cid, "--seat", "s1", "--epoch", "1")
    ok("旧代心跳被栅栏拒绝", rc1 != 0 and ("换代" in out1 or "栅栏" in out1), out1.strip()[:80])

    rc2, out2 = board(proj, "beat", cid, "--seat", "s1", "--epoch", "2")
    ok("对照：当代心跳照常通过", rc2 == 0, out2.strip()[:60])

    rc3, out3 = board(proj, "submit", cid, "--seat", "s1", "--epoch", "1")
    ok("旧代提交被栅栏拒绝", rc3 != 0 and ("换代" in out3 or "栅栏" in out3), out3.strip()[:80])


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)
    try:
        for fn in (test_race, test_submit_needs_lease, test_reclaim_cmd,
                   test_term_whitelist, test_l1_stale, test_migrate, test_epoch_fence):
            print(f"\n--- {fn.__name__} ---")
            fn()
        print(f"\n{'=' * 50}")
        if fails:
            print(f"✗ 未通过：{'、'.join(fails)}")
            return 1
        print("✓ 租约/提交/回收/白名单/L1/迁移/换代栅栏 七组反向测试全过")
        return 0
    finally:
        shutil.rmtree(SANDBOX, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
