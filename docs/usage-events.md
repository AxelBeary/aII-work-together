# 事件流速查（AI 与人都用这一页）

> 2026-11-19 · D-033 落地版。**到手即用**：下面每条都实测跑过。

## 一句话

**事件流是唯一真相。** 评论、执行记录、验收清单、软删除都不是表里的列，
而是事件折叠出来的投影。所有写入口都带幂等键 —— agent 可以无脑重试。

---

## 给 AI 的四条规矩

1. **每个命令都可以加 `--json`**：成功 `{ok:true, value, next}`，失败 `{ok:false, error:{code,message,hint,retryable}}`。
2. **失败时退出码非 0**，但输出仍是合法 JSON —— 脚本不用 try 人话。
3. **`next` 告诉你下一步**，不用读文档猜。
4. **重试是安全的**：同一句话重发不会产生第二条评论（幂等键）。

```bash
board schema --json    # 全部命令 / 状态机 / 错误码 / 事件类型，一次看全
```

---

## 常用命令

### 评论

```bash
board comment <卡号> "交付已完成，产物在 out/x.md" --as agent --seat w1
board comment <卡号>                    # 不带正文＝列出全部
board comment <卡号> --json
```

**幂等**：同一作者 + 同一句话重发 → 只有一条。要发两条一样的话，加 `--thread` 区分。

### 验收清单（DoD）

```bash
board checklist <卡号> add --text "接口返回 200" --json
board checklist <卡号> check --item k-abc123 --note "curl 实测 200" --json
board checklist <卡号> uncheck --item k-abc123
board checklist <卡号> ls
```

### 执行记录

```bash
EID=$(board exec <卡号> open --json | jq -r .value.execution)
board exec <卡号> report --execution $EID --body '{"summary":"改完 3 个文件","risk":"无"}'
board exec <卡号> close --execution $EID --outcome succeeded
board exec <卡号> ls
```

一条卡同一时刻只允许一条 running 执行（`open` 会拒）。

### 事件流（增量）

```bash
board events <卡号> --json                # 全量
board events <卡号> --since 42 --json     # 只要 seq > 42 的
```

HTTP 同理：`GET /api/card/events?id=<卡号>&since=42`

### 软删除

```bash
board trash <卡号> --reason "重复建卡"
board trash <卡号> --restore
```

⛔ 不物理删除：事件流全部保留，可恢复、可审计。

---

## 两个游标，别搞混

| 游标 | 管什么 | 怎么用 |
|---|---|---|
| `seq` | 事件流位置 | `--since N` 增量拉取；单调递增，无并列 |
| `epoch` | 租约代次 | `claim` 后拿到，`beat`/`submit` 带上；被回收后旧代写不进 |

---

## 错误码（闭集，8 个）

| code | 意思 | 怎么办 |
|---|---|---|
| `invalid_input` | 参数不对 | 看 `hint` |
| `not_found` | 卡/项不存在 | `board ls` |
| `version_conflict` | 卡被别人改了 | 重读后重试（retryable） |
| `invalid_transition` | 状态机不许这一步 | 看 `board schema` 的 transitions |
| `forbidden` | 权限不够（如 agent 想 done） | 交给人 |
| `busy` | 已有执行在跑 | 等或 close |
| `blocked` | 依赖/预算挡住 | `board show` 看原因 |
| `internal` | 真 bug | 报上来 |

---

## 实测过的完整流程

```bash
board add --title "某个任务" --json          # → {value:{id:"C1119-xxxx"}, next:[...]}
board comment C1119-xxxx "开工" --as agent    # 重发一次也只有一条
board checklist C1119-xxxx add --text "能跑" --json
board exec C1119-xxxx open --json             # → value.execution
board exec C1119-xxxx close --execution e-xxx --json
board events C1119-xxxx --since 2 --json      # 只回后几条
board trash C1119-xxxx --json                 # 软删
board trash C1119-xxxx --restore --json       # 恢复
```

---

## 自检

```bash
python tests/test_event_stream.py     # 35 条断言，含反例闸
python tools/check.py --quick         # 21 道闸全绿
```
