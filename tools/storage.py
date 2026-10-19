#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
storage.py — SQLite 存储层

为什么换掉「文件即卡」（2026-10-20，用户拍板）：
  · 原子认领原来靠 `os.mkdir` 固定名目录——能用，但脆（错一个名字就退化）
  · journal 并发追加要靠手写跨进程文件锁——能用，但容易漏
  · SQLite 有真事务：认领＝`INSERT` 撞 PRIMARY KEY，写＝`BEGIN IMMEDIATE` 串行化
  ⇒ 上游两个真缺陷（长任务被抢、哈希链分叉）的**根因被消除**，不再靠补丁

不换的部分：
  · 交付物仍在工作区里当普通文件（产物就该是人能直接看的）
  · 证据文件仍落盘（board/evidence/<card>/）
  · 事件仍是 append-only + 哈希链（一致性自检保留）

⚠️ 诚实边界：SQLite 能防**并发冲突**，防不住**有写权限的人改库**。
   哈希链只能做一致性自检，不是安全边界（同 E-18）。
"""
import hashlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS cards (
  id             TEXT PRIMARY KEY,
  title          TEXT NOT NULL,
  goal           TEXT DEFAULT '',
  territory      TEXT DEFAULT '[]',
  deliverables   TEXT DEFAULT '[]',
  accept_patterns TEXT DEFAULT '[]',
  human_gate     TEXT DEFAULT 'none',
  engine         TEXT DEFAULT 'any',
  model          TEXT DEFAULT 'any',
  effort         TEXT DEFAULT 'any',
  irreversible   INTEGER DEFAULT 0,
  allow_no_numbers INTEGER DEFAULT 0,
  source_card    TEXT,
  created_at     TEXT,
  created_by     TEXT,
  created_kind   TEXT DEFAULT 'human'
);

CREATE TABLE IF NOT EXISTS events (
  seq      INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id  TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
  at       TEXT,
  at_ms    INTEGER,
  type     TEXT NOT NULL,
  data     TEXT NOT NULL,
  prev     TEXT,
  hash     TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_card ON events(card_id, seq);

-- ⭐ 认领的原子性就来自这里的 PRIMARY KEY(card_id)
CREATE TABLE IF NOT EXISTS leases (
  card_id  TEXT PRIMARY KEY REFERENCES cards(id) ON DELETE CASCADE,
  seat     TEXT NOT NULL,
  engine   TEXT,
  model    TEXT,
  effort   TEXT,
  epoch    INTEGER DEFAULT 0,
  at_ms    INTEGER,
  ttl_s    INTEGER
);

CREATE TABLE IF NOT EXISTS lease_log (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id  TEXT NOT NULL,
  seat     TEXT,
  kind     TEXT,
  at       TEXT,
  at_ms    INTEGER,
  detail   TEXT
);
"""


def _now_ms():
    return int(time.time() * 1000)


def _ts():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S%z")


