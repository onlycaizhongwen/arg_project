# 数据清洗与 RAG 服务 Phase 5 对客 PoC 联调计划

## 1. 阶段目标

Phase 5 的目标不是继续扩大底层能力，而是把已经完成的 MVP、检索漏斗、文档治理、批量重建、诊断概览和模型评测能力，整理成客户可以理解、可以部署、可以演示、可以联调的问题闭环包。

交付后应达到：

- 客户能按文档启动一套本地或测试环境。
- 客户能按步骤完成上传、检索、更新、重建、批量重建、诊断查看。
- 客户能看懂接口清单、调用样例、数据流和能力边界。
- 项目组能用统一 demo 脚本完成对客演示。
- 出现常见问题时，可以按排查手册定位到 API、Worker、MQ、对象存储、向量库、模型服务或配置问题。

## 2. 当前基础

已具备的能力：

- 主链路：文件上传 -> RabbitMQ -> Worker 清洗切块 -> Embedding -> Qdrant -> RAG 检索。
- 检索：semantic、keyword、hybrid、RRF、粗排、去重、打散、权限过滤、rerank 降级。
- 治理：文档删除、更新、重建、审计、操作锁、失败 job 重试、批量重建。
- 诊断：`GET /api/v1/diagnostics/overview`。
- 模型：mock、local BGE、DashScope text-embedding-v4 兼容评测。
- 文档：MVP 对客技术方案书、API 契约、架构图、流程图、时序图、模型评测报告。

## 3. 交付物清单

### 3.1 PoC 联调说明

新增：

- `docs/codex/v1/plans/数据清洗与RAG服务PoC联调说明.md`

内容：

- 环境准备。
- Docker 启动。
- 数据库迁移。
- 模型配置选择。
- 标准演示流程。
- 联调用例清单。
- 验收结果记录表。

### 3.2 部署运维说明

新增：

- `docs/codex/v1/plans/数据清洗与RAG服务部署运维说明.md`

内容：

- 服务组件说明。
- 环境变量清单。
- 国内镜像源说明。
- 启停命令。
- 迁移命令。
- 常用健康检查。
- 日志查看。
- 数据清理与备份建议。

### 3.3 对客演示脚本

新增：

- `scripts/poc-demo.ps1`

首版脚本串联：

1. 检查 API 健康状态。
2. 上传 demo 文档。
3. 等待 job 成功。
4. 执行 hybrid 检索。
5. 更新文档版本。
6. 重建文档索引。
7. 创建批量重建任务。
8. 查询诊断概览。
9. 输出一份演示摘要。

### 3.4 问题排查手册

新增：

- `docs/codex/v1/plans/数据清洗与RAG服务问题排查手册.md`

内容：

- API 不通。
- Docker 镜像拉取失败。
- PostgreSQL 迁移失败。
- RabbitMQ 队列积压。
- Worker 不消费。
- MinIO 对象不存在。
- Qdrant 无检索结果。
- Embedding 维度不匹配。
- 本地 BGE 不可用。
- DashScope key 未配置或调用失败。
- rerank 降级。
- 文档操作锁未释放。

### 3.5 对客接口清单更新

更新：

- `docs/codex/v1/plans/data-cleaning-rag-api-contract.md`

重点确认：

- 批量重建接口已经纳入。
- 模型评测脚本已经纳入。
- 对客边界要明确：当前权限是最小标签过滤，不是真实 IAM；当前批量治理首版只做批量重建。

## 4. 推荐实施顺序

### P5-1：PoC 联调说明

先写客户最需要的“怎么跑起来、怎么验证”的文档。

验收：

- 文档包含完整命令。
- 文档能覆盖 `mock`、`local_bge`、DashScope 三种模型配置。
- 文档明确推荐本地演示使用 `local_bge + mock rerank`。

### P5-2：对客演示脚本

把人工演示步骤自动化，减少现场手误。

验收：

- `scripts/poc-demo.ps1` 可在当前 Compose 环境跑通。
- 输出 document_id、job_id、batch_id、检索命中、诊断状态。
- 失败时给出明确错误信息。

### P5-3：部署运维说明

把运行依赖和常用运维命令整理清楚。

验收：

- 能说明每个容器的职责。
- 能说明各环境变量的作用。
- 能说明国内镜像源配置。
- 能说明如何查看 API、Worker、RabbitMQ、PostgreSQL、Qdrant、MinIO 状态。

### P5-4：问题排查手册

把联调高频问题固化成排查路径。

验收：

- 每类问题包含现象、可能原因、检查命令、修复建议。
- 覆盖模型、向量库、MQ、对象存储和数据库。

### P5-5：对客材料一致性检查

对齐技术方案书、API 契约、PoC 联调说明和实际代码能力。

验收：

- 文档中不存在已经过期的“未实现”描述。
- API 清单与实际路由一致。
- 脚本清单与实际文件一致。
- 明确当前边界和后续增强项。

## 5. 验收命令

Phase 5 完成后建议跑：

```powershell
.\scripts\smoke-test.ps1
.\scripts\document-batch-rebuild-test.ps1
.\scripts\model-eval.ps1 -SkipMock
.\scripts\poc-demo.ps1
```

如果需要完整回归，再补：

```powershell
.\scripts\phase2-eval.ps1
.\scripts\document-operation-lock-test.ps1
.\scripts\diagnostics-test.ps1
```

## 6. 风险与边界

- 当前 PoC 仍是本地/测试联调包，不等同生产上线包。
- 当前 `actor_id`、`request_source` 仍来自请求参数，生产应改为认证上下文注入。
- 当前权限是标签交集过滤，不是完整组织、角色、用户授权体系。
- 当前批量治理首版只支持批量重建，批量删除、批量 retry、批量取消可放后续。
- 当前模型评测样例集较小，需要在客户真实语料上扩充评测集。

## 7. 当前完成情况

Phase 5 已完成：

1. P5-1：已输出 `数据清洗与RAG服务PoC联调说明.md`。
2. P5-2：已新增并验证 `scripts/poc-demo.ps1`，在 `local_bge/bge-m3 + mock rerank` 环境跑通。
3. P5-3：已输出 `数据清洗与RAG服务部署运维说明.md`。
4. P5-4：已输出 `数据清洗与RAG服务问题排查手册.md`。
5. P5-5：已完成 API 契约、脚本清单和过期描述一致性检查。

下一步建议进入 Phase 6：生产部署与运维加固，重点补真实鉴权、生产监控告警、锁超时释放、批量任务取消/重试、评测集扩展和容量压测。
