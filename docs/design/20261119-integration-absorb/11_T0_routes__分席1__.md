# T0 写点清单 · routes.ts（11 处）

> 批次：20261119-integration-absorb｜席位：发牌席（原定分席 1，因分席失败由发牌席亲做）
> 量具：`10_内核写面清单__发牌席__公共量具.md`
> 复跑基线：`grep -c 'store.mutate(' routes.ts` = **11**｜实际清点 = **11** ✅

---

## 逐点表（四列）

| # | 行 | kind | 实际变更（读闭包体） | 内核命令（A表） | 内核侧校验 | 缺口类型 |
|---|---|---|---|---|---|---|
| 1 | 812 | `task-created` | 校验 `blockedBy` 依赖后 `ledger.tasks.push(task)`；返回 `[task]` | **#1 建卡** `create_card` | 卡号白名单 + 主键撞键即拒 | — |
| 2 | 846 | `task-updated` | 改 title/description/prompt/urgency/workspaceId/blockedBy/blocked/execution + `version+1`；`ifVersion` 冲突校验 | **缺口（命令）** | 内核无「改卡字段」命令；只有 `budget` 改预算 | 命令 |
| 3 | 937 | `task-moved` | 用户点「移动」：`canTransition` + 依赖门 + `syncClaim`（用户移动**不记 holder**，离开 in_progress 即释放持有） | **部分**：agent 认领→#2 `claim`；其余转移无命令 | `claim` 有 epoch CAS；但「用户移动」在内核里不存在 | 命令 |
| 4 | 970 | `task-moved` | 用户点「退回」：in_review→todo **并同闭包 push 一条 comment**（原子） | **部分**：#7 `review --verdict fail` 只走「核验中→待返工」 | review 需 `--evidence` 且复核席≠执行席；与「用户退回」语义不同 | 命令 + 语义 |
| 5 | 993 | `comment-added` | push comment，`version+1` | **缺口（承载位）** | 内核无 comments 存储（C 表无此列/表） | 承载位 |
| 6 | 1022 | `comment-added` | 同上（comment-run 路径，`if` 内条件写） | **缺口（承载位）** | 同上 | 承载位 |
| 7 | 1093 | `task-deleted` | **purge 物理删除**：`ledger.tasks.filter(...)`，**返回 `[]`** | **#11 删卡** `cmd_rm --yes` | 需 `--yes`；不可逆动作 | ⚠️ 返回 `[]` 但真实删除 |
| 8 | 1103 | `task-deleted` | **软删除**：`trashedAt` + 删 `claimedBy/claimedAt` + `blocked=false` | **缺口（命令）** | 内核无「软删除/回收站」概念 | 命令 + 承载位 |
| 9 | 1214 | `comment-added` | worktree 合并后写**系统评论**（systemKey/systemParams/systemRows），`threadId:'host'`；返回 `[next]` | **缺口（承载位）** | 无 comments；且『系统评论』这一概念内核没有 | 承载位 |
| 10 | 1428 | `ledger-replaced` | **一次闭包改三块**：`ledger.tasks`（整册换/合并）+ `ledger.externalSync` + `ledger.settings`；replace 模式先拒「有运行中执行」 | **缺口（命令 + 承载位）** | 内核无整册导入；无 externalSync/settings 承载 | 命令 + 承载位 |
| 11 | 1527 | `settings-updated` | `ledger.settings = next`，**返回 `[]`** | **缺口（承载位）** | 内核无 board settings 承载位 | 承载位 |

---

## 缺口汇总

| # | 缺口 | 类型 | 影响面 | 建议处置 |
|---|---|---|---|---|
| G1 | 改卡字段（title/goal/priority/execution） | 命令 | 面板「编辑任务」整个不可用 | 内核加 `board edit`（白名单字段 + 版本号 CAS） |
| G2 | 用户直接移动卡（不经认领） | 命令 | 面板拖拽/按钮全不可用 | 内核加 `board move --by human`，与 agent 认领分开记 `actor` |
| G3 | 用户退回 + 附带评论（原子） | 命令 + 语义 | 退回意见丢失或非原子 | 并入 `board review --actor user`，意见写 `cards.meta` |
| G4 | 评论（含系统评论） | 承载位 | 交接说明、diff 讨论全丢 | 先落 `cards.meta.comments[]`，后续再拆表 |
| G5 | 软删除 / 回收站 | 命令 + 承载位 | 删了不可恢复 | `cards.meta.trashedAt` + `board rm --soft` |
| G6 | 整册导入/导出（ledger-replaced） | 命令 + 承载位 | 迁移、备份恢复不可用 | P1 的 import/export 命令，按 `(source, legacy_id)` 幂等 |
| G7 | board settings | 承载位 | 面板设置无处存 | `projects.defaults` 已有先例，扩为 `settings` JSON |
| G8 | externalSync | 承载位 | 禅道/TAPD 同步 | **v2.1 已决定摘除**，不补 |

---

## 三条必须记下的行为特性（会决定适配器怎么写）

1. **「返回 `[]` 仍提交」共 3 处**（#7 purge、#11 settings、以及 execution 侧）——适配器若按返回值 diff，这些写会**静默丢失**。必须整 draft 深比较。
2. **复合原子闭包 2 处**（#4 退回+评论、#10 三块同改）——拆成多条内核命令会丢原子性。
3. **`ifVersion` 冲突校验**（#2/#3/#4/#8）——内核侧要有对应的版本号 CAS，否则并发下后写覆盖先写。

---

## 反空跑自检

| 项 | 值 |
|---|---|
| 复跑命令 | `grep -c 'store.mutate(' routes.ts` |
| 期望行数 | 11 |
| 实际清点 | **11** ✅ |
| 缺口条数 | **8**（其中「纯命令」2、「纯承载位」4、「命令+承载位」2） |
| 「缺口=0」声明 | 无（本文件缺口 8 条，均为实证） |

---

## 复跑证据

```bash
cd "C:/Users/qly19/.dsh/profiles/desktop/node_modules/dsh-taskboard/src/host"
grep -c 'store.mutate(' routes.ts        # 11
grep -n 'store.mutate(' routes.ts        # 812 846 937 970 993 1022 1093 1103 1214 1428 1527
```
