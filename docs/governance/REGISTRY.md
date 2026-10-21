# REGISTRY.md — 产出物登记册

> 规矩：新增／变更产出物就登一行。**收件只登存在性，⛔ 判合格**；核验另派复核席。
> 状态词（闭集）：`已交（待验）`／`已验（PASS）`／`打回`／`进行中`。

| 日期 | 产出物 | 路径 | 席号 | 状态 | 验证证据 |
|---|---|---|---|---|---|
| 2026-10-19 | 项目纪律入口 | `AGENTS.md` | 发牌席 | 已交（待验） | 由用户与本项目后续会话使用检验 |
| 2026-10-19 | 人话定位 | `README.md` | 发牌席 | 已交（待验） | 同上 |
| 2026-10-19 | 拍板台账 | `docs/governance/DECISIONS.md` | 发牌席 | 已交（待验） | D-001 待用户拍板 |
| 2026-10-19 | 环境事实 | `docs/governance/ENVIRONMENT.md` | 发牌席 | 已交（待验） | 每条附可复跑命令 |
| 2026-10-19 | 派工度量台账 | `docs/governance/DELEGATION-LEDGER.md` | 发牌席 | 已交（待验） | 本轮 3 席在册 |
| 2026-10-19 | 会话交接块 | `docs/governance/HANDOFF.md` | 发牌席 | 已交（待验） | 收工时更新 |
| 2026-10-19 | 调研批次目录＋派工单 | `docs/research/20261019-agent-board-survey/` | 发牌席 | 已验（PASS） | 派工总单＋3 派工单＋3 交件＋抽验记录＋合并摘要齐全 |
| 2026-10-19 | P1 开源横评（17 产品） | `docs/research/20261019-agent-board-survey/P1-开源agent看板横评__调研席A__外部公开资料.md` | 调研席 A | 已交（部分抽验） | 20,863 字节；抽验 2 条属实（Symphony/KittyClaw）；余 13 项未回源 |
| 2026-10-19 | P2 协议与底座（16 条） | `docs/research/20261019-agent-board-survey/P2-协议与底座__调研席B__外部公开资料.md` | 调研席 B | 已交（1 处已更正） | 22,300 字节；Codex 链接 404 已修；MAST 逐字属实 |
| 2026-10-19 | P3 本机资产与约束 | `docs/research/20261019-agent-board-survey/P3-本机可复用资产与约束__调研席C__本机实测.md` | 调研席 C | 已交（部分抽验） | 24,494 字节；AGENTS.md 三段行号锚点核对一致 |
| 2026-10-19 | 发牌席抽验记录 | `docs/research/20261019-agent-board-survey/99_发牌席抽验记录.md` | 发牌席 | 已验（PASS） | 5 条抽验：4 属实、1 链接错 |
| 2026-10-19 | 合并摘要（人话版） | `docs/research/20261019-agent-board-survey/98_合并摘要__发牌席__人话版.md` | 发牌席 | 已验（PASS） | 三席结论合并＋许可红线＋下一步 |
| 2026-10-19 | 架构期派工单（总单＋D1/D2/D3） | `docs/design/20261019-architecture-deepdive/` | 发牌席 | 已交（待验） | 受 D-002 约束：本批不写代码 |
| 2026-10-19 | D3 Symphony 规格＋MAST 失效映射 | `docs/research/20261019-architecture-deepdive/D3-Symphony规格与MAST失效映射__调研席D3__外部公开资料.md` | 调研席 D3 | 已交（待抽验） | 38,102 字节；sha256 前 8 = `4F60F5C1`；自报 8 机制／14 失效／13 输入 已核 |
| 2026-10-19 | D1 卡片数据模型与状态机 | `docs/design/20261019-architecture-deepdive/D1-卡片数据模型与状态机__设计席D1__设计稿.md` | 设计席 D1 | 进行中（后台） | 文件已在盘 46,833 字节；**未回执、未亲验** |
| 2026-10-19 | D2 租约与验收判据 | `docs/design/20261019-architecture-deepdive/D2-租约与验收判据__设计席D2__设计稿.md` | 设计席 D2 | 已验（PASS） | 45,375 字节／518 行／MD5 前 8 = `08FC240D`，三项与自报全一致；退出码权重 0 已写死 |
| 2026-10-19 | D1 卡片数据模型与状态机 | `docs/design/20261019-architecture-deepdive/D1-卡片数据模型与状态机__设计席D1__设计稿.md` | 设计席 D1 | 已验（PASS） | 61,114 字节／593 行／MD5 前 8 = `94F919BE`；34 字段／17 边／12 不变量／2 冲突 全核一致；反空跑对照 0 命中 |
| 2026-10-19 | P4 三个指定产品调查 | `docs/research/20261019-agent-board-survey/P4-三个指定产品调查__调研席E__外部公开资料.md` | 调研席 E | 已验（PASS） | 42,003 字节／MD5 `3C98A6C3`；四仓库 star／许可经 GitHub API 逐个复核一致；「毕方 0 命中」对照＝BitFun 22 命中（尺活） |
| 2026-10-19 | 架构总图（合并稿） | `docs/design/20261019-architecture-deepdive/98_架构总图__发牌席__合并稿.md` | 发牌席 | 已验（PASS） | 三席结论合并＋红线真实强度表＋4 条待拍板 |
| 2026-10-19 | **看板工具本体** | `tools/board.py` | 发牌席 | **已验（PASS）** | 单文件零依赖；闭环实测通过；四条防线均有拒绝路径实测（见下） |
| 2026-10-19 | **引擎适配层** | `tools/engines.py` | 发牌席 | **已验（PASS）** | 四引擎统一调用＋逐家结构化回执解析；opencode/qoderclicn 实测 ok=True |
| 2026-10-19 | **自主编排器** | `tools/orchestrator.py` | 发牌席 | **已验（PASS）** | **端到端实跑成功**：自动认领→执行 26s→3158B→L1-L3 过→异会话复核→完成 |
| 2026-10-19 | 使用说明 | `docs/usage.md` | 发牌席 | 已交 | 一条命令覆盖主流程 |
| 2026-10-19 | 看板页（自动生成） | `board/board.html` | 发牌席 | 已生成 | 30s 自动刷新；含引擎/模型/思考强度徽标＋AI 发布标记 |

