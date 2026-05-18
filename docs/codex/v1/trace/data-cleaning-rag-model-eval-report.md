# Data Cleaning RAG Model Evaluation Report

- Generated at: 2026-05-18T07:49:14.2678665Z
- Documents directory: `samples\documents\demo-zh`
- Query file: `samples\queries\model-eval-queries-zh.json`

## Summary

| Config | Hit rate | MRR | Recall@K | Passed/Total | P50(ms) | P95(ms) | P99(ms) | Rerank degraded | Embedding | Rerank |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| local_bge | 0.5 | 0.4167 | 0.5 | 6/12 | 231.69 | 285.18 | 285.18 | 0 | local_bge/bge-m3 | mock/mock-reranker |
| local_bge_external_rerank | 0.5 | 0.3472 | 0.5 | 6/12 | 480.1 | 708.45 | 708.45 | 0 | local_bge/bge-m3 | external/BAAI/bge-reranker-base |
| dashscope_text_embedding_v4 | 0.75 | 0.4722 | 0.75 | 9/12 | 271.9 | 341.5 | 341.5 | 0 | dashscope/text-embedding-v4 | mock/mock-reranker |

## Notes
- Best config in this sample set: `dashscope_text_embedding_v4` with hit rate `0.75`.
- `mock` is useful as a development fallback, not as a semantic quality baseline.
- `local_bge` is the recommended local demo and offline validation baseline.
- DashScope `text-embedding-v4` is included when `DASHSCOPE_API_KEY` is configured.
- PoC recommendation: use `local_bge/bge-m3 + mock rerank` for offline demo stability; production still needs customer corpus, DashScope quota, and rerank capacity testing.

## Details

### local_bge

#### Category Summary

| Category | Hit rate | MRR | Passed/Total |
| --- | ---: | ---: | ---: |
| 事实问答 | 1 | 1 | 2/2 |
| 操作步骤 | 1 | 0.5 | 2/2 |
| 故障排查 | 0 | 0 | 0/2 |
| 权限隔离 | 1 | 1 | 2/2 |
| 长尾表达 | 0 | 0 | 0/2 |
| 效果调优 | 0 | 0 | 0/2 |

#### Query Details

| Query | Category | Mode | Passed | Rank | RR | Matched keywords | Latency(ms) | Result count | Rerank |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| zh-fact-embedding-provider | 事实问答 | semantic | yes | 1 | 1 | local_bge, bge-m3, 1024 | 261.6 | 5 | mock, scores=5, degraded=False |
| zh-fact-embedding-provider | 事实问答 | hybrid | yes | 1 | 1 | local_bge, bge-m3, 1024 | 243.3 | 5 | mock, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | semantic | yes | 2 | 0.5 | Worker | 231.69 | 5 | mock, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | hybrid | yes | 2 | 0.5 | Worker | 211.95 | 5 | mock, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | semantic | no |  | 0 |  | 232.85 | 5 | mock, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | hybrid | no |  | 0 |  | 247.03 | 5 | mock, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | semantic | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags | 210.67 | 5 | mock, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | hybrid | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags | 239.41 | 5 | mock, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | semantic | no |  | 0 |  | 228.22 | 5 | mock, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | hybrid | no |  | 0 |  | 213.85 | 5 | mock, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | semantic | no |  | 0 |  | 216.47 | 5 | mock, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | hybrid | no |  | 0 |  | 285.18 | 5 | mock, scores=5, degraded=False |

### local_bge_external_rerank

#### Category Summary

| Category | Hit rate | MRR | Passed/Total |
| --- | ---: | ---: | ---: |
| 事实问答 | 1 | 1 | 2/2 |
| 操作步骤 | 1 | 0.3333 | 2/2 |
| 故障排查 | 0 | 0 | 0/2 |
| 权限隔离 | 1 | 0.75 | 2/2 |
| 长尾表达 | 0 | 0 | 0/2 |
| 效果调优 | 0 | 0 | 0/2 |

#### Query Details

| Query | Category | Mode | Passed | Rank | RR | Matched keywords | Latency(ms) | Result count | Rerank |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| zh-fact-embedding-provider | 事实问答 | semantic | yes | 1 | 1 | local_bge, bge-m3, 1024 | 650.74 | 5 | external, scores=5, degraded=False |
| zh-fact-embedding-provider | 事实问答 | hybrid | yes | 1 | 1 | local_bge, bge-m3, 1024 | 609.55 | 5 | external, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | semantic | yes | 3 | 0.3333 | Worker | 502.72 | 5 | external, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | hybrid | yes | 3 | 0.3333 | Worker | 474.46 | 5 | external, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | semantic | no |  | 0 |  | 480.1 | 5 | external, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | hybrid | no |  | 0 |  | 511.97 | 5 | external, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | semantic | yes | 2 | 0.5 | tenant_id, knowledge_base_id, permission_tags | 514.87 | 5 | external, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | hybrid | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags | 708.45 | 5 | external, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | semantic | no |  | 0 |  | 458.6 | 5 | external, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | hybrid | no |  | 0 |  | 451.6 | 5 | external, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | semantic | no |  | 0 |  | 455.62 | 5 | external, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | hybrid | no |  | 0 |  | 457.15 | 5 | external, scores=5, degraded=False |

### dashscope_text_embedding_v4

#### Category Summary

| Category | Hit rate | MRR | Passed/Total |
| --- | ---: | ---: | ---: |
| 事实问答 | 1 | 1 | 2/2 |
| 操作步骤 | 1 | 0.25 | 2/2 |
| 故障排查 | 0.5 | 0.25 | 1/2 |
| 权限隔离 | 1 | 1 | 2/2 |
| 长尾表达 | 1 | 0.3333 | 2/2 |
| 效果调优 | 0 | 0 | 0/2 |

#### Query Details

| Query | Category | Mode | Passed | Rank | RR | Matched keywords | Latency(ms) | Result count | Rerank |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| zh-fact-embedding-provider | 事实问答 | semantic | yes | 1 | 1 | local_bge, bge-m3, 1024 | 315.33 | 5 | mock, scores=5, degraded=False |
| zh-fact-embedding-provider | 事实问答 | hybrid | yes | 1 | 1 | local_bge, bge-m3, 1024 | 306.01 | 5 | mock, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | semantic | yes | 4 | 0.25 | Worker | 280.09 | 5 | mock, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | hybrid | yes | 4 | 0.25 | Worker | 271.9 | 5 | mock, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | semantic | yes | 2 | 0.5 | locks release, rebuild | 265.5 | 5 | mock, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | hybrid | no |  | 0 |  | 341.5 | 5 | mock, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | semantic | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags, permission_context | 258.82 | 5 | mock, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | hybrid | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags, permission_context | 259.6 | 5 | mock, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | semantic | yes | 3 | 0.3333 | RERANK_DEGRADED | 281.46 | 5 | mock, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | hybrid | yes | 3 | 0.3333 | RERANK_DEGRADED | 277.01 | 5 | mock, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | semantic | no |  | 0 |  | 260.49 | 5 | mock, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | hybrid | no |  | 0 |  | 265.37 | 5 | mock, scores=5, degraded=False |
