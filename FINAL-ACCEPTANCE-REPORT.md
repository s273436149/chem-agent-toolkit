# 最终验收报告（本轮真实实验）

日期：2026-10-27　副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
结论：**本次副本首版验收未通过 —— 阻塞于环境缺陷（Codex CLI 安装不完整），不是 DeepSeek 适配或管线代码缺陷。** 真实实验在"发现"阶段终止，未进入编写、审阅、关联、规划、构建与业务验收。

> 审查与结论由**当前执行代理**完成，并非独立模型复核；下文对每条结论标注了依据。

---

## 1. 基线、提交与工作区

| 项 | 值 |
| --- | --- |
| 副本 HEAD（实验时） | `84e925310c82917888a4d4322ff783f0ddaf0299` |
| 本轮新增提交 | 见 §9（`runtime_defaults` + 新 input + 证据 + 本报告） |
| 工作区 | 干净（提交前 `git status --porcelain` 为空） |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，`git status` 为空，未被修改 |
| 分支 | `integration/deepseek-api-backend`（独立历史；未 merge/push/发布） |

**调用链（实测确认的架构）**

| 阶段 | 传输 | 依据 |
| --- | --- | --- |
| 发现 / 编写 / 独立审阅 | Codex CLI `NativeSession.stage` | 本轮 discovery 回执 `model=gpt-6-astra`、usage 完整、`session_id` 记录 |
| 入口关联 / 规划 / 契约诊断 | DeepSeek API `model_call.call(backend=deepseek_api)` | 配置 `runtime_defaults.options.backend=deepseek_api`；本轮未到该阶段（0 次 DeepSeek 调用） |
| 回退 | 无 | 未知 backend 即报错；`api_model` 为空时不猜模型（离线用例覆盖） |

局部迁移，不是全部模型阶段迁移。

---

## 2. 启动检查（均为真实执行）

| 检查 | 结果 |
| --- | --- |
| 副本提交/工作区 | 通过（见 §1） |
| 离线回归（本轮最后一次代码修改后） | **408 tests OK（3 skipped，POSIX-only）** |
| DeepSeek 配置 | 通过：`.env` 解析出 `DEEPSEEK_API_KEY`(35) / `DEEPSEEK_MODEL=deepseek-flash` / `DEEPSEEK_BASE_URL`（官方）；`resolve()` 无网络预检：`https://api.deepseek.com/chat/completions`、kind=official |
| 凭据泄漏扫描 | 通过：本轮运行树中凭据出现 **0 次**；`.env` 未进入任何证据 |
| Codex CLI | **可解析但不完整**：`~\.codex\.sandbox-bin\codex.exe`（0.159.2），`codex_command()` 返回该路径，`isolated_options()` 生成 40 个参数并保留 provider、禁用两个 MCP 服务 —— 但缺同目录 `codex-code-mode-host.exe`（见 §4 F1） |
| Docker | 可用：`29.8.2`，`linux/x86_64` |
| 来源可达性（预检） | 通过：两个 URL 均 200，SHA-256 与固定值一致 |

未做认证探针式模型调用；正式阶段失败计入账本（见 §5）。

---

## 3. 本次实验配置（未预填 binding、不强制脚本）

* 新 input：`validation/deepseek-api/acceptance-normal-input.json`（sha256 `6c6636c7…bfb6`）
* 来源、prompt、model、execution、limits **与已核验的 normal-creation input 逐字节相同**（`sources`/`prompt` 逐字段比较为 `True`；prompt sha256 `348cb739…e837`）
* **无** `runtime.<candidate>.binding`：入口解析走正式优先级（用户绑定 → 作者声明 → 保守识别；歧义仍拒绝）
* 新增 `runtime_defaults.options`（本轮为让"候选名未知的正常创建"固定 DeepSeek 提供方而引入）：`backend=deepseek_api`、`api_model=null`、`api_retries=0`、`api_stream=true`、`api_max_output_tokens=65536`、`model_timeout=600`、`total_seconds=2400`、`reasoning_effort=medium`、`service_tier=default`、`progress_watch=observe`
* 预算：`model_calls=8`、`model_timeout=600`、`total_seconds=3600`、`repair_rounds=1`、`max_builds=1`
* 隔离目录：`E:\Users\27343\Docker\acceptance-deepseek-20261027\{state,library}`，不复用历史通过状态/镜像/验收结果

