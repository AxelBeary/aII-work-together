# ENVIRONMENT.md — 本机环境事实（已实测）

> 规矩：只写**实测过**的事实，每条附**可复跑命令**与取证日期。踩过的新坑收工前必须补进来。
> 本项目专用；跨项目纪律见全局 `~/.config/opencode/AGENTS.md`。


## E-01 · 工作区现状（取证 2026-10-19）

- 工作区：`E:\GithubClone\allworktogether`。
- 立项目前**只有** `.opencode\memory\project.md`（69 字节）＋ `.opencode\memory\.gitignore`（内容＝`*`，即项目记忆默认不进库）。
- 立项目前**不是** git 仓库 → 2026-10-19 由发牌席 `git init` 建立**本地库**（⛔ 无远程）。

复跑：`Get-ChildItem -Force -Recurse E:\GithubClone\allworktogether | Select-Object FullName,Length`；`git -C E:\GithubClone\allworktogether status`

## E-02 · 兄弟项目与本机资产（取证 2026-10-19）

`E:\GithubClone\` 下同级项目：`.qoder-distill-work`、`agent-delegation`、`agents`、`allworktogether`、`cutting-room-floor`、`JIGSAW_PUZZLES`、`qodercnbackup`、`renforge-mcp`、`renpy-aistudio`、`renpyslim`、`sentinel-ops`、`waypost`（另有 1 个中文名目录）。

- **`sentinel-ops`**：本机治理范式来源（`AGENTS.md` 六纪律／部署三分法／席位制／插件六道门）。本项目**只借鉴范式**。
- **`agent-delegation`**：派工方法学正档（技能体在 `~\.agents\skills\agent-delegation`）。
- **`waypost`**／**`renforge-mcp`**：代码库结构参考（`docs/`＋`src/`＋`tests/`＋`tools/`）。

## E-03 · 技能库落点（取证 2026-10-19）

- 权威根：`C:\Users\qly19\.agents\skills\`（**唯一真本**；`~\.qoder-cn\skills` 已退役）。
- 现有技能目录（30 个，含 `_dev`）：agent-delegation／blender-modeling／fetch-analyze-data／huiyue-layout-audit／knowledge-base／neat-freak／opencode-v2-playbook／renpy-*（9 个）／safe-identifier-rename／ship-gate／simplify-codebase／skill-library-audit／software-teardown／vn-*（5 个）／zx-imgapi。
- **用前按文件名现查**，⛔ 不记绝对路径硬编码。

复跑：`Get-ChildItem "$env:USERPROFILE\.agents\skills" -Directory | Select-Object -ExpandProperty Name`

## E-04 · 本机可调用的 CLI 引擎（取证 2026-10-19，源自 agent-delegation 技能 §2；**本轮未现场复算**）

| 引擎 | 无头最小式 | 判成败 |
|---|---|---|
| Hermes | `hermes -p <角色> -z "<提示词>"` | 运行期错误也 RC=0；看 `--usage-file` 的 `completed/failed` |
| codex | `Get-Content -Raw p.md \| codex exec --ephemeral --skip-git-repo-check --sandbox <档> -c approval_policy=never --json -` | 参数错 RC=2／运行期错 RC=1 |
| qoderclicn | `qoderclicn -p "<提示词>" -o json --no-session-persistence` | RC=1 铁败；RC=0 还要看 `is_error` |
| opencode | `opencode run --format json "<提示词>"` | **退出码两态同码**，不可独信；判 `type:"text"` 回执 |

> ⚠️ 以上为技能正档转录，**尚未在本项目现场复算**；真要用某引擎前，先按技能 targets.md 的口径现场验一次。

## E-05 · RTOC 信道（可选外部模型出口，取证 2026-10-17/18）

- 端点 `POST https://api.rtoc.cc/v1/messages`；钥匙在 `C:\Users\qly19\Desktop\2rtoc.env`（`sk-` 开头行）。
- **硬坑**：请求体硬上限约 46000 字节（≥64KB 静默返回空**且照样计费**）；它本质是「被套了人设的编辑器助手」，会以「请切到能生成代码的模式」拒答；成败主要取决于**时段窗口**。
- ⛔ 明文钥匙不得出现在任何输出／日志／文件／记忆里。详见本机记忆 `rtoc-channel`。