| 2026-10-19 | 回归库（15 条＋反向测试） | `tests/run_regression.py`＋`tests/regression/cases.json` | 发牌席 | **已验（PASS）** | 15 条全过；`--break` 注入故障被 R07/R08 抓住 |
| 2026-10-19 | 断点续跑 | `tools/resume.py`＋`tests/test_resume.py` | 发牌席 | **已验（PASS）** | 3 条判据 + 反空跑计数=2 |
| 2026-10-19 | 专家团／子代理／会话续接 | `tools/experts.py`＋`tools/subagents.py`＋`engines.py` | 发牌席 | **已验（PASS）** | 真辩论 2 独立会话；真跑 --agent 3 档；两个引擎会话续接实测 |

### 补齐四项后的新 bug（2026-10-19，均从测试里抓出）

| # | Bug | 抓法 | 修复 |
|---|---|---|---|
| 6 | L3 只查 `.md/.txt`，`.py` 永远判不中 | G1 submit 误判 | 扩展到 .py/.json/.yaml/.html/.css/.js/.ts |
| 7 | 机器闸有问题仍可给 PASS | 手工复核时发现 | `review` 前查最后一次 verify 的 problems |
| 8 | 反空跑只在有 `--accept` 时才执行 | 回归库 R08 | 改为无条件；纯文字稿需 `allow_no_numbers=true` |

| 2026-10-19 | **多项目支持** | `tools/projects.py` | 发牌席 | **已验（PASS）** | 注册表只存位置；零配置自动登记；两项目实测隔离 |
| 2026-10-19 | **跨项目总览页** | `tools/render.py` → `~/.aII-work-together/overview.html` | 发牌席 | **已验（PASS）** | 每项目一行色条 + 卡片数，链接到各自看板 |
| 2026-10-19 | **worktree 并行** | `tools/parallel.py` | 发牌席 | **已验（PASS）** | 2 卡并行 14s 完成；冲突实测判 BLOCKED 未覆盖 |
| 2026-10-19 | 回归库扩到 18 条 | `tests/run_regression.py` | 发牌席 | **已验（PASS）** | 新增多项目隔离／默认值继承／并行冲突 3 条 |
| 2026-10-20 | **用量统计** | `board.py cost` ＋ `engines.py` 用量解析 | 发牌席 | **已验（PASS）** | 实测入 26,738／出 521／缓存 47,232／$0.0045；拿不到标「未知」 |
| 2026-10-20 | **项目工作区** | `projects.py` workspace 字段 | 发牌席 | **已验（PASS）** | agent 干活、交付物、worktree 全部以工作区为基准 |
| 2026-10-20 | **opus 设计评审** | `docs/design/20261020-opus-review/OPUS-设计评审__外部专家__claude-opus-5-5.md` | 外部专家 | 已收（3 条已复现） | 15,095 字节；3 个缺陷经本席复现确认属实 |
| 2026-10-20 | **修 3 个真缺陷** | `board.py`／`orchestrator.py`／`parallel.py` | 发牌席 | **已验（PASS）** | 状态转移守卫／执行期心跳／基线冲突判据；回归 18→23 条全过 |
| 2026-10-20 | **拍板收件箱** | `cli.py inbox` | 发牌席 | **已验（PASS）** | 实测：人话摘要 + 建议 + 可复制命令；**驳回理由实测传回下一轮并生效** |
| 2026-10-20 | **体检命令** | `cli.py doctor [--fix]` | 发牌席 | **已验（PASS）** | 查残留租约／孤立 worktree／断链／丢件／注册表失效 |
| 2026-10-20 | **一条命令自检** | `tools/check.py` | 发牌席 | **已验（PASS）** | 7 道闸一次跑完；实测全绿 |
| 2026-10-20 | **代码拆分** | `board.py`（核心）＋`cli.py`（命令层） | 发牌席 | **已验（PASS）** | 拆分后 23 条回归全过 + 端到端真跑通过 |

### 编排器端到端实测（2026-10-19，C1019-01，含专家团）

| 阶段 | 实测 |
|---|---|
| 找活 | 按规格精确匹配 |
| 认领 | 固定名目录原子创建成功 |
| 执行 | opencode + deepseek，61 秒 |
| 产出 | `board/artifacts/g0-g7-design.md`，11,153 字节，sha8 `c4b15141` |
| 提交 | L1-L3 全过 |
| 复核 | **专家团 security + skeptic 双视角**，均 PASS |
| 终态 | 转「拍板中」→ 人 approve → **完成**，7 条事件全可追溯 |
| 产出质量 | 引用 Metis 源码真实读数（G7=45、receipt=68、119,121 字节），与本席先前核对一致 |

