# 最终验收报告（真实实验 · 第二次运行，使用完整 Codex CLI）

日期：2026-10-27
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
运行目录：`E:\Users\27343\Docker\acceptance-deepseek-run2-20261027`（`state/` + `library/`，全新隔离）

## 结论

**未通过（部分完成）。** 前五个阶段真实通过——来源准备、发现、编写、独立审阅、**入口关联（DeepSeek）**——然后在**环境规划**阶段，DeepSeek 的流式响应在 52.5 秒时被连接错误打断，规划未产出，后续 Docker 构建、业务验收、catalog 晋升、安装与安装后使用全部 `not_run`。

按停止规则：不重试、不续批、不恢复、不切换提供方（`api_retries=0` 未被违反）。预算使用 **6 / 8** 次应用层调用，墙钟约 **11 分钟 / 3600 秒**。

> 审查与判定由**当前执行代理**完成，非独立模型复核。

---

## 1. 基线与提交

| 项 | 值 |
| --- | --- |
| 副本 HEAD（运行时代码） | `eb90c4d`（本轮证据与本报告随后提交） |
| 工作区 | 运行前干净 |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，未修改 |
| 分支 | `integration/deepseek-api-backend`；未 merge / push / 发布 |
| Codex CLI | `C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.EXE`，`codex-cli 0.164.0-alpha.11.1`，`code-mode-host` 齐全；**仅进程 PATH 前置**，未改系统配置、未重装 |
| Docker | `29.8.2`，`linux/x86_64` |
| DeepSeek | 官方 `https://api.deepseek.com/chat/completions`，`deepseek-flash`，`api_retries=0`，streaming |

## 2. 调用链（实测）

| 阶段 | Provider | 实测证据 |
| --- | --- | --- |
| 发现 | Codex CLI | 138.3 s，7 个 tool 事件，usage 完整（in 104,222 / out 3,275） |
| 编写 | Codex CLI | 184.6 s，7 个 tool 事件，usage 完整（in 381,797 / out 7,610） |
| 独立内容审阅 | Codex CLI | 77.1 s，9 个 tool 事件，usage 完整（in 185,395 / out 1,322） |
| 入口关联 | **DeepSeek** | 1 次请求，18.5 s，`completed`，HTTP 200 |
| 关联独立审阅 | Codex CLI | `status=pass`、`binding_verified=true`、`requirement_assessment=confirmed` |
| 环境规划 | **DeepSeek** | 1 次请求，52.5 s，**失败**：HTTP 200 + SSE 后读响应 OSError |

无自动回退、无提供方切换。

## 3. 各阶段状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 来源准备 | **通过** | 2 个 URL，SHA-256 与固定值一致；记录 upstream(repo/commit/path/sha256) 与 snapshot_id |
| 发现 | **通过** | 产出候选 `rdkit-recap-terminal-fragments` |
| 编写 | **通过** | 交付 `SKILL.md`(5,643 B) + `references/source-notices.md`(4,738 B)，**未交付脚本** |
| 独立内容审阅 | **通过** | `content_review=pass`、`structure=pass`、`runtime_paths=pass` |
| 入口关联 | **通过** | 作者声明 `{"kind":"markdown_python","path":"SKILL.md","block_index":0}` → 校验通过 → DeepSeek 提案 → 精确引用校验 → 独立审阅批准 |
| 环境规划 | **失败（传输）** | 见 §4 |
| Docker 构建 | not_run | 0 次构建 |
| 业务验收 | not_run | `source-terminal-example` / `valid-empty-fragments` / `reject-blank-input` 均未执行 |
| catalog 晋升 | not_run | 候选停在该库 `candidates/` 区（`candidate_saved`），未晋升 accepted |
| 默认/候选查询、安装、安装后使用 | not_run | 无正式产物 |

## 4. 首个阻断点

```
阶段   environment planning（单次 DeepSeek 规划请求）
请求   POST https://api.deepseek.com/chat/completions  model=deepseek-flash
参数   stream=true, response_format=json_object, max_tokens=65536,
       thinking=enabled, reasoning_effort=high（requested medium）
回执   HTTP 200, content-type: text/event-stream
结果   52.5 s 时读响应抛 OSError → error_class=model_stream_interrupted
重试   0（api_retries=0，未违反）
计划   未产出；本地 schema 校验未执行；未进入 Docker
```

规划 prompt 已按正式路径构建：**46,295 字节**，sha256 `4c3ef47a…c882`；schema 为未改动的 `PLAN_SCHEMA`（sha256 `7e53e6be…0818`）。

对比同一批内的关联调用（18.5 s、小 prompt）成功，失败只出现在这个长 prompt 的流式规划上——指向**长连接流被中断**（代理/网络侧），而不是请求构造或认证问题。该判断为**推断**，未用额外调用验证。

## 5. 本轮真正被验证的新能力

这是上次（`84e9253`）入口声明改造的**首次真实端到端验证，并通过**：

* 作者在交付回执里声明 `{"kind":"markdown_python","path":"SKILL.md","block_index":0}`；
* 系统校验：SKILL.md 只有一个完整 python 围栏 → 抽取唯一；`block_index=0`；静态检查通过；
* 绑定落盘 `binding.json`：`declaration_source=author_declaration`、`association=reviewed`、
  `code_sha256=e5cca3f3…a307`、`markdown_sha256=2792eade…2e18`、`files` 清单 2 个文件、
  来源 `recap/document.py` 精确引用 `>>> res = Recap.RecapDecompose(m)`；
