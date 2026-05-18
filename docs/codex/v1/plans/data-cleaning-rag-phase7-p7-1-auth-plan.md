# 数据清洗与 RAG 服务 Phase 7 P7-1 生产认证与授权接入计划

## 1. 目标

基于 `data-cleaning-rag-phase7-auth-design.md`，完成生产认证与授权接入的首版落地：

- 增加认证上下文配置。
- 保持 local/PoC 兼容。
- 在 gateway/iam 模式下强制校验 `tenant_id` 和 `actor_id`。
- 明确权限标签兜底策略。
- 补充验证脚本和文档。

## 2. 前置条件

- Phase 6 已完成 Header 上下文注入、trace_id、审计、权限标签检索过滤。
- 当前 `RequestContext` 已集中在 `services/api/app/core/request_context.py`。
- API 已有统一错误结构 `AppError`。

## 3. 改动范围

代码：

- `services/api/app/core/request_context.py`
- `services/api/app/core/config.py` 或现有配置读取模块
- `services/api/app/core/errors.py`
- 涉及依赖 `get_request_context` 的 API 入口，如上传、文档治理、job、batch、search。

配置：

- `.env.local.example`
- `.env.test.example`
- `.env.prod.example`

脚本：

- `scripts/request-context-test.ps1`
- `scripts/permission-test.ps1`

文档：

- `docs/codex/v1/plans/data-cleaning-rag-api-contract.md`
- `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`
- `docs/codex/v1/plans/数据清洗与RAG服务问题排查手册.md`

## 4. 实施步骤

### P7-1-1：配置项接入

新增配置：

```text
AUTH_CONTEXT_MODE=local|gateway|iam
AUTH_TRUSTED_HEADER_ENABLED=true|false
AUTH_REQUIRE_ACTOR=true|false
AUTH_REQUIRE_TENANT=true|false
AUTH_DEFAULT_REQUEST_SOURCE=api
AUTH_DEFAULT_PERMISSION_TAGS=public
AUTH_EMPTY_PERMISSION_POLICY=public_only|deny
```

完成标准：

- local 默认值不影响现有 PoC。
- test/prod 模板明确推荐 gateway/iam。

### P7-1-2：上下文校验逻辑

实现策略：

- local 模式保持当前行为。
- gateway/iam 模式：
  - 缺少 tenant 时返回 `AUTH_CONTEXT_MISSING`。
  - 缺少 actor 时返回 `AUTH_CONTEXT_MISSING`。
  - request_source 缺省时使用配置默认值。
  - permission_context 缺省时按 `AUTH_EMPTY_PERMISSION_POLICY` 处理。

完成标准：

- 错误响应包含 `trace_id`。
- 所有依赖 `RequestContext` 的入口行为一致。

### P7-1-3：权限标签兜底策略

实现策略：

- `public_only`：无权限上下文时仅允许 `public`。
- `deny`：无权限上下文时拒绝检索。
- local 模式默认 `public_only`。

完成标准：

- 检索接口无权限上下文时行为可配置。
- 现有 `permission-test` 可扩展覆盖。

### P7-1-4：脚本验证

扩展验证：

- local 模式不传 Header，smoke 通过。
- gateway 模式缺少 actor，返回 `AUTH_CONTEXT_MISSING`。
- gateway 模式完整 Header，上传和检索通过。
- Header actor 优先级高于 query/body actor。
- 权限标签仍能过滤检索结果。

完成标准：

- `request-context-test.ps1` 通过。
- `permission-test.ps1` 通过。
- `smoke-test.ps1` 通过。

### P7-1-5：文档同步

更新内容：

- API 契约补充认证模式和错误码。
- 部署运维说明补充 test/prod 的认证配置。
- 问题排查手册补充 401/403 排查路径。

完成标准：

- 对客文档能说明 PoC Header 与生产 IAM/网关注入的差异。

## 5. 验证命令

```powershell
python -m compileall services\api\app services\worker\app
docker compose -f infra\docker-compose.yml config --quiet
.\scripts\request-context-test.ps1
.\scripts\permission-test.ps1
.\scripts\smoke-test.ps1
.\scripts\diagnostics-test.ps1
git diff --check
```

## 6. 风险与回滚

| 风险 | 影响 | 回滚 |
| --- | --- | --- |
| gateway/iam 校验阻断 PoC 脚本 | 演示不可用 | 切回 `AUTH_CONTEXT_MODE=local` |
| 网关注入字段名不一致 | 测试环境全部 401 | 暂按 Header alias 兼容或调整网关 |
| 权限标签映射错误 | 误拒绝或误召回 | 切回 `AUTH_EMPTY_PERMISSION_POLICY=public_only` 并复查映射 |
| query/body 兼容被破坏 | 旧脚本失败 | 保留 local 模式下参数兜底 |

## 7. 下一步

P7-1 首版已完成，下一步进入 P7-2 正式 rerank 服务接入与容量基线：

1. 明确 external rerank 的候选服务和测试配置。
2. 扩展模型评测和压测脚本，输出 rerank 开启/关闭的质量和延迟对比。
3. 固化 rerank 超时、批大小、降级和监控指标说明。