---

## 4. 独立代码与迁移审查

### 4.1 能力映射（以源码与实测为依据）

| 能力 | 状态 | 机制测试 / 证据 |
| --- | --- | --- |
| 发现/编写/审阅（NativeSession） | 保留 | `tests/pipeline/test_native.py`、`test_research.py`；本轮 discovery 真实回执 |
| 入口关联 / 规划 / 契约诊断 → DeepSeek | 适配迁移 | `tests/pipeline/test_deepseek_backend.py`（54 用例）；`c165aa5` 的 1 次真实请求记录（plan_rejected） |
| 入口声明优先（新增） | 新增 | `tests/pipeline/test_entry_declaration.py`（17 用例） |
| 共享运行时默认（新增） | 新增 | `tests/pipeline/test_runtime_defaults.py`（5 用例） |
| 单一主入口/状态协议/恢复/catalog | 保留 | `cli.py` 操作集合；`store.catalog/get/qualification`；`contracts.qualify` |
| 冻结交付 / 作者回执 / 动态执行记录分离 | 保留 | `deliveries/*.json` ↔ `evidence/*` ↔ `runtime/*` ↔ `summary.json`（`verify_bundle` 三处交叉校验） |
| 查询/安装/恢复遵守当前资格 | 保留 | `store.qualification()` 重算 `qualify()`；`package.install_bundle` 对每个 ready 项再 `qualify()` |

### 4.2 发现

| # | 严重度 | 位置 | 触发条件 | 影响 / 证据 |
| --- | --- | --- | --- | --- |
| F1 | **high（阻断）** | `~\.codex\.sandbox-bin\codex.exe` 缺 `codex-code-mode-host.exe` | 任何使用工具的 NativeSession 回合（发现/编写/审阅） | 工具路由报 `os error 2`，模型只能返回 `blocked`；本轮实测发现阶段终止。证据 `evidence/real-batch-20261027/discovery-stderr.log` |
| F2 | medium（流程） | 上一轮启动检查把"CLI 可用"当结论 | 仅用 `--version`/`--help` 验证 | 结论被高估：可解析≠可运行。本报告更正为"可解析、不完整"，并把"能用工具跑完一个回合"列为下次启动检查的硬条件 |
| F3 | medium | `planner.DEFAULTS.pin_base_image` 显式未实现（请求即报错） | 需要固定基础镜像 digest | `python:3.11-slim` 这类 tag 漂移无法检测；收据记录构建出的 image id，但不 pin base。本轮未构建，**待核查**其在重建场景的实际影响 |
| F4 | low | `entry.declared_entry()` 允许任意已交付 `.py/.sh` 作为脚本入口 | 作者把 `examples/*.py` 声明为入口 | 仍有静态检查、来源关联、独立审阅与计划校验兜底；仅残余风险，未观察到滥用 |
| F5 | low | `preparation.render()` 渲染确定（实测两次字节相同，sha256 `c8f5695d…c891`） | — | 可复现边界仅在"同一 base image digest"内成立，见 F3 |
| F6 | info | DeepSeek 参数映射（`medium→high`、`service_tier` 不发送） | — | 已在收据/账本中分列，未声称与 Codex 等价 |

已核对且未见问题的点（依据）：manifest 对每个文件比较 `path+sha256+bytes` 且比较完整列表；环境修复不得改动锁定用例（`preparation.validate` 的 `locked_cases` 指纹检查）；上游身份记录 `repo/commit/path/sha256` 与 `snapshot_id`（本轮来源准备实测）；Codex 配置隔离保留 provider 且禁用 MCP；DeepSeek 期限/取消/清理与脱敏由 54 个离线用例覆盖。

**未证明的疑点**：跨平台 manifest 在换行差异下的严格性（仅 Windows 实测）；"较新审阅拒绝对旧计划恢复的约束"仅有文档与代码路径，本轮未做真实验证 → **待核查**。

---

## 5. 实际执行结果与账本

