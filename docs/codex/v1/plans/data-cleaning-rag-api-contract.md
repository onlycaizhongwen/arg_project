# 数据清洗与 RAG 服务 MVP API 契约

## 基础信息

- Base URL: `http://localhost:8000`
- API version: `v1`
- Content-Type:
  - JSON 接口：`application/json`
  - 文件上传：`multipart/form-data`
- 默认租户：`default`
- 默认数据源：`default-file-source`
- 默认知识库：`kb-default`

## 统一错误响应

所有业务错误、参数校验错误和未捕获异常统一返回：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

当前错误码：

| code | HTTP status | 触发场景 |
| --- | --- | --- |
| `JOB_NOT_FOUND` | 404 | 查询不存在的 job |
| `JOB_NOT_FAILED` | 409 | 尝试重试非 `FAILED` 状态的 job |
| `DOCUMENT_NOT_FOUND` | 404 | 删除不存在或不属于当前租户的 document |
| `DOCUMENT_DELETED` | 409 | 尝试更新或重建已删除的 document |
| `DOCUMENT_OPERATION_IN_PROGRESS` | 409 | 同一 document 已有更新、删除或重建操作正在执行 |
| `DOCUMENT_VERSION_NOT_INDEXED` | 409 | 尝试重建尚无 `INDEXED` 版本的 document |
| `EMPTY_FILE` | 400 | 上传文件为空 |
| `VALIDATION_ERROR` | 422 | 请求参数类型或结构不合法 |
| `INTERNAL_ERROR` | 500 | 依赖服务异常、模型调用异常、未捕获异常 |

## 健康检查

### `GET /health`

用于确认 API 服务已启动。

#### 响应示例

```json
{
  "status": "ok",
  "service": "rag-cleaning-api"
}
```

#### curl

```powershell
curl.exe -s http://localhost:8000/health
```

## 诊断概览

### `GET /api/v1/diagnostics/overview`

输出阶段 4 P4-5 的最小异常迹象口径，用于在接入 Prometheus/APM 前快速判断当前清洗与检索链路是否健康。

### Query 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `tenant_id` | string | 否 | `default` | 租户 ID |
| `window_minutes` | number | 否 | `60` | 近期失败率和 rerank 降级事件统计窗口 |
| `stale_lock_minutes` | number | 否 | `30` | document 操作锁超过该时长视为滞留 |

### 响应重点字段

| 字段 | 说明 |
| --- | --- |
| `status` | `ok`、`warning` 或 `critical` |
| `job_metrics` | cleaning job 状态分布、近期失败数和失败率 |
| `queue_metrics` | RabbitMQ 队列是否可读、ready 消息数和消费者数 |
| `lock_metrics` | 当前 document 操作锁数量和滞留锁列表 |
| `rerank_metrics` | 当前 rerank provider、模型和近期降级次数 |
| `signals` | 已触发的异常迹象，如 `JOB_BACKLOG`、`DOCUMENT_LOCK_STALE`、`RERANK_DEGRADED` |

### curl

```powershell
curl.exe -s "http://localhost:8000/api/v1/diagnostics/overview?tenant_id=default&window_minutes=60&stale_lock_minutes=30"
```

## 文件上传接入

### `POST /api/v1/ingestions/files`

上传一个文件，创建文档、文档版本和清洗任务，并投递 RabbitMQ 任务。

### Query 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `source_id` | string | 否 | `default-file-source` | 数据源 ID |
| `tenant_id` | string | 否 | `default` | 租户 ID |
| `knowledge_base_id` | string | 否 | `kb-default` | 知识库 ID，用于后续检索过滤 |
| `permission_tags` | string | 否 | `public` | 逗号分隔权限标签，例如 `public`、`internal`、`public,team-a` |

