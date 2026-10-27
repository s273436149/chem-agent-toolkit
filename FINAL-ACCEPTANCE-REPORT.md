# 最终验收报告（真实实验 · 第 8 次运行）

日期：2026-10-27
副本：`E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi`
本次运行目录：`E:\Users\27343\Docker\acceptance-deepseek-run8-20261027`
构建 ID：`20261027T171821-354e8d22`（17:18:21 → 17:24:58，墙钟 6 分 37 秒）

## 最终结论

**未通过（阻塞：作者交付违反包布局，在 3/8 次调用后失败）。** 来源准备与发现阶段真实通过；
编写阶段交付了根级 `LICENSES.txt`，被既有包布局校验拒绝；唯一一次作者修复轮此前**只被告知**
check 定义错误（`json_equals must be an object`），于是修好该错误后仍因布局失败而终止。
独立审阅、入口关联、环境规划、Docker 构建、业务验收、catalog 晋升、安装与安装后使用全部 `not_run`。

本批暴露并已离线修复两个**阻断性**缺陷（见 §4）：作者可见的打包规则从未写明"闭合角色布局"，
以及 `finish()` 只报告第一个校验问题（导致一次修复轮被浪费）。修复后离线回归 493 OK (3 skipped)。
本批**没有**执行为验证而额外增加的任何真实调用，也没有重启、续批或恢复。

> 独立代码与迁移审查由**当前执行代理**完成，依据源码、调用路径与反例；**并非独立模型复核**。

## 1. 基线与提交

| 项 | 值 |
| --- | --- |
| 副本运行前 HEAD | `d569bb0`（`feat(prompt): record the identity of what the acceptance path actually sends`） |
| 运行前工作区 | 干净（`git status --porcelain` 空） |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，未修改 |
| 分支 | `integration/deepseek-api-backend`；未 merge / push / 发布 |
| Codex CLI | `C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009\codex.EXE`（0.164.0-alpha.11.1），仅本进程 PATH |
| DeepSeek 配置 | 官方端点，`deepseek-v4-pro`，`api_retries=0`，流式，单次 600 s，无回退 |
| 取源预检 | 通过：`Recap.py` 20,662 B / `license.txt` 1,580 B，SHA-256 与固定值一致 |
| Docker | 可用：linux/x86_64，8,115,138,560 B 内存，12 CPU（`docker info`） |
| 本批授权 | 8 次应用层调用、单次 600 s、整批 3600 s、240 s 仅观测 |

本轮运行**之后**的本地改动（不改变本批已记录的运行证据，但影响后续批次）：
`artifacts/delivery.py`（聚合反馈）、`docs/skills/packaging.md` 与 `minimum.md`（闭合布局规则）、
`tests/pipeline/test_author_feedback.py`（回归）、本报告与 `validation/deepseek-api/` 证据。

## 2. 运行 8 各阶段

| 阶段 | Provider / 模型 | 状态 | 证据 |
| --- | --- | --- | --- |
| 来源准备 | — | **通过** | `sources.lock.json`，两文件哈希匹配 |
| 发现 | Codex CLI / `gpt-6-astra` | **通过** | `candidate-discovery.json`：1 个候选 |
| 编写 | Codex CLI / `gpt-6-astra`（2 轮） | **失败** | 根级 `LICENSES.txt` → `Unsupported file role` |
| 独立审阅 | Codex CLI | `not_run` | 未达该阶段 |
| 入口关联 | DeepSeek | `not_run` | 未达该阶段 |
| 环境规划 | DeepSeek | `not_run` | 未达该阶段 |
| Docker 构建 | — | `not_run` | 未达该阶段 |
| 业务验收 | — | `not_run` | 未达该阶段 |
| catalog 晋升 | — | `not_run` | 仅 `candidate_saved`（candidates 区） |
| 安装 / 安装后使用 | — | `not_run` | 无合格正式产物 |

候选记录：`status=failed`、`error="Unsupported file role: LICENSES.txt"`、`repair_rounds=1`、
`checks=[author_or_validation: fail]`。交付文件（原样保留在证据中）：
`SKILL.md`（4,520 B）、`LICENSES.txt`（3,200 B）、`scripts/terminal_fragments.py`（1,596 B）。

## 3. 调用账本与预算

