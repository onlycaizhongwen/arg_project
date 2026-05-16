# 数据清洗与 RAG 服务阶段 3 实施计划

## 目标

阶段 3 聚焦“索引生命周期与治理增强”。阶段 2 已证明检索漏斗可用，但生产系统还必须处理文档更新、删除、重建索引、版本可见性和治理审计。

阶段 3 首版目标：

- 文档删除后不可再被检索召回。
- 文档版本、chunk、vector 的可见性有明确状态。
- 索引重建不会暴露半完成版本。
- 后续可以平滑扩展到文档更新、批量重建和真实权限审计。

## P3-1：文档删除与不可见过滤

改动范围：

- API 新增文档管理入口。
- PostgreSQL 增加 `deleted_at` 字段。
- 删除时标记 document/document_version 为 `DELETED`。
- 删除 Qdrant 中对应 chunk 向量。
- 搜索回查时过滤已删除文档。
- 增加删除验证脚本。

验收：

- 上传文档后可检索。
- 调用删除接口后同一 query 不再返回该文档。
- 重复删除具备幂等性。

## P3-2：文档更新与新版本可见性

首版策略：

- 更新文件时创建新的 document_version。
- 新版本清洗成功后切换当前可见版本。
- 旧版本保留但默认不可见。
- 失败的新版本不影响旧版本检索。

当前执行记录：

- 2026-05-16：完成 P3-2 首版：新增 `PUT /api/v1/documents/{document_id}/versions`；新版本成功后旧 `INDEXED` 版本标记为 `SUPERSEDED`，检索仅返回 `INDEXED` 版本；新增 `scripts/document-update-test.ps1`，并通过阶段 2/MVP/删除/权限/异常/重排降级回归。

## P3-3：索引重建

首版策略：

- 支持按 document_id 重建。
- 重建时复用原始对象存储文件。
- 重建成功后覆盖 chunk/vector。
- 重建失败时保留旧索引。

当前执行记录：

- 2026-05-16：完成 P3-3 首版：新增 `POST /api/v1/documents/{document_id}/rebuild`；重建复用当前 `INDEXED` 版本的 `object_key`，创建新的清洗 job，不创建新版本；Worker 支持 `rebuild=true` 消息，重新解析/切块/Embedding/upsert 向量，并在成功后清理本次未再生成的旧 chunk/vector；新增 `scripts/document-rebuild-test.ps1`，并通过更新、删除、阶段 2 与 smoke 回归。

## P3-4：治理与审计增强

首版策略：

- 记录删除、更新、重建操作审计。
- 检索返回可追溯 document_id、document_version_id、chunk_id。
- 后续接入用户/角色/组织权限上下文。

当前执行记录：

- 2026-05-16：完成 P3-4 最小审计首版：新增 `document_audit_event` 表和 `0007_audit_event` 迁移；`PUT /documents/{id}/versions`、`POST /documents/{id}/rebuild`、`DELETE /documents/{id}` 支持 `actor_id` 与 `request_source` 并写入审计；新增 `GET /documents/{id}/audit` 和 `scripts/document-audit-test.ps1`，验证版本创建、重建请求、删除三类审计事件可查。

## 当前立即执行

下一步建议做阶段 3 trace 审查：

1. 对照阶段 3 计划检查 P3-1 到 P3-4 是否闭环。
2. 明确索引生命周期剩余风险：并发重建、批量重建、失败补偿和审计完整性。
3. 更新 `docs/codex/v1/trace/` 阶段 3 审查文档。
