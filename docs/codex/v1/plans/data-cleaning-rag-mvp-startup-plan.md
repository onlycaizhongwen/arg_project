# 数据清洗与 RAG 服务 MVP 开工计划

## 目标

将当前规划推进到可进入编码的状态，先完成 MVP 工程初始化前的落地清单。本文档定义工程目录、依赖服务、初始化脚本、开发顺序和第一轮验收命令。

## 已确认决策

| 决策项 | 结论 |
| --- | --- |
| 技术栈 | Python |
| API 控制面 | FastAPI |
| 后台处理 | Python Worker |
| 异步队列 | RabbitMQ |
| 元数据库 | PostgreSQL |
| 对象存储 | MinIO |
| 向量库 | Qdrant |
| Embedding 模型 | 通义/阿里云百炼，默认 `text-embedding-v4` |
| MVP 检索能力 | 语义召回 + 基础粗排/候选截断 |
| 暂不实现 | Cross-Encoder 精排、去重打散、多源同步、复杂 OCR、完整后台管理 |

## 推荐工程目录

```text
.
├── services/
│   ├── api/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── api/
│   │   │   │   ├── ingestion.py
│   │   │   │   ├── jobs.py
│   │   │   │   └── search.py
│   │   │   ├── core/
│   │   │   │   ├── config.py
│   │   │   │   └── logging.py
│   │   │   ├── db/
│   │   │   │   ├── session.py
│   │   │   │   └── models.py
│   │   │   ├── infra/
│   │   │   │   ├── object_store.py
│   │   │   │   ├── mq.py
│   │   │   │   └── vector_store.py
│   │   │   └── services/
│   │   │       ├── ingestion_service.py
│   │   │       ├── job_service.py
│   │   │       └── search_service.py
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── worker/
│       ├── app/
│       │   ├── main.py
│       │   ├── consumers/
│       │   │   └── cleaning_consumer.py
│       │   ├── parsers/
│       │   │   ├── base.py
│       │   │   ├── pdf_parser.py
│       │   │   ├── docx_parser.py
│       │   │   └── csv_parser.py
│       │   ├── cleaners/
│       │   │   └── basic_cleaner.py
│       │   ├── chunkers/
│       │   │   └── paragraph_chunker.py
│       │   ├── embeddings/
│       │   │   └── embedding_client.py
│       │   └── vectorstores/
│       │       └── qdrant_client.py
│       ├── pyproject.toml
│       └── Dockerfile
├── infra/
│   ├── docker-compose.yml
│   ├── db/
│   │   └── init.sql
│   └── minio/
│       └── README.md
├── samples/
│   ├── documents/
│   └── queries/
├── docs/
└── .env.example
```

## 第一批依赖服务

### PostgreSQL

用途：

- 存储文档元数据。
- 存储任务状态。
- 存储 chunk 文本和 vector_record 映射。

建议端口：

- `5432`

### RabbitMQ

用途：

- 接收清洗任务。
- Worker 消费任务。

建议端口：

- `5672`
- 管理端：`15672`

### MinIO

用途：

- 保存原始文件。
- 后续可保存解析中间产物。

建议端口：

- API：`9000`
- Console：`9001`

### Qdrant

用途：

- 存储文本 chunk 向量。
- 支持按知识库、文档、版本等 metadata 过滤。

建议端口：

- `6333`

## MVP 数据库初始化表

第一轮只建 6 张表：

1. `data_source`
2. `document`
3. `document_version`
4. `cleaning_job`
5. `text_chunk`
6. `vector_record`

后续可以再补：

- `knowledge_base`
- `cleaning_stage_log`
- `search_log`
- `model_config`
- `index_version`

## API 第一轮接口

### 健康检查

`GET /health`

验收：

- API 服务启动后返回 `ok`。

### 文件上传

`POST /api/v1/ingestions/files`

验收：

- 文件保存到 MinIO。
- PostgreSQL 中生成 document、document_version、cleaning_job。
- RabbitMQ 中产生清洗任务。
- 返回 `job_id`。

### 查询任务

`GET /api/v1/jobs/{job_id}`

验收：

- 可查看 `status`、`current_stage`、`error_message`。

### 语义检索

`POST /api/v1/rag/search`

验收：

- 输入 query。
- 返回 top_k 片段。
- 每个结果包含 `document_id`、`chunk_id`、`score`、`metadata`。

## Worker 第一轮能力

### 文件解析