## E-06 · 子代理免费模型池不可裸派（取证 2026-10-19，本项目实测）

- **现象**：3 席 `subagent` 同时派出、**未指定模型**（走默认免费池）→ **3/3 全败**，报错原文：
  `OpenCode's free models aren't available from your current network because we've detected abusive traffic from this IP address.`
- **处置**：显式指定付费模型 `opencode-go/gpt-6-luna` 后**同一批 3 席一次全过**。
- **教训**：派工前先确认模型可用性；**别用默认池裸派**。失败会话 `sessionID` 仍在（`ses_eacc1c5efffe…` 等），可续但上下文已污染，重派更省。
- **可复跑**：`tools.opencode.models({ provider: "opencode-go" })` 查可用模型；或直接 `subagent` 带 `model` 参数。

## E-07 · 抽验该抽什么（取证 2026-10-19）

- 本项目首轮 3 席调研，发牌席抽验 5 条：**4 条属实、1 条链接路径错**（`/docs/codex/non-interactive-mode` → 404，正确为 `/docs/non-interactive-mode`），**内容本身无误**。
- **结论**：子代理在「结论与判断」上表现好（会主动标「未见」「未证」），**易错点是可机械核对的字串**——链接路径、星数、版本号。
- **做法**：抽验优先抽**数字与 URL**（机器可判、成本低），不必重读其论证过程。

## E-08 · 子代理模型可用性实测（取证 2026-10-19，一天内 5 次失败）

**背景**：本项目同一天派出两批共 6 席，**前 4 次尝试全部失败**，全部是模型/网络侧问题，不是任务问题。

| 模型 | 结果 | 报错原文（要点） |
|---|---|---|
| 默认免费池（不指定 model） | ❌ 3/3 全败 | `OpenCode's free models aren't available from your current network because we've detected abusive traffic from this IP address` |
| `opencode-go/gpt-6-luna` | ✅ 首批 3/3 通过 → ⚠️ 同日稍后 **❌ 3/3 全败** | `Country, region, or territory not supported` |
| `claudecodesale/claude-sonnet-5-5` | ❌ | `当前地区暂不支持访问模型 claude-sonnet-5-5` |
| `opencode/deepseek-v4.1-flash` | ❌ | `Upstream request failed: Insufficient account funds` |
| **`opencode-go/deepseek-v4.1-flash`** | ✅ **本次 3/3 通过** | —（与主代理同款模型、同 provider，资金与地区都确定可用） |

**结论与做法**：
1. **派子代理时显式指定 `opencode-go/deepseek-v4.1-flash`**（＝主代理自己用的那款）。理由最硬：主代理能跑 ⇒ 该模型在本机、本地区、本账户下**确定可用**，不会出现「地区不支持」或「余额不足」。
2. ⛔ **不要靠默认模型池**：免费池被网络侧封禁，且报错原因（`abusive traffic from this IP`）与账号无关，改配置也治不了。
3. **同一个模型可用性会漂**：`gpt-6-luna` 同一天内先可用后区域封禁 ⇒ **⛔ 不要把「刚才还能用」当稳态**，每次派工都要按回执判，失败即换。
4. 失败会话 `sessionID` 会返回，但上下文已被污染，**重派比续跑划算**。

## E-09 · 「毕方」与「BitFun」不是同一件事（取证 2026-10-19，P4 实证）

- 用户点名调查「毕方 BitFun」，但**两者没有公开关联**：
  - `BitFun` ＝ `GCWing/OpenBitFun`（2,857★、MIT、桌面 agent 工作台）。
  - 「毕方」＝ 广州实验室的科研多智能体平台（**无公开仓库、无许可**，仅媒体转述）。