### Form 参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | 上传文件，MVP 已验证 txt/md/csv/pdf 基础解析 |

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `job_id` | string | 清洗任务 ID |
| `document_id` | string | 文档 ID |
| `document_version_id` | string | 文档版本 ID |
| `source_id` | string | 数据源 ID |
| `knowledge_base_id` | string | 知识库 ID |
| `permission_tags` | array[string] | 权限标签，默认 `["public"]` |
| `filename` | string | 文件名 |
| `status` | string | 初始为 `PENDING` |

### 响应示例

```json
{
  "job_id": "08131054-4022-438d-9440-7ddfcc375fc1",
  "document_id": "70fef73a-2f6c-4d2b-a192-89da5e5f933b",
  "document_version_id": "cc44d077-07c0-4922-ab66-47e1a891fe1a",
  "source_id": "default-file-source",
  "knowledge_base_id": "kb-default",
  "permission_tags": ["public"],
  "filename": "smoke.txt",
  "status": "PENDING"
}
```

### curl

```powershell
curl.exe -s -X POST "http://localhost:8000/api/v1/ingestions/files?source_id=default-file-source&tenant_id=default&knowledge_base_id=kb-default&permission_tags=public" -F "file=@samples/documents/smoke.txt"
```

## 查询清洗任务

### `GET /api/v1/jobs/{job_id}`

查询清洗任务状态、重试次数和错误信息。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `job_id` | string | 是 | 文件上传接口返回的任务 ID |

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `job_id` | string | 清洗任务 ID |
| `document_version_id` | string | 文档版本 ID |
| `tenant_id` | string | 租户 ID |
| `status` | string | `PENDING`、`RUNNING`、`RETRYING`、`FAILED`、`SUCCEEDED` |
| `retry_count` | number | 已重试次数 |
| `error_message` | string/null | 失败原因 |
| `started_at` | string/null | 开始时间 |
| `finished_at` | string/null | 完成时间 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 响应示例

```json
{
  "job_id": "08131054-4022-438d-9440-7ddfcc375fc1",
  "document_version_id": "cc44d077-07c0-4922-ab66-47e1a891fe1a",
  "tenant_id": "default",
  "status": "SUCCEEDED",
  "retry_count": 0,
  "error_message": null,
  "started_at": "2026-05-16T11:00:00.000000+00:00",
  "finished_at": "2026-05-16T11:00:04.000000+00:00",
  "created_at": "2026-05-16T11:00:00.000000+00:00",
  "updated_at": "2026-05-16T11:00:04.000000+00:00"
}
```

### curl

```powershell
curl.exe -s http://localhost:8000/api/v1/jobs/<job_id>
```

### 不存在任务响应

```json
{
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "Job not found"
  }
}
```

## 人工重试失败任务

### `POST /api/v1/jobs/{job_id}/retry`

为 `FAILED` 状态的清洗任务创建一个新的 retry job，复用原 `document_version` 和对象存储文件。原 job 保留失败记录，新 job 独立进入 `PENDING` 并投递 Worker。

### Path 参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `job_id` | string | 是 | 原失败任务 ID |

### Query 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `tenant_id` | string | 否 | `default` | 租户 ID |
| `actor_id` | string | 否 | `system` | 操作者 ID，写入审计事件 |
| `request_source` | string | 否 | `api` | 请求来源，写入审计事件 |

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `job_id` | string | 新 retry job ID |
| `retry_of_job_id` | string | 原失败 job ID |
| `document_id` | string | 文档 ID |
| `document_version_id` | string | 文档版本 ID |
| `tenant_id` | string | 租户 ID |
| `status` | string | 初始为 `PENDING` |
| `operation` | string | 固定为 `RETRY_JOB` |

### curl

```powershell
curl.exe -s -X POST "http://localhost:8000/api/v1/jobs/<job_id>/retry?tenant_id=default&actor_id=operator&request_source=console"
```

## 删除文档

### `DELETE /api/v1/documents/{document_id}`

软删除文档及其版本，并删除 Qdrant 中对应 chunk 向量。删除后该文档不应再被检索召回。接口具备幂等性，重复删除同一文档仍返回 `DELETED`。

