# 数据清洗与 RAG 服务 Phase 7 生产就绪计划

## 1. 阶段目标

Phase 7 的目标是把 Phase 6 形成的“测试/准生产交付基线”，继续推进到“可进入客户真实生产准备”的状态。

本阶段重点不再是继续堆功能，而是补齐真实生产落地必须回答的几个问题：

- 谁可以访问系统，身份和权限从哪里来。
- 正式 rerank 服务是否稳定、收益是否明确、容量是否足够。
- 客户真实语料下检索质量、延迟、失败率是否达标。
- 备份不只是能导出，还能在隔离环境恢复并验证业务可用。
- 发布不只是有清单，还能被流水线稳定执行和回滚。
- 部署形态从本地 Compose 过渡到测试/生产平台。

完成后应达到：

- Header 兼容上下文升级为可接入网关/IAM/SSO 的认证授权契约。
- rerank 服务有正式 provider 配置、容量边界、降级策略和评测报告。
- 中文评测集可替换为客户真实语料评测包，并形成验收口径。
- PostgreSQL、MinIO、Qdrant 至少完成一次隔离恢复演练。
- CI/CD 或发布脚本可以串联构建、推送、迁移、冒烟、诊断和回滚检查。
- 有一版面向测试/生产环境的部署形态设计，例如 Compose overlay、Helm 或 Kubernetes 清单。

## 2. 当前基础

已完成：

- MVP 主链路和阶段 2/3/4 功能增强。
- Phase 5 对客 PoC 联调包。
- Phase 6 生产部署与运维加固首版：
  - 分环境配置模板。
  - 请求上下文 Header 注入。
  - trace_id 串联。
  - Prometheus 指标出口。
  - 滞留锁释放治理。
  - 批量失败项重试和取消。
  - 中文评测集和轻量压测。
  - 备份 dry-run 和发布检查清单。

当前主要边界：

- `X-Actor-Id`、`X-Tenant-Id`、`X-Permission-Tags` 仍是 Header 透传，不是可信认证结果。
- rerank 在 PoC 推荐配置中仍为 `mock`，真实 BGE rerank 已验证但未做生产容量基线。
- 当前中文评测集是项目样例，不代表客户真实知识库。
- 备份演练只验证导出和组件检查，未验证隔离恢复后的业务可用。
- 发布流程是清单和命令集合，尚未固化为流水线。
- 当前本地部署主形态仍是 Docker Compose。

## 3. 实施拆分

### P7-1：生产认证与授权接入方案

目标：把 Phase 6 的 Header 兼容上下文升级为生产可接入的认证授权边界。

实施内容：

- 定义 API 认证模式：
  - PoC：保留 Header 注入。
  - 测试/生产：由网关/IAM/SSO 签发可信身份。
- 明确 `tenant_id`、`actor_id`、`request_source`、`permission_tags` 的可信来源。
- 增加请求上下文校验策略：
  - 生产模式下禁止缺失 `tenant_id` / `actor_id`。
  - 禁止客户端直接伪造高权限标签。
  - 保留本地开发模式开关。
- 设计权限映射：
  - 用户/角色/组织 -> permission tags。
  - 知识库/文档 -> resource tags。
  - 检索时仍使用标签交集作为首版执行模型。
- 更新 API 契约、部署运维说明和问题排查手册。

建议产物：

- `docs/codex/v1/designs/data-cleaning-rag-phase7-auth-design.md`
- `docs/codex/v1/plans/data-cleaning-rag-phase7-p7-1-auth-plan.md`
- 更新 `.env.test.example`、`.env.prod.example`
- 更新 `services/api/app/core/request_context.py`

验收：

- 本地 PoC 不传认证网关时仍可运行。
- 测试/生产模式缺少必要身份字段时返回明确错误。
- 审计事件中的 actor/source 来自可信上下文。
- 检索权限过滤仍保持向后兼容。

执行状态：

- 2026-05-18：已完成 P7-1 首版实现。新增 local/gateway/iam 三种认证上下文模式及相关配置，API 在 gateway/iam 模式下可强制校验 `X-Tenant-Id` 和 `X-Actor-Id`；Compose、环境模板、API 契约、部署运维说明和问题排查手册已同步；已通过 request-context、permission、smoke、diagnostics、metrics 和 one-off gateway 模式验证。

### P7-2：正式 rerank 服务接入与容量基线