- **实测**：`GCWing/BitFun` 的 `README.zh-CN.md` 里「毕方」出现 **0 次**（同文件「BitFun」出现 22 次 ⇒ 尺是活的，非空跑）。
- **教训**：**中文名与英文名撞在一起时，先证它们是一件事，再当一件事写**。⛔ 不得因为「用户这么叫」就合并成一个条目。
- **可复跑**：
  ```powershell
  $t=(Invoke-WebRequest 'https://raw.githubusercontent.com/GCWing/BitFun/main/README.zh-CN.md' -UseBasicParsing).Content
  ([regex]::Matches($t,'毕方')).Count   # 期望 0
  ([regex]::Matches($t,'BitFun')).Count # 必须非零（22）
  ```

## E-10 · 四引擎无头调用实测（取证 2026-10-19，本项目现场复算）

> 本表是**本项目现场实测**，不是技能转录。每次派工前按此复算。

| 引擎 | 版本 | 无头可用？ | 实测结论 |
|---|---|---|---|
| **opencode** | v2.0.32 | ✅ **可用（必须显式指定模型）** | `opencode run --format json --model opencode-go/deepseek-v4.1-flash "..."` → RC=0，stdout 出 `type:"text"`。⛔ **不加 `--model` 会走免费池，被 IP 封禁返回 `type:"error"` + RC=1** |
| **qoderclicn** | 1.1.68 | ✅ **可用** | `qoderclicn -p "..." -o json --no-session-persistence` → RC=0，`is_error:false`，含 `session_id`／`duration_ms`／`modelUsage` |
| **codex** | 0.153.4 | ❌ **当前不可用** | 走 RTOC 中转，返回 `401 Unauthorized: Invalid token`（`api.rtoc.cc/v1/responses`）；JSONL 末尾 `turn.failed`。**需先修 RTOC 钥匙** |
| **hermes** | v0.22.0 | 未测 | 本轮未验证 |
| claude | — | 未安装 | — |

**两条铁律（本项目已多次验证）**：
1. **退出码不可信**：opencode 免费池失败返回 RC=1，但错误藏在 stdout JSON 的 `type:"error"` 里；qoderclicn 的 `subtype:"success"` 也不能单独信（要看 `is_error`）。
2. **判成败必须解析结构化回执**，不能看 RC。

**可复跑**：
```powershell
# opencode（必须带 --model）
opencode run --format json --model opencode-go/deepseek-v4.1-flash "只回复两个字：可用"
# qoderclicn
qoderclicn -p "只回复两个字：可用" -o json --no-session-persistence
# codex（当前会 401）
"只回复两个字：可用" | codex exec --ephemeral --skip-git-repo-check --sandbox read-only -c approval_policy=never --json -
```

## E-11 · opencode 默认模型池不可用（取证 2026-10-19）

- `opencode run` **不指定 `--model`** 时走免费池 → 返回：
  `FreeTierError: OpenCode's free models aren't available from your current network because we've detected abusive traffic from this IP address`
- **RC=1，但错误只在 stdout JSON 的 `type:"error"` 里**（stderr 为空）。
- **处置**：编排器**必须强制给每个 opencode 任务指定模型**，默认钉 `opencode-go/deepseek-v4.1-flash`。
- 同 E-08：子代理派工同样必须钉模型。

## E-12 · 会话续接实测（取证 2026-10-19，本项目）

**两个引擎都实测通过**：

| 引擎 | 续接方式 | 实测结果 |
|---|---|---|
| **opencode** | `--session <id>` | ✅ 第1轮记 42 → 第2轮准确答 42 |
| **qoderclicn** | `-r/--resume <id>` | ✅ 第1轮记 77 → 第2轮准确答 77 |

**qoderclicn 的坑**：⛔ **不能加 `--no-session-persistence`**。加了之后 `--resume` 报
`Error resuming session: Invalid session identifier`（会话没落盘）。
⇒ 要支持续接就必须持久化会话；已在 `engines.py` 去掉该旗标。

