# 数据清洗与 RAG 服务 Phase 6 生产部署与运维加固计划

## 1. 阶段目标

Phase 6 的目标是把当前“可演示、可联调”的 PoC 工程，推进到“可进入测试/准生产环境”的工程基线。

本阶段不以继续扩展 RAG 检索能力为主，而是补齐真实环境最容易卡住交付的内容：

- 环境配置分层。
- 认证上下文与操作人来源。
- 生产观测、告警和问题定位。
- 锁滞留治理。
- 批量任务增强。
- 模型评测集扩展和容量压测。
- 备份恢复和部署发布流程。

完成后应达到：

- 测试/生产环境配置不再依赖手改 Compose 文件。
- API 操作人、租户、权限上下文有统一注入位置。
- 关键链路可以通过 `trace_id`、`job_id`、`document_id` 串联日志。
- 诊断概览可以扩展为监控指标或被日志平台采集。
- 锁滞留和批量任务失败有标准处理路径。
- 模型配置和容量指标有可复用评测口径。
- 数据库、对象存储和向量库有备份恢复演练方案。

## 2. 当前基础

已完成：

- MVP 主链路：上传、异步清洗、切块、Embedding、向量入库、检索。
- 检索漏斗：semantic、keyword、hybrid、粗排、去重、打散、权限标签、rerank 降级。
- 文档治理：删除、更新、重建、审计、document 操作锁。
- 生产可控性首版：失败 job 人工重试、批量重建、诊断概览、模型评测。
- 对客联调包：PoC 联调说明、部署运维说明、问题排查手册、演示脚本。

当前主要边界：

- `actor_id`、`request_source` 仍来自请求参数，不是可信认证上下文。
- 权限仍是最小标签交集过滤，不是真实 IAM。
- 诊断概览是 API 聚合视图，尚未输出 Prometheus 指标。
- document 锁滞留目前只能诊断，缺少安全释放接口。
- 批量治理首版只支持批量重建，不支持取消、失败项重试、批量删除。
- 模型评测样例集较小，尚未覆盖客户真实语料和并发压测。

## 3. 实施拆分

### P6-1：环境配置分层与生产模板

目标：把本地 PoC 配置、测试配置、生产配置分开，减少交付现场手改风险。

实施内容：

- 新增 `.env.local.example`、`.env.test.example`、`.env.prod.example`。
- 明确本地 BGE、DashScope、mock 三类模型配置模板。
- 明确本地镜像源、客户内网镜像源、默认公网镜像源覆盖方式。
- 将 Compose 启动说明改成按环境变量模板启动。
- 补充“生产环境敏感信息不入库”的说明，例如 `DASHSCOPE_API_KEY`、数据库密码、MinIO 密钥。

建议产物：

- `.env.local.example`
- `.env.test.example`
- `.env.prod.example`
- 更新 `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`

验收：

- `docker compose -f infra/docker-compose.yml config --quiet` 通过。
- 文档能清楚说明本地、测试、生产三套配置差异。

### P6-2：认证上下文与操作人注入设计

目标：从 query 参数里的 `actor_id`、`request_source` 过渡到可信请求上下文。

实施内容：

- 设计统一请求上下文对象：`tenant_id`、`actor_id`、`request_source`、`permission_context`、`trace_id`。
- 支持首版 Header 注入：
  - `X-Tenant-Id`
  - `X-Actor-Id`
  - `X-Request-Source`
  - `X-Permission-Tags`
  - `X-Trace-Id`
- 保留 query/body 参数兼容，但文档标记为 PoC 兼容方式。
- 审计事件优先使用 Header 上下文。
- 检索接口的 `permission_context` 支持从 Header 兜底。

建议产物：

- `services/api/app/core/request_context.py`
- 更新文档治理、job retry、batch rebuild、search 等入口。
- 更新 API 契约。

验收：

- 未传 Header 时保持现有 PoC 用例可跑。
- 传 Header 时审计事件记录 Header 中的 actor/source。
- 权限标签 Header 能影响检索过滤。

执行结果：

- 2026-05-18：已完成首版 Header 兼容实现。新增 `services/api/app/core/request_context.py`，上传、文档治理、job retry、批量重建和检索入口已接入 `X-Tenant-Id`、`X-Actor-Id`、`X-Request-Source`、`X-Permission-Tags`、`X-Trace-Id`；新增 `scripts/request-context-test.ps1` 验证 Header 覆盖租户、审计操作人/来源和检索权限上下文。

### P6-3：结构化日志与 trace_id 串联

目标：让一次上传、清洗、入库、检索能通过统一字段定位。

实施内容：

- API 请求入口生成或读取 `trace_id`。
- MQ 消息携带 `trace_id`。
- Worker 日志输出 `trace_id`、`job_id`、`document_id`、`document_version_id`。
- API 错误响应可包含 `trace_id`。
- 文档说明如何通过日志查询一次完整链路。

建议产物：

- API middleware。
- Worker 日志增强。
- 更新问题排查手册。

验收：

- 上传响应或日志中可看到 `trace_id`。
- Worker 处理同一 job 时日志包含同一个 `trace_id`。
- 排查手册有按 `trace_id` 定位示例。

