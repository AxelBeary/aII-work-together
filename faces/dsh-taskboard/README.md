# dsh-taskboard · 内核适配版

> 2026-11-20 · D-041。**界面用 taskboard 原版，宿主换成 aII-work-together 内核。**

## 是什么

- `lib/client.js`：taskboard 0.10.0 的**原版预构建客户端**（未改一行）。
  它只认 `/dsh-taskboard/*` 的 HTTP 契约。
- `lib/index.js`：我们写的宿主适配层，把这些路由逐条映射到内核：
  - `GET /state` → 内核 `/api/state` + `/api/cards`
  - `GET /tasks/:id` → `/api/card`（含 comments/checklist/executions 折叠）
  - `POST /tasks` → `/api/card`（建卡）
  - `POST /tasks/:id/{update,move,comment,delete,cancel,reject,run}`
  - `GET /workspaces` → 内核项目列表
  - `GET /events` → SSE 心跳（面板自身轮询 state）

**账本仍是内核**：宿主不存任何数据；每个请求实时读内核。

## 安装（已执行）

```bash
cp -r faces/dsh-taskboard ~/.dsh/profiles/desktop/node_modules/dsh-taskboard
# profile package.json 的 bundles 含 dsh-taskboard
# profile cordis.patch.yml 的 dsh-taskboard 改成 disabled: false
```

## 自测（不需要 DSH）

```bash
cd faces/dsh-taskboard
BOARD_PORT=8789 BOARD_API_TOKEN=t7 node selftest.mjs   # 期望 SELFTEST PASS
```

覆盖：workspaces → state → 建卡 → 移动到进行中（认领）→ 评论 → 详情回读 → 删除。

## 回滚

```bash
P=~/.dsh/profiles/desktop
cp $P/package.json.bak3-20261120-030506 $P/package.json
cp $P/cordis.patch.yml.bak3-20261120-030506 $P/cordis.patch.yml
rm -rf $P/node_modules/dsh-taskboard
cp -r $P/node_modules/dsh-taskboard.upstream-20261120-030053 $P/node_modules/dsh-taskboard
```

## 已知限制

- 富功能（diff/worktree/模板/外部同步/定时 UI）暂未接；按钮会提示「这个动作还没接到内核」。
- 面板「开始」会以内核要求的方式认领（按卡自己的 engine/model/effort）。
- 「完成」仍必须走内核 review/human 闸，面板不能直接 done。