**其他相关旗标**：
- opencode：`--continue`（续最近）、`--fork`（分叉）、`--agent`（build/plan/general/explore）
- qoderclicn：`-c/--continue`、`--fork-session`、`--reasoning-effort`、`--thinking`

**教训**：⛔ 别再假设「每次调用都是全新上下文」。

**可复跑**：
```powershell
python -c "import sys; sys.path.insert(0,'tools'); import engines as E; r1=E.run('qoderclicn','记住77'); r2=E.run('qoderclicn','刚才那个数？',session_id=r1.session_id); print(r2.text)"
```

## E-13 · 原子认领必须用固定路径名（取证 2026-10-19，专家团抓出 + 本席复现）

- **反例（已修的 bug）**：租约目录名写成 `L__<seat>__<engine>__<ms>__<uuid6>` ⇒ **每个进程创建的路径都不同**，`os.mkdir` 的 `FileExistsError` 永远不会触发，互斥退化成「先读后写」的 TOCTOU。
- **实测**：12 线程抢同一张卡 → **3 个成功、3 个活跃租约**（红线③当场破）。
- **正解**：租约目录用**固定名**（`lease/active/holder`），`os.mkdir` 才真正互斥；席位身份写进 `owner.json` 而不是目录名。
- **复测**：12 线程 → **1 成功、11 失败、1 个租约**。
- **教训**：**「用了原子 API」≠「实现了原子性」**。名字里带 uuid 的独占创建等于没有独占。

**可复跑**：`python tools/_test_race.py`（临时件，已在收口时清理；复算口径见上）

## E-14 · 「端到端跑通」不等于「防线有效」（取证 2026-10-19）

- 本项目在编排器**端到端成功**之后，派专家团审自己的代码，**又抓出 5 个真 bug**（红线③被破、返工死锁、空 token 放行、journal 可整份伪造、机器闸写死 True）。
- **结论**：**跑通只证明「顺利路径能用」，不证明「异常路径挡得住」**。
- **做法**：任何声称「有防线」的东西，必须配**攻击视角的反向测试**（并发、伪造、越权、空输入各来一次）；没有反向测试的防线一律按 `未证` 处理。
- 这条与全局规则 §1「反向测试＝故意改坏一处必须被抓住」同源，此处是它的**实证**。

## E-15 · 哈希链的能力边界（取证 2026-10-19，辩论中对方点出）

- **能防**：手写插入一条事件、改动某条内容、删除中间行 → 链条断裂，`audit` 抓到。
- **防不住**：**有权限的伪造者把整条链重算一遍**（无密钥哈希，`_hash = sha256(prev + body)` 谁都能算）。
- **结论**：这是**篡改可见**（tamper-evident），不是**篡改不可能**（tamper-proof）。
- **要真防住**只有两条路：① 用密钥签名（HMAC/Ed25519），密钥不进看板目录；② 把链头哈希存到看板之外的只追加位置。
- **当前判断**：本机单用户场景下，**篡改可见已够用**——因为唯一的「攻击者」是 agent，而 agent 没有动机也没有必要做整链重算（它只要按 CLI 走就能通过）。
- ⛔ **不得对外宣称「journal 不可篡改」**，只能说「可检测篡改」。

## E-16 · 打桩测试 ≠ 真跑验证（取证 2026-10-19）

- G2（辩论）与 G3（内置子代理）的单元测试**都通过**，但都是 `FakeEngine` / `E._exec` 打桩——只证明「参数拼对了、逻辑走通了」。
- **真跑**才暴露兼容性：真辩论跑出 2 个独立 `ses_` 会话；`--agent plan/general` 真跑成功；`--agent nope` 真被拒。
- **做法**：凡声称「兼容/可用」的功能，**至少要有一条真引擎的实跑证据**；只有打桩的一律标 `未证`。

## E-17 · 三个「值得抄」的实件（取证 2026-10-19）

