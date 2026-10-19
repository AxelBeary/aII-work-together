# allworktogether

> **单人用的多 agent 编排看板**：让本机所有 AI agent 在同一块板上分工协作，全程可追责。

## 三分钟上手

```bash
# 1. 在任意项目目录，设一次默认值（只做一次）
python <本项目>/tools/board.py project default --engine opencode --model opencode-go/deepseek-v4.1-flash

# 2. 建一张卡
python <本项目>/tools/board.py add --title "把登录页改成深色" --goal "只改 landing 目录"

# 3. 让它自己跑
python <本项目>/tools/orchestrator.py run --max 5

# 4. 看
python <本项目>/tools/board.py open --show
```

就这四条。剩下的它会自己做。

## 它替你做什么

| 你担心的 | 它怎么管 |
|---|---|
| agent 说做完了但其实没做 | **完成＝证据**：产物在不在、字节>0、必含项命中、有数字 |
| 两个 agent 抢同一张卡 | **原子认领**：`mkdir` 独占，12 个线程只有一个赢 |
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

## 并行（可选，默认串行）

```bash
python tools/orchestrator.py run --parallel 2 --max 4
```

每张卡在独立 git worktree 里跑，互不踩文件；收工时只拷**该卡的交付物**，两卡交付物重叠就判阻塞。
⚠️ 建议 ≤2：本机引擎会抢资源，开太多反而慢。

## 自检（改完代码必跑）

```bash
python tests/run_regression.py          # 18 条回归
python tests/run_regression.py --break  # 反向测试：故意改坏必须被抓
python tests/test_resume.py             # 断点续跑
python tools/board.py audit             # 有没有绕过 CLI 手改
```

## 文件结构

| 文件 | 职责 |
|---|---|
| `tools/board.py` | 看板本体：卡片、状态机、租约、闸门、哈希链、CLI |
| `tools/render.py` | 看板页与跨项目总览（纯静态 HTML） |
| `tools/projects.py` | 多项目注册表与根目录解析 |
| `tools/engines.py` | 引擎适配：结构化回执解析 + 会话续接 |
| `tools/experts.py` | 专家团：11 个角色 |
| `tools/subagents.py` | 子代理：独立会话、可并行 |
| `tools/orchestrator.py` | 自主编排 |
| `tools/resume.py` | 断点续跑 |
| `tools/parallel.py` | worktree 并行执行 |

零依赖，Python 3.9+。

## 从哪读起

| 你想干什么 | 读哪里 |
|---|---|
| **马上用** | [`docs/usage.md`](docs/usage.md) |
| 进入本项目动手 | `AGENTS.md` |
| 看架构 | `docs/design/20261019-architecture-deepdive/98_架构总图__发牌席__合并稿.md` |
| 看已踩的坑 | `docs/governance/ENVIRONMENT.md` |
| 看拍板记录 | `docs/governance/DECISIONS.md` |
