# P1 · 开源 agent 看板／编排产品横评

> 调研席 A ｜ 访问日期：2026-10-19 ｜ 仅查公开仓库页面与 README、许可文件；未安装、未 clone、未运行任何候选。

## 能力边界与证据降级档位

本轮网页检索服务返回空结果；改为直接打开 GitHub 官方仓库、README、许可证、项目规格与提交记录。下表的产品定位、架构和协作能力来自这些页面的可回读文字；GitHub Star 数为页面访问时显示值，只代表当时快照。只有确实看见页面显示具体提交日期/版本时才记录，否则写「未见」。未在页面找到的 claim/lease、心跳、审批、验收和留痕能力一律写「未见文档」，不将「没有看到」说成「产品绝对没有」。此为公开资料桌面调研，不等于安装实测、代码审计或许可证法律意见。

## 三类候选横评（17 个项目）

| 类别／项目（链接与访问日） | 许可证 | 技术形态／部署 | 派活、认领、审批与完成证据 | agent 接入 | 活跃度（页面所见） | 判定；最有价值点／最致命缺点 |
|---|---|---|---|---|---|---|
| **1 原生 agent 看板/工作站** · [Vibe Kanban](https://github.com/BloopAI/vibe-kanban)（2026-10-19） | Apache-2.0 | 本地 Web 看板＋服务端；README 给出 `npx vibe-kanban` 启动；仓库有 Rust crates 与 JS/TS packages。 | 人在看板建/分配 issue；agent 在独立 workspace/branch 工作；可看 diff、评论、预览、PR。页面未见面向跨用户的租约/心跳或强制验收门禁。 | README 称支持 Claude Code、Codex、Gemini CLI、Copilot、Amp、Cursor、OpenCode 等多种 coding agent。 | 仓库页 28.4k stars；提交记录页最新可见 2026-09-19（commit），版本 bump 到 0.1.45 同日。README 同时有「sunsetting」警告，且记录有后续提交；维护/产品状态存在页面内冲突，勿据此断言已停更或仍受支持。 | **部分可用**；现成 UI、隔离工作区和 diff 审查很接近；但主要解决 coding agent 工作区，不是全机任意 agent 的治理看板，且 sunsetting 信号提高采用风险。 |
| **1 原生 agent 看板/工作站** · [OpenAI Symphony](https://github.com/openai/symphony)（2026-10-19） | Apache-2.0 | 语言无关服务规格；仓库另有 Elixir 参考实现。长驻轮询 issue tracker、为每个 issue 建独立 workspace 并运行 agent；需配置 tracker 与运行环境。 | 规格定义唯一调度状态、claimed 集合、并发上限、重试/回收、状态对账和结构化日志；允许按配置交给人工 Review，但明确不提供丰富 Web UI/多租户控制台，验收由 workflow/agent/human policy 决定。 | 规范化 tracker adapter；当前参考执行通道以 Codex app-server 为中心，不是任意 CLI 的现成通用接入。 | 仓库页 27.7k stars（2026-10-19）；提交日期/发行版页面本轮未见可读具体值。 | **部分可用**；最值得借鉴的是调度状态机、claim 防重复、隔离、重试与对账规格；不是可直接安装的完整看板产品。 |
| **1 原生 agent 看板/工作站** · [KittyClaw](https://github.com/Ekioo/KittyClaw)（2026-10-19） | **AGPL-3.0-or-later**；NOTICE 另列额外署名/来源要求；README 说 v0.11 及以前为 MIT。 | .NET 10 / Blazor Server、SQLite、EF Core、REST/OpenAPI；本机启动 `run.bat`/`run.sh`，常驻本地 Web 服务。 | 人建票并决定最终发布；可自定义列/流程、processor、排队次序、持久重试、路由；run 快照记录事件/状态/退出码，流式输出并有人工验证。README 未承诺互斥租约/心跳。 | Claude Code、Codex、Grok Build、Mistral Vibe、Ollama；另提供 REST API 与可选 MCP board tools。不是任意 CLI 自动适配。 | 仓库页 27 stars（2026-10-19）；页面有 907 commits，但本轮未见具体最新提交日期/发行版。 | **部分可用**；17 项中最贴近「看板＋agent 任务执行＋可读运行证据＋人类发布决定」；但新项目、用户/agent 接入范围较窄，且 AGPL 对改造/提供网络服务有明显义务，需先做许可评估。 |
| **1 原生 agent 看板/工作站** · [OpenHands Agent Canvas](https://github.com/OpenHands/OpenHands)（2026-10-19） | MIT（仓库许可）；部署/产品细节见 README。 | OpenHands 仓库内的 Canvas 产品：Web UI＋Agent Server/Automation Server，可本机、Docker、VM 或远端后端运行；需 Node.js/`uv`，Docker 沙箱为可选。 | 可启动/监视 agent 会话、排程/事件触发 automation、将 GitHub issue 拆成任务；多后端对话执行。页面未见共享 Kanban 卡片的互斥 claim/租约；完成状态不等同于经独立验证。 | OpenHands 原生及 Claude Code、Codex、Gemini、Pi、OpenCode 和 ACP-compatible agents。 | OpenHands 仓库页 91.2k stars（2026-10-19；这是整个仓库数字，非 Canvas 单独数据）；具体最新提交日期未记。 | **部分可用**；接入面与本地/远端执行后端值得借鉴；主要是会话控制台和自动化，不是以卡片租约、证据链、审批列为核心的任务板。 |
| **2 通用开源看板** · [Plane](https://github.com/makeplane/plane)（2026-10-19） | **AGPL-3.0** | Django 后端＋React/React Router 前端；可 Docker 或 Kubernetes 自托管，依赖数据库/服务，部署明显重于单机小工具。 | 工作项、循环、模块、视图、分析；可由人分配任务。README 未证明有 agent lease/heartbeat、独立验证或不可越过的人类审批位。 | 普通项目管理平台；当前 README 未见 agent 原生调度/通用 agent adapter。 | 仓库页 61.1k stars（2026-10-19）；README 说明持续演进，具体最新提交日期本轮未记。 | **部分可用**；界面、任务/项目数据模型成熟；作为单机多 agent 工具底座会引入较大的服务栈，且 AGPL 是实际改造约束。 |
| **2 通用开源看板** · [Focalboard（Mattermost Community）](https://github.com/mattermost-community/focalboard)（2026-10-19） | 源码受 **AGPL-3.0** 管辖并含例外；指定 Admin/config 子目录为 Apache-2.0；编译版许可另有说明。不可简单写成 MIT。 | Go 服务端、Web 前端；有单用户桌面版和可自托管多用户 Server。 | 普通看板与工作管理；页面没有 agent 认领/租约、心跳和验收规则。 | 未见原生 agent adapter；需自行接 API/改造。 | 26.5k stars；仓库页面明确写「currently not maintained」（2026-10-19）。 | **部分可用**；可借看板结构和自托管形态；维护已停止且源码 AGPL，做新底座风险高。 |
| **2 通用开源看板** · [Vikunja](https://github.com/go-vikunja/vikunja)（2026-10-19） | **AGPL-3.0-or-later**（README）；`desktop/` 单独 GPL-3.0-or-later。 | Go 后端＋Vue 前端；自托管 Web/API，另有 desktop 目录；有 Docker 安装路径。 | 任务管理、任务列表和 API；README 未见 agent claim/lease、心跳或人类审批/证据门。 | 可由 API 做外接；未见内建 agent orchestration。 | 5.8k stars（2026-10-19）；README 展示安装徽章 v2.7.0，但它是页面可见版本徽章，不作「最新正式版」推断。 | **部分可用**；自托管任务 API 可供薄适配；不含 agent 生命周期与证据验收，且 AGPL。 |
| **2 通用开源看板** · [Huly Platform（旧仓库）](https://github.com/hcengineering/platform)（2026-10-19） | EPL-2.0（仓库页）。 | TypeScript/Node 业务平台；自托管需 Docker、Docker Compose、Rush 等，文档列出 MongoDB、Elasticsearch、MinIO 等服务，部署重。 | 含 project management/issue tracker 等应用；README 未见 agent claim、lease、心跳或证据门。 | 未见原生 agent adapter；可探索 API，但本轮未核实适配路径。 | 27.9k stars；仓库 README 明确「frozen / no longer actively maintained」，指向 `Platform-Collective/platform`；并称 Hosted Huly 已关闭。 | **不可用**（不宜基于此旧仓库开新改造）；功能范围宽但当前源码入口和托管服务均已迁移/关闭，须另行评估新仓库。 |
| **2 通用开源看板** · [WeKan](https://github.com/wekan/wekan)（2026-10-19） | MIT | Meteor/JavaScript Web 应用；Docker、Kubernetes、桌面/单机等部署方式丰富；自托管需要常驻服务/数据库。 | 普通协作 Kanban，API、webhook、自动化规则等较多；未见针对 agent 的唯一认领租约/心跳/独立验收。 | 可用 REST/API 或 webhook 外接；没有 README 证据表明内建通用 agent runner。 | 21.1k stars；README 描述持续维护并显示大量变更，但本轮未取最新具体 commit 日期。 | **部分可用**；成熟可自托管、API/导入导出丰富；改成 agent 看板仍要补身份、租约、执行证据和人类闸门。 |
| **2 通用开源看板** · [Taiga（新一代仓库）](https://github.com/kaleidos-ventures/taiga)（2026-10-19） | MPL-2.0 | 新一代 Taiga 仓库，页面称「next iteration」；Python 服务＋Angular/TypeScript 前端，项目仍在重构/演进。 | 敏捷项目管理/看板方向；本仓 README 内容少，agent claim/lease、心跳、审批及验收均未见证据。 | 未见 agent 接入。 | 575 stars（2026-10-19）；repo 有 2,124 commits，未在本轮看到具体最近提交日期。 | **部分可用**；许可较宽松且目标是项目协作；但此仓库是下一代迭代，不应直接当作成熟 Taiga 看板或已有稳定底座。 |
| **2 通用开源看板** · [OpenProject](https://github.com/opf/openproject)（2026-10-19） | GPL-3.0 | Ruby Web 平台；可自托管/云部署；覆盖项目组合、Agile board、Gantt、协作等，属完整企业级服务。 | Work package、角色/工作流、项目跟踪；页面未见 agent 租约/心跳/基于独立验证的 Done 门禁。 | README 列 GitHub/GitLab/Nextcloud 等集成，不等于 agent 执行适配。 | 16.5k stars（2026-10-19）；确切最新 commit 日期本轮未记。 | **部分可用**；团队权限和成熟项目流程可作参考；对本项目目标太重，GPL-3.0 且要自行补 agent 执行/证据治理。 |
| **3 agent 队列/共享黑板范式** · [Claude Task Master / Taskmaster](https://github.com/eyaltoledano/claude-task-master)（2026-10-19） | MIT + Commons Clause（仓库 README 明确限制将其本身作为托管服务/竞争产品销售；不是纯 MIT）。 | TypeScript/Node CLI＋MCP server；在 IDE/项目中本地读写任务；依赖用户配置模型/API 或本地 CLI。 | PRD 拆分、依赖、next task、状态更新；可通过 MCP 工具操作任务。README 有 Team Collaboration 文档入口，但本轮未核实共享多人租约；未见 heartbeat/独立验收门。 | README 列 Cursor、Windsurf、Roo、VS Code、Claude Code、Codex CLI 等集成；任务工具经 MCP/CLI。 | 28.2k stars（2026-10-19）；仓库有 1,216 commits，具体最新提交日期未见。 | **部分可用**；任务拆解、依赖、下一任务选择与 MCP 工具形状值得借鉴；它是项目内任务助手，不是跨主机/跨人 agent 共享任务看板。 |
| **3 agent 队列/共享黑板范式** · [OpenHands SDK / Agent Server](https://github.com/OpenHands/OpenHands)（2026-10-19） | MIT | OpenHands Agent Server 是运行多个 agent/conversations 的 REST 服务，Canvas 可连接本机、Docker、VM 等后端；需常驻服务。此条与上表 Agent Canvas 同仓，按「运行底座」而非独立仓库计能力。 | API/automation 负责派发会话和事件驱动任务；README 未证任务卡之间的互斥认领/租约，也没有以验收证据决定 Done 的标准流程。 | OpenHands 原生 agent，外接 ACP agents；并提到多种第三方 coding CLI。 | 同仓快照 91.2k stars（2026-10-19，非独立 SDK 统计）。 | **部分可用**；可参考 agent server、后端抽象、自动化与会话持久化；不能把「多会话可运行」误当「共享任务队列已有原子 claim」。 |
| **3 agent 队列/共享黑板范式** · [Microsoft AutoGen](https://github.com/microsoft/autogen)（2026-10-19） | 代码 MIT；文档 CC-BY-4.0。 | Python/.NET 多 agent 框架；AutoGen Studio 是原型 GUI，可本机启动。 | 多 agent 对话/消息传递及人机交互；Studio README 明确非生产级产品。未见 shared task claim/lease/heartbeat/交付证据板。 | 模型客户端与扩展层支持多种 provider/tool；这是构建 agent 的框架，不是任意既有 CLI 的运行面板。 | 61.5k stars（2026-10-19）；页面明确项目 Archived / 不再维护，并指向 Microsoft Agent Framework。 | **不可用**（不选其作为新底座）；历史多 agent/Studio 原型可参考，维护状态与其自身警告都不适合直接承接生产看板。 |
| **3 agent 队列/共享黑板范式** · [AG2](https://github.com/ag2ai/ag2)（2026-10-19） | Apache-2.0 | Python agent framework；以 library/API 方式运行，非看板产品。 | Agent Network 的 Hub 管理 registry、write-ahead log、audit trail；支持 channel/workflow、HITL；这些是协作消息/执行轨迹，不是用户故事级任务板，也未证明卡片 lease。 | 多模型/provider/tool；支持 Hub/typed channels 与人工输入 hook。 | 5.0k stars（2026-10-19）；页面列出维护团队/文档；本轮未核实具体 release/最新 commit 日期。 | **部分可用**；WAL/audit trail 和集中 Hub 是值得借鉴的共享黑板模式；其调度对象是 agent 消息/工作流，不是人和所有外部 agent 共用的任务卡。 |
| **3 agent 队列/共享黑板范式** · [MetaGPT](https://github.com/FoundationAgents/MetaGPT)（2026-10-19） | MIT | Python framework/CLI；可 pip/Docker；运行多个角色 agent 并生成项目制品。 | 以 PM、架构师、工程师等角色/SOP 协作产出；不是通用任务板。README 未见持久化原子认领、心跳回收或独立验收机制。 | 基于 LLM/provider 配置及自定义 agent/工具；主要在 MetaGPT 框架内运行。 | 70.9k stars（2026-10-19）；具体最新提交/发行版日期本轮未记。 | **部分可用**；角色分工、标准步骤、产物流转可借鉴；架构是 agent team 执行流程，不能直接管理不同引擎/人工的并行委派。 |
| **3 agent 队列/共享黑板范式** · [ChatDev 2.0 / DevAll](https://github.com/OpenBMB/ChatDev)（2026-10-19） | Apache-2.0 | FastAPI/Python 后端＋Vue 3 前端，Web Console；README 支持 Docker Compose 和本地运行，需数据库、模型配置及服务。 | 可视化配置 agent/workflow/task，运行时看日志、检查中间产物、接受 human-in-the-loop feedback；未见跨工作项唯一认领 lease/heartbeat 或独立 reviewer 对 Done 的强制判据。 | workflow 内定义/配置 agent 与 provider；可被 OpenClaw 调用；并非任意 coding CLI 的统一适配板。 | 34.5k stars（2026-10-19）；README 标注 ChatDev 2.0 于 2026-01-07 发布；本轮未取最新 commit 日期。 | **部分可用**；可参考工作流画布、运行日志/中间产物、人类反馈；重心是搭建并执行 agent workflow，不是跨项目任务调度及认领治理。 |

> 活跃度口径：各仓库页显示的 stars 均于 2026-10-19 浏览时记录；它是瞬时近似值。只把确实在来源页面读到的具体版本/日期写出；未见到的不补记。页面上的「commit 数」不等于最近提交日期。

## 人话结论（≤600 字）

现成产品已把几块拼图做出来：Vibe Kanban、KittyClaw、OpenHands Canvas 有 agent 工作区/控制 UI；Symphony 规格写清轮询、claim、并发、重试和对账；AG2 有共享 Hub 与审计日志。Plane、WeKan、OpenProject 是成熟的人类看板，但 API 不等于 agent 租约或交付证据。

仍缺跨引擎统一认领、心跳回收、独立验收与不可被 agent 越过的人类审批，也缺轻量本机看板。因此并非从零造轮子，却没有完整现成答案。机会是组合 Symphony 的调度、KittyClaw 的证据呈现和通用看板的易读 UI，做薄而可插拔的治理层。复用前先审许可：KittyClaw/Plane/Focalboard 涉 AGPL，另有 GPL 与 Commons Clause 项目。

## 未证清单

- Cline Kanban：GitHub 精确词组仓库搜索返回 27 个结果，但前列是多份互不相干仓库；未找到能确认是派工所述「CLI 无关多 agent 编排应用」的唯一官方项目，因此不纳入计数、不按记忆补写。可替代取数路径：提供产品官网/仓库 owner 或确切 URL 后，再逐项查 README、LICENSE、commit。
- KittyClaw：虽公开页和 README 信息充分，本轮没有实际部署；「27 stars」和 README 所述能力并不证明真实使用稳定性、并发安全性或许可条款在具体改造方案中的适用性。
- 对除 Vibe Kanban 外大多数候选，未核到可靠的最新 release/最近 commit 的具体日期；对应活跃度栏明确不记未看见的日期。各项目的互斥 claim/租约、超时回收和外部验证只在来源有明确描述时才写已具备。
- 不包含真实运行、接口探测、代码级锁语义核查、部署难度实测、法律意见；仅根据公开页面做第一轮筛查。

## 可回读锚点汇总

以下链接均于 2026-10-19 打开；仓库首页包含 README、许可证链接及 Star 快照。凡特别说明的规格/提交/许可证另给直接锚点。

### 类 1 · agent 原生板/工作站

1. [Vibe Kanban 仓库/README/Apache-2.0](https://github.com/BloopAI/vibe-kanban)；[提交历史](https://github.com/BloopAI/vibe-kanban/commits/main/)（可见 2026-09-19 commit、0.1.45 bump；同页 README 标示 sunsetting）。
2. [OpenAI Symphony 仓库/README/Apache-2.0](https://github.com/openai/symphony)；[SPEC.md](https://github.com/openai/symphony/blob/main/SPEC.md)（语言无关服务规格；issue tracker、claimed、状态对账、工作区、retry；不以 rich UI 为目标）。
3. [KittyClaw 仓库/README/AGPL 页面](https://github.com/Ekioo/KittyClaw)；[README 直接页](https://github.com/Ekioo/KittyClaw/blob/main/README.md)；[LICENSE](https://github.com/Ekioo/KittyClaw/blob/main/LICENSE)；[NOTICE](https://github.com/Ekioo/KittyClaw/blob/main/NOTICE.md)。
4. [OpenHands 仓库/README/MIT](https://github.com/OpenHands/OpenHands)（README 同时说明 Agent Canvas、Agent Server、Automation Server、ACP）。

### 类 2 · 通用看板

5. [Plane 仓库/README/AGPL-3.0](https://github.com/makeplane/plane)。
6. [Focalboard 仓库/README](https://github.com/mattermost-community/focalboard)；[LICENSE.txt 原文](https://raw.githubusercontent.com/mattermost-community/focalboard/main/LICENSE.txt)（说明源代码 GNU AGPL v3、指定目录 Apache-2.0、编译版许可；README 说明 unmaintained）。
7. [Vikunja 仓库/README/AGPL-3.0-or-later](https://github.com/go-vikunja/vikunja)。
8. [Huly Platform 仓库/README/EPL-2.0](https://github.com/hcengineering/platform)（README 明示冻结、迁移指向 Platform-Collective、托管服务关闭）。
9. [WeKan 仓库/README/MIT](https://github.com/wekan/wekan)。
10. [Taiga 下一代仓库/README/MPL-2.0](https://github.com/kaleidos-ventures/taiga)。
11. [OpenProject 仓库/README/GPL-3.0](https://github.com/opf/openproject)。

### 类 3 · agent 队列/共享黑板

12. [Taskmaster 仓库/README/license（MIT + Commons Clause）](https://github.com/eyaltoledano/claude-task-master)。
13. [OpenHands SDK/Agent Server（与第 4 项同仓）](https://github.com/OpenHands/OpenHands)。
14. [Microsoft AutoGen 仓库/README（代码 MIT、文档 CC-BY-4.0；已归档）](https://github.com/microsoft/autogen)。
15. [AG2 仓库/README/Apache-2.0](https://github.com/ag2ai/ag2)（Hub/WAL/audit trail/HITL 说明位于 README 的 Multi-Agent Orchestration 与 Human in the Loop 小节）。
16. [MetaGPT 仓库/README/MIT](https://github.com/FoundationAgents/MetaGPT)。
17. [ChatDev 仓库/README/Apache-2.0](https://github.com/OpenBMB/ChatDev)（README 可见 2026-01-07 ChatDev 2.0 发布声明、Web Console 与 Human-in-the-loop 能力）。

另作发现索引（不是候选产品实证）：[awesome-agent-orchestrators](https://github.com/andyrewlee/awesome-agent-orchestrators)（2026-10-19 浏览；页面将候选分为并行 coding agents、swarms、autonomous task runners 和基础设施，适合扩展搜索，清单描述不代替逐项回源）。

**反空跑计数：核过 17 个候选项目，采信 17 个作为可比较样本；其中 15 个判为「部分可用」、2 个判为「不可用」，0 个判为「可用」。** 判定是针对本项目所述「本机所有 agent 与人共用任务看板」这一目标，不代表这些产品在其各自目标场景中无用。
