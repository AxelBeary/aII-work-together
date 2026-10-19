# G0–G7 收据闸门设计（抄 Metis 的「完成即证据」）

> 卡片：`C1019-01`　口径：**只抄设计，不抄代码**　立稿：2026-10-19
> 目标：在现有 L1–L3 之外补出**分级机械闸门**，把「完成」从一句自述变成一个**必须交出收据才能通过的状态转移**。
> 本稿只描述设计，⛔ 不含任何对 `tools/board.py` 的改动。

---

## 0 抄谁的、抄了多少（可回读的实证数字）

来源：`docs/research/20261019-agent-board-survey/P4-三个指定产品调查__调研席E__外部公开资料.md`（§3.2 表二 Metis）。

| 项 | 读数 | 出处 |
|---|---|---|
| 目标仓库 | `Wholiver/metis`（MIT，403★） | P4 §3.2 |
| 承载文件 | `src/core/performance-runtime.ts` | 同上 |
| 该文件字节数 | **119,121** | 同上 |
| 关键词命中 | `G0`=**23**、`G7`=**45**、`receipt`=**68**、`exitCode`=**7**、`gate`=**225**、`FALSE_COMPLETION_BLOCKED`=**1** | 同上 |
| 反向对照（尺没坏） | 同文件 `receipt` 非零 ⇒ 计数函数可用 ⇒ 别处报的「0 命中」才可信 | P4 §1 量具对照 |

**为什么值得抄**：Metis 把闸门做到了**机械可判**——README 原文「Even if an LLM outputs “all tests passed”, Metis verifies the exit code, test stdout, and diff boundaries」，缺 receipt 即强制返工。
**为什么只抄一半**：Metis 自评 32 个零分任务里 **27** 个是「写了文件但没通过隐藏评分器」，首因是**治理仪式吃掉产出**。⇒ 本设计的硬约束见 §6。

---

## 1 总表：8 道闸门（G0–G7）

数字口径：闸门总数 **8**；本项目现有机械闸门 **3**（`tools/board.py` 中 `def gate_*` 实测 3 个，文件共 1087 行）；本次**新增 5**（G0／G1／G2／G6／G7）；**复用 3**（G3–G5 ＝ 现有 L1–L3）。

| 闸门 | 名称 | 判的什么 | 谁来判 | 不通过的后果 |
|---|---|---|---|---|
| **G0** | 契约收据 | 卡本身可执行（有目标、有交付物、有必含项） | 机器 | 建卡即拒，卡不进列 |
| **G1** | 认领收据 | 一张卡同一时刻只有一个写者 | 机器（原子） | 认领失败，卡留在原列 |
| **G2** | 心跳收据 | 认领者还活着 | 机器 | 心跳超时＝回收＋留痕 |
| **G3** | 产出收据 | 交付物**存在**且非空（≈ L1） | 机器 | 停在施工中，不进核验中 |
| **G4** | 形制收据 | 交付物**能读**（编码／可解析）（≈ L2） | 机器 | 同上 |
| **G5** | 内容收据 | 派工单声明的必含项**逐条命中**＋有数字（≈ L3） | 机器 | 同上 |
| **G6** | 执行收据 | 引擎**真跑过**（结构化回执＋改动边界） | 机器 | 判 `BLOCKED`，不算跑过 |
| **G7** | 终局收据 | 收据齐＋异会话复核＋人闸 | 机器＋异会话＋人 | `FALSE_COMPLETION_BLOCKED` |

**读法**：G0–G2 管「谁来干、还在不在」，G3–G5 管「东西对不对」，G6 管「你真跑了吗」，G7 管「敢不敢落章」。

---

## 2 逐闸门契约（收据字段 ＋ 判据 ＋ 非零断言）

每道闸门都要**落一份收据文件**（形态见 §4）。判据一律**机器可判**，⛔ 不收自由文本的「我已确认」。

### G0 契约收据（intake）
- 判据：`card.json` 存在、字节 > 0、键数 ≥ 1；`deliverables` 条数 ≥ 1；`accept_patterns` 条数 ≥ 1。
- 非零断言：`deliverables.len() > 0`。
- 现场基准：本卡 `card.json` 键 **15** 个、`deliverables` **1** 条、`accept_patterns` **1** 条。

