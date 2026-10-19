# P4 · 三个指定产品调查（ekko studio／MetisAgent／毕方 BitFun）

- 席号：**调研席 E** ｜ 调查日期：**2026-10-19**（全部访问/抓取时刻见 §6）
- 派工单：`P4_三个指定产品调查.md` ｜ 父总单：`00_派工总单.md`
- 结论口径：只报**本次实测抓到的**；推断一律标「推断」。数字全部带抓取时刻。

---

## ① 能力边界与证据降级档位

### 1.1 本轮实际用了哪些手段（可复算）

| 手段 | 用途 | 本轮状态 |
|---|---|---|
| `websearch`（网页检索） | 首轮定位、同名扩散 | 可用，共发起 12 次查询 |
| `webfetch`（抓正文） | 官网／README／文档正文 | 部分站点超时（见 1.2） |
| GitHub REST API（`api.github.com/repos/...`） | star／fork／license／created／pushed／open_issues | **可用且为准**（比页面数字稳） |
| GitHub 页面 HTML（`github.com/...`） | 取 Commits 总数 | 可用 |
| `raw.githubusercontent.com` | 抓 README／LICENSE／docs 原文做关键词计数 | 可用 |
| `registry.npmjs.org` | 取 npm 最新版本号＋许可证 | 可用 |
| `pypi.org/pypi/<pkg>/json` | 取 Python 包作者／许可证／版本史 | 可用 |

### 1.2 证据降级档位（如实报，别当全绿读）

| 档 | 含义 | 本轮命中 |
|---|---|---|
| **A 档：官方一手 + 机器可复核** | GitHub API／npm registry／PyPI JSON／raw 文件原文 | ekko studio、Metis、BitFun 三者的 star／license／版本／提交时间全部 A 档 |
| **B 档：官方一手但需人读** | 官网首页、README 正文、官方文档 | 三者的产品能力描述均为 B 档（厂商自述） |
| **C 档：第三方转述** | 新闻稿、技术博客、导航站 | 仅用于「广州实验室毕方」的定位（A 档缺失，见 §2.3） |
| **未取到** | 抓取失败／不存在 | ① `github.com/EKKOLearnAI/ekko-studio` 页面 HTML 直连两次超时（改用 API + raw 成功）；② `metisagent.co` 直连 Transport error（只有检索摘要）；③ BitFun Playbook 的 `task-board` 子页 404（导航里列出但正文取不到）；④ `zhuanlan.zhihu.com` 403 |

> **降级声明**：本报告所有「能力」判断来自**厂商自述文本 + 代码文件存在性**，**没有一处来自实际部署试用**（派工单禁止 clone／安装）。凡我写成「有」，指「官方文档写明有且能找到对应代码/配置入口」，不等于「我跑通了」。

### 1.3 反空跑（非零计数，先自证量具没瞎）

| 计数项 | 数值 | 口径 |
|---|---|---|
| 三目标候选条目总数 | **18 个** | ekko 5 ＋ Metis 6 ＋ 毕方 7；逐个列于 §2，可回读 |
| 其中判为「本轮目标」 | **3 个** | 一目标一个，无遗漏 |
| 其中判为「同名不同实体」而剔除 | **14 个** | 18 − 3 − 1（额外独立实体「广州实验室毕方」单列保留） |
| 定位成功并建表的目标 | **3 of 3** | 派工单要求的「不许只写两个」已满足 |
| 额外记录的**独立同名实体** | **1 个**（广州实验室「毕方」） | 与 BitFun 无公开关联证据，单列不合并 |
| 明确回答的同名疑问 | **1 条**（ekko studio ≠ Ekioo） | §2.1 |
| 判 `可用` | **0 个** | — |
| 判 `部分可用` | **2 个**（ekko studio、Metis） | — |
| 判 `不可用`（对看板用途） | **1 个**（BitFun） | — |
| 判 `未证` | **0 个** | — |
| 「毕方＝BitFun 中文名」这条命题 | **未能证实（0 条正面证据）** | 见 §2.3、§5 |

**量具对照（必须非零）**：为确认「关键词计数」这把尺没坏，我对同一份 Metis 源码做了正向对照——`src/core/performance-runtime.ts`（119,121 字节）中 `G7` 命中 **45** 次、`receipt` 命中 **68** 次、`FALSE_COMPLETION_BLOCKED` 命中 **1** 次。若计数函数失效，这三个数会同时为 0；它们非零 ⇒ 计数尺可用 ⇒ 下面对 BitFun／ekko 报出的「0 次命中」才可信。

---

## ② 同名甄别结论（先甄别，再谈能力）

### 2.1 `ekko studio` 与 `Ekioo`：**不是同一家。明确分开写。**

这是派工单点名必须回答的问题，答案是**否**，依据是四条互相独立的硬证据：

| 比对项 | ekko studio（本轮目标） | Ekioo（KittyClaw 作者） |
|---|---|---|
| 主体 | GitHub 用户 `EKKOLearnAI`（id 152005280，name=`ekko`，2023-11-25 注册） | GitHub 用户 `Ekioo`（name=`EKIOO`，2026-03-03 注册，**仅 1 个公开仓库**） |
| 官网 | `https://ekkostudio.xyz`（API `homepage` 字段） | `https://ekioo.com`（API `blog` 字段） |
| 代表产物 | Ekko Studio（多 agent 工作台，TypeScript／Vue3） | KittyClaw（本地看板，**.NET 10／Blazor Server**） |
| 许可 | **BSL-1.1**（源码 LICENSE 原文，2029-05-10 转 Apache-2.0） | **AGPL-3.0**（API `license.spdx_id`） |
| 交叉引用 | 全站／README 中未出现 `Ekioo`／`ekioo.com` | `ekioo.com` 的 Projects 页未出现 Ekko Studio |

补充反证：Ekko Studio 的 README 明写 **「Ekko Studio was previously named Hermes Studio / Hermes Web UI」**——它的前身是 Hermes Studio，与 Ekioo 的 KittyClaw 毫无传承关系。两者只是名字字母相近（ekko／ekioo），**是巧合，不是同一家**。

