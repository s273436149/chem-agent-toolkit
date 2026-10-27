# DeepSeek 结构化模型后端迁移报告

副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
分支：`integration/deepseek-api-backend`（独立 Git 历史）
报告时间：2026-10-27

---

## 0. 结论速览

| 项目 | 结果 |
| --- | --- |
| 隔离 | 副本独立 Git 历史；源目录 `78003de` 提交、`git status` 干净，未被修改 |
| 迁移范围 | **3 个结构化调用点**：入口关联、运行时规划（含 plan patch）、契约诊断 |
| 未迁移 | 发现、编写、独立审阅（`NativeSession` / Codex CLI）——按要求未重写 Agent 框架 |
| 后端选择 | 显式 `runtime.<candidate>.options.backend=deepseek_api`，默认仍是 `codex_cli`，**无自动回退** |
| 契约 | 保持 `model_call.call(...) -> (answer, receipt)`；Codex 路径逐字节未改 |
| 结构化输出 | DeepSeek 只有 `response_format=json_object`，无 caller JSON Schema，因此**强制本地 jsonschema 校验** |
| 离线测试 | 新增 **51** 个，全通过；完整回归 **383 个测试 OK，3 个跳过**（仅 POSIX 用例） |
| 真实小范围验证 | **0 次请求**：`E:\Users\27343\Docker\.env` 不存在，缺 `DEEPSEEK_API_KEY`，按失败关闭处理（未猜测、未重试、未续跑） |
| 提交 | 基线 `58917da`，实现 `43a69ce`，本报告与检查记录见后续提交 |

**唯一阻塞缺项：`E:\Users\27343\Docker\.env`（或环境变量）中没有 DeepSeek 凭据与模型名。** 因此“一次真实 planner 请求”的结构/语义/账本核验尚未发生；其余可独立完成的工作均已完成并验证。

---

## 1. 隔离与记录

### 1.1 源目录状态（只读检查）

```
路径      E:\Users\27343\Docker\chem-agent-toolkit-integration
提交      78003de47c8bee93c705cd3a2098ee1f90646aae
分支      integration/planner-timeout
标题      P2: one fixed planner request timed out silently and emits no request id
未提交改动 无（git status --porcelain 为空）
```

仓库内没有 `AGENTS.md`（`E:\Users\27343\Docker` 及其子树内 glob `**/AGENTS.md` 无结果），因此没有额外的项目级代理约定需要遵循。

### 1.2 副本与复制范围

```
目标      E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
方式      目标不存在，新建；未覆盖或删除任何已有内容
体积      约 2 MB（源目录 91 MB）
```

已复制：`creation_pipeline/`、`tests/`、`docs/`、`examples/`、`skills/`、`evaluation/`、`README.md`、`LICENSE`、`.gitattributes`、`.gitignore`。

已排除：`.git/`（改为独立历史）、`.pipeline/`（13.1 MB 运行状态）、全部 `__pycache__/`、`*.pyc`、`.pytest_cache/`、`.venv*/`、`evaluation/**/{cache,runs,results}/`。

`validation/` 共 64.7 MB 历史运行产物，只保留**既有回归必需的测试夹具**（共约 0.9 MB）：

| 路径 | 被谁使用 |
| --- | --- |
| `validation/final-acceptance-review/input-batch-1.json` | `test_batch_conditions` |
| `validation/planner-frame-gate/source-excerpts.json` | `test_planner_frame_gate` |
| `validation/final-acceptance-run/batch-2/agent-turn-001-events.jsonl` | `test_reconnect_recovery` |
| `validation/planner-schema-isolation/before/{plan,patch,summary}.json` | `test_planner_schema` |
| `validation/stage3/rdkit-library/**` | `test_runtime_recovery` |
| `validation/planner_wait_stage_support.py`、`validation/planner_frame_observation.py`、`validation/planner-wait-stage/diagnostics.py` | `test_model_wait_stage`、`test_planner_frame_gate` 的导入 |

