# D3 · Symphony 规格精读 ＋ MAST 失效映射

- 席号：**调研席 D3** ｜ 日期：**2026-10-19** ｜ 实测时刻：**2026-10-19 16:38（+08:00，见文末可复跑命令）**
- 父总单：`docs/design/20261019-architecture-deepdive/00_派工总单.md`
- 派工单：`docs/design/20261019-architecture-deepdive/D3_外部规格与失效模式.md`
- 性质：**纯外部调研**（联网只读）。受 D-002 约束：**⛔ 未写任何产品代码、⛔ 未 clone 仓库、⛔ 未装依赖、⛔ 未跑代码**。
- 判定词表（闭集）：`直接覆盖`／`部分覆盖`／`不覆盖`（红线覆盖判定）；`可用`／`部分可用`／`不可用`／`未证`（机制可用性）。

> **人话摘要（30 秒版）**：Symphony 的 SPEC 是一份「调度器规格书」，把「谁认领、跑几个、失败怎么重试、状态怎么对账」写得很细，**能直接抄的主要是调度骨架**；但它**只管调度、不管验收**——它自己明说「写工单是 agent 的活，Symphony 只负责跑」，所以我们的红线①（完成＝证据）它**不覆盖**；它的「人审批」是可选实现细节，红线②它**不覆盖**；它的「认领」是进程内内存集合、**没有心跳租约**，红线③它**不覆盖**。MAST 论文给的 14 类失效里，我们的三条红线**直接防得住 2 类、部分防 7 类、完全防不住 5 类**——那 5 类就是我们要补的设计缺口（最要命的是「验证是错的」，占比 9.1%）。

---

## 0 本席产出总览（反空跑计数）

| 口径 | 计数 | 说明 |
|---|---|---|
| 外部来源（URL） | **5** | SPEC raw ＋ SPEC blob ＋ LICENSE ＋ arXiv 摘要页 ＋ arXiv 全文 HTML（全部见 §E） |
| Symphony 机制逐节精读 | **8** | 每个均有「规格原文要点／能用／不适用＋为什么」三栏（§A） |
| SPEC 假设在我们场景「会破」的清单 | **9** | §A.9 |
| MAST 失效类目 | **14**（分 3 大类） | 逐条列表（§B1）；**每条**有「会不会发生／哪条红线／防不住缺什么」 |
| 红线判定分布 | 直接 **2** ／ 部分 **7** ／ 不覆盖 **5** | 合计 = 14（§B2） |
| 「红线覆盖不到」的失效 | **5 类完全 ＋ 7 类部分** | §B3（**必须非零**，见下） |
| 交给 D1／D2 的设计输入条目 | **13** | §C（C-1…C-13） |
| 未证条目 | **6** | §D |

**非零反空跑闸（AGENTS §1.2）**：
- 判定「红线完全覆盖不到」的失效数 = **5 > 0**。若此数为 0，说明本席在美化（把「没覆盖」说成「覆盖」），闸门即失效。
- 判定「红线直接覆盖」的失效数 = **2 > 0**。若为 0，说明判定尺坏了（红线一条都没生效也不合常理），需先怀疑尺、再判件。
- MAST 逐条列表逐条数 = **14**，与论文原文 14 条一一对齐（少一条即本席 FAIL）。

---

## A Symphony SPEC 逐节精读

### A.0 来源与访问凭据

- 件：`openai/symphony` → `SPEC.md`（标题原文：**Symphony Service Specification**；自述状态：**Status: Draft v1（language-agnostic）**）。
- 派工单指定入口：`https://github.com/openai/symphony/blob/main/SPEC.md`。
- 本席实际取数入口（等效全文）：`https://raw.githubusercontent.com/openai/symphony/main/SPEC.md`。
- **访问日期：2026-10-19**（实测时刻以文末 `Get-Date` 输出为准）。
- 全文 **2312 行**，本席分两段读入（1–1270，1270–2312），**未发现截断**。
- 许可：`https://raw.githubusercontent.com/openai/symphony/main/LICENSE` 回源＝**Apache License Version 2.0**（本席亲验，非引用旧结论）。
- ⚠️ 本席**未**单独回读 blob 页面本身确认渲染、**未**取 SPEC 的 commit sha／最后提交日期（见 §D 未证）。

### A.1 定位与边界（SPEC §1–§3）

**规格原文要点（转述）**：
- Symphony 是一个长驻服务：轮询 issue tracker → 为每个 issue 建独立 workspace → 在其中跑一个 **coding agent 会话**。
- 自我定位极窄：**它是 scheduler/runner ＋ tracker reader**；工单的写操作（状态流转、评论、PR 链接）**由 agent 通过 provider 工具完成**，不是它干的。
- 明确允许「成功」停在 **handoff state**（例：`Human Review`），不一定是 `Done`。
- 非目标（§2.2）：不做丰富 Web UI／多租户控制台；不做通用工作流引擎／分布式作业调度；**不强制统一的审批／沙箱／人确认姿态**（交由实现自定）。

**我们能直接用什么**：
- 可直接采纳它的**边界自觉**：看板本体只做「调度 ＋ 读真相源」，不把业务写法硬塞进调度器。
- §1 的「成功可停在 Human Review」与我们红线②（人拍板位）**天然同向**，可作为 D1 里「完成 ≠ Done、可停在 review/拍板列」的规格依据。

