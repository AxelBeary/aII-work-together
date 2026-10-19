# HANDOFF.md — 会话交接块

> 给**下一个主会话**读。子代理读的是派工单，⛔ 两者不得混用。

## 2026-10-19 · 建席与首轮调研

- **会话**：`allworktogether` 首个主会话。
- **领地**：`E:\GithubClone\allworktogether`（本轮由发牌席全写；3 个调研席各写自己一个交件）。
- **本轮已写文件**：
  - `AGENTS.md`、`README.md`、`.gitignore`
  - `docs/governance/`：`DECISIONS.md`、`ENVIRONMENT.md`、`REGISTRY.md`、`DELEGATION-LEDGER.md`、`HANDOFF.md`
  - `docs/research/20261019-agent-board-survey/`：`00_派工总单.md`、3 份派工单、3 份交件、`99_发牌席抽验记录.md`、`98_合并摘要__发牌席__人话版.md`
  - `git init` 建**本地库**（无远程），首次提交 `575c6d9`
- **未拍板项**：**D-001 四条**（形态／agent 接入／一期范围／治理强度）。**新会话先问用户这四条是否已拍板**。
- **已写文件默认只读**（除本文件与 REGISTRY／LEDGER 的追加行）。
- **下一步**：
  1. 用户拍板 D-001；
  2. 按拍板结论出「一期最小闭环」设计（`docs/design/`）；
  3. **首个施工批次开工前**必须建最小回归库（≥10 条）＋做反向测试（全局规则 §1）；
  4. 若要继续调研，只建议精读 **Symphony 的 SPEC.md**（唯一「规格级可抄」件）——需用户点名，⛔ 不自行扩面。
- **本轮教训（已入 ENVIRONMENT）**：
  - **免费模型池不可裸派**：3 席全败于 `abusive traffic from this IP`，指定 `opencode-go/gpt-6-luna` 后一次通过。
  - **子代理自报不可信，但抽验命中率不错**：5 条抽验 4 条属实，唯一错误是链接路径（内容无误）。**⇒ 抽验该抽「数字与链接」，不必抽「结论」**。

