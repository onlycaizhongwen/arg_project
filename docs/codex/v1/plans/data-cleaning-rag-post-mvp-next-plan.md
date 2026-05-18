# 数据清洗与 RAG 服务后 MVP 下一步规划

## 1. 当前结论

MVP 已经完成并验证通过，当前系统已经具备：

- 文档上传、异步清洗、切块、Embedding、向量入库、语义检索主链路。
- 混合检索、粗排、去重、打散、权限标签过滤、可选重排与降级。
- 文档删除、更新、索引重建、操作审计。
- document 级操作锁、失败 job 人工重试、诊断概览。
- 本地 BGE embedding 与本地 BGE rerank 验证链路。
- 对客技术方案书、接口清单、架构图、流程图、时序图等交流材料。

所以后续不再按“把 MVP 跑通”推进，而应进入“准生产化 + 对客联调准备”阶段。

## 2. 推荐路线

推荐按下面顺序推进：

1. P4-3 批量治理任务
2. P4-6 生产模型评测
3. Phase 5 对客 PoC 联调包
4. Phase 6 生产部署与运维加固

其中最应该先做的是 P4-3 批量治理任务。原因是客户真实使用时不会只管理单个文档，通常会按知识库、数据源、租户维度批量重建、批量删除、批量重试或批量巡检。如果没有批量任务模型，后续运维和交付都会靠手工脚本，不利于对客演示和长期维护。

## 3. P4-3 批量治理任务

### 目标

补齐“按批次管理文档操作”的能力，让系统从单文档治理升级为批量治理。

### 首版范围

- 新增批量任务表：`document_operation_batch`。
- 新增批量任务明细表：`document_operation_batch_item`。
- 首版优先支持批量重建索引。
- 每个 item 复用已有单文档 rebuild 能力。
- 批量任务支持状态查询和统计汇总。
- 单个 item 失败不阻断整个批次。

### 建议接口

- `POST /api/v1/document-batches/rebuild`
  - 按 `tenant_id`、`knowledge_base_id`、`source_id`、可选 `document_ids` 创建批量重建任务。
- `GET /api/v1/document-batches/{batch_id}`
  - 查询批量任务整体状态、成功数、失败数、跳过数、运行中数量。
- `GET /api/v1/document-batches/{batch_id}/items`
  - 分页查询批量任务明细。
- `POST /api/v1/document-batches/{batch_id}/retry-failed`
  - 重试失败 item，首版可先规划，是否实现看工作量。

### 状态设计

批量任务状态：

- `PENDING`
- `RUNNING`
- `PARTIAL_SUCCEEDED`
- `SUCCEEDED`
- `FAILED`
- `CANCELLED`

批量 item 状态：

- `PENDING`
- `RUNNING`
- `SKIPPED`
- `FAILED`
- `SUCCEEDED`

### 验收脚本

新增：

- `scripts/document-batch-rebuild-test.ps1`

覆盖：

- 创建多个文档。
- 创建批量重建任务。
- 查询 batch 状态。
- 查询 item 列表。
- 验证部分成功、部分跳过或失败时，批次统计准确。
- 验证已有 document 操作锁仍然生效。

## 4. P4-6 生产模型评测

### 目标

把“模型可用”升级为“模型效果、延迟、稳定性可比较”，为后续选型提供依据。

### 评测对象

- `mock`：开发兜底基线。
- `local_bge`：本地 BGE embedding。
- `local_bge + bge-reranker`：本地 embedding + 本地 rerank。
- `dashscope text-embedding-v4`：线上通义 embedding。
- 后续可扩展到通义 rerank 或其他兼容模型服务。

### 评测输出

新增：

- `scripts/model-eval.ps1`
- `samples/queries/model-eval-queries.json`
- `docs/codex/v1/trace/data-cleaning-rag-model-eval-report.md`

输出指标：

- 命中率。
- TopK 命中位置。
- P50/P95 延迟。
- rerank 是否降级。
- query 数、文档数、chunk 数。
- 当前模型配置。

### 验收标准

- 同一批样例可以在不同 provider 下重复运行。
- 报告能说明：本地 BGE 是否满足演示，通义是否适合线上联调，rerank 是否带来排序收益。

## 5. Phase 5 对客 PoC 联调包

### 目标

把当前工程整理成客户可理解、可演示、可联调的交付包。

### 交付内容

- 对客接口清单补充批量治理接口。
- 补充一份“PoC 联调步骤说明”。
- 准备标准 demo 数据集。
- 准备标准演示脚本。
- 准备问题排查手册。

### 建议文档

- `docs/codex/v1/plans/数据清洗与RAG服务PoC联调说明.md`
- `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`

### 验收标准

- 新环境能按说明启动。
- 能完成上传、检索、更新、重建、批量重建、诊断查看。
- 客户能看懂当前能力边界和后续增强路线。

## 6. Phase 6 生产部署与运维加固

### 目标

为真实环境部署补齐安全、配置、监控、容量和恢复能力。

### 建议工作

- 配置分层：开发、测试、生产环境变量模板。
- 鉴权接入：从 query 参数里的 `actor_id` 迁移到网关或认证上下文。
- 限流与超时：API、Embedding、Rerank、Qdrant、RabbitMQ。
- 日志链路：统一 `trace_id`、`job_id`、`document_id`。
- 监控出口：Prometheus metrics 或日志平台指标。
- 备份恢复：PostgreSQL、MinIO、Qdrant 数据恢复演练。
- Docker 镜像优化：尤其是 reranker 镜像体积和模型预热方式。

## 7. 近期执行建议

下一轮建议直接进入 P4-3 实现，按下面顺序做：

1. 设计并新增批量任务数据表迁移。已完成首版。
2. 实现批量重建创建接口。已完成首版。
3. 实现批量任务查询和 item 查询接口。已完成首版。
4. 让批量 item 复用已有 document rebuild 逻辑。已完成首版。
5. 补充批量任务审计事件。已完成 item 提交审计。
6. 新增 `document-batch-rebuild-test.ps1`。已完成脚本。
7. 回归现有 `smoke`、`phase2`、`document-operation-lock`、`diagnostics` 测试。已完成，`phase2` 在 `local_bge + mock rerank` 下通过。

完成 P4-3 后，再进入 P4-6 模型评测。这样路线是：先把治理能力补齐，再拿稳定的治理底座去做模型效果比较和对客联调。