目标：从 `mock rerank` 过渡到可验证收益和容量边界的正式 rerank 服务。

实施内容：

- 明确 rerank provider 候选：
  - 本地 `BAAI/bge-reranker-base`。
  - 客户内网 rerank 服务。
  - 通义或其他兼容 rerank 服务。
- 固化 external rerank 的超时、批量大小、失败降级和最大候选数。
- 扩展 `model-eval.ps1`：
  - 输出 rerank 前后 TopK 变化。
  - 输出 rerank 调用耗时。
  - 输出降级次数和降级原因。
- 扩展 `search-load-test.ps1`：
  - 增加 rerank enabled 场景。
  - 输出 search + rerank 总延迟。
- 更新推荐配置：
  - PoC 配置。
  - 测试配置。
  - 生产待压测配置。

建议产物：

- `docs/codex/v1/trace/data-cleaning-rag-rerank-capacity-report.md`
- 更新 `scripts/model-eval.ps1`
- 更新 `scripts/search-load-test.ps1`
- 更新部署运维说明中的 rerank 容量建议。

验收：

- `RERANK_PROVIDER=external` 场景可稳定跑通。
- rerank 失败时检索不阻断，且指标和诊断能看到降级。
- 有一份明确的 rerank 开启/关闭质量和延迟对比。

执行状态：

- 2026-05-18：已完成 P7-2 首轮容量基线。`scripts/bge-rerank-test.ps1` 已验证本地 `BAAI/bge-reranker-base` external rerank 链路，`rerank_degraded=false`；`scripts/model-eval.ps1` 已支持 `-IncludeExternalRerank` 并输出 `local_bge + external rerank` 对比；`scripts/search-load-test.ps1` 已支持 rerank 开关和容量指标。容量报告见 `docs/codex/v1/trace/data-cleaning-rag-rerank-capacity-report.md`。当前结论是 PoC 默认继续使用 `local_bge + mock rerank`，客户测试/准生产再开启 external rerank 做真实语料验证。

### P7-3：客户真实语料评测包

目标：把样例评测升级为客户可验收的质量评测口径。

实施内容：

- 定义客户语料导入格式：
  - 文档目录。
  - 查询集 JSON。
  - 预期命中文档/关键词。
  - 权限标签。
- 扩展评测指标：
  - Recall@K。
  - MRR。
  - 命中文档率。
  - 权限误召回数。
  - 无答案/低置信度样例。
- 支持评测报告脱敏：
  - 不输出原文全文。
  - 只输出 doc_id、chunk_id、关键词摘要和指标。
- 形成验收阈值建议。

建议产物：

- `samples/queries/customer-eval-template.json`
- `docs/codex/v1/plans/数据清洗与RAG服务客户语料评测说明.md`
- `docs/codex/v1/trace/data-cleaning-rag-customer-eval-report.md`

验收：

- 客户只需替换文档目录和查询集即可跑评测。
- 报告能说明质量、延迟、误召回和权限过滤结果。
- 评测数据不误提交到仓库。

### P7-4：隔离恢复演练

目标：把备份 dry-run 升级为“恢复后业务可用”的演练。

实施内容：

- 新增隔离恢复脚本或手册：
  - 创建临时 PostgreSQL restore database。
  - 导入 `pg_dump`。
  - 检查关键表、迁移版本和样例数据。
- MinIO 恢复演练：
  - 明确 bucket 导出/导入方式。
  - 检查对象数量和关键对象路径。
- Qdrant 恢复演练：
  - PoC：通过批量重建恢复向量。
  - 生产：使用 snapshot 或存储快照。
- 恢复后执行 smoke/search 验证。

建议产物：

- `scripts/restore-dry-run.ps1`
- `docs/codex/v1/trace/data-cleaning-rag-restore-dry-run-report.md`
- 更新发布检查清单。

验收：

- PostgreSQL 备份可导入隔离库。
- 恢复环境可执行基础查询或主链路 smoke。
- 文档明确哪些步骤不能直接在生产原库执行。

### P7-5：CI/CD 发布流水线

目标：把发布检查清单固化为可重复执行的流水线。

实施内容：

- 设计流水线阶段：
  - 代码检查。
  - Python 编译。
  - Docker Compose 配置检查。
  - 镜像构建。
  - 镜像 tag。
  - Alembic 迁移检查。
  - smoke/diagnostics/metrics。
  - 备份 dry-run。