**哪里不适用及为什么**：
- Symphony 假设「**存在一个可轮询的 issue tracker**」且它是任务真相源；我们的真相源是**盘上卡片文件**（D-001 拍板「文件即卡＝唯一事实源」），没有远程 API 轮询语义 ⇒ 它的「轮询 + 对账」要改写成「读盘／读 git + 对账」。
- 它假设「**执行体是 coding agent**」；我们含**非编码 agent**（翻译、调研、视觉、出图等），「为每个 issue 建 workspace 跑代码」对纯调研席大部分不成立 ⇒ workspace 隔离只是可选，不是通用底座。

### A.2 调度状态机（SPEC §7.1／§7.2／§7.3／§7.4）

**规格原文要点（转述）**：
- **内部 claim 状态**（≠ tracker 状态）共 **5 个**：`Unclaimed`／`Claimed`／`Running`／`RetryQueued`／`Released`（§7.1）。
- **Run Attempt 生命周期**共 **11 个相位**（§7.2）：`PreparingWorkspace`→`BuildingPrompt`→`LaunchingAgentProcess`→`InitializingSession`→`StreamingTurn`→`Finishing`，终态区分 `Succeeded`／`Failed`／`TimedOut`／`Stalled`／`CanceledByReconciliation`。规格明确：**区分不同终态原因很重要**，因为重试逻辑与日志各不相同。
- **转移触发器**（§7.3）：`Poll Tick`／`Worker Exit(normal)`／`Worker Exit(abnormal)`／`Codex Update Event`／`Retry Timer Fired`／`Reconciliation State Refresh`／`Stall Timeout`。
- **幂等与恢复**（§7.4）：所有状态变更**经单一权威序列化**；启动任何 worker 前**必须**检查 `claimed` 与 `running`；每个 tick **对账先于派发**。

**我们能直接用什么**：
- **「内部 claim 状态」与「人的看板列」解耦**——这条思想可直接抄为 D1 的双维度：看板列（Todo/In Progress/Review/拍板/Done）是一维，调度层租约状态是另一维。**建议照抄 5 个 claim 状态名**，映射到我们的单卡单执行者。
- **distinct terminal reasons** 直接抄：卡片完成/失败要带**原因类型**（成功／失败／超时／失联回收／被人工取消），这是 D2 判据与留痕的字段。
- **对账先于派发**直接抄为铁律。

**哪里不适用及为什么**：
- 它的「单一权威内存态」在我们的场景**必须换成盘上态**：因为红线①要求状态即证据、且我们有**跨会话／跨引擎**读写，内存态重启即丢（SPEC §14.3 自己承认重启不恢复 retry／session）。⇒ 这是 SPEC 与红线①冲突处，**按红线走**（落盘）。
- 它的 11 个相位里 `PreparingWorkspace`／`LaunchingAgentProcess`／`InitializingSession`／`StreamingTurn` 是**Codex app-server 专用**，我们多引擎无此公共相位，只能保留 `Finishing` 之后的**终态分类**。

### A.3 claim 防重复怎么做的（SPEC §7.4／§8.2／§4.1.8／§16.4）

**规格原文要点（转述）**：
- 权威状态 `Orchestrator Runtime State` 含 `claimed`（issue ID 集合：reserved/running/retrying）与 `running`（`issue_id → running entry` 映射）（§4.1.8）。
- 派发前逐条检查（§8.2）：「不在 `running` 且不在 `claimed`」才可派。
- 派发动作 `dispatch_issue`（§16.4）先起 worker，成功后 `state.claimed.add(issue.id)` 并移除其 retry 条目。
- 关键句：**orchestrator 通过单一权威把状态变更串行化，避免重复派发**（§7.4）。

**我们能直接用什么**：
- 「派发前查 claimed／running」＋「单写者序列化」＝我们红线③「认领即租约」的同义机制，**语义可直接抄为 D2 的认领前置校验**。

**哪里不适用及为什么**：
- 它的 claim 是**进程内内存集合**、**无 TTL、无心跳、无留痕**；一旦 orchestrator 崩了或有两个进程，防重即失效。我们的场景恰恰是**多 agent／多会话同时看一块板**，认领必须**落盘且跨进程可见**，回收必须**留痕**（红线③）⇒ 必须把「内存 claimed 集合」改造成「盘上租约件（holder／acquired_at／expires_at／heartbeat_at／回收记录）」。
- 它是**单 orchestrator**，天然无并发抢卡问题；我们是**多执行者抢同一张卡**，这是 SPEC **没有**回答的问题。

### A.4 并发上限怎么控（SPEC §8.3／§5.3.5）

**规格原文要点（转述）**：
- 全局上限 `agent.max_concurrent_agents`（**默认 10**）；每状态上限 `agent.max_concurrent_agents_by_state`（map，默认空）。
- 公式：`available_slots = max(max_concurrent_agents - running_count, 0)`；per-state 有则用它、否则回落全局（§8.3）。
- state key 归一化＝`trim + lowercase`；非法条目（非正数/非数字）忽略（§5.3.5）。

**我们能直接用什么**：
- 公式与「全局 ＋ 按状态双层上限」可直接抄；state 归一化规则可直接抄到卡片状态比较。

