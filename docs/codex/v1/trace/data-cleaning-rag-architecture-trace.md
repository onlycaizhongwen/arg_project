# data-cleaning-rag-architecture 追踪报告

## 审查范围

- requirements: `docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md`
- design: `docs/codex/v1/designs/data-cleaning-rag-architecture-design.md`
- plan: `docs/codex/v1/plans/data-cleaning-rag-architecture-plan.md`
- MVP plans:
  - `docs/codex/v1/plans/data-cleaning-rag-mvp-startup-plan.md`
  - `docs/codex/v1/plans/data-cleaning-rag-engineering-init-plan.md`
- implementation:
  - `services/api`
  - `services/worker`
  - `infra`
  - `scripts`
  - `samples`

## 当前实现概览

当前 MVP 已形成一条可运行主链路：

`文件上传 -> MinIO 保存 -> PostgreSQL 记录 -> RabbitMQ 投递 -> Worker 解析/清洗/切块 -> Embedding -> Qdrant 入库 -> 语义检索`

已验证：

- Docker Compose 可启动 PostgreSQL、RabbitMQ、MinIO、Qdrant、API、Worker。
- `scripts/db-migrate.ps1` 可执行 Alembic 迁移。
- `scripts/embedding-check.ps1` 在 `local_bge` provider 下通过。
- `scripts/smoke-test.ps1` 在本地 BGE `bge-m3` 下通过。
- 本地 BGE 通过 Ollama `/v1/embeddings` 返回 1024 维向量。
- `knowledge_base_ids` 已从上传、入库、Qdrant payload 到检索过滤完成贯通，smoke 已验证错误知识库不会返回结果。
- `scripts/demo-eval.ps1` 已上传 3 份 demo 文档并执行 5 条查询，检索结果全部命中预期关键词。
- `scripts/failure-test.ps1` 已验证统一错误响应和异步失败路径。
- 阶段 2 P2-1/P2-2 已完成：`semantic`、`keyword`、`hybrid` 三种检索模式和 PostgreSQL 全文关键词召回已通过 `scripts/phase2-eval.ps1` 验证。
- 阶段 2 P2-3/P2-4 已完成：内容去重、同文档版本限额和 MMR 简化打散已进入业务干预层，并通过阶段 2 评测。
- 阶段 2 P2-5 已完成：`RerankClient` 支持 `disabled/mock/external`，外部重排不可用时返回降级结果并标记 `rerank_degraded=true`。
- 阶段 2 P2-6 已完成：上传、Worker、PostgreSQL、Qdrant payload 和检索过滤已贯通 `permission_tags` / `permission_context`，默认只返回 `public` 标签内容。

## 已对齐项

| 需求/设计项 | 当前实现 | 结论 |
| --- | --- | --- |
| 统一 Python 技术栈 | 已实现 FastAPI API + Python Worker | 已对齐 |
| 文件上传接入 | `POST /api/v1/ingestions/files` 保存文件并创建任务 | 已对齐 MVP |
| 元数据模型 | 已有 data_source、document、document_version、cleaning_job、text_chunk、vector_record | 已对齐 MVP |
| 对象存储 | MinIO 已接入，原始文件可保存 | 已对齐 |
| 异步任务队列 | RabbitMQ 投递与 Worker 消费已实现 | 已对齐 |
| 基础解析 | Worker 支持 TXT/MD/CSV/PDF 等基础解析入口 | 已对齐 MVP |
| 基础清洗 | 已实现空白、换行等基础清洗 | 已对齐 MVP |
| 文本切分 | 已实现段落与长度切分 | 已对齐 MVP |
| Embedding 适配层 | 支持 `mock`、`dashscope`、`local_bge` | 已对齐 |
| 本地 BGE | 已通过 Ollama `bge-m3` 端到端验证 | 已对齐 |
| 向量库 | Qdrant collection 写入和查询已实现 | 已对齐 |
| 语义检索 API | `POST /api/v1/rag/search` 可返回 chunk 结果 | 已对齐 MVP |
| 基础候选截断 | `recall_size`、`pre_rank_size`、`top_k` 已进入接口参数和 search plan | 已对齐 MVP 下限 |
| 知识库过滤 | `knowledge_base_id` 已写入 document、text_chunk、Qdrant payload，检索按 `knowledge_base_ids` 过滤 | 已对齐 MVP |
| Worker 幂等 | 已成功 job 跳过，chunk/vector 使用稳定 ID 和 upsert | 已对齐 MVP |
| 失败重试 | `cleaning_job.retry_count` 和 RabbitMQ requeue 已实现 | 已对齐 MVP |
| 数据库迁移 | Alembic `0001_initial`、`0002_retry_count` 已实现 | 已对齐 |
| 自动化冒烟 | `scripts/smoke-test.ps1` 已覆盖上传、处理、检索 | 已对齐 |
| Demo 样例 | `samples/documents/demo` 已提供 3 份样例文档，`samples/queries/demo-queries.json` 已提供 5 条查询 | 已对齐 MVP |
| 检索质量最小验证 | `scripts/demo-eval.ps1` 已验证 5 条查询全部命中预期关键词 | 已对齐 MVP |
| API 契约文档 | `docs/codex/v1/plans/data-cleaning-rag-api-contract.md` 已描述上传、任务查询、检索和错误响应 | 已对齐 MVP |
| 异常场景验证 | `scripts/failure-test.ps1` 已覆盖 `JOB_NOT_FOUND`、`VALIDATION_ERROR`、`EMPTY_FILE` 和不支持格式异步失败 | 已对齐 MVP |
| 阶段 2 搜索契约 | `search_mode` 与召回来源、语义分、关键词分、粗排分、候选计数已进入响应 | 已对齐阶段 2 首版 |
| 关键词召回 | PostgreSQL 全文检索已作为阶段 2 首版关键词召回实现 | 已对齐阶段 2 首版 |
| 业务干预 | 已支持内容去重、同文档版本返回上限和 MMR 简化打散 | 已对齐阶段 2 首版 |
| 重排降级 | 已支持 mock/external/disabled provider，external 不可用时降级返回 | 已对齐阶段 2 首版 |
| 权限标签过滤 | `permission_tags` 写入 document、text_chunk、Qdrant payload，检索按 `permission_context` 标签交集过滤 | 已对齐阶段 2 首版 |

