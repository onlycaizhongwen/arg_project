# data-cleaning-rag-phase2 追踪审查

## 审查范围

- requirements: `docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md`
- design: `docs/codex/v1/designs/data-cleaning-rag-architecture-design.md`
- phase2 plan: `docs/codex/v1/plans/data-cleaning-rag-phase2-plan.md`
- API contract: `docs/codex/v1/plans/data-cleaning-rag-api-contract.md`
- implementation:
  - `services/api/app/api/search.py`
  - `services/api/app/services/search_service.py`
  - `services/api/app/services/ingestion_service.py`
  - `services/api/app/rerank/rerank_client.py`
  - `services/worker/app/consumers/cleaning_consumer.py`
  - `services/api/migrations/versions/0004_add_text_chunk_fts_index.py`
  - `services/api/migrations/versions/0005_add_permission_tags.py`
  - `scripts/phase2-eval.ps1`
  - `scripts/rerank-degrade-test.ps1`
  - `scripts/permission-test.ps1`
  - `scripts/bge-rerank-test.ps1`
  - `services/reranker/app/main.py`

## 审查结论

阶段 2 首版已达到计划定义的“混合检索与质量增强”目标：检索链路已经从 MVP 的单一路径扩展为：

`语义召回 + 关键词召回 -> RRF 合并粗排 -> 去重/限额/MMR 打散 -> 可选重排/降级 -> 权限标签过滤 -> 可追溯返回`

本轮已验证：

- `scripts/phase2-eval.ps1`：15 个模式/查询检查全部通过。
- `scripts/smoke-test.ps1`：MVP 主链路回归通过。
- `scripts/demo-eval.ps1`：5 条 Demo 查询全部命中。
- `scripts/failure-test.ps1`：错误响应和异步失败路径通过。
- `scripts/rerank-degrade-test.ps1`：外部重排不可用时降级通过。
- `scripts/permission-test.ps1`：默认/public/internal 权限标签过滤通过。
- `scripts/bge-rerank-test.ps1`：本地 BGE 真实重排通过，`rerank_provider=external` 且 `rerank_degraded=false`。

## 已对齐项

| 需求/计划项 | 当前实现 | 结论 |
| --- | --- | --- |
| 搜索契约升级 | 请求支持 `search_mode`、`dedup_enabled`、`diversity_enabled`、`rerank_enabled`、`permission_context`；响应包含召回来源、语义分、关键词分、粗排分、重排分和 search_plan | 已对齐 |
| 关键词召回 | PostgreSQL `to_tsvector('simple', content)` + GIN 索引，支持 tenant、knowledge_base、permission 标签过滤 | 已对齐首版 |
| 混合召回 | semantic/keyword 结果按 chunk 合并，使用 RRF 计算 `pre_rank_score` | 已对齐首版 |
| 候选规模控制 | `recall_size`、`pre_rank_size`、`rerank_size` 分层限制候选规模 | 已对齐 |
| 业务干预 | 内容规范化去重、同文档版本限额、MMR 简化打散 | 已对齐首版 |
| 重排兼容接口 | `RerankClient` 支持 `disabled/mock/external`，mock 可产出分数；本地 `services/reranker` 可用 `BAAI/bge-reranker-base` 提供真实 external rerank | 已对齐首版 |
| 重排降级 | external provider 调用失败时保留业务干预结果并标记 `rerank_degraded=true` | 已对齐 |
| 权限标签过滤 | 上传 `permission_tags`，检索 `permission_context`，PostgreSQL 和 Qdrant 双层过滤 | 已对齐首版 |
| 可重复评测 | `phase2-eval`、`permission-test`、`rerank-degrade-test` 已覆盖阶段 2 核心链路 | 已对齐 |

## 未完全对齐项

| 需求/设计项 | 当前差异 | 判断 |
| --- | --- | --- |
| 十万级候选压缩到千级 | 当前通过参数和小样例验证漏斗行为，未做十万级压测 | 阶段 2 首版可接受，生产前需压测 |
| 训练型粗排模型 | 当前粗排是 RRF/向量分/关键词分，不是 DSSM/FM/DNN | 首版可接受，后续按质量需要引入 |
| SimHash/MinHash/DPP | 当前去重为规范化内容 key，打散为 MMR 简化版，未实现 SimHash/MinHash/DPP | 首版可接受 |
| 真实 Cross-Encoder/通义重排 | 本地 BGE `BAAI/bge-reranker-base` 已验证；通义/百炼或生产模型服务尚未选型压测 | 本地验证已补齐，生产仍待确认 |
| 中文关键词检索 | PostgreSQL `simple` 全文检索对中文弱 | 已知风险，后续需 ES/OpenSearch 或中文分词方案 |
| 完整权限体系 | 当前是标签交集过滤，不含用户、角色、组织、文档授权策略和审计 | 生产前必须增强 |
| 禁用文档/时效/质量过滤 | 阶段 2 计划提到过滤扩展，目前只做权限、知识库、租户 | 后续业务治理项 |

## 风险与影响

- 如果业务语料以中文为主，当前关键词召回效果会明显受限；hybrid 的 keyword 部分不能代表最终生产质量。
- 本地 BGE reranker 已证明真实模型链路可用，但尚未证明生产排序收益；仍需要更大评测集和延迟/吞吐压测。
- 权限标签过滤已具备最小闭环，但不能替代真实鉴权系统；真实接入前需要明确用户权限上下文来源。
- 当前评测集规模很小，适合作为回归，不适合作为检索质量验收的唯一依据。

## 建议后续动作

1. 继续比较真实重排 provider：已验证本地 BGE，可补充通义/百炼重排或企业已有 rerank 服务的效果、成本和延迟评估。
2. 补文档生命周期能力：更新、删除、向量删除、索引重建、版本可见性。
3. 扩展权限治理：用户/角色/组织到 `permission_context` 的映射、审计日志、越权测试集。
4. 扩大评测集，至少覆盖中文查询、同义表达、精确术语、权限负例和过期文档负例。
5. 如继续使用 PostgreSQL 关键词召回，需要评估中文分词插件；否则规划 ES/OpenSearch 适配层。

## 总结

阶段 2 首版可以标记为“功能闭环完成”：混合检索、粗排、业务干预、重排降级、真实本地 BGE 重排和权限标签过滤均已落地，并通过自动化脚本验证。

下一阶段不建议继续堆小功能，建议转向“索引生命周期 + 真实模型 + 权限治理增强 + 评测集扩大”四条线，把当前可演示系统推向可验收系统。