**哪里不适用及为什么**：
- 全局纪律明令**路数数字不写死**（由当场可切分文件数与用户审查带宽决定）⇒ 采纳 `max_concurrent_agents` 这个**旋钮**，但**默认值与上限由人当场定**，照抄它的默认 10 属越界。
- 它的并发是**跨 issue 的流水线**；我们更要防的是**同一张卡被两个执行者同时跑**（红线③）——那是租约问题，不是并发槽问题。

### A.5 重试与回收策略（SPEC §8.4／§7.3／§16.6）

**规格原文要点（转述）**：
- 正常退出（clean exit）：按固定短延迟 **1000 ms** 排一次 continuation retry（§8.4／§16.6）。
- 异常退出：指数退避 `delay = min(10000 * 2^(attempt-1), agent.max_retry_backoff_ms)`，上限默认 **300000 ms（5 分钟）**（§8.4）。
- RetryEntry 字段：`issue_id`／`identifier`／`attempt`（1 基）／`due_at_ms`（单调时钟）／`timer_handle`／`error`（§4.1.7）。
- 重试触发时（§8.4）：先 `fetch_issues_by_ids([id])` 刷新；找不到 → release claim；已终态 → 清工作区并 release；仍活跃可路由 → 有槽则派、无槽则 requeue（错误＝`no available orchestrator slots`）；不再活跃 → release 不派。
- 回收：`on_retry_timer`（§16.6）无槽时也 requeue 并记录原因。

**我们能直接用什么**：
- **退避公式与参数名**可直接抄进 D2；「重试前先刷新真相、刷新失败不硬派」的可直接抄。
- **requeue 必带错误原因**（`no available orchestrator slots` 这种显式原因）可直接抄为卡片 blocked 理由字段。

**哪里不适用及为什么**：
- 它的「刷新真相」是 `fetch_issues_by_ids`（远程 API）；我们是**读卡片文件**，要改成「读盘 + 比 sha/mtime」。
- 它的「release claim」是**静默移除集合元素**；我们的回收**必须留痕**（谁回收／何时／原执行者，红线③）⇒ release 要写成一条**回收记录**，不能静默。
- 它的 retry timer 是进程内存的定时器，重启即丢（§14.3）；我们要能**断点续跑**（全局规则）⇒ 重试排程需落盘。

### A.6 状态对账（reconciliation）机制（SPEC §8.5／§8.6）

**规格原文要点（转述）**：
- 每个 tick 都跑对账，分两段（§8.5）：
  - **Part A 停滞检测**：对每个 running issue，算 `elapsed_ms`（自 `last_codex_timestamp`，无事件则自 `started_at`）；`> codex.stall_timeout_ms`（默认 **300000 ms／5 分钟**）则杀 worker 并排重试；`<= 0` 则关闭该检测。
  - **Part B tracker 状态刷新**：拉所有 running issue 的当前状态——终态→杀 worker 并清工作区；仍活跃且可路由→更新内存快照；活跃但不可路由→杀 worker **不清**工作区；既非活跃也非终态→杀 worker **不清**工作区。刷新失败→**保持 worker 运行**，下个 tick 再试。
- 启动清理（§8.6）：启动时查终态 issue，删除其工作区；查询失败→记警告并继续启动。

**我们能直接用什么**：
- **「每 tick 先对账再派发」＋「刷新失败保持现状、绝不静默改变状态」**＝我们红线「退化必须可见」的同向机制，直接抄。
- Part A 的**停滞检测公式**（自最后事件起算的静默超时）可借为心跳超时的**辅助**判据。

**哪里不适用及为什么**：
- Part A 的「last_codex_timestamp」是**来自 agent 的事件流**；我们多引擎未必有统一事件流 ⇒ 我们**必须**把主动心跳（租约件心跳）当主判据，事件静默当辅判据。**SPEC 没有「执行者主动心跳」这个概念**，这是要新造的部分（红线③）。
- Part B 的「清不清工作区」依赖有 workspace 概念；对非编码席不适用。

### A.7 结构化日志字段（SPEC §13.1／§13.3）

**规格原文要点（转述）**：
- issue 相关日志**必需**上下文字段：`issue_id`、`issue_identifier`（§13.1）。
- coding-agent 会话生命周期日志**必需**：`session_id`。
- 格式：稳定 `key=value` 措辞；含动作结果（`completed`／`failed`／`retrying`）；含简明失败原因；避免打大 payload。
- 可选快照接口（§13.3）：`running` 行（含 `turn_count`）、`retrying` 行、`codex_totals`（input/output/total tokens ＋ `seconds_running`）、`rate_limits`。

**我们能直接用什么**：
- 字段模板直接映射：`issue_id → card_id`、`issue_identifier → card 可读 ID`、`session_id → 「引擎-会话ID」`。
- 「key=value ＋ 动作结果 ＋ 失败原因」的日志形状直接抄，作为看板日志与留痕格式。

**哪里不适用及为什么**：
- token／rate-limit 统计是 Codex 专用（§13.5）；我们多引擎无统一口径 ⇒ 只保留「运行秒数／往返数」这种**引擎无关**指标。

### A.8 workspace 隔离与安全不变量（SPEC §9／§15）

