# 数据清洗与 RAG 服务 Phase 6 P6-1 环境配置分层执行计划

## 1. 目标

P6-1 的目标是把当前单一 `.env.example` 拆成面向不同环境的配置模板，让本地演示、测试联调和生产部署有清晰边界。

完成后应达到：

- 本地 PoC 可以直接使用本地 BGE 或 mock 快速启动。
- 测试环境可以使用客户内网中间件、内网镜像源和可选 DashScope。
- 生产环境模板不放真实密码和真实 Key，只保留占位符和安全说明。
- 部署运维说明能指导用户按环境模板启动服务。
- 后续 P6-2 鉴权上下文、P6-3 日志、P6-4 监控可以继续沿用环境分层方式。

## 2. 当前问题

当前只有 `.env.example`，它同时承担本地 PoC、镜像源、数据库、模型和重排配置示例，存在几个问题：

- 本地演示推荐 `local_bge + mock rerank`，但 `.env.example` 默认仍是 `mock + disabled`。
- 测试/生产环境的敏感信息没有明确占位规则。
- 客户内网镜像仓库、数据库地址、对象存储地址等没有分层模板。
- 部署文档虽然说明了变量含义，但没有明确“本地、测试、生产分别怎么配”。

## 3. 新增文件规划

### 3.1 `.env.local.example`

用途：本地开发、本地 PoC、对客演示。

建议特点：

- 保留 `docker.m.daocloud.io` 国内镜像源默认值。
- 数据库、RabbitMQ、MinIO、Qdrant 连接指向 `localhost`，便于宿主机脚本访问。
- 推荐本地 BGE：
  - `EMBEDDING_PROVIDER=local_bge`
  - `EMBEDDING_MODEL=bge-m3`
  - `EMBEDDING_DIMENSION=1024`
  - `EMBEDDING_BASE_URL=http://host.docker.internal:11434`
- 推荐演示使用：
  - `RERANK_PROVIDER=mock`
- 保留可选本地 BGE reranker 注释项：
  - `COMPOSE_PROFILES=reranker`
  - `RERANK_PROVIDER=external`
  - `RERANK_BASE_URL=http://reranker:8010/rerank`

### 3.2 `.env.test.example`

用途：客户测试环境、联调环境、预生产前验证环境。

建议特点：

- 镜像地址允许替换为客户内网 registry。
- 数据库、RabbitMQ、MinIO、Qdrant 地址使用占位符。
- Embedding 推荐两种二选一：
  - 内网本地 BGE 服务。
  - DashScope `text-embedding-v4`。
- Rerank 默认 `disabled` 或 `mock`，真实 rerank 作为可选项。
- 明确 `DASHSCOPE_API_KEY=<set-in-env-or-secret-manager>`。

### 3.3 `.env.prod.example`

用途：生产部署前的配置清单模板。

建议特点：

- 不提供真实密码、Key、AK/SK。
- 所有敏感值使用占位符：
  - `<set-by-secret-manager>`
  - `<prod-postgres-password>`
  - `<prod-minio-secret-key>`
- 强调生产环境不建议使用默认账号密码。
- Embedding provider 推荐按项目选型固定，不建议运行时频繁切换。
- Rerank provider 明确容量评估后再开启。
- 预留后续 P6-2/P6-3/P6-4 变量：
  - `AUTH_CONTEXT_MODE=header`
  - `LOG_LEVEL=INFO`
  - `TRACE_ID_HEADER=X-Trace-Id`
  - `METRICS_ENABLED=true`

## 4. 文档更新规划

更新 `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`。

新增内容：

1. 环境模板选择表。
2. 本地 PoC 启动方式：
   ```powershell
   Copy-Item .env.local.example .env
   docker compose -f infra/docker-compose.yml up -d
   ```
3. 测试环境配置方式：
   ```powershell
   Copy-Item .env.test.example .env
   ```
   然后按客户中间件地址和模型服务地址调整。
4. 生产环境配置原则：
   - `.env.prod.example` 只能作为模板。
   - 真实敏感信息由密钥管理、CI/CD 变量或部署平台注入。
   - 生产环境不提交 `.env`。
