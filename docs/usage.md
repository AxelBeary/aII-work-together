# 怎么用（三分钟，之后只看一条命令）

## 最常用四条

```bash
board project default --engine opencode --model opencode-go/deepseek-v4.1-flash --workspace <代码目录>   # 一次
board add --title "要做什么" --goal "具体目标"
python tools/orchestrator.py run --max 5
board inbox        # 看有没有等你拍板的
```

`board` 就是 `python tools/board.py`（建议加个 alias 或 .cmd 包装）。

---

## 📥 拍板收件箱（你最常用的一个）

```bash
board inbox              # 一次最多 3 张，多了不列（免得你看花眼）
board inbox --limit 5    # 想一次多看点
```

每张卡它会用人话告诉你：
- **目标**是什么
- agent **做了什么**
- **产出**有哪些、多大
- **门禁**过没过、**复核**是谁做的、**凭据**是什么
- **花了多少钱**（token / 缓存 / 美元）
- **建议批准还是驳回**（并说明理由）

然后给两行可直接复制的命令：

```bash
board human <卡号> --decision approve --who owner
board human <卡号> --decision reject  --who owner --note "要改什么"
```

**驳回时写的理由会传回下一轮**，agent 会针对性改，不会重做一遍。

---

## 多项目

每个项目在自己目录下有 `board/`，数据跟项目走（可 git、可搬）。**每个项目还能指定工作区**（agent 干活的地方，可以和项目根不同）：

```bash
board project add /path/to/project --workspace /path/to/code   # 登记时指定
board project default --workspace /path/to/code                # 之后改
board project ls                                                # 所有项目 + 卡片数
board -p other-project ls                                       # 切到别的项目
board overview                                                  # 跨项目总览页
```

**零配置**：在任意目录直接跑 `board add ...`，它会自动把当前目录当项目、自动建看板、自动登记。

**默认值**：项目级设一次引擎/模型/思考强度，之后建卡自动继承。

---

## 用量与花费

```bash
python tools/board.py cost            # token + 缓存 + 花费
python tools/board.py cost --per-card # 按卡片细分
```

数据来自引擎自己报的结构化回执（opencode 的 `step_finish` 带 tokens/cache/cost）。
**引擎没报就标「未知」，不会记成 0**——避免让你以为不要钱。

---

## 并行（默认串行）

```bash
python tools/orchestrator.py run --parallel 2 --max 4
```

每张卡一个独立 git worktree，互不踩文件。收工只拷该卡的交付物；**两卡写同一个文件且内容不同 ⇒ 后到的判阻塞**，不会静默覆盖。

⚠️ 建议 ≤2：本机引擎会抢资源。

---

## 编排器（全自动）

```
python tools/orchestrator.py run --engine opencode --max 5
```

**加专家团复核**（多视角，取最严）：

```
python tools/orchestrator.py run --engine opencode --panel security skeptic simplifier --max 5
```

| 步骤 | 它做什么 |
|---|---|
| 1 找活 | 按引擎／模型／思考强度匹配，**精确匹配优先** |
| 2 认领 | **固定名目录 + `os.mkdir`** 原子独占（实测 12 线程只有 1 个成功） |
| 3 执行 | 调引擎，把卡变成提示词（含领地、交付物、必含项） |
| 4 提交 | **自动跑 L1-L3** |
| 5 复核 | 单席或**专家团**；取最严，任一 FAIL 即 FAIL |
| 6 返工 | FAIL → 状态转「待返工」，**能被重新认领**；3 次不过转阻塞 |
| 7 人闸 | 需要拍板的转「拍板中」停下等你 |
| 8 记账 | 自动追加 `DELEGATION-LEDGER.md` |

**先看它会干什么**：`--dry-run`

---

## 专家团（多视角审一遍）

| 角色 | 它专门看什么 |
|---|---|
| `security` | 能不能绕过、密钥会不会泄漏、权限边界 |
| `skeptic` | 这件事到底该不该做、有没有更简单的做法 |
| `simplifier` | 哪些没人用、哪些该砍、哪些过度设计 |
| `architect` | 模块边界、失败怎么退化、以后改起来痛不痛 |
| `perf` | 慢在哪、量级对不对 |
| `ux` | 新用户能不能三分钟上手、错误信息说不说人话 |
| `reviewer` / `worker` / `lead` / `researcher` | 基础四席（对应 AGENTS.md §3） |

```
python tools/orchestrator.py run --engine opencode --panel security skeptic
```

---

## 子代理（独立会话，可并行）

```python
import subagents
res = subagents.spawn([
    {"task": "查 A", "name": "a"},
    {"task": "查 B", "name": "b", "role": "skeptic"},
], model="opencode-go/deepseek-v4.1-flash")
print(subagents.gather_summary(res))
```

- 每个子代理**独立上下文**，互不污染
- 带 `session_id` 可续接（实测：第一轮记住 42，第二轮答出 42）
- `parallel=True` 可并行，但本机引擎会抢资源，建议 ≤2

---

## 建卡：可以指定「谁干、用什么模型、思考多深」

```
python tools/board.py new --title "标题" --goal "要做什么" `
  --engine opencode `
  --model opencode-go/deepseek-v4.1-flash `
  --effort high `
  --deliverable board/artifacts/产出.md `
  --accept "必含关键词" `
  --human-gate before_done
```

