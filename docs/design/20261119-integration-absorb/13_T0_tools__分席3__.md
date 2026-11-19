# T0 写点清单 · tools.ts（8）+ scheduler.ts（10）+ external-sync.ts（5）= 23 处

> 批次：20261119-integration-absorb｜席位：发牌席亲做（原分席 3 两次失败，零产出）
> 量具：`10_内核写面清单__发牌席__公共量具.md`
> 复跑基线：tools=**8**、scheduler=**10**、external-sync=**5**｜实际清点 = **23** ✅

---

## A · tools.ts（8 处）— 10 个 `taskboard_*` agent 工具的写实现

| # | 行 | kind | 实际变更 | 内核命令 | 内核侧校验 | 缺口类型 |
|---|---|---|---|---|---|---|
| T1 | 666 | `task-created` | `taskboard_create`：校验依赖后 push 新卡 | **#1 建卡** | 卡号白名单 + 主键撞键 | — |
| T2 | 722 | `task-updated` | `taskboard_update`：`versionGuard` + 改 title/description/prompt/urgency/blocked/blockedBy/waitingForHuman/permission，`version+1` | **缺口（命令）** | 内核无改卡命令；`ifVersion` 无对应 CAS | 命令 |
| T3 | 782 | `task-moved` | `taskboard_move`：`versionGuard` + 转移白名单 + **代码级闸：`to==='done'` 一律拒** + 独占持有校验 | **部分**：#2 claim / #5 submit / #7 review | 内核同样挡 agent 到 done（review 需异会话）；但「移动」不是一条命令 | 命令 |
| T4 | 880 | `comment-added` | `taskboard_comment_add`：push comment + `version+1`（无 ifVersion，append 语义） | **缺口（承载位）** | 无 comments | 承载位 |
| T5 | 949 | `task-deleted` | `taskboard_delete`：软删除 `trashedAt` + 清 claim + 禁「有 running 执行时删」 | **缺口（命令+承载位）** | 无回收站概念 | 命令+承载位 |
| T6 | 1014 | `task-updated` | `taskboard_checklist`：add/check/uncheck 验收清单，带证据 note | **缺口（承载位）** | 无 checklist | 承载位 |
| T7 | 1120 | `execution-recorded` | `taskboard_execution_report` **路径1**：把报告挂到本会话的 running execution | **缺口（承载位）** | 无 executions | 承载位 |
| T8 | 1137 | `execution-recorded` | 同工具**路径2**：回填到本会话最近一条 succeeded execution（复审回填） | **缺口（承载位）** | 同上 | 承载位 |

> 这是唯一一处「一个工具两次 mutate」：路径1 找不到 running 才落路径2。

---

## B · scheduler.ts（10 处）— v2.1 决定**全部删除**

| # | 行 | 实际变更 | 删掉后原本负责什么 | 内核侧由谁接 |
|---|---|---|---|---|
| C1 | 223 | `skipDependencyBlocked`：清 dispatching/queued + 写系统评论（依赖未满足跳过） | 依赖门禁的可观测性 | 内核 `withholding()` 已有依赖判断；需补一条事件 |
| C2 | 255 | `queueCron`：算下一次 cron + 写 queuedRunAt | **cron 排期核心** | 内核 `schedules` 表 + `tick` |
| C3 | 271 | `queueRunAt`：一次性定时消费 runAt | 一次性定时 | 内核 `tick` |
| C4 | 287 | `expireQueued`：超时丢弃队列项 + 评论 | 队列保鲜 | 内核 `tick` 的过期策略 |
| C5 | 315 | `clearQueue`：清全部排队（手动清队列） | 用户「清队列」按钮 | 内核需一条 `board unschedule` |
| C6 | 340 | `markDispatched`：标记已派发 | 派发确认 | 内核 `tick` 内部状态 |
| C7 | 353 | `restoreQueued`：派发被拒时还回队列 | 失败回队 | 内核 `tick` 重试 |
| C8 | 367 | `consumeRunAt`：消费一次性触发（含错过窗口补评论） | 一次性防重跑 | 内核 `tick` |
| C9 | 383 | `advanceAndMark`：cron 推进 + 死 cron 停用 + 评论 | cron 生命周期 | 内核 `tick` |
| C10 | 417 | （`clearQueue` 内第二次 mutate，逐卡清） | 同上 | 同上 |

