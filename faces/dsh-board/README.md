# dsh-board · DSH 看板面板（内核代理）

> 2026-11-19 · D-040。把 aII-work-together 的内核看板挂进 DSH 侧栏。
> **不改内核代码，不 fork taskboard**：面板只是内核 HTTP 的一个同源代理。

## 它是什么

- 宿主半边（`lib/index.js`）：确保内核 HTTP 服务在跑（不在就拉起），把 `/board/*` 代理过去。
- 浏览器半边（`lib/client.js`）：注册 DSH 面板（`slots` 的 `main` + `sidebar.panellist`），
  列出卡片、看详情、评论 / 改标题 / 开始 / 取消 / 回退 / 删除 / 恢复 / 勾选清单。
- **账本仍是内核**：浏览器不存副本，刷新即重拉；所有写走内核事件流。

## 依赖

- 内核仓库默认 `E:\\GithubClone\\aII-work-together`（可用 `BOARD_REPO` 覆盖）。
- 内核端口默认 **8790**（`BOARD_PORT` 覆盖）；令牌默认 `dsh-board-local`（`BOARD_API_TOKEN` 覆盖）。
- Python 在 PATH（`BOARD_PYTHON` 可指定解释器）。

## 安装（已由发牌席执行）

```bash
# 1) 复制到 profile
cp -r faces/dsh-board ~/.dsh/profiles/desktop/node_modules/dsh-board
# 2) 把 dsh-board 加进 profile 的 dsh.profile.bundles
# 3) 重启 DSH 宿主
```

## 验收（重启后）

1. 侧栏出现「看板」行 → 点开应看到卡片列。
2. 点一张卡 → 右侧出现详情与按钮。
3. 点「评论」→ 写入后详情出现该评论；再点一次发同一句 → 不会重复（幂等）。
4. 内核不在跑时：首屏最多等 10 秒（插件自动拉起），失败会显示错误而不是空白。

## 回滚（一条命令恢复）

备份在 profile 目录：`package.json.bak-20261119-222011`。

```bash
cp ~/.dsh/profiles/desktop/package.json.bak-20261119-222011 ~/.dsh/profiles/desktop/package.json
rm -rf ~/.dsh/profiles/desktop/node_modules/dsh-board
# 再重启 DSH
```

## 自测（不需要 DSH）

```bash
cd faces/dsh-board
BOARD_PORT=8781 BOARD_API_TOKEN=t1 node selftest.mjs   # 期望 SELFTEST PASS
```
