# aII-work-together

> **单人／小团队用的多 agent 编排看板**：让本机所有 AI agent 在同一块板上分工协作，全程可追责。

## 最快的用法：桌面窗口（双击 `open-board.cmd`）

`open-board.cmd` 会启动 **桌面壳**：自己的图标、自己的窗口、**没有地址栏和标签页**。

- 壳＝C# + WebView2（复用系统 Edge 内核），产物 `shell\boardshell.exe` 几十 KB，**不是 Electron**。
- 窗口里什么都有：看板 + **内置终端**（底部抽屉，`Ctrl+`` 开合）+ **留言**（跨会话传话）。
- **最小化 / 关闭都收进托盘**；双击托盘图标回来，真要退出走托盘右键菜单。
- 壳没编译过会自动退回「托盘 + 默认浏览器」。

```cmd
shell\build.cmd                    :: 编译壳（要改壳才需要跑）
shell\boardshell.exe --selftest    :: 无界面自检：真起内核、真加载页面、回读 DOM
```

托盘仍在：`tray\tray.cmd` → 右下角「板」图标 → 双击打开看板。

## 三分钟上手（命令行）
```bash
# 1. 在任意项目目录，设一次默认值（只做一次）
python <本项目>/tools/board.py project default --engine opencode --model opencode-go/deepseek-v4.1-flash

# 2. 建一张卡
python <本项目>/tools/board.py add --title "把登录页改成深色" --goal "只改 landing 目录"

# 3. 让它自己跑
python <本项目>/tools/orchestrator.py run --max 5

# 4. 看（或直接跑 board inbox 看有没有等你拍板的）
python <本项目>/tools/board.py inbox
```

就这四步。剩下的它会自己做。

## 你只做两件事

| 什么时候 | 跑什么 |
|---|---|
| 想知道现在该干嘛 | `board`（不带参数，给面板）/ `board inbox` |
| 需要你拍板时 | `board human <卡号> --decision approve`（或 `reject --note "要改什么"`） |

**驳回时写的理由会传回下一轮**，agent 会针对性修改，不是重做一遍。

## 它替你做什么

| 你担心的 | 它怎么管 |
|---|---|
| agent 说做完了但其实没做 | **完成＝证据**：产物在不在、字节/行数/非空白由闸门机器算、必含项命中；复核凭据里要有数字 |
| 两个 agent 抢同一张卡 | **原子认领**：`leases.card_id` 主键 ＋ `BEGIN IMMEDIATE`（CAS 删插），12 个线程只有一个赢 |
| agent 自己验自己 | **异会话复核**：复核席==执行席直接拒 |
| agent 偷改状态 | **哈希链**：手改 journal 会被 `audit` 抓 |
| agent 替你拍板 | **人闸**：出「拍板中」只有 `human` 命令 + token |
| 跑一半崩了 | **断点续跑**：按 journal 状态接上，不重做 |
| 多个 agent 改同一文件 | **worktree 隔离**：每卡一个工作区，冲突判阻塞 |
| 多个项目混在一起 | **多项目**：各项目自己的 `board/`，全局总览一眼看全 |

## 多项目

每个项目在自己目录下有 `board/`，数据跟项目走（可 git、可搬）。

```bash
board project add /path/to/other/project   # 登记
board project ls                            # 所有项目 + 卡片数
board overview                              # 跨项目总览页
board -p other-project ls                   # 切到别的项目
```

**零配置**：在任意目录直接跑 `board add ...`，它会自动把当前目录当项目、自动建看板、自动登记。

## 当文件夹装进工作区（不安装也能用）

把整个仓库当一个文件夹放进工作区（或任意位置）就行：**没有安装步骤、没有依赖**。

```powershell
git clone https://github.com/AxelBeary/aII-work-together D:\work\tools\aII-work-together
```

三种用法（都实测过）：

| 用法 | 命令 | 说明 |
|---|---|---|
| **管别的项目**（推荐） | `python D:\work\tools\aII-work-together\tools\board.py -C D:\work\mygame add --title "…"` | `-C` 指定项目根；数据写进**那个项目**的 `board/` |
| **在项目里直接跑** | `cd D:\work\mygame`，再 `python ..\tools\aII-work-together\tools\board.py ls` | 从项目子目录里跑也行（向上找 `board/cards`） |
| **当命令用** | 把工具目录加进 PATH，之后任意目录 `board ls` | `board.cmd` 用 `%~dp0` 定位自己，路径无关 |

两条边界：

- **注册表默认在家目录**（`~/.aII-work-together`）。要「完全只装在工作区」，设一个环境变量：

  ```powershell
  $env:ABOARD_REGISTRY_DIR = "D:\work\.aboard"
  ```

  各项目的数据仍在各自 `board/` 里，这里只登记「项目在哪」，删了不影响任何卡片。

- **桌面壳要自己编译一次**：`boardshell.exe`／`boardtray.exe` 不入库（`.gitignore` 里），下载的包里没有。**CLI 和浏览器界面（`board open`）开箱可用**；想要那个单窗口桌面壳，跑一次 `shell\build.cmd`（用系统自带 .NET Framework 的 csc，不下载任何东西，约几秒）。

两个容易踩的点：

- 工具目录**本身不是项目**：在工具文件夹里跑 `board` 会得到一个空看板（不报错）。要管哪个项目，用 `-C` 指过去，或进那个项目目录再跑。
- 工作区本身是 git 仓库时，把工具目录写进它的 `.gitignore`（或做成 submodule），别让工具的运行产物混进你的提交。

## 跨会话留言（agent 之间传话）

```bash
board msg send --to w1 --from b1 --body "契约第三段改为 30 天"   # 存住，得号 #12
board msg inbox --as w1          # 对方干活前收信（标已读）
board msg ls --as w1             # 看全部（●＝没读过）
board msg reply-to 12 --body "..."   # 用 --reply-to 12 接上那一句
board msg wake 12 --wake-engine opencode --wake-session ses_xxx  # 让它当场续会话答
```

- **只保证「存住了」**：唤不醒就如实写 `HELD`（退出码 2），绝不把「存下」说成「送到」。
- **不重发**：已回复过的拒绝再投（防对方答两遍、防重复扣费）。
- 编排器开工会自动收信：`orchestrator.py run` 启动时先把 `--seat` 的留言打出来并标已读。

## 内置终端（白名单，不是 shell）

界面右下角「终端」按钮或 `Ctrl+`` 打开。能跑：`board …` / `orch …` / `check …` / `py tools|tests/xxx.py` / 只读 `git`。
⛔ 管道、重定向、`&&` 一律拒绝（不经过 shell，按空格切数组直执行）；`board rm` / `board human` 不在白名单（拍板要走界面按钮或令牌）。

