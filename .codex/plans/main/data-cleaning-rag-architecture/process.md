# 恢复胶囊

- 任务需求：基于用户提供的“数据清洗与 RAG 服务架构”图，先完成规划、需求分析、技术选型与设计。
- 关键决策：主题命名为 `data-cleaning-rag-architecture`，版本使用 `docs/codex/v1`。
- 当前阶段：等待确认。
- 已完成产物：requirements、design、plan、status、任务记录。
- 剩余工作：等待用户确认技术栈、首期基础设施和 MVP 范围后进入工程初始化或细化专项设计。
- 重要发现：仓库当前只有项目规则与 docs/codex/v1 骨架，没有业务代码和既有主题文档。

## 步骤列表

- [v] 检查 AGENTS.md、docs/codex/v1、.codex/plans/main/TASKS.md。
- [v] 产出结构化规划文档。
  - 当前产物：requirements、design、plan、status。
  - 下一步：用户确认后进入实现或细化专项设计。
  - 涉及文件：docs/codex/v1/requirements、docs/codex/v1/designs、docs/codex/v1/plans、docs/codex/v1/status.md。
- [~] 等待用户确认技术选型与范围后进入实现或细化设计。
- [v] 补充下一步执行计划。
  - 当前产物：docs/codex/v1/plans/data-cleaning-rag-next-step.md。
  - 下一步：确认 5 个关键决策后进入工程初始化。
- [v] 补充 MVP HTML 可视化页面。
  - 当前产物：docs/codex/v1/plans/data-cleaning-rag-mvp.html。
  - 下一步：用户确认后可打开预览或继续细化工程任务。
- [v] 修正 MVP 版本边界。
  - 当前产物：MVP HTML 和 next-step 文档已明确只做基础粗排/候选截断，不接完整业务干预和 Cross-Encoder 精排。
  - 下一步：如需继续，可补充 MVP 接口清单和表结构草案。
- [v] 进一步规划 MVP 工程实施蓝图。
  - 当前产物：docs/codex/v1/plans/data-cleaning-rag-mvp-implementation-blueprint.md。
  - 下一步：确认默认技术选择后进入工程初始化。
- [v] 确认统一 Python 技术栈。
  - 当前产物：相关设计与计划文档已调整为 FastAPI 控制面 + Python Worker。
  - 下一步：确认向量库、Embedding 来源和 Docker Compose 后进入工程初始化。
- [v] 补充最小 MVP 时序图。
  - 当前产物：MVP HTML 中新增可视化时序图，工程蓝图中新增 Mermaid 时序图。
  - 下一步：可继续细化接口字段、表结构 SQL 或工程目录结构。
- [v] 优化 MVP HTML 时序图可读性。
  - 当前产物：时序图已从长线布局改为三段式紧凑流程图，减少空白和跨栏连线。
  - 下一步：刷新 HTML 页面检查新版展示。
- [v] 改用 Mermaid 绘制 MVP 时序图。
  - 当前产物：MVP HTML 内的时序图已替换为 Mermaid sequenceDiagram。
  - 下一步：刷新 HTML；如本地无法加载 CDN，可直接查看工程蓝图中的 Mermaid 源码。
- [v] 沉淀总体架构图到工程。
  - 当前产物：docs/codex/v1/assets/data-cleaning-rag-overall-architecture.html。
  - 下一步：如需要精确 PNG 原图，请提供本地图片文件路径后再复制入 assets。
- [v] 引用原始总体架构 PNG。
  - 当前产物：docs/codex/v1/assets/总体架构图.png 已存在，设计文档已优先引用该原图。
  - 下一步：后续设计说明以 PNG 原图为准，HTML 版仅作为可编辑备份。

## 研究发现

- 架构图覆盖业务应用、数据资产管理、多源异构接入、智能清洗、语义切分与向量化、向量存储与索引优化、RAG 检索服务、计算存储基础设施、模型与算法服务、横向治理能力。
- 当前阶段适合先定义平台级边界，再拆出 MVP：文件/API 接入、清洗流水线、向量化入库、语义/混合检索、重排、基础管理与监控。

## 错误记录

- 暂无。