### 5.1 阶段状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 来源准备 | **通过** | 2 个 URL，200，SHA-256 与固定值一致；记录 upstream（repo/commit/path/sha256）与 snapshot_id |
| 发现 | **失败** | 回合 1 完成（有 usage），但工具宿主起不来 → `blocked`，无候选 |
| 编写 / 独立审阅 / 入口关联 / 环境规划 | not_run | 被 F1 阻断 |
| Docker 构建 | not_run | 0 次构建 |
| 业务验收 / catalog 晋升 / 默认查询 / 安装 / 安装后使用 | not_run | 无正式产物 |
| 离线回归 | **通过** | 408 tests OK（3 skipped） |

### 5.2 调用账本（应用层）

| 项 | 值 |
| --- | --- |
| 已用调用 | **1 / 8**（discovery，Codex `gpt-6-astra`，https/medium/default） |
| 该次状态 | `completed`（提供方返回 usage：input 42831 / output 352 / cached 28288），31.4 s，2 个 tool 事件（均为 error） |
| DeepSeek 请求 | **0**（未到规划/关联/诊断阶段） |
| CLI 内部重连 | 0（events 中无 reconnect 通知） |
| 单次耗时 | 31.4 s ≪ 600 s；进度观测 `observe_only`，最大静默 3.9 s，未触发 240 s 窗口 |
| 批次耗时 | 约 36 s ≪ 3600 s |
| 预算耗尽 | 否（因阻断终止，不是预算） |

### 5.3 首个阻断点

```
discovery turn 1 → codex_core::tools::router:
failed to spawn code-mode host
C:\Users\27343\.codex\.sandbox-bin\codex-code-mode-host.exe
(os error 2)
```

分类：**环境/安装缺陷**。按停止规则：不重跑、不续批、不恢复。

---

## 6. 证据路径（副本内，已脱敏）

```
validation/deepseek-api/evidence/real-batch-20261027/
  build.log              完整 CLI 输出
  summary.json           运行摘要（状态、usage、来源身份）
  discovery-stderr.log   CLI 工具路由报错原文
  discovery-events.jsonl 发现回合事件流
  discovery-command.json 该回合实际 CLI 命令（参数已脱敏）
  verification.json      阶段状态、账本、指纹、判定（汇总）
```
运行现场（未提交）：`E:\Users\27343\Docker\acceptance-deepseek-20261027\{state,library}`。

---

## 7. 未验证范围与最小剩余工作

**未验证**：编写、独立审阅、入口关联（DeepSeek）、环境规划（DeepSeek）、一次 Docker 构建、全部业务验收、catalog 晋升、默认/候选查询、安装与安装后使用；以及 DeepSeek 在真实规划中的通过率与语义质量。

**最小剩余工作（需另行授权）**

1. 修复 Codex CLI 安装：让 `codex.exe` 同目录存在匹配版本（0.159.2）的 `codex-code-mode-host.exe`；或换用完整安装。**不自动重装**，由你决定。
2. 复检方式改为"能跑完一个带工具的回合"，而不是只看 `--version`：例如用现有 discovery 路径做一次 1 回合的最小真实调用（会计入届时的预算）。
3. 修复后，用**同一份** `acceptance-normal-input.json` 在**新的**隔离 state/library 目录重跑唯一一批（预算 8 次、3600 s）。
4. 若通过，再执行 §五 的默认查询、隔离路径安装与容器内实际使用核验。

**可用预算评估**：本轮已用 1 次（8 次预算内）；若重跑，按新的批次重新计 8 次，不叠加本次。

---

## 8. 可复现命令

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
$env:PATH = 'C:\Users\27343\.codex\.sandbox-bin;' + $env:PATH
# 配置自检（不取源、不调模型）
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json --preflight
# 唯一一批（本轮实际执行，已失败）
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir E:\Users\27343\Docker\acceptance-deepseek-20261027\state `
  --library-dir E:\Users\27343\Docker\acceptance-deepseek-20261027\library
# 离线回归
python -m unittest discover -s tests -q
```

**最终 SKILL.md 直接地址**：无（本批未生成交付物）。

---

## 9. 本轮提交

见 `git log`：`runtime_defaults` 支撑、新 input、证据与报告。未 merge/push/发布，源目录只读、未被修改。

固定案例通过与否都不证明历史超时根因已解决，也不证明性能或跨案例稳定性；本轮更未进入性能与稳定性验证。
