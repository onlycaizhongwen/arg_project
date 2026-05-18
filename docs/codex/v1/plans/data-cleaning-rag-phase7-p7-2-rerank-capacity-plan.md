# 数据清洗与 RAG 服务 Phase 7 P7-2 正式 rerank 服务接入与容量基线计划

## 1. 目标

把当前 PoC 默认的 `mock rerank` 过渡到可评估、可压测、可降级的正式 rerank 服务接入基线。

本阶段目标：

- 明确 external rerank 的配置、超时、批大小和降级边界。
- 扩展模型评测脚本，支持 local BGE embedding + external rerank 组合。
- 扩展压测脚本，输出 rerank 开启状态、降级次数和检索延迟。
- 形成一份容量基线报告，说明当前环境是否具备启用正式 rerank 的条件。

## 2. 当前基础

已具备：

- API 支持 `RERANK_PROVIDER=disabled|mock|external`。
- `services/reranker` 已提供本地 `BAAI/bge-reranker-base` CrossEncoder 服务。
- `scripts/bge-rerank-test.ps1` 已验证过真实 BGE rerank 链路。
- `scripts/model-eval.ps1` 已输出 MRR、Recall@K、延迟分位和 rerank 分数覆盖。
- `scripts/search-load-test.ps1` 已输出上传吞吐、搜索 QPS 和延迟分位。
- `GET /api/v1/diagnostics/overview` 和 `GET /api/v1/metrics` 已能观察 rerank 降级。

当前缺口：

- `model-eval.ps1` 没有标准 external rerank 配置入口。
- `search-load-test.ps1` 报告未显式记录 rerank provider、rerank score 覆盖和降级数。
- 当前运行环境不保证 reranker 容器和模型缓存长期可用。

## 3. 改动范围

脚本：

- `scripts/model-eval.ps1`
- `scripts/search-load-test.ps1`

文档：

- `docs/codex/v1/plans/data-cleaning-rag-phase7-production-readiness-plan.md`
- `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`
- `docs/codex/v1/trace/data-cleaning-rag-rerank-capacity-report.md`

运行配置：

- `RERANK_PROVIDER=external`
- `RERANK_MODEL=BAAI/bge-reranker-base`
- `RERANK_BASE_URL=http://reranker:8010/rerank`
- `RERANK_TIMEOUT_SECONDS=30`

## 4. 实施步骤

### P7-2-1：扩展模型评测脚本

新增能力：

- 参数化 external rerank：
  - `-IncludeExternalRerank`
  - `-ExternalRerankBaseUrl`
  - `-ExternalRerankModel`
  - `-ExternalRerankTimeoutSeconds`
- 新增配置组合：
  - `local_bge_external_rerank`
- 报告继续输出：
  - hit rate
  - MRR
  - Recall@K
  - P50/P95/P99
  - rerank degraded count
  - rerank score count

完成标准：

- 不传 external 参数时保持现有行为。
- 传 external 参数时可将 API/Worker 切换为 external rerank 组合。

### P7-2-2：扩展压测脚本

新增能力：

- 参数化 rerank：
  - `-RerankEnabled`
  - `-RerankSize`
- 每次搜索记录：
  - `rerank_provider`
  - `rerank_degraded`
  - `rerank_score_count`
- 报告汇总：
  - rerank degraded count
  - average rerank score count
  - rerank enabled/provider/model

完成标准：

- 现有轻量压测仍可跑。
- 报告能区分 mock/external/disabled rerank 状态。

### P7-2-3：执行容量基线验证

推荐命令：

```powershell
docker compose -f infra/docker-compose.yml --profile reranker up -d reranker

$env:EMBEDDING_PROVIDER = "local_bge"
$env:EMBEDDING_MODEL = "bge-m3"
$env:EMBEDDING_DIMENSION = "1024"
$env:EMBEDDING_BASE_URL = "http://host.docker.internal:11434"
$env:RERANK_PROVIDER = "external"
$env:RERANK_MODEL = "BAAI/bge-reranker-base"
$env:RERANK_BASE_URL = "http://reranker:8010/rerank"
$env:RERANK_TIMEOUT_SECONDS = "30"
docker compose -f infra/docker-compose.yml up -d api worker

.\scripts\model-eval.ps1 -DocumentsDir samples\documents\demo-zh -QueriesFile samples\queries\model-eval-queries-zh.json -SkipMock -IncludeExternalRerank
.\scripts\search-load-test.ps1 -UploadCount 2 -SearchCount 8 -Concurrency 2 -RerankEnabled -RerankSize 5
```

完成标准：

- external rerank 可用时，`rerank_degraded=false` 且结果包含 `rerank_score`。
- external rerank 不可用时，报告明确记录阻塞点，API 仍能降级或切回 mock。

## 5. 验证命令

```powershell
python -m compileall services\api\app services\worker\app
docker compose -f infra/docker-compose.yml config --quiet
.\scripts\model-eval.ps1 -DocumentsDir samples\documents\demo-zh -QueriesFile samples\queries\model-eval-queries-zh.json -SkipMock
.\scripts\search-load-test.ps1 -UploadCount 2 -SearchCount 8 -Concurrency 2 -RerankEnabled -RerankSize 5
.\scripts\diagnostics-test.ps1
.\scripts\metrics-test.ps1
git diff --check
```

## 6. 风险与回滚

| 风险 | 影响 | 回滚 |
| --- | --- | --- |
| reranker 镜像或模型拉取失败 | 无法跑 external 基线 | 切回 `RERANK_PROVIDER=mock`，记录环境阻塞 |
| external rerank 延迟过高 | P95/P99 上升 | 降低 `rerank_size` 或关闭 rerank |
| external rerank 不稳定 | 检索降级增加 | 缩短超时并依赖降级返回 |
| reranker 模型缓存体积大 | 部署成本增加 | 使用客户内网模型仓库或预热镜像 |

## 7. 下一步

完成 P7-2 后进入 P7-3 客户真实语料评测包：

1. 定义客户文档目录和查询集模板。
2. 输出脱敏评测报告格式。
3. 给出 Recall@K、MRR、误召回和权限过滤的验收口径。
## 8. 执行状态

2026-05-18 已完成 P7-2 首轮验证：

- `scripts/model-eval.ps1` 已支持 `-IncludeExternalRerank`，可跑 `local_bge + external rerank` 配置。
- `scripts/search-load-test.ps1` 已支持 `-RerankEnabled`、`-RerankSize`，报告可输出 rerank provider、降级次数和平均 rerank 分数覆盖。
- 本地 reranker profile 已启动，`scripts/bge-rerank-test.ps1` 通过，确认 `rerank_provider=external` 且 `rerank_degraded=false`。
- 容量报告已输出到 `docs/codex/v1/trace/data-cleaning-rag-rerank-capacity-report.md`。
- 当前建议：PoC 默认仍使用 `local_bge + mock rerank`；客户测试和准生产再开启 external rerank 做真实容量验证。
