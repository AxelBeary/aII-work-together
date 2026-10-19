# HANDOFF.md — 会话交接块

> 给**下一个主会话**读。子代理读的是派工单，⛔ 两者不得混用。
> 最近更新：2026-10-20（收工批次）。上一次交接在 `04c2dc6` 之前。

---

## 一、一句话现状

**能用了。** 看板（网页 + 托盘 + 桌面快捷方式）、自主编排、点对点评审、多项目，全部跑通并有闸门守着。
剩下的是「没做」而不是「没做完」——见 §五。

---

## 二、五分钟跑起来

```cmd
看板.lnk                              :: 桌面快捷方式：起托盘 + 开网页
python tools/check.py --quick         :: 12 道闸（约 1 分钟）
python tools/check.py --perf          :: 再加规模压测（轻量 20×15）
orch run --max 3                      :: 让 agent 自己找活干
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
| `tools/server.py` + `tools/ui.html` | 本地网页界面（127.0.0.1:8777） |
| `tools/cli.py` | 26+ 子命令 |
| `tray/BoardTray.cs` | C# 托盘（编译约 14.8 KB，非 Electron） |
| `tools/make_icon.py` | 代码画图标（纯标准库） |
| `assets/board.ico` | 托盘与快捷方式共用图标 |
| `open-board.cmd` / `看板.lnk` | 一键启动 |
| `tools/check.py` | 一条命令跑 12 道闸 |
| `docs/怎么用.md` | 给人看的五分钟上手 |
| `docs/点对点评审.md` | 评审链路怎么用、为什么不是聊天室 |

数据：每项目 `board/board.db`；证据 `board/evidence/<卡号>/`；交付物在工作区。
全局注册表 `~/.allworktogether/registry.db`（可用 `ABOARD_REGISTRY_DIR` 隔离）。

---

## 四、四条红线（都有拒绝路径实测，不是口号）

| 红线 | 落地 | 测试 |
|---|---|---|
| ① 状态即证据 | L1 产物 / L2 形制 / L3 内容＋机器量反空跑；复核必须异会话且带凭据 | R04–R11、R24 |
| ② 人的拍板位不可越 | `human` 子命令 + 令牌；`guard_transition` 白名单 | R19、R20、R12 |
| ③ 认领即租约 | `leases.card_id` 主键；执行期后台心跳；`guard_holder` | R01、R21 |
| ④ 完成必须异会话 | 复核席 == 执行席直接拒 | R10 |

**当前数字**：闸门 **12 道**（语法 / 子命令烟测 / 界面语法 / 回归 / 反向测试 / 断点续跑 /
多项目 / 并发隔离 / 接口契约 / 点对点评审 / 审计 / 体检），回归 **24 条**，
`tools/`＋`tests/` 共 24 个 py 文件 ≈ 295 KB。

---

## 五、没做的（明确记录，不是遗忘）

| # | 缺口 | 说明 |
|---|---|---|
| 1 | 无常驻调度器 | 靠手动 `run-all` 或托盘「跑一轮」；用户明确暂不做守护进程 |
| 2 | 无权限模型 | 能访问机器就能改库 |
| 3 | 无跨机同步 | 假设同一台机器 |
| 4 | 托盘图标 / 桌面快捷方式**未被人点过** | 会往桌面弹东西，只能用户自己双击验证 |
| 5 | `ui.html` 内联 JS 未转 TS | 转 TS 要引构建步骤，破坏零依赖，待拍板 |
| 6 | 未吸收 `ocs` 的跨会话消息 | 见 §七 |
| 7 | 改后核对只**记录**未改条数，不强制再改 | 有界设计，防无限循环；未改条数显示在看板上 |
| 8 | 评审意见没有「必改/可选」分级 | 全局一致性（人称/时态）容易被「不要整篇重写」挡掉——实测栽过一次 |

---

## 六、踩过并已记档的坑（详见 `ENVIRONMENT.md`）

- **E-24** 网页界面多项目串号（全局状态 + 每请求一线程）
- **E-25** 接口字段被当契约 / 首页白烧 CPU / 压测自重
- **E-26** 每请求重建 SQLite 连接＝纯税（已改固定线程池）
- **E-27** 反空跑闸把统计注释逼进产物（已按 D-012 改成机器测量）

另有两条**行为**教训，不在环境文档里但在项目记忆里：

1. **上下文压缩后不要凭「文件比 HEAD 旧」就断定有别人在写**。本会话曾把提交 `64d6b2f` 误判成「另一个会话干的」，写进了提交信息 `e6fdb8e`。核对本机会话库后确认：那段时间只有本会话在活动，真相是压缩把那段工作裁出了视野。
2. **改文档只用追加，⛔ 不截断重写**。本会话用「截断到某标题再重写」的方式，真的删掉了自己先前写的 E-25 和 REGISTRY 一整段。

---

## 七、下一步最值得做的（按价值排）

1. **评审意见分级**（§五 #8）：让评审席输出 `MUST-FIX` / `OPTIONAL`，修改轮只许忽略 OPTIONAL。这能直接解决「人称混用改不掉」那类问题。
2. **吸收 `ocs` 的跨会话消息**：`leeguooooo/open-cross-session`（MIT，纯 TS，90 个 .ts）解决唯一没做的协作维度——跨会话发消息并**唤醒**对方。
   - 值得抄：append-only JSONL + 单调 seq；`wake: HELD` 语义（送达被拦要明说）；退出码分档且**一律不重发**。
   - ⚠️ 它依赖常驻会话的唤醒通道（Claude socket / Codex IPC）。我们的引擎是「起进程等结果」，短生命周期 ⇒ **不能直接照搬**。
3. **`ui.html` 内联 JS 转 TS**：需要引入构建步骤，与「零依赖双击就能跑」冲突，需拍板。

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
2059c90  feat: code-drawn icon + desktop shortcut
4aa1701  feat(ui): show the review at a glance
ce03beb  chore: ledger rows from the smoke runs
86ec93f  feat: meter the reviewers, verify the revision, stop dropping card fields
f92eb16  feat(gate): anti-empty check measures instead of demanding digits
c29b5f1  fix: review seat ran in the wrong directory
d64c95f  feat: point-to-point review
```

工作树干净；`doctor` 干净。