## 未对齐项

| 需求/设计项 | 当前差异 | MVP 判断 |
| --- | --- | --- |
| Word/Excel/PPT/HTML/JSON/图片/音视频完整接入 | 当前仅完成 MVP 基础解析，复杂格式和 OCR/音视频未覆盖 | 延后到增强阶段 |
| 独立关键词引擎 | 未接入 ES/OpenSearch，当前先用 PostgreSQL 全文检索 | 阶段 2 可接受 |
| 混合召回增强 | 已有 RRF 首版，尚未做复杂权重调参和大规模评测 | 阶段 2 继续增强 |
| 真正粗排模型 | 当前是向量召回分数和候选截断，不是 DSSM/FM/DNN 双塔粗排模型 | MVP 可接受，需在文档中保持边界 |
| 业务干预增强 | 已有轻量去重和 MMR 首版，尚未实现 SimHash/MinHash/DPP 完整算法 | 阶段 2 继续增强 |
| 真实 Cross-Encoder 精排 | 已有兼容接口、降级机制，并已通过本地 BGE `BAAI/bge-reranker-base` 验证真实重排链路 | 生产前仍需压测与收益评估 |
| 完整权限模型 | 已有最小标签交集过滤，尚未接入真实用户、角色、组织、资源授权 | 阶段 2 可接受，生产前需增强 |
| 任务阶段耗时 | 当前有状态与错误原因，阶段级耗时/日志不足 | MVP 收口项 |
| 人工重试入口 | 已实现 `POST /api/v1/jobs/{job_id}/retry`，支持失败 job 创建 retry job 并写入审计 | 已在阶段 4 闭环 |
| 删除/更新/索引重建 | 已在阶段 3 实现文档删除、版本更新、向量删除和索引重建，阶段 4 已补 document 操作锁和批量重建首版 | 后续补生产级批量取消/重试和锁超时释放 |
| 线上 DashScope 验证 | 适配代码已完成，缺真实 `DASHSCOPE_API_KEY` 联调 | 待外部配置 |
| 可观测性 | 缺统一 trace_id、结构化日志、指标暴露 | 增强阶段 |

## 风险与影响

- 当前检索质量验证仍是最小样例集，只能证明 Demo 查询可命中，不能代表真实业务语料质量。
- 业务干预和精排已进入阶段 2 首版，但仍是轻量规则和 mock/external 兼容接口，不能代表真实十万级候选下的最终排序质量。
- 权限模型已具备最小标签过滤，但还不能替代真实鉴权系统和资源授权策略。
- 任务监控目前偏最小状态查询，定位复杂解析失败或模型异常时仍需要看容器日志。

## 建议后续动作

### P0：MVP 收口

已完成：

1. Demo 样例和查询集。
2. 检索质量最小验证。
3. API 契约文档。
4. 知识库过滤行为确认。
5. 异常场景验证。

### P1：真实模型和演示交付

1. 注入真实 `DASHSCOPE_API_KEY`，验证通义 `text-embedding-v4`。
2. 整理从零启动 MVP 的操作文档。
3. 形成一份演示脚本：启动服务、上传文档、查看 job、发起检索、解释结果字段。

### P2：下一阶段能力

1. 补阶段 2 trace 审查，确认 requirements/design/plan/API 契约与实现一致。
2. 接入真实重排 provider，或明确通义/本地 rerank 模型选型。
3. 补文档更新、删除、重建索引和版本可见性控制。
4. 增强权限过滤：用户、角色、组织、资源授权和审计日志。
5. 扩大评测集，补中文分词/关键词召回策略验证。

## 总结结论

当前实现已经达到“MVP 主链路可运行”的状态：文件上传、异步清洗、切分、Embedding、向量入库和语义检索均已跑通，并且本地 BGE 已真实验证。

但当前还不应标记为“完整 v1 完成”。剩余差距主要集中在 MVP 交付收口和增强能力两类：

- MVP 收口：已完成。
- 增强能力：关键词/混合召回、业务干预、精排、权限治理、索引重建和观测体系。

历史建议已闭环：阶段 2、阶段 3、阶段 4 和 Phase 5 对客 PoC 联调包均已推进。下一步建议进入 Phase 6，围绕生产鉴权、监控告警、锁超时释放、评测集扩展和容量压测做加固。