执行结果：

- 2026-05-18：已完成首版 trace_id 串联。API middleware 会读取或生成 `trace_id`，响应头回传 `X-Trace-Id`，错误响应包含 `trace_id`；上传、更新、重建、retry、批量重建等 MQ 消息携带 `trace_id`；Worker 以 JSON 日志输出 `trace_id`、`job_id`、`document_id`、`document_version_id` 和 `operation`。已通过 `scripts/request-context-test.ps1`，并在 API/Worker 容器日志中确认同一 trace_id 可串联。

### P6-4：监控指标出口

目标：把诊断概览从人工查询接口扩展为可被监控系统采集的指标。

实施内容：

- 新增 `GET /metrics` 或 `GET /api/v1/metrics`。
- 输出 Prometheus text format 或 JSON 指标首版。
- 指标覆盖：
  - job 状态分布。
  - 近期失败率。
  - RabbitMQ ready 消息数和 consumer 数。
  - document 操作锁数量和滞留锁数量。
  - rerank 降级次数。
  - API 基础请求计数和错误计数。
- 文档补充告警建议阈值。

建议产物：

- `services/api/app/api/metrics.py`
- `scripts/metrics-test.ps1`
- 更新部署运维说明。

验收：

- 指标接口可访问。
- `diagnostics-test` 与新增 `metrics-test` 均通过。
- 文档有建议告警项。

执行状态：

- 2026-05-18：已完成首版 Prometheus 指标出口。新增 `GET /api/v1/metrics`，复用 diagnostics 聚合输出 cleaning job 状态/失败率、RabbitMQ 队列、document 操作锁、rerank 降级指标；新增进程内 API 请求/5xx 错误计数；新增 `scripts/metrics-test.ps1` 并更新 API 契约与部署运维说明。告警建议：`rag_cleaning_queue_available == 0`、`rag_cleaning_queue_consumer_count == 0`、`rag_cleaning_job_failure_rate > 0`、`rag_cleaning_document_lock_stale_count > 0`、`rag_cleaning_rerank_degraded_recent_count > 0`、`rag_api_request_error_total` 持续增长时需要排查。

### P6-5：锁超时释放与治理闭环

目标：document 操作锁从“可诊断”升级为“可治理”。

实施内容：

- 新增锁滞留查询接口或复用 diagnostics 明细。
- 新增安全释放锁接口，例如 `POST /api/v1/documents/{document_id}/locks/release`。
- 释放锁必须记录审计事件。
- 仅允许超过阈值的滞留锁释放。
- 对仍在运行的 job 做保护，避免误释放正常任务锁。

建议产物：

- 新增 API。
- 新增审计 operation：`DOCUMENT_OPERATION_LOCK_RELEASED`。
- `scripts/document-lock-release-test.ps1`。

验收：

- 正常运行中的锁不能释放。
- 滞留锁可释放并记录审计。
- 释放后文档可继续更新/重建。

执行状态：

- 2026-05-18：已完成首版锁超时释放治理。新增 `POST /api/v1/documents/{document_id}/locks/release`，仅允许释放超过阈值的 document 操作锁，并保护 `PENDING`、`RUNNING`、`RETRYING` 状态关联 job；释放成功写入 `DOCUMENT_OPERATION_LOCK_RELEASED` 审计事件；新增 `scripts/document-lock-release-test.ps1` 覆盖未滞留拒绝、活跃 job 拒绝、失败 job 滞留锁释放和释放后重建。

### P6-6：批量治理增强

目标：让批量治理从“批量重建首版”升级为可运维任务体系。

实施内容：

- 支持失败 item 重试：`POST /api/v1/document-batches/{batch_id}/retry-failed`。
- 支持批量任务取消：`POST /api/v1/document-batches/{batch_id}/cancel`。
- 规划批量删除：先出设计，视风险决定是否实现首版。
- batch 和 item 审计增强。
- 批量任务分页、过滤和状态统计优化。

建议产物：

- 更新 `document_batch_service.py`。
- 新增 `scripts/document-batch-retry-test.ps1`。
- 更新 API 契约。

验收：

- 批量重建部分失败后可重试失败项。
- 取消未完成批次后不再继续提交新 item。
- 已完成 item 不被重复执行。

执行状态：

- 2026-05-18：已完成首版批量治理增强。新增 `POST /api/v1/document-batches/{batch_id}/retry-failed` 和 `POST /api/v1/document-batches/{batch_id}/cancel`；失败 item 可在原批次内重新提交，已成功 item 不重复执行；取消接口仅取消 `PENDING` item；批量明细支持 `status` 过滤并返回 `total_count`；新增 `scripts/document-batch-retry-test.ps1` 覆盖失败项重试、取消 pending item 和状态过滤。

### P6-7：评测集扩展与容量压测

目标：把模型评测从“样例可用”升级为“能指导选型和容量评估”。

实施内容：

- 增加中文真实业务风格样例文档。
- 增加查询集分类：事实问答、操作步骤、故障排查、权限隔离、长尾表达。
- 扩展 `model-eval.ps1` 输出：
  - MRR。
  - Recall@K。
  - rerank 前后排名变化。
  - 并发请求延迟。