| 项 | 实际 |
| --- | --- |
| 应用层调用 | **3 / 8**（turn 1 发现，turn 2 编写，turn 3 编写修复） |
| 提供方 | 全部 Codex CLI（`gpt-6-astra`，HTTPS，medium/default）；**本批 DeepSeek 调用 0 次** |
| 单次时长 | 未触及 600 s 硬上限；CLI 内部重连未出现 |
| 批次时长 | 6 分 37 秒（3600 s 预算未触及） |
| 重试 / 回退 | `api_retries=0`；无提 provider 切换；未做认证探针 |
| 240 s 观测窗口 | `progress_watch=observe`，无终止 |
| 停止原因 | 作者修复轮后包布局校验失败（非预算、非超时、非模型不可用） |

## 4. 审查发现、修复与未解决

| # | 严重度 | 位置 | 触发条件 | 影响 | 处置 |
| --- | --- | --- | --- | --- | --- |
| F1 | **阻断** | `docs/skills/packaging.md`、`minimum.md`（作者可见上下文） | 交付任何根级非 `SKILL.md` 文件（如 `LICENSES.txt`、`LICENSE`、上游模块副本） | 候选在消耗作者调用后必然失败；本批 3/8 调用即止步于此 | **已修**：明确闭合布局（`SKILL.md` 唯一顶层文件；其余必须在 `scripts/references/examples/resources/assets` 下；许可文本放 `references/`），并加回归测试 |
| F2 | **阻断** | `artifacts/delivery.py::finish` | 同时存在包布局错误与 check 定义错误 | 修复轮只收到第一个错误，修好后仍因未告知的问题失败（本批即如此） | **已修**：一次性聚合所有问题（布局/check/issues/entry），单一修复轮可见全部；加回归测试 |
| F3 | 中 | `runtime/planner.py:126`（`pin_base_image`） | 需要"基础镜像同版重建" | 只按构建记录镜像身份，不保证重建同一镜像 | **未修**（既有已知缺口，保持显式拒绝而非静默），报告为未验证边界 |
| F4 | 信息 | 本批执行路径 | 批次在关联/规划前终止 | 三态非法输入提示、嵌套补丁、provenance 记录在本批**未被执行**；先前真实请求早于这些改动 | 如实记录，不以机制测试代替 |

未证明事项（待核查）：Markdown 定位/提取在真实候选上的行为（本批未到关联阶段，仅有机制测试）；
跨平台 manifest 已在 `artifacts/evidence.py` 以"排序无关、逐项 path/sha256/bytes"比较并有测试，但本批
未在真实冻结树上重复验证。

## 5. 能力迁移映射与证据（基于源码与调用路径）

| 能力 | 机制 | 证据 |
| --- | --- | --- |
| 发现 / 编写 / 独立审阅 | Codex CLI `NativeSession`，无工具、`--output-schema` | 本批真实运行 3 次；`test_native`、`test_components` |
| 结构化调用（入口关联、环境规划、契约诊断） | `model_call` → `deepseek_api`，本地 JSON Schema + 语义门禁 | 本批未执行；真实请求证据在 run 3–7 |
| 单一主入口与状态协议 | `pipeline` 单一编排；`runtime/service.py` 各恢复/构建入口 | `test_runtime_recovery`、`test_reconnect_recovery` |
| catalog 唯一实现 | `artifacts/store.py` + `artifacts/library.py` 门面 | 查询/安装/晋升均经 `qualify()`/`reconcile()`；`test_skill_library`、`test_delivery_protocol` |
| 交付分离 | 作者回执 `deliveries/` ↔ 冻结证据 `evidence/` ↔ 动态记录 `runs/` | `test_delivery_protocol`；`evidence.py` 冻结/校验 |
| 资格过滤 | `qualification()`/`install_from_library()` 复核当前 Docker 证据与内容撤销 | `store.py:206/423`；查询不因宿主暂不可用而永久失格（`host_unavailable` 保留记录、标 deferred） |
| 新增（本轮前） | 三态 `input_contract`、嵌套补丁、`scope-delta`、prompt provenance/契约审计 | `test_input_contract`(26)、`test_patch_encoding`(23)、`test_prompt_contract`(7)、`test_prompt_provenance`(5) |
| 删除 | 无（未删除仍被调用的成熟逻辑） | 生产树对 `validation/`、`frozen/` 的历史依赖审计为 **0** |

## 6. 未验证范围与最小剩余工作

未验证：独立审阅、入口关联、环境规划、DeepSeek 三态提示的真实执行、Docker 构建、业务验收、
catalog 晋升、安装与容器内使用、镜像丢失/漂移的破坏性验证。

最小剩余工作（需另行授权）：
1. 用修复后的代码**新开一批**正常创建（建议 8→10 次调用，因关联+审阅+规划需更多余量），
   仍受 600 s/单次、3600 s/整批、`api_retries=0`、首次 Docker 失败即停的约束。
