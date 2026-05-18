# data-cleaning-rag-phase7-auth 追踪报告

## 审查范围

- 设计文档：`docs/codex/v1/designs/data-cleaning-rag-phase7-auth-design.md`
- 计划文档：`docs/codex/v1/plans/data-cleaning-rag-phase7-p7-1-auth-plan.md`
- 实现文件：
  - `services/api/app/core/config.py`
  - `services/api/app/core/request_context.py`
  - `services/api/app/core/errors.py`
  - `services/api/app/main.py`
  - `infra/docker-compose.yml`
  - `.env.local.example`
  - `.env.test.example`
  - `.env.prod.example`
- 文档：
  - `docs/codex/v1/plans/data-cleaning-rag-api-contract.md`
  - `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`
  - `docs/codex/v1/plans/数据清洗与RAG服务问题排查手册.md`

## 已对齐项

| 设计/计划项 | 当前实现 | 结论 |
| --- | --- | --- |
| local/gateway/iam 三种模式 | 新增 `AUTH_CONTEXT_MODE=local|gateway|iam` | 已对齐 |
| PoC 兼容 | local 默认不强制 actor/tenant，现有 smoke/request/permission 脚本可跑 | 已对齐 |
| 生产身份强制校验 | gateway/iam 下可通过 `AUTH_REQUIRE_ACTOR`、`AUTH_REQUIRE_TENANT` 强制校验 | 已对齐 |
| 可信 Header 开关 | 新增 `AUTH_TRUSTED_HEADER_ENABLED` | 已对齐 |
| 默认请求来源 | 新增 `AUTH_DEFAULT_REQUEST_SOURCE`，gateway/iam 可兜底 source | 已对齐 |
| 权限标签兜底 | 新增 `AUTH_DEFAULT_PERMISSION_TAGS`、`AUTH_EMPTY_PERMISSION_POLICY` | 已对齐 |
| 认证错误码 | 新增 `AUTH_CONTEXT_MISSING`、`AUTH_CONTEXT_FORBIDDEN` 的处理路径 | 已对齐首版 |
| Compose 配置透传 | API 服务环境变量已接入认证配置 | 已对齐 |
| 文档同步 | API 契约、部署运维说明、问题排查手册已补充认证上下文说明 | 已对齐 |

## 验证结果

已执行：

| 验证项 | 结果 |
| --- | --- |
| `python -m compileall services\api\app services\worker\app` | 通过 |
| `docker compose -f infra\docker-compose.yml config --quiet` | 通过 |
| `docker compose -f infra\docker-compose.yml build api` | 通过 |
| `docker compose -f infra\docker-compose.yml up -d api` | 通过 |
| `scripts/request-context-test.ps1` | 通过 |
| `scripts/permission-test.ps1` | 通过 |
| `scripts/smoke-test.ps1` | 通过 |
| `scripts/diagnostics-test.ps1` | 通过 |
| `scripts/metrics-test.ps1` | 通过 |
| gateway 模式缺少 actor/tenant 的 one-off 容器验证 | 返回 `AUTH_CONTEXT_MISSING` |
| gateway 模式完整 Header 的 one-off 容器验证 | 可解析 tenant、actor、source、permission tags |
| `git diff --check` | 仅 LF/CRLF warning，无空白错误 |

## 未对齐项

| 项 | 当前差异 | 建议 |
| --- | --- | --- |
| 真实 IAM/JWT 校验 | 当前仍采用“可信网关注入 Header，API 校验上下文字段”的模式 | 后续与客户 IAM/SSO 对接时补 JWT 或网关签名校验 |
| 权限策略引擎 | 当前仍是标签交集，不是完整 RBAC/ABAC | 后续根据客户组织、角色、知识库授权模型增强 |
| 自动化 gateway 模式端到端脚本 | 已做 one-off 容器验证，尚未新增完整切换/恢复脚本 | 后续可新增独立 `auth-context-mode-test.ps1` |

## 风险与影响

- 默认 `AUTH_CONTEXT_MODE=local`，不会影响现有 PoC。
- 测试/生产若切换到 `gateway` 或 `iam`，必须确保网关注入 `X-Tenant-Id` 和 `X-Actor-Id`。
- 如果 `AUTH_EMPTY_PERMISSION_POLICY=deny`，无权限上下文的检索会返回 `AUTH_CONTEXT_FORBIDDEN`。

## 总结结论

P7-1 生产认证与授权接入首版已完成。当前实现把 Phase 6 的 Header 兼容能力升级为可配置的 local/gateway/iam 三模式，并保持现有 PoC 回归通过。下一步建议进入 P7-2 正式 rerank 服务接入与容量基线。