### Query 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `tenant_id` | string | 否 | `default` | 租户 ID |
| `actor_id` | string | 否 | `system` | 操作者 ID，写入审计事件 |
| `request_source` | string | 否 | `api` | 请求来源，写入审计事件 |

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `document_id` | string | 文档 ID |
| `tenant_id` | string | 租户 ID |
| `status` | string | 删除后为 `DELETED` |
| `chunk_count` | number | 文档对应 chunk 数 |
| `deleted_vector_count` | number | 本次请求尝试删除的向量点数量 |

### curl

```powershell
curl.exe -s -X DELETE "http://localhost:8000/api/v1/documents/<document_id>?tenant_id=default"
```

## 创建文档新版本

### `PUT /api/v1/documents/{document_id}/versions`

为已有文档上传新文件并创建新的 `document_version` 与清洗任务。新版本清洗成功前，旧的 `INDEXED` 版本保持可见；新版本成功后，旧版本标记为 `SUPERSEDED`，检索只返回新的 `INDEXED` 版本。

### Query 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `tenant_id` | string | 否 | `default` | 租户 ID |
| `actor_id` | string | 否 | `system` | 操作者 ID，写入审计事件 |
| `request_source` | string | 否 | `api` | 请求来源，写入审计事件 |

### Form 参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | 新版本文件 |

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `job_id` | string | 新版本清洗任务 ID |
| `document_id` | string | 原文档 ID |
| `document_version_id` | string | 新文档版本 ID |
| `version_no` | number | 新版本号 |
| `knowledge_base_id` | string | 继承自原文档的知识库 ID |
| `permission_tags` | array[string] | 继承自原文档的权限标签 |
| `filename` | string | 新版本文件名 |
| `status` | string | 初始为 `PENDING` |

### curl

```powershell
curl.exe -s -X PUT "http://localhost:8000/api/v1/documents/<document_id>/versions?tenant_id=default" -F "file=@samples/documents/smoke.txt"
```

## 重建文档索引

### `POST /api/v1/documents/{document_id}/rebuild`

对当前可见的 `INDEXED` 文档版本创建一个新的清洗任务，复用原始对象存储文件重新解析、切块、Embedding 并 upsert Qdrant 向量。重建成功后仍使用原 `document_version_id`；重建失败时不会创建新版本，旧索引默认继续可用。

### Query 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `tenant_id` | string | 否 | `default` | 租户 ID |
| `actor_id` | string | 否 | `system` | 操作者 ID，写入审计事件 |
| `request_source` | string | 否 | `api` | 请求来源，写入审计事件 |

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `job_id` | string | 重建清洗任务 ID |
| `document_id` | string | 文档 ID |
| `document_version_id` | string | 当前可见版本 ID |
| `version_no` | number | 当前可见版本号 |
| `knowledge_base_id` | string | 文档知识库 ID |
| `permission_tags` | array[string] | 文档权限标签 |
| `status` | string | 初始为 `PENDING` |
| `operation` | string | 固定为 `REBUILD_INDEX` |

### curl

```powershell
curl.exe -s -X POST "http://localhost:8000/api/v1/documents/<document_id>/rebuild?tenant_id=default"
```

## 查询文档审计

### `GET /api/v1/documents/{document_id}/audit`

返回文档管理操作审计事件。当前记录文档新版本创建、索引重建请求和文档删除。

### Query 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `tenant_id` | string | 否 | `default` | 租户 ID |
| `limit` | number | 否 | `50` | 返回条数，范围 1-200 |
| `operation` | string | 否 | 无 | 按审计操作类型过滤 |

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `document_id` | string | 文档 ID |
| `tenant_id` | string | 租户 ID |
| `items[].operation` | string | 操作类型 |
| `items[].actor_id` | string | 操作者 ID |
| `items[].request_source` | string | 请求来源 |
| `items[].document_version_id` | string/null | 关联版本 ID |
| `items[].job_id` | string/null | 关联任务 ID |
| `items[].metadata` | object | 操作补充信息 |
| `items[].created_at` | string | 审计事件创建时间 |