### 专家团抓出的 5 个真 bug 及修复（2026-10-19，重要）

用户质疑「子代理／专家团／会话交流都有吗」后派专家团审自己的代码，**抓出 5 个真 bug**，全部已修并复测：

| # | Bug | 抓获方式 | 修复 | 复测 |
|---|---|---|---|---|
| 1 | **红线③被破**：租约目录名带 uuid ⇒ `os.mkdir` 永不撞名，互斥退化为先读后写 | 12 线程并发实测 | 改**固定名** `lease/active/holder` | 12 线程仅 1 成功、1 个租约 ✅ |
| 2 | **返工死锁**：FAIL 后状态回「进行中」，而认领只收「待认领/阻塞」⇒ 卡永久卡死 | 专家团静态审 | 新增 `待返工` 状态 | FAIL → 待返工 → 可重新认领 ✅ |
| 3 | **人闸可空文件绕过**：只判 `token.exists()`，0 字节也放行 | 专家团实跑 | 校验非空 + ≥16 字符 + sha256 登记 | 空 token 被拒 ✅ |
| 4 | **journal 可整份重写**：手写 6 行即伪造「完成」，audit 报干净 | 专家团实跑 | 加**哈希链**（prev/hash） | 插入伪造行即断链被抓 ✅ |
| 5 | **编排器写死 `L1/L2/L3=True`**：机器闸变盖章 | 专家团读码 | 改为真调 `gate_l1/l2/l3` | 未过则判 FAIL 返工 ✅ |

> **教训**：这 5 个 bug 我自己「跑通了」时一个都没发现。**「端到端跑通」不等于「防线有效」**——必须有人从攻击者视角专门去找反例。这正是专家团存在的理由。

### `tools/board.py` 实测记录（2026-10-19）

| 防线 | 实测动作 | 结果 |
|---|---|---|
| 红线③ 原子认领 | worker-1 认领后，worker-2 抢同一张卡 | **被拒**：「当前状态「进行中」，不可认领」 |
| 红线① 异会话复核 | worker-1 自己复核自己的卡 | **被拒**：「复核席不得是执行席本人」 |
| 红线① 反空跑 | 复核不带 `--evidence` | **被拒**（argparse 强制必填） |
| 红线② 人拍板位 | 无 token 调 `human` | **被拒**：「缺人令牌」 |
| 红线② agent 越权 | 卡在「拍板中」时 agent 调 `review` | **被拒**：「不可复核」 |
| 审计（反向测试） | 手写 journal 伪造 review 事件 | **被抓**：`audit` 退出码 2，报「复核记录缺 evidence 字段 ← 疑似绕过 CLI」 |
| 完整闭环 | 认领→提交→复核→人拍板 | **通过**，卡进「完成」，`audit` 干净 |

### 多项目压测新增（2026-10-20）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 多项目压测（9 条） | `tests/test_multiproject.py` | PASS（9 of 9） | 12 个项目 / 36 张卡 / 8 线程并发登记一条不丢 / 工作区还原 |
| 界面并发隔离（真 bug 回归） | `tests/test_ui_concurrency.py` | PASS | 两项目并发 25+25 张，4 个读线程，零串号；**拆除锁则转红** |
| 注册表目录可隔离 | `tools/projects.py`（`ABOARD_REGISTRY_DIR`） | 已实现 | 测试用沙箱注册表，不碰真实 `~/.aII-work-together` |
| 建卡原子拒绝重号 | `tools/board.py`（`create_card()`） | 已修 | 重号抛 `ValueError`，不再静默覆盖 |
| 界面并发串号 | `tools/server.py`（`_BOARD_LOCK`） | 已修 | 见 ENVIRONMENT.md E-24 |
| 汇总不改调用方工作区 | `tools/projects.py`（`project_summary()`） | 已修 | P9 用例；反向测试确认能抓 |
| 汇总缓存原子写 | `tools/projects.py` | 已修 | 临时文件 + `os.replace` |

`tools/check.py` 现为 **9 道闸**（新增「多项目」「并发隔离」）。

### 全部项目总览 + 接口契约（2026-10-20）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 全部项目总览 | `tools/server.py`（`__all__`）+ `tools/ui.html` | 已实现 | 下拉框「全部项目」；每张卡带项目名；每列最多画 60 张 |
| 首页不再重放全部卡 | `tools/server.py`（`api_state`） | 已简化 | 张数改由前端从卡片列表自己数，后端零重放 |
| 一份日志只读一次 | `tools/board.py`（`replay(cid, events=...)`） | 已优化 | 列表页每卡的日志扫描从 2 遍降到 1 遍 |
| 托盘状态显示 | `tray/BoardTray.cs`（`ShowStatus`） | 已修 | 改读 `/api/cards`；以前读 `/api/state` 恒显示 0 张 |
| 接口形状契约（14 条） | `tests/test_ui_api.py` | PASS | 含「总览不串项目」「重号被拒且原卡不变」 |
| 规模基准 | `tests/bench_scale.py` | 工具 | 20 项目 × 15 卡最慢 34ms；重规模需机器空闲时手跑 |
| 界面 JS 语法闸 | `tools/check.py`（有 node 才查） | 已加 | 整页脚本一个错字就白屏，必须机器查 |
| 使用说明补充 | `docs/怎么用.md` | 已补 | 托盘 + 网页看板的鼠标操作 |

