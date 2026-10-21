# HANDOFF.md — 会话交接块

> 给**下一个主会话**读。子代理读的是派工单，⛔ 两者不得混用。
> 最近更新：2026-10-20（收工批次）。上一次交接在 `04c2dc6` 之前。

---

## 一、一句话现状

**能用了，而且现在是一个真正的桌面应用。** 桌面壳（WebView2 单 exe，无地址栏）＋ 内置终端 ＋ 跨会话留言 ＋ 看板 ＋ 托盘 ＋ 点对点评审 ＋ 多项目，全部跑通并有闸门守着。
剩下的是「没做」而不是「没做完」——见 §五。

---

## 二、五分钟跑起来

```cmd
看板.lnk                              :: 桌面快捷方式：开桌面壳（壳自己起后端）
python tools/check.py --quick         :: 13 道闸（约 1 分半）
python tools/check.py --perf          :: 再加规模压测（轻量 20×15）
orch run --max 3                      :: 让 agent 自己找活干（开工会先收留言）
orch run --max 1 --consult "b1:opencode:claudecodesale/claude-opus-5-5@native,b2:opencode:opencode-go/deepseek-v4.1-flash@faithful"
```

---

## 三、文件在哪（按「改东西先找这里」排）

| 文件 | 职责 |
|---|---|
| `AGENTS.md` | **唯一入口**：纪律、领地、红线。动手前先读 |
| `tools/board.py` | 核心：卡片 / 状态机 / journal / 租约 / 三道闸 / 守卫 |
| `tools/storage.py` | SQLite 存储（cards / events / leases / lease_log / meta） |
| `tools/projects.py` | 多项目注册表 + 根目录与工作区解析 |
| `tools/consult.py` | **点对点评审**：评审席只准看、改后核对 |
| `tools/orchestrator.py` | 自主编排（认领 → 执行 → 评审 → 修改 → 提交 → 复核） |
| `tools/engines.py` | 引擎适配（回执解析、会话续接、用量） |
| `tools/server.py` + `tools/ui.html` | 本地网页界面（127.0.0.1:8777）；含终端抽屉 + 留言抽屉 |
| `tools/messages.py` | **跨会话留言**：append-only + 唤醒语义（抄 ocs 的四条，换掉传输层） |
| `tools/msgwake.py` | 唤醒工作者：拿 sessionID 续会话，把回答写成回复留言 |
| `tools/term.py` | **窗口内置终端**：白名单执行、一次一条、输出进环形缓冲 |
| `shell/BoardShell.cs` | **桌面壳**：WebView2 单 exe（`shell\build.cmd` 编译）；`VENDOR.md` 记 vendored 依赖 |
| `shell/boardshell.exe` | 编译产物（不进库）；`--selftest` / `--shot` 无界面自检 |
| `tools/cli.py` | 29 子命令 |
| `tray/BoardTray.cs` | C# 托盘（编译约 14.8 KB，非 Electron） |
| `tools/make_icon.py` | 代码画图标（纯标准库） |
| `assets/board.ico` | 托盘与快捷方式共用图标 |
| `open-board.cmd` / `看板.lnk` | 一键启动 |
| `tools/check.py` | 一条命令跑 12 道闸 |
| `docs/怎么用.md` | 给人看的五分钟上手 |
| `docs/点对点评审.md` | 评审链路怎么用、为什么不是聊天室 |

数据：每项目 `board/board.db`；证据 `board/evidence/<卡号>/`；交付物在工作区。
全局注册表 `~/.aII-work-together/registry.db`（可用 `ABOARD_REGISTRY_DIR` 隔离）。

---

## 四、四条红线（都有拒绝路径实测，不是口号）

| 红线 | 落地 | 测试 |
|---|---|---|
| ① 状态即证据 | L1 产物 / L2 形制 / L3 内容＋机器量反空跑；复核必须异会话且带凭据 | R04–R11、R24 |
| ② 人的拍板位不可越 | `human` 子命令 + 令牌；`guard_transition` 白名单 | R19、R20、R12 |
| ③ 认领即租约 | `leases.card_id` 主键；执行期后台心跳；`guard_holder` | R01、R21 |
| ④ 完成必须异会话 | 复核席 == 执行席直接拒 | R10 |

