# 鸣谢 / Acknowledgements

这个项目的代码是自写的，但**思路不是凭空来的**。这一页把「学过谁、借过什么、用过什么」逐条写清楚，
免得日后有人问「这是不是抄的」时只能靠猜。

分三类：**用过的代码**（有法律义务）／**借鉴的思路**（无法律义务，但应当致谢）／**调研参考**（只读过，没用过）。

---

## 一、用过的代码（随仓库分发）

| 件 | 许可 | 说明 |
|---|---|---|
| Microsoft Edge WebView2 SDK 1.0.4258.31（3 个 DLL） | Microsoft WebView2 SDK License（BSD-3 式，**非 MIT**） | 桌面壳用它承载界面。许可证全文与义务履行见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。 |

**除这 3 个 DLL 之外，本仓库不含任何第三方代码**：无第三方 Python 包、无前端框架、无 CDN 外链、
无第三方图标素材。这一点做过全仓溯源核验，依据写在 THIRD-PARTY-NOTICES.md §2。

---

## 二、借鉴的思路（独立实现，未复制代码）

### [ocs — Open Cross-session](https://github.com/leeguooooo/open-cross-session)（MIT，Copyright (c) 2026 leeguooooo）

跨会话留言的四条**语义**借自它，实现完全重写（SQLite 三表 + 续会话唤醒，不是它的 JSONL/Unix socket 方案）：

1. append-only ＋ 单调 seq（历史不可改，可寻址）；
2. `HELD` —— 「存下了但唤不醒」必须如实上报，不许说成「送到了」；
3. 退出码分档（本项目的 2/3 与它的 2/3 含义**并不相同**，是按自己的语义重定的）；
4. **一律不重发** —— 已回复过的不再投递（防对方答两遍、防重复扣费）。

对照记录：`tools/messages.py` 文件头、`docs/governance/DECISIONS.md` 的 D-014。

### 作者本人的其它项目（只借范式，不共享代码）

| 项目 | 许可状态 | 借了什么 |
|---|---|---|
| `sentinel-ops` | 无许可证文件（`dock/Cargo.toml` 写有 `MIT OR Apache-2.0`，但无正文 ⇒ 不构成对外授权） | 治理范式：席位／领地／闸门／证据分级 |
| `agent-delegation`（技能） | 无许可证文件 | 委派方法学：该不该派、派给谁、怎么收 |
| `waypost` | 无许可证文件（README 明写「暂未选许可证（私有仓）」） | 值班／守护形态 |
| `renforge-mcp` | **MIT**（Copyright (c) 2026 RenForge contributors） | 仅调研其 MCP 形态，**未包含其任何代码** |

> `renforge-mcp` 的上游：<https://github.com/alex-jordan547/renforge-mcp>（以该仓 LICENSE 为准）。
> 上述前三个项目没有许可证文本，因此本项目**没有复制它们的代码或文档原文**，相关能力均为独立实现；
> 按版权法「无许可证＝保留所有权利」处理。`renforge-mcp` 虽是 MIT，本项目也没有引用其代码。

---

## 三、调研参考（只读过公开资料，未使用代码）

| 项目 | 许可 | 用来干什么 |
|---|---|---|
| [Vibe Kanban](https://github.com/BloopAI/vibe-kanban) | Apache-2.0（仓库 LICENSE 未填版权人） | 开源 agent 看板横评的对照对象 |
| [OpenHands](https://github.com/OpenHands/OpenHands) | MIT（Copyright © 2025 OpenHands contributors） | 同上 |
| [Symphony](https://github.com/openai/symphony) | Apache-2.0（含 NOTICE：Copyright 2025 OpenAI） | 规格／失效模式的架构参考 |
| [MAST — Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) | 仓库**无许可证**；论文 CC BY-NC-ND 4.0 | 只把它的失效分类当**概念**引用；⛔ 未复制其代码、数据、图表 |

调研结论原档在 `docs/research/20261019-agent-board-survey/`。按上面的许可，这些项目**都没有**对
「借鉴思路」施加署名义务；这一节是出于学术惯例与可追溯性而写，不代表存在授权关系。

---

## 四、运行时与工具链

- **Python 3.9+**（仅标准库）—— 无 pip 依赖，`git clone` 即可跑。
- **.NET Framework 4.x 自带的 `csc.exe`** —— 桌面壳与托盘用它编译，不需要 MSBuild / NuGet 还原。
- **WebView2 Evergreen Runtime** —— Win11 自带，Win10 由 Windows Update 安装。

---

## 五、关于作者

本项目的代码由 **AxelBeary** 与其使用的 **AI 编程代理**（opencode 等 CLI agent）共同编写，
按 [LICENSE](LICENSE)（MIT）发布。提交历史里两种作者标识都保留着，没有改写。

发现本页有遗漏或署名不当，请开 issue —— 这类问题通常改一行就能修好。
