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
| 2026-10-19 | **跨项目总览页** | `tools/render.py` → `~/.allworktogether/overview.html` | 发牌席 | **已验（PASS）** | 每项目一行色条 + 卡片数，链接到各自看板 |
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
| 注册表目录可隔离 | `tools/projects.py`（`ABOARD_REGISTRY_DIR`） | 已实现 | 测试用沙箱注册表，不碰真实 `~/.allworktogether` |
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
| 注册表目录可隔离 | `projects.py`（`ABOARD_REGISTRY_DIR`） | 已实现 | 测试用沙箱注册表，不碰真实 `~/.allworktogether` |
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