5. 镜像源覆盖说明：
   - 默认国内镜像源。
   - 客户内网 registry 覆盖方式。
   - 国外源恢复方式。

## 5. 实施步骤

### Step 1：新增本地模板

新增 `.env.local.example`，从当前 `.env.example` 派生，调整为本地 PoC 推荐配置。

验收：

- 文件包含本地 BGE 推荐变量。
- 文件仍支持直接启动 Compose。

### Step 2：新增测试模板

新增 `.env.test.example`，把连接地址和敏感信息改为测试环境占位符。

验收：

- 不包含真实密码。
- 明确模型服务可以选 DashScope 或内网 BGE。

### Step 3：新增生产模板

新增 `.env.prod.example`，只保留生产配置项和占位符。

验收：

- 不包含默认弱密码。
- 包含敏感信息注入说明。
- 预留认证、日志、监控变量。

### Step 4：更新部署运维说明

在部署运维说明中新增“环境模板”章节。

验收：

- 本地、测试、生产三种场景能看懂用哪个模板。
- 明确 `.env` 不应提交。
- 明确生产敏感信息管理方式。

### Step 5：验证

执行：

```powershell
docker compose -f infra/docker-compose.yml config --quiet
git diff --check
```

如果本机 Docker 不可用，则至少执行：

```powershell
git diff --check
```

并在结果中说明 Compose 验证未执行原因。

## 6. 影响范围

文件新增：

- `.env.local.example`
- `.env.test.example`
- `.env.prod.example`

文件修改：

- `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`
- `docs/codex/v1/status.md`
- `.codex/plans/main/TASKS.md`
- `.codex/plans/main/data-cleaning-rag-architecture/process.md`

不修改：

- `infra/docker-compose.yml`
- API/Worker 业务代码
- 数据库迁移
- 现有脚本

## 7. 风险与控制

- 风险：模板与 Compose 实际读取变量不一致。
  - 控制：以 `infra/docker-compose.yml` 和 `.env.example` 为字段来源，不凭空增加 Compose 不读取的变量；预留变量需标注为后续阶段使用。
- 风险：生产模板误放默认弱密码。
  - 控制：生产模板统一使用占位符。
- 风险：本地模板默认依赖 Ollama，用户没启动时跑不通。
  - 控制：文档明确本地 BGE 前置命令；保留切回 `mock` 的说明。
- 风险：测试环境模型选择不一致。
  - 控制：模板中明确 DashScope 和内网 BGE 二选一，不建议同时启用。

## 8. 完成标准

P6-1 完成时应满足：

- 三份环境模板已新增。
- 部署运维说明已补充按环境启动和敏感信息管理。
- `git diff --check` 通过。
- `docker compose -f infra/docker-compose.yml config --quiet` 通过，或明确记录未执行原因。
- `status.md` 和任务记录已同步下一步到 P6-2。

## 9. P6-1 完成后的下一步

进入 P6-2：认证上下文与操作人注入。

建议优先做 Header 兼容方案：

- `X-Tenant-Id`
- `X-Actor-Id`
- `X-Request-Source`
- `X-Permission-Tags`
- `X-Trace-Id`

保持现有 query/body 参数兼容，避免破坏 PoC 脚本和对客联调材料。

## 10. 执行结果

2026-05-18 已完成 P6-1 首版：

- 已新增 `.env.local.example`、`.env.test.example`、`.env.prod.example`。
- 已更新 `.gitignore`，允许三份 `.env.*.example` 模板入库，同时继续忽略真实 `.env` 和其他 `.env.*` 文件。
- 已更新 `数据清洗与RAG服务部署运维说明.md`，补充分环境模板选择、敏感信息管理、镜像源覆盖、测试/生产配置原则。
- 已验证 `.env.local.example` 不会被 git ignore 规则忽略。
- 已执行 `docker compose -f infra/docker-compose.yml config --quiet`。
- 已执行 `git diff --check`。

下一步进入 P6-2：认证上下文与操作人注入。