`tools/check.py` 现为 **11 道闸**（新增「接口契约」「界面语法」）。

### 连接复用与热路径（2026-10-20）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 固定线程池（线程/连接复用） | `tools/server.py`（`PoolHTTPServer`） | 已实现 | 40 项目/1200 卡：汇总冷缓存 14→4ms，看板列表 29→15ms；`--workers 0` 可 A/B |
| 切项目不重复 set_root | `tools/server.py`（`_switch`） | 已实现 | 省掉每请求 mkdir + 迁移检查（与数据量无关的纯税） |
| 汇总缓存可主动失效 | `projects.invalidate_summary_cache()` | 已实现 | 建卡/拍板后项目张数立刻更新，不再滞后 15 秒 |
| 注册表目录可隔离 | `projects.py`（`ABOARD_REGISTRY_DIR`） | 已实现 | 测试用沙箱注册表，不碰真实 `~/.aII-work-together` |
| 汇总还原工作区 + 缓存原子写 | `projects.py`（`project_summary`） | 已修 | P9 用例；临时文件 + `os.replace`，避免读到半截 JSON |
| 规模压测接入自检 | `tools/check.py --perf` | 已接 | 默认轻量 20×15（重规模见 E-25 §3 的自我约束） |

坑与口径：ENVIRONMENT.md **E-26**。

### 点对点评审（2026-10-20）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 评审内核（并行、异构、防改文件） | `tools/consult.py` | 已实现 | 两席不同提供商实测：opus 30.1s / deepseek 28.4s，各自给出 9–10 条意见 |
| 命令 `board consult` | `tools/cli.py` | 已实现 | `--by` 支持 `seat:engine:model:effort`，模型名带 `/` 不切坏 |
| 编排器自动链路 | `tools/orchestrator.py`（`run --consult`） | 已实现 | 端到端：初翻 46s → 两席判 needs-work → 修改轮 29s → 过闸 → 复核 → done |
| 评审席只准看 | `consult.snapshot/check_and_restore` | 已实现 | 改动即按原字节恢复 + `consult_violation` 事件；测试 C3 正反都验 |
| 空材料拒绝 | `consult.consult` | 已实现 | 路径写错直接拒（测试 C5），不再空评出一份"看着正常"的结论 |
| 留痕 | 卡片事件 + `board/evidence/<卡号>/consult-*.md` | 已实现 | 实测 2 席 → 2 份证据文件，源文件未被改动 |
| 确定性闸门 | `tests/test_consult.py`（5 条） | PASS | 已接入 `check.py`（现 **12 道闸**） |
| 使用文档 | `docs/点对点评审.md` + `docs/怎么用.md` 末尾 | 已写 | 含「为什么不建聊天室」与已知问题 |

已知问题：反空跑闸（必须包含数字）把统计注释逼进译文正文，见 ENVIRONMENT.md **E-27**。

### 评审闭环 + 图标 + 快捷方式（2026-10-20 收工批次）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 评审席记账 | `tools/consult.py` | 已实现 | 每席一条 `usage` 事件（`phase: consult` / `consult-verify`），成本表不再漏半张 |
| 改后核对 | `consult.verify_fix` + `parse_verify` | 已实现 | 实测 b1 6/6、b2 11/12，剩 1 条；糊话记为「未知」不当 0（测试 C7） |
| 卡片自定义字段不丢 | `tools/storage.py`（`meta` 列 + 老库补列） | 已修 | 测试 C9；反向测试停用后 C9 变红（`consult_files 丢了：None`） |
| 评审席可带角度 | `--consult "...@native,...@faithful"` | 已实现 | 实测 opus 看母语读感、deepseek 逐句对照，两席结论各自成立 |
| 看板显示评审 | `tools/server.py`＋`tools/ui.html` | 已实现 | 卡片标签 `评审 2` / `未改 1`；详情一行摘要；契约测试已钉 `consult` 字段 |
| 反空跑闸改口径 | `tools/board.py`（`gate_l3`/`MIN_NONSPACE`） | 已改（D-012） | 回归 24 条全过；旧件留档 `gate-archive/` |
| 代码画图标 | `tools/make_icon.py` | 已实现 | 纯标准库；`System.Drawing.Icon` 解析成功、PNG 256×256 ARGB |
| 桌面快捷方式 | `看板.lnk` → `open-board.cmd` | 已创建 | 回读验证目标/工作区/图标/最小化；**尚未被人双击** |
| 网页图标 | `/favicon.ico`、`/assets/board.png` | 已实现 | HTTP 200，5293 / 2288 字节，首页已引用 |
| 复核席跑错目录（整盘搜的根因） | `tools/orchestrator.py` | 已修 | 复核/专家团改用卡片工作区；提示词禁止整盘搜索 |

规模：`tools/`＋`tests/` 共 24 个 py 文件 ≈ 295 KB；闸门 **12 道**、回归 **24 条**。