| 件 | 是什么 | 为什么值得抄 |
|---|---|---|
| `openai/symphony` SPEC.md | Apache-2.0 的调度服务规格 | **唯一「规格级可抄」**：claim 防重复、并发上限、重试回收、状态对账、结构化日志；§17/§18 有 60+ 条断言可当回归库种子 |
| `Wholiver/metis` | 403★ MIT，非看板 | **「完成即证据」做成了机械闸门**：G0–G7 收据状态机、`FALSE_COMPLETION_BLOCKED`（源码实测 G7 出现 45 次、该常量 1 次） |
| `EKKOLearnAI/ekko-studio` | 11,471★，前身 Hermes Studio | 14 引擎同屏 + 看板 + 审批门 + 运行回放，**外壳最像我们要造的**；⚠️ 许可 **BSL-1.1**（非开源，2029 转 Apache） |

⚠️ **反向警告（Metis 自评）**：其 32 个零分任务里 27 个是「跑了但跑错」，首因是**治理仪式吃掉产出**。⇒ **闸门别做成表演**。

**可复跑**：`Invoke-RestMethod https://api.github.com/repos/<owner>/<repo>` 读 stars／license／pushed_at（⛔ 别信记忆里的数）。

## E-18 · 拆代码的教训：渐进，不重写（取证 2026-10-19）

- `board.py` 一度 1099 行／44KB。**没有**一次性拆成完整包，而是按职责抽出 `render.py`（渲染）、`projects.py`（多项目）、`parallel.py`（并行），`board.py` 保留为 CLI 入口。
- **理由**：一次性大重构会让回归基线失效、且无法二分定位回归来源；渐进拆每次只动一块，跑完 18 条回归即知有没有坏。
- **做法固化**：拆一个模块 → 立即跑 `run_regression.py` + `--break` → 绿了才继续下一块。

## E-19 · 多项目与并行实测（取证 2026-10-19）

**多项目**：
- 注册表 `~/.allworktogether/projects.json`，只存 `name/path/defaults`，**不存卡片**。
- 实测在 `C:\Users\qly19\AppData\Local\Temp\opencode\demo-project` 里直接 `board add` ⇒ 自动建 `board/`、自动登记、`board ls` 只看得到本项目 1 张卡；主项目不受影响。
- `board project ls` 能汇总两个项目各自的卡片数。

**并行（worktree）**：
- 实测 `orchestrator.py run --parallel 2`：两张卡同时跑，各在 `.worktrees/<card-id>/`，均在 14s 内完成，交付物正确拷回，worktree 自动清理。
- **冲突检测实测**：两张卡都产出 `board/artifacts/same.md` ⇒ 后到的判 `conflict`，**未覆盖**先到的；先到的正常完成。
- ⚠️ worktree 依赖 git；无 git 或仓库无提交时退化为「目录副本」，隔离性弱但仍不互踩。

## E-20 · SQLite 迁移的两个真 bug（取证 2026-10-20）

换存储过程中，**测试抓出 2 个真 bug**（都不是测试写错）：

| # | Bug | 现象 | 根因 | 修复 |
|---|---|---|---|---|
| 12 | **`_store()` 无锁** | 12 线程并发首次调用 ⇒ 造出 **12 个 Store 实例**（各带一把锁）⇒ 互斥失效，**3 个 agent 同时认领成功** | 惰性单例没加锁 | 模块级 `threading.Lock` 包住创建 |
| 13 | **SQLite 连接跨线程共享** | 压力下报 `sqlite3.InterfaceError: bad parameter or other API misuse` | sqlite3 连接不是线程安全的（`check_same_thread=False` 只是关掉检查，不是让它安全） | 读：**每线程一个连接**；写：**每次写独立连接 + BEGIN IMMEDIATE** |

