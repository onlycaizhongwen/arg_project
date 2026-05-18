# 数据清洗与 RAG 服务阶段 4 实施计划

## 目标

阶段 4 聚焦“生产可控性”。阶段 3 已完成文档删除、更新、重建和最小审计，但这些能力在真实环境中还需要并发保护、批量治理、失败补偿、完整审计和异常迹象观测。

阶段 4 首版目标：

- 文档级管理操作具备互斥控制，避免更新、删除、重建互相覆盖。
- 提供失败任务的人工重试/补偿入口。
- 建立批量重建/批量删除的任务模型和执行边界。
- 扩展审计事件，从“请求留痕”升级到“请求 + 执行结果留痕”。
- 定义并输出关键异常迹象，用于后续监控告警。
- 建立生产模型评测入口，比较 mock、本地 BGE、线上通义/百炼模型链路。

## P4-1：文档级并发控制

问题：

- 当前更新、删除、重建都可直接请求。
- 如果同一 document 同时触发更新和重建，可能出现版本切换、chunk 清理、向量 upsert 的竞争。

首版策略：

- 在 `document` 表增加 `operation_status`、`operation_lock_id`、`operation_started_at`。
- 管理操作开始前尝试获取 document 级操作锁。
- 同一 document 同时只允许一个管理操作运行：`UPDATE_VERSION`、`REBUILD_INDEX`、`DELETE_DOCUMENT`。
- 操作完成或失败后释放锁。
- 超时锁允许后台巡检或人工接口释放。

验收：

- 同一 document 并发触发更新和重建时，只允许一个成功进入任务。
- 删除中的 document 不能再触发更新或重建。
- 锁超时场景有明确错误码和审计记录。

## P4-2：失败补偿与人工重试

问题：

- Worker 已有自动重试计数，但没有人工补偿入口。
- 失败后需要支持按 job 或 document_version 重试。

首版策略：

- 新增 `POST /api/v1/jobs/{job_id}/retry`。
- 只允许 `FAILED` job 重试。
- 重试时创建新的 job，复用原 document_version 和 object_key。
- 保留原 job 失败记录，不覆盖历史。
- 审计记录 `JOB_RETRY_REQUESTED`。

验收：

- 不支持格式失败的 job 不应无限重试成功，而是可产生新的失败 job 并保留原因。
- 临时依赖失败场景可通过人工 retry 恢复。
- 旧 job 与新 job 的关系可追溯。

## P4-3：批量治理任务

问题：

- 当前只支持单文档删除和重建。
- 真实场景需要按知识库、数据源、租户批量重建或批量删除。

首版策略：

- 先设计批量任务表，不急于一次性实现所有批量能力。
- 新增 `document_operation_batch` 和 `document_operation_batch_item`。
- 批量任务按 item 拆分执行，每个 item 复用单文档操作能力。
- 支持分页、限流、失败 item 重试。

验收：

- 可创建批量重建计划并查看 item 状态。
- 单个 item 失败不影响整批继续处理。
- 批量任务输出成功数、失败数、跳过数和耗时。

## P4-4：完整审计增强

问题：

- 当前审计只记录请求类事件。
- 还缺少 Worker 执行完成、失败、重试、锁冲突、批量任务结果等事件。

首版策略：

- 扩展 `document_audit_event.operation`：
  - `DOCUMENT_OPERATION_LOCKED`
  - `DOCUMENT_OPERATION_REJECTED`
  - `JOB_RETRY_REQUESTED`
  - `DOCUMENT_INDEX_REBUILD_SUCCEEDED`
  - `DOCUMENT_INDEX_REBUILD_FAILED`
  - `DOCUMENT_DELETE_SUCCEEDED`
  - `DOCUMENT_VERSION_INDEXED`
  - `BATCH_OPERATION_CREATED`
  - `BATCH_OPERATION_FINISHED`
- 审计 metadata 保留错误码、影响 chunk 数、影响 vector 数、锁 ID、批量 ID。
- 后续接入真实认证后，`actor_id` 不再信任 query 参数，而从网关或认证上下文注入。

