# 设计评审：aII-work-together（单人多 agent 编排看板）

> 评审席：外部专家 · claude-opus-5-5 · 2026-10-20
> 口径：只读评审。读过 `tools/board.py`（L30–460、L640–850）、`tools/orchestrator.py`（L130–409）、`tools/parallel.py`（全文）、`tools/engines.py`（L100–179），并 grep 了全部 `tools/*.py`。**没有跑任何命令、没有复现**，下文写「代码可见」的都指读源码得出的结论，写「未证」的需要复跑确认。
> 外部资料：openai/symphony `SPEC.md`（2026-04 发布）、ACP 官方 agent 列表与 Python SDK 的 PyPI 页（2026-10 检索）。

---

## 结论先行（给产品主的三句话）

1. **大方向对，自造的部分大多该保留**。现成的「大轮子」（Temporal、Plane、CrewAI、A2A）对单人本机场景都是负收益，别引。
2. **真正该换的轮子只有一个：把 `journal.jsonl` 与租约换成 Python 自带的 SQLite**（零新依赖）。现在的地基在「多个进程同时写同一张卡」这件事上没有锁，这是后续一切并发问题的根。
3. 代码里有**两处会在真实使用中出事的缺陷**，优先级高于任何新功能：① 执行期间不发心跳，跑超 10 分钟的卡会被别人回收；② 并行模式下「修改已有文件」的卡必然被判冲突。

---

## 1 哪里在重复造轮子（逐项裁决）