**教训（第 5 次同源）**：**「看起来是原子的 API」不等于「实现了原子性」**。
`INSERT + PRIMARY KEY` 本身是对的，但被没有锁的惰性单例包住就失效了——和 E-15（`mkdir` 名字带 uuid）是同一类错：**外层封装把内层的保证吃掉了**。

**做法**：任何「靠数据库/文件系统原语保证互斥」的地方，必须配一条**并发实测**（≥12 线程），且必须检查「成功次数 == 1」而不只是「没报错」。

## E-21 · 几十个项目规模的实测（取证 2026-10-20）

- 造 20 个项目 × 15 张卡 ＝ **300 张**，跨项目扫描 **0.21 秒**（冷）、**0.0004 秒**（15 秒缓存命中）。
- 结论：**每项目一个 SQLite + 注册表一个 SQLite** 的架构，几十个项目量级完全够用，不需要引入服务端。
- 缓存文件 `~/.allworktogether/summary-cache.json`，15 秒 TTL；`board all --refresh` 可强制重扫。

**可复跑**：`python -c "import sys;sys.path.insert(0,'tools');import projects as P;print(len(P.project_summary(use_cache=False)))"`

## E-22 · opus 评审抓出的 3 个真缺陷（取证 2026-10-20）

外部专家（claude-opus-5-5）读源码评审，指出 3 个缺陷；本席**逐条复现确认属实**后修复：

| # | 缺陷 | 复现方式 | 后果 | 修复 |
|---|---|---|---|---|
| 9 | **状态转移白名单从未被调用** | `grep TRANSITIONS` 只有定义处，零调用点 | 任何状态下追加一条 `human` 事件都能直接变「完成」——**红线被架空** | 新增 `guard_transition()`，接入 claim/submit/verify/review/human/block |
| 10 | **长任务会被抢走** | `LEASE_TTL=600` vs `engines.run(timeout=1800)` | 引擎跑超 10 分钟 ⇒ 租约超时被回收 ⇒ 另一引擎接手同一张卡 ⇒ **同一卡双写** | 执行期后台线程按 `HB_INTERVAL` 持续心跳；提交前 `guard_holder()` 校验租约还在自己手上 |
| 11 | **并行改已有文件必被误判冲突** | `collect()` 判据＝「工作区有该文件且内容不同」 | **所有修改旧文件的卡都被判冲突**，并行等于只能新建文件 | 改为**基线判据**：开工时记录交付物 hash，只有「我干活期间别人改过」才算冲突 |

**附带修的两个隐患**：
- **journal 并发写入分叉哈希链** ⇒ 加跨进程文件锁（Windows `msvcrt` / POSIX `fcntl`），「读 prev → 算 hash → 写」整段原子。复测：20 线程并发写，21 条事件、seq 无重复、链完整。
- **坏行被静默丢弃** ⇒ 解析失败的行写入 `journal.corrupt`，不再吞掉。

**教训（第 4 次同源）**：**「定义了」不等于「生效了」**。`TRANSITIONS` 写在文件里 66 行处，看着像防线，实际零调用。⇒ 凡声称「有某道防线」，必须有一条**测试直接调用它并证明它会拒绝**（对应回归用例 R19/R20/R21）。

**可复跑**：`python tests/run_regression.py`（R19–R23 覆盖上述修复）

## E-23 · opus 评审：哪些轮子该用、哪些别用（取证 2026-10-20）

外部专家（claude-opus-5-5）关键判断，本席采信并已落地的部分：

| 判断 | 我们的处置 |
|---|---|
| Temporal / Plane / CrewAI / A2A 在**单人本机**场景不划算，别引 | ✅ 维持零依赖，不引 |
| 卡片记录建议换 SQLite（Python 自带，不算新依赖） | ⏸ **暂缓**——当前加文件锁已解决并发写；换存储是大事，留待真出问题再做 |
| 并行收工建议改用 git 分支+合并 | ⏸ **部分采纳**——已用「基线判据」修掉误判；分支合并留待需要多文件协同改时 |
| **ACP 官方列表已收录 opencode／qoder／hermes／codex** | 📌 **记下**：以后接新引擎优先走 ACP，不再手写回执解析器 |
| 最该做的一件事＝「拍板收件箱」 | 📌 **记为下一步**（一次最多 3 张、人话、带可复制命令） |