其余历史 `validation/` 运行记录未复制；它们不影响任何测试（完整回归已证明）。

### 1.3 Git 隔离

```
git init -b integration/deepseek-api-backend
58917da  baseline: import of chem-agent-toolkit-integration at 78003de
         （该提交额外加入本副本需要的 .env 忽略规则与模板，不改任何源代码）
43a69ce  feat(model-call): opt-in DeepSeek API backend for structured ...
```

源目录从未被写入，其 `HEAD` 与 `git status` 在全部工作前后一致（见 1.1）。

### 1.4 凭据处理（重要缺项）

* `E:\Users\27343\Docker\.env` **不存在**（`E:\Users\27343\Docker` 深度 2 内也没有任何 `.env*` 文件），因此“把根目录 `.env` 复制到副本”无法执行，也没有伪造配置文件。
* 副本新增 `.env.example`（只有变量名与说明，无值），并在 `.gitignore` 中新增 `.env`、`.env.*`、`!.env.example`、`validation/**/runs/`、`validation/**/real/`。已验证：`git check-ignore -v .env` 命中 `.gitignore:12`，`.env.example` 不被忽略。
* 凭据只从进程环境或 `.env` 读取；不写入 prompt、日志、测试夹具、账本或报告；接收方返回的错误文本、审计文件在写盘前统一用解析出的密钥值 + 现有 `redact()` 双重脱敏。离线测试用哨兵密钥验证“磁盘上任何文件都不含该值”。

---

## 2. 实际切换范围（避免把局部迁移说成全部）

调用图梳理结果：结构化接口 `creation_pipeline/runtime/model_call.py:call(prompt, schema, model, ...)` 只有三个生产调用点。

| 阶段 | 代码路径 | 改前 | 改后 | 是否迁移 |
| --- | --- | --- | --- | --- |
| 发现 / 编写（`NativeSession.stage`） | `agent/backend.py` | Codex CLI | Codex CLI | 否 |
| 独立内容 / 契约审阅快照（`review_snapshot`） | `runtime/review.py` → `NativeSession` | Codex CLI | Codex CLI | 否 |
| 入口关联（`entry.associate`） | `runtime/entry.py` → `model_call.call` | Codex CLI | **DeepSeek API** | 是 |
| 运行时规划 / plan patch（`planner.plan`） | `runtime/planner.py` → `model_call.call` | Codex CLI | **DeepSeek API** | 是 |
| 契约诊断（`diagnosis.diagnose`） | `runtime/diagnosis.py` → `model_call.call` | Codex CLI | **DeepSeek API** | 是 |

因此：**planner 及其同一结构化接口的关联、诊断调用改走 DeepSeek；发现、编写、审阅仍走原 Codex CLI。** 这不等于“全部模型阶段迁移”。

`model.backend` 仍必须是 `codex_cli`（原生阶段需要），选择结构化后端的位置是 `runtime.<candidate>.options.backend`；这样既明确选择，又不会悄悄改变原生传输。`models.py` 对 `model.backend` 的拒绝行为保持不变（只是报错文本补充了正确配置位置），既有测试 `test_api_backends_rejected_at_configuration` 仍然通过。

---

## 3. DeepSeek 官方接口事实（2026-10-27 读取 api-docs.deepseek.com）

| 项 | 值 |
| --- | --- |
| OpenAI 兼容 base URL | `https://api.deepseek.com` |
| Anthropic 兼容 base URL | `https://api.deepseek.com/anthropic` |
| 端点 | `POST /chat/completions`，`Authorization: Bearer <key>` |
| 模型标识 | 文档为 `deepseek-flash`、`deepseek-v4-pro`（`deepseek-v4-flash` 为旧别名，由同一模型服务） |
| 结构化输出 | 仅 `response_format: {"type": "json_object"}`，**没有 caller JSON Schema 约束**；文档明确提示可能返回空内容、`finish_reason=length` 会截断 |
| 流 | SSE，终止符 `data: [DONE]`；usage 附在最后一个 chunk 上（该 chunk 无新增内容、带非空 `finish_reason`） |
| 完成标记 | `finish_reason ∈ {stop, length, content_filter, tool_calls, insufficient_system_resource, aborted}`，仅 `stop` 为完成 |
| 心跳 | 流式 `: keep-alive`；非流式空行；10 分钟未开始推理由服务端断开 |
| 错误码 | 400/422 请求、401 认证、402 余额、429 限流、500/503 服务端 |
| 思考与 effort | 默认开启、effort 默认 high；`reasoning_effort` 接受 `none/low/high/max`，`minimal→low`、`medium/xhigh→high` |

