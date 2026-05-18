# 数据清洗与 RAG 服务问题排查手册

## 1. 快速定位顺序

出现联调问题时，建议按下面顺序排查：

1. API 是否可访问：`curl.exe -s http://localhost:8000/health`
2. 容器是否正常：`docker compose -f infra/docker-compose.yml ps`
3. 诊断概览是否异常：`curl.exe -s "http://localhost:8000/api/v1/diagnostics/overview?tenant_id=default"`
4. Worker 是否消费：看 RabbitMQ ready/consumer 和 Worker 日志
5. 模型是否可用：运行 `.\scripts\embedding-check.ps1` 或 `.\scripts\bge-rerank-test.ps1`
6. 数据是否入库：查 job、PostgreSQL、MinIO、Qdrant

## 2. API 不通

### 现象

- `http://localhost:8000/health` 无响应。
- 请求返回连接失败或超时。

### 可能原因

- Docker Desktop 未启动。
- `rag-cleaning-api` 容器未启动或启动失败。
- 端口 `8000` 被占用。
- API 启动配置校验失败。

### 检查命令

```powershell
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml logs --tail 200 api
curl.exe -s http://localhost:8000/health
```

### 修复建议

- 启动 Docker Desktop 后重新执行 `docker compose -f infra/docker-compose.yml up -d`。
- 查看 API 日志中缺失的环境变量或依赖连接错误。
- 如端口冲突，修改 `infra/docker-compose.yml` 中 API 端口映射。

## 3. Docker 镜像拉取失败

### 现象

- `docker compose build` 或 `docker compose up` 拉取镜像超时。
- 日志出现 Docker Hub 连接失败。

### 可能原因

- 国外镜像源不可达。
- 客户网络限制访问公共 registry。

### 检查命令

```powershell
docker compose -f infra/docker-compose.yml config
docker pull docker.m.daocloud.io/library/python:3.12-slim
```

### 修复建议

- 优先使用 `.env.example` 中默认的 `docker.m.daocloud.io` 国内镜像源。
- 客户环境有内网镜像仓库时，覆盖 `PYTHON_BASE_IMAGE`、`POSTGRES_IMAGE`、`RABBITMQ_IMAGE`、`MINIO_IMAGE`、`QDRANT_IMAGE`。
- 只改镜像地址，不改服务名和端口，避免影响 Compose 内部依赖。

## 4. PostgreSQL 迁移失败

### 现象

- `.\scripts\db-migrate.ps1` 失败。
- API 日志提示表或字段不存在。

### 可能原因

- PostgreSQL 容器未健康。
- Alembic 版本不一致。
- 本地旧数据卷结构与新迁移冲突。

### 检查命令

```powershell
docker compose -f infra/docker-compose.yml ps postgres
docker compose -f infra/docker-compose.yml logs --tail 200 postgres
docker compose -f infra/docker-compose.yml exec postgres psql -U rag -d rag_cleaning -c "select * from alembic_version;"
.\scripts\db-migrate.ps1
```

### 修复建议

- 等 PostgreSQL healthcheck 通过后再迁移。
- PoC 环境可备份后执行 `docker compose -f infra/docker-compose.yml down -v` 重建数据卷。
- 不要手工跳过迁移文件；新增字段应继续通过 Alembic 管理。

## 5. RabbitMQ 队列积压

### 现象

- 上传接口返回 `PENDING`，job 长时间不进入 `SUCCEEDED`。
- 诊断概览出现 `JOB_BACKLOG`。
- RabbitMQ ready 消息数持续增长。

### 可能原因

- Worker 未启动。
- Worker 无法连接 RabbitMQ。
- Worker 处理失败后反复重试。

### 检查命令

```powershell
curl.exe -s "http://localhost:8000/api/v1/diagnostics/overview?tenant_id=default"
docker compose -f infra/docker-compose.yml logs --tail 200 worker
docker compose -f infra/docker-compose.yml logs --tail 200 rabbitmq
```

也可打开 RabbitMQ 控制台：

```text
http://localhost:15672
账号：rag
密码：rag
```

### 修复建议

- 重启 Worker：`docker compose -f infra/docker-compose.yml up -d worker`
- 先修复 Worker 日志中的模型、MinIO、Qdrant 或数据库错误。
- 对已失败的 job 使用 `POST /api/v1/jobs/{job_id}/retry` 或运行 `scripts/job-retry-test.ps1` 验证重试链路。

## 6. Worker 不消费

### 现象

- RabbitMQ 队列有 ready 消息，但 consumer 为 0。
- Worker 容器退出。

### 可能原因

- Worker 启动配置校验失败。
- RabbitMQ 地址、账号或队列配置错误。
- Worker 镜像未重建，代码版本旧。

### 检查命令

```powershell
docker compose -f infra/docker-compose.yml ps worker
docker compose -f infra/docker-compose.yml logs --tail 200 worker
docker compose -f infra/docker-compose.yml build worker
```

