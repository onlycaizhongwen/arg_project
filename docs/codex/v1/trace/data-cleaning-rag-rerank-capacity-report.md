# 数据清洗与 RAG 服务 P7-2 Rerank 容量基线报告

## 1. 结论

P7-2 已完成首轮正式 rerank 服务接入与容量基线验证。

- 本地 `BAAI/bge-reranker-base` reranker 容器可以启动，并通过 `http://localhost:8010/health` 健康检查。
- API 在 `RERANK_PROVIDER=external`、`RERANK_BASE_URL=http://reranker:8010/rerank` 下可以稳定调用真实 BGE rerank。
- `scripts/bge-rerank-test.ps1` 已验证 `rerank_provider=external`、`rerank_degraded=false`，检索结果包含真实 `rerank_score`。
- 轻量压测下 external rerank 无失败、无降级，但 P50/P95 延迟明显高于 mock rerank。
- 当前不建议直接把 external rerank 作为默认 PoC 配置；建议 PoC 继续默认 `local_bge + mock rerank`，客户测试或准生产环境再按容量目标开启 external rerank。

## 2. 验证环境

| 项 | 配置 |
| --- | --- |
| Embedding provider | `local_bge` |
| Embedding model | `bge-m3` |
| Embedding base URL | `http://host.docker.internal:11434` |
| Embedding dimension | `1024` |
| Rerank provider | `external` |
| Rerank model | `BAAI/bge-reranker-base` |
| Rerank URL | `http://reranker:8010/rerank` |
| Rerank timeout | `30s` |
| Compose service | `reranker` profile |

## 3. 验证结果

### 3.1 真实 BGE Rerank 链路

命令：

```powershell
.\scripts\bge-rerank-test.ps1
```

结果：

| 指标 | 结果 |
| --- | ---: |
| result_count | 4 |
| rerank_provider | external |
| rerank_degraded | false |
| rerank_score_count | 4 |
| first_rerank_score | 0.6176 |

### 3.2 模型评估对比

命令：

```powershell
.\scripts\model-eval.ps1 -DocumentsDir samples\documents\demo-zh -QueriesFile samples\queries\model-eval-queries-zh.json -SkipMock -IncludeExternalRerank
```

报告文件：

- `docs/codex/v1/trace/data-cleaning-rag-model-eval-report.md`
- `docs/codex/v1/trace/data-cleaning-rag-model-eval-report.json`

汇总：

| 配置 | Hit rate | MRR | Recall@K | Passed/Total | P50(ms) | P95(ms) | P99(ms) | 降级 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| local_bge + mock rerank | 0.5 | 0.4167 | 0.5 | 6/12 | 231.69 | 285.18 | 285.18 | 0 |
| local_bge + external rerank | 0.5 | 0.3472 | 0.5 | 6/12 | 480.10 | 708.45 | 708.45 | 0 |
| DashScope text-embedding-v4 + mock rerank | 0.75 | 0.4722 | 0.75 | 9/12 | 271.90 | 341.50 | 341.50 | 0 |

说明：

- 在当前样例集上，external rerank 没有带来 hit rate 提升，MRR 反而下降。
- external rerank 的 P95 延迟约为 `708.45ms`，明显高于 `local_bge + mock rerank` 的 `285.18ms`。
- DashScope embedding 在当前样例集上质量更好，但这属于样例集结果，不能直接代表客户真实语料。

### 3.3 轻量容量压测

命令：

```powershell
.\scripts\search-load-test.ps1 -UploadCount 2 -SearchCount 8 -Concurrency 2 -RerankEnabled -RerankSize 5
```

报告文件：

- `docs/codex/v1/trace/data-cleaning-rag-load-test-report.md`
- `docs/codex/v1/trace/data-cleaning-rag-load-test-report.json`

结果：

| 指标 | external rerank |
| --- | ---: |
| upload throughput docs/sec | 0.915 |
| upload P50 ms | 55.23 |
| upload P95 ms | 59.24 |
| search QPS | 1.852 |
| search P50 ms | 521.23 |
| search P95 ms | 608.25 |
| search P99 ms | 608.25 |
| search failures | 0 |
| rerank provider | external |
| rerank degraded count | 0 |
| avg rerank score count | 2 |

补充基线：

- 同规模 mock rerank 曾测得 QPS 约 `1.91`，P50 约 `413.93ms`，P95 约 `500.25ms`。
- 本轮 external rerank 相比 mock rerank 延迟上升，但仍保持 0 失败、0 降级。

## 4. 风险与建议

| 风险 | 影响 | 建议 |
| --- | --- | --- |
| 模型首次下载依赖 Hugging Face 或镜像站 | 容器首次启动可能失败或超时 | 客户环境应预热模型缓存，或改用内网模型仓库 |
| external rerank 延迟高于 mock | 检索 P95/P99 上升 | 测试环境先控制 `rerank_size=5~20`，再逐步扩大 |
| 样例集质量收益不明显 | 启用 rerank 的价值需要重新证明 | P7-3 使用客户真实语料重新评估 |
| reranker CPU 推理能力有限 | 并发提升后可能成为瓶颈 | 生产前补 GPU/多副本/批处理容量测试 |

## 5. 推荐配置

PoC / 离线演示：

```env
EMBEDDING_PROVIDER=local_bge
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSION=1024
EMBEDDING_BASE_URL=http://host.docker.internal:11434
RERANK_PROVIDER=mock
RERANK_MODEL=mock-reranker
```

客户测试 / 准生产验证：

```env
EMBEDDING_PROVIDER=local_bge
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSION=1024
EMBEDDING_BASE_URL=http://host.docker.internal:11434
RERANK_PROVIDER=external
RERANK_MODEL=BAAI/bge-reranker-base
RERANK_BASE_URL=http://reranker:8010/rerank
RERANK_TIMEOUT_SECONDS=30
```

生产建议：

- 不直接沿用本地 CPU reranker 作为生产容量结论。
- 先用客户真实语料完成 P7-3 质量评估，再根据目标 QPS、P95 和候选规模决定是否启用 external rerank。
- 如果使用通义或客户内网兼容 rerank 服务，应复用 `external` provider 契约，只替换 `RERANK_BASE_URL`、模型名和鉴权方式。

## 6. 下一步

进入 P7-3 客户真实语料评测包：

1. 定义客户文档目录和查询集模板。
2. 支持脱敏评测报告。
3. 输出 Recall@K、MRR、权限误召回、无答案样例和 rerank 开关收益对比。