**本实现不猜测这些值**：endpoint 默认官方主机；模型名必须来自 `api_model` 或 `DEEPSEEK_MODEL`，缺失即报错且不发请求；非官方主机除非显式声明 `DEEPSEEK_ALLOW_CUSTOM_ENDPOINT`（仅供本地测试端点）否则拒绝，并在账本中记录为 `endpoint.kind=custom`。

> 注：本机 DNS 把 DeepSeek 域名解析到代理 fake-IP，官方文档通过同一代理读取成功；未使用任何第三方 API 地址。

---

## 4. 实现要点

### 4.1 契约与 schema

* `model_call.call` 签名新增 `backend`（默认 `codex_cli`，旧行为不变）与 `api_options`，返回契约 `(answer, receipt)` 不变。
* 后端内部固定三段处理：`json.loads` → 必须是 JSON object → `jsonschema.validate(answer, schema)`。**合法 JSON 不等于符合 schema**：不满足即 `model_schema_mismatch`，绝不交给上层当计划。
* 上层原有语义校验全部保留：`planner.validate_plan`（schema、平台、grounded 资源引用、路径、entrypoint、环境变量、锁定用例）、`preparation.validate`（入口匹配、超时）、`entry.associate` 的 jsonschema + 精确引用校验。业务脚本、断言、门禁一律未改。

### 4.2 协议与不完整输出

成功判据是**全部满足**：HTTP 200 + `finish_reason=stop` + `data: [DONE]` + 非空 content + JSON 解析成功 + 本地 schema 通过。

分类（均不会产出 answer）：

| 现象 | 错误码 |
| --- | --- |
| `finish_reason=length` | `model_output_truncated` |
| 缺 `[DONE]` / 缺 `finish_reason` / SSE 帧损坏 / 连接中断 / `insufficient_system_resource` / `aborted` | `model_stream_interrupted` |
| content 为空（JSON 模式已知现象） | `model_output_empty` |
| 非 JSON、非 object、schema 不符 | `model_output_invalid` / `model_schema_mismatch` |
| 出现 tool_calls | `model_output_invalid`（tool-free 契约） |
| 401 / 402 / 429 / 5xx | `model_auth_failed` / `model_insufficient_balance` / `model_rate_limited` / `model_server_error` |
| 连接失败 | `model_connection_failed` |
| 总期限到期 | `model_timeout` |

心跳、`: keep-alive`、重连提示都只记为“存活”，不记进程度、更不记成成功。

### 4.3 期限、重试与连接释放

* `timeout` 是**一个应用层总期限**，覆盖 DNS/连接、发送、每次读取、全部流消费以及配置的重试。读超时被切成 5 秒片只是为了复核剩余时间，**不会**被当成整体期限。
* 到期即关闭 socket 并抛 `model_timeout`；取消（`KeyboardInterrupt`）由 `finally` 先释放 response 与连接再向上传播（测试断言 `connection.sock is None`）。
* 不使用 SDK（直接 `http.client`），因此不存在隐式重试；重试必须显式配置（`api_retries` 0–3），计入账本且受同一总期限约束；认证/余额/请求格式错误永不重试。

### 4.4 账本与回执