**当前数字**：闸门 **16 道**（语法 / 子命令烟测 / 界面语法 / 回归 / 反向测试 / 断点续跑 /
多项目 / 并发隔离 / 接口契约 / 点对点评审 / **留言** / **租约竞态** / **预算与依赖** / **安全反向** / 审计 / 体检），回归 **24 条**，
`tools/`＋`tests/` 共 31 个 py 文件；界面契约 25 条；留言闸 17 条；租约竞态闸 14 条；预算/依赖闸 31 条；
安全反向 8 组 21 条；子命令 29 条。

---

## 五、没做的（明确记录，不是遗忘）

| # | 缺口 | 说明 |
|---|---|---|
| 1 | 无常驻调度器 | 靠手动 `run-all` 或托盘「跑一轮」；用户明确暂不做守护进程 |
| 2 | 无权限模型 | 能访问机器就能改库 |
| 3 | 无跨机同步 | 假设同一台机器 |
| 4 | 托盘图标 / 桌面快捷方式**未被人点过** | 会往桌面弹东西，只能用户自己双击验证 |
| 5 | `ui.html` 内联 JS 未转 TS | 转 TS 要引构建步骤，破坏零依赖，待拍板 |
| 6 | ~~未吸收 `ocs` 的跨会话消息~~ | **已做（D-014）**：语义抄全、传输换成「续会话唤醒」；见 `tools/messages.py` |
| 7 | 改后核对只**记录**未改条数，不强制再改 | 有界设计，防无限循环；未改条数显示在看板上 |
| 8 | 评审意见没有「必改/可选」分级 | 全局一致性（人称/时态）容易被「不要整篇重写」挡掉——实测栽过一次 |
| 9 | 壳：无边框自绘标题栏未做 | 用户未选；现在是 Win11 原生边框 + 暗色标题栏（D-015） |
| 10 | 壳的托盘菜单 / 最小化行为**未被人手验过** | 会弹桌面物，只能用户自己点；`--selftest` 只证明了「能起、能渲染、DOM 对」 |

---

## 六、踩过并已记档的坑（详见 `ENVIRONMENT.md`）

- **E-24** 网页界面多项目串号（全局状态 + 每请求一线程）
- **E-25** 接口字段被当契约 / 首页白烧 CPU / 压测自重
- **E-26** 每请求重建 SQLite 连接＝纯税（已改固定线程池）
- **E-27** 反空跑闸把统计注释逼进产物（已按 D-012 改成机器测量）
- **E-28** WebView2 五坑（csc/net462、0 透明度自检、DLL 位置…）
- **E-29** 唤醒会话两点（未知 sessionID 会新建会话；重复唤醒＝重复回复）
- **E-31** 旧 server 进程还在 8777 ⇒ 新界面配旧接口报 not found
- **E-32** **在 UI 线程上等 WebView2 初始化＝双击卡死**（用户实报）；根教训是「自检不能另起炉灶」——现在自检与真实窗口共用 `BuildWindow + InitView`
- **E-33** 双击等 4 秒：窗口建在等后端之后 ＋ `HttpClient` 首次探活白等 1.5 秒（改 TCP 探活后 → 窗口 0.13s／页面 1.3s）
- **E-34** **「主键互斥」被超时自愈旁路**：并发 12 线程能有 4~6 个同时认领成功；教训＝自愈路径必须同事务＋带版本条件（CAS）
- **E-35** **接口忘了切项目根**：`/api/alert` 不切根就永远读到「上一个请求的项目」，壳收到的提醒恒为空（假绿：独立进程手工测是对的）
- **E-36** **`NotifyIcon` 没有 `BeginInvoke`**：它是组件不是 Control；要回 UI 线程得用一个隐藏 `Control` 先建句柄再 `BeginInvoke`

另有两条**行为**教训，不在环境文档里但在项目记忆里：

1. **上下文压缩后不要凭「文件比 HEAD 旧」就断定有别人在写**。本会话曾把提交 `64d6b2f` 误判成「另一个会话干的」，写进了提交信息 `e6fdb8e`。核对本机会话库后确认：那段时间只有本会话在活动，真相是压缩把那段工作裁出了视野。
2. **改文档只用追加，⛔ 不截断重写**。本会话用「截断到某标题再重写」的方式，真的删掉了自己先前写的 E-25 和 REGISTRY 一整段。

---

## 七、下一步最值得做的（按价值排）

