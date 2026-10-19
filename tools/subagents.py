#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
subagents.py — 子代理：真正的独立会话

与 orchestrator 的区别：
  orchestrator = 按卡跑流程（看板驱动）
  subagents    = 按需起独立会话干活（编排器/专家团/辩论都用它）

关键能力（全部实测，2026-10-19）：
  · 独立上下文   每个子代理一个新 session，互不污染
  · 会话续接     带 session_id 可续（上下文全在，实测记住了 42）
  · 分叉         带 fork 可保留原会话再续
  · 并行         多个子代理同时跑（引擎层面支持，但本机建议 ≤2）
"""
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engines as E


class SubAgent:
    """一个子代理 = 一个独立会话 + 一份任务。"""

    def __init__(self, task: str, engine: str = "opencode", model: str = None,
                 effort: str = None, agent: str = None, role: str = None,
                 name: str = None, cwd: str = None):
        self.id = f"sub-{uuid.uuid4().hex[:6]}"
        self.name = name or self.id
        self.task = task
        self.engine = engine
        self.model = model
        self.effort = effort
        self.agent = agent        # opencode 内置 agent: build/plan/general/explore
        self.role = role          # 专家角色名（experts.py）
        self.cwd = cwd
        self.session_id = None
        self.result = None
        self.history = []

    def run(self, extra: str = None) -> dict:
        prompt = self.task if not extra else f"{self.task}\n\n{extra}"
        if self.role:
            import experts
            prompt = experts.build_prompt(self.role, prompt)
        res = E.run(self.engine, prompt, cwd=self.cwd, model=self.model,
                    effort=self.effort, agent=self.agent,
                    session_id=self.session_id)
        self.session_id = res.session_id or self.session_id
        self.result = res
        rec = {"name": self.name, "ok": res.ok, "text": res.text,
               "session_id": self.session_id, "reason": res.reason,
               "engine": self.engine, "model": res.model_used or self.model}
        self.history.append(rec)
        return rec

    def follow_up(self, message: str) -> dict:
        """续同一个会话追问（上下文保留）。"""
        if not self.session_id:
            return self.run(extra=message)
        res = E.run(self.engine, message, cwd=self.cwd, model=self.model,
                    effort=self.effort, agent=self.agent,
                    session_id=self.session_id)
        rec = {"name": self.name, "ok": res.ok, "text": res.text,
               "session_id": self.session_id, "reason": res.reason,
               "engine": self.engine, "model": res.model_used or self.model}
        self.history.append(rec)
        return rec

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "role": self.role,
            "engine": self.engine, "model": self.model, "effort": self.effort,
            "agent": self.agent, "session_id": self.session_id,
            "history": self.history,
        }


def spawn(tasks: list, engine: str = "opencode", model: str = None,
          effort: str = None, parallel: bool = False, max_workers: int = 2,
          cwd: str = None) -> list:
    """批量起子代理。

    tasks: [{"task": "...", "name": "...", "role": "...", "agent": "..."}]
    parallel: 是否并行（本机建议 False 或 max_workers<=2，引擎会抢资源）
    """
    agents = []
    for t in tasks:
        if isinstance(t, str):
            t = {"task": t}
        agents.append(SubAgent(
            task=t["task"], engine=t.get("engine", engine),
            model=t.get("model", model), effort=t.get("effort", effort),
            agent=t.get("agent"), role=t.get("role"),
            name=t.get("name"), cwd=cwd))

    results = []
    if parallel:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(a.run): a for a in agents}
            for f in as_completed(futs):
                a = futs[f]
                try:
                    results.append(f.result())
                except Exception as e:
                    results.append({"name": a.name, "ok": False,
                                    "text": "", "reason": f"异常：{e}"})
    else:
        for a in agents:
            results.append(a.run())

    # 保持输入顺序
    order = {a.name: i for i, a in enumerate(agents)}
    results.sort(key=lambda r: order.get(r.get("name"), 99))
    return results


def gather_summary(results: list) -> str:
    """把多个子代理的结果汇总成一段可读的文本。"""
    lines = []
    ok_n = sum(1 for r in results if r.get("ok"))
    lines.append(f"共 {len(results)} 个子代理，{ok_n} 个正常返回。")
    lines.append("")
    for r in results:
        status = "✓" if r.get("ok") else "✗"
        name = r.get("name", "?")
        text = (r.get("text") or r.get("reason") or "").strip()
        lines.append(f"### {status} {name}")
        lines.append(text[:1200] if text else "（无输出）")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    # 自测：起两个独立子代理
    res = spawn([
        {"task": "只回复三个字：我是A", "name": "A"},
        {"task": "只回复三个字：我是B", "name": "B"},
    ], model="opencode-go/deepseek-v4.1-flash")
    print(gather_summary(res))
