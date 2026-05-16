# 数据清洗与 RAG 服务阶段 2 实施计划

## 目标

在 MVP 已收口的基础上，进入“混合检索与质量增强”阶段。阶段 2 的目标不是推翻 MVP，而是在现有 FastAPI + Python Worker + PostgreSQL + Qdrant + RabbitMQ + MinIO 架构上补齐检索漏斗：

`语义召回 + 关键词召回 -> 合并粗排 -> 业务干预去重/打散 -> 可选精排/降级 -> 可追溯返回`

阶段 2 完成后，需要能证明：

- 检索不再只依赖语义向量召回。
- 候选规模被明确控制，不会把大候选直接送给重排模型。
- 去重、打散、权限过滤有最小可用实现。
- 重排服务不可用时可以降级返回。
- 检索质量有可重复评测脚本。

## 当前前提

已完成：

- MVP 主链路。
- 本地 BGE `bge-m3` 验证。
- 知识库过滤。
- Demo 样例和最小检索质量验证。
- API 契约文档。
- 异常场景验证。

待外部确认：

- 线上通义 `DASHSCOPE_API_KEY` 是否可用于阶段 2 质量验证。
- 是否已有企业标准关键词检索组件，例如 Elasticsearch/OpenSearch。
- 是否已有重排模型服务；如果没有，阶段 2 先实现兼容接口和 mock reranker。
- 权限模型先做到租户 + 知识库 + 文档权限标签，还是需要段落级权限。

## 技术选型

### 关键词检索

阶段 2 首版建议使用 PostgreSQL 全文检索，不新增 ES/OpenSearch 依赖。

原因：

- 当前 MVP 已依赖 PostgreSQL，部署成本低。
- Demo 和中小规模验证足够。
- 后续可把 `KeywordRetriever` 替换为 ES/OpenSearch，不影响搜索编排层。

首版方案：

- 在 `text_chunk` 上增加 `search_vector` 或使用表达式索引。
- 对 `content` 做 `to_tsvector('simple', content)`。
- 使用 `plainto_tsquery('simple', query)` 检索。
- 返回 `keyword_score` 和 `recall_source=keyword`。

### 混合召回

首版采用 RRF 或归一化加权融合。

推荐先做 RRF：

- 对语义召回和关键词召回分别得到 rank。
- `rrf_score = 1 / (k + rank)`，默认 `k=60`。
- 同一 `chunk_id` 合并来源和分数。

原因：

- 不依赖不同分数体系的绝对值可比。
- 对小样本稳定。
- 便于解释和调参。

### 业务干预

首版做轻量规则，不引入复杂模型：

- 去重：内容规范化后 hash + 简单相似度阈值。
- 文档限额：同一 `document_version_id` 最多返回 N 条。
- 打散：MMR 简化版，兼顾 query 相似分和候选之间相似度。
- 过滤：租户、知识库、权限标签、禁用文档状态。

### 精排

阶段 2 首版实现兼容接口和降级机制：

- `RerankClient` 抽象。
- `mock` provider：按粗排分返回，用于链路验证。
- `external` provider：预留 HTTP 调用。
- 超时或失败时返回业务干预后的结果，并在 `search_plan` 标记 `rerank_degraded=true`。

如后续确认通义或本地重排模型，再接真实 provider。

## 实施步骤

### P2-1：搜索请求与响应契约升级

改动范围：

- `services/api/app/api/search.py`
- `services/api/app/services/search_service.py`
- `docs/codex/v1/plans/data-cleaning-rag-api-contract.md`

内容：

- 请求新增 `search_mode`: `semantic`、`keyword`、`hybrid`，默认 `hybrid`。
- 请求新增 `rerank_enabled`、`rerank_size`。
- 请求新增 `dedup_enabled`、`diversity_enabled`。
- 响应 `items[]` 增加：
  - `recall_sources`
  - `semantic_score`
  - `keyword_score`
  - `pre_rank_score`
  - `rerank_score`
- 响应 `search_plan` 增加：
  - `search_mode`
  - `semantic_recall_count`
  - `keyword_recall_count`
  - `merged_count`
  - `business_filtered_count`
  - `rerank_size`
  - `rerank_degraded`