> **顺带纠一个首轮可能踩的坑**：`ekko.studio`（无 `k` 前缀差异，是 `ekko` 不是 `ekko studio` 产品）是**美国密歇根 Grand Rapids 的一家设计咨询公司**（2018 年成立，20 人，Tracxn 记录）。它和 `ekkostudio.xyz` 也是两家。第三个近似体 `eckko.fr` 是法国播客录音棚。**三个「ekko」不是一家。**

### 2.2 `ekko studio` 候选清单（5 筛 1）

| # | 候选 | 是不是本轮目标 | 判定依据 |
|---|---|---|---|
| 1 | **EKKOLearnAI/ekko-studio**（ekkostudio.xyz） | **是** | 唯一同时满足「叫 ekko studio」+「做多 agent 工作台」+「有公开仓库」 |
| 2 | EKKO Studio（ekko.studio，美国设计咨询） | 否 | 行业＝管理咨询／体验设计，无 agent 产品 |
| 3 | Eckko Studio（eckko.fr，法国录音棚） | 否 | 行业＝影视录音 |
| 4 | ekko.zone（Ekko 产品套件） | 否 | 是「Protocol Ops／Alert Studio／WalletAlert」安全运营套件；其 `Agents` 页面标注 **COMING SOON**，且定位是「解释信号、给有界建议」，不是多 agent 看板 |
| 5 | **Ekioo**（ekioo.com） | 否 | 见 §2.1，KittyClaw 作者，另一家 |

### 2.3 `毕方 BitFun`：**「毕方」与「BitFun」在公开材料里对不上号——这条必须如实报。**

派工单要求「先列候选再定位」。我把「毕方」和「BitFun」当成**两个可能重合的名字**分别查，结果如下。

**候选清单（7 筛 2）**：

| # | 候选 | 是什么 | 与「毕方 BitFun」的关系 |
|---|---|---|---|
| 1 | **GCWing/BitFun → GCWing/OpenBitFun**（openbitfun.com／bitfun.work） | 开源桌面 AI Agent 工作台，Rust + Tauri | **BitFun 这一半已定位**（见 §3.3） |
| 2 | **广州实验室「毕方（AI Biologists）」一站式多智能体科研工作台** | 科研机构自研平台，2026-09-22 在广东省 AI 应用对接大会发布 | **「毕方」这一半已定位**，但**与 BitFun 无任何公开关联** |
| 3 | 毕方AI（bifangshenhua.com） | AI 出图／私有风格训练，付费 | 无关（不是 agent） |
| 4 | 毕方智能云沙箱 Bold-Falcon（PowerLZY/Bold-Falcon，BSD-3-Clause，162★） | 自动化恶意软件分析 | 无关 |
| 5 | gitee `bifang`（aguncn/bifang） | 自动化软件部署平台 | 无关 |
| 6 | gitee `bifang`（yyzh/bifang） | SpringBoot 后端框架 | 无关 |
| 7 | 毕方资源网（bfbke.com）／毕方AI助手 | 资源下载站＋站内 AI 助手 | 无关 |

**关键否定证据（这条最该被复核）**：我在 BitFun 的**三处官方中文材料**里逐字计数「毕方」：

| 材料 | 长度 | 「毕方」出现次数 |
|---|---|---|
| `raw.githubusercontent.com/GCWing/BitFun/main/README.zh-CN.md` | 4,835 字符 | **0** |
| `raw.githubusercontent.com/GCWing/BitFun/main/AGENTS-CN.md` | 13,186 字符 | **0** |
| `openbitfun.com` 首页 HTML | 1,754 字符 | **0** |
| `raw.githubusercontent.com/GCWing/OpenBitFun/main/README.zh-CN.md` | 4,835 字符 | **0** |

同时 GitHub 仓库搜索 API 查 `毕方 agent` 得 **total_count = 0**；查 `bifang multi-agent` 得 **0**；查 `openbitfun` 得 4 条（全是 BitFun 生态本身及其周边 Mini App／skill，无一条叫毕方）。

⇒ **结论**：BitFun 官方从未自称「毕方」。若用户是从某个渠道（某篇中文介绍、某个群、某份名单）看到「毕方 BitFun」连写，**该来源我未能定位**，请提供出处，我再回源核。**在此之前，我不能把这两个名字合并成一个条目**——这正是派工单禁止的事。

**而广州实验室的「毕方」是一个真实存在、且真的在做「多智能体」的独立实体**，值得单列（下表），但它是**机构内部科研平台**，无公开仓库、无许可证、无 star 数据，证据只到 C 档。

---

## ③ 三张维度表（定位到的每个实体一张）

### 3.1 表一 · Ekko Studio（EKKOLearnAI）