**规格原文要点（转述）**：
- 三条安全不变量（§9.5）：① agent 只在 per-issue workspace 内跑（启动前校验 `cwd == workspace_path`）；② workspace 路径必须在 workspace root 前缀内；③ workspace key 只允许 `[A-Za-z0-9._-]`，其他字符换 `_`，若发生替换则**追加原标识的稳定 hash（≥64 位熵）**防碰撞。
- 秘密处理（§15.3）：配置支持 `$VAR` 间接；**不打印密钥**；tracker 凭据**不进子进程环境**。
- harness hardening（§15.5）：不假定 tracker 数据／仓库／工具参数可信；建议收窄工具、网络、凭据、路径。

**我们能直接用什么**：
- **workspace key 清洗规则（含 64 位 hash 防碰撞）**可直接抄为**卡片文件/目录命名规则**（D1）。
- **「凭据不进子进程」**直接抄进适配层契约。

**哪里不适用及为什么**：
- workspace 隔离假设每个 issue 要建独立代码工作区；对非编码席不成立 ⇒ 列为**可选**，不进一期最小骨架。

### A.9 SPEC 假设在我们「多引擎、含非编码 agent」场景下**会破**的地方（9 条）

| # | SPEC 的假设 | 出处 | 在我们场景为什么破 | 我们要怎么改 |
|---|---|---|---|---|
| 1 | 存在一个**可轮询的 issue tracker** 且它是真相源 | §1／§3.3／§11 | 我们真相源是**盘上卡片文件**（D-001），无远程轮询 | 对账源改「读盘／读 git + sha/mtime」 |
| 2 | 调度状态可**只放内存**、重启不恢复 | §4.1.8／§7.4／§14.3 | 我们要跨会话／跨引擎可见、要断点续跑 | **落盘**（与红线①一致，此处以我们为准） |
| 3 | 执行体是**单一 Codex app-server**、有 stdio 协议 | §10／§3.3 | 我们多引擎（codex／qoderclicn／opencode／Hermes／RTOC），且退出码不可信（P3） | 适配层自造；只借 session_id 构造与事件回调骨架 |
| 4 | 任务是**编码任务**、有 workspace | §1／§9 | 我们含翻译／调研／视觉等非编码席 | workspace 隔离降为可选 |
| 5 | 成功可停在 handoff state（Human Review） | §1 boundary | 与我们红线②**同向**，可直接用 | 采纳；但 SPEC 未强制「只有人能推」 |
| 6 | 审批／沙箱／人确认是 **implementation-defined**（不强制） | §2.2／§10.5／§15.1 | 我们红线②要求**人的拍板位不可被 agent 覆盖** | SPEC **不覆盖**红线②，须新造权限模型 |
| 7 | claim 是**进程内内存集合**、无 TTL 心跳 | §4.1.8／§8.2 | 我们红线③要求**心跳超时回收 + 留痕** | 改造为盘上租约件＋心跳＋回收记录 |
| 8 | **单 orchestrator** 单进程权威，天然无抢卡 | §7.4 | 我们多 agent／多会话抢同一张卡 | 认领必须落盘、跨进程原子（新造） |
| 9 | **不做完成验收**（scheduler not verifier；写工单是 agent 的活） | §1 boundary／§11.5 | 我们红线①要求**完成必须挂盘上凭据** | SPEC **不覆盖**红线①，须新造完成判据 |

---

## B MAST 14 类失效 → 我们的设计对策

### B.0 来源与凭据

- 论文：**《Why Do Multi-Agent LLM Systems Fail?》**（MAST：Multi-Agent System Failure Taxonomy）。
- arXiv 摘要页：`https://arxiv.org/abs/2503.13657`；全文 HTML（v3）：`https://arxiv.org/html/2503.13657v3`。
- **访问日期：2026-10-19**。
- 规模（摘要原文口径）：初始分析 **150** 条轨迹（6 位专家、Grounded Theory）→ **14** 条失效模式 → **3** 大类；人工一致率 κ=0.88；最终数据集 MAST-Data 含 **1642** 条标注轨迹、跨 **7** 个 MAS 框架。
- 14 条模式定义取自论文 **Appendix A**（FC1 §A.1／FC2 §A.2／FC3 §A.3）；占比取自正文 **§4**（对 1642 条轨迹的统计）。
- ⚠️ **占比是我们直接引用的论文数字，不是我们场景的失效率**（见 §D 未证 #6）。
- ⚠️ **「在我们场景会不会发生、哪条红线能否防住」全部是本席推断**（论文研究对象是 7 个 MAS 框架在编码/数学/通用任务上的失败，**不是**「agent 共享看板」），已在 §D 未证 #4 显式标注。

### B.1 逐条列表（14 条，按 3 大类）

**判定尺（先声明，防事后改口径）**：
- `直接覆盖`＝某条红线的机制语义**就是**防这条失效。
- `部分覆盖`＝红线的**附带效果能减轻**，但主防线在红线之外。
- `不覆盖`＝三条红线**都指不到**。

#### FC1 · System Design Issues（系统设计，5 条）

