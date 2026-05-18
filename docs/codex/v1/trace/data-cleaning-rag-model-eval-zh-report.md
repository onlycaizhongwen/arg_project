# Data Cleaning RAG Model Evaluation Report

- Generated at: 2026-05-18T06:58:30.9639203Z
- Documents directory: `samples\documents\demo-zh`
- Query file: `samples\queries\model-eval-queries-zh.json`

## Summary

| Config | Hit rate | MRR | Recall@K | Passed/Total | P50(ms) | P95(ms) | P99(ms) | Rerank degraded | Embedding | Rerank |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| local_bge | 0.5 | 0.4167 | 0.5 | 6/12 | 210.56 | 253.12 | 253.12 | 0 | local_bge/bge-m3 | mock/mock-reranker |
| dashscope_text_embedding_v4 | 0.75 | 0.4722 | 0.75 | 9/12 | 277 | 379.93 | 379.93 | 0 | dashscope/text-embedding-v4 | mock/mock-reranker |

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
| zh-fact-embedding-provider | 事实问答 | semantic | yes | 1 | 1 | local_bge, bge-m3, 1024 | 253.12 | 5 | mock, scores=5, degraded=False |
| zh-fact-embedding-provider | 事实问答 | hybrid | yes | 1 | 1 | local_bge, bge-m3, 1024 | 230 | 5 | mock, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | semantic | yes | 2 | 0.5 | Worker | 207.5 | 5 | mock, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | hybrid | yes | 2 | 0.5 | Worker | 206.34 | 5 | mock, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | semantic | no |  | 0 |  | 213.8 | 5 | mock, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | hybrid | no |  | 0 |  | 226.08 | 5 | mock, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | semantic | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags | 210.56 | 5 | mock, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | hybrid | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags | 225.33 | 5 | mock, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | semantic | no |  | 0 |  | 208.05 | 5 | mock, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | hybrid | no |  | 0 |  | 208.95 | 5 | mock, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | semantic | no |  | 0 |  | 204.72 | 5 | mock, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | hybrid | no |  | 0 |  | 216.04 | 5 | mock, scores=5, degraded=False |

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
| zh-fact-embedding-provider | 事实问答 | semantic | yes | 1 | 1 | local_bge, bge-m3, 1024 | 379.93 | 5 | mock, scores=5, degraded=False |
| zh-fact-embedding-provider | 事实问答 | hybrid | yes | 1 | 1 | local_bge, bge-m3, 1024 | 304.52 | 5 | mock, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | semantic | yes | 4 | 0.25 | Worker | 295.95 | 5 | mock, scores=5, degraded=False |
| zh-ops-upload-not-searchable | 操作步骤 | hybrid | yes | 4 | 0.25 | Worker | 266.97 | 5 | mock, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | semantic | yes | 2 | 0.5 | locks release, rebuild | 257.53 | 5 | mock, scores=5, degraded=False |
| zh-trouble-stale-lock | 故障排查 | hybrid | no |  | 0 |  | 303 | 5 | mock, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | semantic | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags, permission_context | 261.8 | 5 | mock, scores=5, degraded=False |
| zh-permission-isolation | 权限隔离 | hybrid | yes | 1 | 1 | tenant_id, knowledge_base_id, permission_tags, permission_context | 248.29 | 5 | mock, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | semantic | yes | 3 | 0.3333 | RERANK_DEGRADED | 279.45 | 5 | mock, scores=5, degraded=False |
| zh-longtail-rerank-degrade | 长尾表达 | hybrid | yes | 3 | 0.3333 | RERANK_DEGRADED | 277 | 5 | mock, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | semantic | no |  | 0 |  | 260.34 | 5 | mock, scores=5, degraded=False |
| zh-tuning-latency | 效果调优 | hybrid | no |  | 0 |  | 293.17 | 5 | mock, scores=5, degraded=False |
