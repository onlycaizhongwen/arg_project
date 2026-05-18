# 项目状态

- 当前版本：v1
- 当前阶段：Phase 7 P7-2 已完成，下一步 P7-3 客户真实语料评测包
- 当前主题：data-cleaning-rag-architecture
- 说明：此文件用于记录需求、设计、计划、实现与追踪的主线状态。

## 需求索引

| 主题 | 需求文档 | 设计文档 | 计划文档 | 依赖 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| data-cleaning-rag-architecture | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-architecture-plan.md | 对象存储、关系库、Redis、消息队列、向量库、Embedding/重排模型服务 | 已计划 |
| data-cleaning-rag-phase2 | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-phase2-plan.md | MVP 主链路、PostgreSQL、Qdrant、Embedding provider、可选重排服务 | 已计划 |
| data-cleaning-rag-phase3 | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-phase3-plan.md | 阶段 2 检索漏斗、文档/版本/chunk/vector 元数据 | 首版已完成 |
| data-cleaning-rag-phase4 | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-phase4-plan.md | 阶段 3 索引生命周期、审计事件、清洗任务状态、RabbitMQ/Qdrant/PostgreSQL 指标 | P4-5 已完成 |
| data-cleaning-rag-phase5 | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-phase5-poc-plan.md | MVP、阶段 2/3/4 能力、API 契约、模型评测、PoC 演示脚本 | 已完成 |
| data-cleaning-rag-phase6 | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-phase6-production-hardening-plan.md | Phase 5 对客联调包、部署运维说明、诊断概览、批量治理、模型评测 | P6-8 已完成 |
| data-cleaning-rag-phase7 | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-phase7-production-readiness-plan.md | Phase 6 生产部署与运维加固、客户测试/生产环境、IAM/SSO、正式 rerank、真实语料、CI/CD | 已规划 |
| data-cleaning-rag-phase7-auth | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-phase7-auth-design.md | docs/codex/v1/plans/data-cleaning-rag-phase7-p7-1-auth-plan.md | Phase 6 Header 上下文、审计、权限标签过滤、部署配置模板 | 首版已完成 |
| data-cleaning-rag-phase7-rerank-capacity | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-phase7-p7-2-rerank-capacity-plan.md | 本地 BGE reranker、external rerank、模型评估、轻量容量压测、降级观测 | 首版已完成 |
| data-cleaning-rag-demo-console | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-demo-console-plan.md | Vue 对客演示控制台、上传、任务轮询、检索、rerank 开关、诊断摘要 | MVP 已完成 |

## 进度与状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 需求分析 | 已完成 | 已基于架构图抽取目标、范围、场景、功能需求、非功能需求和待确认项。 |
| 技术设计 | 已完成 | 已完成总体架构、技术选型、模块设计、数据对象、接口草案、状态流转和风险说明。 |
| 执行计划 | Phase 7 P7-2 已完成 | 已拆分选型验证、MVP、混合检索、多源治理、索引生命周期、生产可控性、对客 PoC 联调包、生产部署运维加固和生产就绪计划；P7-1 生产认证与授权、P7-2 正式 rerank 容量基线已完成首版。 |
| 实现 | Phase 7 P7-2 已完成 | 已完成 MVP 主链路、阶段 2 检索漏斗、阶段 3 索引生命周期、阶段 4 生产可控性增强、Phase 5 对客 PoC 联调材料、Phase 6 生产部署与运维加固首版、P7-1 认证上下文模式，以及 P7-2 external rerank 评估与压测脚本增强。 |
| 追踪审查 | Phase 7 P7-2 已完成报告 | 已补充 MVP 主链路、阶段 2、阶段 3、Phase 6、P7-1 一致性 trace 和 P7-2 rerank 容量报告；Phase 5 已对 API 契约、脚本清单和过期描述做对客材料一致性检查。 |

## 变更记录