### 跨会话留言 + 桌面壳 + 内置终端（2026-10-20 第二轮收工批次）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 留言内核（append-only + 唤醒语义） | `tools/messages.py` | 已实现 | 闸 16 条；HELD 退出码 2 实测；「已回复不重发」实测挡住第二次投递 |
| 唤醒工作者 | `tools/msgwake.py` | 已实现 | 真跑：续 opencode 会话 → 回答写成 `#6`/`#7`（重复唤醒的教训见 E-29） |
| 命令 `board msg` | `tools/cli.py`（29 子命令） | 已实现 | `send/ls/inbox/ack/thread/wake/states` 七动作全通 |
| 留言存储三表 | `tools/storage.py`（`messages`/`msg_reads`/`msg_wakes`） | 已实现 | **无 UPDATE/DELETE 接口**；已读另记一表（append-only） |
| 开工收信 | `tools/orchestrator.py`（`cmd_run` 开头） | 已实现 | 沙箱实测：`📬 开工收信：1 条给 auto-worker（共 1 条，已标已读）` |
| 留言闸 | `tests/test_messages.py`（16 条） | PASS | 已接入 `check.py`（现 **13 道闸**） |
| 留言接口 | `server.py`（`/api/messages`、`/api/messages/ack`）＋ `ui.html`（留言抽屉） | 已实现 | 界面契约测试 25 条全过（含 unread 计数与 ack 归零） |
| 内置终端（白名单） | `tools/term.py` | 已实现 | `board stats` 输出可取回、退出码 0；`del` 与 `\|` 均被拒（人话报错） |
| 终端接口 | `server.py`（`/api/term/run`、`/api/term/tail`、`/api/term/stop`） | 已实现 | 行号单调 1..8；一次只许跑一条 |
| 界面终端抽屉 | `tools/ui.html`（底部 dock，`Ctrl+\`` 开合） | 已实现 | 界面语法闸 15,744 字符过；页面内 5 列 + 抽屉均在 |
| **桌面壳** | `shell/BoardShell.cs` + `shell/build.cmd` | 已实现 | `--selftest` PASS（真起内核、DOM 回读 `cols=5 term=true msg=true`）；`--shot` 34.9 KB；真窗截图 45.8 KB |
| 壳的 vendored 依赖 | `shell/*.dll`（WebView2 1.0.4258.31） | 已入库 | 682/38/190 KB；来源与许可见 `shell/VENDOR.md` |
| 一键启动改走壳 | `open-board.cmd`、`tray/BoardTray.cs` | 已改 | 壳在就用壳，没有退回浏览器 |
| 坑记录 | `docs/governance/ENVIRONMENT.md` | 已写 | **E-28**（WebView2 五坑）、**E-29**（唤醒两点） |
| 拍板 | `docs/governance/DECISIONS.md` | 已记 | **D-014** 留言、**D-015** 桌面壳 |

规模：`tools/`＋`tests/` 共 **28** 个 py 文件；闸门 **13 道**、回归 **24 条**、留言 16 条、界面契约 25 条。
未验：壳的托盘菜单/最小化行为**只能人手点**；窗口与终端抽屉的**人眼观感**已出图但未由用户确认。

### 图标第二版 + 启动提速（2026-10-20，用户报「图标不好看」「双击要 4 秒」）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 图标 v2（渐变底＋三列＋白卡打勾；≤32px 自动简化成三柱） | `tools/make_icon.py` → `assets/board.ico`（7 尺寸） | 已实现 | 用户已认可「挺不错」；`System.Drawing.Icon` 解析 32×32 通过 |
| 图标候选对照图 | `assets/icon-preview.png`（三种风格 × 四种尺寸 × 深/浅底） | 已生成 | A 纯白卡 / B 白卡打勾（**采用**）/ C 卡片高光 |
| 启动：窗口不再等后端 | `shell/BoardShell.cs`（`StartBackendAsync` + `MaybeNavigate` + 启动遮罩） | 已改 | 日志：`window shown +131ms` |
| 启动：探活改 TCP | `shell/BoardShell.cs`、`tray/BoardTray.cs` | 已改 | `HttpClient` 首次请求白等 1.5s（E-33）；改后 `server spawned +548ms` |
| 启动实测 | `board/shell.log` | 已测 | 窗口 **0.13s**、页面 **1.33s**（修前 3–4s） |

坑记 **E-33**。

### A 批 · 红线与假防线（2026-10-20 第二轮，Q1 复核后）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 租约回收竞态（致命） | `tools/storage.py`（`try_claim` 同事务 CAS、`reclaim` 带版本条件） | 已修 | 12 线程抢超时卡：**4/12 → 1/12**；新鲜租约 0 人抢到 |
| 回收留痕统一 | `storage.reclaim` + `board._reclaim_lease` + `board.claim(on_reclaim)` | 已修 | 回收后 `replay` 能看到 `reclaim` 事件 |
| `submit` 必须持租约 | `tools/cli.py` `cmd_submit` 起手 `guard_holder` | 已修 | 删掉租约行后 submit → 退出码 1「你没有活跃租约」 |
| `board reclaim` 走库 | `tools/cli.py` `cmd_reclaim` | 已修 | 输出 `回收 1 of 1`；没东西时明说「无可回收」 |
| 终端白名单不可绕过 | `tools/term.py`（任何位置出现 `rm`/`human` 一律拒） | 已修 | 4 种绕法全拒；`board -p demo stats` 仍放行 |
| 旧布局迁移函数真的存在 | `tools/storage.py` `migrate_from_files` | 已补 | 老布局 fixture 首条命令不崩、跑两次不重复迁 |
| L1 真查 mtime | `tools/board.py` `gate_l1` | 已修 | 旧文件提交 → 报「旧文件，比认领早 N 分钟」；真改过 → 过 |
| 新闸 | `tests/test_lease_race.py`（6 组 14 条） | PASS | 闸门 13 → **14** |
| 壳的「后端旧版」告警 | `shell/BoardShell.cs`（正则解析 + 解析失败报未知） | 已修 | 编译过、`--selftest` PASS |