### ⚠️ 删掉 scheduler.ts 的真实代价（必须写进方案）

这 10 处**不是简单定时器**，它承载了 5 个隐性语义：
1. **一次性任务被消费后归一为 `mode='claim'`**（#95 修复）——否则卡变成「有定时壳但无触发」的幽灵。
2. **错过窗口要留系统评论**——⛔ 不许静默丢。
3. **死 cron 自动停用 + 评论**——防空转。
4. **依赖未满足时窗口作废、不自动唤醒**。
5. **派发被拒要还回队列**（不是丢弃）。

⇒ **内核 `tick` 必须把这 5 条语义原样实现，否则删 scheduler 就是功能倒退。** 这是 P1 的必做项，不是可选项。

---

## C · external-sync.ts（5 处）— v2.1 决定**整块摘除**

| # | 行 | 实际变更 | 摘除后切断什么 |
|---|---|---|---|
| X1 | 57 | 旧格式元数据一次性迁移到 `externalSync` | 历史配置迁移 |
| X2 | 110 | 清空 ignored/links（重置连接） | 「重置同步」按钮 |
| X3 | 119 | **字段冲突裁决**：接受外部值写入 task 并清冲突标记 | 禅道/TAPD 字段冲突处理 |
| X4 | 218 | **同步主循环**：按外部条目建卡/更新/忽略，写 links/lastResult | 禅道/TAPD 全量同步 |
| X5 | 287 | 同步失败时写 lastError（`return []`） | 失败可见性 |

### 摘除影响面

- **被切断的能力**：禅道 / TAPD 双向同步、按处理人导入、冲突保护、定时同步、连接配置管理。
- **用户可见变化**：面板「外部同步」整块消失；已有 `externalSync` 字段进归档不再读。
- **谁来接**（建议）：P4 之后作为**内核的一个 source 适配器**重做——外部条目 → `board add --source=zentao --source-ref=...`，走同一条幂等键，⛔ 不让面板直写账本。
- **不可逆点**：X4 会**自动建卡**。摘除前必须确认现有 `externalSync.links` 已被导出，否则「哪些卡来自外部」这一事实会丢。

---

## 缺口汇总（23 处）

| 缺口 | 类型 | 涉及 | 备注 |
|---|---|---|---|
| G16 | 改卡字段（含 versionGuard） | T2 | 同 G1（routes #2），**合并处理** |
| G17 | 移动卡（含 done 拒写） | T3 | 同 G2 |
| G18 | comments | T4 | 同 G5 承载位 |
| G19 | checklist | T6 | 新增：验收清单 |
| G20 | executions（含 report 双路径） | T7 T8 | 同 G10 |
| G21 | 调度 5 条隐性语义 | C1–C10 | **P1 必做**，非可选 |
| G22 | 外部同步 | X1–X5 | 已决定摘除；需先导出 links |

---

## 反空跑自检

| 项 | tools | scheduler | external-sync |
|---|---|---|---|
| 复跑 | `grep -c 'store.mutate(' tools.ts` | `scheduler.ts` | `external-sync.ts` |
| 期望 | 8 | 10 | 5 |
| 实际 | **8** ✅ | **10** ✅ | **5** ✅ |

合计 **23**；全库 52 处已全部清点（11 + 18 + 23 = 52）✅

---

## 跨文件补充发现

1. **`return []` 写点全库统计（复跑核准）**：routes.ts:1096、:1529；session-sync.ts:426；external-sync.ts:60、:113、:290 = **6 处**。按返回值 diff 会全部静默丢失。
   （初稿写「7 处」，把 external-sync 记成 4 处，复跑 `grep -n 'return \[\]'` 实为 3 处 —— **已更正**。）
2. **`versionGuard` / `ifVersion` 出现在**：routes#2/#3/#4/#8、tools T2/T3/T5。内核契约必须带 `version` 与 `if_version`。
3. **两次 mutate 的工具只有 1 个**（T7→T8）。
