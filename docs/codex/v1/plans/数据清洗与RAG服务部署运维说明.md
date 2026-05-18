# 数据清洗与 RAG 服务部署运维说明

## 1. 适用范围

本文面向本地 PoC、测试环境和对客联调环境，说明数据清洗与 RAG 服务的部署、启动、迁移、健康检查、日志查看、备份和清理方式。

当前推荐演示配置：

- Embedding：本地 BGE，`EMBEDDING_PROVIDER=local_bge`，`EMBEDDING_MODEL=bge-m3`
- Rerank：默认 `mock` 或 `disabled`；需要验证真实重排时启用本地 `reranker` profile
- API 地址：`http://localhost:8000`
- Compose 文件：`infra/docker-compose.yml`

## 2. 组件职责

| 组件 | 容器名 | 端口 | 职责 |
| --- | --- | --- | --- |
| FastAPI API | `rag-cleaning-api` | `8000` | 文件上传、任务查询、文档治理、RAG 检索、诊断概览 |
| Python Worker | `rag-cleaning-worker` | 无 | 消费 RabbitMQ 清洗任务，解析文件、清洗切块、生成向量、写入 Qdrant |
| PostgreSQL | `rag-cleaning-postgres` | `5432` | 保存 document、version、job、chunk、审计、批量任务等结构化数据 |
| RabbitMQ | `rag-cleaning-rabbitmq` | `5672` / `15672` | 清洗任务异步队列和管理控制台 |
| MinIO | `rag-cleaning-minio` | `9000` / `9001` | 保存上传原始文件 |
| Qdrant | `rag-cleaning-qdrant` | `6333` | 保存 chunk 向量和检索 payload |
| BGE Reranker | `rag-bge-reranker` | `8010` | 可选，本地 `BAAI/bge-reranker-base` 重排服务 |

## 3. 环境变量

核心环境变量以 `.env.example` 和分环境模板为准。PoC 演示建议优先使用 `.env.local.example`：

```powershell
Copy-Item .env.local.example .env
```

### 3.1 环境模板选择

| 模板 | 适用场景 | 主要特点 |
| --- | --- | --- |
| `.env.example` | 通用最小示例 | 保留 mock embedding 和 disabled rerank，适合作为字段全集参考 |
| `.env.local.example` | 本地开发、本地 PoC、对客演示 | 默认使用 `local_bge/bge-m3 + mock rerank`，镜像源使用 `docker.m.daocloud.io` |
| `.env.test.example` | 客户测试环境、联调环境 | 使用占位符描述客户内网 registry、中间件地址、DashScope 或内网 BGE 配置 |
| `.env.prod.example` | 生产部署配置清单 | 不放真实密码和 Key，只保留密钥管理占位符，并预留鉴权、日志、监控变量 |

当前 `infra/docker-compose.yml` 是本地一体化 Compose 栈，API/Worker 在容器内通过 `postgres`、`rabbitmq`、`minio`、`qdrant` 等服务名访问本地容器。`.env.test.example` 和 `.env.prod.example` 更适合作为测试/生产部署平台、Compose overlay 或 Helm/Kubernetes 配置的基线清单，不建议直接复制后期望当前本地 Compose 自动连接外部中间件。

真实 `.env` 文件包含敏感信息，已被 `.gitignore` 忽略，不应提交到仓库。生产环境的 `DASHSCOPE_API_KEY`、数据库密码、MinIO 密钥等应通过密钥管理、CI/CD 受保护变量或部署平台注入。

