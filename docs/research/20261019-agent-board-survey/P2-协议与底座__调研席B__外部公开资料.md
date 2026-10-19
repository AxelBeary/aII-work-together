# P2 调研席 B｜协议与底座（外部公开资料）

> 口径：公开网页定向检索；访问日期统一为 **2026-10-19**。下文「公开事实」来自所链页面；「本席判断」是针对本机单机共享任务看板的适配意见，不是来源原话。成熟度只写来源能支持的程度，不把宣传性采用数字当独立验证。

## ① 能力边界与证据降级档位

- 本席可联网检索并直接打开多个官方/项目文档、规范仓库及论文页面；因此本报告不是 `BLOCKED`。
- 本轮核对 **16 条候选（条目口径）**，每条均有可回读 URL 和访问日期；覆盖派工要求的 6 个方向。非零反空跑计数：**16 条核对、16 条有链接、16 条有明确层级**。
- 档位：协议/产品能力以维护方文档或规范仓库为主；失效研究以论文元数据/摘要为锚。此为桌面调研，不代表对实现做了安装、互操作测试、负载测试或本机接入验证。产品「支持」列表、采用数均只作维护方/项目方公开陈述。
- 范围限于公开事实；未访问本机外部技能文件、未验证各 CLI 在本机当前安装版本的实际行为；也未评估许可证、长期维护风险、供应商 SLA 或完整安全模型。

## ② 六方向逐条清单（16 条）

成熟度：维护方/规范/多实现依据；接入代价为本席估算。判定词只用 `可用`／`部分可用`／`不可用`／`未证`。

### A. Agent 间协议、发现与交互