### 修复建议

- 重新构建并启动 Worker。
- 确认 Compose 内部 `RABBITMQ_HOST` 为 `rabbitmq`，不是 `localhost`。
- 确认 `RABBITMQ_QUEUE=cleaning.jobs`。

## 7. MinIO 对象不存在

### 现象

- Worker 日志提示对象下载失败。
- job 进入 `FAILED`，错误信息包含对象存储读取失败。

### 可能原因

- MinIO 容器未启动。
- bucket 未创建或本地数据卷被清理。
- 数据库中 job 指向的对象已不存在。

### 检查命令

```powershell
docker compose -f infra/docker-compose.yml ps minio
docker compose -f infra/docker-compose.yml logs --tail 200 minio
```

打开 MinIO 控制台：

```text
http://localhost:9001
账号：rag
密码：rag_password
```

### 修复建议

- 确认 bucket `rag-documents` 存在。
- PoC 环境中如果数据卷被清空，重新上传文档。
- 对旧 job 不建议强行重试，优先重新上传或创建新版本。

## 8. Qdrant 无检索结果

### 现象

- job 已 `SUCCEEDED`，但检索 `items` 为空。
- Qdrant dashboard 中 collection 为空。

### 可能原因

- `knowledge_base_ids` 或 `permission_context` 过滤条件不匹配。
- Worker 写入 Qdrant 失败。
- Qdrant collection 维度与当前 embedding 维度不一致。
- 文档已被删除或版本已被 `SUPERSEDED`。

### 检查命令

```powershell
.\scripts\smoke-test.ps1
curl.exe -s "http://localhost:6333/dashboard"
docker compose -f infra/docker-compose.yml logs --tail 200 worker
```

### 修复建议

- 检查检索请求中的 `knowledge_base_ids`，确认和上传时的 `knowledge_base_id` 一致。
- 检查 `permission_context` 是否包含文档的 `permission_tags`。
- 如切换过 embedding 维度，清理 Qdrant 数据卷或重建 collection 后重新入库。

## 9. Embedding 维度不匹配

### 现象

- Worker 写入 Qdrant 报错。
- 切换模型后检索失败。

### 可能原因

- `EMBEDDING_DIMENSION` 与模型实际输出维度不一致。
- Qdrant collection 已按旧维度创建。

### 检查命令

```powershell
.\scripts\embedding-check.ps1
docker compose -f infra/docker-compose.yml logs --tail 200 worker
```

### 修复建议

- 本地 `bge-m3` 和 DashScope `text-embedding-v4` 当前按 `1024` 维配置。
- 切换到不同维度模型时，同步修改 `EMBEDDING_DIMENSION`。
- PoC 环境可删除 Qdrant 数据卷后重新上传文档。

## 10. 本地 BGE 不可用

### 现象

- `embedding-check.ps1` 失败。
- API/Worker 日志提示连接 `host.docker.internal:11434` 失败。

### 可能原因

- Ollama 未启动。
- `bge-m3` 模型未拉取。
- 容器内错误使用了 `localhost:11434`。

### 检查命令

```powershell
ollama pull bge-m3
curl.exe -s http://localhost:11434/api/tags
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"
.\scripts\embedding-check.ps1
```

### 修复建议

- 宿主机访问 Ollama 用 `localhost:11434`。
- 容器访问宿主机 Ollama 用 `host.docker.internal:11434`。
- 如果客户环境不允许宿主机模型服务，可先切回 `EMBEDDING_PROVIDER=mock` 验证工程链路。

## 11. DashScope Key 或调用失败

### 现象

- DashScope embedding 调用返回认证失败或超时。
- `embedding-check.ps1` 失败。

### 可能原因

- `DASHSCOPE_API_KEY` 未配置或无效。
- 客户网络无法访问 DashScope。
- 模型名称或输出参数不正确。

### 检查命令

```powershell
$env:EMBEDDING_PROVIDER = "dashscope"
$env:EMBEDDING_MODEL = "text-embedding-v4"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_OUTPUT_TYPE = "dense"
$env:DASHSCOPE_API_KEY = "<your-key>"
.\scripts\embedding-check.ps1
```

### 修复建议

- 确认 Key 已开通对应模型权限。
- 对客户内网环境，优先使用本地 BGE 演示。
- DashScope 仅作为线上兼容模型配置，不阻塞本地 PoC。

## 12. Rerank 降级

### 现象

- 检索有结果，但 `search_plan.rerank_degraded=true`。
- 诊断概览出现 `RERANK_DEGRADED`。

### 可能原因

- 外部 rerank 服务不可用。
- `RERANK_BASE_URL` 配置错误。
- 模型首次下载耗时过长导致超时。

### 检查命令

```powershell
.\scripts\rerank-degrade-test.ps1
docker compose -f infra/docker-compose.yml logs --tail 200 reranker
curl.exe -s "http://localhost:8000/api/v1/diagnostics/overview?tenant_id=default"
```