每次结构化调用在调用方审计目录写入：`request.json`（endpoint、模型、**实际发送的参数**、prompt/schema/messages 指纹、期限范围、进度策略、状态）、`attempts.json`（逐次尝试：状态、HTTP 状态、耗时、错误分类、request id）、`stream.json`（chunk/keep-alive/字节）、成功时 `response.json`、失败时 `error.json`，以及 `schema.json`。

返回的 `receipt` 在原有字段外增加：`backend`、`provider`、`request_params`、`mapping`、`request_id`（服务返回头或 body `id`）、`request_count`、`requests`、`completion`。

**预算守卫未被改动**：`planner`/`pipeline` 的 `call_guard` 仍在请求前执行并计数；离线测试证明守卫抛错时**一次 HTTP 请求都不会发出**。

### 4.5 参数映射（不伪称等价）

| Codex 侧 | 实际发给 DeepSeek | 记录方式 |
| --- | --- | --- |
| `reasoning_effort=medium` | `thinking: {type: enabled}` + `reasoning_effort: high` | 记录 requested=`medium`、sent=`high`，注明“兼容映射，非等价” |
| `reasoning_effort=none` | `thinking: {type: disabled}` | requested/sent 均为 `none` |
| `service_tier=default` | 不发送（无对应项） | 记录“本后端不支持，仅记录不发送” |
| `transport=https` | 单次 HTTPS JSON 调用 | endpoint kind |
| 240 秒 stall watchdog | 不套用 | 心跳不是生成进度；总期限是唯一界限（DeepSeek 自身 10 分钟无推理才断开） |
| `model.name`（Codex，如 `gpt-6-astra`） | **绝不发送** | 由 `api_model`/`DEEPSEEK_MODEL` 单独提供；离线测试断言 Codex 模型名不出现在请求体中 |

---

## 5. 验证

### 5.1 离线测试（全部通过，不触真实服务）

`tests/pipeline/test_deepseek_backend.py`，**51 个用例**，使用进程内 loopback 脚本化 HTTP 服务；使用明显的假凭据值（`sk-sentinel-…`，仅用于验证 `redact()` 命中）；不读仓库 `.env`。覆盖：

1. 正常完成：SSE 流式 + 非流式（含非流式前置空行 keep-alive），回执字段、账本文件集合、请求体参数（`json_object`、`max_tokens`、`stream_options`、system 中的 schema）。
2. schema 不符：缺必填字段、类型错误、JSON 数组、非 JSON、空内容。
3. 不完整输出：`length`、缺 `[DONE]`、有 `finish_reason` 无 `[DONE]`、有 `[DONE]` 无 `finish_reason`、帧损坏、服务端中断 `insufficient_system_resource`、流中错误帧、连接中途断开、tool_calls。
4. 认证失败 401（配置 retries=2 仍只发 1 次）、402 余额、429 限流（不配置重试=1 次；配置 1 次重试=2 次且账本逐条记录）、503、连接失败。
5. 整体期限：静默 keep-alive 流在 2 秒期限内被中止（断言 `model_timeout`、耗时 < 8 秒、连接已释放）；读取间隙不被误当总期限；期限≤0 时不发请求。
6. 取消：`KeyboardInterrupt` 传播且连接释放。
7. 预算耗尽/守卫：`planner.plan` 的 guard 抛错时 0 次 HTTP。
8. 脱敏：认证失败与成功两条路径下，审计目录所有文件、回执、异常文本均不含密钥；prompt 正文不进入回执。
9. 配置：缺密钥/缺模型/非官方 endpoint/URL 内嵌凭据/未知 backend 均拒绝且 0 请求；`.env` 只读不导出；官方主机识别；`api_model` 与 `model` 身份不串用；`api_*` 参数校验。

回归：`python -m unittest discover -s tests -q` → **Ran 383 tests, OK (skipped=3)**。3 个跳过与迁移前一致（仅 POSIX 用例在 Windows 跳过）；改动前的 332 个既有测试全部通过，未修改任何断言。

### 5.2 固定 planner prompt / schema

`validation/deepseek-api/verify_planner.py`：