首批建议：

- PDF
- DOCX
- CSV

若时间紧，第一轮可先做：

- PDF
- CSV

### 清洗

第一轮只做基础清洗：

- 空内容过滤。
- 换行和空白标准化。
- 编码异常兜底。
- 简单重复空白压缩。

### 切分

第一轮策略：

- 按段落切分。
- 超长段落按字符长度切分。
- 保留 `chunk_no`、`source_page`、`section` 等 metadata 扩展位。

### Embedding

第一轮要求：

- 使用统一 `EmbeddingClient` 接口。
- 默认接入通义/阿里云百炼 Embedding 服务。
- 默认模型使用 `text-embedding-v4`，配置化支持降级到 `text-embedding-v3`。
- 通过环境变量 `DASHSCOPE_API_KEY` 管理调用密钥。
- 通过环境变量 `EMBEDDING_PROVIDER=dashscope`、`EMBEDDING_MODEL=text-embedding-v4` 管理模型选择。
- 不把具体模型调用散落在业务代码中。

### 向量写入

第一轮要求：

- 写入 Qdrant collection。
- payload 中保留 `document_id`、`document_version_id`、`chunk_id`、`tenant_id`、`knowledge_base_id`。

## 开发顺序

### D1：工程骨架

产物：

- `services/api`
- `services/worker`
- `infra/docker-compose.yml`
- `.env.example`
- `GET /health`

验收：

- API 服务可启动。
- Worker 可启动。
- 依赖容器可启动。

### D2：数据库与元数据

产物：

- `infra/db/init.sql`
- SQLAlchemy models 或等价 ORM 模型。
- data_source 默认初始化。

验收：

- 数据库表创建成功。
- API 可连接数据库。

### D3：文件上传与任务投递

产物：

- 上传接口。
- MinIO 客户端。
- RabbitMQ producer。
- cleaning_job 创建逻辑。

验收：

- 上传文件后返回 job_id。
- 文件可在 MinIO 查到。
- RabbitMQ 中可看到任务消息。

### D4：Worker 消费与解析

产物：

- RabbitMQ consumer。
- PDF/CSV 解析器。
- 基础 cleaner。
- 状态回写。

验收：

- Worker 消费任务后状态从 PENDING 到 RUNNING。
- 成功解析后写入 text_chunk。
- 失败能写入 error_message。

### D5：Embedding 与向量入库

产物：

- EmbeddingClient。
- DashScope / 通义 Embedding 适配实现。
- QdrantClient。
- vector_record 写入。

验收：

- 可通过 `DASHSCOPE_API_KEY` 调用通义 Embedding。
- text_chunk 有对应向量。
- Qdrant 可按 query vector 召回。

### D6：检索 API

产物：

- `/api/v1/rag/search`
- recall_size、pre_rank_size、top_k 参数。
- 基础粗排/候选截断。
- 元数据补全。

验收：

- 输入问题可返回来源片段。
- 不调用 Cross-Encoder。
- 不直接暴露大候选集。

### D7：Demo 和验收

产物：

- 3 份样例文档。
- 5 到 10 个查询问题。
- Demo 操作文档。

验收：

- 可以完整演示上传、处理、检索。
- 失败场景可定位。

## 第一轮命令草案

```bash
docker compose -f infra/docker-compose.yml up -d
```

```bash
cd services/api
uvicorn app.main:app --reload --port 8000
```

```bash
cd services/worker
python -m app.main
```

## 风险与约束

- 如果本地不能使用 Docker，需要把 PostgreSQL、RabbitMQ、MinIO、Qdrant 改成外部连接配置。
- 如果通义 Embedding 暂时不可用，保留 mock embedding 作为开发兜底，只验证链路，不评估检索质量。
- 如果 PDF 解析质量不稳定，先将解析器接口固定，后续替换具体实现。
- 如果 Qdrant 不可部署，可临时替换为 pgvector，但接口层保持 `VectorStore` 抽象。

## 下一步建议

建议下一轮直接进入工程初始化，顺序是：

1. 创建目录结构。
2. 编写 `infra/docker-compose.yml`。
3. 编写 `.env.example`，包含 `DASHSCOPE_API_KEY`、`EMBEDDING_PROVIDER`、`EMBEDDING_MODEL`。
4. 编写 `infra/db/init.sql`。
5. 创建 FastAPI 与 Worker 最小启动文件。
6. 验证 `GET /health`。
