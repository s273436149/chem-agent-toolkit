# 最终验收报告（真实实验 · 运行 5，`deepseek-v4-pro`）

日期：2026-10-27
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
本次运行目录：`E:\Users\27343\Docker\acceptance-deepseek-run5-20261027`

## 最终结论

**未通过（部分完成，但已是迄今最接近的一次）。** 前五个阶段真实通过；环境规划阶段 `deepseek-v4-pro` 产出了一份包含 7 条用例的完整计划，**此前被拒的三条夹具规则一条都没有再犯**，但被另一条验收契约拒绝（operation selector 必须是字面调用 token）；修复轮返回的补丁本身非法（`/output_contract` 不是合法 JSON）；随后 **8 次调用预算耗尽**，按规则停止。

Docker 构建、业务验收、catalog 晋升、安装与安装后使用：全部 `not_run`。

> 审查与判定由**当前执行代理**完成，非独立模型复核。

---

## 1. 基线与提交

| 项 | 值 |
| --- | --- |
| 副本 HEAD（运行时） | `43d0eb6` |
| 本次改动 | `1e4112e`：`api_model=deepseek-v4-pro`；`planner.POLICY` 增加三条夹具约定的正反例；小型冻结夹具重新冻结 |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，未修改 |
| 分支 | `integration/deepseek-api-backend`；未 merge / push / 发布 |
| Codex CLI | `bin\2993767bd1dfb009\codex.EXE`（0.164.0-alpha.11.1，code-mode host 齐全），仅进程 PATH 前置 |
| DeepSeek | 官方 `https://api.deepseek.com/chat/completions`，`deepseek-v4-pro`，`api_retries=0` |
| Docker | `29.8.2`，`linux/x86_64`（未构建） |
| 取源预检 | **通过**：两个 URL 均为完整 20,662 / 1,580 字节且 SHA-256 匹配 |

## 2. 五次运行的关系

| 运行 | 结果 | 根因 |
| --- | --- | --- |
| 1 | 发现失败 | Codex CLI 缺 `codex-code-mode-host.exe`（环境） |
| 2 | 规划 52.5 s 中断 | **本地读取缺陷**：切片超时后复用被毒化的 reader |
| 3 | 规划 3 轮语义拒绝 → 预算耗尽 | `deepseek-flash` 未遵守三条夹具约定 |
| 4 | 发现前失败 | 源码下载被截断（11,024 B），固定哈希正确拒绝 |
| 5 | 规划 2 轮 → 预算耗尽 | 见 §3 |

## 3. 运行 5 各阶段

| 阶段 | Provider | 状态 | 证据 |
| --- | --- | --- | --- |
| 来源准备 | — | **通过** | 2 个 URL 完整，哈希匹配 |
| 发现 | Codex | **通过** | 167.5 s |
| 编写 | Codex | **通过（1 次修复）** | 500.4 s + 91.9 s；首轮把 `UPSTREAM-NOTICES.txt` 放在包根被文件角色规则拒绝，次轮移入 `references/` 并同步 SKILL.md |
| 独立内容审阅 | Codex | **通过** | 81.5 s，`content_review=pass` |
| 入口关联 | **DeepSeek v4-pro** | **通过** | 作者声明 `{"kind":"markdown_python","path":"SKILL.md","block_index":0}`；绑定含 `declaration_source=author_declaration`、精确引用、文件清单 |
| 关联独立审阅 | Codex | **通过** | `binding_verified=true` |
| 环境规划 | **DeepSeek v4-pro** | **失败（语义 + 补丁非法）** | 见 §3.1 |
| Docker 构建 / 业务验收 / 晋升 / 查询 / 安装 | — | not_run | 0 次构建 |

### 3.1 规划两轮的实际结果

| 轮 | 调用 | 响应 | 结论 |
| --- | --- | --- | --- |
| 0 | `deepseek-v4-pro`，**505.1 s**，HTTP 200 | 13,781 B 完整计划，7 条用例（environment/interface/behavior，全部 `reference`+`supported`） | **拒绝**：`Operation selector must match a literal documented invocation token`（`acceptance.operations[0].selector` 用了正则 `{"index":0,"pattern":"^.+$"}`，而规则要求字面调用 token） |
| 1 | `deepseek-v4-pro`，203.7 s，HTTP 200 | 10,358 B 补丁 | **补丁非法**：`Invalid plan patch /output_contract: Expecting value: line 1 column 1 (char 0)`（`value_json` 不是合法 JSON） |
| 2 | 仅构建 prompt（59,866 B），**未发起调用** | — | 8 次预算耗尽 → `RuntimeBlocked('explicit_budget')` |

值得注意的是：修复轮里模型试图把 selector 换成"字面 token `terminal_fragments`"，即在验收契约里**发明**了一个源码中不存在的 CLI 调用形式——同样会被门禁拒绝。这说明它理解"要字面 token"，但选错了字面量。

### 3.2 强化 policy 的效果（可验证的正面结果）

运行 3 中被拒的三条规则，在运行 5 中**一条都没有再出现**：