- 支持国内镜像源和客户内网 registry 参数化。
- 输出发布报告：
  - commit。
  - image tag。
  - migration version。
  - 验证结果。
- 设计回滚入口：
  - API/Worker image tag 回滚。
  - 模型配置回滚。
  - 迁移失败停机保留现场。

建议产物：

- `scripts/release-check.ps1`
- `.github/workflows/release-check.yml` 或客户 CI 模板
- `docs/codex/v1/plans/数据清洗与RAG服务CI-CD发布说明.md`

验收：

- 本地可一键执行 release check。
- GitHub Actions 或客户 CI 可复用同一套命令。
- 失败时能清楚定位失败阶段。

### P7-6：测试/生产部署形态设计

目标：从本地 Compose 过渡到客户测试/生产环境可落地的部署形态。

实施内容：

- 设计三种部署形态：
  - 本地 PoC：现有 Docker Compose。
  - 测试环境：Compose overlay 或客户容器平台。
  - 生产环境：Kubernetes/Helm 或客户标准 PaaS。
- 明确外部依赖：
  - PostgreSQL。
  - RabbitMQ。
  - MinIO/对象存储。
  - Qdrant。
  - Embedding。
  - rerank。
- 明确资源建议：
  - API CPU/内存。
  - Worker 并发和副本数。
  - rerank 服务 GPU/CPU 资源。
  - Qdrant 存储和备份策略。
- 明确配置注入、密钥管理和日志采集方式。

建议产物：

- `docs/codex/v1/designs/data-cleaning-rag-production-deployment-design.md`
- `infra/k8s/` 或 `infra/helm/` 初稿。
- 更新部署运维说明。

验收：

- 能向客户说明本地 PoC、测试、生产三套形态差异。
- 生产部署前置依赖、网络、资源、密钥、监控和备份边界清楚。

## 4. 推荐执行顺序

建议按下面顺序推进：

1. P7-1 生产认证与授权接入方案。
2. P7-2 正式 rerank 服务接入与容量基线。
3. P7-3 客户真实语料评测包。
4. P7-4 隔离恢复演练。
5. P7-5 CI/CD 发布流水线。
6. P7-6 测试/生产部署形态设计。

最建议下一步先做 P7-1。原因是认证和权限是生产边界的入口，它会影响审计、检索过滤、对客接口说明和部署配置；先把它定清楚，后面的 rerank、评测和发布都能继续沿用同一套可信上下文。

## 5. 验证策略

通用验证：

```powershell
docker compose -f infra/docker-compose.yml config --quiet
python -m compileall services\api\app services\worker\app
.\scripts\smoke-test.ps1
.\scripts\diagnostics-test.ps1
.\scripts\metrics-test.ps1
git diff --check
```

认证上下文验证：

```powershell
.\scripts\request-context-test.ps1
.\scripts\permission-test.ps1
```

rerank 和评测验证：

```powershell
.\scripts\model-eval.ps1 -DocumentsDir samples\documents\demo-zh -QueriesFile samples\queries\model-eval-queries-zh.json -SkipMock
.\scripts\search-load-test.ps1 -UploadCount 2 -SearchCount 8 -Concurrency 2
```

恢复与发布验证：

```powershell
.\scripts\backup-dry-run.ps1
.\scripts\restore-dry-run.ps1
.\scripts\release-check.ps1
```

## 6. 风险与回滚

- 认证模式切换必须保留本地开发和 PoC 兼容开关，避免阻断现有演示脚本。
- 权限上下文不能仅信任客户端自传 Header，生产必须由网关或 IAM 注入。
- rerank 开启可能显著增加 P95/P99 延迟，需要设置超时、批大小和降级策略。
- 客户真实语料可能包含敏感信息，评测输入和报告默认不应入库。
- 恢复演练必须在隔离环境执行，不能直接覆盖现有库或清空生产 bucket。
- CI/CD 里执行迁移要先备份和确认版本，迁移失败时应停止发布并保留现场。

## 7. 下一步

下一步执行 P7-1：

1. 输出生产认证与授权接入设计，明确 PoC Header、测试网关、生产 IAM/SSO 三种模式。
2. 拆分 P7-1 实施计划，明确要改的配置、API 上下文校验、错误码、审计字段和验证脚本。
3. 在不破坏现有 PoC 的前提下，新增生产模式身份字段校验和文档说明。
