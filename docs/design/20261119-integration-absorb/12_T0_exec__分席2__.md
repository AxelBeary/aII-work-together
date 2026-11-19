# T0 写点清单 · session-sync.ts（9）+ execution.ts（9）= 18 处

> 批次：20261119-integration-absorb｜席位：发牌席亲做（原分席 2 两次失败，零产出）
> 量具：`10_内核写面清单__发牌席__公共量具.md`
> 复跑基线：`grep -c 'store.mutate(' session-sync.ts` = **9**，`execution.ts` = **9**｜实际清点 = **18** ✅

---

## A · session-sync.ts（9 处）

| # | 行 | kind | 实际变更（读闭包体） | 内核命令 | 内核侧校验 | 缺口类型 |
|---|---|---|---|---|---|---|
| S1 | 354 | `task-updated` | 把卡标题同步成真实会话标题（`current.title = normalizedReal`）；仅当不同才写 | **缺口（命令）** | 内核无「改标题」命令 | 命令 |
| S2 | **370** | `task-updated` | 会话一活跃即：`status='in_progress'` + `claimedBy=sessionId` + `claimedAt` + **必要时 push 一条 running execution**。⛔ **全程不认领、不校验租约** | **缺口（命令）** | 内核 `claim` 是唯一置 in_progress 的路径且必写租约；此处绕过 | **命令 + 红线** |
| S3 | **420** | `task-deleted` | 识别到子代理会话后，把自己的卡 `splice` 物理删掉，**返回 `[]`** | #11 删卡 `cmd_rm` | 需 `--yes`；无可逆 | ⚠️ 返回 `[]` 仍真删 |
| S4 | **477** | `task-updated` | turn/start 时：置 in_progress + claimedBy + 补 running execution（与 S2 同型，另一入口） | **缺口（命令）** | 同上，绕过租约 | **命令 + 红线** |
| S5 | 517 | `execution-recorded` | `touchActivity`：更新 running execution 的 `lastActivityAt`（节流 60s） | **缺口（承载位）** | 内核无 executions 结构 | 承载位 |
| S6 | **547** | `task-created` | 「事件里冒出一个会话」时**自动建卡**（已有则复用）；可能补 running execution | #1 建卡 `create_card` | 建卡可映射；但「会话→卡」的自动派生内核没有 | 命令（派生逻辑） |
| S7 | **650** | `task-updated` | 用户消息进来：改标题/描述 + **置 in_progress + claimedBy + 补 running execution** | **缺口（命令）** | 第三次同型绕过 | **命令 + 红线** |
| S8 | 725 | `task-updated` | 同步会话标题（`updatedBy={kind:'user'}`） | **缺口（命令）** | 同 S1 | 命令 |
| S9 | 759 | `execution-recorded` | turn/end 时结算：running→succeeded/failed，`delete claimedBy/claimedAt` | **部分**：#5 `submit` 只走「跑闸门→待验收」 | submit 会跑 L1-L4；此处是「会话结束」而非「交付提交」 | 命令 + 语义 |

### ⚠️ 本节的红线发现（最重要）

**S2 / S4 / S7 三处，是「会话一活跃就把卡置为进行中并写 claimedBy」**，全程：
- ⛔ 不调用任何认领
- ⛔ 不检查租约是否存在
- ⛔ 不检查 epoch

这正是 B2 评审指认的「agent 面无租约写」。**若面板照搬这三处，任何会话只要发一条消息，就能把别人持有的卡抢走并改状态**——租约红线在面板侧完全失效。P2 闸门必须挡住这三处（拒绝数 ≥3）。

---

## B · execution.ts（9 处）