验收：

- 更新、删除、重建不只记录请求，也记录执行结果。
- 查询审计可以看到一次操作从请求到完成的关键节点。
- 错误和拒绝原因可追溯。

## P4-5：异常迹象与监控指标

阶段 4 需要先把“系统出问题的迹象”定义清楚，后续再接 Prometheus、日志平台或 APM。

### 清洗链路迹象

| 迹象 | 指标 | 说明 |
| --- | --- | --- |
| 任务积压 | RabbitMQ ready/unacked 数量、最老消息等待时长 | Worker 消费能力不足或卡死 |
| 失败上升 | `FAILED` job 数、失败率、同类错误码聚集 | 解析、模型、对象存储或数据库异常 |
| 重试过多 | `retry_count` 分布、达到最大重试的 job 数 | 依赖抖动或不可恢复错误 |
| 处理变慢 | job 从 `PENDING` 到 `SUCCEEDED` 的 P50/P95/P99 | 文件过大、模型变慢、队列拥堵 |

### 检索链路迹象

| 迹象 | 指标 | 说明 |
| --- | --- | --- |
| 搜索无结果 | 按知识库/租户统计 zero-result rate | 索引缺失、权限过严或召回质量差 |
| 召回异常 | semantic/keyword recall count 过低或骤降 | Qdrant、FTS、Embedding 可能异常 |
| 重排降级 | `rerank_degraded=true` 比例 | rerank 服务不可用或超时 |
| 权限过滤异常 | permission filter 后结果骤降 | 权限上下文传错或标签配置错误 |
| 延迟异常 | search API P95/P99、Embedding/Rerank 耗时 | 模型服务或数据库性能问题 |

### 索引生命周期迹象

| 迹象 | 指标 | 说明 |
| --- | --- | --- |
| 版本切换异常 | 同一 document 多个 `INDEXED` 版本 | 并发控制或状态切换异常 |
| 孤儿向量 | Qdrant point 存在但 PostgreSQL chunk/version 不存在或不可见 | 删除/重建清理不完整 |
| stale chunk 增长 | `SUPERSEDED`/`DELETED` 版本 chunk 仍高频被回查 | 搜索过滤或清理策略有问题 |
| 锁长时间不释放 | `operation_started_at` 超过阈值 | Worker 卡死或操作失败未补偿 |

### 基础设施迹象

| 迹象 | 指标 | 说明 |
| --- | --- | --- |
| 存储异常 | MinIO 读写失败率、对象不存在错误 | 原文丢失会影响重建和重试 |
| 数据库异常 | PostgreSQL 连接数、慢 SQL、锁等待 | API/Worker 共享数据库压力 |
| 向量库异常 | Qdrant upsert/query 失败率、耗时 | 入库和检索都会受影响 |
| 模型异常 | Embedding/Rerank 请求失败率、耗时、维度不匹配 | 模型服务不可用或配置错误 |

## P4-6：生产模型评测

问题：

- 当前已验证 mock、本地 BGE embedding、本地 BGE rerank。
- 线上通义/百炼 embedding 已完成适配，但还缺真实 key 下的质量/延迟/成本评测。

首版策略：

- 扩展 `samples/queries` 为评测集目录。
- 新增 `scripts/model-eval.ps1`，输出不同 provider 的检索命中、延迟、rerank 降级、token/成本估算。
- 对比：
  - `mock`：开发基线。
  - `local_bge` + `bge-m3`：本地可控基线。
  - `dashscope` + `text-embedding-v4`：线上候选。
  - `external rerank` + BGE reranker：精排候选。

验收：

- 同一批 query 可以在不同模型配置下重复跑。
- 输出命中率、P95 延迟、失败率和模型配置。
- 能给出是否进入生产联调的建议。

## 推荐实施顺序

1. P4-1 文档级并发控制。
2. P4-2 失败补偿与人工重试。
3. P4-4 完整审计增强。
4. P4-5 异常迹象与监控指标输出。
5. P4-3 批量治理任务。
6. P4-6 生产模型评测。