坑记 **E-34**。规模：闸门 **14 道**、`tools/`＋`tests/` 共 **29** 个 py 文件。

### B 批 · 预算 / 错误分级 / 依赖 / 拍板 diff / 提醒（2026-10-20 第三段，D-016／D-017）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 单卡预算与时长上限（P0） | `storage.py` 三列（老库自动补列）、`board.budget_status`、`orchestrator` 四处刹车 | 已做 | 超预算 `$0.7500/$0.50` 认领被拒；超时长 11/10 分钟被拒；没超的卡能认领 |
| 放宽只能人 | `cli.cmd_budget`（`--seat human`） | 已做 | 执行席放宽 → 退出码 1；human 放宽 → 0；收款收紧执行席可以做 |
| 错误分级 | `engines.classify`（9 类样本）、`orchestrator.run_engine_guarded` | 已做 | 可重试试 3 次成功；不可重试 1 次停；unknown 1 次停 |
| 卡间依赖 | `storage` `blocked_by` 列、`board.withholding`、编排器 `pick` 跳过 | 已做 | 依赖未完成认领被拒；编排器「跳过 CDN-1」且不处理 |
| 拍板 diff | `board.diff_vs_baseline`＋认领时 `baseline` 快照；`board show`／详情页 | 已做 | 详情页「这次改了什么 27B → 169B」 |
| 提醒 | `server.api_alert`（纯文本行）、壳 `WatchCards`＋`--notify-test`＋任务栏闪烁 | 已做 | 气泡实测弹出；`needs=C1\|failed=C3` |
| 新闸 | `tests/test_budget_deps.py`（6 组 24 条） | PASS | 闸门 14 → **15**；子命令 27 → **28** |
| 界面 | 新建对话框预算两栏、卡片预算/依赖标签、diff 列表、深链接 `?open=`／`?new=1` | 已做 | `board/shots/20261020-b2-list.png`、`-card.png`、`-new.png` |

坑记 **E-35**。规模：闸门 **16 道**、`tools/`＋`tests/` 共 **31** 个 py 文件。

### C 批 · 界面列布局 ＋ Q1 剩余五条（2026-10-20 第四段，D-018）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 只画有卡的列 ＋ 顶部状态筛选 | `tools/ui.html`（`FILTER`／`.chip`／`render`） | 已做 | `board/shots/20261020-b3-list.png`：三列都在窗口内，无横向滚动 |
| 壳自检同步 | `shell/BoardShell.cs`（列数 ≥1 ＋ 筛选条存在） | PASS | `cols:1 filt:true … SELFTEST PASS` |
| 项目默认预算 | `cli.cmd_project default --max-cost/--max-minutes`、`server._budget_field` | 已做 | 继承 1.50/20 分钟；单卡覆盖；`none` 取消 |
| 提醒声 | `shell/BoardShell.cs` `AlertBalloon`（`SystemSounds.Asterisk`→`MessageBeep`） | 已做 | `--notify-test`：`balloon+sound shown at +919ms` |
| Q1 #6 托盘不读管道 | `tray/BoardTray.cs` `Hook`（后台吸流到 `board/ui-server.log`） | 已修 | 托盘 `--selftest` PASS |
| Q1 #9 `msg --json --wake` 夹人话 | `cli.cmd_msg`（整体一个 JSON，唤醒放 `wake` 字段） | 已修 | 留言闸 17 条（新增严格 json.loads 断言） |
| Q1 #10 托盘 UI 线程等 HTTP | `tray.ShowStatus` 移到后台线程 + `OnUI` 回 UI | 已修 | 编译通过；托盘 `--selftest` PASS |
| Q1 #11 `_WriteTx.__enter__` 漏连接 | `tools/storage.py`（BEGIN 失败先 close 再抛） | 已修 | 全量闸绿 |
| Q1 #12 托盘端口不透传 | `tray.OpenBoard` 传 `--port=`／`--project=` | 已修 | 代码级；未起可见托盘验证 |

### D 批 · 多选批量 ＋ 端到端实跑验收（2026-10-21，D-019）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 多选（勾选框 ＋ 底部操作栏） | `tools/ui.html`（`SEL`／`.pick`／`.selbar`） | 已做 | 壳自检真点击：`sel:2 bar:true hidden0:true n:"2"` |
| 批量跑（只跑选中的） | `orchestrator run --cards`、`server.api_bulk` | 已做 | `--cards` 过滤在 `pick()` 里；非法动作/空选择被拒 |
| 批量取消（要人令牌） | `server.api_bulk` action=cancel | 已做 | 无令牌 403；有令牌只动选中那张；留痕 actor=human |
| 端到端实跑（人肉验收） | 临时项目 `%TEMP%\opencode\hello-run` | PASS | 认领→opencode 8s→L1-L3→异会话复核→完成；`out/hello.txt` 177B；$0.0058 |

规模：闸门 **16 道**、`tools/`＋`tests/` 共 **31** 个 py 文件；预算与依赖闸 **37 条**；留言闸 **17 条**；安全反向 **21 条**；子命令 **29 条**。