| 维度 | 内容 |
|---|---|
| **正名＋归属** | **Ekko Studio**；GitHub 用户 `EKKOLearnAI`（个人账号，非组织）。仓库 [github.com/EKKOLearnAI/ekko-studio](https://github.com/EKKOLearnAI/ekko-studio)（2026-10-19 访问）；官网 [ekkostudio.xyz](https://ekkostudio.xyz/)；npm `ekko-studio`。**曾用名 Hermes Studio／Hermes Web UI**，旧仓库 `EKKOLearnAI/hermes-studio` 仍在。 |
| **它到底是什么** | 一个**本地优先的多 agent 工作台**：把 14 种编码 agent 接进同一个界面，能单聊／群聊／拉可视化工作流，带 Kanban 看板、定时任务、审批门。桌面端（Win/mac/Linux）＋自托管 Web 控制台＋手机端。 |
| **与我们的关系** | **正面竞品，且是三件里最接近的一件**。它已经做出了「多引擎同屏 + 看板 + 审批门 + 运行快照回放」这套外壳，但缺我们红线里的租约与心跳。 |
| **形态与部署** | 桌面 App（Tauri 类）／`npm i -g ekko-studio` + `ekko-studio-web start`／Docker。**自托管可行**（本地 SQLite 存会话）。 |
| **agent 接入** | **有通用适配层**：README 列出 Claude Code、Codex、Pi、Grok、OpenCode、DeepSeek Harness（DSH）、Qwen Code、Kimi Code、CodeBuddy、GitHub Copilot CLI、ZCode、Cursor、Qoder、Antigravity，加内置的 Ekko Agent 与 Hermes Agent。运行时通过 runtime adapter 分发（Socket.IO `/chat-run`）。**这是「跨引擎」这一条目前见过做得最宽的。** |
| **协作模型** | 有 **Kanban 看板**（「Profile-aware Kanban board for planning and tracking agent work」，但底层用的是 **Hermes Kanban CLI 及其任务存储**，不是 Studio 自研状态机）；有**群聊房间**与**全局 agent 编排**；有**审批门**（workflow 里的 approval gates、任务卡上的 approval prompts）。**没有找到「认领／lease／心跳／超时回收」的任何文字或字段**——README 全文按词边界数：`heartbeat`=0、`reclaim`=0、`lease`=0、`leases`=1，且那唯一一处是「per-tab control **leases**」（浏览器标签页控制租约），与任务认领无关（另 8 处 `lease` 子串来自 `releases` 一词，非租约义）。 |
| **完成判据** | **偏「有证据可看」而非「无证据不准完成」**：有冻结运行快照（frozen run snapshots）、节点对话、边决策记录、画布上的**证据回放**（evidence playback）、运行预算/截止/停止重跑、持久执行历史。**但没有找到「无凭据则禁止进入 Done」的闸门**。 |
| **许可** | **BSL-1.1（Business Source License 1.1）**。LICENSE 原文：非商业用途（个人／教育／研究）免费；**商业用途（含 SaaS 托管、嵌入商业产品）须另购商业许可**；Change Date **2029-05-10** 自动转 Apache-2.0。GitHub API 的 `license.spdx_id` 报 `NOASSERTION`（因为 BSL 不是 OSI 许可），npm 报 `BSL-1.1`。 |
| **活跃度（亲眼所见，2026-10-19 17:0x +08:00）** | star **11,470**、fork **1,417**、open issues **485**、commits **1,674**（仓库页 HTML）、created **2026-04-11**、pushed **2026-10-19T08:00:49Z**、语言 TypeScript。npm 最新 **0.7.37**（registry `time.modified` = 2026-10-19）。 |
| **可用性判定** | **`部分可用`** |
| **最有价值点** | ① 14 种引擎的 runtime adapter 目录——「跨引擎接入」这块不用自己从零摸；② 审批门 + 冻结运行快照 + 证据回放，是「状态即证据」的现成 UI 范式。 |
| **最致命缺点** | **许可**：BSL-1.1 意味着只要我们的看板将来带一点商业色彩（哪怕只是内部收费工具），就得先谈许可；这不是技术问题，是法律问题，且 2029 年前一直存在。技术上第二致命：**它没有任务级租约与心跳**，两个 agent 抢同一张卡它拦不住。 |

**四条红线逐条点名**：

| 红线 | Ekko Studio | 依据 |
|---|---|---|
| 跨引擎统一认领 | **半条**：跨引擎「接入」做到了 14 种；「认领」没有 | README 有 agent catalog，无 claim/assignee 互斥语义 |
| 心跳回收 | **无** | 全文无 heartbeat／timeout reclaim |
| 完成即证据 | **半条**：有证据呈现与回放，无「无证据不准 Done」的硬闸 | 有 evidence playback，无 gate 阻断 |
| 人的审批位不可越 | **半条**：有 approval gate（工作流级） | 是流程约定，不是「只有人能推进某列」的权限不变量 |

---

### 3.2 表二 · Metis（Wholiver）

> 甄别说明：`MetisAgent` 这串字符**不是任何一个产品的正式名**，而是**域名**。`metisagent.tech` 指向本表这一家，故取它为目标。其余同名候选见 §2.2 之后的清单（本节末）。

| 维度 | 内容 |
|---|---|
| **正名＋归属** | **Metis**（自称 Metis 2.0）；作者 GitHub 用户 `Wholiver`（个人，id 126302682）。仓库 [github.com/Wholiver/metis](https://github.com/Wholiver/metis)（2026-10-19 访问）；官网 [metisagent.tech](https://metisagent.tech/)；npm `@wholiver_hu/metis`。**基于 [pi](https://github.com/earendil-works/pi)（Mario Zechner）二次开发**（README 自述）。 |
| **它到底是什么** | 一个**编码 agent 本体**（不是看板）：桌面 App ＋终端 TUI ＋可装进 Codex／OpenCode／DeepSeek Harness 的 Skill 三种形态；内部是一个**5 角色递归多智能体体系**（coordinator／planner／implementer／reviewer／verifier），跑在 Git worktree 隔离里。 |
| **与我们的关系** | **不是竞品，是可借鉴件——但它恰好补的是我们最想要的那一块：「完成即证据」的机械闸门。** |
| **形态与部署** | 桌面 App（.dmg／.exe，内置运行时）／`npm i -g @wholiver_hu/metis`（需 Node ≥22.19）／`metis-skill` 装进别的 agent。**自托管＝本地跑，无服务端**。 |
| **agent 接入** | **反向的**：它不是「接入别人」，而是「被别人接入」（`metis-plugin install codex|opencode|deepseek`）。内部多 agent 靠 `spawn_agent` 递归（L0→L4），有 `SpawnGuard`：`max_spawn_depth` 默认 5、`max_children_per_agent` 默认 8、`max_concurrent_agents` 默认 4。 |
| **协作模型** | **有派活、有隔离、无看板、无租约**。派活＝coordinator 拆解后 `spawn_agent`（sync／async）；隔离＝`worktree: inherit|branch|temp`（物理 Git worktree，含未提交与未跟踪文件快照）；生命周期＝`list_agents`／`wait_agent`／`kill_agent`（cascade 默认杀整个 PGID）；防跑飞＝`SpawnGuard` 三道上限 + 重复任务检测（`DUPLICATE_TASK_WARNING`）+ 孤儿进程回收（SIGINT/SIGTERM/exit 处理器）。**心跳？无。超时回收？无（只有 wait 的 timeout）。** |
| **完成判据** | **这一项是三件里唯一做到「机械闸门」的**。README 原文：内置 **G0–G7 验证状态机**；`FALSE_COMPLETION_BLOCKED` 会拦截「无凭据的完成」；「Even if an LLM outputs “all tests passed”, Metis verifies the exit code, test stdout, and diff boundaries」；缺 receipt 就强制返工。带多模态证据（内置 ffmpeg/ffprobe 视频抽检、截图断言）。**我复核了代码存在性**：`src/core/performance-runtime.ts` 119,121 字节，`G7` 命中 45 次、`receipt` 68 次、`gate` 225 次、`FALSE_COMPLETION_BLOCKED` 1 次 ⇒ 这不是 README 吹的，代码里真有这套东西。 |
| **许可** | **MIT**（API `license.spdx_id` = `mit`；README 徽章亦 MIT）。 |
| **活跃度（亲眼所见，2026-10-19 17:0x +08:00）** | star **403**、fork **35**、open issues **7**、commits **184**、created **2026-07-11**、pushed **2026-10-16T04:43:03Z**、语言 TypeScript。最新提交信息 `chore(release): v2.0.2`（2026-10-16T04:42:24Z）。npm 最新 **2.0.2**，共 **77** 个版本。 |
| **可用性判定** | **`部分可用`** |
| **最有价值点** | **G0–G7 receipt 状态机 + `FALSE_COMPLETION_BLOCKED`**——把「完成」从一句自述变成一个必须交出退出码/测试 stdout/diff 边界才能通过的状态转移。这正好是我们红线 1（状态即证据）想要的东西，且**可以直接照抄设计，不必照抄代码**。 |
| **最致命缺点** | 它**不是看板**：没有卡、没有列、没有认领、没有心跳，一张卡在多 agent 之间怎么流转它不管。而且**它自己承认这套治理会反噬**——仓库 `docs/ale-metis-agent-failure-modes.md` 原文：在官方 ALE 跑批里，**32 个零分任务中有 27 个「写了文件但没通过隐藏评分器」**，作者把首因写成「performance-governance 在每道长任务上默认开启，会话文本被 ROADMAP／G2 assurance 占据，模型花回合协调人格而不是读任务契约」，并出现 `MAX_CHILDREN_EXCEEDED`（约 13 个任务）。⇒ **闸门能挡「没跑就宣称完成」，挡不住「跑了但跑错」；而且治理开销本身会吃掉产出。** 这条对我们极重要：别把闸门做成仪式。 |

**四条红线逐条点名**：

| 红线 | Metis | 依据 |
|---|---|---|
| 跨引擎统一认领 | **无** | 无卡、无 claim；它只调度自己 spawn 的子 agent |
| 心跳回收 | **无** | 只有 `wait_agent` 的 timeout，不是心跳 |
| 完成即证据 | **有（三件里唯一）** | G0–G7 receipt + `FALSE_COMPLETION_BLOCKED` + 验退出码/stdout/diff，代码实证存在 |
| 人的审批位不可越 | **无** | reviewer 是 agent，不是人；无「只有人能推进」的列 |

**MetisAgent 同名候选清单（6 筛 1）**：

| # | 候选 | 是什么 | 判定 |
|---|---|---|---|
| 1 | **Wholiver/metis**（metisagent.tech） | 编码 agent + 5 角色递归 + G0–G7 闸门 | **采纳为本轮目标** |
| 2 | metisagent.co | 「Solana 代币化市场的自主研究 agent」，观察→调查→发布带证据的研究 | 同名不同实体（区块链研究 agent），非编码／非看板 |
| 3 | `metis-agent`（PyPI，作者 Metis OS Team，`cjohnson@metisos.com`，仓库 `metisos/metisos_agentV1`） | Python agent 框架，Apache-2.0，12★，**最后上传 2025-09-28**，已近一年无更新 | 同名不同实体，**停滞** |
| 4 | withmetis.ai（Metis） | 企业 agent 的「后训练 + 持续学习 + 评估」层，产品名 Insight | 同名不同实体（研究实验室，闭源） |
| 5 | NaCode-Studios/metis-benchmark | 一个预测市场／预测模型的 G0 回测报告仓 | 同名不同实体（只是也用了 G0 这个词，**与本表目标的 G0–G7 无关联**，勿混） |
| 6 | 「Metis Community（QQ 801193315）」 | 表一目标自己的社区群 | 属于候选 1，非独立实体 |

---

### 3.3 表三 · BitFun／OpenBitFun（GCWing）

> 甄别说明：`GCWing/BitFun` 与 `GCWing/OpenBitFun` 是**同一个仓库**——`api.github.com/repos/GCWing/BitFun` 返回的 `full_name` 直接是 `GCWing/OpenBitFun`（GitHub 重命名重定向）。旧名 BitFun，新名 OpenBitFun，版本线 0.2.x → 1.0.x（官方提供 0.2.17–0.2.19 的数据迁移器）。**「毕方」与它无公开关联，见 §2.3。**

| 维度 | 内容 |
|---|---|
| **正名＋归属** | **OpenBitFun**（旧名 **BitFun**）；作者 GitHub 用户 `GCWing`（个人，id 29406332）。仓库 [github.com/GCWing/OpenBitFun](https://github.com/GCWing/OpenBitFun)（2026-10-19 访问）；官网 [openbitfun.com](https://openbitfun.com/) 与 [bitfun.work](https://www.bitfun.work/)（后者主打鸿蒙版）；Playbook `playbook.openbitfun.com`。 |
| **它到底是什么** | 一个**桌面级 Agent 运行时 + 一整套桌面 Agent 应用**：Rust 内核 + Tauri 外壳，内置 Code Agent（Agentic／Plan／Debug／Review 四模式）、Cowork Agent（办公）、Computer Use，加 Mini Apps（一句话生成专属界面）、Skills 市场、MCP、ACP 互联、手机远控、自托管多设备 relay。自称「Agentic OS」。 |
| **与我们的关系** | **基本无关，但不是零**。它不解决「谁认领、谁在做、交了什么」，它是「一个 agent 怎么把活干完」的容器。可借鉴的只有外围两件：ACP 互联层、自托管零知识 relay。 |
| **形态与部署** | 桌面 App（Win/mac/Linux，另有鸿蒙版）／源码 `pnpm run desktop:dev`（需 Node 22.12+、pnpm 10.15、Rust、Tauri 前置）。**自托管可行**：relay 可自部署（Argon2id + AES-GCM，零知识）。 |
| **agent 接入** | **有互联层但不是适配目录**：官方站写「**ACP 协议**——结构化多 Agent 通信标准，让 BitFun 与主流 AI 工具互联协作（Claude／Cursor／Codex／opencode）」，并支持 MCP（含 MCP App）与兼容 Codex 的 Hooks。仓库有 `packages/dsh-acp/` 目录（DSH 的 ACP 对接）。**没有像 Ekko Studio 那样一张 14 引擎的适配表。** |
| **协作模型** | 有「**Agent 团队**」概念（会话流／Agent 团队／小应用三视图）、自定义 Agent（Markdown 定义角色/记忆/能力）、个人助理可调度 Code／Cowork／自定义 Agent。**但没有任何「卡」的概念**：无看板列、无认领、无租约、无心跳。Playbook 导航里确有「Task board & scheduled jobs」条目，**但该子页两次抓取均 404，正文未取到 ⇒ 未证**。 |
| **完成判据** | **无闸门**。官方强调的「可验证性」指工程侧（CI、E2E、下载包签名校验 `docs/verify-downloads.md`），不是「任务完成必须交证据」。Deep Review 模式是「按仓库规范评审」，评审者仍是 agent。 |
| **许可** | **MIT**（API `license.spdx_id` = `mit`；README 徽章 `Core code: MIT`）。注意措辞是 **Core code**，第三方依赖另见 `THIRD_PARTY_NOTICES.md`（未逐条核）。 |
| **活跃度（亲眼所见，2026-10-19 17:0x +08:00）** | star **2,857**、fork **273**、open issues **112–113**（两次抓取间 +1，说明正在被写）、commits **5,725**（仓库页 HTML）、created **2026-02-02**、pushed **2026-10-19T08:36:37Z**、语言 Rust。最新 Release **1.0.3**（2026-09-30T14:17Z）。旧仓 `GCWing/BitFun` 页显示 1,878★／213 fork／3,475 commits（历史快照，已被重定向）。 |
| **可用性判定** | **`不可用`**（就「多 agent 共享看板」这个用途而言） |
| **最有价值点** | ① **ACP 互联**给了「不同引擎之间怎么结构化对话」的一个现成协议落点（与我们红线里的「跨引擎」相关，但方向是通信不是认领）；② **自托管零知识 relay**——如果将来看板要跨机器、又不许过第三方云，这套多设备同步的加密设计值得读。 |
| **最致命缺点** | **它压根没有「板」**。没有卡、没有列、没有认领、没有心跳、没有人工审批位、没有完成闸门——我们四条红线它一条不占。它是个很好用的「单兵 agent 工作台」，不是「多人（多 agent）协作治理层」。 |

**四条红线逐条点名**：

| 红线 | BitFun | 依据 |
|---|---|---|
| 跨引擎统一认领 | **无**（有 ACP 通信，无认领） | ACP 是对话协议，无 assignee/claim 语义 |
| 心跳回收 | **无** | 全文无 heartbeat |
| 完成即证据 | **无** | 无 receipt／无 gate 阻断完成 |
| 人的审批位不可越 | **半条（弱）**：手机端可「respond to approval requests」 | 是工具调用审批，不是看板列权限 |

**「毕方」候选清单**：见 §2.3（7 筛 2），此处不重复。

---

### 3.4 附加表 · 广州实验室「毕方（AI Biologists）」

> **为什么单列**：它是本轮唯一一个**名字真的叫「毕方」且真的在做「多智能体」**的实体。它与 BitFun 无公开关联，但如果不单列，就等于把「毕方」这个名字含糊掉了。

| 维度 | 内容 | 证据档 |
|---|---|---|
| 正名＋归属 | **毕方（AI Biologists）一站式多智能体科研工作台**；发布方＝**广州实验室**（广州国家实验室，呼吸系统疾病领域新型科研事业单位） | C（新华社《经济参考报》2026-09-24、21 世纪经济报道 2026-09-23、搜狐转载 2026-09-22 三源一致） |
| 它到底是什么 | 面向生命健康领域的**科研多智能体工作台**，官方定位「为生命健康领域 AI+ 科技创新提供**自主可控的数智底座**」 | C |
| 与我们的关系 | **技术路线相关（多智能体），产品形态无关（科研闭环，不是通用任务看板）** | 推断 |
| 形态与部署 | 未见公开形态说明；其底层依托 **Bio-OS**（广州实验室自研生物医学大数据操作系统，社区开源版在 GitHub 公开） | C＋推断 |
| agent 接入 | 未证 | — |
| 协作模型 | 未证（只知道叫「多智能体」） | — |
| 完成判据 | 未证 | — |
| 许可 | 未证（未见公开仓库与许可证） | — |
| 活跃度 | 无 star／无版本可查（非 GitHub 项目） | — |
| 可用性判定 | **`未证`**（不是「不可用」——是根本没材料可判） | — |
| 最有价值点 | 无（对我们不可复用） | — |
| 最致命缺点 | 全封闭：无仓库、无文档、无许可、无试用入口 ⇒ 对我们是**纯黑盒** | — |

---

## ④ 人话结论（≤500 字，含「是否改变首轮结论」）

**名字先分清。**「ekko studio」和「Ekioo」**不是一家**：前者是 EKKOLearnAI 的多 agent 工作台（前身 Hermes Studio），后者是 KittyClaw 作者，技术栈、许可、域名全不同，只是字母撞脸。「毕方 BitFun」这条对不上：BitFun 官方中文材料里「毕方」出现 **0 次**；真正叫「毕方」的是**广州实验室**的科研多智能体平台，与 BitFun 无公开关联。我不合并，请给出处。

**东西。** 最接近我们要造的是 **Ekko Studio**：14 种引擎同屏、看板、审批门、运行快照回放，外壳已很像。两处硬伤：**无任务级租约与心跳**（两 agent 抢一张卡拦不住），许可是 **BSL-1.1**（商用另买，2029 才转 Apache）。

**Metis 是意外收获**：不是看板，但把「完成即证据」做成了**机械闸门**——G0–G7 收据状态机，`FALSE_COMPLETION_BLOCKED` 拦住「没跑就说做完」，验退出码、测试 stdout、diff 边界。源码实证：`G7` 45 次、`receipt` 68 次。**这块直接抄设计。**

**BitFun 是空的**：好用的桌面 agent 工作台，但无卡、无认领、无心跳、无闸门，四条红线一条不占。

**是否改变首轮「17 个产品 0 可用」？不改变。** 三件仍无一件同时满足四条红线，`可用` 仍是 **0**。但结论更细了：**「跨引擎接入」与「完成即证据」各自都已有成熟实现；我们缺的是把它们缝起来的那层「认领＋心跳＋人的审批位」，三件里没有一家做。**

⚠️ **反向警告**：Metis 自评 32 个零分任务里 27 个是「跑了但跑错」，首因是**治理仪式吃掉产出**。闸门别做成表演。

---

## ⑤ 未证清单（含「未能定位」与试过的检索词）

### 5.1 明确未能证实 / 未能定位

| # | 未证项 | 我做了什么 | 状态 |
|---|---|---|---|
| 1 | **「毕方」是不是 BitFun 的中文名** | ① 抓 BitFun 官方 `README.zh-CN.md`（4,835 字符）、`AGENTS-CN.md`（13,186 字符）、`openbitfun.com` 首页（1,754 字符）、`OpenBitFun/README.zh-CN.md`，逐字计数「毕方」＝ **0/0/0/0**；② GitHub 仓库搜索 `毕方 agent` → **0 条**、`bifang multi-agent` → **0 条**、`openbitfun` → 4 条（全是 BitFun 生态自身）；③ 12 次网页检索，未找到任何把两者连写的可靠来源 | **未能证实**（不是「不是」，是「没有公开证据」） |
| 2 | 广州实验室「毕方」的仓库／许可／形态／接入方式 | 检索「广州实验室 毕方」「AI Biologists 毕方」「毕方 Bio-OS 智能体 开源」；查 gzlab.ac.cn 与 bioos.ac.cn；GitHub 搜索 `毕方 AI Biologists` → 0 条 | **未能定位**（只有 3 家媒体转述，无一手产品页） |
| 3 | BitFun 的「Task board」到底有没有、长什么样 | Playbook 导航列出该条目，但 `playbook.openbitfun.com/capabilities/feature.task-board`、`.html`、`/features/task-board` 三次均 404；`playbook.openbitfun.com` 首页只返回「Loading BitFun Playbook…」（JS 渲染，抓不到正文） | **未能定位** |
| 4 | metisagent.co 的产品细节 | 直连 Transport error；只有检索摘要（「Solana 代币化市场的自主研究 agent」） | **未能定位**（且已判为同名不同实体，不投入更多） |
| 5 | 三件产品的**实际运行表现** | 派工单明令禁止 clone／安装／注册 | **未做**（本报告全部能力判断均为文档级，非实测级） |
| 6 | BitFun `THIRD_PARTY_NOTICES.md` 的完整许可构成 | 未逐条核 | **未做** |

### 5.2 我试过的检索词（原样列出，便于复核席复算）

**ekko studio 侧**
- `ekko studio agent`
- `Ekioo KittyClaw ekioo.com`
- `ekko studio 区别 是否同一家`
- `EKKOLearnAI ekko-studio Hermes Studio multi-agent workspace`

**MetisAgent 侧**
- `MetisAgent`
- `Metis G0-G7 gate receipts FALSE_COMPLETION_BLOCKED docs`

**毕方 BitFun 侧**
- `毕方 BitFun`
- `毕方 BitFun AI Agent Rust`
- `"毕方" "BitFun" agent 开源`
- `"BitFun" "毕方" 同一个 中文名`
- `毕方 AI Agent 开源 项目`
- `"毕方" 桌面 Agent Rust Tauri 开源`
- `毕方智能体 桌面 AI Agent 开源 下载`
- `"毕方" AI Agent 平台 产品 2026`
- `"毕方" 多智能体 编排 平台 智能体协作`
- `毕方AI 编程工具 开源 项目 GitHub 中文名 BitFun 别称`
- `BitFun 中文社区 叫法 毕方 山海经 命名`
- `"毕方" 智能体平台 bifang.ai agent platform`
- `"AI Biologists" 毕方 广州实验室 多智能体 科研工作台`
- `广州实验室 毕方 一站式多智能体科研工作台`
- `广州实验室 毕方 Bio-OS 智能体 开源 平台 科研`

**API 检索**
- `api.github.com/search/repositories?q=毕方+agent` → total 0
- `api.github.com/search/repositories?q=bifang` → 命中均为无关（FreeNodes／论文模板等）
- `api.github.com/search/repositories?q=bitfun` → 8 条，仅 `GCWing/OpenBitFun` 相关
- `api.github.com/search/repositories?q=openbitfun` → total 4
- `api.github.com/search/repositories?q=毕方+AI+Biologists` → total 0
- `api.github.com/search/code` → **401 Unauthorized**（无 token，代码级搜索不可用）

---

## ⑥ 锚点汇总（每条带访问日期与看到的读数）

> 统一访问日期 **2026-10-19**；抓取时刻 **17:0x–17:09 +08:00**（UTC 09:0x）。star 数在多次抓取间有漂移（11,142／11,458／11,470），**以 §3 表中标注的 API 读数为准**，漂移本身即活跃证据。

### 6.1 Ekko Studio

| # | 锚点 | 看到的读数 |
|---|---|---|
| 1 | `https://api.github.com/repos/EKKOLearnAI/ekko-studio` | stars 11,470；forks 1,417；open_issues 485；created 2026-04-11T07:38:18Z；pushed 2026-10-19T08:00:49Z；language TypeScript；license `{key:other, spdx:NOASSERTION}`；homepage `https://ekkostudio.xyz` |
| 2 | `https://github.com/EKKOLearnAI/ekko-studio`（HTML） | Commits **1,674** |
| 3 | `https://raw.githubusercontent.com/EKKOLearnAI/ekko-studio/main/LICENSE` | 正文首行 `Business Source License 1.1`；Licensor `EKKOLearnAI`；Change Date `2029-05-10`；Change License `Apache License 2.0`；商业用途须另购 |
| 4 | `https://raw.githubusercontent.com/EKKOLearnAI/ekko-studio/main/README.md` | 34,696 字符；「previously named Hermes Studio / Hermes Web UI」；Kanban 段（L140-144）；Visual Workflows 段（approval gates／frozen run snapshots／evidence playback，L149-152）；14 引擎表（L76-78） |
| 5 | `https://registry.npmjs.org/ekko-studio` | `dist-tags.latest` = **0.7.37**；`time.modified` = 2026-10-19；`license` = **BSL-1.1** |
| 6 | `https://ekkostudio.xyz/` | 「Your agents. One studio.」；agent 列表含 Ekko/Hermes/Claude Code/Codex/Cursor/Antigravity/OpenCode/Grok/Pi/DSH/Qwen Code/Kimi Code/CodeBuddy/Qoder/Copilot/ZCode；页脚 `© 2026 EKKOLearnAI` |
| 7 | `https://api.github.com/users/EKKOLearnAI` | name `ekko`；id 152005280；created 2023-11-25；public_repos 12 |
| 8 | `https://api.github.com/repos/EKKOLearnAI/hermes-studio`（旧名对照） | 返回 `full_name` = **`EKKOLearnAI/ekko-studio`** ⇒ 重命名重定向实证 |

### 6.2 Metis（Wholiver）

| # | 锚点 | 看到的读数 |
|---|---|---|
| 1 | `https://api.github.com/repos/Wholiver/metis` | stars **403**；forks 35；open_issues 7；created 2026-07-11T07:02:59Z；pushed 2026-10-16T04:43:03Z；license `mit`；homepage `https://metisagent.tech/`；topics 含 `agent-orchestration`／`multi-agent-systems`／`subagents` |
| 2 | `https://github.com/Wholiver/metis`（HTML） | Commits **184**；Issues **7** |
| 3 | `https://api.github.com/repos/Wholiver/metis/commits?per_page=3` | 最新 `8b1eda9…` message `chore(release): v2.0.2`，author date **2026-10-16T04:42:24Z** |
| 4 | `https://registry.npmjs.org/@wholiver_hu%2Fmetis` | `dist-tags.latest` = **2.0.2**；共 **77** 个版本；`time.modified` = 2026-10-16 |
| 5 | `https://raw.githubusercontent.com/Wholiver/metis/main/README.md` | 4,650 字符；「G0–G7 verification state machine」「`FALSE_COMPLETION_BLOCKED`」「verifies the exit code, test stdout, and diff boundaries」「5-Role Recursive Team (Git Worktrees)」「MIT」「builds on pi by Mario Zechner」 |
| 6 | `https://raw.githubusercontent.com/Wholiver/metis/main/docs/agents.md` | 8,164 字符；L0→L4 递归委派；5 角色定义；`spawn_agent` 参数（`mode` sync/async，`worktree` inherit/branch/temp）；`SpawnGuard` 上限（depth 5／children 8／concurrent 4）；`DUPLICATE_TASK_WARNING`；PGID 孤儿回收；环境变量过滤；trace 脱敏 |
| 7 | `https://raw.githubusercontent.com/Wholiver/metis/main/src/core/performance-runtime.ts` | **119,121 字节**；关键词命中：`G0`=23、`G7`=45、`receipt`=68、`exitCode`=7、`gate`=225、`FALSE_COMPLETION_BLOCKED`=1 |
| 8 | `https://raw.githubusercontent.com/Wholiver/metis/main/docs/ale-metis-agent-failure-modes.md` | 8,299 字符；原文「Observed r2 completed zeros (n=32): **27 wrote files that failed the hidden grader**, 3 polluted `output/`…」；「the model spends turns coordinating personas instead of reading the task contract」；`MAX_CHILDREN_EXCEEDED` 约 13 个任务 |
| 9 | `https://api.github.com/repos/metisos/metisos_agentV1`（同名候选 3） | stars 12；license apache-2.0；created 2025-07-19；pushed **2025-08-16**（停滞） |
| 10 | `https://pypi.org/pypi/metis-agent/json` | latest **0.20.0**；author `Metis OS Team` / `cjohnson@metisos.com`；63 个发行；**最后上传 2025-09-28** |
| 11 | `https://metisagent.tech/`（检索摘要） | 「Metis · Open-Source Coding Agent with Verified Same-Model Harness Lift」；Terminal-Bench ~82% vs OpenCode ~67%；MIT；v1.3.5 徽章（**注意：官网徽章 v1.3.5 落后于仓库 v2.0.2，属官网滞后，非矛盾**） |
| 12 | `https://metisagent.co/`（检索摘要） | 「Metis — An autonomous research agent for tokenized markets on Solana」⇒ 同名不同实体 |

### 6.3 BitFun／OpenBitFun（GCWing）

| # | 锚点 | 看到的读数 |
|---|---|---|
| 1 | `https://api.github.com/repos/GCWing/OpenBitFun` | stars **2,857**；forks 273；open_issues 112→113；created 2026-02-02T09:52:10Z；pushed 2026-10-19T08:36:37Z；language **Rust**；license `mit`；homepage `openbitfun.com` |
| 2 | `https://api.github.com/repos/GCWing/BitFun` | 返回 `full_name` = **`GCWing/OpenBitFun`** ⇒ **旧名 BitFun 已重命名为 OpenBitFun**（重定向实证） |
| 3 | `https://github.com/GCWing/OpenBitFun`（HTML） | Commits **5,725** |
| 4 | `https://github.com/GCWing/BitFun`（HTML，旧仓快照） | stars 1,878；forks 213；Commits 3,475；license MIT；created 2026-02-02 |
| 5 | `https://github.com/GCWing/OpenBitFun/releases` | 最新 **OpenBitFun 1.0.3**，发布于 **2026-09-30T14:17Z**；另有 `1.0.3-nightly.20261008`；迁移器 `data-migrator-v0.1.1` |
| 6 | `https://raw.githubusercontent.com/GCWing/OpenBitFun/main/README.md` | 8,902 字符；「Four powerful Agent Harness modes · Cross-device remote control」；「respond to **approval requests**」；关键词 `heartbeat`=0、`claim`=0、`kanban`=0、`board`=0、`gate`=0 |
| 7 | `https://raw.githubusercontent.com/GCWing/BitFun/main/README.zh-CN.md` | 4,835 字符；**「毕方」= 0 次** |
| 8 | `https://raw.githubusercontent.com/GCWing/OpenBitFun/main/AGENTS-CN.md` | 13,186 字符；**「毕方」= 0 次** |
| 9 | `https://openbitfun.com/`（HTML） | 1,754 字符；`<title>OpenBitFun · Open Agent System</title>`；**「毕方」= 0 次** |
| 10 | `https://www.bitfun.work/`（HTML） | 40,421 字符；主打「BitFun Agentic IDE · For 鸿蒙」；**「毕方」= 0 次** |
| 11 | `https://openbitfun.com/`（检索正文） | 「ACP 协议——结构化多 Agent 通信标准，让 BitFun 与主流 AI 工具互联协作（Claude／Cursor／Codex／opencode）」；「Mobile Office 扫码配对」；「X25519 + AES-256-GCM」；「最新版本 0.2.19」（**该站为旧版本线页面，与 GitHub 1.0.3 并存，属站点未同步**） |
| 12 | `https://www.openbitfun.com/download`（检索正文） | 「v1.0.3 Latest SOURCE CHECK · 2026-09-30」 |
| 13 | `https://github.com/GCWing/OpenBitFun/blob/main/docs/architecture/product-architecture.md`（检索正文） | 940 行；「面向 GUI、TUI/CLI、Web、ACP、Server、Remote、SDK 与扩展生态」；OpenCode 插件兼容适配层 |
| 14 | `https://playbook.openbitfun.com/capabilities/feature.task-board` | **404**（三次变体均 404）⇒ Task board 存在性未证 |

### 6.4 广州实验室「毕方」

| # | 锚点 | 看到的读数 |
|---|---|---|
| 1 | `http://jjckb.xinhuanet.com/20260924/1d6ffe1351f44095b8f65ab18025efd0/c.html`（新华社《经济参考报》，2026-09-24） | 「广州实验室发布**毕方（AI Biologists）一站式多智能体科研工作台**，为生命健康领域“AI+”科技创新提供自主可控的数智底座」 |
| 2 | `https://www.21jingji.com/article/20260923/herald/303d9cac20f5642a4c6b4d9c9a3f751b.html`（21 世纪经济报道，2026-09-23） | 「科技创新专题对接会上…广州实验室发布毕方一站式多智能体科研工作台」；大会 2026-09-22 于广州 |
| 3 | `https://m.sohu.com/a/1079643527_120046696`（搜狐转载，2026-09-22） | 同 1、2 的第三源，措辞一致 |
| 4 | `https://www.gzlab.ac.cn/Evolve/index_44.html` | Bio-OS（生物医学大数据操作系统）自述：「社区开源版已在 Github 平台公开」；支撑 50+ 科研团队；PB 级数据 |
| 5 | `https://www.gzlab.ac.cn/evolve/index_219.html` | 广州国家实验室 LLM 智能体单细胞组学基准（Genome Biology，DOI 10.1186/s13059-026-03998-z）；兼容 ReAct／LangGraph／AutoGen 三框架、8 个模型、50 任务、18 指标 |

### 6.5 同名甄别专用锚点（Ekioo）

| # | 锚点 | 看到的读数 |
|---|---|---|
| 1 | `https://api.github.com/users/Ekioo` | name `EKIOO`；blog `https://ekioo.com`；created **2026-03-03**；public_repos **1** |
| 2 | `https://api.github.com/repos/Ekioo/KittyClaw` | stars **27**；forks 0；license **AGPL-3.0**；created 2026-04-06T11:56:55Z；pushed 2026-09-06T04:07:43Z |
| 3 | `https://github.com/Ekioo/KittyClaw`（HTML） | Commits **907**（与首轮 P1 记录一致） |
| 4 | `https://ekioo.com/en/projects` | 项目列表：Kalceo／KittyClaw／Lain／Protocol 223／UnityToolkit／VizMail；页脚 `© 2026 Ekioo — Damien Hoffschir` |
| 5 | `https://ekioo.com/en/projects/kittyclaw` | 「KittyClaw is a local kanban that does more than track tickets: it orchestrates your Claude Code agents」；技术栈 **.NET 10 SDK / Blazor / SQLite**；端口 5230 |

---

## 附 · 给发牌席的一句话处置建议（非结论，供拍板参考）

1. **Ekko Studio**：不采用（BSL-1.1 是硬约束），但**读它的 runtime adapter 目录与审批门 UI**——那是「跨引擎接入」目前最完整的公开样本。
2. **Metis**：不采用其本体（不是看板），但**把 G0–G7 receipt 的设计搬过来**，作为我们红线 1 的闸门蓝图；同时把它的失败复盘（治理仪式吃掉产出）写进我们的设计约束。
3. **BitFun**：不看（四条红线全不占），仅在其「自托管零知识 relay」将来有跨机需求时回看。
4. **「毕方」**：请用户给出处。若用户指的是广州实验室那家，则与我们无交集（封闭科研平台）。

---

*本件由调研席 E 生成；未改动本批次目录以外任何文件；未 clone、未安装、未注册、未提交任何表单。*
