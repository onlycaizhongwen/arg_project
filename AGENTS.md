# Codex 项目规则

本文档是项目级自动入口规则。进入本仓库工作时，优先按这里的规则识别任务类型，并把任务导向正确技能链路。

## 默认入口

除非任务非常小、且明显不属于项目工作，否则优先从 `$project-entry` 开始，由它负责识别任务意图、判断任务阶段、并串联后续技能。

## 任务识别总原则

1. 先识别用户这次主要想达成什么结果，而不是只看字面措辞。
2. 如果一句话同时包含多个目标，优先按“当前最先需要完成的阶段”进入流程。
3. 如果任务描述模糊，但明显属于项目工作，默认先进入 `project-entry`，再由它兜底分流。
4. 如果任务会跨多轮推进、可能中断、涉及多个主要步骤或多个文件，必须接入 `task-control`。
5. 如果任务涉及 requirements、design、plan、trace 这些结构化交付物，必须先进入 `project-skill-convention`。
6. 如果任务主要是代码实现、代码修改、代码阅读、配置调整、缺陷修复，至少进入 `dev-constraints`。

## 自动识别与分流规则

### 1. 日常开发 / 缺陷修复 / 代码阅读

优先进入：
- `project-entry`
- 再由它转入 `dev-constraints`
- 如任务较大、跨文件、可中断，再补 `task-control`

典型用户说法：
- 修一下这个 bug
- 看看这段代码在干嘛
- 帮我改一下这个接口逻辑
- 继续实现这个功能
- 调整一下配置
- 帮我排查这个报错

### 2. 需求分析

优先进入：
- `project-entry`
- `project-skill-convention`
- `req-analysis`
- 如主题较大，再补 `task-control`

典型用户说法：
- 帮我分析这个需求
- 先整理 requirements
- 把这个想法拆成明确需求
- 把边界条件和异常流补齐

### 3. 技术设计

优先进入：
- `project-entry`
- `project-skill-convention`
- `design-phase`
- 如主题较大，再补 `task-control`

典型用户说法：
- 基于需求出技术方案
- 给我一版设计文档
- 设计一下表结构、接口和流程
- 说明兼容策略、回滚方案、幂等处理

### 4. 执行计划

优先进入：
- `project-entry`
- `project-skill-convention`
- `plan-phase`
- 如主题较大，再补 `task-control`

典型用户说法：
- 把这个方案拆成执行计划
- 给我拆实施步骤
- 明确改动范围、风险和验证项
- 按阶段排一下落地顺序

### 5. 闭环审查 / 差异追踪

优先进入：
- `project-entry`
- `project-skill-convention`
- `req-trace`
- 审查范围较大时，再补 `task-control`

典型用户说法：
- 看看这个需求有没有闭环
- 审查 requirements、design、plan 和实现是否一致
- 帮我找缺口
- 做一版 trace 审查
- 这个任务做完了，帮我收尾检查一下
- 验证完成后补一版一致性审查
- 提交前帮我看看实现和文档是否一致

补充规则：
- 如果主题已经完成实现或验证，但 `docs/codex/{version}/trace/` 下还没有对应 trace 文档，不要默认流程已经结束。
- 应自动补接 `req-trace`，至少产出一版 trace 审查结果。

### 6. 基础设施只读查询

优先进入：
- `project-entry`
- `dev-small-tool`

典型用户说法：
- 查一下表结构
- 看看这个索引
- 查一下 Nacos 配置
- 看 ES mapping
- 查链路追踪或中间件依赖

### 7. 业务域文档沉淀

优先进入：
- `project-entry`
- `docs-desc-generation`

典型用户说法：
- 梳理一下这个业务域
- 初始化长期业务说明文档
- 沉淀核心对象、状态流转和上下游依赖

### 8. 项目初始化 / 项目接入

优先进入：
- `project-entry`
- `dev-constraints`
- `task-control`

典型用户说法：
- 初始化当前项目
- 按项目规则初始化项目骨架
- 把这个仓库接成 Codex 项目
- 初始化 docs、plans、requirements 目录
- 建立项目入口和任务记录骨架

初始化时应补齐：
- `AGENTS.md`
- `docs/codex/v1/requirements/.gitkeep`
- `docs/codex/v1/designs/.gitkeep`
- `docs/codex/v1/plans/.gitkeep`
- `docs/codex/v1/trace/.gitkeep`
- `docs/codex/v1/status.md`
- `.codex/plans/main/TASKS.md`

说明：
- 只要用户是在“初始化项目”，就不能只创建 `AGENTS.md` 和 `docs` 目录
- 必须把 `.codex/plans/main/TASKS.md` 一并补齐

### 9. 安装 / 导出 / 使用说明

按任务目标进入：
- 安装导入：`starter-kit-import`
- 打包导出：`starter-kit-backup`
- 只读说明：`starter-kit-guide`

## 模糊任务的兜底规则

如果用户说法比较模糊，按下面顺序判断：

1. 只要明显是在“改东西、查问题、读代码”，先走 `dev-constraints`。
2. 只要明显是在“先想清楚需求或方案”，先走 `project-skill-convention` 对应阶段。
3. 只要明显是在“继续、恢复、接着做、上次那个任务”，优先补 `task-control`。
4. 只要明显是在“查表、查索引、查配置、查中间件”，走 `dev-small-tool`。
5. 如果同时含有“分析 + 设计 + 计划 + 实现”，优先从最前面的缺失阶段开始，不跳阶段。

## 长任务判定

符合以下任一条件时，必须进入 `task-control`：
- 预计跨多轮对话
- 可能暂停后恢复
- 涉及 3 个以上主要步骤
- 涉及多个模块或多个文件
- 用户明确说“继续”“恢复”“接着做”“先记下来”

## 子代理规则

如果任务被拆给子代理或并行执行，子代理也必须继续遵守本文档中的入口规则，不得绕开项目入口和任务持久化要求。

派发前，主代理必须传递：
- 当前任务目标和边界
- 本文档规则继续生效
- 当前必须遵守的技能链路
- 必读文档、状态文件或任务记录
- 回传格式：改动文件、验证结果、剩余风险、下一步建议

如果是长任务或阶段任务，主代理必须先建立或更新 `task-control` 记录，再把任务编号、`TASKS.md` 路径、`process.md` 路径一并传给子代理。

## 工作前检查

1. 先看项目内现有工作区材料，例如 `.codex/`、`docs/`、设计文档、计划文档。
2. 如果任务属于结构化交付流，先读 `docs/codex/{version}/status.md`。
3. 如果任务直接进入实现，先读当前主题对应的 requirements、design、plan 文档。
4. 如果任务属于普通开发任务，至少遵守 `dev-constraints`。

## 目标

项目根 `AGENTS.md` 负责“优先走哪条流程”，`project-entry` 负责“当前任务该串联哪些技能”，其他技能负责各阶段的具体执行细则。

目标是让用户在项目里尽量用自然语言描述任务，也能被稳定识别并导向正确流程。
