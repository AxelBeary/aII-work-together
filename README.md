# allworktogether

> 让本机**所有 agent（以及人）在同一块看板里分工协作**的工具。

## 这是什么（人话）

我们手上已经有多个能干活的 AI 引擎（codex、opencode、qoderclicn、Hermes…），也有成型的派工方法学（`agent-delegation` 技能）。
但它们现在**各干各的**：任务写在哪、谁接了、做到哪一步、交了什么、卡在哪 —— 分散在几十个会话里，人只能靠记忆和翻聊天记录拼。

**本项目要造的**就是那块**共用的板**：

- 一个任务＝一张卡（目标、领地、验收判据、时限）
- 卡在列之间流动：`待认领 → 进行中 → 待验收 → 完成`（`拍板`／`阻塞` 单独成列）
- **agent 自己认领与回报**；状态变更必须挂**盘上凭据**，不是「模型说完成了」
- **人**在看板上看得见全局、能一键接管、能拍板
- 每个 agent 的动作**可复跑、可追责**：谁在什么时候改了什么，板上有痕

一句话：**把「派工」从聊天记录里搬进一张能一眼看懂的板子。**

## 现状

- 2026-10-19 项目立项：治理层已就位（`AGENTS.md`＋`docs/governance/`），**产品形态待拍板**（见 `docs/governance/DECISIONS.md` D-001）。
- 第一轮调研已派出（见 `docs/research/20261019-agent-board-survey/`）：开源现成轮子／协议底座／本机可复用资产。

## 从哪读起

| 你想干什么 | 读哪里 |
|---|---|
| 进入本项目动手 | `AGENTS.md`（唯一入口） |
| 看本机已实测的坑 | `docs/governance/ENVIRONMENT.md` |
| 看已拍板／待拍板 | `docs/governance/DECISIONS.md` |
| 看有哪些产出物 | `docs/governance/REGISTRY.md` |
| 看派工历史与引擎表现 | `docs/governance/DELEGATION-LEDGER.md` |
| 接手上一轮会话 | `docs/governance/HANDOFF.md` |