### 3.2 基础镜像

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PYTHON_BASE_IMAGE` | `docker.m.daocloud.io/library/python:3.12-slim` | API/Worker/Reranker 基础镜像 |
| `POSTGRES_IMAGE` | `docker.m.daocloud.io/library/postgres:16-alpine` | PostgreSQL 镜像 |
| `RABBITMQ_IMAGE` | `docker.m.daocloud.io/library/rabbitmq:3.13-management-alpine` | RabbitMQ 镜像 |
| `MINIO_IMAGE` | `docker.m.daocloud.io/minio/minio:RELEASE.2025-04-22T22-12-26Z` | MinIO 镜像 |
| `QDRANT_IMAGE` | `docker.m.daocloud.io/qdrant/qdrant:v1.18.0` | Qdrant 镜像 |

如果国外镜像拉取失败，优先使用当前默认的 `docker.m.daocloud.io`。如客户侧已有私有镜像仓库，可把以上变量统一改为内网镜像地址：

```powershell
$env:PYTHON_BASE_IMAGE = "<internal-registry>/library/python:3.12-slim"
$env:POSTGRES_IMAGE = "<internal-registry>/library/postgres:16-alpine"
$env:RABBITMQ_IMAGE = "<internal-registry>/library/rabbitmq:3.13-management-alpine"
$env:MINIO_IMAGE = "<internal-registry>/minio/minio:RELEASE.2025-04-22T22-12-26Z"
$env:QDRANT_IMAGE = "<internal-registry>/qdrant/qdrant:v1.18.0"
```

### 3.3 模型配置

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `EMBEDDING_PROVIDER` | `mock` / `local_bge` / `dashscope` | Embedding 提供方 |
| `EMBEDDING_MODEL` | `bge-m3` / `text-embedding-v4` | 模型名称 |
| `EMBEDDING_DIMENSION` | `1024` | 向量维度，必须与 Qdrant collection 一致 |
| `EMBEDDING_BASE_URL` | `http://host.docker.internal:11434` | 本地 BGE OpenAI-compatible 地址 |
| `DASHSCOPE_API_KEY` | `<your-key>` | 通义 DashScope Key |
| `RERANK_PROVIDER` | `disabled` / `mock` / `external` | 重排提供方 |
| `RERANK_BASE_URL` | `http://reranker:8010/rerank` | 外部重排服务地址 |
| `RERANK_TIMEOUT_SECONDS` | `30` | 重排超时时间 |

本地 BGE 需要宿主机先准备模型：

```powershell
ollama pull bge-m3
curl.exe -s http://localhost:11434/api/tags
```

容器内访问宿主机 Ollama 时使用：

```powershell
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"
```

测试环境如果使用 DashScope：

```powershell
$env:EMBEDDING_PROVIDER = "dashscope"
$env:EMBEDDING_MODEL = "text-embedding-v4"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_OUTPUT_TYPE = "dense"
$env:DASHSCOPE_API_KEY = "<your-key-from-secret-manager>"
```

生产环境应固定一种 embedding 配置并保持 `EMBEDDING_DIMENSION` 稳定。切换维度不同的模型前，需要规划 Qdrant collection 重建或全量重建索引。

## 4. 启动与停止

### 4.1 首次启动

```powershell
Copy-Item .env.local.example .env
docker compose -f infra/docker-compose.yml build api worker
docker compose -f infra/docker-compose.yml up -d
.\scripts\db-migrate.ps1
docker compose -f infra/docker-compose.yml ps
```

### 4.2 使用本地 BGE 启动

```powershell
$env:EMBEDDING_PROVIDER = "local_bge"
$env:EMBEDDING_MODEL = "bge-m3"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"
$env:RERANK_PROVIDER = "mock"

docker compose -f infra/docker-compose.yml up -d api worker
.\scripts\embedding-check.ps1
```

### 4.3 启用本地 BGE Reranker

```powershell
$env:COMPOSE_PROFILES = "reranker"
$env:HF_ENDPOINT = "https://hf-mirror.com"
$env:EMBEDDING_PROVIDER = "local_bge"
$env:EMBEDDING_MODEL = "bge-m3"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"
$env:RERANK_PROVIDER = "external"
$env:RERANK_MODEL = "BAAI/bge-reranker-base"
$env:RERANK_BASE_URL = "http://reranker:8010/rerank"
$env:RERANK_TIMEOUT_SECONDS = "30"

docker compose -f infra/docker-compose.yml build reranker
docker compose -f infra/docker-compose.yml up -d reranker api worker
.\scripts\bge-rerank-test.ps1
```

### 4.4 停止服务

```powershell
docker compose -f infra/docker-compose.yml down
```

停止并删除本地开发数据卷：

```powershell
docker compose -f infra/docker-compose.yml down -v
```

注意：`down -v` 会删除 PostgreSQL、RabbitMQ、MinIO、Qdrant 和 Hugging Face 模型缓存卷，只适合本地重置环境。

### 4.5 测试/生产配置原则

测试环境建议从模板开始：

```powershell
Copy-Item .env.test.example .env
```

然后按客户环境替换镜像仓库、中间件地址和模型服务地址。生产环境不要直接提交或共享 `.env`，而是把 `.env.prod.example` 作为配置清单，由部署平台注入真实敏感信息。

生产环境至少需要确认：