* `freeze`：用**生产代码路径**（`planner.plan` 走桩 `model_call.call`）生成 prompt，保存 `frozen/prompt-0.txt`（8568 B，sha256 `93b49f99…b5dc`）、`frozen/schema.json`（sha256 `7e53e6be…0818`）、`frozen/manifest.json`（含 fixture 文件哈希、binding、options）。
* `check`：离线重建并比对——prompt/schema/fixture 全部一致，且“落盘文件 == 实际发送文本（未发生脱敏替换）”为真。输出留存 `frozen/check.txt`。
* `run`：先比对冻结件，再用 `planner.plan` 发**最多一次**请求（硬上限 600 秒、`api_retries=0`、`max_read_rounds=1`、guard 在第 2 次调用前抛错），随后执行 `preparation.validate`（原有语义门禁），收集账本与脱敏检查。

### 5.3 真实小范围验证结果

```
status        blocked_model_unavailable
error_class   model_config_invalid
reason        DEEPSEEK_API_KEY is not configured (process environment or repository .env);
              no request was sent
request_count 0
guard         1 次（未发出的调用）
frozen        prompt/schema/fixture 均一致
```

存放：`validation/deepseek-api/result.json`（脱敏摘要）与 `validation/deepseek-api/evidence/blocked-config-invalid/`（prompt、`model-request.json`、`model-error.json`）。

即：**未发出任何真实请求**，没有猜测模型名，没有反复请求或续跑；未启动 Docker，未做完整业务验收。

### 5.4 尚未验证（明确列出）

* 真实 DeepSeek 响应下的结构输出、`grounded` 资源引用与 plan 语义校验结果（被 §1.4 缺项阻塞）。
* 真实请求的 `receipt`/账本/日志内容（除“配置失败、0 请求”这条已记录的路径）。
* 完整业务验收（发现→编写→审阅→Docker 构建→业务验收）：按要求**未启动**。

---

## 6. 复现方式

```sh
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi

# 1) 全量离线回归（383 个用例）
python -m unittest discover -s tests -q

# 2) 只看新增后端测试
python -m unittest tests.pipeline.test_deepseek_backend -v

# 3) 冻结 planner prompt/schema 复核（不发请求）
python validation\deepseek-api\verify_planner.py check

# 4) 补齐 .env（DEEPSEEK_API_KEY、DEEPSEEK_MODEL）后，做一次真实请求
python validation\deepseek-api\verify_planner.py run --timeout 600
```

补齐 `.env` 后若要跑完整链路（需要 Codex CLI + Docker + 凭据，本次未启动）：

```sh
python -m creation_pipeline build validation/deepseek-api/acceptance-input.json
```

`validation/deepseek-api/acceptance-input.json` 是本副本的验收配置：`model.backend` 保持 `codex_cli`（原生阶段），候选 `rdkit-recap-terminal-fragments` 的运行时选项显式写 `"backend": "deepseek_api"`、`"api_model": null`（模型名取自 `DEEPSEEK_MODEL`，不在此处猜测）、`api_retries: 0`、`model_timeout: 600`。

---

## 7. 已知限制

1. 未做真实调用，所以“所选接口的结构化输出能力”只验证到**协议与本地约束层面**（json_object 支持、无 schema 约束、必须本地校验），没有验证到真实模型的遵循率。
2. `progress_timeout`（Codex 路径的 240 秒静默看门狗）对 API 后端**不套用**：keep-alive 让“静默即故障”不成立，DeepSeek 自身在 10 分钟未开始推理时断连，因此只保留总期限。该决定被显式记录在账本的 `progress_watch` 字段。
3. 迁移只覆盖结构化调用；Codex 阶段仍消耗 `limits.model_calls`，两种后端的“一次调用”语义不同（CLI 轮次 vs 一次 HTTP 请求），本报告与 receipt 中分别标注，不声称等价。
4. 副本的 `validation/` 是既有回归夹具子集；历史运行证据留在源目录，未复制。