### curl

```powershell
curl.exe -s "http://localhost:8000/api/v1/documents/<document_id>/audit?tenant_id=default&limit=20"
```

## RAG 语义检索

### `POST /api/v1/rag/search`

执行 RAG 检索，支持语义召回、关键词召回、混合 RRF 粗排、业务干预去重/打散、可选重排降级和权限标签过滤。

### 请求字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `query` | string | 是 | 无 | 用户查询 |
| `tenant_id` | string | 否 | `default` | 租户过滤 |
| `knowledge_base_ids` | array[string] | 否 | `["kb-default"]` | 知识库过滤 |
| `permission_context` | array[string] | 否 | `["public"]` | 当前请求具备的权限标签，和 chunk 权限标签取交集 |
| `search_mode` | string | 否 | `hybrid` | `semantic`、`keyword`、`hybrid` |
| `top_k` | number | 否 | `10` | 最终返回条数 |
| `recall_size` | number | 否 | `200` | Qdrant 召回候选数 |
| `pre_rank_size` | number | 否 | `50` | MVP 粗排/截断后的候选数 |
| `dedup_enabled` | boolean | 否 | `true` | 是否启用内容去重 |
| `diversity_enabled` | boolean | 否 | `true` | 是否启用 MMR 简化打散 |
| `max_chunks_per_document` | number | 否 | `2` | 同一文档版本最多返回的 chunk 数 |
| `rerank_enabled` | boolean | 否 | `false` | 是否启用重排 |
| `rerank_size` | number | 否 | `50` | 最多进入重排的候选数 |

### 请求示例

```json
{
  "query": "Which request parameters bound the semantic recall candidate set?",
  "tenant_id": "default",
  "knowledge_base_ids": ["kb-demo"],
  "permission_context": ["public"],
  "search_mode": "hybrid",
  "top_k": 5,
  "recall_size": 30,
  "pre_rank_size": 10,
  "dedup_enabled": true,
  "diversity_enabled": true,
  "max_chunks_per_document": 2,
  "rerank_enabled": false,
  "rerank_size": 5
}
```

### 响应字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `query` | string | 原始查询 |
| `items` | array | 命中的 chunk 列表 |
| `items[].chunk_id` | string | chunk ID |
| `items[].score` | number | 当前排序分，语义/关键词模式为对应原始分，hybrid 模式为 RRF 融合分 |
| `items[].recall_sources` | array[string] | 命中来源，例如 `semantic`、`keyword` |
| `items[].semantic_score` | number/null | 语义召回原始分 |
| `items[].keyword_score` | number/null | 关键词召回原始分 |
| `items[].pre_rank_score` | number | 粗排融合分 |
| `items[].rerank_score` | number/null | 重排分；未启用重排或降级时为空 |
| `items[].content` | string | chunk 内容 |
| `items[].document_id` | string | 文档 ID |
| `items[].document_version_id` | string | 文档版本 ID |
| `items[].knowledge_base_id` | string | 知识库 ID |
| `items[].permission_tags` | array[string] | chunk 权限标签 |
| `items[].chunk_index` | number | chunk 序号 |
| `items[].metadata` | object | 解析器元数据 |
| `search_plan.search_mode` | string | 本次搜索模式 |
| `search_plan.recall_size` | number | 本次召回候选数配置 |
| `search_plan.pre_rank_size` | number | 本次截断候选数配置 |
| `search_plan.top_k` | number | 本次返回数配置 |
| `search_plan.dedup_enabled` | boolean | 是否启用去重 |
| `search_plan.diversity_enabled` | boolean | 是否启用打散 |
| `search_plan.max_chunks_per_document` | number | 同一文档版本返回上限 |
| `search_plan.permission_context` | array[string] | 本次检索使用的权限上下文 |
| `search_plan.semantic_recall_count` | number | 语义召回数量 |
| `search_plan.keyword_recall_count` | number | 关键词召回数量 |
| `search_plan.merged_count` | number | 合并后候选数量 |
| `search_plan.business_filtered_count` | number | 业务过滤后候选数量 |
| `search_plan.dedup_removed_count` | number | 去重移除数量 |
| `search_plan.document_limit_removed_count` | number | 同文档限额移除数量 |
| `search_plan.rerank_size` | number | 进入重排的候选上限 |
| `search_plan.rerank_provider` | string | `disabled`、`mock`、`external` |
| `search_plan.rerank_enabled` | boolean | 本次请求是否启用重排 |
| `search_plan.rerank_degraded` | boolean | 重排失败或超时时是否降级 |