## 并行（可选，默认串行）

```bash
python tools/orchestrator.py run --parallel 2 --max 4
```

每张卡在独立 git worktree 里跑，互不踩文件；收工时只拷**该卡的交付物**，两卡交付物重叠就判阻塞。
⚠️ 建议 ≤2：本机引擎会抢资源，开太多反而慢。

## 自检（改完代码必跑一条）

```bash
python tools/check.py          # 全部：语法/回归/反向/续跑/审计/体检/真跑
python tools/check.py --quick  # 跳过真调模型的
```

单独跑也行：

```bash
python tests/run_regression.py          # 24 条回归
python tests/run_regression.py --break  # 反向测试：故意改坏必须被抓
python tests/test_resume.py             # 断点续跑
python tests/test_messages.py           # 留言：append-only / 唤不醒要说 / 不重发
python tools/board.py audit             # 有没有绕过 CLI 手改
python tools/board.py doctor            # 体检（残留租约/worktree/断链）
python tools/board.py doctor --fix      # 自动清理可修项
```

## 文件结构

| 文件 | 职责 |
|---|---|
| `tools/board.py` | **看板核心**：卡片、状态机、journal、租约、闸门、守卫 |
| `tools/cli.py` | 命令行层（所有命令与参数） |
| `tools/render.py` | 看板页与跨项目总览 |
| `tools/projects.py` | 多项目注册表、工作区解析 |
| `tools/engines.py` | 引擎适配：回执解析 + 会话续接 + 用量 |
| `tools/experts.py` | 专家团：11 个角色 |
| `tools/subagents.py` | 子代理：独立会话 |
| `tools/orchestrator.py` | 自主编排 |
| `tools/resume.py` | 断点续跑 |
| `tools/parallel.py` | worktree 并行 |
| `tools/messages.py` | 跨会话留言（append-only + 唤醒语义） |
| `tools/msgwake.py` | 唤醒工作者（续会话并把回答写成回复留言） |
| `tools/term.py` | 窗口内置终端（白名单执行） |
| `tools/server.py` + `tools/ui.html` | 本地界面（看板 + 终端 + 留言） |
| `shell/BoardShell.cs` | 桌面壳（WebView2，单 exe） |
| `tools/check.py` | 一条命令跑完全部自检（15 道闸） |

零依赖，Python 3.9+。

## 许可与致谢

- 本项目代码：**MIT**，见 [LICENSE](LICENSE)。
- 随仓库分发的第三方二进制（Microsoft WebView2 SDK 的 3 个 DLL）及其许可证全文：
  见 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。**分发 exe 时请把这份一起给。**
- 学过谁、借过什么思路（跨会话留言语义、治理范式、调研参考）：
  见 [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md)。

## 从哪读起

| 你想干什么 | 读哪里 |
|---|---|
| **马上用** | [`docs/usage.md`](docs/usage.md) |
| 进入本项目动手 | `AGENTS.md` |
| 看架构 | `docs/design/20261019-architecture-deepdive/98_架构总图__发牌席__合并稿.md` |
| 看已踩的坑 | `docs/governance/ENVIRONMENT.md` |
| 看拍板记录 | `docs/governance/DECISIONS.md` |