| 编号 | 名称 | 原文含义（转述） | 占比 | 在我们场景会不会发生 | 哪条红线／机制能防 | 防不住的话缺什么 |
|---|---|---|---|---|---|---|
| FM-1.1 | Disobey task specification 不守任务规格 | 没遵守任务给定约束/要求，导致结果次优或错误 | 11.8% | **会**（卡片契约写得糊就会） | **部分**：红线①要求交付挂证据，若证据含「对照任务规格」的检查可抓到；契约本身不属红线 | 卡片必须有**可验收的 doD／约束字段**；独立复核席对照规格 |
| FM-1.2 | Disobey role specification 不守角色规格 | 没守被分配角色的职责/边界，甚至越成另一个 agent | 1.5% | **会**（多引擎多席位尤甚） | **部分**：红线②挡的是「agent 越到**人**的拍板列」；**不挡** agent 扮成另一个 agent 角色 | 卡片要带**席位/角色定义**；权限模型（谁能写哪些列/哪些字段） |
| FM-1.3 | Step repetition 步骤重复 | 重复已完成的步骤，拖慢并可能引入错误 | **15.7%**（本类最高） | **会** | **部分**：红线③挡「同一卡**同时**两个执行者」；**不挡**同一执行者**自己**重复步骤 | 断点续跑**进度契约**（全局规则已有）；执行器内部步骤去重属引擎层，看板只外置进度 |
| FM-1.4 | Loss of conversation history 丢会话历史 | 上下文意外截断，退回较早状态 | 2.8% | **会**（多轮改稿/长任务） | **不覆盖**：三条红线都不涉及 agent 内部上下文 | 状态**外置**＝卡片即事实源（重开会话先读盘重建）；会话**交接块** |
| FM-1.5 | Unaware of termination conditions 不知终止条件 | 不认识「该结束时」的判据，导致无谓继续 | 12.4% | **会** | **部分**：红线①「没凭据不许进 Done」会把它**挡在 verify**，但不教它何时该停 | 卡片必须有**非空 doD/终止条件**；「停在 verify 由复核判」 |

#### FC2 · Inter-Agent Misalignment（agent 间错位，6 条）

| 编号 | 名称 | 原文含义（转述） | 占比 | 在我们场景会不会发生 | 哪条红线／机制能防 | 防不住的话缺什么 |
|---|---|---|---|---|---|---|
| FM-2.1 | Conversation reset 对话重置 | 对话意外重启，丢上下文与进度 | 2.2% | **会** | **不覆盖** | 同 FM-1.4：状态外置＋交接块 |
| FM-2.2 | Fail to ask for clarification 不问就猜 | 信息不清时不追问，直接按猜的做 | 6.8% | **会** | **部分（弱）**：看板提供「请求拍板/待澄清」通道，但**不强制** agent 去用 | 卡片要有 **blocked／待澄清**状态 ＋ 明确「不清就问」的契约；人拍板位 |
| FM-2.3 | Task derailment 任务跑偏 | 偏离原目标，做无关或无产出的动作 | 7.4% | **会** | **不覆盖**：看板层看不见「目标是否漂移」 | 卡片目标/契约 ＋ **复核席**对照；依赖显式化 |
| FM-2.4 | Information withholding 藏信息 | 手握关键信息却不共享，影响他人决策 | 0.85% | **会** | **部分**：红线①「交付必须挂盘」使信息**无法只留在 agent 脑子里**（减轻藏匿面） | 卡片评论/依赖/证据**必填**，跨席信息走盘上件 |
| FM-2.5 | Ignored other agent's input 无视他人输入 | 无视其他 agent 给的输入/建议 | 1.9% | **会** | **不覆盖** | 卡片依赖/评论显式化 ＋ 复核席「有没有回应上游意见」 |
| FM-2.6 | Reasoning-action mismatch 说做不一 | 推理与实际行动不符 | **13.2%** | **会** | **直接覆盖（最强）**：红线①「**模型说完成了不算**、没有盘上凭据一律停 verify」正是防「说的=做的」的假象 | 前提：**凭据必须可复算**（不是 agent 的转述）；否则要复核席 |

#### FC3 · Task Verification（任务验证，3 条）

| 编号 | 名称 | 原文含义（转述） | 占比 | 在我们场景会不会发生 | 哪条红线／机制能防 | 防不住的话缺什么 |
|---|---|---|---|---|---|---|
| FM-3.1 | Premature termination 过早终止 | 目标未达成就结束，结果不完整/错 | 6.2% | **会** | **直接覆盖**：红线①（无凭据不许进 Done → 停在 verify）＋ 红线③（心跳超时＝回收，防甩手） | doD 必须**非空**，否则「凭据」可被空文件伪造 |
| FM-3.2 | No or incomplete verification 不验/浅验 | 不做或只做部分检查/确认，错误静默传播 | 8.2% | **会** | **部分**：红线①强制「有凭据」，**不保证验证深度** | **独立复核席** ＋ **多层验证**（论文 Insight 3）＋ 反空跑对照 |
| FM-3.3 | Incorrect verification 错验 | 验证/交叉检查本身做错，把坏件判成好件 | **9.1%** | **会**（最尖锐） | **不覆盖**：红线①只要求「有凭据」，**不保证凭据为真/对得上** | 独立复跑 ＋ **反空跑两把尺** ＋ 假修复红线（本项目已有此纪律，**但未进红线**） |

### B.2 判定汇总（分布必须非零）

