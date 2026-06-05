# FigureLearning 架构重构任务合同

本任务清单按依赖顺序排列。每个任务应在一个可验证的小步内完成，避免一次性重写系统。

## Phase 1: 规格与任务文档

- [x] Task: 建立架构规格与任务合同
  - Acceptance: `docs/architecture/spec.md` 和 `docs/architecture/tasks.md` 存在，并记录重构目标、目标架构、API 契约、测试门槛和迁移顺序。
  - Verify: 检查两个 Markdown 文件内容完整；无需修改运行代码。
  - Files: `docs/architecture/spec.md`, `docs/architecture/tasks.md`

## Phase 2: 后端基础骨架

- [ ] Task: 新建 FastAPI app factory 规划入口
  - Acceptance: 新入口能够挂载现有静态目录和后续 router；旧 `app.py` 暂时保持可用。
  - Verify: `.\.venv\Scripts\python.exe -m pytest`
  - Files: 后续在 `src/main.py` 和兼容入口中实现。

- [ ] Task: 新建 `shared` 基础设施
  - Acceptance: 提供统一配置、错误类型、响应包装、数据库连接和安全路径工具的目标位置。
  - Verify: 新增 shared 单元测试；现有测试全过。
  - Files: 后续在 `src/shared/` 中实现。

- [ ] Task: 设计新 API 错误/响应契约
  - Acceptance: 新 router 可返回统一成功响应和统一错误响应；错误码稳定可测试。
  - Verify: 新增 API contract 测试；现有测试全过。
  - Files: 后续在 `src/shared/errors.py`, `src/shared/responses.py` 中实现。

## Phase 3: 低风险领域迁移

- [ ] Task: 拆分 `settings`
  - Acceptance: LLM、ASR、图片 API 配置迁移到 `settings` 领域；route 层只处理 HTTP，service/repository 处理行为和存储。
  - Verify: 配置新增、保存、激活、删除、测试接口通过 API 测试；现有测试全过。
  - Files: 后续在 `src/settings/` 中实现。

- [ ] Task: 拆分 `uploads`
  - Acceptance: 图片、文档、媒体上传与去重逻辑迁移到 `uploads` 领域；文件保存细节与 API 层解耦。
  - Verify: 上传、重复识别、文件读取相关测试通过；现有测试全过。
  - Files: 后续在 `src/uploads/` 中实现。

## Phase 4: 核心知识链路迁移

- [ ] Task: 拆分 `knowledge`
  - Acceptance: 知识生成、读取、删除、Markdown 渲染入口迁移到 service/usecase；API 层不直接编排 OCR/LLM/存储细节。
  - Verify: 图片生成知识、列表、详情、删除相关测试通过；现有测试全过。
  - Files: 后续在 `src/knowledge/` 中实现。

- [ ] Task: 拆分 `documents`
  - Acceptance: 文档解析、分页、范围规划、文档到知识生成迁移到独立领域。
  - Verify: 文档页信息、范围规划、分段生成知识相关测试通过；现有测试全过。
  - Files: 后续在 `src/documents/` 中实现。

- [ ] Task: 拆分 `media`
  - Acceptance: 媒体上传后处理、URL 解析、转写、片段规划、媒体到知识生成迁移到独立领域。
  - Verify: 媒体依赖检查、转写、删除字幕、片段规划、知识生成相关测试通过；现有测试全过。
  - Files: 后续在 `src/media/` 中实现。

## Phase 5: 高复杂度领域迁移

- [ ] Task: 拆分 `graph`
  - Acceptance: 图谱入网、节点读取、重命名、删除、pending 节点、重建和检索上下文迁移到 `graph` 领域。
  - Verify: 图谱 API 与 graph service 测试通过；现有测试全过。
  - Files: 后续在 `src/graph/` 中实现。

- [ ] Task: 拆分 `mining`
  - Acceptance: 挖掘项目、素材绑定、策略学习、版本记录迁移到 `mining` 领域。
  - Verify: 项目创建、重命名、素材绑定、策略学习相关测试通过；现有测试全过。
  - Files: 后续在 `src/mining/` 中实现。

- [ ] Task: 拆分 `writer`
  - Acceptance: 选题、文章生成、修订、配图、格式化、公众号发布迁移到 `writer` 领域。
  - Verify: writer session、workspace、article、revise、images、format、publish preflight 测试通过；现有测试全过。
  - Files: 后续在 `src/writer/` 中实现。

## Phase 6: 外部能力网关

- [ ] Task: 抽象 `llm` gateway
  - Acceptance: DeepSeek/OpenAI-compatible 调用通过统一接口暴露；业务 service 不直接依赖 provider 细节。
  - Verify: 使用 fake gateway 测试知识生成、图谱分类、写作生成；现有测试全过。
  - Files: 后续在 `src/llm/` 中实现。

- [ ] Task: 抽象 `ocr` gateway
  - Acceptance: PaddleOCR 与 AI vision OCR 通过统一接口暴露；知识生成 service 只依赖 gateway。
  - Verify: 使用 fake OCR gateway 测试图片到知识链路；现有测试全过。
  - Files: 后续在 `src/ocr/` 中实现。

## Phase 7: 前端路线评估

- [ ] Task: 评估原生模块化或 React/Vite 迁移
  - Acceptance: 基于后端 API 迁移结果，决定继续拆分 `static/` 还是引入前端构建工具。
  - Verify: 形成独立前端迁移计划；不在本任务中直接重写前端。
  - Files: 后续更新架构文档或新增前端计划。

- [ ] Task: 前端 API 调用集中化
  - Acceptance: 若继续原生路线，则提取 shared API client、toast、DOM helper、状态模块。
  - Verify: 页面核心流程可手动验证；现有测试全过。
  - Files: 后续在 `static/` 下拆分实现。

## Phase 8: 测试重组与契约覆盖

- [ ] Task: 重组测试目录
  - Acceptance: 测试按 `api`、`services`、`repositories`、`parsers`、`contract` 组织；保留现有覆盖。
  - Verify: `.\.venv\Scripts\python.exe -m pytest`
  - Files: 后续在 `tests/` 下迁移。

- [ ] Task: 增加新 API contract 测试
  - Acceptance: 新成功/错误响应契约有测试保护，避免格式漂移。
  - Verify: contract 测试和现有测试全过。
  - Files: 后续在 `tests/contract/` 中实现。

## Migration Rules

- 每次只迁移一个领域或一条清晰用例链路。
- 每轮结束必须保持项目可启动。
- 每轮结束必须运行现有测试。
- 不在同一轮同时修改后端架构、前端框架和数据库 schema。
- 旧 API 的删除、数据库 schema 破坏性变更、新依赖引入必须单独确认。