| 参数 | 作用 | 可选值 |
|---|---|---|
| `--engine` | **哪个 agent 框架** | `opencode`／`qoderclicn`／`codex`／`hermes`／`any` |
| `--model` | **哪个模型** | 如 `opencode-go/deepseek-v4.1-flash`；`any`＝不限 |
| `--effort` | **思考强度** | `low`／`medium`／`high`／`max`／`any` |
| `--deliverable` | 交付物路径 | 提交时自动查在不在、字节>0 |
| `--accept` | 交付物里**必须出现**的内容 | 正则；少一个就不让过 |
| `--human-gate` | 人闸 | `none`／`before_done`（必须你拍板）／`both` |
| `--irreversible` | 标记不可逆动作 | 建议配合 `before_done` |

三个规格都不填＝`any`，任何 agent 都能接。

**规格对不上会被拒**——防止低配模型接了需要高思考强度的活：

```
✗ 这张卡的执行规格与你声明的不符：引擎需 opencode
  卡要求：引擎=opencode 模型=... 思考=high
  你声明：引擎=qoderclicn 模型=... 思考=high
```

---

## AI 自己发布任务

```
python tools/board.py publish --title "..." --engine opencode `
  --model opencode-go/deepseek-v4.1-flash --effort medium `
  --seat <发布者席名> --from-card <由哪张卡派生>
```

- **`--seat` 必填**：⛔ 不允许匿名发布（传 `human` 会被拒）
- 看板上这类卡带绿色 **「AI 发布」** 标记
- `--from-card` 记下派生关系（哪个任务拆出来的）
- 发布者身份写进 journal，可追溯

---

## agent 找活干（手动模式）

```
python tools/board.py ready --engine opencode --model opencode-go/deepseek-v4.1-flash --effort medium
python tools/board.py claim <卡号> --seat w1 --engine opencode --model ... --effort ...
python tools/board.py beat  <卡号> --seat w1        # 每 2 分钟一次
python tools/board.py submit <卡号> --seat w1 --note "做了什么"
```

不心跳 = 10 分钟后被回收。

---

## 复核（必须换会话，不能自己验自己）

```
python tools/board.py verify <卡号> --seat rev1
python tools/board.py review <卡号> --seat rev1 --verdict pass --evidence "你跑的命令和读数"
```

`--evidence` **不给就不让过**。编排器会自动做这步。

---

## 你拍板（只有你能做）

```
python tools/board.py human <卡号> --decision approve --who owner
```

第一次用先建令牌（一次性）：

```powershell
Set-Content -Path "$HOME\.board-human.tok" -Value "human-only" -NoNewline
```

⚠️ **这个令牌不要给 agent**。给了就等于把拍板权交出去了。

---

## 出问题查这个

```
board                # 不带参数：面板（项目名 + 各状态张数 + 下一步）
board stats          # 各状态 + 完成率
board doctor         # 体检：残留租约/worktree/断链/丢件
board doctor --fix   # 自动清理可修项
board audit          # 有没有人绕过 CLI 手改文件
board cost           # token / 缓存 / 花费
board show <卡号> --events   # 一张卡的全过程
```

一条命令跑完全部自检：`python tools/check.py`

---

## 断了怎么接（断点续跑）

编排器被杀了（Ctrl+C、断电、OOM）不用慌：

```
python tools/orchestrator.py resume --engine opencode
```

它会按 journal 状态决定每张卡从哪接：

| 卡的状态 | 它怎么做 |
|---|---|
| 待认领 / 待返工 | 从执行开始 |
| 进行中但没租约（上次崩了） | 回收后重跑 |
| 进行中且有活租约 | **跳过**（别人在干） |
| **待验收** | **直接复核，不重做** |
| 核验中 | 补复核结论 |
| 完成 / 拍板中 | 跳过 |

先看计划再跑：`--dry-run`

`audit` 退出码非 0 = 有问题，逐条列出。

---

## 引擎当前可用性（2026-10-19 实测）

| 引擎 | 状态 | 会话续接 | 备注 |
|---|---|---|---|
| **opencode** | ✅ 可用 | ✅ 实测通过 | **必须指定 `--model`**，否则免费池被 IP 封禁 |
| **qoderclicn** | ✅ 可用 | ✅ 实测通过 | ⛔ 不能加 `--no-session-persistence`，否则续接失效 |
| hermes | ⚠️ 未测 | 未测 | 本轮未验证 |

---

## 并发与并行

- **认领是并发的**：多个 agent 可以同时抢不同卡，`os.mkdir` 保证同一张卡只有一个赢家（12 线程实测：1 成功 / 11 失败）。
- **执行是串行的**：编排器一次跑一张卡——本机引擎会抢资源，并行不划算。
- **子代理可并行**：`subagents.spawn(..., parallel=True, max_workers=2)`，但建议 ≤2。

---

## 四条红线在代码里长什么样

| 红线 | 怎么实现的 | 你能看到什么 |
|---|---|---|
| **状态即证据** | 进「完成」必须过 L1 产物／L2 形制／L3 内容三道机器闸 + 异会话复核 | 提交时自动打读数；没过就不进「待验收」 |
| **人的拍板位** | 出「拍板中」只有 `human` 命令，agent 没有这条路径 | 人闸卡没有你的 approve 就永远停在「拍板中」 |
| **认领即租约** | `os.mkdir` 原子独占创建，两进程只有一个成功 | 第二个 agent 抢会直接报错 |
| **完成必须异会话** | 复核席 == 执行席 直接拒 | 想自己验自己，命令就报错 |

---

## 它不做什么（免得你期待错）

- **不是**聊天界面，agent 只用命令行
- **不是**分布式系统，只在本机跑
- **不保证**「证据是真的」，只保证「有证据」——真假靠复核席亲跑
- **挡不住**被回收的进程已经在外面干过的事
- **没做**多用户、权限管理、数据库——文件就是全部
- **引擎串行跑**，不并行（本机引擎会抢资源）
