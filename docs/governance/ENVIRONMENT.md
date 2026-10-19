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

## E-11 · 四引擎无头调用实测（取证 2026-10-19，本项目现场复算）

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

## E-12 · opencode 默认模型池不可用（取证 2026-10-19）

- `opencode run` **不指定 `--model`** 时走免费池 → 返回：
  `FreeTierError: OpenCode's free models aren't available from your current network because we've detected abusive traffic from this IP address`
- **RC=1，但错误只在 stdout JSON 的 `type:"error"` 里**（stderr 为空）。
- **处置**：编排器**必须强制给每个 opencode 任务指定模型**，默认钉 `opencode-go/deepseek-v4.1-flash`。
- 同 E-08：子代理派工同样必须钉模型。

## E-14 · 会话续接实测（取证 2026-10-19，本项目）

- **opencode 支持真正的多轮会话**：`--session <id>` 续接，上下文全在。
- **实测**：第 1 轮让模型「记住 42」→ 得到 `session_id`；第 2 轮带同一 `session_id` 问「刚才那个数」→ **准确回答 42**。
- 其他相关旗标：`--continue`（续最近）、`--fork`（分叉后续）、`--agent`（指定内置 agent：build/plan/general/explore）。
- **教训**：这是「会话间交流」的技术基础；⛔ 别再假设「每次调用都是全新上下文」。

**可复跑**：
```powershell
python -c "import sys; sys.path.insert(0,'tools'); import engines as E; r1=E.run('opencode','记住42',model='opencode-go/deepseek-v4.1-flash'); print(r1.session_id); r2=E.run('opencode','刚才那个数？',model='opencode-go/deepseek-v4.1-flash',session_id=r1.session_id); print(r2.text)"
```

## E-15 · 原子认领必须用固定路径名（取证 2026-10-19，专家团抓出 + 本席复现）

- **反例（已修的 bug）**：租约目录名写成 `L__<seat>__<engine>__<ms>__<uuid6>` ⇒ **每个进程创建的路径都不同**，`os.mkdir` 的 `FileExistsError` 永远不会触发，互斥退化成「先读后写」的 TOCTOU。
- **实测**：12 线程抢同一张卡 → **3 个成功、3 个活跃租约**（红线③当场破）。
- **正解**：租约目录用**固定名**（`lease/active/holder`），`os.mkdir` 才真正互斥；席位身份写进 `owner.json` 而不是目录名。
- **复测**：12 线程 → **1 成功、11 失败、1 个租约**。
- **教训**：**「用了原子 API」≠「实现了原子性」**。名字里带 uuid 的独占创建等于没有独占。

**可复跑**：`python tools/_test_race.py`（临时件，已在收口时清理；复算口径见上）

## E-16 · 「端到端跑通」不等于「防线有效」（取证 2026-10-19）

- 本项目在编排器**端到端成功**之后，派专家团审自己的代码，**又抓出 5 个真 bug**（红线③被破、返工死锁、空 token 放行、journal 可整份伪造、机器闸写死 True）。
- **结论**：**跑通只证明「顺利路径能用」，不证明「异常路径挡得住」**。
- **做法**：任何声称「有防线」的东西，必须配**攻击视角的反向测试**（并发、伪造、越权、空输入各来一次）；没有反向测试的防线一律按 `未证` 处理。
- 这条与全局规则 §1「反向测试＝故意改坏一处必须被抓住」同源，此处是它的**实证**。

## E-17 · 三个「值得抄」的实件（取证 2026-10-19）

| 件 | 是什么 | 为什么值得抄 |
|---|---|---|
| `openai/symphony` SPEC.md | Apache-2.0 的调度服务规格 | **唯一「规格级可抄」**：claim 防重复、并发上限、重试回收、状态对账、结构化日志；§17/§18 有 60+ 条断言可当回归库种子 |
| `Wholiver/metis` | 403★ MIT，非看板 | **「完成即证据」做成了机械闸门**：G0–G7 收据状态机、`FALSE_COMPLETION_BLOCKED`（源码实测 G7 出现 45 次、该常量 1 次） |
| `EKKOLearnAI/ekko-studio` | 11,471★，前身 Hermes Studio | 14 引擎同屏 + 看板 + 审批门 + 运行回放，**外壳最像我们要造的**；⚠️ 许可 **BSL-1.1**（非开源，2029 转 Apache） |

⚠️ **反向警告（Metis 自评）**：其 32 个零分任务里 27 个是「跑了但跑错」，首因是**治理仪式吃掉产出**。⇒ **闸门别做成表演**。

**可复跑**：`Invoke-RestMethod https://api.github.com/repos/<owner>/<repo>` 读 stars／license／pushed_at（⛔ 别信记忆里的数）。
