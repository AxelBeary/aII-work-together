# DELEGATION-LEDGER.md — 派工度量台账

> 规矩：**每次派工收口追加一行**；月初月末各出一次趋势表。
> 字段：日期 / 任务类型 / 口径（内派·外包＋引擎名）/ 结果（成·假绿·败）/ 往返数 / 返工数 / 断点续跑触发否。
> **假绿定义**：自报成功但交付件未落盘，或被写入凭证（mtime／sha256／git diff）证伪。

| 日期 | 任务类型 | 口径 | 结果 | 往返数 | 返工数 | 断点续跑 | 备注 |
|---|---|---|---|---|---|---|---|
| 2026-10-19 | 建制（治理层落盘） | 主代理亲做 | 成 | 0 | 0 | 否 | D-000 |
| 2026-10-19 | 外部调研·开源横评 | 内派（宿主子代理 general ×1，模型 opencode-go/gpt-6-luna） | 成 | 1 | 0 | 否 | P1；17 产品；抽验 4 条属实 |
| 2026-10-19 | 外部调研·协议底座 | 内派（宿主子代理 general ×1，模型 opencode-go/gpt-6-luna） | 成（1 处链接错已修） | 1 | 1 | 否 | P2；16 条；正文 Codex 链接 404 → 已更正 |
| 2026-10-19 | 本机资产侦察 | 内派（宿主子代理 general ×1，模型 opencode-go/gpt-6-luna） | 成 | 1 | 0 | 否 | P3；4 引擎/18 映射/17 约束 |
| 2026-10-19 | 首轮派工失败（免费模型被 IP 封禁） | 内派（宿主子代理 general ×3，默认免费模型） | 败 | 1 | 0 | 否 | 3 席全失败：`abusive traffic from this IP`；改指定付费模型后一次通过 |
| 2026-10-19 | 架构期派工失败（3 次尝试） | 内派（子代理 ×3，gpt-6-luna → claude-sonnet-5-5 → opencode/deepseek） | 败 | 3 | 0 | 否 | 依次报 `region not supported`／`当前地区暂不支持`／`Insufficient account funds` |
| 2026-10-19 | 架构期（D1 卡片模型与状态机） | 内派（宿主子代理 general ×1，`opencode-go/deepseek-v4.1-flash`） | 成 | 1 | 0 | 否 | 61,114 字节；亲验 5 项计数全对；**主动报 2 条冲突而非放宽红线** |
| 2026-10-19 | 架构期（D2 租约与验收判据） | 内派（宿主子代理 general ×1，`opencode-go/deepseek-v4.1-flash`） | 成 | 1 | 0 | 否 | 45,375 字节；亲验字节/MD5/行数三项全一致 |
| 2026-10-19 | 外部调研·三个指定产品 | 内派（宿主子代理 general ×1，`opencode-go/deepseek-v4.1-flash`） | 成 | 1 | 0 | 否 | P4；四仓库 API 读数逐个复核一致；「毕方」未能证实，如实报 |
| 2026-10-19 | 架构期（D3 Symphony 规格＋MAST 映射） | 内派（宿主子代理 general ×1，`opencode-go/deepseek-v4.1-flash`） | 成 | 1 | 0 | 否 | 38,102 字节；自报计数已核（8 机制／14 失效／13 输入） |

## 引擎与模型表现观察（首批，供月度趋势表）

- **免费模型池**：3/3 全败，网络侧 IP 封禁（**非账号问题**）。**教训：派工前先确认模型可用，别用默认池裸派。**
- **`opencode-go/gpt-6-luna`**：首轮 3/3 成功（1 席有 1 处链接错）；同日稍后 3/3 被区域封禁。**⇒ 可用性会漂，不可当稳态。**
- **`opencode-go/deepseek-v4.1-flash`**（＝主代理同款）：本批 3/3 通过。**当前推荐默认。**
- 一句话：**要派子代理，一律显式钉 `opencode-go/deepseek-v4.1-flash`**（见 `ENVIRONMENT.md` E-08）。

## 待建（治理缺口，按全局规则 §1）

- **最小回归库**：新项目首次派工前应建「≥10 条/技能」。本轮为**纯调研（无技能产物、无闸门口径变更）**，暂不适用；**首个施工批次开工前**必须补建最小回归库（≥10 条），并把反向测试一起做掉（故意改坏一处必须被抓住）。
- **月度趋势表**：派工满 1 个月或满 20 行后首次生成。
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 部分 0/1 | 1 | 0 | 否 | C1019-01=awaiting-human |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 成 2/2 | 2 | 0 | 否 | G2=done；G3=done |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 成 2/2 | 2 | 0 | 否 | P2=done；P1=done |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 成 1/2 | 2 | 0 | 否 | C1=conflict；C2=done |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 成 1/1 | 1 | 0 | 否 | COST1=done |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 部分 0/2 | 2 | 0 | 否 | RT1=error: name 'threading' is not defined；RT2=error: name 'threading' is not defined |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 成 2/2 | 2 | 0 | 否 | RT1=done；RT2=done |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 部分 0/1 | 1 | 0 | 否 | INBOX1=awaiting-human |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 部分 0/1 | 1 | 0 | 否 | INBOX1=awaiting-human |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 成 1/1 | 1 | 0 | 否 | SMOKE1=done |
| 2026-10-19 | 自动编排 | 内派（opencode/opencode-go/deepseek-v4.1-flash） | 成 1/1 | 1 | 0 | 否 | SQ1=done |