| 判定 | 条数 | 编号 |
|---|---|---|
| `直接覆盖` | **2** | FM-2.6、FM-3.1 |
| `部分覆盖` | **7** | FM-1.1、FM-1.2、FM-1.3、FM-1.5、FM-2.2、FM-2.4、FM-3.2 |
| `不覆盖` | **5** | FM-1.4、FM-2.1、FM-2.3、FM-2.5、FM-3.3 |
| 合计 | **14** | — |

### B.3 ⚠️ 我们的三条红线**覆盖不到**的失效（要补的设计缺口）

> 本小节是本批最重要的产出。**不粉饰**：三条红线**只直接防住 2/14**。

**(a) 完全覆盖不到（5 类，红线一条都指不到）**

| 失效 | 占比 | 为什么红线指不到 | 缺口性质 |
|---|---|---|---|
| **FM-3.3 Incorrect verification** | **9.1%** | 红线①只保证「有凭据」，**不保证凭据是真的/对得上**——一个假验证器照样能产出「看起来合格的凭据」 | **最高优先**：需把「独立复核＋反空跑对照＋假修复红线」**形式化进卡片模型** |
| FM-2.3 Task derailment | 7.4% | 红线管状态/权限/租约，**不管目标是否漂移** | 需「契约（doD）＋评估/复核列」 |
| FM-1.4 Loss of conversation history | 2.8% | agent 内部上下文，红线不可见 | 需「状态外置＋交接块」（看板只能减轻） |
| FM-2.1 Conversation reset | 2.2% | 同上 | 同上 |
| FM-2.5 Ignored other agent's input | 1.9% | 红线不管「有没有读别人意见」 | 需依赖/评论显式化＋复核 |

**(b) 部分覆盖（7 类）——红线只减轻、主防线在红线之外**

FM-1.1、FM-1.2、FM-1.3、FM-1.5、FM-2.2、FM-2.4、FM-3.2。它们的共同点：**红线提供了「兜底」，但不提供「判据」**。例：红线①能把 FM-3.2（浅验）**挡在 verify**，但「验到什么深度才算过」得靠独立复核席与多层验证——**那是红线之外的新造件**。

**(c) 从 B.3 抽出的三个补缺主题**

1. **验证质量**（FM-3.3／3.2／1.1）：红线只保「有证据」，不保「证据为真」。→ 卡片必须带 `verifier`／`required_evidence`／`negative_control` 三个字段，把「独立复核」与「反空跑两把尺」变成**卡片模型的一部分**，而不是流程口头纪律。
2. **执行者内部进程**（FM-1.3／1.4／2.1）：看板看不到 agent 内部步骤与上下文。→ 只能靠「卡片即事实源 ＋ 断点续跑进度契约 ＋ 交接块」把损失**外置可控**，不能根除。
3. **目标守恒**（FM-2.3／2.5／2.2）：跑偏／无视输入／不问就猜。→ 靠「契约（doD）＋ 依赖显式化 ＋ 复核席 ＋ 人拍板位」。

### B.4 由 MAST 三类推出的必补机制（一句话）

- FC1（设计）→ 卡片要有**契约与角色**（doD、席位、任务规格）。
- FC2（错位）→ 信息与依赖要**显式落盘**（评论/依赖/`blocked`），且提供**澄清通道**。
- FC3（验证）→ **多层验证 ＋ 独立复核 ＋ 反空跑对照**（论文 Insight 3 原话：只靠最后一层低阶检查不够）。

---

## C 交给 D1／D2 的设计输入清单（可执行条目）

> 约定：`照抄`＝SPEC 语义直接可用；`改造`＝借骨架但换掉不适用的假设；`新造`＝SPEC/论文都没有、必须我们自造。

### C.1 给 D1（卡片数据模型与状态机）

- **C-1【照抄】双维度状态**：照抄 SPEC §7.1「内部 claim 状态 ≠ 人的看板列」。D1 的状态机要**同时**描述两维：
  - (a) 人的看板列：`Todo`／`In Progress`／`Review`／`拍板`／`Done`；
  - (b) 调度层租约状态（照抄 5 个名字）：`Unclaimed`／`Claimed`／`Running`／`RetryQueued`／`Released`。
- **C-2【照抄】区分终态原因**：照抄 SPEC §7.2 的 distinct terminal reasons：`Succeeded`／`Failed`／`TimedOut`／`Stalled`／`CanceledByHuman`。卡片完成/失败必须带**原因类型**（供 D2 判据与留痕）。
- **C-3【改造】卡片字段**：以 SPEC §4.1.1 的 Issue 字段为基础（`id`／`identifier`／`title`／`description`／`priority`／`state`／`assignee_id`／`labels`／`blocked_by`／`created_at`／`updated_at`），**但必须补 SPEC 没有的三件**：
  - `required_evidence`（**红线①**：完成要挂什么凭据，非空才可进 Done）；
  - `human_gate`（**红线②**：哪些列只能人推、agent 只能请求）；
  - `lease`（**红线③**：holder／acquired_at／expires_at／heartbeat_at／回收记录）。
- **C-4【照抄】命名规则**：照抄 SPEC §4.2 workspace key 清洗规则——只允许 `[A-Za-z0-9._-]`，其余换 `_`；若清洗改变了原标识，**追加原标识的稳定 hash（≥64 位熵）** 防碰撞。用途：卡片文件/目录命名。