| 规则 | 运行 3 | 运行 5 |
| --- | --- | --- |
| `capture_stdout` 必须与 `output_file` 同现且为布尔 | 违反（第 0 轮） | **未违反** |
| `case_json` 必须是 JSON 文本 | 违反（第 1 轮） | **未违反** |
| supported behavior 用例必须有断言 | 违反（第 2 轮） | **未违反**（7 条用例全部带断言或显式 runner） |

即：写进 policy 的正反例确实改变了模型行为；新的失败点是**另一条更深的验收契约**。

## 4. 调用账本与预算（运行 5）

| 项 | 值 |
| --- | --- |
| 应用层调用 | **8 / 8（耗尽）** |
| Codex 回合 | 4（发现 167.5 s、编写 500.4 s、编写修复 91.9 s、内容审阅 81.5 s） |
| DeepSeek 请求 | 4（关联 1；关联审阅 1 为 Codex；规划 2：505.1 s / 203.7 s） |
| API 重试 | 0（`api_retries=0`） |
| CLI 内部重连 | 0 |
| 单次最长 | 505.1 s ≪ 600 s |
| 批次墙钟 | **1,786 s ≪ 3,600 s** |
| 240 s 观测 | 未触发终止（observe-only） |
| 终止原因 | **预算耗尽**，非超时、非传输失败 |

## 5. 审查发现

| # | 严重度 | 位置 | 触发 | 影响 / 状态 |
| --- | --- | --- | --- | --- |
| F1 | ~~high~~ 已解决 | Codex CLI 缺 code-mode host | 带工具回合 | 完整安装后，运行 2/3/5 的 Codex 回合全部成功 |
| F7 | **high（已修复）** | `deepseek_api._Reader` | 读取静默/`Connection: close` | 读取超时=剩余期限、不重试；socket 在 connect 后捕获。运行 3/5 规划调用全部 `completed` |
| F8 | medium（已修复） | 失败分支 | 任何读取失败 | 记录 `bytes_received`/`errno`/异常原文 |
| F9 | **medium（本轮收窄）** | 规划输出契约 | `deepseek-v4-pro` | 三条夹具规则已收敛；剩余缺口是 `acceptance.operations[].selector` 的字面 token 规则与 patch 的 `value_json` 编码 |
| F10 | medium | `preparation`/接受度 | 编写回合接近 600 s 上限（500.4 s） | 高负载下可能触发单次超时；建议关注，不与门禁混为一谈 |
| F3 | medium | `pin_base_image` 未实现 | 需要固定 base digest | 本轮未构建，未实测 |
| F4 | low | 声明入口可为任意已交付 `.py/.sh` | 作者声明示例文件 | 由关联+审阅+计划校验兜底 |
| F5 | low | 渲染确定性（两次渲染字节相同） | — | 可复现限于同一 base digest |
| F6 | info | 参数映射 `medium→high`、`service_tier` 不发送 | — | 分列记录，不声称等价 |

**待核查**：跨平台换行下的 manifest 严格性；"较新审阅拒绝对旧计划恢复"只有代码路径与文档。

## 6. 未验证范围与最小剩余工作

**未验证**：规划通过、计划语义门禁通过、Docker 构建、业务验收、catalog 晋升、查询、安装、容器内使用。

**最小剩余工作（需授权）**

1. 在 `planner.POLICY` 里再补两条正反例（不改门禁）：
   * `acceptance.operations[].selector` 必须使用**源码里出现过的字面调用 token**，不得用 `^.+$` 之类正则，也不得发明 `terminal_fragments` 这类源码中没有的 token；
   * patch 的 `value_json` 必须是合法 JSON 文本（字符串要再套一层引号），非法 JSON 会被直接判为无效补丁。
2. 预算：8 次被 4 个 Codex 回合 + 2 次规划 + 1 次关联 + 1 次关联审阅占满，仅剩 1 次修复机会。建议下一批提高到 **10–12**，给规划留 2–3 轮修复空间（需你决定）。
3. 通过后继续一次 Docker 构建 → 全部业务验收 → catalog 晋升 → 默认查询/隔离安装/容器内使用。

## 7. 证据与复现

脱敏证据（五个运行树中凭据出现 **0 次**）：

```
validation/deepseek-api/evidence/
  real-batch-20261027/       运行 1：环境阻断
  real-batch-run2-20261027/  运行 2：读取缺陷现场
  real-batch-run3-20261027/  运行 3：v4-flash 三轮拒绝
  real-batch-run4-20261027/  运行 4：下载截断
  real-batch-run5-20261027/  运行 5：v4-pro 计划 + 两条诊断 + 账本 + 绑定
```

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 412 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付；候选在 `library/candidates/rdkit-recap-terminal-fragments`（候选态）。

## 8. 边界声明

本批未通过说明：在 8 次预算内，`deepseek-v4-pro` 的计划在验收契约上仍未一次通过，且修复轮产出了非法补丁。它不说明门禁有误，也不说明历史 600 s 超时根因已解决、性能达标或版本可合并。未执行 merge / push / 发布，未修改源目录，未删除共享镜像；未自动重启、续批或恢复。

## 9. 本轮提交

`43d0eb6`、`41db081`、`1e4112e`、`3cc5be9`，以及本报告与运行 5 证据的提交。