class Store:
    """一个项目一个库。"""

    def __init__(self, db_path, evidence_dir=None):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_dir = Path(evidence_dir) if evidence_dir else self.path.parent / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        # 读连接：每线程一个（SQLite 连接不是线程安全的；共享会报
        # "bad parameter or other API misuse"）。写走 _WriteTx 的独立连接。
        self._local = threading.local()
        self._init_schema()

    def _read_conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA busy_timeout=30000")
            self._local.conn = c
        return c

    def _init_schema(self):
        c = self._read_conn()
        c.executescript(SCHEMA)
        c.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version',?)",
                  (str(SCHEMA_VERSION),))

    def close(self):
        c = getattr(self._local, "conn", None)
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
            self._local.conn = None

    # ---------- 事务 ----------

    def write(self):
        """写事务上下文：BEGIN IMMEDIATE 让写者串行，避免『database is locked』。"""
        return _WriteTx(self.path)


    # ---------- 卡片 ----------

    def save_card(self, card: dict):
        cols = ("id", "title", "goal", "territory", "deliverables",
                "accept_patterns", "human_gate", "engine", "model", "effort",
                "irreversible", "allow_no_numbers", "source_card",
                "created_at", "created_by", "created_kind")
        vals = []
        for c in cols:
            v = card.get(c)
            if c in ("territory", "deliverables", "accept_patterns"):
                v = json.dumps(v or [], ensure_ascii=False)
            elif c == "irreversible":
                v = 1 if v else 0
            elif c == "allow_no_numbers":
                v = 1 if card.get("allow_no_numbers") else 0
            vals.append(v)
        placeholders = ",".join("?" * len(cols))
        with self.write() as c:
            c.execute(
                f"INSERT OR REPLACE INTO cards({','.join(cols)}) VALUES({placeholders})",
                vals)

    def get_card(self, cid: str):
        r = self._read_conn().execute("SELECT * FROM cards WHERE id=?", (cid,)).fetchone()
        if not r:
            return None
        return self._row_to_card(r)

    def all_cards(self):
        rows = self._read_conn().execute("SELECT * FROM cards ORDER BY id").fetchall()
        return [self._row_to_card(r) for r in rows]

    @staticmethod
    def _row_to_card(r):
        d = dict(r)
        for k in ("territory", "deliverables", "accept_patterns"):
            try:
                d[k] = json.loads(d.get(k) or "[]")
            except Exception:
                d[k] = []
        d["irreversible"] = bool(d.get("irreversible"))
        d["allow_no_numbers"] = bool(d.get("allow_no_numbers"))
        return d

    # ---------- 事件（append-only + 哈希链）----------

    @staticmethod
    def _hash(prev: str, data_obj) -> str:
        raw = prev + json.dumps(data_obj, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def append_event(self, cid: str, ev: dict) -> dict:
        with self.write() as c:
            row = c.execute(
                "SELECT hash FROM events WHERE card_id=? ORDER BY seq DESC LIMIT 1",
                (cid,)).fetchone()
            prev = (row["hash"] if row else "") or ""
            data = {k: v for k, v in ev.items()
                    if k not in ("seq", "at", "at_ms", "prev", "hash")}
            obj = {"at": _ts(), "at_ms": _now_ms(), **data}
            h = self._hash(prev, obj)
            cur = c.execute(
                "INSERT INTO events(card_id,at,at_ms,type,data,prev,hash) "
                "VALUES(?,?,?,?,?,?,?)",
                (cid, obj["at"], obj["at_ms"], obj.get("type", "?"),
                 json.dumps(data, ensure_ascii=False), prev, h))
            obj["seq"] = cur.lastrowid
            obj["prev"] = prev
            obj["hash"] = h
            return obj

    def events(self, cid: str):
        rows = self._read_conn().execute(
            "SELECT seq,at,at_ms,type,data,prev,hash FROM events "
            "WHERE card_id=? ORDER BY seq", (cid,)).fetchall()
        out = []
        for r in rows:
            try:
                data = json.loads(r["data"])
            except Exception:
                data = {}
            out.append({"seq": r["seq"], "at": r["at"], "at_ms": r["at_ms"],
                        "type": r["type"], **data,
                        "prev": r["prev"], "hash": r["hash"]})
        return out

    def event_count(self, cid: str) -> int:
        r = self._read_conn().execute("SELECT COUNT(*) n FROM events WHERE card_id=?",
                              (cid,)).fetchone()
        return r["n"] if r else 0

    def verify_chain(self, cid: str):
        prev = ""
        for i, ev in enumerate(self.events(cid), 1):
            if not ev.get("hash"):
                return False, f"第 {i} 条无 hash"
            if ev.get("prev", "") != prev:
                return False, f"第 {i} 条 prev 断裂"
            body = {k: v for k, v in ev.items()
                    if k not in ("seq", "at", "at_ms", "prev", "hash")}
            obj = {"at": ev["at"], "at_ms": ev["at_ms"], **body}
            if self._hash(prev, obj) != ev["hash"]:
                return False, f"第 {i} 条 hash 不符（内容被改过）"
            prev = ev["hash"]
        return True, ""

    # ---------- 租约（原子性来自 PRIMARY KEY）----------

    def get_lease(self, cid: str):
        r = self._read_conn().execute("SELECT * FROM leases WHERE card_id=?",
                              (cid,)).fetchone()
        return dict(r) if r else None

    def try_claim(self, cid: str, seat: str, engine=None, model=None,
                  effort=None, epoch: int = 0, ttl_s: int = 600,
                  now_ms: int = None):
        """原子认领。返回 (ok, 原因)。

        互斥来自 leases.card_id 的 PRIMARY KEY：INSERT 撞键＝别人已持有。
        ⛔ 不是「先查后插」。
        """
        now_ms = now_ms or _now_ms()
        try:
            with self.write() as c:
                c.execute(
                    "INSERT INTO leases(card_id,seat,engine,model,effort,epoch,"
                    "at_ms,ttl_s) VALUES(?,?,?,?,?,?,?,?)",
                    (cid, seat, engine, model, effort, epoch, now_ms, ttl_s))
                c.execute(
                    "INSERT INTO lease_log(card_id,seat,kind,at,at_ms,detail) "
                    "VALUES(?,?,?,?,?,?)",
                    (cid, seat, "acquire", _ts(), now_ms, engine or ""))
            return True, ""
        except sqlite3.IntegrityError:
            cur = self.get_lease(cid)
            if not cur:
                return False, "被别人抢先了"
            age = (now_ms - (cur.get("at_ms") or 0)) / 1000
            if age > (cur.get("ttl_s") or ttl_s):
                # 超时 → 回收后重试一次
                self.reclaim(cid, reason=f"心跳超时 {int(age)}s")
                return self.try_claim(cid, seat, engine, model, effort, epoch,
                                      ttl_s, now_ms)
            return False, (f"卡片已被占用（{cur.get('seat')}，"
                           f"心跳 {int(age)}s 前）")

    def touch_lease(self, cid: str, seat: str):
        with self.write() as c:
            cur = c.execute(
                "UPDATE leases SET at_ms=? WHERE card_id=? AND seat=?",
                (_now_ms(), cid, seat))
            n = cur.rowcount          # ⚠️ 必须在连接关闭前取
            c.execute(
                "INSERT INTO lease_log(card_id,seat,kind,at,at_ms,detail) "
                "VALUES(?,?,?,?,?,?)", (cid, seat, "heartbeat", _ts(), _now_ms(), ""))
        return n > 0

    def release_lease(self, cid: str, kind: str = "released"):
        cur = self.get_lease(cid)
        with self.write() as c:
            c.execute("DELETE FROM leases WHERE card_id=?", (cid,))
            c.execute(
                "INSERT INTO lease_log(card_id,seat,kind,at,at_ms,detail) "
                "VALUES(?,?,?,?,?,?)",
                (cid, (cur or {}).get("seat"), kind, _ts(), _now_ms(), ""))
        return cur

    def reclaim(self, cid: str, reason: str = "心跳超时"):
        cur = self.get_lease(cid)
        with self.write() as c:
            c.execute("DELETE FROM leases WHERE card_id=?", (cid,))
            c.execute(
                "INSERT INTO lease_log(card_id,seat,kind,at,at_ms,detail) "
                "VALUES(?,?,?,?,?,?)",
                (cid, (cur or {}).get("seat"), "reclaimed", _ts(), _now_ms(), reason))
        return cur

    def expired_leases(self, now_ms: int = None):
        now_ms = now_ms or _now_ms()
        rows = self._read_conn().execute("SELECT * FROM leases").fetchall()
        out = []
        for r in rows:
            age = (now_ms - (r["at_ms"] or 0)) / 1000
            if age > (r["ttl_s"] or 600):
                out.append({**dict(r), "age_s": int(age)})
        return out

    def lease_log(self, cid: str = None):
        if cid:
            rows = self._read_conn().execute(
                "SELECT * FROM lease_log WHERE card_id=? ORDER BY id", (cid,)).fetchall()
        else:
            rows = self._read_conn().execute(
                "SELECT * FROM lease_log ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    # ---------- 证据 ----------

    def evidence_path(self, cid: str) -> Path:
        d = self.evidence_dir / cid
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ---------- 维护 ----------

    def integrity(self):
        r = self._read_conn().execute("PRAGMA integrity_check").fetchone()
        return (r[0] == "ok"), r[0]

    def vacuum(self):
        self._read_conn().execute("VACUUM")

    def stats(self):
        return {
            "cards": self._read_conn().execute("SELECT COUNT(*) n FROM cards").fetchone()["n"],
            "events": self._read_conn().execute("SELECT COUNT(*) n FROM events").fetchone()["n"],
            "leases": self._read_conn().execute("SELECT COUNT(*) n FROM leases").fetchone()["n"],
            "size": self.path.stat().st_size if self.path.exists() else 0,
        }


class _WriteTx:
    """每次写开一个独立连接 + BEGIN IMMEDIATE。

    为什么不用共享连接：SQLite 连接不是线程安全的，靠 Python 锁串行化
    既要小心重入、又要小心事务残留；而「一写一连接」是 SQLite 官方推荐做法，
    天然支持多线程与多进程（team + 多项目场景必需）。
    """

    def __init__(self, path):
        self.path = str(path)
        self.conn = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.conn.execute("ROLLBACK")
            else:
                self.conn.execute("COMMIT")
        finally:
            self.conn.close()
            self.conn = None
        return False
