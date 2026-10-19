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

**可复跑**：`tools.opencode.models({ provider: "opencode-go" })` 列出候选；派工时 `subagent` 带 `model: "opencode-go/deepseek-v4.1-flash"`。