| # | 候选、公开事实与锚点（访问日期） | 成熟度 | 解决哪一层 | 接入代价（人话） | 契合判定与本席判断 |
|---|---|---|---|---|---|
| 1 | **A2A**。公开定位为异构 agent 间协作协议；有 AgentCard、任务生命周期、消息/产物；由 Google 发起并捐给 Linux Foundation，现归 Agentic AI Foundation；公开 SDK 覆盖多语言。 [协议首页](https://a2a-protocol.org/latest/)；[Linux Foundation 移交公告](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents)（访问：2026-10-19） | 有公开规范、治理与多语言 SDK；LF 页面记录 2025-06 项目启动，协议首页当前标明加入 AAIF。官方支持不等于每个 CLI 均兼容。 | **任务层**：远端 agent 间任务委派、状态更新和产物交换。 | 若目标 agent 原生支持，接客户端/服务端 SDK；否则还要给本地 CLI 包 HTTP 服务、身份/授权、任务映射和运维，成本高。 | **部分可用**。可作未来跨机器/跨组织 agent 的接入适配器；不是本机看板的核心任务库、租约或人的审批状态机。**重议触发（判断）**：需要接入至少 2 个异厂商远端 agent，且它们之间需独立发现/委派/回传任务时，做窄范围互通试点；仅多 CLI 同机不够。 |
| 2 | **ACP（Agent Client Protocol）**。规范将自己定位为编辑器/IDE 与编码 agent 的通信标准；本地子进程用 JSON-RPC/stdio，远端 HTTP/WebSocket 支持仍在推进中；提供 diff 等编码交互类型。 [ACP Introduction](https://agentclientprotocol.com/get-started/introduction)；[Zed ACP](https://zed.dev/acp)（访问：2026-10-19） | 有公开协议文档和 Zed 发起的生态；官方介绍明确远端完整支持仍是进行中。 | **工具层**（agent 接入/交互 UI）：把编码 agent 接到编辑器，不是 agent-to-agent 任务总线。 | 对协议实现双方需写客户端/agent adapter；可复用现成 ACP agent/编辑器时中等，否则高。 | **部分可用**。有助于未来接入 ACP 原生 agent，但看板的任务状态、租约、凭据隔离仍须自有。当前不应因为有 ACP 就把所有 CLI 改造成 ACP。 |
| 3 | **AG-UI**。开放、事件驱动、双向协议，连接用户界面与 agent 后端；定义事件流、共享状态、人机中断等 UI 交互；公开列有多种框架集成。 [AG-UI Overview](https://docs.ag-ui.com/introduction)（访问：2026-10-19） | 可读公开协议/概念文档；项目维护方列出多框架集成。属于正在发展的生态层，不能据此推定本机 CLI 全支持。 | **工具层**（agent↔用户界面事件接口；不是协作任务层）。 | 若要统一实时事件流/审批卡 UI，需接入其事件模型并为 agent/backend 做 adapter；单纯本地看板做轮询/服务端推送更省。 | **部分可用**。将来若看板要嵌入多种 agent 前端或统一交互流可评估；当前板卡显示只需任务自身事件，不必让业务状态迁就 AG-UI。 |

### B. 工具与上下文接入

| # | 候选、公开事实与锚点（访问日期） | 成熟度 | 解决哪一层 | 接入代价（人话） | 契合判定与本席判断 |
|---|---|---|---|---|---|
| 4 | **MCP（Model Context Protocol）**。官方文档将其定义为 AI 应用连接外部系统的开放标准，面向工具、数据源和工作流；官方列出 Claude、ChatGPT、VS Code、Cursor 等客户端/服务端生态。 [MCP What is MCP](https://modelcontextprotocol.io/docs/)（访问：2026-10-19） | 有公开规范与多家客户端支持；具体工具生态质量、权限粒度和版本兼容仍需逐项核。 | **工具层**：看板可通过 MCP 暴露「列卡/取状态/写进度」等工具给 agent；它不负责 agent 进程启动，也不替代任务状态机。 | 暴露只读工具较低；可写工具还需鉴权、参数校验、幂等、审计、人工审批以及各客户端配置，约中等。 | **部分可用**。把 MCP 当可选插件/工具面，不当看板↔agent 的唯一接口或全链路标准。**重议触发（判断）**：至少 3 种本机 agent 客户端要复用同一套看板工具，且各写一套适配的维护成本已大于一个 MCP server 的维护成本，再做小试点；写操作仍以看板权限规则为准。 |

### C. 本机 CLI 启动与项目交接约定

| # | 候选、公开事实与锚点（访问日期） | 成熟度 | 解决哪一层 | 接入代价（人话） | 契合判定与本席判断 |
|---|---|---|---|---|---|
| 5 | **AGENTS.md 约定**。项目站将其定义为面向 coding agents 的开放 Markdown 指令文件，无必需字段；网站自报被 60k+ 开源项目采用，并展示多家工具支持。格式本身不是任务 API，也没有强制 schema。 [AGENTS.md](https://agents.md/)；[规范仓库](https://github.com/agentsmd/agents.md)（访问：2026-10-19） | 开放约定、广泛但非强制；站点所报采用量是项目方口径，未独立抽样。各 CLI 对 CLAUDE.md、`.claude`、`.agents` 等另有厂商自定义。 | **工具层**（向 agent 注入项目说明/约束）。 | 看板只需把卡片任务文本、项目路径、AGENTS 文件路径交给 CLI；读文件可由 agent 自身完成，成本低。 | **可用**。作为项目级指令载体和派工上下文入口；不可拿它表达租约、状态真相或任务交接协议。`.agents` 目录/各家 hooks、subagent 定义没有被这份 Markdown 约定统一标准化，须各自适配。 |
| 6 | **OpenAI Codex CLI `codex exec`**。官方无交互模式支持脚本/CI；默认只读 sandbox，可指定 workspace-write；`--json` 输出事件流、可 resume。 [Codex Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)（访问：2026-10-19）<br>⚠️ **发牌席更正 2026-10-19**：原写 `/docs/codex/non-interactive-mode` 实测 404，已改为正确路径；页面正文与本节结论一致（见 `99_发牌席抽验记录.md` §三）。 | 厂商官方文档、正式 CLI 能力；属于单一实现，不是跨厂商标准。 | **工具层**：把卡片转成一个子进程调用并收集 stdout/退出结果。 | 低至中：参数组装、超时/取消、工作目录、权限策略、stdout/stderr 与退出码解析、sessionID/日志归档。 | **可用**，适合作为逐家 CLI adapter 的一种。**本席判断**：保留统一内部接口 `启动/轮询/停止/收件`，CLI 各自实现；不要假设命令参数、认证、权限模型相同。 |
| 7 | **OpenCode CLI `opencode run`**。官方 CLI 文档标注可脚本/自动化非交互运行；可输出 JSON 事件、指定 agent/session/目录；另有 `serve` 和 ACP server 命令。 [OpenCode CLI](https://opencode.ai/docs/cli)（访问：2026-10-19；页面显示更新 2026-10-17） | 官方 CLI 文档与产品实现；运行参数随版本变化，需锁定/探测本机版本。 | **工具层**：本地子进程启动；`serve` 还可提供 HTTP 控制接口。 | 低至中；同上，但需分清 `run`、`serve` 与 `acp` 的会话/权限语义。 | **可用**，作为一条引擎 adapter 路径；不能直接当跨引擎的看板协议。 |
| 8 | **Claude Code CLI `claude -p`**。官方 CLI reference 说明 `-p/--print` 非交互输出；支持 text/json/stream-json、session resume、限制 turns/budget、subagent 等选项。 [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)（访问：2026-10-19） | 官方 CLI 文档、具备多种脚本能力；特定 flags 与行为版本相关。 | **工具层**：以子进程方式执行 agent 并采集结果/事件。 | 低至中：适配 CLI 调用/流事件和权限模式；需明确定义 headless 授权，防止将交互授权误认为自动许可。 | **可用**，作为独立 adapter。三种 CLI 都已有 headless 形态，意味着「启动 agent 进程」不需自造 agent runtime；但统一调度和可信验收仍要由看板实现。 |

### D. 任务持久化、恢复与多写同步

| # | 候选、公开事实与锚点（访问日期） | 成熟度 | 解决哪一层 | 接入代价（人话） | 契合判定与本席判断 |
|---|---|---|---|---|---|
| 9 | **Temporal Durable Execution**。官方定义工作流在崩溃/服务故障时保持状态与进度；通过事件历史重放恢复，提供任务队列、超时、重试、信号/查询等。 [Temporal glossary](https://docs.temporal.io/glossary)；[Workflow execution](https://docs.temporal.io/workflow-execution)（访问：2026-10-19） | 成熟的专用 workflow 服务/SDK 生态，公开产品文档与多语言 SDK；采用它意味着引入服务端、worker、持久层和运维。 | **状态层**（耐久工作流/执行进度）；非通用看板 UI，也不是 agent 协议。 | 高：要建/托管 Temporal service、worker、工作流代码、版本兼容与运维；还要定义卡片↔workflow ID 映射。 | **部分可用**。当任务跨进程/数小时以上、故障后必须可靠续跑时可作执行底座；不适合作为当前本机 MVP 的直接替换。**重议触发（判断）**：连续两个迭代出现可复现的进程崩溃丢失进度，且进度文件/数据库加恢复逻辑成本高于专用 runtime；或需多机持久在线任务与明确恢复 SLA。 |
| 10 | **Restate Durable Execution**。官方文档说明 workflow 步骤写入服务端日志，崩溃后重放恢复；支持长期等待、durable promise、外部事件、状态查询与人审暂停/恢复。 [Restate Workflows](https://docs.restate.dev/tour/workflows)（访问：2026-10-19） | 有 SDK/服务端和多语言示例；官方提供可运行用法。依赖引入与生产成熟度仍须项目自己评估。 | **状态层**：持久执行、等待外部信号、重试/恢复。 | 中高：加服务端和 SDK、部署/版本与 workflow semantics；通常比单机文件看板重。 | **部分可用**。适合异步、人审和长流程作为底座候选，不代替看板本体。重议条件同 Temporal：明确丢进度风险/续跑成本已超过新增服务的维护成本。 |
| 11 | **DBOS Durable Execution**。官方说明开源库将 workflow/step checkpoint 写入 PostgreSQL；失败可从最后已完成步骤恢复；可多进程共享数据库队列，并可配 Conductor 控制平面。 [DBOS Architecture](https://docs.dbos.dev/architecture)（访问：2026-10-19） | 官方开源库/文档，多语言入口；持久化依赖 Postgres，分布式生产管理能力与开源库边界须留意。 | **状态层**：数据库 checkpoint、队列与工作流恢复。 | 中：需把运行逻辑改成 deterministic workflow/step，加 Postgres；如需生产高可用/运维面再叠控制面。 | **部分可用**。若未来本体已有 Postgres，且任务需要 checkpoint，可能比单独引入完整 orchestration service 轻；当前无此需要。 |
| 12 | **Yjs CRDT**。官方文档说明共享类型支持并发修改/自动合并，网络层可替换，状态可经 provider 持久化；Yjs 本身不规定应用权限和工作流。 [Yjs Introduction](https://docs.yjs.dev/)（访问：2026-10-19） | 活跃公开库及编辑器/网络/持久化生态；其组件模块化，不等于完整数据库或任务系统。 | **状态层**：多副本共享数据与并发合并。 | 中高：除 CRDT 数据模型还要选 provider、持久化、身份/权限、删除/保留策略，并对任务状态做语义约束。 | **不可用**（作为本机任务状态真相源）；**部分可用**（作为多人实时编辑备注/文档）。CRDT 的自动合并不能单独保证「单卡只有一位执行者」「只有人能推进审批」等业务不变量。**重议 worktree/CRDT（判断）**：至少 2 台机器离线写同一共享资料并需要自动合并，才试点 Yjs 文档层；卡状态仍走有权限的服务端事务。 |
| 13 | **Automerge CRDT**。官方文档描述 JSON-like 文档、变更历史、冲突合并；`automerge-repo` 提供网络/存储 plumbing，sync protocol 与传输解耦。 [Automerge Concepts](https://automerge.org/docs/reference/concepts)（访问：2026-10-19） | 开源库/文档/多语言实现；CRDT/sync 是库能力，不是看板任务生命周期规范。 | **状态层**：本地优先文档同步和并发变更合并。 | 中高：引入 CRDT 文档/仓库、存储及传输，再写业务规则与访问控制。 | **不可用**（作任务状态机的权威源）；多设备离线共同编辑非关键说明时才可考虑，约束与 Yjs 同。 |

### E. 多 agent 失败模式与黑板架构

| # | 候选、公开事实与锚点（访问日期） | 成熟度 | 解决哪一层 | 接入代价（人话） | 契合判定与本席判断 |
|---|---|---|---|---|---|
| 14 | **经典 Blackboard Architecture**。Hayes-Roth 的经典论文以共享黑板数据库承载数据/假设（部分解），多知识源在其上协作；该架构本身不是现代 agent 协议或现成产品。 [Hayes-Roth, “A Blackboard Architecture for Control” (1985)](https://www.sciencedirect.com/science/article/pii/0004370285900633)；[斯坦福扫描材料](https://stacks.stanford.edu/file/druid:mq853nj9727/mq853nj9727.pdf)（访问：2026-10-19） | 经典研究架构，有后续应用/论文；不是可直接接入的标准实现。 | **状态层**（共享问题/工作状态）；协作控制位于任务层。 | 概念借鉴成本低；照搬通用黑板调度器、知识源触发器则成本高，并不能自动提供租约/审计/验收。 | **部分可用**。借鉴「共享可读产物、显式部分结果、可追溯写入」；不要借用无仲裁共享可写模式。一个文件一个写者、状态变更挂证据是更适配本项目的硬约束。 |
| 15 | **MAST：Why Do Multi-Agent LLM Systems Fail?** 论文报告对 150 条执行轨迹做人工分析，建立 14 类失效分类，分系统设计、agent 间错位、任务验证三类；数据集超过 1,600 条、来自 7 个框架；arXiv 当前页面版本 v3，2025-10-26 更新。 [arXiv paper](https://arxiv.org/abs/2503.13657)（访问：2026-10-19） | 研究论文/公开数据，非规范；覆盖框架和任务并不等于对所有 agent board 的失效率估计。 | **任务层**（识别协调、规格、终止和验证失败）；也指导状态层要记录什么证据。 | 低：把 taxonomy 转成验收清单/回归样例；若用论文数据做自动判定则需另建工具和人工复核。 | **可用**（作为反向设计依据，不作为软件底座）。直接支持本项目明确任务契约、持久进度、任务终态、独立验证、agent 不自判等设计方向；不能由论文推导具体单机规模阈值。 |

### F. 可观测与 OpenTelemetry

| # | 候选、公开事实与锚点（访问日期） | 成熟度 | 解决哪一层 | 接入代价（人话） | 契合判定与本席判断 |
|---|---|---|---|---|---|
| 16 | **OpenTelemetry GenAI semantic conventions**。维护仓库覆盖 GenAI client、MCP、provider 及 agent/framework spans；当前 agent span 文档明确标记 `Development`，包括 `invoke_agent`、`execute_tool` 等语义。 [GenAI conventions repository](https://github.com/open-telemetry/semantic-conventions-genai)；[agent spans spec](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md)（访问：2026-10-19） | OTel 基础遥测生态成熟；GenAI/agent 语义子集仍标 Development，需 pin 版本并预期命名变化。 | **可观测层**：统一记录模型/agent/tool 调用时间、属性与关联 span；不构成任务账本、权限控制或完成证据。 | 中高：SDK/provider instrumentation、collector/backend、采样/保留、敏感字段过滤和查询面板都要接；只要本机审计可用结构化事件日志。 | **部分可用**。保持任务ID/会话ID/退出码等低成本结构化事件即可。**重议 tracing（判断）**：同时满足任一项——(a) 一次任务跨 ≥3 台机器或 ≥3 个独立服务边界；(b) 每月 ≥5 次无法靠日志重建因果链的跨组件事故；且信息可安全脱敏并有明确排障负责人——再用短期抽样试点，不先上全量分布式 tracing。 |

## ③ 人话结论（≤600 字）

**可以直接用/借用三层：**
1. **agent 启动工具层**：Codex `exec`、OpenCode `run`、Claude Code `-p` 已能非交互启动；看板做薄 adapter，不必自造模型运行时。
2. **项目说明层**：AGENTS.md 是低成本的共享 Markdown 约定，派工时把项目路径/指令交给进程即可；它不是任务账本。
3. **失败模式与验证方法**：借鉴 MAST 的系统设计、交接错位、任务验证分类，强化卡片契约、证据与独立复核；无需把论文框架装进产品。

**必须自己造的核心：**本机看板的**状态层/权限不变量**——卡片真相、认领租约、证据绑定、agent 完成与人类拍板的边界。A2A 是远端 agent-to-agent，MCP 是 agent-to-tool，ACP/AG-UI 是编辑器或前端交互，Temporal/Restate/DBOS 是长流程恢复，Yjs/Automerge 是多副本合并；都不同时解决本项目的状态机、唯一认领与人的审批权。把它们整套接入反而扩大运维与权限面。

本机既有「不做全链路标准化/不做分布式 tracing/worktree 不默认引入」立场不应因协议热度而推翻。仅在本报告各条明确的**跨机器、异厂商复用、离线多写、进程故障续跑、跨边界排障**阈值被实际命中后，再做可量化小试点；上述数字阈值是本席建议的复议触发条件，不是论文或标准规定。

## ④ 未证清单

- 未对本机实际安装的 codex/opencode/claude CLI 做版本、退出码、权限提示、流式输出或 session resume 实测；本报告仅证明官方文档公开了这些能力。
- 未运行任何 A2A/ACP/AG-UI/MCP 互操作 demo；各 agent 是否支持对应协议、认证如何落地、是否能通过本机安全策略，均未证。
- 未实测 Temporal、Restate、DBOS 的部署/成本/故障恢复，也未比较本机文件数据库与这些系统的性能。当前规模是否达到耐久执行门槛未证。
- 未验证 Yjs/Automerge 在任务状态、租约和审批并发冲突下的产品正确性；判定只基于其 CRDT 同步定位与本项目不变量的适配分析。
- 未测 OpenTelemetry 的端到端 exporter 覆盖、数据成本和敏感字段风险；agent 语义当前 Development 的状态来自访问时仓库页面。
- 未找到并核验一个能直接管理本机 Codex/OpenCode/Claude 等 CLI 进程的通用、跨厂商任务注册中心标准。A2A 的 AgentCard/Task 面向协议兼容的远端 agent；是否有其他更匹配标准未证。
- 本报告中的复议规模阈值为**本席建议**，不是公开规范要求；需由发牌席结合项目真实派工量、故障记录及审查带宽拍板。

## ⑤ 锚点汇总

| 领域 | 回源链接（均于 2026-10-19 访问） |
|---|---|
| A2A | [A2A 官方站/规范入口](https://a2a-protocol.org/latest/)；[Linux Foundation 项目公告](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents)；[任务模型页](https://agent2agent.info/docs/concepts/task) |
| ACP / AG-UI | [ACP Introduction](https://agentclientprotocol.com/get-started/introduction)；[AG-UI Introduction](https://docs.ag-ui.com/introduction) |
| MCP / AGENTS.md | [MCP 官方入门](https://modelcontextprotocol.io/docs/)；[AGENTS.md 项目站](https://agents.md/)；[AGENTS.md GitHub](https://github.com/agentsmd/agents.md) |
| CLI | [Codex 非交互文档](https://learn.chatgpt.com/docs/non-interactive-mode)；[OpenCode CLI](https://opencode.ai/docs/cli)；[Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference) |
| Durable Execution | [Temporal glossary](https://docs.temporal.io/glossary)；[Restate workflows](https://docs.restate.dev/tour/workflows)；[DBOS architecture](https://docs.dbos.dev/architecture) |
| CRDT / 黑板 | [Yjs Introduction](https://docs.yjs.dev/)；[Automerge Concepts](https://automerge.org/docs/reference/concepts)；[Hayes-Roth 1985](https://www.sciencedirect.com/science/article/pii/0004370285900633) |
| 失败模式 / tracing | [MAST arXiv v3](https://arxiv.org/abs/2503.13657)；[OTel GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai)；[OTel agent span conventions](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md) |

---

**复核口径提示**：共 16 条候选（条目数，不是文件数）；6/6 方向覆盖；本席建议由发牌席抽验原链接，不将本席自报视为终审结论。
