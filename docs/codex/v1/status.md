# 项目状态

- 当前版本：v1
- 当前阶段：已计划
- 当前主题：data-cleaning-rag-architecture
- 说明：此文件用于记录需求、设计、计划、实现与追踪的主线状态。

## 需求索引

| 主题 | 需求文档 | 设计文档 | 计划文档 | 依赖 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| data-cleaning-rag-architecture | docs/codex/v1/requirements/data-cleaning-rag-architecture-requirements.md | docs/codex/v1/designs/data-cleaning-rag-architecture-design.md | docs/codex/v1/plans/data-cleaning-rag-architecture-plan.md | 对象存储、关系库、Redis、消息队列、向量库、Embedding/重排模型服务 | 已计划 |

## 进度与状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 需求分析 | 已完成 | 已基于架构图抽取目标、范围、场景、功能需求、非功能需求和待确认项。 |
| 技术设计 | 已完成 | 已完成总体架构、技术选型、模块设计、数据对象、接口草案、状态流转和风险说明。 |
| 执行计划 | 已完成 | 已拆分选型验证、MVP、混合检索、多源治理和业务扩展阶段，并补充下一步执行计划与 MVP 开工计划。 |
| 实现 | 未开始 | 等待用户确认首期技术栈、基础设施和 MVP 范围。 |
| 追踪审查 | 未开始 | 实现或范围确认后补充 trace 审查。 |

## 变更记录

- 2026-05-14：创建 `data-cleaning-rag-architecture` 主题，完成需求分析、技术选型/设计和实施计划文档。
- 2026-05-14：补充 `docs/codex/v1/plans/data-cleaning-rag-next-step.md`，明确下一步进入选型验证与 MVP 骨架准备。
- 2026-05-14：补充 RAG 检索漏斗方案，将“召回 -> 粗排 -> 业务干预 -> 精排”纳入需求、设计和计划。
- 2026-05-14：新增 `docs/codex/v1/plans/data-cleaning-rag-mvp.html`，用于可视化展示 MVP 版本范围、阶段和验收路径。
- 2026-05-14：修正 MVP 边界，明确 MVP 只做语义召回、基础粗排/候选截断，不接 Cross-Encoder 精排和完整业务干预。
- 2026-05-14：新增 `docs/codex/v1/plans/data-cleaning-rag-mvp-implementation-blueprint.md`，将 MVP 进一步拆成工程模块、数据模型、API 契约和 M1-M7 实施任务。
- 2026-05-14：根据技术栈决策，将默认方案从 Spring Boot 控制面调整为统一 Python：FastAPI 控制面 + Python Worker。
- 2026-05-14：在 MVP HTML 和工程实施蓝图中补充最小 MVP 时序图，覆盖上传异步入库和语义检索链路。
- 2026-05-14：优化 MVP HTML 时序图展示，将长线时序图调整为三段式紧凑流程图：上传请求、后台入库、在线检索。
- 2026-05-14：根据评审意见，将 MVP HTML 时序图改为 Mermaid sequenceDiagram，减少自定义 CSS 图形带来的排版问题。
- 2026-05-14：新增总体架构图资产 `docs/codex/v1/assets/data-cleaning-rag-overall-architecture.html`，并在设计文档中登记。
- 2026-05-14：确认原始总体架构图已放入 `docs/codex/v1/assets/总体架构图.png`，设计文档已改为优先引用 PNG 原图。
- 2026-05-15：新增 `docs/codex/v1/plans/data-cleaning-rag-mvp-startup-plan.md`，明确工程目录、依赖服务、首批接口、Worker 能力和 D1-D7 开发顺序。
- 2026-05-15：确认 MVP Embedding 模型使用通义/阿里云百炼，默认 `text-embedding-v4`，通过 `DASHSCOPE_API_KEY` 配置。