验收：

- 老请求仍兼容。
- `search_mode=semantic` 行为等价 MVP。
- 响应能解释每一层候选数量。

### P2-2：关键词召回最小实现

改动范围：

- `services/api/migrations`
- `services/api/app/services/search_service.py`
- 可新增 `services/api/app/search/keyword_retriever.py`

内容：

- 增加 PostgreSQL 全文索引。
- 实现关键词召回函数。
- 支持 tenant + knowledge_base 过滤。
- 返回 `chunk_id`、`keyword_score`、`rank`。

验收：

- `search_mode=keyword` 可返回包含关键词的 chunk。
- `search_mode=keyword` 下错误知识库返回 0 条。
- 新增脚本或扩展 `demo-eval.ps1` 验证关键词召回。

### P2-3：混合召回与粗排

改动范围：

- `services/api/app/services/search_service.py`
- 可新增 `services/api/app/search/hybrid_ranker.py`

内容：

- 并行或顺序执行语义召回和关键词召回。
- 用 RRF 合并同一 chunk。
- 输出 `pre_rank_score`。
- 用 `pre_rank_size` 截断候选。

验收：

- `search_mode=hybrid` 同时返回 semantic/keyword 来源。
- 同一 chunk 多路召回时只返回一次。
- `pre_rank_size` 生效。

### P2-4：业务干预

改动范围：

- 可新增 `services/api/app/search/business_rules.py`
- `services/api/app/services/search_service.py`

内容：

- 去重：对规范化 content 做 hash，重复内容只保留高分项。
- 文档限额：默认同一文档版本最多 2 条。
- 打散：MMR 简化版。
- 权限过滤：先预留 `permission_tags` 请求字段与 payload 字段。

验收：

- 重复内容不会挤满 top_k。
- 同一文档版本不会垄断结果。
- 打散后结果覆盖不同文档或不同主题。

### P2-5：重排接口与降级

改动范围：

- 可新增 `services/api/app/rerank/rerank_client.py`
- `services/api/app/core/config.py`
- `services/api/app/services/search_service.py`
- `.env.example`
- `infra/docker-compose.yml`

内容：

- 新增配置：
  - `RERANK_PROVIDER=mock|external|disabled`
  - `RERANK_MODEL`
  - `RERANK_BASE_URL`
  - `RERANK_TIMEOUT_SECONDS`
- `rerank_enabled=true` 时仅对 `rerank_size` 候选调用 reranker。
- 调用失败或超时时降级，返回未精排结果。

验收：

- `RERANK_PROVIDER=mock` 时链路可跑通。
- `RERANK_BASE_URL` 不可用时接口不失败，`rerank_degraded=true`。
- 不超过 `rerank_size` 候选进入 rerank。

### P2-6：权限与治理字段最小增强

改动范围：

- 数据库迁移。
- 上传接口。
- Worker payload。
- Qdrant payload。
- Search filter。

内容：

- document/text_chunk 增加 `permission_tags` JSONB 或 TEXT[]。
- 上传接口可传 `permission_tags`。
- 检索接口可传 `permission_context`。
- MVP 阶段先做标签交集过滤。

验收：

- 不带权限上下文时只返回公开或默认标签内容。
- 带权限上下文时可返回匹配标签内容。
- 错误权限标签不会越权返回。

### P2-7：评测脚本升级

改动范围：

- `samples/queries`
- `scripts/demo-eval.ps1`
- 可新增 `scripts/phase2-eval.ps1`

内容：

- 查询集增加 `expected_recall_sources`。
- 记录 semantic、keyword、hybrid 三种模式结果。
- 输出命中率、平均结果数、来源覆盖情况。

验收：

- 能比较 semantic 与 hybrid 的结果差异。
- 能证明 hybrid 至少在指定样例上不弱于 semantic。

## 推荐执行顺序

1. P2-1 搜索契约升级。
2. P2-2 PostgreSQL 关键词召回。
3. P2-3 RRF 混合召回和粗排。
4. P2-7 评测脚本升级第一版。
5. P2-4 业务干预。
6. P2-5 重排接口与降级。
7. P2-6 权限治理字段。
8. 最后一轮 trace 审查。

