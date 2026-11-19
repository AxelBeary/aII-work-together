# contracts/ · P0 契约（v1 草案）

> 状态：**草案，未冻结**。按 05 §7.2 第 5 条，TaskEnvelope v1 在 T0 缺口报告出来前不冻结。

## 三份契约

| 文件 | 管什么 | 冻结条件 |
|---|---|---|
| `task-envelope-v1.schema.json` | 任务外壳；四个面只交换这个形状 | T0 缺口报告 + 承载决议（comments/executions/checklist/settings）拍板 |
| `event-v1.schema.json` | append-only 事件 + 哈希链 + 幂等键 | epoch 进 HTTP 契约后冻结 |

## 已在 spec 里写死的硬约束（来自三席评审）

1. **`lease.epoch` 是必填写参**：任何写路径必须带；内核用 SQL CAS 判，⛔ 不用「先读后写」。
2. **`idempotency_key` 全局唯一**：重放同 key 不得产生第二条事件。
3. **`project_id` 必须匹配**：跨项目写一律拒。
4. **`meta` 是唯一扩展位**：P0 阶段 comments/executions/checklist/settings 挂这里，不拆表。
5. **`legacy_id` 保留**：迁移不丢旧编号，可对账。

## 未做

- `conformance.py` 尚未写（P0 的 T3）。
- 未与内核代码对账：schema 里的字段有几项内核还没有承载位（见 T0 缺口）。