评审全文：`docs/design/20261020-opus-review/OPUS-设计评审__外部专家__claude-opus-5-5.md`

## E-24 · 网页界面的多项目串号（实测抓到的真 bug，2026-10-20）

**现象**：两个浏览器标签页分别指向不同项目，同时建卡 ⇒ **卡被建到别的项目里**、同号卡被静默覆盖、25 张只建成 10 张。

**根因**：`server.py` 每个接口都靠 `B.set_root(...)` 改**模块级全局**当前项目，而 `ThreadingHTTPServer` 是一请求一线程。线程 A 刚把根切到 alpha，线程 B 立刻切到 beta，A 随后写入就落进了 beta。

**为什么之前没发现**：只注册过 1 个项目，单项目下「切根」永远切到同一个地方，错误不可见。⇒ **多项目能力必须用多项目压测，不能靠单项目回归倒推。**

**修法**（两条都要）：
1. `server.py` 加 `_BOARD_LOCK`（RLock），所有看板访问串行化。单人本地界面够用；要真并发得把项目根改成 `contextvars`，那是另一件事。
2. `board.create_card()` 先查后写、重号直接 `ValueError`。存储层用的是 `INSERT OR REPLACE`，**覆盖是静默的**，不先查就会「看起来建成了」。

**同批修掉**：`projects.project_summary()` 遍历完几十个项目后只还原 `ROOT`、没还原 `WORKSPACE` ⇒ 调用方的工作区悄悄变成「最后一个被遍历的项目」。现连工作区一起还原，并把缓存文件改成**原子写**（临时文件 + `os.replace`）。

**反向测试（关键）**：把 `with _BOARD_LOCK:` 换成 `with threading.RLock():`（每次新锁＝没锁），并发测试必须变红；实测红（6 次失败 + 双向串号）。恢复后转绿。

**可复跑**：

```
python tests/test_ui_concurrency.py     # 两项目并发 25+25 张，4 个读线程
python tests/test_multiproject.py       # 12 个项目 / 注册表并发 / 工作区还原
```

**教训（第 6 次同源）**：「全局状态 + 每请求一线程」＝**必然串号**，只是没压测时看不见。凡「切换全局当前对象」的接口，先问一句：**同时来两个请求会怎样？**

## E-25 · 两个「接口字段被当契约」的坑（2026-10-20）

### 1. 托盘「看看状态」永远是 0 张

托盘读 `/api/state` 里的卡片，可那个接口**只返回项目列表和当前项目**，压根没有卡片 ⇒ 它数出来恒为 0，而且**不报错**。

**教训**：一个接口只要被第二个程序消费，它的字段就是**契约**。改后端时不会报错，另一个程序会安静地显示错数。
⇒ 现在有 `tests/test_ui_api.py` 专门钉住每个接口的形状（哪些字段必须在、哪些**必须不在**），并断言「拒绝后原卡没被改掉」。

### 2. 首页刷新白烧 CPU

`/api/state` 为了给「各状态几张卡」这个数字，把当前项目的**每张卡的事件流完整重放了一遍**；而前端本来就已经从 `/api/cards` 拿到了全部卡片。

后果：一张卡＝两遍日志扫描（重放一次 + 用量聚合一次），几百张卡时首页刷新是纯浪费。

**修法**：
- `/api/state` 不再算张数（前端自己数，永远是实时值，也不会和列出的卡不一致）
- `board.replay(cid, events=...)` 支持传入已读好的事件流 ⇒ 一份日志只读一次
- 顺带：下拉框里的项目张数改用实时值，不再显示后端 15 秒缓存

**教训**：**同一份数据不要算两遍**。前端已经拿到的，后端不要为了「方便」再算一次——多一次计算就多一个不一致的可能。