* 独立审阅 `binding_verified=true`；
* 计划校验器未运行（规划未产出），所以"计划必须调用该入口"这一层本轮**未被验证**。

**歧义政策未触发**：交付里没有脚本，只有一个 Markdown 代码块，因此保守识别本身也够用；声明机制是"顺带被真实走通"，不是唯一解。

## 6. 调用账本与预算

| 项 | 值 |
| --- | --- |
| 应用层已用调用 | **6 / 8** |
| Codex 回合 | 4（发现、编写、内容审阅、关联审阅） |
| DeepSeek 请求 | 2（关联 1 次完成；规划 1 次失败） |
| 实际后端请求合计 | 6（无 CLI 内部重连，事件流中 reconnect 通知 0） |
| 单次最长 | 184.6 s（编写） ≪ 600 s |
| 批次墙钟 | 约 659 s ≪ 3600 s |
| 进度观测 | `observe_only`，各回合最大静默 3.95–8.11 s，未触发 240 s 窗口 |
| 预算耗尽 | 否（因传输失败终止，不是预算） |

## 7. 审查发现（更新）

| # | 严重度 | 位置 | 触发 | 影响 / 状态 |
| --- | --- | --- | --- | --- |
| F1 | ~~high~~ 已解决 | Codex CLI 缺 `codex-code-mode-host.exe` | 带工具回合 | 上批阻断；本轮换完整安装（0.164.0-alpha.11.1）后，4 个 Codex 回合全部成功 |
| F2 | medium（流程） | 启动检查方法 | 只看 `--version/--help` | 已更正为"能跑完带工具回合"；本轮由此方式跨过 |
| **F7** | **high（本轮阻断）** | `deepseek_api._Reader._fill()` 读 SSE 时 OSError | 长 prompt（46 KB）流式规划，约 52 s | 规划未产出 → 整批停止。仅 1 次观测，未证明可复现 |
| **F8** | medium | 失败分支未记录已收字节数/chunk 数/errno | 任何流中断 | 无法区分"未收到任何数据"与"收到 N KB 后中断"，影响定位；建议下次前补上 |
| F3 | medium | `pin_base_image` 未实现（显式报错） | 需要固定 base digest | 本轮未构建，未实测影响 |
| F4 | low | 声明入口可为任意已交付 `.py/.sh` | 作者声明示例文件为入口 | 本轮未观察到滥用；由关联+审阅+计划校验兜底 |
| F5 | low | 渲染确定性（两次渲染字节相同 `c8f5695d…c891`） | — | 可复现仅限同一 base digest |
| F6 | info | DeepSeek 参数映射 `medium→high`、`service_tier` 不发送 | — | 已分列记录，不声称等价 |

未变化的历史结论：上一阶段那次单请求回放仍为"传输/schema 通过、计划语义被未改动门禁拒绝"（`c165aa5` 证据），本轮**没有重跑它**。

## 8. 未验证范围与最小剩余工作

**未验证**：环境规划成功产出、计划语义门禁（`preparation.validate`）、Docker 构建、全部业务验收、catalog 晋升、默认/候选查询、隔离安装、容器内实际使用。

**最小剩余工作（需你授权后执行）**

1. 先补 F8（记录失败时的字节数/errno，无模型调用，跑全量回归）。
2. 针对 F7 选择传输缓解（可同时）：
   * `api_stream=false`：规划改为单次响应，避免长连接被中途切断（仍受 600 s 总期限约束）；
   * `api_retries=1`：把一次瞬时断连吸收在同一 600 s 期限与账本内。
3. 用同一份 `validation/deepseek-api/acceptance-normal-input.json`、**新的**隔离 state/library 目录重跑唯一一批（新的 8 次预算、3600 s）。
4. 若构建与业务验收通过，再执行默认查询、隔离安装与容器内使用核验。

## 9. 证据与复现

脱敏证据（副本内，已扫描：运行树中凭据出现 0 次）：

```
validation/deepseek-api/evidence/real-batch-run2-20261027/
  verification.json                 阶段状态、账本、指纹、判定
  summary.json                      运行摘要（6 次调用、来源身份）
  record.json                       实体记录（含 runtime_preparation.gaps）
  binding.json                      作者声明 → 绑定的完整内容（含 code_sha256、files）
  association-proposal.json          DeepSeek 关联提案
  association-independent-review.json 关联独立审阅（pass, binding_verified=true）
  association-request.json / -attempts.json
  planning-request.json / -attempts.json / -error.json   规划失败现场
```

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 最后一次代码修改后：408 OK (3 skipped)
```

**最终 SKILL.md**：本批未形成可验收交付（候选在 `library/candidates/rdkit-recap-terminal-fragments`，未晋升）。其 SKILL.md 位于该候选目录内，仅为候选态，不构成交付资格。

## 10. 边界声明

一次运行未通过，不说明 DeepSeek 规划能力不足，也不说明历史 600 s 超时根因已解决；本轮只观测到规划请求在 52.5 s 被连接错误中断，未做重试对照、未做性能评估。未执行 merge / push / 发布，未修改源目录，未删除任何共享镜像或历史产物。