### 修复建议

- 本地真实重排验证时启用 `COMPOSE_PROFILES=reranker`。
- 首次下载模型较慢，必要时增大 `RERANK_TIMEOUT_SECONDS`。
- 如 `hf-mirror.com` 元数据异常，可临时切换 `HF_ENDPOINT=https://huggingface.co` 预热模型缓存。
- 业务联调可先使用 `RERANK_PROVIDER=mock` 或 `disabled`，不影响主检索链路。

## 13. 文档操作锁滞留

### 现象

- 更新、删除或重建接口返回 `DOCUMENT_OPERATION_IN_PROGRESS`。
- 诊断概览出现 `DOCUMENT_LOCK_STALE`。

### 可能原因

- Worker 处理过程中异常退出。
- job 最终失败但锁未释放。
- 文档正在执行更新或重建，属于正常保护。

### 检查命令

```powershell
curl.exe -s "http://localhost:8000/api/v1/diagnostics/overview?tenant_id=default&stale_lock_minutes=30"
docker compose -f infra/docker-compose.yml logs --tail 200 worker
.\scripts\document-operation-lock-test.ps1
.\scripts\document-lock-release-test.ps1
```

### 修复建议

- 先确认对应 job 是否仍在运行。
- 如果是正常运行，等待 job 完成后重试。
- 如果确认为异常滞留，使用 `POST /api/v1/documents/{document_id}/locks/release` 安全释放；接口会拒绝未超过阈值的锁，并保护 `PENDING`、`RUNNING`、`RETRYING` 状态 job。
- 释放成功后检查 `DOCUMENT_OPERATION_LOCK_RELEASED` 审计事件，并发起一次重建或更新验证链路恢复。

## 14. 批量重建异常

### 现象

- 批量任务状态为 `FAILED` 或 `PARTIAL_SUCCEEDED`。
- 部分 item 失败或跳过。

### 可能原因

- 过滤条件下没有可重建文档。
- 部分 document 正在被更新、删除或重建。
- 个别文档对象存储文件缺失。

### 检查命令

```powershell
.\scripts\document-batch-rebuild-test.ps1
.\scripts\document-batch-retry-test.ps1
curl.exe -s "http://localhost:8000/api/v1/document-batches/<batch_id>?tenant_id=default"
curl.exe -s "http://localhost:8000/api/v1/document-batches/<batch_id>/items?tenant_id=default&limit=20"
```

### 修复建议

- 查看 item 的 `error_code` 和 `error_message`。
- 对锁冲突文档，等待当前操作完成后再次提交批量重建。
- 对失败 item，使用 `POST /api/v1/document-batches/{batch_id}/retry-failed` 重试失败项；已成功 item 不会重复提交。
- 如批次仍有未提交的 `PENDING` item，可使用 `POST /api/v1/document-batches/{batch_id}/cancel` 取消剩余项。
- 对对象缺失文档，重新上传新版本。

## 15. 最小回归命令

## 15. 认证上下文异常

### 现象

- 接口返回 `AUTH_CONTEXT_MISSING`。
- 接口返回 `AUTH_CONTEXT_FORBIDDEN`。
- 审计中的 actor/source 与预期不一致。

### 可能原因

- `AUTH_CONTEXT_MODE=gateway` 或 `iam` 时，网关未注入 `X-Tenant-Id` 或 `X-Actor-Id`。
- 生产模式下终端用户绕过可信网关直接访问 API。
- `X-Permission-Tags` 为空，且 `AUTH_EMPTY_PERMISSION_POLICY=deny`。
- 网关映射的权限标签与文档 `permission_tags` 不匹配。

### 检查命令

```powershell
curl.exe -i http://localhost:8000/health
.\scripts\request-context-test.ps1
.\scripts\permission-test.ps1
docker compose -f infra/docker-compose.yml logs --tail 200 api
```

### 修复建议

- 本地 PoC 使用 `AUTH_CONTEXT_MODE=local`。
- 测试/生产确认网关已注入 `X-Tenant-Id`、`X-Actor-Id`、`X-Request-Source` 和 `X-Permission-Tags`。
- 如果只是联调环境临时缺少权限标签，可先使用 `AUTH_EMPTY_PERMISSION_POLICY=public_only`。
- 生产环境不要让浏览器或终端用户直接伪造身份 Header。

## 16. 最小回归命令

修复问题后建议至少运行：

```powershell
.\scripts\smoke-test.ps1
.\scripts\diagnostics-test.ps1
```

涉及批量治理时补充：

```powershell
.\scripts\document-batch-rebuild-test.ps1
.\scripts\document-batch-retry-test.ps1
```

涉及模型配置时补充：

```powershell
.\scripts\embedding-check.ps1
.\scripts\bge-rerank-test.ps1
```
