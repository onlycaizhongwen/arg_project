# 数据清洗与 RAG 服务 Phase 7 生产认证与授权设计

## 1. 设计目标

本设计用于 P7-1，将当前 PoC Header 上下文升级为可接入客户网关、IAM 或 SSO 的生产认证授权边界。

目标：

- 保留本地 PoC 的低门槛联调能力。
- 测试/生产环境要求身份上下文来自可信来源。
- 审计事件、文档治理、批量治理和检索权限使用同一套请求上下文。
- 首版权限执行模型继续使用标签交集，避免一次性引入复杂 IAM 规则引擎。

非目标：

- 不在 API 内部实现完整用户、角色、组织和菜单权限系统。
- 不直接替代客户 IAM/SSO。
- 不在本阶段实现细粒度 ABAC/RBAC 策略引擎。

## 2. 当前现状

当前 `RequestContext` 支持：

- `X-Tenant-Id`
- `X-Actor-Id`
- `X-Request-Source`
- `X-Permission-Tags`
- `X-Trace-Id`

当前风险：

- Header 可以被客户端直接传入，不能视为生产可信身份。
- 生产模式下缺少强制校验，空 actor 仍可能回退到 query/body 参数。
- 权限标签缺少“可信来源”和“允许范围”的边界说明。

## 3. 认证模式

### 3.1 local 模式

适用范围：

- 本地开发。
- PoC 演示。
- 自动化脚本。

行为：

- 允许缺省 `tenant_id`、`actor_id`。
- 允许 query/body 参数兜底。
- 允许 `X-Permission-Tags` 直接作为权限上下文。

推荐配置：

```text
AUTH_CONTEXT_MODE=local
AUTH_TRUSTED_HEADER_ENABLED=true
AUTH_REQUIRE_ACTOR=false
AUTH_REQUIRE_TENANT=false
```

### 3.2 gateway 模式

适用范围：

- 客户测试环境。
- 由 API Gateway、Nginx、Ingress 或内部网关注入身份。

行为：

- 要求 `X-Tenant-Id`、`X-Actor-Id` 存在。
- `X-Request-Source` 缺省时可使用 `gateway`。
- `X-Permission-Tags` 仅信任网关注入，不建议暴露给浏览器或终端用户直接填写。
- query/body 参数只保留兼容，不覆盖 Header。

推荐配置：

```text
AUTH_CONTEXT_MODE=gateway
AUTH_TRUSTED_HEADER_ENABLED=true
AUTH_REQUIRE_ACTOR=true
AUTH_REQUIRE_TENANT=true
AUTH_DEFAULT_REQUEST_SOURCE=gateway
```

### 3.3 iam 模式

适用范围：

- 生产环境。
- 客户 IAM/SSO/JWT 已完成接入。

行为：

- 身份来源应由网关校验 token 后注入，或由 API 校验受信 JWT。
- 本阶段建议优先采用“网关校验 + API 读取可信 Header”，降低系统内 IAM 复杂度。
- 禁止客户端绕过网关直连 API。
- 权限标签由 IAM/网关映射后注入。

推荐配置：

```text
AUTH_CONTEXT_MODE=iam
AUTH_TRUSTED_HEADER_ENABLED=true
AUTH_REQUIRE_ACTOR=true
AUTH_REQUIRE_TENANT=true
AUTH_DEFAULT_REQUEST_SOURCE=iam-gateway
```

## 4. 上下文字段契约

| 字段 | Header | 含义 | local | gateway/iam |
| --- | --- | --- | --- | --- |
| `tenant_id` | `X-Tenant-Id` | 租户或业务域 | 可缺省 | 必填 |
| `actor_id` | `X-Actor-Id` | 操作人 ID | 可缺省 | 必填 |
| `request_source` | `X-Request-Source` | 请求来源 | 可缺省 | 建议必填，可默认 |
| `permission_context` | `X-Permission-Tags` | 调用方可访问标签 | 可直传 | 仅信任网关/IAM 注入 |
| `trace_id` | `X-Trace-Id` | 链路追踪 ID | 可缺省自动生成 | 可缺省自动生成 |

## 5. 权限执行模型

首版继续使用标签交集：

```text
document.permission_tags ∩ request.permission_context != empty
```

约定：

- 文档无权限标签时，默认按 `public` 处理。
- 请求无权限上下文时，local 模式默认 `public`。
- gateway/iam 模式无权限上下文时，可配置为：
  - 拒绝检索。
  - 或仅允许 `public`。

推荐生产策略：

```text
AUTH_DEFAULT_PERMISSION_TAGS=public
AUTH_EMPTY_PERMISSION_POLICY=public_only
```

## 6. API 行为变更

新增错误码建议：

| 错误码 | HTTP | 场景 |
| --- | --- | --- |
| `AUTH_CONTEXT_MISSING` | 401 | 生产模式缺少必要身份上下文 |
| `AUTH_CONTEXT_INVALID` | 400 | Header 格式非法或权限标签非法 |
| `AUTH_CONTEXT_FORBIDDEN` | 403 | 身份存在但无访问权限 |

兼容策略：

- local 模式保持当前脚本全部可跑。
- gateway/iam 模式只影响未携带可信 Header 的请求。
- 审计事件优先记录可信上下文中的 actor/source。

## 7. 配置项设计

新增配置建议：

```text
AUTH_CONTEXT_MODE=local|gateway|iam
AUTH_TRUSTED_HEADER_ENABLED=true|false
AUTH_REQUIRE_ACTOR=true|false
AUTH_REQUIRE_TENANT=true|false
AUTH_DEFAULT_REQUEST_SOURCE=api
AUTH_DEFAULT_PERMISSION_TAGS=public
AUTH_EMPTY_PERMISSION_POLICY=public_only|deny
```

## 8. 验证设计

验证场景：

- local 模式不传 Header，现有 smoke/poc 脚本通过。
- gateway 模式缺少 `X-Actor-Id` 返回 `AUTH_CONTEXT_MISSING`。
- gateway 模式携带完整 Header，上传、审计、检索通过。
- Header 权限标签能限制检索结果。
- query/body 中 actor 不覆盖可信 Header actor。

建议脚本：

- 扩展 `scripts/request-context-test.ps1`
- 扩展 `scripts/permission-test.ps1`

## 9. 风险与回滚

- 风险：生产模式校验过严导致联调脚本失败。
  - 回滚：切回 `AUTH_CONTEXT_MODE=local`。
- 风险：网关未正确注入 Header，导致全部请求 401。
  - 回滚：临时切回 `gateway` 宽松配置，或在网关补默认来源。
- 风险：权限标签映射错误导致误拒绝或误召回。
  - 回滚：切回 `AUTH_EMPTY_PERMISSION_POLICY=public_only`，并暂停非 public 权限数据导入。

## 10. 结论

P7-1 首版建议采用“网关/IAM 负责认证，API 负责上下文校验和权限标签执行”的方案。这样既不把当前 RAG 服务扩成完整 IAM 系统，又能满足生产环境对可信身份、审计和权限过滤的基本要求。