先做 P4-1 的原因：并发控制是后续批量治理、重试补偿和审计可信的基础。如果没有 document 级互斥，批量任务会把已有竞争问题放大。

## 当前执行记录

- 2026-05-18：完成 P4-6 生产模型评测首版：新增 `samples/queries/model-eval-queries.json` 和 `scripts/model-eval.ps1`，用于在同一批样例文档和查询集下比较 `mock`、`local_bge` 与可选 DashScope `text-embedding-v4` 的命中率、检索延迟和 rerank 降级情况，并输出 JSON/Markdown 报告；本轮报告已生成到 `docs/codex/v1/trace/data-cleaning-rag-model-eval-report.md`，结果为 `mock` 8/10、`local_bge` 10/10、DashScope 10/10。
- 2026-05-18：完成 P4-3 批量治理任务首版：新增批量重建任务接口、批量任务表、批量 item 表和 `scripts/document-batch-rebuild-test.ps1` 验证脚本；首版采用 API 侧编排，逐个复用已有单文档 rebuild 能力，避免扩大 Worker 协议改动面；已通过迁移、批量重建端到端、smoke、diagnostics、document-operation-lock 回归，phase2 在 `local_bge + mock rerank` 下通过。
- 2026-05-16：完成 P4-1 文档级并发控制首版：新增 `document.operation_status`、`operation_lock_id`、`operation_started_at` 迁移；文档更新与重建使用 job_id 作为锁 ID，Worker 成功或最终失败后释放锁；删除操作使用同步锁并在删除完成后清理锁字段；新增 `DOCUMENT_OPERATION_IN_PROGRESS` 错误码和 `scripts/document-operation-lock-test.ps1` 验证脚本；锁冲突会写入 `DOCUMENT_OPERATION_REJECTED` 审计事件。
- 2026-05-16：完成 P4-2 失败补偿与人工重试首版：新增 `cleaning_job.retry_of_job_id` 迁移；新增 `POST /api/v1/jobs/{job_id}/retry`，仅允许 `FAILED` job 创建新的 retry job；retry job 复用原 `document_version` 与对象存储文件，并写入 `JOB_RETRY_REQUESTED` 审计事件；新增 `scripts/job-retry-test.ps1` 验证脚本，覆盖失败 job 重试、retry job 可追溯、审计事件和非失败 job 拒绝。
- 2026-05-16：完成 P4-4 完整审计增强：上传、更新、重建、重试消息补充 `operation` 语义；Worker 成功时写入 `DOCUMENT_VERSION_INDEXED`、`DOCUMENT_INDEX_REBUILD_SUCCEEDED` 或 `JOB_RETRY_SUCCEEDED`；Worker 最终失败时写入 `DOCUMENT_VERSION_INDEX_FAILED`、`DOCUMENT_INDEX_REBUILD_FAILED` 或 `JOB_RETRY_FAILED`；删除完成后补 `DOCUMENT_DELETE_SUCCEEDED`；审计查询支持按 `operation` 过滤；`scripts/document-audit-test.ps1`、`scripts/job-retry-test.ps1`、`scripts/document-operation-lock-test.ps1`、`scripts/phase2-eval.ps1` 和 `scripts/smoke-test.ps1` 已通过。
- 2026-05-16：完成 P4-5 异常迹象与监控指标首版：新增 `search_diagnostic_event` 表记录 `RERANK_DEGRADED` 事件；新增 `GET /api/v1/diagnostics/overview` 输出 job 失败率、RabbitMQ 队列 ready/consumer、document 操作锁滞留、rerank 降级统计和统一 signals；新增 `scripts/diagnostics-test.ps1`；同时将 `scripts/phase2-eval.ps1` 默认知识库改为每次唯一，避免多轮评测数据污染语义召回。

## 当前立即执行

建议下一步进入 P4-3：

1. 设计 `document_operation_batch` 与 `document_operation_batch_item` 最小表结构。
2. 新增批量重建任务创建与查询接口，首版按 item 复用单文档重建能力。
3. 增加批量治理验证脚本，覆盖部分成功、部分失败和统计输出。