| 自造部分 | 对照的现成方案 | 裁决 | 理由与接入代价 |
|---|---|---|---|
| 状态机（`replay()` 里的 if/elif） | Temporal / XState / Python `transitions` | **都不用，但要改写成表驱动** | Temporal 要起服务端＋数据库，单人本机过重；XState 是 JS；`transitions` 库带来的只是语法糖。问题不在「没用库」，而在**自己定义的 `TRANSITIONS` 白名单（board.py L66）没有被任何代码调用**——grep 只在定义处出现。`replay()` 对非法事件照单全收（例：任何状态下追加一条 `human` 事件都会直接变「完成」）。改法：`append_event` 前按 `TRANSITIONS` 查 (当前态, 目标态, actor)，不在表里就拒绝。约 40 行。 |
| 编排循环本身 | **openai/symphony `SPEC.md`** | **抄规范，不抄代码** | Symphony 绑 Linear＋Codex，不能直接用。但它的四个概念比现在的设计更成熟，值得逐字借过来：① 仓库内 `WORKFLOW.md`（YAML 头＋提示模板）＝派工单随代码版本化，替代 `build_prompt()` 里写死的提示；② **reconciliation（对账循环）**：每轮按卡片当前状态核对正在跑的进程，卡被取消/改状态就停掉对应进程——这正是你们缺的「停手」能力；③ 每卡一个隔离工作区；④ 成功不必然进 Done，可停在 handoff 态（对应你们的「拍板中」）。代价：读一遍 SPEC，改 orchestrator 主循环约 150 行。 |
| 事件溯源＋哈希链 | immudb / SQLite＋Litestream | **换 SQLite（stdlib `sqlite3`），哈希链降级为可选** | immudb 是独立服务，过重。Litestream 解决的是「复制到云端」，本项目禁远程，不相关。SQLite 的价值是**事务和跨进程锁**：`BEGIN IMMEDIATE` 天然串行化同一库的写；`UNIQUE(card_id, seq)` 让并发追加撞号时直接失败而不是分叉；认领可以写成一条 `INSERT INTO leases ... ` 带主键约束，比 `os.mkdir` 语义更清楚。卡片目录保留，只放 `card.json`、`artifacts/`、`evidence/`；事件和租约进 `board/board.db`（WAL 模式）。代价：改 `append_event / load_journal / claim / heartbeat / release / reclaim` 六个函数，约 300 行；`audit` 和 HTML 渲染改读库。哈希链说明见下。 |
| 哈希链本身 | git | **不值得继续加码** | 哈希是无密钥 sha256（L137–141），同一 Windows 用户下的 agent 能读源码、重算整条链，所以它只防「手抖改一行」，防不了「有意改写」。AGENTS.md §4.1 已诚实声明这一点，很好。别再往它上面投入。若真要锚定，正确的轮子是 git：收口时把链头哈希写进一次 commit 信息，git 本身就是外部哈希链。 |
| 多项目注册表＋零配置发现 | git 的向上找 `.git`、`platformdirs` | **保留自造** | 向上找 `board/cards` 就是业界通用约定（git、npm、cargo 都这样），没有更好的轮子。唯一小改：Windows 上惯例是 `%APPDATA%\aII-work-together\projects.json`，不是 `~/.aII-work-together`；不改也不出事，属于可选。 |
| 引擎适配层 | **ACP（Agent Client Protocol）** / A2A | **现有两家保留 CLI 解析；第三家起一律走 ACP；A2A 不碰** | ACP 官方列表已收录 OpenCode、Qoder CLI、Hermes Agent、Codex（经适配器），覆盖你们全部四家。它提供统一的会话、流式更新、取消、权限请求——尤其**流式更新可以直接当心跳**，正好修掉下文风险 1。但 Python SDK `agent-client-protocol` 依赖 pydantic、要求 Python ≥3.10、1.0 仍是 rc（2026-10-12 rc3），与「零依赖 3.9+」冲突。裁决：现在不迁；**不再为任何新引擎手写回执解析器**，hermes 接入时直接走 `hermes acp`（stdio JSON-RPC，可以先用 stdlib 手写最小客户端约 200 行，不引 SDK）。A2A 是跨组织网络协议，单机无收益（与记忆里「不追 A2A」一致）。 |
| 看板 UI（静态 HTML） | Plane / Focalboard API | **静态 HTML 保留，不引外部看板** | Plane 自托管要 Postgres＋Redis＋MinIO 的 docker 栈，对单人 Windows 是纯负担；Focalboard 独立版已基本无人维护。更重要的是：一个带「批准」按钮的本地 Web 服务，agent 也能用 curl 调，会直接打穿红线②。静态只读页＋CLI 拍板是对的设计。要改的是页面**内容**，见第 4 节。 |
| 专家团 / 多角色 | CrewAI / AutoGen / LangGraph | **保留自造** | 这三者都是「直接调模型 API」的框架，引进来等于绕开 opencode/qoder 已有的工具、权限、订阅额度，还要再管一份 API 钥匙。你们的形态（提示词库＋调 CLI＋取最严）就是这些框架里 "reviewer/critic" 模式的最小实现，100 行足够。真正的问题不是框架，而是**专家团全部用同一个引擎、同一个模型**（orchestrator.py L230 传的是执行席同款 `engine, model`），六个角色本质上是同一个模型换六种口吻，错误高度相关。改法：复核默认换引擎（opencode 执行 → qoderclicn 复核，反之亦然），这是一行配置的事，收益比加角色大。 |

---

## 2 哪些自造是对的（不该引外部依赖）

- **卡片＝目录、产物与证据落盘**：用户不读代码，但要能「双击打开看交付物」。文件夹是非程序员唯一不需要学的界面。保留。
- **L1/L2/L3 闸门**：这是项目自己的业务规则（字节、编码、必含项），没有任何通用库懂你的验收口径。保留，但 L3 的「交付物里有任意一个数字就算非空跑」（board.py L443）太松——日期、版本号都满足。改成卡片声明 `min_counts`（例：「至少 5 个 `## ` 小节」）。
- **人闸令牌**：不引入身份系统是对的，单人本机引 OAuth/Windows Hello 不值。
- **引擎 CLI 调用里的 Windows 坑处理**（`.cmd` 走 `cmd /c`＋列表参数、提示走 stdin，engines.py L104–131）：这些是实测出来的本机事实，任何 SDK 都不会替你处理，留着。
- **注册表只存路径、删了不丢数据**：设计正确，避免了「中央库坏了全盘坏」。
- **零依赖本身**：对单人、非程序员维护者，「装不上依赖」是比「代码多 300 行」严重得多的故障。SQLite 在 stdlib 里，所以建议的唯一换轮子不破这条。