- 数据库、RabbitMQ、对象存储、Qdrant 是否使用托管服务或独立集群。
- Embedding provider 使用 DashScope 还是内网 BGE 服务。
- 是否开启 external rerank，以及 rerank 服务容量是否已压测。
- 镜像是否已经推送到客户可访问的 registry。
- 备份、恢复、监控、告警和发布回滚流程是否已审批。

## 5. 数据库迁移

迁移脚本：

```powershell
.\scripts\db-migrate.ps1
```

当前迁移由 Alembic 管理，目录为：

- `services/api/migrations/versions`
- `services/api/alembic.ini`

检查当前版本：

```powershell
docker compose -f infra/docker-compose.yml exec postgres psql -U rag -d rag_cleaning -c "select * from alembic_version;"
```

## 6. 健康检查

### 6.1 基础服务

```powershell
curl.exe -s http://localhost:8000/health
docker compose -f infra/docker-compose.yml ps
```

管理控制台：

- RabbitMQ：`http://localhost:15672`，默认账号 `rag` / `rag`
- MinIO：`http://localhost:9001`，默认账号 `rag` / `rag_password`
- Qdrant：`http://localhost:6333/dashboard`

### 6.2 链路验证脚本

| 脚本 | 用途 |
| --- | --- |
| `scripts/smoke-test.ps1` | MVP 主链路冒烟 |
| `scripts/poc-demo.ps1` | 对客 PoC 演示链路 |
| `scripts/embedding-check.ps1` | Embedding provider 可用性验证 |
| `scripts/bge-rerank-test.ps1` | 本地 BGE Rerank 验证 |
| `scripts/diagnostics-test.ps1` | 诊断概览验证 |
| `scripts/metrics-test.ps1` | Prometheus 指标出口验证 |
| `scripts/document-lock-release-test.ps1` | 滞留文档操作锁释放验证 |
| `scripts/document-batch-rebuild-test.ps1` | 批量重建验证 |
| `scripts/document-batch-retry-test.ps1` | 批量失败项重试与取消验证 |
| `scripts/model-eval.ps1` | 模型效果与延迟评测 |
| `scripts/search-load-test.ps1` | 上传吞吐与检索 QPS 轻量压测 |
| `scripts/backup-dry-run.ps1` | PostgreSQL/MinIO/Qdrant 备份检查 dry-run |

PoC 环境验收建议：

```powershell
.\scripts\smoke-test.ps1
.\scripts\poc-demo.ps1
.\scripts\diagnostics-test.ps1
.\scripts\metrics-test.ps1
```

模型与容量验证建议：

```powershell
.\scripts\model-eval.ps1 -DocumentsDir samples\documents\demo-zh -QueriesFile samples\queries\model-eval-queries-zh.json -SkipMock
.\scripts\search-load-test.ps1 -UploadCount 2 -SearchCount 8 -Concurrency 2
```

输出报告：

- `docs/codex/v1/trace/data-cleaning-rag-model-eval-zh-report.md`
- `docs/codex/v1/trace/data-cleaning-rag-load-test-report.md`

### 6.3 监控指标采集

指标出口：

```powershell
curl.exe -s "http://localhost:8000/api/v1/metrics?tenant_id=default&window_minutes=60&stale_lock_minutes=30"
```

首版指标采用 Prometheus text format，覆盖清洗 job 状态/失败率、RabbitMQ ready/consumer、document 操作锁、rerank 降级、API 请求计数和 5xx 错误计数。

建议告警项：

| 指标 | 建议阈值 | 处理建议 |
| --- | --- | --- |
| `rag_cleaning_queue_available` | 等于 `0` | 检查 RabbitMQ 连接、账号、队列是否存在 |
| `rag_cleaning_queue_consumer_count` | 等于 `0` | 检查 Worker 是否运行并订阅队列 |
| `rag_cleaning_job_failure_rate` | 大于 `0` 或连续升高 | 查看失败 job、Worker 日志和文件解析错误 |
| `rag_cleaning_document_lock_stale_count` | 大于 `0` | 检查是否存在异常中断的文档操作 |
| `rag_cleaning_rerank_degraded_recent_count` | 大于 `0` | 检查 rerank provider、模型服务和超时配置 |
| `rag_api_request_error_total` | 持续增长 | 查看 API 结构化日志中的 `trace_id` 并定位异常请求 |

### 6.4 滞留锁治理

