# Data Cleaning RAG Load Test Report

- Generated at: 2026-05-18T07:50:17.2132517Z
- Knowledge base: `kb-load-test`
- Upload count: 2
- Search count: 8
- Search concurrency: 2

## Summary

| Metric | Value |
| --- | ---: |
| Upload throughput docs/sec | 0.915 |
| Upload P50 ms | 55.23 |
| Upload P95 ms | 59.24 |
| Search QPS | 1.852 |
| Search P50 ms | 521.23 |
| Search P95 ms | 608.25 |
| Search P99 ms | 608.25 |
| Search failures | 0 |
| Rerank enabled | True |
| Rerank provider | external |
| Rerank degraded count | 0 |
| Avg rerank score count | 2 |

## Recommendation

- PoC baseline: keep concurrency modest and verify P95 latency with customer sample documents.
- Production sizing should rerun this script with larger documents, realistic query mixes, and the selected embedding/rerank provider.
