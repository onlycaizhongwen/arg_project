# 数据清洗与 RAG 服务工程初始化执行计划

## 目标

在 MVP 开工计划基础上，进一步把第一轮工程初始化拆到文件级任务。完成本计划后，项目应具备：

- 可启动的 FastAPI API 服务。
- 可启动的 Python Worker。
- 可通过 Docker Compose 启动 PostgreSQL、RabbitMQ、MinIO、Qdrant。
- 可配置的兼容 Embedding 适配层。
- 可执行的数据库初始化脚本。

## 当前前提

已确认：

- 技术栈：Python。
- API 控制面：FastAPI。
- Worker：Python Worker。
- Embedding：兼容适配层，线上通义 text-embedding，本地 BGE，mock 兜底。
- MVP 检索：语义召回 + 基础粗排/候选截断。

待确认：

- 本地是否可使用 Docker Compose。
- 首批解析格式是否锁定为 PDF + CSV。
- 本地 BGE 服务地址与向量维度。
- 线上 DashScope API Key 的注入方式。

## 阶段 E1：创建工程骨架

### 文件任务

创建目录：

```text
services/api/app/
services/worker/app/
infra/db/
infra/minio/
samples/documents/
samples/queries/
```

创建文件：

```text
services/api/app/main.py
services/api/app/core/config.py
services/api/app/api/ingestion.py
services/api/app/api/jobs.py
services/api/app/api/search.py
services/api/pyproject.toml
services/api/Dockerfile

services/worker/app/main.py
services/worker/app/embeddings/embedding_client.py
services/worker/app/consumers/cleaning_consumer.py
services/worker/pyproject.toml
services/worker/Dockerfile

infra/docker-compose.yml
infra/db/init.sql
.env.example
```

### 验收

- `services/api/app/main.py` 提供 `GET /health`。
- `services/worker/app/main.py` 能启动并打印 worker ready。
- `.env.example` 包含全部基础配置。

## 阶段 E2：基础配置与依赖

### API 依赖建议

```text
fastapi
uvicorn
pydantic-settings
sqlalchemy
psycopg[binary]
pika
minio
qdrant-client
httpx
python-multipart
```

### Worker 依赖建议

```text
pydantic-settings
sqlalchemy
psycopg[binary]
pika
minio
qdrant-client
httpx
pypdf
pandas
python-docx
```

### 环境变量

```env
APP_ENV=local

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=rag_cleaning
POSTGRES_USER=rag
POSTGRES_PASSWORD=rag

RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=rag
RABBITMQ_PASSWORD=rag
RABBITMQ_QUEUE=cleaning.jobs

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=rag
MINIO_SECRET_KEY=rag_password
MINIO_BUCKET=rag-documents
MINIO_SECURE=false

QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=rag_chunks

EMBEDDING_PROVIDER=mock
EMBEDDING_MODEL=mock-embedding
EMBEDDING_DIMENSION=1024
DASHSCOPE_API_KEY=
EMBEDDING_BASE_URL=
```

### 验收

- API 和 Worker 都从同一套命名规范读取配置。
- 未配置真实模型时，默认走 `mock` embedding。

## 阶段 E3：Docker Compose

### 服务清单

```text
postgres
rabbitmq
minio
qdrant
```

### 验收命令

```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps
```

### 验收标准

- PostgreSQL 端口 `5432` 可访问。
- RabbitMQ 管理端 `15672` 可打开。
- MinIO Console `9001` 可打开。
- Qdrant `6333` 可访问。

## 阶段 E4：数据库初始化

### 表

第一轮创建：

- `data_source`
- `document`
- `document_version`
- `cleaning_job`
- `text_chunk`
- `vector_record`

### 初始化数据

插入默认数据源：

```text
id = default-file-source
name = 默认文件数据源
type = FILE
tenant_id = default
status = ENABLED
```

### 验收

- Docker Compose 启动 PostgreSQL 后自动执行 `init.sql`。
- 可以查询到默认数据源。

## 阶段 E5：Embedding 适配层接口

### 接口设计

统一接口：

```python
class EmbeddingClient:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...
```

Provider：

```text
mock
dashscope
local_bge
```

### Provider 行为

`mock`：

- 根据文本 hash 生成稳定伪向量。
- 用于链路验证，不用于质量评估。

`dashscope`：

- 使用 `DASHSCOPE_API_KEY`。
- 使用 `EMBEDDING_MODEL`，如 `text-embedding-v4`。

`local_bge`：

- 使用 `EMBEDDING_BASE_URL`。
- 约定本地服务提供 OpenAI-compatible 或自定义 `/embeddings` 接口。

### 验收

- 三种 provider 至少 mock 可运行。
- dashscope 和 local_bge 可以在没有密钥/地址时给出清晰错误。

## 阶段 E6：第一轮提交节奏

### Commit 1：工程骨架

内容：

- 目录结构。
- API / Worker 最小启动。
- `.env.example`。

建议提交信息：

```text
feat: initialize python mvp project skeleton
```

### Commit 2：基础设施

内容：

- Docker Compose。
- PostgreSQL init.sql。
- MinIO / RabbitMQ / Qdrant 配置。

建议提交信息：

```text
feat: add local infrastructure for mvp
```

### Commit 3：Embedding 适配层

内容：

- EmbeddingClient。
- mock provider。
- dashscope provider skeleton。
- local_bge provider skeleton。

建议提交信息：

```text
feat: add compatible embedding adapter
```

## 进入编码前的最终确认

请确认：

1. 是否直接按本计划创建工程骨架。
2. 本地是否可以使用 Docker Compose。
3. 首批解析格式是否先做 PDF + CSV。
4. 本地 BGE 服务是否已有地址；如果没有，先保留 `local_bge` 适配骨架。
5. 通义 DashScope Key 是否后续通过 `.env` 注入，不写入仓库。