这样排序的原因：

- 先把接口契约定住，避免后续每加一层都改响应结构。
- 先做关键词召回和混合合并，阶段 2 的价值最早可见。
- 业务干预依赖合并后的候选集。
- 重排必须放在候选压缩之后。
- 权限治理字段影响数据模型，等检索主流程稳定后再收口更稳。

## 验证方式

每个子阶段至少执行：

```powershell
& 'C:\Program Files\Python312\python.exe' -m compileall services\api\app services\worker\app
docker compose -f infra\docker-compose.yml config --quiet
.\scripts\db-migrate.ps1
.\scripts\smoke-test.ps1
.\scripts\demo-eval.ps1
.\scripts\failure-test.ps1
```

阶段 2 完成后新增：

```powershell
.\scripts\phase2-eval.ps1
```

## 风险与回滚

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| PostgreSQL 全文检索中文效果有限 | 中文查询关键词召回弱 | 阶段 2 先验证英文/术语样例；后续切 ES/OpenSearch 或分词插件 |
| 混合分数不可比 | 排序不稳定 | 首版用 RRF，避免直接混合绝对分 |
| 去重/打散误杀 | 相关结果被过滤 | 保留开关 `dedup_enabled`、`diversity_enabled` |
| 重排服务不稳定 | 检索延迟或失败 | 设置超时和降级，默认可关闭 |
| 权限过滤遗漏 | 越权风险 | Qdrant filter + PostgreSQL 回查双层过滤 |

## 检查点

- CP2-1：关键词召回完成后，确认是否继续使用 PostgreSQL，还是切 ES/OpenSearch。
- CP2-2：混合召回完成后，确认 RRF 参数和响应字段。
- CP2-3：业务干预完成后，确认去重/打散默认是否开启。
- CP2-4：重排接口完成后，确认真实 rerank provider。
- CP2-5：阶段 2 trace 审查后，决定是否进入阶段 3 多源接入与资产治理。

## 本轮建议立即开始的任务

建议先实现 P2-1 和 P2-2：

1. 升级搜索请求/响应契约。
2. 新增 PostgreSQL 关键词召回。
3. 保持 `search_mode=semantic` 兼容当前 MVP 行为。
4. 用现有 demo 文档扩展评测，先证明 `keyword` 和 `hybrid` 模式可用。

## 当前执行记录

- 2026-05-16：完成 P2-1/P2-2 首版实现：搜索请求新增 `search_mode`，响应增加召回来源、语义分、关键词分、粗排分和候选计数；新增 PostgreSQL `to_tsvector('simple', content)` GIN 索引；实现 `semantic`、`keyword`、`hybrid` 三种搜索模式；新增 `scripts/phase2-eval.ps1`。
- 2026-05-16：完成 P2-3/P2-4 首版实现：在 `pre_rank_size` 后增加业务干预层，支持内容去重、同文档版本最多返回 2 条、MMR 简化打散，并在 `search_plan` 输出去重和限额计数；`scripts/phase2-eval.ps1`、`scripts/smoke-test.ps1`、`scripts/demo-eval.ps1`、`scripts/failure-test.ps1` 均通过。
- 2026-05-16：完成 P2-5 首版实现：新增 `RerankClient` 抽象和 `disabled/mock/external` provider，搜索请求支持 `rerank_enabled` 与 `rerank_size`；重排失败时保留业务干预结果并标记 `rerank_degraded=true`；新增 `scripts/rerank-degrade-test.ps1`。
- 2026-05-16：完成 P2-6 权限治理字段实现：上传接口新增 `permission_tags`，检索请求新增 `permission_context`，PostgreSQL 和 Qdrant 均按标签交集过滤；新增 `0005_permission_tags` 迁移和 `scripts/permission-test.ps1`，权限验证与阶段 2/MVP 回归均通过。
- 2026-05-16：补充真实本地 BGE 重排验证：新增可选 `services/reranker` 服务和 `scripts/bge-rerank-test.ps1`；使用 Ollama `bge-m3` 做 embedding、`BAAI/bge-reranker-base` 做 external rerank，验证 `rerank_provider=external`、`rerank_degraded=false` 且结果包含 `rerank_score`。