### 响应示例

```json
{
  "query": "Which request parameters bound the semantic recall candidate set?",
  "items": [
    {
      "chunk_id": "c23f3c58-92cb-5f45-9983-7d6d1cf6cc30",
      "score": 0.8123,
      "content": "The search request exposes recall_size, pre_rank_size, and top_k so the candidate set is bounded before results are returned.",
      "document_id": "59da62d8-8ff6-4ef5-8055-b08f46f253b1",
      "document_version_id": "8e3da0b2-b7c9-4d03-83f1-620c6db6d355",
      "knowledge_base_id": "kb-demo",
      "permission_tags": ["public"],
      "chunk_index": 2,
      "metadata": {
        "parser": "plain_text",
        "filename": "retrieval-funnel-boundary.md"
      }
    }
  ],
  "search_plan": {
    "recall_size": 30,
    "pre_rank_size": 10,
    "top_k": 5,
    "rerank_enabled": false
  }
}
```

### PowerShell

```powershell
$body = @{
  query = "Which request parameters bound the semantic recall candidate set?"
  tenant_id = "default"
  knowledge_base_ids = @("kb-demo")
  permission_context = @("public")
  top_k = 5
  recall_size = 30
  pre_rank_size = 10
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/rag/search" -Method Post -ContentType "application/json" -Body $body
```

## MVP 验收脚本

### 冒烟验证

```powershell
.\scripts\smoke-test.ps1
```

覆盖：

- API 健康检查。
- 上传 `samples/documents/smoke.txt`。
- 等待 job 到 `SUCCEEDED`。
- 检索 `kb-default`。
- 验证错误知识库不返回结果。

### Demo 评测

```powershell
.\scripts\demo-eval.ps1
```

覆盖：

- 上传 `samples/documents/demo` 下 3 份文档到 `kb-demo`。
- 执行 `samples/queries/demo-queries.json` 下 5 条查询。
- 检查返回 chunk 是否包含预期关键词。

### 异常场景验证

```powershell
.\scripts\failure-test.ps1
```

覆盖：

- 不存在 job 返回 `JOB_NOT_FOUND`。
- 非法请求参数返回 `VALIDATION_ERROR`。
- 空文件上传返回 `EMPTY_FILE`。
- 不支持的文件类型创建异步任务后进入 `FAILED`，并记录解析错误。

### 重排降级验证

当 `RERANK_PROVIDER=external` 且外部服务不可用时：

```powershell
.\scripts\rerank-degrade-test.ps1
```

预期：

- 检索接口仍返回结果。
- `search_plan.rerank_degraded=true`。

### 本地 BGE 重排验证

当需要验证真实重排链路时，可启用 Compose profile `reranker`：

```powershell
$env:COMPOSE_PROFILES = "reranker"
$env:EMBEDDING_PROVIDER = "local_bge"
$env:EMBEDDING_MODEL = "bge-m3"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"
$env:RERANK_PROVIDER = "external"
$env:RERANK_MODEL = "BAAI/bge-reranker-base"
$env:RERANK_BASE_URL = "http://reranker:8010/rerank"
$env:RERANK_TIMEOUT_SECONDS = "30"

docker compose -f infra\docker-compose.yml up -d reranker api worker
.\scripts\bge-rerank-test.ps1
```