---

## 3 最大的三个设计风险

### 风险 1：租约和执行脱钩——长任务一定会被误回收（代码可见，未复现）

- `LEASE_TTL = 600` 秒（board.py L60），引擎调用 `timeout=1800` 秒（engines.py L135）。
- `orchestrator.run_one()` 在 `E.run(...)` 阻塞期间**从不发心跳**（grep `beat|heartbeat` 在 orchestrator.py 零命中）。
- 后果：任何一张跑超 10 分钟的卡，另一个 `orchestrator run` 或一次 `board.py reclaim` 都会判它超时并回收，然后**第二个引擎在同一个工作区同时改同一批文件**。
- 当前的唯一栅栏是 `submit` 检查 `holder == seat`（L649）。但记忆里的标准命令是 `--seat w1`，两个编排器都用默认席名时这道栅栏失效。`epoch` 已经记了（L334），但 submit/review 都不校验它。
- **修法（必须做）**：① `run_one` 起一个后台线程，每 `HB_INTERVAL` 秒调一次 `heartbeat()`，引擎返回后停；② `claim()` 返回 epoch，后续 `submit/review/release` 必须带上并比对，不等即拒（标准名：fencing token）；③ 席名默认带随机后缀或进程号，⛔ 让两个进程同名。

### 风险 2：同一张卡的事件追加没有锁，且坏行被静默吞掉（代码可见，未复现）

- `append_event()`（L144–161）是「读末行取 prev → 读全文算 seq → 追加」，三步之间无锁。执行席心跳、复核席写结论、`reclaim` 写回收、人敲 `human`，都可能同时写同一个 `journal.jsonl`。撞上时会出现重复 seq、两条指向同一 prev 的事件——哈希链分叉，`audit` 报「被篡改」。**真并发被报成篡改，会让人逐渐不再相信 audit**，这比没有 audit 还糟。
- `load_journal()` 遇到解析不了的行直接 `pass`（L132–133）。进程在写半行时被杀，那一行被静默丢弃，卡片状态静默回退一步。这违反 AGENTS.md §1.3「退化必须可见」。
- 加上第 1 节说的 `TRANSITIONS` 未生效，三者合起来是：**状态机的正确性目前只靠「大家都乖乖按顺序调用」**。
- **修法**：换 SQLite（第 1 节）一次解决三件事。若暂不换，最低限度：用 `msvcrt.locking` 给 journal 加文件锁；坏行改为报警并让该卡进「阻塞」；`append_event` 内调用转移表校验。

### 风险 3：worktree 并行只对「新建文件」的卡成立（代码可见，未复现）

- `parallel.collect()` 的冲突判定是「主树里已有该文件且字节不同 ⇒ 冲突」（L89–92）。凡是「修改一个已有文件」的卡，主树里必然有旧版、worktree 里必然是新版，于是**必判冲突、必进阻塞**。返工卡同理。
- worktree 基于 `HEAD` 创建（L60），工作区里未提交的改动 agent 看不到；无提交时退化为 `copytree` 整个工作区（L57），大项目上会很慢。
- 复核用 `cwd=ROOT`（orchestrator L231、L248），而执行用 `WORKSPACE` 或 worktree；当项目设置了独立 workspace 时，复核席看的目录与执行席不一致（未证，取决于 ROOT 与 WORKSPACE 是否相同）。
- **修法：把「逐字节比对」换成 git 本身**——这是本项目里第二个明确该用现成轮子的地方。每卡建分支 `card/<id>`，agent 在 worktree 里干完由编排器 `git commit` 交付物，收口时 `git merge --no-ff card/<id>`；git 的三方合并知道「基线是什么」，只有两卡真改了同一处才冲突，冲突时 `git merge --abort` 并判 BLOCKED。建 worktree 前要求工作区干净（`git status --porcelain` 为空），不干净就拒绝并行，⛔ 退化成 copytree。约 80 行，替换 `collect()`。

