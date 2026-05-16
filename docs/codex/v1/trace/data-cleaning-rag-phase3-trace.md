# data-cleaning-rag-phase3 追踪审查

## 审查范围

- requirements: `docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md`
- design: `docs/codex/v1/designs/data-cleaning-rag-architecture-design.md`
- phase3 plan: `docs/codex/v1/plans/data-cleaning-rag-phase3-plan.md`
- API contract: `docs/codex/v1/plans/data-cleaning-rag-api-contract.md`
- implementation:
  - `services/api/app/api/documents.py`
  - `services/api/app/services/document_service.py`
  - `services/api/app/services/search_service.py`
  - `services/worker/app/consumers/cleaning_consumer.py`
  - `services/api/migrations/versions/0006_add_document_deleted_at.py`
  - `services/api/migrations/versions/0007_add_document_audit_event.py`
  - `scripts/document-delete-test.ps1`
  - `scripts/document-update-test.ps1`
  - `scripts/document-rebuild-test.ps1`
  - `scripts/document-audit-test.ps1`

## 审查结论

阶段 3 首版已达到“索引生命周期与治理增强”的计划目标：文档删除、文档更新、新旧版本可见性、按文档重建索引和最小操作审计均已闭环。

当前链路可以概括为：

`文档上传/更新 -> 清洗任务 -> INDEXED 版本可见 -> 删除/更新/重建管理入口 -> 搜索回查过滤状态 -> 审计事件留痕`

本轮已验证：

- `python -m compileall services\api\app services\worker\app`：通过。
- `docker compose -f infra\docker-compose.yml config --quiet`：通过。
- `scripts/phase2-eval.ps1`：15 个阶段 2 检索检查全部通过。
- `scripts/document-audit-test.ps1`：版本创建、重建请求、删除三类审计事件可查。
- `scripts/document-rebuild-test.ps1`：重建后仍可检索且版本 ID 不变。
- `scripts/document-update-test.ps1`：新版本成功后旧版本不可检索，新版本可检索。
- `scripts/document-delete-test.ps1`：删除后同一文档不再被检索，重复删除不报错。
- `scripts/permission-test.ps1`：最小权限标签过滤通过。
- `scripts/failure-test.ps1`：错误响应和异步失败路径通过。
- `scripts/smoke-test.ps1`：MVP 主链路回归通过。

## 已对齐项

| 计划项 | 当前实现 | 结论 |
| --- | --- | --- |
| 文档删除后不可检索 | `DELETE /api/v1/documents/{document_id}` 软删除 document/version，并删除 Qdrant points；搜索回查过滤 `DELETED` 状态 | 已对齐 |
| 删除幂等 | 重复删除同一 document 不报错，返回删除状态 | 已对齐首版 |
| 文档更新与新版本可见 | `PUT /api/v1/documents/{document_id}/versions` 创建新 version/job；新版本成功后旧 `INDEXED` 版本标记为 `SUPERSEDED` | 已对齐 |
| 失败新版本不影响旧索引 | 旧版本在新 job 成功前保持可见；切换动作在 Worker 成功后执行 | 已对齐首版 |
| 按 document_id 重建索引 | `POST /api/v1/documents/{document_id}/rebuild` 复用当前 `INDEXED` 版本的 `object_key` 创建重建 job | 已对齐 |
| 重建不创建新版本 | rebuild 消息携带 `rebuild=true`，Worker 对原 version 重新解析、切块、Embedding 和 upsert | 已对齐 |
| 重建后清理旧 chunk/vector | Worker 成功后删除本次未再生成的 stale chunk/vector | 已对齐首版 |
| 最小审计 | 新增 `document_audit_event` 表，记录版本创建、索引重建请求、文档删除 | 已对齐首版 |
| 操作人和来源 | 更新、重建、删除支持 `actor_id` 与 `request_source` 查询参数并写入审计 | 已对齐首版 |
| 审计查询 | `GET /api/v1/documents/{document_id}/audit` 返回文档审计事件列表 | 已对齐 |
| API 文档 | `data-cleaning-rag-api-contract.md` 已补删除、更新、重建和审计接口 | 已对齐 |

## 未完全对齐项

| 需求/设计项 | 当前差异 | 判断 |
| --- | --- | --- |
| 并发更新/删除/重建互斥 | 当前没有 document 级锁或状态机 CAS，多个管理操作并发时可能互相覆盖 | 阶段 3 首版可接受，生产前必须增强 |
| 批量重建 | 当前只支持单文档重建 | 后续治理能力 |
| 失败补偿 | rebuild 失败保留旧索引，但缺少显式人工重试/补偿入口 | 后续运维能力 |
| 审计完整性 | 当前只记录请求类事件，不记录 Worker 成功/失败、搜索访问、权限判定详情 | 最小审计已完成，完整审计未完成 |
| 操作者可信来源 | `actor_id` 和 `request_source` 来自 query 参数，没有接入真实认证鉴权 | 生产前必须接入网关或认证上下文 |
| 删除物理清理 | 当前软删除 PostgreSQL 元数据，删除 Qdrant points，但对象存储原文和 chunk 行仍保留 | 符合可恢复/审计首版策略，后续需定义保留周期 |
| 删除返回计数 | 重复删除时 `deleted_vector_count` 仍按历史 chunk 计数返回，不代表第二次实际删除点数 | 已知表现，需在后续改成 attempted/actual 两类计数 |

## 风险与影响

- 阶段 3 已能支撑演示和基础验收，但还不是生产级生命周期状态机；并发管理操作是下一阶段优先风险。
- 审计目前解决“谁请求了什么操作”的最小问题，尚未解决“系统实际执行结果、权限判断过程、访问行为留痕”的完整审计问题。
- 更新版本切换依赖 Worker 成功后的状态更新，当前自动化覆盖了成功路径；失败路径需要更细的版本保留和可观测性验证。
- 权限标签过滤在本轮回归通过，但仍是最小标签模型，不能替代真实组织、角色、用户授权体系。

## 建议后续动作

1. 阶段 4 优先补 document 级并发控制：更新、删除、重建互斥，避免版本切换和向量清理竞争。
2. 增加人工重试/失败补偿入口：按 job 或 document_version 重试失败清洗任务。
3. 扩展审计事件：记录 Worker 成功/失败、重建完成、删除向量实际数量和操作者认证来源。
4. 规划批量重建和批量删除，明确限流、分页、断点续跑和失败重试策略。
5. 扩大验证集：加入中文语料、权限负例、并发操作、删除后重传和重建失败场景。

## 总结

阶段 3 首版可以标记为“功能闭环完成”：索引生命周期的核心管理动作已经落地，并且没有破坏阶段 2 检索漏斗与 MVP 主链路。

下一步建议进入阶段 4，重点从“功能可用”推进到“生产可控”：并发控制、批量治理、审计可信来源、失败补偿和真实模型质量评测。