| # | 行 | kind | 实际变更 | 内核命令 | 内核侧校验 | 缺口类型 |
|---|---|---|---|---|---|---|
| E1 | 312 | `execution-recorded` | `lastActivityAt` 节流更新（`ACTIVITY_PERSIST_MS` 内直接 `return undefined`） | 缺口（承载位） | 无 executions | 承载位 |
| E2 | 524 | `execution-recorded` | `patchExecution`：对 running execution `Object.assign(execution, patch)` | 缺口（承载位） | 无 executions | 承载位 |
| E3 | **580** | `execution-recorded` | **开跑闸**（复合原子）：夹在同一个闭包里的有——依赖门禁、scheduled 只接 todo、comment 唤必须 in_review、**已在跑/已 claimedBy 则拒**、全册 running 数上限。通过后：开 execution + 置 in_progress + 写 claimedBy | **部分**：#2 `claim` 只覆盖「独占」 | claim 的 epoch CAS 可复用；但依赖门/容量上限/trigger 分支内核元 | 命令 |
| E4 | 831 | `execution-recorded` | 绑定 `sessionId` 到 execution；写 `autoReuseSessionId`；`target.claimedBy = sessionId` | 缺口（承载位 + 命令） | 无 executions；直接写 claimedBy 绕过 claim | 承载位 + 红线 |
| E5 | **935** | `execution-recorded` | **结算**（最大闭包）：running→outcome；失败则 `status='todo'` + 清 claim + **push 系统评论**；成功则清 claim；cron 任务按 `periodicCompletion` 派生后继卡或回 todo | **缺口（命令 + 承载位）** | 内核 `review` 只管「核验中→完成/返工」；无「执行失败自动退回」 | 命令 + 承载位 |
| E6 | 1107 | `task-updated` | worktree 分支名变更后回写 `target.branch` / `target.branches[repo]` | 缺口（承载位） | 内核无 branch 字段 | 承载位 |
| E7 | 1230 | `execution-recorded` | **宿主重启恢复**：把所有 running 且未被接管的 execution 标 failed（`interrupted by host restart`），in_progress 的卡退回 todo 并清 claim | **缺口（命令）** | 内核无「崩溃恢复」命令；`doctor` 只清残留租约 | 命令 |
| E8 | 1332 | `comment-added` | 标记评论已投递（`deliveredAt`）+ 可选系统评论 | 缺口（承载位） | 无 comments | 承载位 |
| E9 | 1487 | `execution-recorded` | `revertProgress`：in_progress→todo 并清 claim | **部分**：#4 `release` 只放租约，不改状态 | release 不清 claimedBy 语义 | 命令 |

---

## 缺口汇总（18 处）

| 缺口 | 类型 | 涉及 | 影响 |
|---|---|---|---|
| G9 | **绕过租约置 in_progress** | S2 S4 S7 E4 | **红线**：面板侧可抢卡、改状态。必须挡 |
| G10 | **executions 承载位** | S5 E1 E2 E4 E5 E8 | 执行记录、活动时间、报告全丢 |
| G11 | 改标题/描述 | S1 S7 S8 | 会话标题同步失效（可降级为不写） |
| G12 | 执行失败自动退回 | E5 E7 E9 | 失败卡滞留 in_progress，需人手清 |
| G13 | 会话→卡自动派生 | S6 | 「一个会话自动出现在板上」这一能力归谁 |
| G14 | 分支/镜像元数据 | E6 | worktree 分支名对不上 |
| G15 | 依赖门 / 容量上限 / trigger 分支 | E3 | 内核 claim 不含这些策略 |

---

## 三条行为特性（决定适配器怎么写）

1. **返回 `undefined` 与返回 `[]` 语义不同**：`undefined` = 中止不写；`[]` = **确实写了但不报 touched**。按返回 diff 必丢（S3 就是真删却返回 `[]`）。
2. **复合原子 E3**：门禁 + 开执行 + 改状态在同一闭包，拆开会出现「开了执行但没置 in_progress」的中间态。
3. **崩溃恢复 E7 是全局扫描**：它遍历全部卡，不适合映射成单卡命令，应作为内核自己的启动动作。

---

## 反空跑自检

| 项 | session-sync.ts | execution.ts |
|---|---|---|
| 复跑命令 | `grep -c 'store.mutate(' session-sync.ts` | `grep -c 'store.mutate(' execution.ts` |
| 期望 | 9 | 9 |
| 实际清点 | **9** ✅ | **9** ✅ |
| 缺口 | 8 | 9 |

**红线计数（可直接做 P2 断言）**：绕过租约置 in_progress = **4 处**（S2:370、S4:477、S7:650、E4:831）。
断言：`agent 面无租约写 in_progress 必须被拒`，拒绝计数 **≥4**。