1. **评审意见分级**（§五 #8）：让评审席输出 `MUST-FIX` / `OPTIONAL`，修改轮只许忽略 OPTIONAL。这能直接解决「人称混用改不掉」那类问题。
2. **壳的人手验收**（§五 #10）：托盘菜单、最小化/关闭收托盘、Ctrl+` 开终端 —— 这些只能你自己点。
3. **留言的「推送」**：现在是「开工先收信」（`orchestrator.py` 启动时 drain）。真正推送要常驻进程，用户明确暂不做守护进程。
4. **`ui.html` 内联 JS 转 TS**：需要引入构建步骤，与「零依赖双击就能跑」冲突，需拍板。

### 已做（本轮新增）

- **跨会话留言**（D-014）：`messages.py` / `msgwake.py` / `board msg …` / `/api/messages*` / 界面「留言」抽屉。抄 ocs 四条语义，传输换成「续会话唤醒」（`--session` 续接），唤不醒记 HELD。
- **桌面壳**（D-015）：`shell/`（WebView2 单 exe）、`open-board.cmd` 优先走壳、托盘「打开看板」优先走壳。
- **内置终端**：`tools/term.py` + `/api/term/*` + 界面底部抽屉（`Ctrl+`` 开合）。白名单、不走 shell、一次一条。

---

## 八、新会话开工顺序

1. 读 `AGENTS.md`
2. 读本文件
3. `python tools/check.py --quick` 确认基线没坏
4. 读 `DECISIONS.md` 最新几条（**D-013 / D-012 / D-001…**），不重问已拍板项
5. `git log --oneline -5` 对齐提交线

---

## 九、提交线（收工时）

```
fa4b65e  feat: cross-session messages + native shell + in-window terminal
ef179c7  docs: closeout - handoff, decisions and registry brought up to date
2059c90  feat: code-drawn icon + desktop shortcut
4aa1701  feat(ui): show the review at a glance
ce03beb  chore: ledger rows from the smoke runs
86ec93f  feat: meter the reviewers, verify the revision, stop dropping card fields
```

工作树干净；`doctor` 干净；13 道闸全过（语法已含 `shell/` 外的 28 个 py）。

**本轮留下的三张图**（人眼验收用，本地未入库）：
`board/shots/20261020-shell-page.png`（页面，0 透明度抓取）、
`board/shots/20261020-shell-window.png`（真窗口含标题栏）。

---

## 十、进行中的批次（压缩/换会话后从这里接）

> **2026-10-21 目录与命名已统一**：仓库＝文件夹＝`aII-work-together`（`E:\GithubClone\aII-work-together`），
> 全局注册表迁到 `~/.aII-work-together`；旧名 `allworktogether` 已从代码/文档中清零（D-020）。
> 下一步排队的：`docs/plan/20261020-fix-and-gaps.md` 的 C 批剩余项与「导出日报」（用户暂不做）。

**计划文件**：`docs/plan/20261020-fix-and-gaps.md`（A/B/C 三批 + 列布局都已完成）。

| 批 | 内容 | 状态 |
|---|---|---|
| **A** | 红线三洞（租约竞态 / submit 无租约 / reclaim 空转）＋ 终端白名单绕过 ＋ 旧布局迁移 ＋ L1 旧文件 ＋ 壳的旧版告警 | **已完成**（`40f1266`），闸门 13→14 |
| **B** | B1 预算/时长上限（P0）／B2 提醒／B3 错误分级／B4 拍板 diff／B5 卡间依赖 | **已完成**，闸门 14→15；见 D-016／D-017 |
| C | Q1 #6 托盘管道、#9 msg --json、#10 托盘 UI 线程、#11 _WriteTx、#12 端口透传 | **已完成**（除「起可见托盘验证」） |
| D | 看板列布局（只画有卡的列 ＋ 顶部筛选，D-018）／提醒声走系统音 | **已完成** |
| E | 多选批量（跑一轮／取消，D-019）＋ 端到端实跑验收 | **已完成**；导出日报按用户要求暂不做 |

**B 批交付要点（给人看的）**：
- 卡可以设「最多花多少美元／最多跑多少分钟」，超了当场停手转阻塞，原因里写清花了多少/上限多少；**放宽上限只能人来做**。
- 失败分了类：限流/超时/网络会自动退避重试 2 次；鉴权/参数类一次就停，不烧钱。
- 卡可以写「依赖哪几张卡」，上游没完成就不接，也不消耗尝试次数。
- 卡片详情有「这次改了什么」（认领前 → 现在的字节数），拍板时不用自己跑 git diff。
- 需要你拍板 / 卡住了 → 托盘气泡 ＋ 任务栏闪烁；跑完了没待拍板**不弹**。

**C/D 批交付要点（给人看的）**：
- 看板**不再横向滚动**：只画有卡的列，顶部一排状态筛选带张数，「拍板中」再也不藏在屏幕外（D-018）。
- 提醒带**声音**（Windows 自带提醒音），仍然只推「需要你拍板 / 卡住了」。
- 预算可以设**项目默认值**（`board project default --max-cost 1.5 --max-minutes 20`），新卡自动继承、单卡可覆盖、不设＝不限。
- 托盘侧的五个老毛病一起修了：后端管道不再堵死、托盘状态不再卡界面、`--json` 输出纯净、写库失败不漏连接、自定义端口透传给壳。

**还没验的一处**：托盘（`tray\boardtray.exe`）的**菜单点击**无法无头验证——只能你手动点一下「看看状态」确认不卡。
其余已由 `tray --selftest`（PASS）+ 编译通过兜住。

**E 批（2026-10-21）**：
- 多选批量：勾选框 →「跑一轮」只跑选中的（`orchestrator run --cards`）；「取消这些卡」要人令牌（同拍板）；
  ⛔ 不做批量删除（不可逆只能一张一张来）。
- 端到端实跑验收（真引擎）：临时项目 `%TEMP%\opencode\hello-run`，认领 → opencode 8 秒 → L1-L3 → 异会话复核 → 完成，
  `out/hello.txt` 177 字节、花费 $0.0058；卡片详情能看到「新增 out/hello.txt → 177B」。
- 导出日报：用户已明确**暂不做**，别自己加回来。
- 找卡：顶部搜索（卡号/标题/目标），输入即过滤；卡片显示「最后活动」，列内按活动倒序，超 12 小时没动标黄。
- 性能基线（2026-10-21 实测）：20 项目×15 卡时 首页 23ms／列表 5ms／详情 12ms。**没有瓶颈就没加缓存**。
- 卡内实时输出：编排器每张卡写 `board/evidence/<卡>/run.log`（线程局部上下文，并行不串卡），
  卡片详情 1.5 秒增量拉取（`/api/card/log?since=` 按字节），跑完自动停；不用再另开窗口看日志。
- 列内排序：最近活动／花费／时长／卡号（记忆选择）；卡面同时露出花费与时长。

---

## 十一、会话交接（2026-10-21 压缩前 · 下一次从这里接）

> 本块给**新主会话**读；派工单给子代理读，两者别混用。写完这一块，本会话不再改动任何文件。

### 11.1 基线（压缩时的真实状态）

| 项 | 值 |
|---|---|
| HEAD | `38158df`（工作树干净；仅 `docs/research/20261021-security-scan/` 故意不入库） |
| 闸门 | **16 道全绿**（`python tools/check.py --quick`） |
| 子命令 | 29 条（含新增 `token`） |
| 看板 | 本项目 5 张卡，`audit` 全查无绕过 |
| 模型口径（用户指定） | 引擎统一 `opencode`；弱＝`opencode-go/minimax-m3.1-flash-free`，强＝`opencode-go/deepseek-v4.1-flash` |
| 桌面 | 壳与托盘 `--selftest` 均 PASS；⛔ 托盘菜单点击**只能人手验** |

### 11.2 本会话已落地的四件事

1. **安全 23 条全修**（D-022）：HTTP 令牌＋Host 校验、卡号白名单、终端白名单、UPSERT 替 REPLACE、租约单调时钟、交付物路径限制、`review_only`、壳 scheme 白名单；新增第 16 道闸 `tests/test_security.py`。
2. **命名/目录统一**（D-020）：仓库＝文件夹＝`aII-work-together`，注册表 `~/.aII-work-together`。
3. **证据层级＋外问升级**（D-023）：`VERIFIED` / `AUDITED-UNGROUNDED` / `UNVERIFIED`；`--escalate-model/--escalate-after` 按**复核失败次数**触发。
4. **外问升级实验**：15 题题库＋隐藏检查器（两把尺 15/15）＋四臂 runner（W/G/M/S）；pilot 已跑；学界调研 30 篇。

### 11.3 实验现状（一句话：流水线可用，假设未检验）

- pilot：**弱模型 15/15 全对**（$0，662s）／强模型 15/15（$0.0263，262s）⇒ 题库对弱模型**已饱和**，升级 0 次触发。
- 结论：该任务族上**升级买的是时延（2.5×），不是正确率**。
- 文献（`docs/research/20261021-escalation-lit/`）：学界把题库区分度当**前置条件**，做法是**筛题**（只留历史通过率 30–70%），不是造更难的题；「误升级率」是空白；没人用墙钟当成本口径。
- ⛔ 不得引用 pilot 数字支持「级联更优/更差」。

### 11.4 压缩后的执行计划（按顺序，不要跳）

**P0 · 零成本（只改代码/流程，不调模型）**

> 进度（2026-10-21 晚，`fa42be2`）：第 1–4 条**已完成**，第 5 条**部分完成**（已加 6 道机械精确题，题库 21 题）。

1. `exp/run_experiment.py` 加 **V 臂**（弱＋同族自检 2 次但不升级）。✅ 已加（自检 1 轮，可调）
2. 聚合加三计数：`triggered` / `escalated_true` / `escalated_waste_unneeded` ⇒ **误升级率**。✅ 已加
3. 成本双记：`cost_actual`（免费记 0 且标 `cost_source=free`）、`cost_equiv`（价目表未取，**留 None 不编**）、`wall_clock`。✅ 已加
4. 新增 `exp/screen.py`：只跑 W，按 30–70% 带筛题。✅ 已加（`--repeat` 默认 3）
5. 扩题到 **40 题池**（现有 15 题都落在 >70% 带，必须补）：优先长上下文（≥4 文件、≥300 行）与需要外部事实核对的任务。🟡 已到 21 题（N01–N06 机械精确类），长上下文类**未做**

**P1 · 小额（$0.1 以内）**

6. 对筛后题库跑 `W/G/M/S/V` 五臂；先 `--validate` 再全量。
7. 出三张图/表：**等效成本 × 墙钟 × 通过率**帕累托；误升级率；同族复核放行率。
8. 用数据回填 `--escalate-after` 默认值（当前 2 是设计默认，不是实验结论）。

**P2 · 可选**

9. 筛后仍无区分度 ⇒ 换难度轴（长上下文/跨模块一致性），不要继续加同类题。
10. 结论只写进 `docs/research/20261021-escalation-experiment/`，对外材料禁用未证结论。

### 11.5 验收口径（新会话必须自己跑，⛔ 不采信任何自报）

```powershell
python tools/check.py --quick                                                   # 期望 16 道全绿
python "docs/research/20261021-escalation-experiment/exp/run_experiment.py" --validate   # 期望 15/15
& "shell\boardshell.exe" --selftest                                             # 期望 SELFTEST PASS
python tools\board.py audit                                                     # 期望 N 张卡全查、无绕过
```

### 11.6 领地与只读

- 本会话已改、**默认只读**：`tools/*.py`、`tools/ui.html`、`shell/BoardShell.cs`、`tests/*`、`docs/governance/{DECISIONS,REGISTRY,HANDOFF,ENVIRONMENT}.md`、`docs/research/20261021-*`。
- 改之前先读 `DECISIONS.md` 最新编号（当前到 **D-023**），新决定从 **D-024** 起。
- `docs/research/20261021-security-scan/` **只留本地**（用户明确「不必发」）。

### 11.7 交接时明确未拍板/未做

| # | 项 | 状态 |
|---|---|---|
| 1 | 实验 H1/H2/H3 | **未检验**（题库饱和） |
| 2 | `escalate_after=2` | 设计默认值，未用数据校准 |
| 3 | 托盘菜单点击 | 只能人手验，未验 |
| 4 | 渗透复测 | 未做（只有代码复核＋21 条反向测试） |
| 5 | README 是否加「常见问题」 | 未做，用户未表态 |

### 11.8 新会话开工顺序

`git log --oneline -3` → 本块 → `DECISIONS.md` D-020～D-023 → `python tools/check.py --quick` → 实验目录 `Pilot结果__20261021.md` → 按 §11.4 的 P0 开工。
