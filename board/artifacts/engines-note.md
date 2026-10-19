# 引擎可用性说明（四引擎无头调用实测）

> 依据：`docs/governance/ENVIRONMENT.md` E-11／E-12（本项目现场复算，取证 2026-10-19）。
> 口径：**只写实测结论**；未跑过的写「未测」，不写「理论上可以」。
> 本说明覆盖 **4** 个引擎（外加 1 个未安装的参照项 claude），共 **2** 条铁律。

## 一 结论速览

| 引擎 | 版本 | 无头可用？ | 关键读数 |
|---|---|---|---|
| opencode | v2.0.32 | 可用（**必须显式指定模型**） | RC=0，stdout 出现 `type:"text"` |
| qoderclicn | 1.1.68 | 可用 | RC=0，`is_error:false`，回包含 `session_id`／`duration_ms`／`modelUsage` |
| codex | 0.153.4 | 当前不可用 | 走 RTOC 中转返回 `401 Unauthorized: Invalid token`，JSONL 末尾 `turn.failed` |
| hermes | v0.22.0 | 未测 | 本轮未验证，**不得当作可用** |
| claude | — | 未安装 | — |

统计：4 个引擎中**可用 2 个**、不可用 1 个、未测 1 个。

## 二 逐引擎说明

### 1 opencode（v2.0.32）— 可用，但有一个硬前提

- 最小可用式：`opencode run --format json --model opencode-go/deepseek-v4.1-flash "只回复两个字：可用"`
- ⛔ **不加 `--model` 会走免费池**：返回 `FreeTierError`（提示该 IP 有滥用流量），RC=1，而错误只出现在 stdout JSON 的 `type:"error"` 里，stderr 为空。
- ⇒ 编排器**必须给每个 opencode 任务钉死模型**，默认 `opencode-go/deepseek-v4.1-flash`。

### 2 qoderclicn（1.1.68）— 可用

- 最小可用式：`qoderclicn -p "只回复两个字：可用" -o json --no-session-persistence`
- 实测回执：RC=0，`is_error:false`，并带 `session_id`／`duration_ms`／`modelUsage` 三项。
- ⛔ 但 **`subtype:"success"` 不能单独信**（会谎报），必须看 `is_error`；同时核 `modelUsage` 防坏模型静默回落。
- ⛔ 无头下写权限可能**静默被拒**：即便 `is_error:false`，仍要回到盘上查文件是否真落了。

### 3 codex（0.153.4）— 当前不可用

- 调用形态：`"提示词" | codex exec --ephemeral --skip-git-repo-check --sandbox read-only -c approval_policy=never --json -`
- 现状：走 RTOC 中转，返回 `401 Unauthorized: Invalid token`（`api.rtoc.cc/v1/responses`），JSONL 末尾 `turn.failed`。
- 处置：**先修 RTOC 钥匙**再复测；修好前不得排进任何派工。

### 4 hermes（v0.22.0）— 未测

- 本轮**未验证**，既不算可用也不算不可用。真要用前先按最小式现场验一次并回写 E-11。

## 三 两条铁律（跨引擎通用）

1. **退出码不可信**：4 个引擎里没有一家能用 RC 判成败——opencode 免费池失败 RC=1 但错误藏在 stdout JSON；qoderclicn 的 `subtype` 会谎报 success。
2. **判成败必须解析结构化回执**（opencode 看 `type:"text"`／qoderclicn 看 `is_error`），并且**回执只算自证**：最终以盘上证据为准。

## 四 未做 / 未证

- hermes 未测（0 次调用）；codex 未修钥匙，可用性未证。
- 四引擎的版本号取自 2026-10-19 单次实测，版本漂移后判据可能失效，需按 E-11 复算。