### 次要但要知道的

- **人闸是「同一用户下的君子协定」**：agent 与人同一 Windows 账户，能读 `~/.board-human.tok`，也能删 `board/.human-token.sha` 重新登记（L786 的提示语甚至告诉了它怎么做）。§4.1 已声明边界，这里只补一条廉价加固：`cmd_human` 要求 `sys.stdin.isatty()` 为真，并让人当场敲入卡号后四位确认。无头 agent 子进程通常没有终端，门槛会实质提高（未证，需在 opencode/qoder 的 shell 工具里各实测一次 `isatty`）。
- **规模**：`pick()` 每轮对每张卡全量 `replay()`，`append_event` 每次读两遍全文件。几百张卡无感，上千张卡会明显变慢。换 SQLite 后自然消失，不必单独优化。

---

## 4 只做一件事：做「拍板收件箱」

**这件事是：一个命令 `board inbox`（以及看板页顶部同内容的一栏），只列出此刻需要人的卡，每轮最多 3 张，每张用人话写清「它做了什么／证据数字／建议批还是驳／一行命令怎么批」。**

为什么是它而不是 SQLite：

- SQLite 和心跳修复是**正确性**问题，属于必须修的缺陷，不是「更接近单人最佳」的那件事——修好了也只是「不出错」。
- 「单人」的瓶颈从来不是 agent 吞吐，而是**人的注意力**。用户画像写得很清楚：非程序员、单轮最多拍 3–4 条、需要「免看代码即可验收」。现在的看板按 9 个状态平铺所有卡，人要自己找「拍板中」「阻塞」「返工 3 次」在哪，还要自己去 `evidence/` 里翻 JSON 才知道 agent 干了什么。
- 编排越自主，人越需要一个**唯一入口**来回答「我现在要做什么」。没有它，自主编排跑得越多，堆给人的东西越乱。

具体规格（可直接作为派工单的契约）：

1. 收件条件：状态为「拍板中」，或「阻塞」且原因为返工超限/并行冲突/引擎失败。按等待时长排序，**单次最多显示 3 张**，其余只显示「还有 N 张」。
2. 每张卡四行：一句话标题 → 交付物路径＋字节数＋L1/L2/L3 结果 → 复核席结论与理由（取 `review.note` 前 80 字）→ 可复制的批准/驳回命令。
3. 驳回时强制写一句原因，原因自动成为下一轮返工提示的一部分（现在 `human` 的 `note` 不进 `build_prompt`，人的意见到不了 agent）。
4. 收件箱为空时明确显示「0 张待你处理（共 M 张卡，其中进行中 K 张）」——带非零对照，符合反空跑纪律。

估算：读 journal、拼文本、加到 `render.py` 一栏，约 150 行，零新依赖。

---

## 建议执行顺序

| 顺序 | 事项 | 类型 | 估算 |
|---|---|---|---|
| 1 | 执行期心跳线程＋epoch 栅栏＋席名去重 | 缺陷修复（风险 1） | ~60 行 |
| 2 | `TRANSITIONS` 接入 `append_event`；坏行报警不吞 | 缺陷修复（风险 2 最低限度） | ~50 行 |
| 3 | 拍板收件箱 | 单人体验（第 4 节） | ~150 行 |
| 4 | journal＋租约迁 SQLite | 换轮子（风险 2 根治） | ~300 行 |
| 5 | 并行收口改 git 分支＋merge | 换轮子（风险 3） | ~80 行 |
| 6 | 复核默认换引擎；L3 改 `min_counts` | 质量 | ~30 行 |
| 7 | 借 Symphony 的 `WORKFLOW.md`＋对账循环 | 规范借鉴 | ~150 行 |

每一步都要配一条反向测试：1 用「伪造 11 分钟慢引擎＋第二个编排器」证明不再被回收；2 用「两进程各追加 100 条」证明 seq 无重复、链不分叉；5 用「两卡改同一文件不同行」证明能合并、「改同一行」证明判 BLOCKED。