### F · 找卡与僵尸卡可见（2026-10-21，用户「优先功能 实用 性能」）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 顶部搜卡（卡号/标题/目标，输入即过滤，Esc 清空） | `ui.html` `SEARCH`／`matchesSearch` | 已做 | 壳自检真输入：`before:5 after:1 back:5` |
| 每张卡显示「最后活动」＋列内按活动倒序（超 12 小时标黄＝僵尸） | `server._card_view.last_at`、`ui.html` `ago()` | 已做 | `/api/cards` 契约新增 `last_at>0`；截图 `20261021-search.png` |
| 性能基线（不做投机优化） | `tests/bench_scale.py` | 实测 | 20 项目×15 卡：首页 23ms／列表 5ms／详情 12ms，远低于 800ms 流畅线 |

> 性能这条**没有改代码**：实测没有瓶颈，加缓存属投机优化（用户「没用的东西别做」）。

### G · 卡内实时输出 ＋ 列内排序（2026-10-21，用户「这两个比较值得做」）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 每张卡一份运行日志（线程局部，不串卡） | `orchestrator._LOG_CTX` / `open_card_log`、`board/evidence/<卡>/run.log` | 已做 | 实跑 C2：8 行 357B，跑完最后两行是汇总且**没写进卡日志** |
| 卡片详情里看实时输出（1.5s 增量轮询，跑完停） | `server.api_card_log`（`since` 字节增量）、`ui.html` `pollCardLog` | 已做 | t+4s：`size=105 running=true`；跑完：`size=357 running=false`；截图 `20261021-live-log.png` |
| 列内排序（最近活动／花费／时长／卡号，记忆选择） | `ui.html` `SORT` / `sortList` / `#sort` | 已做 | 壳自检切三种排序：`opts:4 before:5 after:5 after2:5`（不丢卡） |
| 卡面露出花费与时长 | `ui.html` 标签 | 已做 | 没设上限时也显示「0.3 分」，否则按花费/时长排序看不出凭据 |
| 长字段折叠（凭据 619 字 → 3 行 + 展开按钮） | `ui.html` `kvHtml` / `.foldbtn` | 已做 | 壳自检：`longBtn:true longFull:true shortNoBtn:true`；截图 `20261021-fold.png` |
| 窄窗口标题栏换行（加排序框后 892px 会挤） | `ui.html` `header{flex-wrap:wrap}` | 已做 | 自检新增「页面不许横向滚动」断言（含打开详情时）：`W:892 S:892` |

### H · 外部评审核验 ＋ audit 去死判据（2026-10-21，D-021）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 外部评审记录（含逐条回源核验表） | `docs/research/20261021-peer-review-lead/外部评审记录__青芽季遇领队__只读.md` | 已记录 | 三条主张逐条核对，1 条修正（见下） |
| audit 租约判据改读库 ＋ 新增「状态/租约互证」 | `tools/cli.py::cmd_audit` | 已修 | 反向：删 `leases` 行 → `exit=2`「进行中 但库里没有租约」；还回租约 → `exit=0`（同一张卡红绿翻转） |
| audit 输出带分母（防 0 命中假绿） | 同上 | 已做 | 真仓：`✓ 审计通过：5 张卡全查` |
| 文档口径对齐 3 处 | `README.md`／`AGENTS.md`／`tools/check.py` 注释 | 已改 | 「有数字」→机器测；`os.mkdir`→SQLite 主键＋CAS；五道闸→15 道 |

> 对方说「audit 跳过只在库里的卡」不成立（`CardRef.is_dir()` 查的是库）；但「租约判据读不存在的目录」成立且已修。

### I · 安全与缺陷只读扫描（2026-10-21，子代理派工）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 安全 + 缺陷扫描报告（23 条：P0×1／P1×6／P2×11／P3×5） | `docs/research/20261021-security-scan/安全与缺陷扫描__审计席__只读.md`（**本地，暂不入库**） | 已交，待修 | 报告 49 941 字节；基线 `f38fb7c`；主代理亲验 F-01～F-07（HTTP 无来源校验／卡号直通路径／终端黑名单可绕／`.cmd` 注入／id 未转义／FK 级联雷／`--seat human` 绕预算） |
| 派工度量 | `docs/governance/DELEGATION-LEDGER.md` 末行 | 已记 | 内派 1 路，往返 1，返工 0 |

> 报告不入公开库的理由：本项目多数用户会把它跑在本机，报告等于一张「本地攻击面地图」；修完再决定是否随版本发布。

