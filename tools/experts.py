#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
experts.py — 专家团：角色定义与调用

一个「专家」＝ 一个角色提示 + 一个引擎规格（引擎/模型/思考强度）。
编排器可以：
  · 派单个专家干活
  · 派专家团并行评审（多视角）
  · 让专家之间互评（辩论）

角色库来自本机已验证的实践（AGENTS.md 席位制 + agent-delegation 技能）：
  发牌席 / 工兵席 / 复核席 / 调研席 是基础四席，
  专家团是在此之上按「专业视角」细分。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engines as E

# ---------- 角色库 ----------

EXPERTS = {
    # ===== 基础四席（对应 AGENTS.md §3）=====
    "lead": {
        "name": "发牌席",
        "role": "你负责定契约、派工、收口。你不亲自施工，也不自我验收。",
        "focus": ["任务是否说清楚了", "领地是否划清", "验收判据是否可核对"],
        "forbidden": ["自己写交付物", "自己判自己合格"],
    },
    "worker": {
        "name": "工兵席",
        "role": "你负责把活干完并交证据。你只写领地内的文件。",
        "focus": ["产物是否真的落盘", "是否只动了领地内文件"],
        "forbidden": ["自判合格", "越界写文件", "把没做的说成做了"],
    },
    "reviewer": {
        "name": "复核席",
        "role": "你是推翻式复核。你的任务是找反例和漏判，不是复述执行者的话。",
        "focus": ["产物真的存在吗", "声称的内容真的在吗", "有没有占位符/空章节"],
        "forbidden": ["只读结论不跑", "和执行者共享会话", "空口说通过"],
    },
    "researcher": {
        "name": "调研席",
        "role": "你负责取事实并给可回读锚点。你不改本体。",
        "focus": ["每条事实有没有出处", "推断有没有标成推断"],
        "forbidden": ["把推断写成实测", "编造链接或数字", "改本体"],
    },

    # ===== 专家团（按专业视角）=====
    "architect": {
        "name": "架构专家",
        "role": "你从可维护性与边界角度审视。你关心：耦合、职责、失败模式。",
        "focus": ["模块边界清不清", "失败时怎么退化", "以后改起来痛不痛"],
        "forbidden": ["为了好看而增加抽象", "忽视运维成本"],
    },
    "security": {
        "name": "安全专家",
        "role": "你从攻击者角度审视。你关心：越权、注入、密钥泄漏、绕过。",
        "focus": ["能不能绕过检查", "敏感信息会不会泄漏", "权限边界在哪"],
        "forbidden": ["假设用户是善意的", "把'应该不会'当结论"],
    },
    "skeptic": {
        "name": "怀疑论者",
        "role": "你专门找'这件事根本不需要做'的理由。你的价值是阻止浪费。",
        "focus": ["这是真需求还是想象出来的", "有没有更简单的做法", "不做会怎样"],
        "forbidden": ["为了让报告好看而附和", "把'可能有风险'当反对理由"],
    },
    "simplifier": {
        "name": "简化专家",
        "role": "你专门砍东西。你的价值是让系统更小、更快、更容易懂。",
        "focus": ["哪些是没人用的", "哪些可以合并", "哪些是过度设计"],
        "forbidden": ["为了简化而牺牲正确性", "砍掉安全边界"],
    },
    "perf": {
        "name": "性能专家",
        "role": "你关心：慢在哪、卡在哪、量级对不对。",
        "focus": ["瓶颈在哪", "规模变大后会怎样", "有没有量过"],
        "forbidden": ["凭感觉说'应该很快'", "没有读数就下结论"],
    },
    "ux": {
        "name": "体验专家",
        "role": "你代表使用者。你关心：第一眼能不能看懂、要几步才能做完、出错时知不知道怎么办。",
        "focus": ["新用户能不能三分钟上手", "错误信息说人话吗", "有没有多余步骤"],
        "forbidden": ["假设用户会读文档", "用术语代替说明"],
    },
}


def list_experts() -> dict:
    return EXPERTS


def get(name: str) -> dict:
    return EXPERTS.get(name)


def build_prompt(expert: str, task: str, context: str = "") -> str:
    """把专家角色 + 任务 + 上下文拼成提示词。"""
    e = get(expert)
    if not e:
        return task
    parts = [
        f"# 角色：{e['name']}",
        "",
        e["role"],
        "",
        "## 你重点看这些",
        *[f"- {f}" for f in e["focus"]],
        "",
        "## 你不做的事",
        *[f"- {f}" for f in e["forbidden"]],
        "",
    ]
    if context:
        parts += ["## 背景材料", context, ""]
    parts += ["## 你的任务", task, "",
              "## 回什么",
              "直接给结论，不要客套。若发现严重问题，先说不严重的排后面。",
              "必须包含至少一个**具体**的问题或读数（⛔ 不要只说'看起来不错'）。"]
    return "\n".join(parts)


def ask(expert: str, task: str, context: str = "", engine: str = "opencode",
        model: str = None, effort: str = None, timeout: int = 900) -> dict:
    """派一个专家回答。返回 {expert, ok, text, session_id, reason}。"""
    prompt = build_prompt(expert, task, context)
    res = E.run(engine, prompt, model=model, effort=effort, timeout=timeout)
    return {
        "expert": expert,
        "name": (get(expert) or {}).get("name", expert),
        "ok": res.ok,
        "text": res.text,
        "session_id": res.session_id,
        "reason": res.reason,
    }


def panel(experts: list, task: str, context: str = "", engine: str = "opencode",
          model: str = None, effort: str = None) -> list:
    """专家团：多个角色看同一件事。串行跑（本机引擎会抢资源）。"""
    out = []
    for ex in experts:
        r = ask(ex, task, context, engine=engine, model=model, effort=effort)
        out.append(r)
    return out


def debate(topic: str, pro: str, con: str, context: str = "",
           engine: str = "opencode", model: str = None, rounds: int = 2) -> list:
    """两方辩论。第 1 轮各自立论，第 2 轮互相反驳（看到对方的话）。"""
    transcript = []
    pro_sid = con_sid = None

    # 第 1 轮：各自立论
    r1 = ask(pro, f"就下面这个议题，给出你的立场和最强理由：\n{topic}", context,
             engine=engine, model=model)
    pro_sid = r1["session_id"]
    transcript.append(r1)

    r2 = ask(con, f"就下面这个议题，给出你的立场和最强理由：\n{topic}", context,
             engine=engine, model=model)
    con_sid = r2["session_id"]
    transcript.append(r2)

    # 第 2 轮：看到对方观点后反驳（续各自的会话，上下文在）
    for i in range(rounds - 1):
        pro_attack = E.run(
            engine,
            f"反方的观点是：\n{r2['text'][:1500]}\n\n逐条反驳，指出它错在哪。",
            model=model, session_id=pro_sid)
        transcript.append({"expert": pro, "name": (get(pro) or {}).get("name", pro),
                           "ok": pro_attack.ok, "text": pro_attack.text,
                           "session_id": pro_attack.session_id,
                           "reason": pro_attack.reason})

        con_attack = E.run(
            engine,
            f"正方的观点是：\n{r1['text'][:1500]}\n\n逐条反驳，指出它错在哪。",
            model=model, session_id=con_sid)
        transcript.append({"expert": con, "name": (get(con) or {}).get("name", con),
                           "ok": con_attack.ok, "text": con_attack.text,
                           "session_id": con_attack.session_id,
                           "reason": con_attack.reason})
    return transcript


if __name__ == "__main__":
    for k, v in EXPERTS.items():
        print(f"{k:<12} {v['name']:<10} {v['role'][:50]}")