### C.2 给 D2（租约与验收判据）

- **C-5【改造】认领语义**：借 SPEC §7.4／§8.2 的「**派发前必查 claimed／running**，单权威序列化」；**但**把「tracker 拉取」换成「**读卡片文件 + 比 sha/mtime**」，把「内存 claimed 集合」换成「**盘上租约件**」（红线③要跨进程可见 + 留痕）。
- **C-6【改造】心跳与回收**：借 SPEC §8.5 Part A 的静默超时公式（自最后事件起算 `elapsed > stall_timeout`）；**但**主判据改用**执行者主动心跳**（全局规则已有 120s 心跳范式），并**补 SPEC 没有的回收留痕**（谁回收／何时／原执行者）。
- **C-7【照抄】并发上限**：照抄 SPEC §8.3 `available_slots = max(global - running, 0)`，per-state 上限 map 可借；state key 归一化 `trim + lowercase`。⚠️ **路数默认值不写死**（全局纪律），当场定。
- **C-8【改造】重试退避**：照抄 SPEC §8.4 公式——continuation retry 固定短延迟（SPEC 用 1000 ms）；failure 指数退避 `min(10000 * 2^(attempt-1), cap)`（SPEC cap 默认 300000 ms）。**但**「刷新真相」改读盘、「release claim」改写**回收留痕**；排程需**落盘**以支持断点续跑。
- **C-9【新造】完成判据（D2 核心）**：SPEC **没有**完成判据（scheduler not verifier，§1 boundary）。D2 必须自造。**可借** SPEC §1「成功可停在 handoff state 而非 Done」作为「**停在 verify 列由复核判**」的规格依据。
- **C-10【新造】独立复核机制**：借 MAST Insight 3（多层验证）＋本项目「反空跑两把尺」＋「假修复红线」，落到卡片字段：`verifier`（复核席身份）、`negative_control`（**必须非零**的反空跑对照）。这是补 FM-3.3/FM-3.2 的关键件。

### C.3 给两席共用

- **C-11【照抄】日志字段**：SPEC §13.1 三字段 → 我们：`card_id`／`card_title`（或可读 ID）／`session_id`（「引擎-会话ID」）；格式 `key=value` ＋ 动作结果 ＋ 失败原因。
- **C-12【照抄】凭据隔离**：SPEC §15.3「**凭据不进子进程环境、不打印**」直接抄进适配层契约。
- **C-13【反用】写路径白名单**：SPEC §11.5 说「orchestrator 不做通用写、写由 agent 经 provider 工具」——这对我们**不适用**（我们的状态变更**就是**要写卡片）。故**反过来**：卡片写入必须**白名单化 ＋ 每次留痕**（谁改了什么字段、何时、凭据），这正是红线①的落点。

---

## D 未证清单（未核到／未读到的原文；推断部分显式标注）

| # | 未证项 | 说明 | 影响 |
|---|---|---|---|
| 1 | **SPEC blob 页面未单独回读** | 派工单指定 `github.com/.../blob/main/SPEC.md`；本席实际用 `raw.githubusercontent.com/.../main/SPEC.md` 取全文（等效）。blob 渲染页未单独打开确认。 | 低：正文一致；若需渲染证据需补 |
| 2 | **SPEC 的 commit sha／最后提交日期未取** | 只知分支 `main`。 | 中：「引用早期读数须带日期」——本席只能给**访问日期**，给不了**版本 sha** |
| 3 | **§17／§18 校验矩阵未逐条三栏化** | 本席对 8 个**机制**做了「能用/不适用」，未对校验矩阵 60+ 条逐条转述。 | 低：矩阵是可抄的**测试清单**，D1/D2 需要时再取 |
| 4 | **「MAST 失效在我们场景是否会发」全为本席推断** | 论文研究对象＝7 个 MAS 框架×编码/数学/通用任务，**非**「agent 共享看板」。 | **高**：B 表「会不会发生」列是推断，⛔ 不得当实测 |
| 5 | **论文只读了 HTML v3，未交叉 PDF** | v3 日期 2025-10-26（摘要页）；HTML 标 experimental。 | 低：14 条定义与占比已逐字核到 |
| 6 | **FM 占比不是我们场景的失效率** | 占比是论文对 1642 条轨迹的统计（§4），照抄自论文，⛔ 不可当我们的预期失效率。 | 中：只用于**排序优先级**，不用于定阈值 |

**已证项（供复核席对照）**：SPEC 全文 2312 行已读入无截断；LICENSE 回源＝Apache-2.0（亲验）；论文 14 条模式名＋定义＋占比与原文一致；3 大类名与原文一致。

---

## E 来源锚点（外部件给 URL ＋ 访问日期；本机件给路径）

