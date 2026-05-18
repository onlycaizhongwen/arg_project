# 数据清洗与 RAG 服务发布检查清单

## 1. 适用范围

本文用于 PoC、测试环境和准生产环境发布前检查。生产发布必须结合客户变更流程、审批流程、备份策略和回滚窗口执行。

## 2. 发布前冻结项

| 检查项 | PoC | 测试/生产 |
| --- | --- | --- |
| 需求、设计、API 契约已更新 | 必须 | 必须 |
| `.env` 使用分环境模板生成且未入库 | 必须 | 必须 |
| 镜像 tag 明确 | 建议 | 必须 |
| 数据库迁移已在测试库验证 | 建议 | 必须 |
| 备份 dry-run 已执行 | 建议 | 必须 |
| 监控指标和诊断接口可用 | 必须 | 必须 |
| 回滚窗口和负责人确认 | 建议 | 必须 |

## 3. 镜像与版本

建议镜像 tag 格式：

```text
clean-rag-pipeline-api:<app_version>-<git_short_sha>-<yyyymmdd>
clean-rag-pipeline-worker:<app_version>-<git_short_sha>-<yyyymmdd>
clean-rag-pipeline-reranker:<model_name>-<yyyymmdd>
```

发布前记录：

| 项 | 值 |
| --- | --- |
| Git branch | `main` |
| Git commit | 待发布时填写 |
| API image tag | 待发布时填写 |
| Worker image tag | 待发布时填写 |
| Reranker image tag | 如启用则填写 |
| 配置模板 | `.env.test.example` / `.env.prod.example` |

## 4. 发布前命令

```powershell
docker compose -f infra/docker-compose.yml config --quiet
python -m compileall services\api\app services\worker\app
.\scripts\db-migrate.ps1
.\scripts\smoke-test.ps1
.\scripts\diagnostics-test.ps1
.\scripts\metrics-test.ps1
.\scripts\backup-dry-run.ps1
```

模型或检索链路变更时补充：

```powershell
.\scripts\embedding-check.ps1
.\scripts\model-eval.ps1 -DocumentsDir samples\documents\demo-zh -QueriesFile samples\queries\model-eval-queries-zh.json -SkipMock
.\scripts\search-load-test.ps1 -UploadCount 2 -SearchCount 8 -Concurrency 2
```

批量治理、锁治理或文档治理变更时补充：

```powershell
.\scripts\document-operation-lock-test.ps1
.\scripts\document-lock-release-test.ps1
.\scripts\document-batch-rebuild-test.ps1
.\scripts\document-batch-retry-test.ps1
```

## 5. 备份与恢复

### 5.1 PostgreSQL

备份：

```powershell
docker compose -f infra/docker-compose.yml exec -T postgres pg_dump -U rag -d rag_cleaning > backups/rag_cleaning_yyyymmdd_hhmmss.sql
```

恢复演练必须在隔离库执行：

```powershell
docker compose -f infra/docker-compose.yml exec -T postgres createdb -U rag rag_cleaning_restore
Get-Content backups/rag_cleaning_yyyymmdd_hhmmss.sql | docker compose -f infra/docker-compose.yml exec -T postgres psql -U rag -d rag_cleaning_restore
```

生产恢复不允许直接覆盖原库，必须先确认恢复点、停写窗口、影响范围和回滚负责人。

### 5.2 MinIO

PoC 可通过 MinIO 控制台导出 bucket 文件。生产建议使用对象存储原生版本管理、跨区域复制或生命周期备份。

检查命令：

```powershell
docker compose -f infra/docker-compose.yml exec -T minio sh -c "mc alias set local http://localhost:9000 rag rag_password && mc ls local/rag-documents --recursive --summarize"
```

### 5.3 Qdrant

PoC 可通过重新上传或批量重建恢复向量数据。生产建议使用 Qdrant snapshot 或云盘快照。

检查命令：

```powershell
curl.exe -s http://localhost:6333/collections
```

## 6. Alembic 迁移发布原则

- 迁移脚本先在测试库执行。
- 发布前记录当前 `alembic_version`。
- 优先使用向前兼容迁移，例如新增列、新增表、新增索引。
- 删除列、改类型、清理数据必须单独评审。
- 迁移失败时优先停止发布并保留现场，不直接手工改生产表。

检查当前版本：

```powershell
docker compose -f infra/docker-compose.yml exec -T postgres psql -U rag -d rag_cleaning -c "select * from alembic_version;"
```

## 7. 发布步骤

1. 确认发布窗口、负责人和回滚负责人。
2. 执行备份 dry-run 并保存报告。
3. 构建并推送 API/Worker 镜像。
4. 更新环境变量和镜像 tag。
5. 执行 Alembic 迁移。
6. 启动 API/Worker。
7. 执行 smoke、diagnostics、metrics。
8. 观察 15-30 分钟日志、队列积压、失败率和锁滞留指标。
9. 发布记录归档。

## 8. 回滚原则

| 场景 | 回滚动作 |
| --- | --- |
| API 启动失败 | 回滚 API 镜像 tag，保留数据库不动 |
| Worker 大量失败 | 暂停 Worker，保留 API 查询能力，排查失败 job |
| 数据库迁移失败 | 停止发布，保留现场，按迁移脚本和备份恢复方案评审 |
| Embedding/Rerank 不可用 | 切回上一版模型配置或 `mock/disabled` 降级策略 |
| 检索质量明显下降 | 回滚模型配置或 Qdrant collection，必要时批量重建 |

## 9. 发布后验收

| 项 | 命令/入口 | 通过标准 |
| --- | --- | --- |
| API 健康 | `curl http://localhost:8000/health` | `status=ok` |
| 主链路 | `scripts/smoke-test.ps1` | 上传、入库、检索成功 |
| 诊断概览 | `scripts/diagnostics-test.ps1` | 无 critical signal |
| 监控指标 | `scripts/metrics-test.ps1` | 指标可采集 |
| 队列 | RabbitMQ 管理台 | ready 无持续积压 |
| 锁治理 | diagnostics | `stale_count=0` |

## 10. 生产审批边界

以下操作必须生产审批：

- 直接恢复 PostgreSQL 生产库。
- 删除或重建 Qdrant collection。
- 清空 MinIO bucket。
- 修改 Embedding 维度。
- 删除历史审计数据。
- 批量删除或批量重建大规模知识库。

以下操作可在 PoC 环境由项目负责人确认后执行：

- `docker compose down -v` 重置本地环境。
- 使用 mock/local_bge/DashScope 切换模型验证。
- 小规模 `search-load-test` 压测。
- 使用 `document-batch-retry-test` 构造治理验证数据。
