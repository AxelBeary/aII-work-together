# contracts/ · P0 契约（v1 草案）

> 状态：**草案，未冻结**。按 15 稿丙案，承载位已从「新增」改为「复用 events 表」。

## 三份契约

| 文件 | 管什么 | 冻结条件 |
|---|---|---|
| `task-envelope-v1.schema.json` | 任务外壳 + `seq`/`version` 双游标 | T0 缺口报告（已完成）+ 丙案承载决议 |
| `event-v1.schema.json` | append-only 事件 + 哈希链 + 幂等键 + 全部折叠源 | 同上 |

## 核心设计（15 稿丙案）

**唯一真相是事件流，不是字段。**

| 数据 | 存在哪 | 怎么读 |
|---|---|---|
| 卡字段（title/state/...） | `cards` 表 | 直接读 |
| comments | **events** | 折叠 `comment` / `comment-delivered` |
| executions | **events** | 折叠 `execution-open/activity/close` |
| checklist | **events** | 折叠 `checklist-*` |
| 软删除 | **events** | 折叠 `trash` / `restore` |
| 调度 | **events** | `schedule-queued/consumed/skipped` |

⛔ **禁止把 append 型数据塞进 `cards.meta`**：那是整表 JSON 读改写，并发会覆盖（`storage.py:245-271` 已核实）。

## 两个游标的分工

| 游标 | 管什么 | 用途 |
|---|---|---|
| `version` | 卡字段并发 | `if_version` 乐观锁（对齐 taskboard 的 `versionGuard`） |
| `seq` | 事件流位置 | `?since=seq` 增量拉取；面板轮询、SSE、适配器同步共用 |

## AI 友好性四要求（15 稿 §4）

1. **结构化错误**：`{ok:false, error:{code,message,hint,retryable}}`，`code` 闭集 8 个。
2. **`--json` 全覆盖**：每个写命令都要，失败也输出 JSON（⛔ 不 die 打断）。
3. **`next` 字段**：写命令的 JSON 固定带下一步命令，agent 不用读文档猜。
4. **`board schema --json`**：命令/参数/状态机自描述，agent 可自举。

## 未做

- `conformance.py`（T3）尚未写。
- 事件折叠逻辑（comments/executions/checklist 的 fold）尚未实现——那是 P1。
