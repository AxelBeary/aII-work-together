# HANDOFF.md — 会话交接块

> 给**下一个主会话**读。子代理读的是派工单，⛔ 两者不得混用。
> 最近更新：2026-10-20（上下文压缩前落盘）

---

## 一、项目现在是什么

**一块看板 + 一个自主编排器 + 一个网页界面 + 一个托盘程序**，用来让本机/本团队的多个 AI agent 在同一个任务板上分工协作，全程可追责。

零依赖（Python 3.9+ 标准库 + Windows 自带 .NET）。

### 文件结构

| 文件 | 职责 | 行数 |
|---|---|---|
| `tools/board.py` | **核心**：卡片/状态机/journal/租约/闸门/守卫 | ~490 |
| `tools/cli.py` | 命令行层（26 个子命令） | ~1300 |
| `tools/storage.py` | **SQLite 存储层** | ~400 |
| `tools/projects.py` | 多项目注册表（SQLite）+ 工作区解析 | ~330 |
| `tools/engines.py` | 引擎适配：回执解析/会话续接/用量 | ~390 |
| `tools/experts.py` | 专家团（11 个角色） | ~190 |
| `tools/subagents.py` | 子代理（独立会话/并行） | ~145 |
| `tools/orchestrator.py` | 自主编排 | ~570 |
| `tools/resume.py` | 断点续跑 | ~200 |
| `tools/parallel.py` | worktree 并行 | ~170 |
| `tools/render.py` | 静态看板页 | ~180 |
| `tools/server.py` | **本地网页界面后端**（127.0.0.1:8777） | ~380 |
| `tools/ui.html` | **网页界面**（单文件，内联 CSS/JS） | — |
| `tools/check.py` | **一条命令跑完 7 道闸** | ~110 |
| `tray/BoardTray.cs` | **托盘程序源码**（C#，编译成 14KB exe） | ~300 |
| `tray/tray.cmd` | 编译 + 启动托盘 | — |
| `board.cmd` / `orch.cmd` | 免打长命令的入口 | — |

### 数据在哪

- 每项目 `board/board.db`（SQLite：cards / events / leases / lease_log / meta）
- 证据文件 `board/evidence/<卡号>/`
- 交付物在工作区里（普通文件）
- 全局注册表 `~/.allworktogether/registry.db`
- 人令牌 `~/.board-human-<who>.tok`

---

## 二、四条红线与它们的落地

| 红线 | 落地方式 | 回归用例 |
|---|---|---|
| ① 状态即证据 | L1 产物 / L2 形制 / L3 内容 + 反空跑；异会话复核且必须带凭据 | R04–R11 |
| ② 人的拍板位不可越 | `human` 子命令 + 令牌；`guard_transition` 白名单 | R19、R20、R12 |
| ③ 认领即租约 | `leases.card_id` PRIMARY KEY；执行期后台心跳；`guard_holder` 防旧执行者 | R01、R21 |
| ④ 完成必须异会话 | 复核席 == 执行席 直接拒 | R10 |

---

## 三、当前状态（2026-10-20）

- **回归库 23 条全过**，反向测试能抓到注入故障
- **多项目压测 9 条全过**（12 个项目 / 注册表 8 线程并发 / 工作区还原）
- **界面并发隔离通过**（两项目并发建卡零串号；拆掉锁会转红）
- `board` / `orch` / 网页界面 / 托盘 全部可用
- 看板上 4 张历史卡（G1–G4）全部完成，`doctor` 干净
- 提交线：`af27eb4`（网页界面+托盘）

### 怎么验证

```cmd
python tools/check.py            :: 9 道闸全量
python tools/check.py --quick    :: 跳过真调模型
```

---

## 四、还没做的（明确记录，不是遗忘）

| # | 缺口 | 为什么没做 |
|---|---|---|
| 1 | **没有常驻调度器** | 现在靠手动 `run-all` 或托盘「跑一轮」。真团队需要定时器 |
| 2 | **没有权限模型** | 能访问机器就能改任何项目的库 |
| 3 | **没有跨机同步** | 假设同一台机器 |
| 4 | 托盘图标**本人未实测** | 会往桌面弹图标，等用户自己双击验证 |
| 5 | `ui.html` 的内联 JS 未转 TS | 转 TS 要引构建步骤，破坏零依赖，**待用户拍板** |
| 6 | 未吸收 `ocs` 的跨会话消息 | 见下节 |

---

## 五、下一步最有价值的一件事：吸收 `ocs`

`leeguooooo/open-cross-session`（MIT，25★，90 个 .ts 零 .js）解决我们**唯一没做的协作维度**：跨会话发消息并**唤醒**对方。

值得抄的三点（不是抄代码，是抄设计）：

1. **append-only JSONL + 单调 seq**，`--reply-to <seq>` 跨 harness 可寻址
2. **`wake: HELD` 语义**：送达被拦时明确告诉发送方「没送到」，不假报成功
3. **退出码分档**：0 送达 / 2 已存但唤醒失败 / 3 结果未知 —— **一律不重发**，按 seq 查

⚠️ 它需要各 harness 的唤醒通道（Claude 的 Unix socket / Windows 命名管道、Codex Desktop IPC 等）。**我们目前的引擎调用是「起进程等结果」，没有常驻会话可唤醒** ⇒ 直接照搬不成立。要先想清楚：我们的 agent 是短生命周期进程，还是常驻会话？

---

## 六、关键教训（已写入 ENVIRONMENT.md，按编号）

1. 「用了原子 API」≠「实现了原子性」（`mkdir` 名字带 uuid、单例没加锁）
2. 「端到端跑通」≠「防线有效」（跑通后专家团抓出 5 个 bug）
3. 「定义了」≠「生效了」（`TRANSITIONS` 写了但从没被调用）
4. 「打桩测试通过」≠「真跑可用」
5. 退出码**权重 0**，判成败只读结构化回执
6. `opencode` 不带 `--model` 会走免费池被 IP 封禁
7. `qoderclicn` 带 `--no-session-persistence` 就无法续接

---

## 七、新会话开工顺序

1. 读 `AGENTS.md`（纪律入口）
2. 读本文件
3. `python tools/check.py --quick` 确认基线没坏
4. 看 `docs/governance/DECISIONS.md` 最新几条，确认哪些已拍板
5. **不要重问已拍板的事**（D-001…D-011）
