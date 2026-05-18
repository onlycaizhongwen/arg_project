# 数据清洗与 RAG 服务 PoC 联调说明

## 1. 联调目标

本说明用于客户 PoC 或测试环境联调，目标是验证一条完整的数据清洗与 RAG 服务链路：

`文件上传 -> 异步清洗 -> 切块 -> Embedding -> 向量入库 -> 混合检索 -> 文档更新 -> 索引重建 -> 批量重建 -> 诊断概览`

完成后，双方可以确认：

- API、Worker、PostgreSQL、RabbitMQ、MinIO、Qdrant 能正常协同。
- 本地 BGE 或通义 Embedding 能正常生成向量。
- RAG 检索能按知识库和权限标签返回结果。
- 文档治理和批量治理接口可用。
- 出现异常时能通过诊断接口和脚本定位。

## 2. 环境准备

### 2.1 基础软件

- Windows PowerShell
- Docker Desktop
- Git
- 可选：Ollama，用于本地 BGE embedding

### 2.2 推荐模型配置

本地演示推荐：

```powershell
$env:EMBEDDING_PROVIDER = "local_bge"
$env:EMBEDDING_MODEL = "bge-m3"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"
$env:RERANK_PROVIDER = "mock"
```

使用本地 BGE 前，确认宿主机有模型：

```powershell
ollama pull bge-m3
curl.exe -s http://localhost:11434/api/tags
```

通义联调可使用：

```powershell
$env:EMBEDDING_PROVIDER = "dashscope"
$env:EMBEDDING_MODEL = "text-embedding-v4"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_OUTPUT_TYPE = "dense"
$env:DASHSCOPE_API_KEY = "<your-key>"
$env:RERANK_PROVIDER = "mock"
```

开发兜底可使用：

```powershell
$env:EMBEDDING_PROVIDER = "mock"
$env:EMBEDDING_MODEL = "mock-embedding"
$env:EMBEDDING_DIMENSION = "1024"
$env:RERANK_PROVIDER = "mock"
```

说明：`mock` 只用于链路验证，不用于判断语义检索质量。

## 3. 启动服务

```powershell
docker compose -f infra/docker-compose.yml build api worker
docker compose -f infra/docker-compose.yml up -d
.\scripts\db-migrate.ps1
docker compose -f infra/docker-compose.yml ps
```

健康检查：

```powershell
curl.exe -s http://localhost:8000/health
```

预期：

```json
{"status":"ok","service":"rag-cleaning-api"}
```

## 4. 标准演示脚本

推荐直接执行：

```powershell
.\scripts\poc-demo.ps1
```

脚本会自动完成：

1. 检查 API 健康状态。
2. 上传演示文档。
3. 等待清洗 job 成功。
4. 执行 hybrid 检索。
5. 更新文档版本。
6. 重建当前文档索引。
7. 按知识库创建批量重建任务。
8. 查询诊断概览。
9. 输出演示摘要。

可指定知识库：

```powershell
.\scripts\poc-demo.ps1 -KnowledgeBaseId "kb-customer-demo"
```

## 5. 手工联调用例

### 5.1 上传文档

```powershell
curl.exe -s -X POST "http://localhost:8000/api/v1/ingestions/files?source_id=default-file-source&tenant_id=default&knowledge_base_id=kb-demo&permission_tags=public" -F "file=@samples/documents/demo/rag-pipeline-mvp.md"
```

记录返回的 `job_id`、`document_id` 和 `document_version_id`。

### 5.2 查询 job

```powershell
curl.exe -s http://localhost:8000/api/v1/jobs/<job_id>
```

预期 `status=SUCCEEDED`。

### 5.3 检索

```powershell
$body = @{
  query = "Which request parameters bound the semantic recall candidate set?"
  tenant_id = "default"
  knowledge_base_ids = @("kb-demo")
  permission_context = @("public")
  search_mode = "hybrid"
  top_k = 5
  recall_size = 30
  pre_rank_size = 10
  rerank_enabled = $true
  rerank_size = 5
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
```

### 5.4 更新文档版本

```powershell
curl.exe -s -X PUT "http://localhost:8000/api/v1/documents/<document_id>/versions?tenant_id=default&actor_id=operator&request_source=poc" -F "file=@samples/documents/demo/retrieval-funnel-boundary.md"
```

### 5.5 重建文档索引

```powershell
curl.exe -s -X POST "http://localhost:8000/api/v1/documents/<document_id>/rebuild?tenant_id=default&actor_id=operator&request_source=poc"
```

### 5.6 批量重建

```powershell
$body = @{
  tenant_id = "default"
  knowledge_base_id = "kb-demo"
  actor_id = "operator"
  request_source = "poc"
  limit = 100
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/document-batches/rebuild" -Method Post -ContentType "application/json" -Body $body
```

查询批次：

```powershell
curl.exe -s "http://localhost:8000/api/v1/document-batches/<batch_id>?tenant_id=default"
```

查询明细：

```powershell
curl.exe -s "http://localhost:8000/api/v1/document-batches/<batch_id>/items?tenant_id=default&limit=20"
```

### 5.7 诊断概览

```powershell
curl.exe -s "http://localhost:8000/api/v1/diagnostics/overview?tenant_id=default&window_minutes=120&stale_lock_minutes=30"
```

重点看：

- `status`
- `job_metrics`
- `queue_metrics`
- `lock_metrics`
- `rerank_metrics`
- `signals`

## 6. 验收脚本

基础链路：

```powershell
.\scripts\smoke-test.ps1
```

批量治理：

```powershell
.\scripts\document-batch-rebuild-test.ps1
```

模型评测：

```powershell
.\scripts\model-eval.ps1 -SkipMock
```

PoC 演示：

```powershell
.\scripts\poc-demo.ps1
```

## 7. 验收记录表

| 验收项 | 命令或接口 | 预期结果 | 结果 |
| --- | --- | --- | --- |
| API 健康检查 | `GET /health` | `status=ok` | 待填写 |
| 文档上传 | `POST /api/v1/ingestions/files` | 返回 `job_id` | 待填写 |
| job 成功 | `GET /api/v1/jobs/{job_id}` | `SUCCEEDED` | 待填写 |
| RAG 检索 | `POST /api/v1/rag/search` | 返回命中片段 | 待填写 |
| 文档更新 | `PUT /api/v1/documents/{document_id}/versions` | 新 job 成功 | 待填写 |
| 文档重建 | `POST /api/v1/documents/{document_id}/rebuild` | 重建 job 成功 | 待填写 |
| 批量重建 | `POST /api/v1/document-batches/rebuild` | batch 成功 | 待填写 |
| 诊断概览 | `GET /api/v1/diagnostics/overview` | 返回诊断指标 | 待填写 |

## 8. 当前边界

- 当前权限是最小标签过滤，不等同完整 IAM 权限系统。
- 当前 `actor_id` 和 `request_source` 来自请求参数，生产建议由网关或认证上下文注入。
- 当前批量治理首版支持批量重建，批量删除、批量 retry、批量取消可后续增强。
- 当前模型评测样例集较小，正式选型前应加入客户真实中文语料。
- `mock` embedding 只做链路兜底，不作为语义效果依据。