| # | 来源 | URL／路径 | 访问日期 |
|---|---|---|---|
| S1 | Symphony SPEC 全文（raw） | `https://raw.githubusercontent.com/openai/symphony/main/SPEC.md` | 2026-10-19 |
| S2 | Symphony SPEC（派工单指定入口） | `https://github.com/openai/symphony/blob/main/SPEC.md` | 2026-10-19（未单独回读，见 D#1） |
| S3 | Symphony LICENSE（Apache-2.0） | `https://raw.githubusercontent.com/openai/symphony/main/LICENSE` | 2026-10-19 |
| S4 | MAST 论文摘要页 | `https://arxiv.org/abs/2503.13657` | 2026-10-19 |
| S5 | MAST 论文全文 HTML v3（含 Appendix A 定义） | `https://arxiv.org/html/2503.13657v3` | 2026-10-19 |
| L1 | 本项目红线原文 | `E:\GithubClone\allworktogether\AGENTS.md` §4（第 70–76 行） | 2026-10-19 |
| L2 | 派工总单／本席派工单 | `docs/design/20261019-architecture-deepdive/00_派工总单.md`／`D3_外部规格与失效模式.md` | 2026-10-19 |
| L3 | 拍板台账（D-001／D-002） | `docs/governance/DECISIONS.md` | 2026-10-19 |

---

## F 可复跑命令

本席为**纯只读外部调研**，无本机写入脚本；核证只用到两件事：取 URL（浏览器/抓取工具）与读本机件。可复跑动作：

```text
# 1. 复核 SPEC 全文（与本席同一入口；应得 2312 行、标题「Symphony Service Specification」、Status: Draft v1）
#    在浏览器打开 S1 URL，或：
curl -s https://raw.githubusercontent.com/openai/symphony/main/SPEC.md | Measure-Object -Line

# 2. 复核许可
#    打开 S3 URL，首行应为「Apache License / Version 2.0, January 2004」

# 3. 复核 MAST 14 条（打开 S5 URL，搜索 "Appendix A MAST Failure Categories"，应得 FC1×5 + FC2×6 + FC3×3 = 14）

# 4. 复核本项目红线原文
#    打开 L1，看 §4「看板本体的三条专属红线」

# 5. 实测时刻（本件报告用）
Get-Date -Format "yyyy-MM-dd HH:mm:ss zzz"      # 本席实测：2026-10-19 16:38:11 +08:00
```

---

## G 交件回报（AGENTS §6 格式）

### 交付：Symphony SPEC 逐节精读（8 机制）＋ MAST 14 类失效逐条映射三条红线（直接2/部分7/不覆盖5）＋ 给 D1／D2 的 13 条设计输入

| 改了什么 | 盘上证据（路径/读数） | 状态 |
|---|---|---|
| 新建本交件 | `docs/research/20261019-architecture-deepdive/D3-Symphony规格与MAST失效映射__调研席D3__外部公开资料.md` | 已交 |
| 精读 8 个 SPEC 机制 | 本件 §A.1–A.8（每个含「原文要点／能用／不适用＋为什么」） | PASS（≥5 达标） |
| 列举 9 条会破的假设 | 本件 §A.9 | PASS |
| 14 类失效逐条映射 | 本件 §B.1（FC1×5／FC2×6／FC3×3 = **14**） | PASS（逐条列全） |
| 红线覆盖不到的失效 | 本件 §B.3（完全 **5** ＋ 部分 **7**） | PASS（含专节） |
| 设计输入清单 | 本件 §C（C-1…C-13 = **13** 条） | PASS |

**计数（N of M，口径＝条目数）**：
- SPEC 机制精读：**8 of 8**（本席自定 8 个必读机制全覆）。
- MAST 失效逐条：**14 of 14**（论文原文 14 条一一对齐）。
- 设计输入：**13 of 13**。
- 外部来源锚点：**5 of 5**（SPEC raw／blob／LICENSE／arXiv abs／arXiv html）。
- 判定分布：直接 **2** ／ 部分 **7** ／ 不覆盖 **5** ＝ **14 of 14**。

### 未做 / 未证（如实列举）

- **未证**：SPEC 的 commit sha／最后提交日期（D#2）；SPEC blob 渲染页未单独回读（D#1）；§17/§18 校验矩阵未逐条三栏化（D#3）；论文只读 HTML v3、未交叉 PDF（D#5）。
- **推断非实测**：「MAST 失效在我们场景会不会发生」全为本席推断（D#4）；FM 占比是论文数字、非我们场景失效率（D#6）。
- **未做（守 D-002）**：未写任何产品代码；未 clone 仓库；未装依赖；未跑代码。**未**动本批次目录以外的任何文件；**未**动 `AGENTS.md`／`docs/governance/`。

### 风险与残留（含「我知道但没处理」的）

- **最大残留**：MAST 的「会不会发生」是推断，但结论「红线覆盖不到 5 类」**依赖该推断**。若用户认为「FM-3.3 错验在我们场景不可能发生」，则 §B.3 的排序需重评——**本席未做这一步**，留待发牌席／用户。
- **我知道但没处理**：SPEC §17/§18 其实是一份现成的**测试清单**，画板施工时可直接改成回归库种子；本席**未**整理，因超出本席派工范围（只精读机制）。
- **红线未被放宽**：本席全篇**未**建议放宽任何红线；对 SPEC 与红线冲突处（内存态 vs 落盘、无审批位、无心跳），一律**按红线走**。

### 判定词（闭集）

- 本席交件整体判定：**PASS**（SPEC 机制 ≥5 且各有能用/不适用；14 类逐条列全；含「红线覆盖不到」专节；含非零计数；外部事实均带 URL＋访问日期）。
- 两条目标件可达性：Symphony SPEC **可读**（非 BLOCKED）；MAST **可读**（非 BLOCKED）。
