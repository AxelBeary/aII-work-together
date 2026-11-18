# 20261119-integration-absorb · 六合一整合吸纳（调研 + 三席评审）

> 状态：**方案已定稿到 v2.1，代码未动**。下一步是 P0 的 T0（52 处写点清单）。
> 入口：先读 05，再读 00；03/04/06 是三席评审回执，03b/03c 是 GLM 通道证明。

## 文件

| 文件 | 是什么 | 状态 |
|---|---|---|
| 00_整合吸纳_盘点与路线 | 六资产盘点、能力矩阵、冲突面、三条路线 | 已交（被 05 部分覆盖） |
| 01_整合吸纳_目标架构与落地计划 | 目标架构、契约、P0–P6 | **§4 已作废**，以 05 为准 |
| 02_独立评审任务书 | 三席共用的派工书（只读、判分口径） | 已交 |
| 03_独立评审_GLM53 | 评审 B（opencode CLI，glm-5.3） | CONCERNS |
| 03b_GLM会话导出 | 原始会话 JSON（证据） | 129 KB，本地 |
| 03c_GLM会话证明 | 模型/渠道/用量证明 | 已交 |
| 04_独立评审_子代理DS | 评审 A（子代理，deepseek-v4.1-flash） | REJECT（交叉意见保留） |
| 05_评审采纳与方案修订 | **v2.1 权威稿**：适配器、零持久化、闸门增补 | 已交 |
| 06_独立评审_B2_GLM53 | 评审 C（cross-session，glm-5.3） | CONCERNS |

## 三席结论（独立、互不可见，收敛到同一处）

- A：REJECT；B：CONCERNS；C：CONCERNS。
- 共同硬伤：01 稿「只改 taskboard 三个文件」不成立 —— 复跑为 **52 处写点 / 6 文件**。
- v2 修订：不换心脏，装 **KernelStore 适配器**；本地零持久化；副本只从内核回执/事件流前进。

## 明天开工（新会话照此）

1. 读 00 → 05 → 06；再跑 05 §6 的复跑命令。
2. 跑 `python tools/check.py --quick` 确认基线（20 道闸）。
3. **开 T0**：52 处调用点四列表（kind → 内核 API → 内核侧校验 → 命令缺口）。
4. T0 出缺口报告后，才拍板：TaskEnvelope 冻结、comments/executions/checklist/settings 承载、HTTP 写面。

⛔ T0 前不写 KernelStore 实现；⛔ 不先改 taskboard 源码；⛔ 不双账本。

## 复跑

```bash
cd /e/GithubClone/aII-work-together
python tools/check.py --quick
cd "C:/Users/qly19/.dsh/profiles/desktop/node_modules/dsh-taskboard"
for f in src/host/*.ts; do n=$(grep -c 'store.mutate(' "$f"); [ "$n" -gt 0 ] && echo "$n $f"; done
```