### J · 安全扫描 23 条全部落地（2026-10-21，D-022）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| HTTP 面加固（会话令牌 + Host 校验 + CSP + body 上限 + 读超时 + 池满 503） | `tools/server.py`、`tools/ui.html` | 已修 | 无令牌 POST→403；`Host: evil`→403；正常 GET→200 |
| 卡号白名单（create／card_dir／rm／parallel／HTTP 五处） | `tools/board.py`、`cli.py`、`server.py`、`parallel.py` | 已修 | `..\..\pwn` 建卡/删卡/日志接口全拒 |
| 终端改白名单（board 只读子命令 + 仅 check.py/test_*.py） | `tools/term.py` | 已修 | `py cli.py rm`／`board publish`／`doctor --fix` 全拒 |
| `.cmd` 参数元字符 fail-closed | `tools/engines.py` | 已修 | `--model x&calc` 被拒 |
| 卡片写入改 UPSERT（不再 REPLACE 清历史）＋建卡原子判重 | `tools/storage.py`、`board.py` | 已修 | 改卡后事件流条数不变；同号建卡被拒 |
| 预算刹车要人令牌（`--seat human` 不再算数） | `tools/cli.py` | 已修 | 隔离 HOME 下被拒；有令牌通过 |
| 人令牌登记移到家目录 + 首次必须 `token --init` | `tools/cli.py`、`server.py` | 已修 | 旧 `board/.human-token.sha` 自动迁移，实测 verify=True |
| 交付物路径必须落在工作区内 | `tools/board.py`、`parallel.py`、`consult.py` | 已修 | 绝对路径／`..` 被拒 |
| 租约 TTL 改单调时钟（`leases.at_mono`） | `tools/storage.py` | 已修 | 租约竞态闸 14 条全过 |
| 续跑 REVIEW 独立复核入口 `review_only` | `tools/orchestrator.py`、`resume.py` | 已修 | 断点续跑闸全过 |
| 壳：scheme 白名单 / `--url` 仅回环 / python 解析 | `shell/BoardShell.cs` | 已修 | `--selftest` PASS |
| 第 16 道闸「安全反向」 | `tests/test_security.py`、`tools/check.py` | 已加 | 8 组 21 条，每条配非零对照 |

> 16 道闸全绿；壳与托盘重编译后 `--selftest` 均 PASS。

### K · 外问升级：证据层级 ＋ 结构触发 ＋ 预注册实验（2026-10-21，D-023）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 证据层级（VERIFIED／AUDITED-UNGROUNDED／UNVERIFIED） | `tools/board.py::evidence_tier`、`cli.show`、`/api/card`、`ui.html` | 已做 | 6 条反向断言：仅复核表态≠已验证；机器闸全过才 VERIFIED |
| 外问升级按结构触发（复核失败 2 次换模型） | `tools/orchestrator.py::pick_model`、CLI `--escalate-model/--escalate-after` | 已做 | 未到阈值不升级／到阈值升级／没配零变化 |
| 预注册实验设计（四臂、60 题、隐藏检查器、McNemar） | `docs/research/20261021-escalation-experiment/实验设计__外问升级触发__预注册.md` | **未跑** | 文档含四条弃用条件与 $10 预算上限 |

> 实验结论（H1/H2/H3）一条都还没有；⛔ 不得在对外材料里引用「级联更便宜」这类结论。

### L · 学界现状调研（2026-10-21，调研席，外部检索）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 30 篇带链接的文献卡片（级联/路由、触发信号、验证边界、基准校准） | `docs/research/20261021-escalation-lit/学界现状__调研席__外部检索.md`（70 KB） | 已交 | 主代理抽验 3 条链接（FrugalGPT／Efficient Benchmarking／Self-Verification Limitations）均 HTTP 200 且摘要与卡片一致 |
| 关键数字表 27 行（逐行标口径与出处） | 同文件 §4 | 已交 | 口径分歧已写明：只有两篇用真实美元，其余用相对算力/调用次数；无一篇用墙钟 |
| 五条可搬做法 | 同文件 §5 | 已交 | ①筛题（30–70% 通过率带）②成本双记 ③结构触发＋单报误升级率 ④加 V 臂（自检不升级）⑤天花板校准题 |

> 影响：实验设计里「加难度」一条已改成「筛题」；V 臂列入下一轮（用于把「自检的成本」与「升级的收益」拆开）。

### M · 编排调研 ＋ epoch 栅栏 ＋ 筛题（2026-10-21 晚，D-024）

| 产出物 | 路径 | 状态 | 证据 |
|---|---|---|---|
| 编排现状调研（34 卡、8 节、69 链接） | `docs/research/20261021-orchestration-lit/编排现状__调研席__外部检索.md`（64 KB） | 已交 | 主代理核：34 张卡、8 节；卡片要求「API/字段名必须来自官方文档」，并点名 3 条未证 |
| 租约 epoch 升为真栅栏 | `tools/storage.py`（`touch_lease` CAS）／`tools/board.py`（`heartbeat`）／`tools/cli.py`（`guard_holder`、`--epoch`）／`tools/orchestrator.py` | 已交 | `test_lease_race.py::test_epoch_fence` 五条（含「当代心跳照常通过」对照），16 闸全绿 |
| audit 增「换代后仍有旧代写入」判据 | `tools/cli.py` | 已交 | 同一闸内跑；误报面为零（旧卡无 epoch 字段时跳过） |
| 题库扩到 23 题（+8） | `exp/hard2.py`（6 机械精确）、`exp/hard3.py`（2 长上下文） | 已交 | 两把尺 23/23（正解绿、错解红） |
| 筛题结果 | `docs/research/20261021-escalation-experiment/筛题结果__20261021.md` | 已交 | 弱模型 23/23 全对 ⇒ 该题族饱和；并记两次「我写错期望、模型是对的」 |
| 五臂 runner／筛题器／聚合器／操作手册 | `exp/run_experiment.py`、`screen.py`、`analyze.py`、`实验操作手册.md` | 已交 | `--validate` 23/23；V/M/S 在 23 题上的运行记录见 `exp/runs/saturated-VMS.jsonl` |

> ⚠️ 本批**没有**产生任何实验结论：23 题对弱模型全饱和，H1/H2/H3 仍未检验。
