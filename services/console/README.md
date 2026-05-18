# 数据清洗与 RAG 演示控制台

这是面向对客交流的 Vue MVP 控制台，用于演示现有 API 的主链路：

- 文档上传
- 清洗任务轮询
- RAG 检索
- rerank 开关
- rerank provider 运行时切换
- 诊断概览
- Prometheus 指标摘要

## 本地启动

先确保后端已经启动：

```powershell
docker compose -f infra\docker-compose.yml up -d api worker postgres rabbitmq minio qdrant
```

启动控制台：

```powershell
cd services\console
npm install
npm run dev
```

打开：

```text
http://localhost:5173
```

Vite 开发服务器默认代理：

- `/health` -> `http://localhost:8000/health`
- `/api/*` -> `http://localhost:8000/api/*`

如需代理到其他 API 地址：

```powershell
$env:VITE_API_PROXY_TARGET = "http://localhost:8000"
npm run dev
```

## 页面边界

当前版本是演示控制台，不是正式运维后台。它优先覆盖“上传 -> 清洗 -> 检索 -> 诊断”的端到端展示，暂不包含用户登录、复杂权限管理、文档列表分页、批量治理和客户语料评测看板。

## Rerank 切换

页面左侧支持在演示环境直接切换：

- `关闭`：`RERANK_PROVIDER=disabled`
- `Mock`：`RERANK_PROVIDER=mock`
- `BGE`：`RERANK_PROVIDER=external`

切到 BGE 前需要先启动 reranker 服务：

```powershell
docker compose -f infra\docker-compose.yml --profile reranker up -d reranker
```

默认 BGE 地址：

```text
http://reranker:8010/rerank
```

该切换是 API 进程内运行时配置，适合本地演示和测试人员验证，不替代生产环境的配置中心或发布流程。