2. 若仍要在 8 次内完成，需要在作者阶段减少往返（例如把布局规则前置到发现阶段上下文）。
3. F3（基础镜像同版重建）如需保证，必须实现 `pin_base_image` 或显式接受"镜像身份随构建记录"。

## 7. 证据与可复现

```text
validation/deepseek-api/evidence/real-batch-run8-20261027/
  batch-summary.json  summary.json  record.json  sources.lock.json  checkpoint.json
  candidate-discovery.json  run8.log
  agent-turns/00{1-discovery,2-author,3-author}/{command.json,prompt.txt,result.json}
  delivered/{SKILL.md,LICENSES.txt,scripts/terminal_fragments.py}
```

凭据扫描：本目录 0 次凭据形状命中；`.env` 值从未写入证据。

```powershell
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 493 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付（候选位于 `library/candidates/rdkit-recap-terminal-fragments`）。

## 附录 A：运行 1–7 记录（历史，结论保留）

### A.1 运行 7 结论

**未通过（阻塞：规划契约未通过 + 模型重复同一非法补丁）。** 前五个阶段真实通过；环境规划在两次尝试、4 次 DeepSeek 调用后仍未产出合格计划，第 3 次尝试提交了**与上一次完全相同**的非法补丁，被既有"无进展"规则拦下（`plan_unresolved`）。Docker 构建、业务验收、晋升、安装全部 `not_run`。

值得记录的是：运行 6 暴露的**管线崩溃缺陷**（结构化值写进文本字段导致 `TypeError` 逃逸、整批 `failed`）已修复，并在运行 7 中**验证生效**——同样的补丁现在被干净地判为无效补丁，进入修复轮而不是崩溃。

> 审查与判定由**当前执行代理**完成，非独立模型复核。

---

### A.2 运行 7 基线与提交

| 项 | 值 |
| --- | --- |
| 运行时 HEAD | `6b468fc` |
| 本次改动 | `33d087f`：policy 增加 selector 字面 token 与 patch 编码正反例；预算 8 → 12<br>`6b468fc`：`patch_plan` 应用补丁后立即按 `PLAN_SCHEMA` 校验，文本字段非文本时报 `PlanningError`<br>`2c767f4` 之后：**预算已改回 8**（运行 7 在 10/12 时因无进展停止，证明停止与预算无关） |
| 源目录（只读） | `78003de47c8bee93c705cd3a2098ee1f90646aae`，未修改 |
| 分支 | `integration/deepseek-api-backend`；未 merge / push / 发布 |
| Codex CLI | `bin\2993767bd1dfb009\codex.EXE`（0.164.0-alpha.11.1，code-mode host 齐全），仅进程 PATH |
| DeepSeek | 官方端点，`deepseek-v4-pro`，`api_retries=0` |
| 取源预检 | 通过（20,662 / 1,580 字节，哈希匹配） |

### A.3 运行 1–7 一览

| 运行 | 结果 | 根因 / 处置 |
| --- | --- | --- |
| 1 | 发现失败 | CLI 缺 `codex-code-mode-host.exe` → 换完整安装 |
| 2 | 规划 52.5 s 中断 | `_Reader` 切片超时毒化 → 已修（读取超时=剩余期限、不重试、捕获 socket） |
| 3 | 规划 3 轮语义拒绝 | `deepseek-flash` 违反三条夹具规则 → policy 加正反例 |
| 4 | 发现前失败 | 源码下载被截断 → 固定哈希正确拒绝 |
| 5 | 规划 2 轮 → 预算耗尽 | v4-pro 计划被 selector 规则拒绝；补丁 `value_json` 非法 → policy 补两条 |
| 6 | **崩溃 `failed`** | 补丁把结构化值写进 `acceptance_json` → `json.loads(dict)` `TypeError` → 已修 |
| 7 | 阻塞 `plan_unresolved` | 见 §3 |

### A.4 运行 7 各阶段

| 阶段 | Provider | 状态 |
| --- | --- | --- |
| 来源准备 | — | **通过** |
| 发现 | Codex | **通过** 166.4 s |
| 编写 | Codex | **通过**（1 次修复）247.5 s + 67.4 s |
| 独立内容审阅 | Codex | **通过** 89.1 s |
| 入口关联 | DeepSeek v4-pro | **通过**（作者声明 markdown 入口） |
| 关联独立审阅 | Codex | **通过** |
| 环境规划 | DeepSeek v4-pro | **失败**，见 §3.1 |
| 构建 / 验收 / 晋升 / 安装 | — | not_run |

#### A.4.1 规划两轮与停止点

| 尝试 | DeepSeek 调用 | 结局 |
| --- | --- | --- |
| 0 | 514.4 s，完整计划 | 拒绝：`Case acceptance requires an exact quotation from read source` |
| 1 | 251.3 s / 269.0 s / 240.8 s（3 轮） | 三轮补丁**全部**被同一 schema 错误拒绝：`Patched plan schema error: {...} is not of type 'string'`（把结构化对象写进 `case_json`）；第三轮重复同一诊断 → 触发"重复非法补丁/无进展"规则停止 |

停止码：`plan_unresolved`，detail 为 `No progress: repeated invalid plan patch: ...`。
**不是预算耗尽**（10 / 12），也**不是超时或传输失败**。

#### A.4.2 本次修复在真实运行中的验证

运行 6 的崩溃点现在表现为：

```
patch-rejection-0.json: Patched plan schema error: {'args': [...], ...} is not of type 'string'
```

即：非法补丁 → 干净的 `PlanningError` → 进入修复轮（并最终由无进展规则收尾），不再让整批 `failed`。

### A.5 运行 7 调用账本与预算

| 项 | 值 |
| --- | --- |
| 应用层调用 | **10 / 12**（当时上限 12；本次已改回 8，见 §7） |
| Codex 回合 | 4（166.4 / 247.5 / 67.4 / 89.1 s） |
| DeepSeek 请求 | 5（关联 1；规划 4，其中 3 轮为修复并全部被拒），全部 HTTP 200、无重试 |
| API 重试 / CLI 重连 | 0 / 0 |
| 单次最长 | 514.4 s ≪ 600 s |
| 批次墙钟 | 2,088 s ≪ 3,600 s |
| 终止原因 | 无进展（重复非法补丁），非预算、非超时 |

### A.6 审查发现（累计）

| # | 严重度 | 位置 | 状态 |
| --- | --- | --- | --- |
| F1 | high | CLI 缺 code-mode host | 已解决（换完整安装） |
| F7 | high | `_Reader` 超时毒化 + `connection.sock` 失效 | 已修并验证 |
| F8 | medium | 失败分支缺取证 | 已修 |
| F11 | **high** | `patch_plan` 允许把结构化值写入文本字段，`TypeError` 逃逸导致整批 `failed` | **已修并验证**（`6b468fc`） |
| F9 | medium | 规划对验收契约的遵守 | **未收敛**：每次失败点不同（selector token → 资源引用 → 用例引用 → 补丁编码），第 7 次尝试还重复了同一非法补丁 |
| F10 | medium | 编写回合接近单次上限（247 s / 500 s 波动） | 观察项 |
| F3 | medium | `pin_base_image` 未实现 | 未实测 |
| F4/F5/F6 | low/info | 入口声明范围、渲染确定性、参数映射 | 已记录 |

**待核查**：跨平台换行下的 manifest 严格性；"较新审阅拒绝对旧计划恢复"缺真实反例。

### A.7 运行 7 未验证范围

规划通过、计划语义门禁通过、Docker 构建、全部业务验收、catalog 晋升、默认/候选查询、隔离安装、容器内实际使用。

### A.8 运行 7 最小剩余工作（需授权）

0. **预算**：`validation/deepseek-api/acceptance-normal-input.json` 当前是 **12 次**
   （运营者本轮临时上调；此前曾改回 8）。运行 7 在 **10/12** 因"重复非法补丁/无进展"
   停止，因此**停止点与预算无关**。
1. **已实现、尚未验收的协议改动**（本轮仅代码 + 离线验证，0 次真实模型调用）：
   * **嵌套指针**：`/acceptance_json/<pointer>`、`/tests/<i>/case_json/<pointer>` 先解码
     该 JSON 文本字段、在内部应用指针、再重新编码；改一条 check/selector/断言不再需要
     重发整段文档，也不必双重编码或整段替换 `/tests`。锁定计划仍禁止触碰
     `/tests` 与 `/acceptance_json`，补丁仍是全有或全无。
   * **撤回范围带保护**：锁定修复只能增长；被拒草稿的修复可撤回**自己**过度承诺的
     用例/用途/检查，但调用方给定的必需用例名、已接受用例内容与上游 fixture 不可删改；
     全量重写走同一检查，撤回写入 `planning/<n>/scope-delta-<k>.json`，不静默缩范围。
   * **资源评估可诚实表达**：`status=unknown` 不再要求引用，但须在 `unresolved` 写明
     未定项；执行策略不变，`resources_unknown` 仍阻止 Docker。
   * **policy 去重**：capture_stdout、case_json 键表、修复期范围保持各只保留一处权威
     表述（fixture 示例仍是可执行反/正例）。
   * **非法输入三态化（按 operation）**：`required` / `none_documented` /
     `not_applicable` 分开判定，"要求"与"是否已验证"分开输出
     （`coverage_complete` / `validation_gaps` / `blockers`）。判定依据包含**交付接口
     自己的承诺**（作者/配置声明的拒绝检查、独立审阅过的要求引文、调用方 requirements
     文本），上游沉默不能豁免；`none_documented` 要求记录检查材料及其指纹、范围、理由、
     limitation 与独立确认，且**不能**替代用户明确要求的非法输入验收——缺独立审阅产物时
     `invalid_input_review_missing` 阻塞。修复轮降级必须带证据，锁定契约不可改。
   * **提示协议已与校验器同步**：三态规则只有一处权威文本（`INPUT_CONTRACT_SPEC`），
     同时渲染进 POLICY 正文与 `acceptance_json` 的 schema description，两者无法各说各话；
     修复协议抽成生产与审计共用的 `patch_protocol()`。`verify_prompt_contract.py` 离线重建
     POLICY、补丁协议、两份 schema 以及**冻结的** prompt/schema 并核对：校验器要求的字段与
     状态必须出现，旧的"两态/整段替换"表述必须消失，修复反馈必须点名缺失证据。审计接入
     测试套件（`test_prompt_contract`），规则与提示脱节即失败。
     代价是提示变大：POLICY 9.5 KB → 12.1 KB，schema description 3.9 KB → 5.7 KB，
     frozen prompt 12,291 B → **14,814 B**（已重新冻结）。
   * **正式验收路径只用当前代码生成 prompt/schema，并记录最终发送指纹**：生产代码不读取
     `validation/deepseek-api/frozen/`（审计断言 0 处引用），每轮提示由
     `planner.build_prompt()`、答案 schema 由 `planner.schema_for()` 从当前模块对象生成；
     每轮在审计目录写入 `prompt-<n>.txt` 与 `prompt-provenance-<n>.json`（prompt/schema/
     policy/acceptance description 的 sha256 与字节数），两种后端的 receipt 都记录
     `prompt_sha256`/`prompt_bytes`/`schema_sha256`（DeepSeek 另记请求体 `messages_sha256`）。
     `validation/deepseek-api/prompt-provenance.json` 离线固化当前代码身份，并用**真实
     planner** 跑到首次模型调用之前，复现已保存 RECAP 案例的 round-0 提示
     （`95f48639…`，schema `141f8b01…`）与其冻结夹具（`50460c7d…`）不同，证明验收不依赖该夹具。
     校验：`verify_acceptance_prompt.py check`、`tests/pipeline/test_prompt_provenance.py`。
   * 这些改动没有放宽任何验收门禁，但**也没有被真实批次验证**。RECAP 历史已接受计划仍是
     `required`（引用交付 `entry/skill.py` 的空白校验），`verify_original_case check`
     显示它在未放宽的门禁下通过（8 个用例）；因此该案例不会、也不应靠新增
     `none_documented` 过关。
2. 之后重跑唯一一批（12 次预算、3600 s、新隔离目录）。
3. 若仍不收敛，则需要重新评估：要么接受"该模型在 8–12 次预算内无法满足这套验收契约"，要么改变策略（更强模型/更多预算/把这套契约拆成可迭代的更小步骤）。

### A.9 运行 7 证据

```
validation/deepseek-api/evidence/
  real-batch-20261027/  real-batch-run2-20261027/  real-batch-run3-20261027/
  real-batch-run4-20261027/  real-batch-run5-20261027/  real-batch-run7-20261027/
```
运行 6（崩溃）的证据并入本报告的 F11 描述与运行 7 的验证记录；凭据在全部运行树中出现 **0 次**。

```powershell
cd E:\Users\27343\Docker\chem-agent-toolkit-integration_deepseekapi
$env:PATH = 'C:\Users\27343\AppData\Local\OpenAI\Codex\bin\2993767bd1dfb009;' + $env:PATH
python -m creation_pipeline build validation/deepseek-api/acceptance-normal-input.json `
  --state-dir <new>\state --library-dir <new>\library
python -m unittest discover -s tests -q      # 490 OK (3 skipped)
```

**最终 SKILL.md**：未形成合格交付（候选在 `library/candidates/`）。

### A.10 运行 7 边界声明

未通过只说明：在 12 次预算内该模型未产出满足既有验收契约的计划，且修复轮出现重复无进展。它不说明门禁有误，也不说明历史 600 s 超时根因已解决、性能达标或版本可合并。未执行 merge / push / 发布，未修改源目录，未删除共享镜像；未自动重启、续批或恢复。