### G1 认领收据（claim／lease）
- 判据：`lease/` 目录以原子独占方式创建成功（**不是先读后写**）；收据记 `seat`／`engine`／`model`／`epoch`。
- 非零断言：`lease.handles == 1`（同刻两个认领必须**一个成功、一个失败**）。
- 现场基准：`journal.jsonl` 第 2 条即 `claim`（本卡共 **2** 条事件：`created`＋`claim`）。

### G2 心跳收据（liveness）
- 判据：`now - last_heartbeat ≤ TTL`（现有默认 TTL 600s／心跳 120s）。
- 非零断言：`heartbeat_count ≥ 1`；TTL 到期后**必须**产出 `reclaim` 事件（回收可被计数）。
- ⛔ 静默失效禁止：判「超时」必须写出 `reclaim` 事件，⛔ 不得只把状态偷偷挪回去。

### G3 产出收据（artifact，≈ L1）
- 字段：每条交付物记 `path`／`exists`／`bytes`／`sha8`／`mtime`。
- 判据：全部 `exists == true` 且 `bytes > 0`，且 `mtime` 落在认领窗口内。
- 非零断言：`sum(bytes) > 0`。
- 反空跑：**故意塞一个不存在路径，必须被发现缺件**（否则是尺瞎，不是件好）。

### G4 形制收据（conformance，≈ L2）
- 判据：`.json` 可解析；`.md/.txt/.py` 为 UTF-8 且无零字节；落盘件与 `deliverables` 声明**一一对应**（`file_count == declared_count`）。
- 非零断言：`file_count ≥ 1`。

### G5 内容收据（content，≈ L3）
- 判据：`accept_patterns` **逐条**命中（一条一条记 `pattern`／`hit`）。
- 非零断言：交付物文本中 `\d` 命中 ⇒ **必须有数字**（字节／条数／行数皆可）。
- 现场基准：本卡 `accept_patterns` = **1** 条（必含项 `G7`）。

### G6 执行收据（execution）—— 本次新增的关键一道
- 灵感：Metis 的「验退出码／测试 stdout／diff 边界」。
- 字段：`engine`／`session_id`／`duration_ms`／`receipt_kind`／`exit_code`／`diff_fingerprint`／`changed_paths[]`。
- 判据：
  1. **退出码权重 0**——⛔ 不得用 `RC == 0` 判成败；
  2. 必须有**结构化回执**（opencode 看 `type:"text"`、qoderclicn 看 `is_error`）；
  3. `changed_paths[]` 必须**等于本席领地**（领地外改动＝越界，判 `FAIL`）；
  4. `diff_fingerprint` 非空（＝有真实改动边界）。
- 非零断言：`changed_paths.len() ≥ 1` 且 `duration_ms > 0`。

### G7 终局收据（terminal）—— 唯一允许落「完成」的闸门
- 前置：G0–G6 **全部存在且非空**（缺一即不许进 G7）。
- 现场基准：Metis 源码中 `G7` 命中 **45** 次，是出现频率最高的闸门名 ⇒ 它是**汇合点**，不是可有可无的装饰。
- 三条硬判据：
  1. **收据齐**：`receipts_present == 8`（G0–G7 计数）；
  2. **异会话复核**：`reviewer_seat != author_seat`，且复核席**亲跑**过 G3–G5（⛔ 不采信自报）；
  3. **人闸**：卡声明 `human_gate != none` 时，`review` 之前必须有人推进过（人闸令牌⛔ 给 agent）。
- 失败动作：任一不满足 ⇒ 输出 **`FALSE_COMPLETION_BLOCKED`**（Metis 源码中该常量命中 **1** 次），卡退回 `核验中` 或 `施工中`，并写明缺哪一份收据。
- 非零断言：`blocked_probe ≥ 1` —— 必须有一条**故意造假的完成**被它挡下（见 §5）。

---

## 3 与现有实现的映射（⛔ 不推翻，只加细）

| 现有 | 收据闸门 | 关系 |
|---|---|---|
| `gate_l1` | G3 | 一一对应，字段可直接复用（`exists`／`bytes`／`sha8`） |
| `gate_l2` | G4 | 一一对应（UTF-8／零字节／`json.loads`） |
| `gate_l3` | G5 | 一一对应（`accept_patterns` 逐条 ＋ 数字反空跑） |
| 认领 `os.mkdir` | G1／G2 | 现有机制＝判据来源，补「收据落盘」这一层 |
| 复核（异会话）＋人闸 | G7 | 收据化，把「口头合规」变成计数 |
| 引擎回执解析（`tools/engines.py`） | **G6** | 首次把「引擎真跑过」作为**独立闸门**，不再藏在 G3 的 mtime 里 |

