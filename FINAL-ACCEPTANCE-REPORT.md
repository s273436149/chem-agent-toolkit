# 最终验收报告（真实实验）

日期：2026-10-27　副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`

## 最终结论

**未通过（部分完成）。** 架构迁移与代码审查无阻断问题；**正常新创建的 5 个阶段真实通过**（来源准备、发现、编写、独立审阅、入口关联），**环境规划阶段被调用并产出了 3 份完整计划，但均被未改动的验收夹具门禁拒绝**；第 3 轮修复后 **8 次调用预算耗尽**，按规则停止。Docker 构建、业务验收、catalog 晋升、安装与安装后使用全部 `not_run`。

失败原因分类：**计划语义拒绝 ×3 → 预算耗尽**。不是传输失败、不是超时、不是环境缺失。

> 审查与判定由**当前执行代理**完成，非独立模型复核。

---

## 1. 基线与提交

| 项 | 值 |
| --- | --- |
| 副本 HEAD（运行 3 时代码） | `3cc5be9` |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，未修改 |
| 分支 | `integration/deepseek-api-backend`；未 merge / push / 发布 |
| Codex CLI | `bin\2993767bd1dfb009\codex.EXE`（`codex-cli 0.164.0-alpha.11.1`，code-mode host 齐全）；仅进程 PATH 前置 |
| DeepSeek | 官方 `https://api.deepseek.com/chat/completions`，`deepseek-flash`，`api_retries=0` |
| Docker | `29.8.2`，`linux/x86_64`（未构建） |

## 2. 三次运行的关系（必读）

| 运行 | 结果 | 关键点 |
| --- | --- | --- |
| 运行 1 | 发现阶段失败 | Codex CLI 缺 `codex-code-mode-host.exe`（环境缺陷） |
| 运行 2 | 规划阶段 52.5 s 中断 | **本地读取缺陷**：5 秒切片超时后重试同一 reader → `OSError: cannot read from timed out object`；且 `Connection: close` 时 `connection.sock` 为 `None` 使切片静默失效 |
| 运行 3 | 规划 3 轮全部语义拒绝 → 预算耗尽 | 读取缺陷修复后，规划真实返回计划 |
| 运行 4 | **发现阶段失败** | 源码下载被截断（11,024 B vs 固定 20,662 B），固定 SHA-256 命中失败 → 门禁正确拒绝，仅剩 license，agent 如实报 blocked。`deepseek-v4-pro` 与新 policy **未被触达** |

运行 2 的中断曾被推断为"代理/网络切断长连接"，**该归因已撤回**；真实原因见 §5 F7。

## 3. 运行 3：各阶段

| 阶段 | Provider | 状态 | 证据 |
| --- | --- | --- | --- |
| 来源准备 | — | **通过** | 2 个 URL，SHA-256 与固定值一致，记录 upstream commit + snapshot_id |
| 发现 | Codex | **通过** | 120.1 s，产出候选 `rdkit-recap-terminal-fragments` |
| 编写 | Codex | **通过** | 171.9 s，交付 SKILL.md + references（无脚本） |
| 独立内容审阅 | Codex | **通过** | 71.2 s，`content_review=pass`、`structure=pass`、`runtime_paths=pass` |
| 入口关联 | **DeepSeek** | **通过** | 1 次请求；提案 + 精确引用 + 独立审阅 `binding_verified=true` |
| 环境规划 | **DeepSeek** | **失败（语义）** | 3 轮，见 §4 |
| Docker 构建 / 业务验收 / 晋升 / 查询 / 安装 | — | not_run | 0 次构建 |
| 离线回归 | — | **通过** | `412 tests OK (3 skipped)`（限于 `3cc5be9` 及之前） |

候选停在该库 `candidates/` 区，未晋升、未安装。

### 3.1 运行 4（`deepseek-v4-pro` + 强化 policy 之后）

按授权改了代码（`1e4112e`：`api_model=deepseek-v4-pro`；`planner.POLICY` 增加三条夹具约定的正反例；小型冻结夹具重新冻结），全量回归 **412 OK**，随后重跑。结果在**发现之前**就失败：

* 来源获取把 `Recap.py` 存成 **11,024 字节**（sha256 `ff168a13…`），而配置固定 **20,662 字节**（`d4f9b969…`）；
* 获取端记录 `Source hash differs from configuration`，**正确地拒绝**了这份字节，只保留 license；
* 发现 agent 因此如实报 blocked（"RECAP behavior could not be grounded in source"）；
* 账本只用 **1 / 8** 次调用，0 次 DeepSeek 请求、0 次构建。

事后复检网络（只读、不耗调用）：对同一 URL 连续 4 次抓取**全部被截断**：

```
IncompleteRead(6890 bytes read, 13772 more expected)
IncompleteRead(11024 bytes read, 9638 more expected)
IncompleteRead(9646 bytes read, 11016 more expected)
IncompleteRead(11024 bytes read, 9638 more expected)
```

即**当前网络路径在稳定截断该响应**（Content-Length 声明 20,662 字节）。所以这不是重跑能绕过的偶发问题，也不是代码缺陷；**`deepseek-v4-pro` 与新 policy 尚未被真实触达**。

## 4. 规划三轮的实际拒绝链（本轮核心证据）