- 新增轻量压测脚本，覆盖上传吞吐和检索 QPS。

建议产物：

- `samples/queries/model-eval-queries-zh.json`
- `scripts/search-load-test.ps1`
- 更新模型评测报告。

验收：

- 本地 BGE、DashScope 可以在同一评测集下比较。
- 输出 P50/P95/P99 延迟。
- 能给出 PoC 推荐配置和生产待压测配置。

执行状态：

- 2026-05-18：已完成首版评测集扩展与轻量压测。新增中文业务样例文档 `samples/documents/demo-zh/`，新增分类查询集 `samples/queries/model-eval-queries-zh.json`，覆盖事实问答、操作步骤、故障排查、权限隔离、长尾表达和效果调优；扩展 `scripts/model-eval.ps1` 输出 MRR、Recall@K、P50/P95/P99、分类汇总和 rerank 分数覆盖；新增 `scripts/search-load-test.ps1` 输出上传吞吐、搜索 QPS 和搜索延迟 P50/P95/P99。已生成中文模型评测报告和轻量压测报告。PoC 推荐配置仍为 `local_bge/bge-m3 + mock rerank`，生产待压测配置需用客户真实语料对 DashScope、本地 BGE 和正式 rerank 服务继续对比。

### P6-8：备份恢复与发布流程

目标：把部署从“能启动”升级为“可恢复、可发布、可回滚”。

实施内容：

- PostgreSQL 备份与恢复演练。
- MinIO bucket 备份说明。
- Qdrant snapshot 或数据卷备份说明。
- Alembic 迁移发布步骤和回滚原则。
- Docker 镜像 tag 规范。
- 发布前检查清单。

建议产物：

- `docs/codex/v1/plans/数据清洗与RAG服务发布检查清单.md`
- 更新部署运维说明。

验收：

- 文档包含备份、恢复、升级、回滚步骤。
- 明确哪些操作适合 PoC，哪些必须生产审批。

执行状态：

- 2026-05-18：已完成首版备份恢复与发布流程。新增 `scripts/backup-dry-run.ps1`，可非破坏式导出 PostgreSQL 备份、检查 MinIO bucket 摘要和 Qdrant collections，并生成 `docs/codex/v1/trace/data-cleaning-rag-backup-dry-run-report.md`；新增 `docs/codex/v1/plans/数据清洗与RAG服务发布检查清单.md`，覆盖发布前冻结项、镜像 tag、发布前命令、备份恢复、Alembic 迁移原则、发布步骤、回滚原则和生产审批边界；部署运维说明已补充发布与回滚入口。备份文件目录 `backups/` 已加入 `.gitignore`，避免本地 SQL 备份误提交。

## 4. 推荐执行顺序

建议按下面顺序推进：

1. P6-1 环境配置分层与生产模板。
2. P6-2 认证上下文与操作人注入设计。
3. P6-3 结构化日志与 trace_id 串联。
4. P6-4 监控指标出口。
5. P6-5 锁超时释放与治理闭环。
6. P6-6 批量治理增强。
7. P6-7 评测集扩展与容量压测。
8. P6-8 备份恢复与发布流程。

Phase 6 已按上述顺序完成 P6-1 到 P6-8。下一步建议进入 Phase 6 收尾 trace 审查和提交前交付检查，确认生产加固计划、实现、脚本、对客文档和验证记录一致。

## 5. 验证策略

文档类变更：

```powershell
git diff --check
```

配置类变更：

```powershell
docker compose -f infra/docker-compose.yml config --quiet
```

接口类变更：

```powershell
python -m compileall services\api\app services\worker\app
.\scripts\smoke-test.ps1
.\scripts\diagnostics-test.ps1
```

模型相关变更：

```powershell
.\scripts\embedding-check.ps1
.\scripts\model-eval.ps1 -SkipMock
```

批量治理相关变更：

```powershell
.\scripts\document-batch-rebuild-test.ps1
```

备份发布相关变更：

```powershell
.\scripts\backup-dry-run.ps1
```

## 6. 风险与回滚

- 鉴权上下文改造要保持 PoC 兼容，不能一次性移除 query 参数。
- 监控指标不能引入明显请求开销，复杂统计应复用 diagnostics 已有聚合。
- 锁释放接口必须有阈值、审计和运行中 job 保护，避免破坏正在执行的清洗任务。
- 批量取消和失败项重试需要避免重复提交同一 document 的并发操作。
- 压测可能污染本地数据，应使用独立 `knowledge_base_id` 和可清理样例集。
- 本地备份演练会生成 SQL 文件，必须保留在 `backups/` 等忽略目录，不进入 Git 提交。

## 7. 下一步

下一步执行 Phase 6 收尾：

1. 补充 Phase 6 一致性 trace 审查，确认 P6-1 到 P6-8 均有对应产物和验证记录。
2. 汇总最终验证命令结果，准备提交与推送。
3. 进入 Phase 7 规划，优先建议围绕真实 IAM/SSO、正式 rerank 服务压测、客户真实语料评测和生产部署形态展开。