### 3. 本机跑压测的自我约束（同日实证）

在用户机器上跑「60 项目 × 40 卡」的合成压测时，本机同时在跑别的 agent 的全盘 `rg`，机器直接卡到用户手动 kill。

**规矩**：
- 压测脚本必须**默认轻量**（`tests/bench_scale.py` 默认 20×15），重规模要显式传参
- 机器已经在忙时**不跑合成负载**；要压就先问一句，或放到用户不在用的时段
- 压测产生的沙箱目录与后台进程，收工必须清（本次清了 2 个进程 + 17 个临时目录）

**可复跑**：

```
python tests/test_ui_api.py             # 接口形状契约（很快）
python tests/bench_scale.py             # 轻量：20 项目 × 15 卡
python tests/bench_scale.py 60 40       # 重规模，机器闲时再跑
```

## E-26 · 结构性浪费：每请求重建 SQLite 连接（2026-10-20）

**怎么发现的**：界面已经 <30ms，看着「够快」。但按「这条请求的时间花在哪」去拆，发现每个 HTTP 请求都要**新建一条 SQLite 连接，并把建表语句重跑一遍**。

**根因**：连接是 thread-local 的（`projects._conn()` / `storage.Store._conn()`，新连接还要 `executescript(SCHEMA)`），而 `ThreadingHTTPServer` 是**一请求一线程** ⇒ 线程一换，thread-local 必然落空，连接必然重建。

**实测单价**：新线程上「建连接 + 跑建表 + 一次查询」＝ **4.2ms 中位 / 5.2ms 最慢**。一条请求要碰两个库（注册表 + 项目卡库）≈ 8ms，而当时整条请求才 20–30ms。

**改法**：`PoolHTTPServer`——固定 4 线程的线程池（`ThreadPoolExecutor`），线程复用 ⇒ 连接复用 ⇒ 建表只付一次。保留 `--workers 0` 走老行为，专门用于 A/B 对照。

**实测（40 项目 / 1200 卡，中位 / p90，均在合并后的代码上重测）**：

| 接口 | 一请求一线程（`--workers 0`） | 线程池 4 |
|---|---|---|
| 看板列表（当前项目全部卡） | 29ms | **15ms** |
| 单卡详情 | 1ms | 1ms |
| 用量汇总 | 13ms | 16ms（噪声区间） |
| 汇总冷缓存那一下 | 16ms / 49ms 抖动 | 26ms / 50ms 抖动 |

**读法**：只有「看板列表」这项是稳定、可复现的改进（29→15ms）；其余几项在这台机器上的噪声（15ms 地板、偶发 50ms 尖峰）盖过了连接复用省下的那几毫秒，**不能当作结论**。连接重建的单价（4.2ms）是直接测出来的，不受这些噪声影响。

**顺带**：`_switch()` 在项目没变时直接返回（原来每个请求都要 mkdir + 查旧数据迁移）；建卡/拍板后主动让汇总缓存失效，下拉框里的张数不再滞后 15 秒。

**教训**：「绝对耗时小」不等于「没有浪费」。判断有没有浪费要问三件事：**这条请求重复做了哪些同样的活？哪些开销跟数据量无关（＝纯税）？缓存真的命中了吗？** 只看总耗时会把这些全掩盖。另外**改动前后要在同一份代码上重测**——换了代码还引用旧读数，就是拿旧数字冒充新结论。

**勘误（2026-10-20 02:10）**：提交 e6fdb8e 的信息里把上述「工作树被回滚」写成「另一个会话干的」，**这是错的**。只读核对本机 `opencode.db` 后确认：那段时间只有本会话在活动，334 个会话里没有叫 btw 的，也没有第二个会话碰过本仓库；相关关键词只出现在本会话。真相＝那段工作在上下文压缩时被裁出视野，同时几个文件被恢复成更早的快照（疑似 harness 的 workspace snapshot 还原）。教训见项目记忆「上下文压缩后的自我不一致」。
