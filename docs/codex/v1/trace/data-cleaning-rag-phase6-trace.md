# data-cleaning-rag-phase6 追踪报告

## 审查范围

- 计划文档：`docs/codex/v1/plans/data-cleaning-rag-phase6-production-hardening-plan.md`
- 部署运维说明：`docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`
- 发布检查清单：`docs/codex/v1/plans/数据清洗与RAG服务发布检查清单.md`
- API 契约：`docs/codex/v1/plans/data-cleaning-rag-api-contract.md`
- 验证报告：
  - `docs/codex/v1/trace/data-cleaning-rag-model-eval-zh-report.md`
  - `docs/codex/v1/trace/data-cleaning-rag-load-test-report.md`
  - `docs/codex/v1/trace/data-cleaning-rag-backup-dry-run-report.md`
- 实现与脚本：
  - `.env.local.example`、`.env.test.example`、`.env.prod.example`
  - `services/api/app/core/request_context.py`
  - `services/api/app/api/metrics.py`
  - `scripts/request-context-test.ps1`
  - `scripts/metrics-test.ps1`
  - `scripts/document-lock-release-test.ps1`
  - `scripts/document-batch-retry-test.ps1`
  - `scripts/model-eval.ps1`
  - `scripts/search-load-test.ps1`
  - `scripts/backup-dry-run.ps1`

## 已对齐项

| Phase 6 项 | 当前实现/产物 | 结论 |
| --- | --- | --- |
| P6-1 环境配置分层 | 已新增本地、测试、生产三份环境模板，并在部署运维说明中补充敏感信息和镜像源策略 | 已对齐 |
| P6-2 认证上下文与操作人注入 | Header 上下文已接入上传、文档治理、job retry、批量重建和检索入口，保留 PoC 参数兼容 | 已对齐首版 |
| P6-3 结构化日志与 trace_id | API middleware 回传 `X-Trace-Id`，错误响应和 MQ 消息携带 trace_id，Worker 输出结构化日志 | 已对齐首版 |
| P6-4 监控指标出口 | `GET /api/v1/metrics` 输出 Prometheus text format，覆盖 job、队列、锁、rerank 降级和 API 请求计数 | 已对齐首版 |
| P6-5 锁超时释放 | `POST /api/v1/documents/{document_id}/locks/release` 支持滞留锁安全释放、运行中 job 保护和审计记录 | 已对齐首版 |
| P6-6 批量治理增强 | 批量失败项重试、批量取消、item 状态过滤和 total_count 已实现 | 已对齐首版 |
| P6-7 评测集与容量压测 | 中文样例、分类查询集、MRR/Recall@K/延迟分位、轻量压测报告已补齐 | 已对齐首版 |
| P6-8 备份恢复与发布流程 | 备份 dry-run、发布检查清单、部署运维发布/回滚说明、`backups/` 忽略规则已补齐 | 已对齐首版 |

## 验证结果

本轮收尾已执行：

| 验证项 | 结果 |
| --- | --- |
| `powershell` 脚本语法检查：`scripts/backup-dry-run.ps1` | 通过 |
| `docker compose -f infra\docker-compose.yml config --quiet` | 通过 |
| `python -m compileall services\api\app services\worker\app` | 通过 |
| `scripts/backup-dry-run.ps1` | 通过，PostgreSQL/MinIO/Qdrant 均为 ok |
| `scripts/diagnostics-test.ps1` | 通过，诊断状态 ok，队列 ready 0，consumer 1，滞留锁 0 |
| `scripts/metrics-test.ps1` | 通过，Prometheus 指标可采集 |
| `scripts/smoke-test.ps1` | 通过，上传、清洗、检索和知识库过滤均成功 |
| `git diff --check` | 仅提示 LF/CRLF 换行转换 warning，无空白错误 |

## 未对齐项

| 项 | 当前差异 | 建议 |
| --- | --- | --- |
| 可信 IAM/SSO | 当前 Header 上下文仍是网关/PoC 兼容方式，不是真实身份系统签发 | Phase 7 接入真实认证网关、JWT 或客户 IAM |
| 生产级备份恢复 | 当前是 dry-run 和文档流程，未在隔离环境执行完整恢复演练 | 在客户测试环境做 PostgreSQL 恢复、MinIO 还原和 Qdrant snapshot 演练 |
| 正式 rerank 容量 | 当前 PoC 推荐仍为 `local_bge/bge-m3 + mock rerank`，真实 rerank 已验证但未纳入生产压测基线 | 用客户真实语料对 DashScope、本地 BGE 和正式 rerank 服务继续压测 |
| 监控接入 | 已有 Prometheus text format，但未接入真实 Prometheus/Grafana/告警平台 | 在部署环境接入采集任务和告警规则 |
| 发布自动化 | 已有检查清单，尚未形成 CI/CD pipeline | Phase 7 补构建、推镜像、迁移、冒烟、回滚的流水线 |

## 风险与影响

- `backups/` 已加入 `.gitignore`，但本地已生成 SQL 备份文件，发布或提交前仍需确认不会被强制加入 Git。
- 备份 dry-run 不会验证“恢复后业务可用”，只能证明导出和组件检查可执行。
- Header 上下文可用于联调和网关透传，但不能直接等价为生产权限模型。
- Phase 6 已显著提升可交付性，但正式生产仍需要客户环境的审批、监控平台、备份平台和真实模型容量数据。

## 总结结论

Phase 6 P6-1 到 P6-8 已完成首版闭环。当前工程已经具备测试/准生产交付基线：分环境配置、请求上下文、trace_id 串联、指标出口、锁治理、批量治理、中文评测/压测、备份 dry-run 和发布检查清单均已落地并完成本地验证。

下一步建议进入 Phase 7：围绕真实 IAM/SSO、正式 rerank 服务容量压测、客户真实语料评测、生产备份恢复演练和 CI/CD 发布流水线继续推进。