2026-05-16 已验证通过：返回 `search_plan.rerank_provider=external`、`search_plan.rerank_degraded=false`，且返回结果包含 `rerank_score`。

### 权限标签验证

```powershell
.\scripts\permission-test.ps1
```

覆盖：

- 上传 `public` 和 `internal` 两类权限标签文档。
- 默认权限上下文只返回 `public`。
- `permission_context=["public"]` 不返回 `internal` 文档。
- `permission_context=["internal"]` 可以返回 `internal` 文档。

### 文档删除验证

```powershell
.\scripts\document-delete-test.ps1
```

覆盖：

- 上传样例文档并确认可检索。
- 调用 `DELETE /api/v1/documents/{document_id}`。
- 删除后同一检索不再返回该文档。
- 重复删除不报错。

### 文档更新验证

```powershell
.\scripts\document-update-test.ps1
```

覆盖：

- 上传原始版本并确认可检索。
- 调用 `PUT /api/v1/documents/{document_id}/versions` 创建新版本。
- 新版本处理成功后，旧版本不再被检索返回。
- 新版本可被检索返回。

### 文档索引重建验证

```powershell
.\scripts\document-rebuild-test.ps1
```

覆盖：

- 上传文档并确认可检索。
- 调用 `POST /api/v1/documents/{document_id}/rebuild`。
- 重建任务成功后仍使用原 `document_version_id`。
- 重建后原文档仍可被检索返回。

### 文档审计验证

```powershell
.\scripts\document-audit-test.ps1
```

覆盖：

- 创建新版本写入 `DOCUMENT_VERSION_CREATED`。
- Worker 完成新版本索引写入 `DOCUMENT_VERSION_INDEXED`。
- 重建索引写入 `DOCUMENT_INDEX_REBUILD_REQUESTED`。
- Worker 完成重建写入 `DOCUMENT_INDEX_REBUILD_SUCCEEDED`。
- 删除文档写入 `DOCUMENT_DELETED` 和 `DOCUMENT_DELETE_SUCCEEDED`。
- 审计事件保留 `actor_id` 和 `request_source`。
- 审计查询支持按 `operation` 过滤。

### 文档操作锁验证

```powershell
.\scripts\document-operation-lock-test.ps1
```

覆盖：

- 创建新版本时持有 document 级操作锁。
- 同一 document 在更新任务完成前请求重建会返回 `DOCUMENT_OPERATION_IN_PROGRESS`。
- 更新任务完成后锁释放，重建请求可继续执行。

### 人工重试验证

```powershell
.\scripts\job-retry-test.ps1
```

覆盖：

- 不支持格式文件进入 `FAILED`。
- 对 `FAILED` job 创建新的 retry job。
- retry job 保留 `retry_of_job_id`。
- 写入 `JOB_RETRY_REQUESTED` 审计事件。
- retry job 最终失败写入 `JOB_RETRY_FAILED`。
- 非 `FAILED` job 重试返回 `JOB_NOT_FAILED`。

### 诊断概览验证

```powershell
.\scripts\diagnostics-test.ps1
```

覆盖：
- `GET /api/v1/diagnostics/overview` 可返回 `status`。
- 返回 job 状态分布、RabbitMQ 队列状态、document 操作锁指标和 rerank 降级统计。
- `signals` 以统一 code/severity/message 结构输出异常迹象。

## 当前边界

- 当前权限治理只实现最小标签交集过滤，尚未接入真实鉴权、用户组、角色和限流。
- 当前未实现人工重试接口。
- 当前已实现文档删除后不可检索、文档更新后新版本可见、按 `document_id` 重建当前可见版本索引、最小文档操作审计、document 级操作锁和失败 job 人工重试；批量重建、审计检索筛选、锁超时释放接口和完整安全审计仍未实现。
- 当前精排已完成本地 BGE `BAAI/bge-reranker-base` 真实链路验证；生产选型、服务容量和排序收益评估仍需后续压测与评测集验证。
- 当前检索质量验证只覆盖 Demo 样例集，不代表真实生产语料效果。