⇒ 增量只有 **5 道**（G0／G1／G2／G6／G7），且 3 道（G3–G5）是现有逻辑改名，**不新增施工负担**。

---

## 4 收据的落地形态（统一 schema，一处一文件）

```
board/cards/<id>/evidence/G<n>.json     # 每道闸门一份，append-only 不复用文件名
board/cards/<id>/evidence/G<n>.result   # PASS / FAIL / BLOCKED / 未证（闭集）
```

```json
{
  "gate": "G7",
  "verdict": "FALSE_COMPLETION_BLOCKED",
  "checked_at": "2026-10-19 18:32:31+0800",
  "receipts_present": 7,
  "missing": ["G6"],
  "counters": { "files": 1, "bytes": 0, "patterns_hit": 1 },
  "evidence": ["board/cards/C1019-01/journal.jsonl#seq=2"]
}
```

- 每份收据**必须带 `counters`**（至少 1 个非零数字），否则该收据自身判 `未证`。
- 判定词表＝闭集 `PASS`／`FAIL`／`BLOCKED`／`未证`，冲突取最严（`BLOCKED` > 缺项 > 齐）。

---

## 5 反空跑与反向测试（缺一即本设计作废）

1. **两把尺**：任何「0 命中／全过」必须配一条**必须非零**的对照。
   - 对照样张：Metis 源文件 **119,121** 字节里 `gate` 命中 **225** 次；若计数尺坏，该数会归零。
2. **反向测试（硬要求）**：构造一张**只有「完成」二字、无任何交付物**的假卡，强行 `review` ⇒ **必须**得到 `FALSE_COMPLETION_BLOCKED`。
   - 「没见闸门失败过，就不是闸门」——本设计交工前必须看到这条失败。
3. **越界对照**：G6 的 `changed_paths` 故意放一条领地外路径 ⇒ 必须判 `FAIL`（防止「闸门只查有没有、不查改哪儿」）。
4. **退化可见**：量具读不到文件／收据缺失 ⇒ 显式 `未证`，⛔ 禁止静默转绿。

---

## 6 不抄的部分 ＋ 治理开销红线（对 Metis 失败复盘的正面回应）

- ⛔ **不抄**：多角色人格递归（`spawn_agent` L0→L4／`SpawnGuard`）、每道任务默认全开 performance-governance、模态证据（ffmpeg 抽检）。
- ⛔ **不抄**：把闸门做成**仪式**。Metis 的 32 个零分里 **27** 个首因是「会话文本被 ROADMAP／G2 assurance 占据，模型花回合协调人格而不是读契约」。
- **本设计的自缚三条**（可机器检查）：
  1. 每道闸门**只允许读盘上已有事实**，⛔ 不新增「必须写一段说明」的自由文本项；
  2. **收据总数 ≥ 6 条**才算治理开销超标，需当场砍闸门；
  3. 任何新增闸门必须能点名它防住的事故，名不出来就不加（对齐全局规则 §14）。

---

## 7 未做 / 未证（如实列举）

- 本稿**只有设计**：G0／G1／G2／G6／G7 五道闸门**未落地代码**，未跑过一次真实拒绝路径。
- `G6` 的 `diff_fingerprint` 口径未定（是用 `sha8` 全量还是按 diff 块），**未证**哪种更省往返。
- 人闸令牌（`~/.board-human.tok`）与 G7 的联动**未做**验证。
- 反向测试（§5.2）**尚未执行**——本次只交设计稿，执行归下一张卡。

---

## 8 关键数字速查（验收逐条可查）

- 闸门总数 **8**（G0–G7）；新增 **5**、复用 **3**。
- 现有 `def gate_*` 函数 **3** 个；`tools/board.py` 共 **1087** 行。
- 本卡 `card.json` 键 **15** 个、`deliverables` **1** 条、`accept_patterns` **1** 条、`journal.jsonl` 事件 **2** 条。
- Metis 实证：`performance-runtime.ts` **119,121** 字节；`G7`=**45**、`receipt`=**68**、`gate`=**225**、`exitCode`=**7**、`G0`=**23**、`FALSE_COMPLETION_BLOCKED`=**1**。
- 反面数字：Metis 零分任务 **32** 个，其中 **27** 个「跑了但跑错」（占比 ≈ **84%**）。
