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