当 `rag_cleaning_document_lock_stale_count` 大于 `0`，先查询诊断概览确认滞留文档：

```powershell
curl.exe -s "http://localhost:8000/api/v1/diagnostics/overview?tenant_id=default&stale_lock_minutes=30"
```

确认对应 job 不再运行后，可释放超过阈值的 document 操作锁：

```powershell
curl.exe -s -X POST "http://localhost:8000/api/v1/documents/<document_id>/locks/release?tenant_id=default&stale_lock_minutes=30&actor_id=ops&request_source=ops-console"
```

保护规则：

- 未超过 `stale_lock_minutes` 的锁不会释放。
- 锁关联的 cleaning job 仍为 `PENDING`、`RUNNING` 或 `RETRYING` 时不会释放。
- 释放成功会写入 `DOCUMENT_OPERATION_LOCK_RELEASED` 审计事件。
- 释放后建议立即执行一次重建或更新验证，确认文档链路恢复。

## 7. 日志查看

```powershell
docker compose -f infra/docker-compose.yml logs -f api
docker compose -f infra/docker-compose.yml logs -f worker
docker compose -f infra/docker-compose.yml logs -f rabbitmq
docker compose -f infra/docker-compose.yml logs -f postgres
docker compose -f infra/docker-compose.yml logs -f minio
docker compose -f infra/docker-compose.yml logs -f qdrant
```

查看最近 200 行：

```powershell
docker compose -f infra/docker-compose.yml logs --tail 200 api
```

## 8. 备份与清理

### 8.1 PostgreSQL 备份

```powershell
docker compose -f infra/docker-compose.yml exec -T postgres pg_dump -U rag -d rag_cleaning > backups/rag_cleaning_yyyymmdd_hhmmss.sql
```

安全 dry-run：

```powershell
.\scripts\backup-dry-run.ps1
```

输出：

- `backups/poc/rag_cleaning_<timestamp>.sql`
- `docs/codex/v1/trace/data-cleaning-rag-backup-dry-run-report.md`

恢复演练必须在隔离库或临时环境执行，不允许直接覆盖当前生产库。

### 8.2 MinIO 文件备份

PoC 环境可通过 MinIO 控制台下载 bucket 文件，或使用 `backup-dry-run` 检查 bucket 文件列表。生产环境建议接入对象存储原生版本管理、生命周期策略、跨区域复制或平台备份策略。

### 8.3 Qdrant 向量数据

本地环境向量数据在 Docker volume `infra_qdrant-data`。PoC 可通过重新上传或批量重建恢复；生产环境应使用 Qdrant snapshot、云盘快照或客户平台提供的存储快照。修改 Embedding 维度前必须规划 Qdrant collection 重建。

### 8.4 开发环境清理

```powershell
docker compose -f infra/docker-compose.yml down -v
docker volume ls
```

清理前确认不需要保留本地文档、索引和模型缓存。

## 9. 发布与回滚

发布检查清单：

- `docs/codex/v1/plans/数据清洗与RAG服务发布检查清单.md`

发布前建议执行：

```powershell
docker compose -f infra/docker-compose.yml config --quiet
python -m compileall services\api\app services\worker\app
.\scripts\db-migrate.ps1
.\scripts\backup-dry-run.ps1
.\scripts\smoke-test.ps1
.\scripts\diagnostics-test.ps1
.\scripts\metrics-test.ps1
```

生产审批边界：

- PostgreSQL 生产恢复、Qdrant collection 删除/重建、MinIO bucket 清空、Embedding 维度切换和大规模批量重建必须审批。
- API/Worker 镜像回滚优先通过镜像 tag 回滚；数据库迁移失败时应停止发布并保留现场，不做未评审的手工修表。

## 10. 运维边界

- 本地 PoC 默认 `AUTH_CONTEXT_MODE=local`，`actor_id` 和 `request_source` 可由请求参数兜底；测试/生产建议使用 `gateway` 或 `iam` 模式，由可信网关或 IAM/SSO 注入 `X-Tenant-Id`、`X-Actor-Id`、`X-Request-Source` 和 `X-Permission-Tags`。
- 当前权限治理是标签交集过滤，不等同于完整组织、角色、用户授权体系。
- 当前诊断接口提供最小健康迹象，不替代生产 Prometheus、日志平台、APM 和告警系统。
- 本地 BGE 和本地 reranker 适合演示与离线验证；生产容量、显存、并发和排序收益仍需压测评估。
