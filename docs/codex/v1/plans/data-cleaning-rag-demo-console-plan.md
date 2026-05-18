# 数据清洗与 RAG 服务对客演示控制台 MVP 计划

## 1. 目标

新增一个轻量 Vue 控制台，用于对客交流时演示“上传 -> 清洗 -> 检索 -> rerank -> 诊断”的端到端链路。

本阶段不做正式运维后台，不引入用户登录、复杂文档管理、批量治理看板和客户语料评测看板。

## 2. 技术选型

| 项 | 选择 |
| --- | --- |
| 前端框架 | Vue 3 |
| 构建工具 | Vite |
| 语言 | TypeScript |
| 图标 | lucide-vue-next |
| 后端访问 | Vite dev proxy 代理到 FastAPI |
| 默认前端端口 | `5173` |
| 默认 API 地址 | `http://localhost:8000` |

## 3. 页面范围

首版页面位于 `services/console`，包含：

- 演示上下文：`tenant_id`、`knowledge_base_id`、权限标签、操作人、请求来源。
- 链路状态：API 健康、队列积压、rerank provider、近期失败率。
- 文档上传：选择文件、上传、轮询 job 状态。
- 检索与重排：输入 query，配置 hybrid/semantic/keyword、TopK、召回数、粗排数、去重、打散、rerank 开关。
- Rerank provider 切换：测试人员可在页面直接切换 `disabled`、`mock`、`external/BGE`。
- 命中片段：展示 score、pre-rank score、rerank score、召回来源和片段内容。
- 诊断摘要：展示 job、queue、lock、rerank 降级和 API 请求指标摘要。

## 4. 文件清单

- `services/console/package.json`
- `services/console/index.html`
- `services/console/vite.config.ts`
- `services/console/tsconfig.json`
- `services/console/src/main.ts`
- `services/console/src/api.ts`
- `services/console/src/App.vue`
- `services/console/src/styles.css`
- `services/console/README.md`
- `services/api/app/api/runtime_config.py`
- `scripts/rerank-runtime-config-test.ps1`

## 5. 启动方式

后端：

```powershell
docker compose -f infra\docker-compose.yml up -d api worker postgres rabbitmq minio qdrant
```

前端：

```powershell
cd services\console
npm install --cache .\.npm-cache --registry=https://registry.npmmirror.com
npm run dev
```

访问：

```text
http://localhost:5173
```

## 6. 验证

已完成：

- `npm install --cache .\.npm-cache --registry=https://registry.npmmirror.com`
- `npm run build`
- `Invoke-WebRequest http://localhost:5173`
- `Invoke-RestMethod http://localhost:5173/health`
- `Invoke-RestMethod http://localhost:5173/api/v1/diagnostics/overview?tenant_id=default`
- `scripts/rerank-runtime-config-test.ps1`

## 7. 后续增强

- 增加文档列表、版本状态和审计事件入口。
- 增加批量重建、失败 item 重试和取消入口。
- 对接 P7-3 客户真实语料评测包，形成质量评测看板。
- 在需要独立部署时补 Dockerfile、Nginx 静态服务和 Compose profile。