- 2026-05-18：新增 `docs/codex/v1/plans/data-cleaning-rag-phase7-production-readiness-plan.md`，规划 Phase 7 生产就绪工作，拆分为 P7-1 生产认证与授权、P7-2 正式 rerank 服务接入与容量基线、P7-3 客户真实语料评测包、P7-4 隔离恢复演练、P7-5 CI/CD 发布流水线、P7-6 测试/生产部署形态设计；建议下一步优先执行 P7-1。
- 2026-05-18：新增 `docs/codex/v1/designs/data-cleaning-rag-phase7-auth-design.md` 和 `docs/codex/v1/plans/data-cleaning-rag-phase7-p7-1-auth-plan.md`，明确 local/gateway/iam 三种认证模式、可信 Header 字段契约、权限标签兜底策略、错误码和 P7-1 实施步骤；下一步进入 P7-1 代码实现。
- 2026-05-18：完成 Phase 7 P7-1 生产认证与授权接入首版：新增 `AUTH_CONTEXT_MODE=local|gateway|iam`、`AUTH_REQUIRE_ACTOR`、`AUTH_REQUIRE_TENANT`、`AUTH_DEFAULT_PERMISSION_TAGS`、`AUTH_EMPTY_PERMISSION_POLICY` 等配置；gateway/iam 模式可强制校验可信 Header，local 模式保持 PoC 兼容；Compose、环境模板、API 契约、部署运维说明和问题排查手册已同步；新增 `docs/codex/v1/trace/data-cleaning-rag-phase7-auth-trace.md`，回归验证通过。下一步进入 P7-2 正式 rerank 服务接入与容量基线。
- 2026-05-18：完成 Phase 7 P7-2 正式 rerank 服务接入与容量基线首版：扩展 `scripts/model-eval.ps1` 支持 `-IncludeExternalRerank`，扩展 `scripts/search-load-test.ps1` 支持 rerank 开关、provider、降级次数和分数覆盖统计；本地 `BAAI/bge-reranker-base` reranker 通过 `scripts/bge-rerank-test.ps1` 验证，external rerank 压测 0 失败、0 降级；新增 `docs/codex/v1/trace/data-cleaning-rag-rerank-capacity-report.md`。下一步进入 P7-3 客户真实语料评测包。
- 2026-05-18：完成对客演示控制台 MVP：新增 `services/console` Vue 3 + Vite + TypeScript 前端，覆盖演示上下文、链路状态、文件上传、job 轮询、RAG 检索、rerank provider 切换、rerank 开关、命中片段和诊断摘要；新增 `services/api/app/api/runtime_config.py` 支持演示环境运行时切换 `disabled/mock/external`；新增 `docs/codex/v1/plans/data-cleaning-rag-demo-console-plan.md`、`services/console/README.md` 和 `scripts/rerank-runtime-config-test.ps1`；前端构建、Vite 页面访问、API 代理和 rerank 切换验证通过。
- 2026-05-18：完成 Phase 6 生产部署与运维加固一致性 trace 审查，新增 `docs/codex/v1/trace/data-cleaning-rag-phase6-trace.md`；结论为 P6-1 到 P6-8 首版闭环已完成，剩余风险集中在真实 IAM/SSO、生产级恢复演练、正式 rerank 容量、监控平台接入和 CI/CD 发布自动化。
- 2026-05-18：完成 Phase 6 P6-8 备份恢复与发布流程首版：新增 `scripts/backup-dry-run.ps1`，可非破坏式导出 PostgreSQL 备份、检查 MinIO bucket 摘要和 Qdrant collections，并生成 `docs/codex/v1/trace/data-cleaning-rag-backup-dry-run-report.md`；新增 `docs/codex/v1/plans/数据清洗与RAG服务发布检查清单.md`，覆盖发布前冻结项、镜像 tag、发布前命令、备份恢复、Alembic 迁移原则、发布步骤、回滚原则和生产审批边界；更新部署运维说明和 Phase 6 计划状态；`backups/` 已加入 `.gitignore`，避免本地 SQL 备份误提交。下一步进入 Phase 6 收尾 trace 审查。
- 2026-05-18：完成 Phase 6 P6-7 评测集扩展与容量压测首版：新增中文业务样例文档和分类查询集，扩展 `scripts/model-eval.ps1` 输出 MRR、Recall@K、P50/P95/P99、分类汇总和 rerank 分数覆盖；新增 `scripts/search-load-test.ps1` 输出上传吞吐、搜索 QPS 和搜索延迟 P50/P95/P99；已生成 `data-cleaning-rag-model-eval-zh-report` 和 `data-cleaning-rag-load-test-report`，并完成 smoke、diagnostics 和 git diff 检查。下一步进入 P6-8 备份恢复与发布流程。
- 2026-05-18：完成 Phase 6 P6-6 批量治理增强首版：新增 `POST /api/v1/document-batches/{batch_id}/retry-failed` 和 `POST /api/v1/document-batches/{batch_id}/cancel`；失败 item 可在原批次内重新提交，已成功 item 不重复执行；取消仅处理 `PENDING` item；批量 item 明细支持 `status` 过滤和 `total_count`；新增 `scripts/document-batch-retry-test.ps1`，更新 API 契约、部署运维说明和问题排查手册；已通过 compileall、Compose config、API 镜像重建、document-batch-retry、document-batch-rebuild、smoke、diagnostics 和 git diff 检查。下一步进入 P6-7 评测集扩展与容量压测。
- 2026-05-18：完成 Phase 6 P6-5 锁超时释放与治理闭环首版：新增 `POST /api/v1/documents/{document_id}/locks/release`，仅释放超过阈值且关联 job 不处于 `PENDING`、`RUNNING`、`RETRYING` 的滞留锁；释放成功写入 `DOCUMENT_OPERATION_LOCK_RELEASED` 审计事件；新增 `scripts/document-lock-release-test.ps1`，更新 API 契约和部署运维说明；已通过 compileall、Compose config、API 镜像重建、document-lock-release、document-operation-lock、diagnostics、smoke 和 git diff 检查。下一步进入 P6-6 批量治理增强。
- 2026-05-18：完成 Phase 6 P6-4 监控指标出口首版：新增 `GET /api/v1/metrics`，以 Prometheus text format 输出 cleaning job 状态/失败率、RabbitMQ 队列、document 操作锁、rerank 降级、API 请求和 5xx 错误计数；新增 `scripts/metrics-test.ps1`，更新 API 契约和部署运维说明中的监控采集与告警建议；已通过 compileall、Compose config、API 镜像重建、metrics-test、diagnostics-test 和 git diff 检查。下一步进入 P6-5 锁超时释放与治理闭环。
- 2026-05-18：完成 Phase 6 P6-3 结构化日志与 trace_id 串联首版：API middleware 读取或生成 `trace_id`，响应头回传 `X-Trace-Id`，错误响应包含 `trace_id`；上传、更新、重建、retry、批量重建的 MQ 消息携带 `trace_id`；Worker 输出包含 `trace_id`、`job_id`、`document_id`、`document_version_id`、`operation` 的 JSON 日志；已通过 request-context 验证并在 API/Worker 日志中确认同一 trace_id 可串联。下一步进入 P6-4 监控指标出口。
- 2026-05-18：完成 Phase 6 P6-2 请求上下文 Header 注入首版：新增 `services/api/app/core/request_context.py`，上传、文档治理、job retry、批量重建和检索入口支持 `X-Tenant-Id`、`X-Actor-Id`、`X-Request-Source`、`X-Permission-Tags`、`X-Trace-Id`；新增 `scripts/request-context-test.ps1`，并更新 API 契约；下一步进入 P6-3 结构化日志与 trace_id 串联。
- 2026-05-18：完成 Phase 6 P6-1 环境配置分层首版：新增 `.env.local.example`、`.env.test.example`、`.env.prod.example`，更新 `.gitignore` 白名单以允许三份模板入库；更新 `数据清洗与RAG服务部署运维说明.md`，补充分环境模板选择、敏感信息管理、镜像源覆盖、测试/生产配置原则；下一步进入 P6-2 认证上下文与操作人注入。
- 2026-05-18：新增 `docs/codex/v1/plans/data-cleaning-rag-phase6-p6-1-env-plan.md`，将 Phase 6 下一步 P6-1 环境配置分层拆成可执行计划，明确 `.env.local.example`、`.env.test.example`、`.env.prod.example` 的目标配置、文档更新范围、验证命令、影响范围和完成标准；下一步可直接进入 P6-1 实现。
- 2026-05-18：新增 `docs/codex/v1/plans/data-cleaning-rag-phase6-production-hardening-plan.md`，规划 Phase 6 生产部署与运维加固，拆分为 P6-1 环境配置分层、P6-2 认证上下文、P6-3 结构化日志与 trace_id、P6-4 监控指标出口、P6-5 锁超时释放、P6-6 批量治理增强、P6-7 评测集扩展与容量压测、P6-8 备份恢复与发布流程；建议下一步优先执行 P6-1。
- 2026-05-18：完成 Phase 5 P5-3/P5-4/P5-5：新增 `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md` 和 `docs/codex/v1/plans/数据清洗与RAG服务问题排查手册.md`，覆盖组件职责、环境变量、国内镜像源、启动停止、迁移、健康检查、日志、备份清理、API/Docker/PostgreSQL/RabbitMQ/Worker/MinIO/Qdrant/Embedding/BGE/DashScope/rerank/锁滞留等排查路径；同步修正 API 契约中过期的“未实现人工重试接口”描述，并对实际路由和脚本清单完成一致性检查。
- 2026-05-18：完成 Phase 5 P5-1/P5-2 首版并验证：新增 `docs/codex/v1/plans/数据清洗与RAG服务PoC联调说明.md` 和 `scripts/poc-demo.ps1`，覆盖 PoC 环境准备、模型配置、启动迁移、手工联调用例、验收记录，以及自动化演示链路；`scripts/poc-demo.ps1` 已在 `local_bge/bge-m3 + mock rerank` 下跑通，批量重建 2/2 成功，诊断状态 `ok`。
- 2026-05-18：新增 `docs/codex/v1/plans/data-cleaning-rag-phase5-poc-plan.md`，规划 Phase 5 对客 PoC 联调包，明确 PoC 联调说明、部署运维说明、演示脚本、问题排查手册和一致性检查五项交付物；下一步建议先执行 P5-1 联调说明和 P5-2 演示脚本。
- 2026-05-18：完成 P4-6 生产模型评测首版：新增 `scripts/model-eval.ps1`、`samples/queries/model-eval-queries.json`，生成 `docs/codex/v1/trace/data-cleaning-rag-model-eval-report.json` 和 `.md`；本轮评测覆盖 `mock`、`local_bge/bge-m3` 和 DashScope `text-embedding-v4`，结果分别为 8/10、10/10、10/10，当前样例下 `local_bge` P95 延迟低于 DashScope。
- 2026-05-18：完成 P4-3 批量治理任务首版并验证：新增 `POST /api/v1/document-batches/rebuild`、`GET /api/v1/document-batches/{batch_id}`、`GET /api/v1/document-batches/{batch_id}/items`，新增 `0011_doc_batch` 迁移和 `scripts/document-batch-rebuild-test.ps1`；已完成编译、Compose 配置解析、API 镜像重建、迁移、批量重建端到端、smoke、diagnostics、document-operation-lock 回归，phase2 在 `local_bge + mock rerank` 下 15/15 通过。
- 2026-05-18：新增 `docs/codex/v1/plans/data-cleaning-rag-post-mvp-next-plan.md`，将 MVP 完成后的路线串联为 P4-3 批量治理任务、P4-6 生产模型评测、Phase 5 对客 PoC 联调包和 Phase 6 生产部署与运维加固；建议下一步优先实现 P4-3 批量重建任务。
- 2026-05-14：创建 `data-cleaning-rag-architecture` 主题，完成需求分析、技术选型/设计和实施计划文档。
- 2026-05-14：补充 `docs/codex/v1/plans/data-cleaning-rag-next-step.md`，明确下一步进入选型验证与 MVP 骨架准备。
- 2026-05-14：补充 RAG 检索漏斗方案，将“召回 -> 粗排 -> 业务干预 -> 精排”纳入需求、设计和计划。
- 2026-05-14：新增 `docs/codex/v1/plans/data-cleaning-rag-mvp.html`，用于可视化展示 MVP 版本范围、阶段和验收路径。
- 2026-05-14：修正 MVP 边界，明确 MVP 只做语义召回、基础粗排/候选截断，不接 Cross-Encoder 精排和完整业务干预。
- 2026-05-14：新增 `docs/codex/v1/plans/data-cleaning-rag-mvp-implementation-blueprint.md`，将 MVP 进一步拆成工程模块、数据模型、API 契约和 M1-M7 实施任务。
- 2026-05-14：根据技术栈决策，将默认方案从 Spring Boot 控制面调整为统一 Python：FastAPI 控制面 + Python Worker。
- 2026-05-14：在 MVP HTML 和工程实施蓝图中补充最小 MVP 时序图，覆盖上传异步入库和语义检索链路。
- 2026-05-14：优化 MVP HTML 时序图展示，将长线时序图调整为三段式紧凑流程图：上传请求、后台入库、在线检索。
- 2026-05-14：根据评审意见，将 MVP HTML 时序图改为 Mermaid sequenceDiagram，减少自定义 CSS 图形带来的排版问题。
- 2026-05-14：新增总体架构图资产 `docs/codex/v1/assets/data-cleaning-rag-overall-architecture.html`，并在设计文档中登记。
- 2026-05-14：确认原始总体架构图已放入 `docs/codex/v1/assets/总体架构图.png`，设计文档已改为优先引用 PNG 原图。
- 2026-05-15：新增 `docs/codex/v1/plans/data-cleaning-rag-mvp-startup-plan.md`，明确工程目录、依赖服务、首批接口、Worker 能力和 D1-D7 开发顺序。
- 2026-05-15：确认 MVP Embedding 模型使用通义/阿里云百炼，默认 `text-embedding-v4`，通过 `DASHSCOPE_API_KEY` 配置。
- 2026-05-15：调整 Embedding 策略为兼容模型适配层：线上通义 text-embedding，本地 BGE，mock 作为开发兜底。
- 2026-05-15：新增 `docs/codex/v1/plans/data-cleaning-rag-engineering-init-plan.md`，将工程初始化拆到文件级任务、依赖、环境变量和提交节奏。
- 2026-05-15：按工程初始化计划创建 `services/api`、`services/worker`、`infra`、`samples` 骨架，补齐 `.env.example`、Docker Compose 和 PostgreSQL 初始化脚本，并完成 Python 编译与 Compose 配置解析验证。
- 2026-05-15：实现 API 文件上传最小链路：MinIO 保存对象、PostgreSQL 创建 document/version/job、RabbitMQ 投递清洗任务；实现 Worker 消费、下载、解析、清洗、切块、Embedding、Qdrant 入库和 job 状态更新的首版代码。
- 2026-05-16：补齐 API 语义检索接口，使用兼容 Embedding 适配层生成 query 向量，从 Qdrant 召回并回查 PostgreSQL `text_chunk`；Docker Desktop 已可用，但 Docker Hub 拉取 `python:3.12-slim` 超时，暂以 `.venv` 完成本地依赖安装、导入验证、health 与解析/切块/embedding 最小行为验证。
- 2026-05-16：将 Docker 镜像默认切换为 `docker.m.daocloud.io` 国内镜像源，成功构建 API/Worker 镜像并启动完整 Compose；上传 `samples/documents/smoke.txt` 后 job 达到 `SUCCEEDED`，检索接口返回 3 条 chunk，端到端冒烟通过。
- 2026-05-16：新增 `scripts/smoke-test.ps1` 自动化冒烟脚本，并增强 Worker 幂等处理：已成功 job 重复消息会跳过，chunk/vector 写入采用稳定 ID 与 upsert 方式避免重复处理冲突。
- 2026-05-16：补充 API 统一错误响应、API/Worker 启动配置校验和 Worker 失败重试计数；本地运行库已补 `cleaning_job.retry_count` 字段，自动冒烟与 `JOB_NOT_FOUND` 错误结构验证通过。
- 2026-05-16：引入 Alembic 正式迁移机制，新增 `0001_initial` 与 `0002_retry_count` 迁移、`scripts/db-migrate.ps1`，API 镜像已内置迁移能力；现有开发库已升级到 `0002_retry_count`，自动冒烟通过。
- 2026-05-16：增强 Embedding provider 切换能力，Compose 已支持通过环境变量切换 `mock`、`dashscope`、`local_bge`；DashScope 调用补充 `output_type=dense` 与 query/document `text_type`；新增 `scripts/embedding-check.ps1` 并在 mock provider 下验证通过。
- 2026-05-16：完成本地 BGE 验证：通过 Ollama 拉取 `bge-m3`，确认 `/v1/embeddings` 返回 1024 维向量；Compose 使用 `EMBEDDING_PROVIDER=local_bge`、`EMBEDDING_BASE_URL=http://host.docker.internal:11434` 后，API/Worker embedding-check 与端到端 smoke-test 均通过。
- 2026-05-16：新增 `docs/codex/v1/trace/data-cleaning-rag-architecture-trace.md`，完成 MVP 主链路闭环审查；当前实现已跑通主链路，但仍需补 Demo 样例、接口文档、检索质量验证、异常场景验证和知识库过滤行为确认。
- 2026-05-16：补齐 `knowledge_base_id` MVP 过滤链路：上传接口、document/text_chunk 字段、Qdrant payload 与检索 `knowledge_base_ids` 过滤已贯通；新增 `0003_knowledge_base` 迁移，smoke 已验证错误知识库不返回结果。
- 2026-05-16：新增 3 份 Demo 文档、5 条 Demo 查询和 `scripts/demo-eval.ps1`；本地 BGE 下 Demo 评测通过，5 条查询全部命中预期关键词。
- 2026-05-16：新增 `docs/codex/v1/plans/data-cleaning-rag-api-contract.md`，整理 MVP API 契约、统一错误响应、curl/PowerShell 示例和当前能力边界。
- 2026-05-16：新增 `scripts/failure-test.ps1` 并补充空文件上传校验 `EMPTY_FILE`；异常场景验证、smoke test 和 demo eval 均通过，MVP P0 收口完成。
- 2026-05-16：进入阶段 2，新增 `docs/codex/v1/plans/data-cleaning-rag-phase2-plan.md`，明确混合检索、业务干预、重排降级、权限治理和评测升级的实施顺序。
- 2026-05-16：完成阶段 2 P2-1/P2-2 首版：搜索接口新增 `search_mode=semantic|keyword|hybrid`，PostgreSQL 全文关键词召回和 RRF 混合合并已实现；新增 `0004_chunk_fts` 迁移和 `scripts/phase2-eval.ps1`，phase2/smoke/demo/failure 验证均通过。
- 2026-05-16：完成阶段 2 P2-3/P2-4 首版：检索链路在 `pre_rank_size` 后加入业务干预，支持内容去重、同文档版本返回上限和 MMR 简化打散；phase2/smoke/demo/failure 验证均通过。
- 2026-05-16：完成阶段 2 P2-5 首版：新增重排兼容接口、mock/external/disabled provider 和失败降级验证；不可用外部重排服务不会阻断检索。
- 2026-05-16：完成阶段 2 P2-6：新增 `permission_tags` / `permission_context` 最小权限治理链路，上传、Worker、PostgreSQL、Qdrant payload 和检索过滤已贯通；新增 `0005_permission_tags` 和 `scripts/permission-test.ps1`，权限验证、phase2、smoke、demo、failure、rerank degrade 均通过。
- 2026-05-16：新增 `docs/codex/v1/trace/data-cleaning-rag-phase2-trace.md`，完成阶段 2 一致性审查；结论为阶段 2 首版功能闭环完成，剩余风险集中在真实重排、中文关键词、完整权限和索引生命周期。
- 2026-05-16：进入阶段 3，新增 `docs/codex/v1/plans/data-cleaning-rag-phase3-plan.md`；完成 P3-1 文档删除与不可见过滤首版，新增 `DELETE /api/v1/documents/{document_id}`、`0006_deleted_at` 迁移和 `scripts/document-delete-test.ps1`，阶段 2/MVP/删除/权限/异常/重排降级回归均通过。
- 2026-05-16：完成阶段 3 P3-2 文档更新与新版本可见性首版，新增 `PUT /api/v1/documents/{document_id}/versions` 和 `scripts/document-update-test.ps1`；新版本成功后旧版本标记 `SUPERSEDED`，检索只返回 `INDEXED` 版本，阶段 2/MVP/更新/删除/权限/异常/重排降级回归均通过。
- 2026-05-16：补充真实 BGE 重排验证：新增可选 `services/reranker` 服务与 `scripts/bge-rerank-test.ps1`，使用本地 Ollama `bge-m3` 作为 embedding、`BAAI/bge-reranker-base` 作为 external reranker；验证返回 `rerank_provider=external`、`rerank_degraded=false` 且 5 条结果包含 `rerank_score`。本次模型预热发现 `hf-mirror.com` 在当前 Hugging Face 客户端下会出现 metadata 错误，已在 `infra/README.md` 记录可切回 `huggingface.co` 预热缓存。
- 2026-05-16：完成阶段 3 P3-3 索引重建首版：新增 `POST /api/v1/documents/{document_id}/rebuild` 和 `scripts/document-rebuild-test.ps1`；重建复用当前 `INDEXED` 版本的原始对象，不创建新版本，Worker 重新解析/切块/Embedding/upsert 向量并清理 stale chunk/vector；重建、更新、删除、阶段 2 和 smoke 回归均通过。
- 2026-05-16：完成阶段 3 P3-4 最小审计首版：新增 `document_audit_event` 表和 `0007_audit_event` 迁移；更新、重建、删除接口支持 `actor_id` 与 `request_source` 并写入审计；新增 `GET /api/v1/documents/{document_id}/audit` 和 `scripts/document-audit-test.ps1`，验证版本创建、重建请求和删除三类审计事件可查。
- 2026-05-16：新增 `docs/codex/v1/trace/data-cleaning-rag-phase3-trace.md`，完成阶段 3 一致性审查；结论为阶段 3 首版功能闭环完成，剩余风险集中在 document 级并发控制、批量治理、失败补偿、完整审计和操作者可信来源。
- 2026-05-16：进入阶段 4，新增 `docs/codex/v1/plans/data-cleaning-rag-phase4-plan.md`；将下一阶段定义为“生产可控性”，覆盖 document 级并发控制、失败补偿、批量治理、完整审计、异常迹象/监控指标和生产模型评测，并建议优先实现 P4-1 文档级并发控制。
- 2026-05-16：完成阶段 4 P4-1 文档级并发控制首版：新增 `0008_operation_lock` 迁移，为 `document` 增加 `operation_status`、`operation_lock_id`、`operation_started_at`；文档更新/重建使用 job_id 持锁，Worker 成功或最终失败后释放锁；删除操作同步持锁并清理锁字段；新增 `DOCUMENT_OPERATION_IN_PROGRESS` 错误码、`DOCUMENT_OPERATION_LOCKED`/`DOCUMENT_OPERATION_REJECTED` 审计事件和 `scripts/document-operation-lock-test.ps1`，验证更新持锁期间重建被拒绝、拒绝事件可审计、更新完成后重建恢复可用。
- 2026-05-16：完成阶段 4 P4-2 失败补偿与人工重试首版：新增 `0009_retry_link` 迁移，为 `cleaning_job` 增加 `retry_of_job_id`；新增 `POST /api/v1/jobs/{job_id}/retry`，仅允许 `FAILED` job 创建新的 retry job，复用原 `document_version` 和对象存储文件，写入 `JOB_RETRY_REQUESTED` 审计事件；新增 `scripts/job-retry-test.ps1`，验证失败 job 可重试、retry job 可追溯、审计事件存在、非失败 job 重试返回 `JOB_NOT_FAILED`。
- 2026-05-16：完成阶段 4 P4-4 完整审计增强：上传、更新、重建、重试消息补充 operation 语义；Worker 成功时写入 `DOCUMENT_VERSION_INDEXED`、`DOCUMENT_INDEX_REBUILD_SUCCEEDED` 或 `JOB_RETRY_SUCCEEDED`，最终失败时写入 `DOCUMENT_VERSION_INDEX_FAILED`、`DOCUMENT_INDEX_REBUILD_FAILED` 或 `JOB_RETRY_FAILED`；删除完成后补 `DOCUMENT_DELETE_SUCCEEDED`；`GET /api/v1/documents/{document_id}/audit` 支持按 `operation` 过滤；`scripts/document-audit-test.ps1`、`scripts/job-retry-test.ps1`、`scripts/document-operation-lock-test.ps1`、`scripts/phase2-eval.ps1` 和 `scripts/smoke-test.ps1` 均已通过。
- 2026-05-16：完成阶段 4 P4-5 异常迹象与诊断概览首版：新增 `search_diagnostic_event` 表和 `0010_search_diag` 迁移，rerank 降级时写入 `RERANK_DEGRADED` 事件；新增 `GET /api/v1/diagnostics/overview`，输出 job 状态/失败率、RabbitMQ ready/consumer、document 操作锁滞留、rerank 降级统计和统一 signals；新增 `scripts/diagnostics-test.ps1`，并修正 `scripts/phase2-eval.ps1` 默认复用固定知识库导致的数据污染问题；诊断、重排降级、smoke 和 phase2 评测均已通过。
