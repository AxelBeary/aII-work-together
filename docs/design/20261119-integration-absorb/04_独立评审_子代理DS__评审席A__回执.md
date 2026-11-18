# 独立评审回执 · 子代理（评审席 A）

> 批次：20261119-integration-absorb｜派工：发牌席｜任务书：02_独立评审任务书
> 通道：宿主子代理（独立上下文），provider opencode-go，model deepseek-v4.1-flash｜名称：reviewer-a
> 口径：只读；回执为子代理收尾原文，未删改。

---

核验已完成，正在撰写评审意见。

## 结论：**REJECT**（方案方向正确，但 P2 的关键前提和四条硬性约束不成立，且缺失项会导致数据丢失）

### 关键发现（按影响排序）

**F1（高｜已读代码，推翻方案断言）「只改三个文件」不成立。** 事实是：`store.mutate(kind, mutatorInPlace)` 接收一个**在内存 JSON 上原地修改**的回调（`store.ts:253-290`），这与 HTTP 的字段补丁完全不同。直接调用它的文件有 **6 个**：`tools.ts`(8)、`execution.ts`(9)、`session-sync.ts`(9)、`scheduler.ts`(10)、`external-sync.ts`(5)、`routes.ts`(11)，共 52 处写入。方案漏掉了 `session-sync.ts`、`scheduler.ts`、`external-sync.ts`（三者合计 24 处写入，占 46%），以及 `storage.ts:187` 上那个 renaming 搬迁事务。`archive-sessions.ts`、`zentao.ts`、`tapd.ts` 也经 store 写入（推断）。真实改动面是 **6–9 个文件 + 一个新适配层**，达到 P2「2–3 周」预估的 2–3 倍。

**F2（高｜已实测）fork 的内容不可重建。** 发布包 `src/` 只有 63 个 `.ts` + 1 个 `index.ts`，**没有 `tsdown.config`、`tsconfig`、锁文件、依赖**（`ls` 已验）；`package.json` 的 `devDependencies` 也不含构建链。交付 `files` 含 `lib/*.map`，可从 map 反推，但这不是「一条命令重建」。先把上游 GitHub 仓 clone 成可构建基线，是 fork 的前置条件。

**F3（高｜已读代码）BD 字段是宿主机级，跨项目冲突。** `LEDGER_SCHEMA_VERSION`/`revision` 是**单文件全局**（`store.ts:2-5`、`ledger.revision += 1`@274），内核若按项目分库，全局 revision 无意义、SSE 单流也不成立；内核 `/api/state` 已被 `_BOARD_LOCK`（单进程 RLock，`server.py:94`）串行化，所有面板写 = 一次内核写 + 一次 SSE，在 UI 批量勾选时会立刻显形。

**F4（高｜已读代码）内核缺 schema 演进。** `storage.py:29` 有 `SCHEMA_VERSION=1`，但 `:204` **只写不读**——全仓无遗留版本校验、无 `VACUUM`/备份接口。方案把它抽成内核且升到 P6 合并，等于在无迁移框架的库上做全机账本。

**F5（中｜已实测）断言核实结果。** ①✅完整 TS（但 F2）；②✅Host 白名单(722)+页面令牌(784)；③✅PATH 无 dsh；④✅`ledger.js:1` 明写 derived/rebuildable；⑤❌；⑥见 A1。

**F6（中｜推断）许可**：repo 已有 `THIRD-PARTY-NOTICES.md`/`ACKNOWLEDGEMENTS.md`，方案还在说「根目录加 NOTICE」——应**改扩现有两文件**，不新建第三份。sentinel-ops 无 LICENSE，按 `AGENTS.md` 纪律必须先由用户签 MIT，否则不能 subtree。

**F7（中｜已读代码）缺 `claim` 的 `if-none-match`**：租约 epoch 只在 CLI 层校验（`cli.py:674-680`），HTTP 面认领无栅栏参数 ⇒ 面板执行器与 CLI 执行器可同时认领。

### A1｜会不会退化成双写？**会。**
「断网 ⇒ 面板转只读」只写在方案里，代码里没有开关。`session-sync.ts:769-829` 会**直接 push 新任务**（成功继任循环），DSH 强绑会话生命周期，一旦网断了只能降级——最可能的实现就是本地缓冲后回放，即双写。推荐改成**结构上不可能**：`TaskStore.persistAtomic` 直接 `throw new ReadOnlyLedger()` 并让存储层不可写（只留 `.dump()` 供迁移），失败即报错。一行保证胜过一条纪律。

### 更好的替代（不采纳方案的「单一内核 + 全面 fork」）
1. **P0 先做只用读取的「总览」和 key 映射，不做写侧打通**（方案 §9 已自承「不做两个账本」）。
2. **用 taskboard 当 DSH 面，但走薄适配，不 fork** ready 就完 —— 关键键：先只实现 **`session-sync` + `scheduler` 两个「别人写入我的账本」的攻击面**，把它们的写入改成调内核 HTTP；`routes/tools` 的读路径和内核对齐即可。UI 侧不动，改动面从 52 处降到约 19 处。
3. **执行器二分**：DSH 会话 = 唯一 UI/调度，CLI 引擎 = 唯一执行，避免同一张卡被两个执行器跑两遍。
4. **不要 CQRS**：内核用 `/api/events?since=seq` 轮询拉取（30–60s），面板本地只做只读缓存；SSE 是 P2 的事，不是 P0。

### 对 P0–P2 的具体修改
- **P0**：`contracts/` 增加**四项**：`idempotency_key`（全局唯一索引）、`lease.epoch` **进 HTTP 契约**（认领/心跳/提交强制带）、`schema_version` 读回 + 拒绝策略、`project_id` 跨项目拒绝（已声明但无实现验证）。验收改用可复跑脚本：kernel `/api/card` 两个 epoch 并发提交，必须**恰好 1 条落库**（非零断言）。
- **P1**：`storage.py` 加 `PRAGMA user_version` 读写 + `VACUUM INTO` 备份/恢复 + 只读降级模式；`server.py` 拆 `_BOARD_LOCK` 为「读锁/写锁」，避免 SSE 持锁。
- **P2**：**先做上游 clone + 构建基线 + 一次性 upstream diff 脚本**（3 天），再做适配器；把「三文件」坐实为 `store.ts` + 新 `kernel-adapter.ts`，其余 5 个 store 调用点改调适配器；`scheduler.ts` 的 10 处写入**直接砍掉**，定位为纯读。

### 只能改一件事
**改方案 §4 的 fork 边界表**：把「只改 3 个文件」改为「6 个写点全部收敛到一个适配器 + 上游可构建基线先行」，并把 P2 从 2–3 周改为 4–6 周。原因：这是唯一一条**如果按原方案实现就会在第二周才发现**、且返工成本最高的错误；其余问题（schema、epoch、锁）都能在 P0/P1 内局部修掉。