| 轮次 | DeepSeek 调用 | 响应 | 门禁诊断 |
| --- | --- | --- | --- |
| 0 | 146.4 s，HTTP 200，1 次请求 | 11,407 B（完整 plan） | `capture_stdout must be boolean with an explicit output_file` |
| 1 | 18.1 s | 2,366 B（patch） | `Plan schema error: ... is not of type 'string'`（`case_json` 被写成对象而非 JSON 文本） |
| 2 | 49.4 s | 2,614 B（patch） | `Behavior test requires assertions or explicit test runner` |
| 3 | 仅构建 prompt（55,820 B），**未发起调用** | — | 8 次预算耗尽 → `RuntimeBlocked('explicit_budget')` |

关键判读：

* 三条诊断**都是既有、已文档化的约定**（`planner.POLICY` 明确写了 `capture_stdout`/`output_file` 语义、"no assertions means …"；`case_json` 在 schema 中就是 string）。因此这是**模型未遵守契约**，不是门禁过严，也不是 prompt 缺失。
* 管线行为正确：拒绝 → 带诊断反馈重试 → 无进展/预算到顶即停；没有降低任何断言，没有人工改计划。
* 传输层完全正常：3 次调用全部 `completed`，无重试（`api_retries=0`），无重连。

## 5. 审查发现
| # | 严重度 | 位置 | 触发 | 影响 / 状态 |
| --- | --- | --- | --- | --- |
| F1 | ~~high~~ 已解决 | Codex CLI 缺 code-mode host | 带工具回合 | 换完整安装后 3 次运行的 Codex 回合全部成功 |
| F7 | **high（已修复）** | `deepseek_api._Reader._fill()` | 读取静默超过 5 s 切片 | 旧实现把健康慢流判成连接中断；`Connection: close` 时切片又静默失效。已改为"读取超时=剩余期限、超时即 `model_timeout`、永不重试"，并在 `connect()` 后捕获 socket。运行 3 中规划 3 次调用全部成功，直接证明修复有效 |
| F8 | medium（已修复） | 失败分支 | 任何读取失败 | 现记录 `bytes_received`/`errno`/异常原文 |
| **F9** | **medium（本轮新发现）** | 规划输出契约 | `deepseek-flash` 生成测试夹具 | 3 轮连续违反 3 条既有约定；在 8 次预算内未收敛。换模型/加预算/加提示均需授权 |
| F3 | medium | `pin_base_image` 未实现 | 需要固定 base digest | 本轮未构建，未实测 |
| F4 | low | 声明入口可为任意已交付 `.py/.sh` | 作者声明示例文件 | 本轮未出现；由关联+审阅+计划校验兜底 |
| F5 | low | 渲染确定性（两次渲染字节相同） | — | 可复现限于同一 base digest |
| F6 | info | DeepSeek 参数映射 `medium→high`、`service_tier` 不发送 | — | 已分列记录，不声称等价 |

**未证明的疑点**：跨平台换行下的 manifest 严格性；"较新审阅拒绝对旧计划恢复"只有代码路径与文档，未有真实反例验证 → **待核查**。

## 6. 调用账本与预算（运行 3）

| 项 | 值 |
| --- | --- |
| 应用层调用 | **8 / 8（耗尽）** |
| Codex 回合 | 5（发现、编写、内容审阅、关联审阅；其中关联审阅计入 runtime 守卫） |
| DeepSeek 请求 | 4（关联 1 + 规划 3），全部 HTTP 200 |
| 重试（API 层） | 0（`api_retries=0`） |
| CLI 内部重连 | 0 |
| 单次最长 | 171.9 s ≪ 600 s |
| 批次墙钟 | 757 s ≪ 3600 s |
| 240 s 观测 | 各回合最大静默远低于 240 s，未触发 |
| 终止原因 | **预算耗尽**（`explicit_budget`），非超时、非传输失败 |

## 7. 未验证范围与最小剩余工作

**未验证**：规划通过、计划语义门禁通过、Docker 构建、全部业务验收、catalog 晋升、默认/候选查询、隔离安装、容器内使用。

**最小剩余工作（需授权）**

1. **F9 收敛路径**（三选一或组合，均需你决定）：
   * 提高本批调用上限（如 12），让修复轮走完 —— 观察用；
   * 换更强的 DeepSeek 模型（如 `deepseek-v4-pro`）后重跑 —— 需授权变更模型，并会改变"第一阶段验证过的模型"这一前提；
   * 在规划 policy 里把三条被违反的夹具约定写成**更具体的正例/反例**（不改门禁、不放宽断言，属文档强化）。
2. 重跑唯一一批（新的 8 次预算、3600 s，新隔离目录）。
3. 若构建与业务验收通过，再执行默认查询、隔离安装与容器内使用核验。

## 8. 证据与复现

脱敏证据（凭据在三个运行树中出现 **0 次**）：

```
validation/deepseek-api/evidence/
  real-batch-20261027/       运行 1：发现阶段环境阻断
  real-batch-run2-20261027/  运行 2：规划 52.5 s 读取中断（含失败现场）
  real-batch-run3-20261027/  运行 3：3 轮规划响应 + 3 份 rejection + 账本 + 绑定
```

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 412 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付；候选位于 `library/candidates/rdkit-recap-terminal-fragments`（候选态，不构成交付资格）。

## 9. 边界声明

本批未通过只说明：在 8 次预算内，`deepseek-flash` 未能一次或三轮内产出符合既有夹具约定的计划。它不说明门禁有误，也不说明历史 600 s 超时根因已解决、性能已达标或整个版本可合并。未执行 merge / push / 发布，未修改源目录，未删除共享镜像或历史产物；未自动重启、续批或恢复本次运行。

## 10. 本轮提交

`3cc5be9`（读取缺陷修复 + 报告/文档更正）、`d98beb8`、`eb90c4d`、`84e9253`。
