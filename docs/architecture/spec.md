# Spec: FigureLearning 架构重构

## Objective

本规格定义 FigureLearning 的长期架构重构方向。目标不是一次性重写系统，而是在现有功能可运行、现有测试可通过的前提下，把当前的功能堆叠型单体逐步改造成边界清晰、可测试、可扩展的领域化架构。

当前系统定位：

- 后端：FastAPI
- 前端：原生 HTML/CSS/JavaScript，位于 `static/`
- 数据库：SQLite
- 存储：本地文件系统
- 能力：截图 OCR、文档解析、媒体转写、知识生成、知识图谱、创作策略挖掘、公众号写作与发布、LLM/API 配置管理

重构总目标：

- 稳健扩展：优先减少大文件和跨层耦合，避免破坏现有可用功能。
- 全量规划：完整定义目标架构和领域边界，再分阶段迁移。
- 前端暂缓：第一轮不改前端实现，后续再评估原生模块化或 React/Vite 迁移。
- 新契约优先：长期允许重新设计 API 契约，但每轮迁移都必须保持项目可启动、现有测试全过。

## Tech Stack

当前技术栈保持不变：

- Python 3.x
- FastAPI
- Uvicorn
- Pydantic
- SQLite
- PaddleOCR
- OpenAI-compatible LLM SDK
- PyMuPDF / python-docx / markdown / BeautifulSoup
- 原生 HTML/CSS/JavaScript

第一步不新增依赖，不创建 `src/` 代码目录，不迁移运行代码。

## Commands

开发启动：

```powershell
.\.venv\Scripts\python.exe run_server.py
```

测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

安装依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Current Architecture

当前代码的主要结构问题：

- `app.py` 同时承担页面路由、API Controller、业务编排、fallback 策略和异常处理。
- `storage.py` 同时承担数据库初始化、文件保存、路径处理、Repository 查询和业务状态更新。
- `graph_core.py`、`writer_tools.py`、`media_parser.py` 等模块包含大量混合职责。
- `static/app.js` 是前端大单体，状态、API 调用、DOM 渲染和事件绑定混在一起。
- API 响应格式不统一，前端需要适配不同错误形态。
- 领域边界已经存在，但目录结构尚未表达领域意图。

## Target Architecture

目标后端采用 Clean Architecture。依赖方向必须向内：

```text
api/controller -> service/usecase -> repository/gateway interfaces -> infrastructure implementations
```

目标领域模块：

- `shared`：配置、错误、响应、数据库连接、文件路径、安全工具。
- `settings`：LLM、ASR、图片生成 API 配置。
- `uploads`：图片、文档、媒体上传与去重。
- `knowledge`：知识条目生成、读取、删除、Markdown 渲染入口。
- `documents`：文档解析、分页、范围规划、文档到知识。
- `media`：媒体 URL 解析、转写、片段规划、媒体到知识。
- `graph`：知识图谱入网、节点管理、检索上下文。
- `mining`：挖掘项目、素材绑定、创作策略学习。
- `writer`：选题、文章生成、修订、配图、格式化、发布。
- `llm`：LLM 网关接口和具体 provider 实现。
- `ocr`：OCR 网关接口和 PaddleOCR 实现。

目标目录示意：

```text
src/
  main.py
  shared/
  settings/
  uploads/
  knowledge/
  documents/
  media/
  graph/
  mining/
  writer/
  llm/
  ocr/
```

每个领域模块内部优先使用以下结构：

```text
api.py          # FastAPI router，只处理 HTTP 翻译
service.py      # 用例编排，表达应用行为
repository.py   # 持久化适配器
schemas.py      # API request/response 模型
entities.py     # 领域实体或纯业务数据结构，按需创建
```

## API Contract

新 API 目标采用统一响应契约。该契约是未来目标，不是第一步立即生效的运行行为。

成功响应：

```json
{
  "data": {},
  "meta": {}
}
```

失败响应：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "参数不合法",
    "details": {}
  }
}
```

新 API 设计原则：

- 资源命名优先使用复数名词。
- 查询参数和响应字段使用 `camelCase`。
- 错误码使用稳定的机器可读字符串。
- API 边界负责校验外部输入。
- Service 层不依赖 FastAPI、Request、UploadFile 或 HTTPException。
- 外部服务响应必须视为不可信数据，在 gateway 或 adapter 边界校验。

旧 API 兼容策略：

- 后续重构以新架构为目标，不把完全兼容旧 API 作为硬约束。
- 在迁移完成前，每一轮代码变更必须保持项目可启动、现有测试全过。
- 是否保留旧 endpoint、增加 v2 endpoint 或让旧 endpoint 调用新 service，由具体迁移任务决定。

## Frontend Strategy

第一轮不修改前端。

后续可选路线：

- 原生模块化：保留 `static/`，拆分 `shared/api.js`、状态、视图、控制器。
- React/Vite：当交互复杂度继续上升、组件复用需求明显时再迁移。

前端重构原则：

- API 调用集中管理。
- UI 状态与 DOM 渲染分离。
- 大页面按功能域拆分。
- 不在同一轮同时重写后端契约和前端框架。

## Code Style

后端用例代码目标风格：

```python
class GenerateKnowledge:
    def __init__(self, repository, ocr_gateway, llm_gateway):
        self.repository = repository
        self.ocr_gateway = ocr_gateway
        self.llm_gateway = llm_gateway

    def execute(self, image_ids: list[int], parser_mode: str) -> dict:
        images = self.repository.get_images(image_ids)
        raw_text = self.ocr_gateway.recognize(images, parser_mode)
        result = self.llm_gateway.generate_knowledge(raw_text)
        return self.repository.save_knowledge(result, images)
```

约定：

- Controller/API 层只做 HTTP request/response 转换。
- Service/usecase 层表达业务流程，不直接读写 FastAPI 对象。
- Repository 层封装 SQLite 和文件路径细节。
- Gateway 层封装 LLM、OCR、媒体下载、公众号发布等外部系统。
- 新代码优先使用类型标注和 Pydantic 模型。
- 避免在新模块中继续扩大 `app.py`、`storage.py`、`static/app.js`。

## Testing Strategy

当前验证门槛：

- 每轮代码重构后必须运行现有测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

目标测试结构：

```text
tests/
  api/
  services/
  repositories/
  parsers/
  contract/
```

测试原则：

- 迁移模块时保留现有行为测试。
- 新 service 优先补单元测试。
- 新 API 契约补 contract 测试。
- Repository 测试使用临时目录和临时 SQLite。
- 外部 LLM/OCR/媒体服务必须 mock 或通过 gateway fake 实现隔离。

## Boundaries

Always:

- 保持项目可启动。
- 保持现有测试全过。
- 重构前先明确模块边界和接口契约。
- 新业务逻辑优先进入 service/usecase，而不是 FastAPI route。
- 新外部调用优先通过 gateway 接口隔离。

Ask first:

- 数据库 schema 破坏性变更。
- 引入新的前端框架或构建工具。
- 新增重量级依赖。
- 删除旧 API endpoint。
- 改变本地文件存储目录结构。

Never:

- 提交或写入密钥。
- 为了通过测试删除测试覆盖。
- 在无迁移策略的情况下重写核心链路。
- 把外部服务响应直接当作可信结构进入业务逻辑。
- 同一轮同时重构后端架构、前端框架和数据库 schema。

## Success Criteria

第一步完成标准：

- 存在 `docs/architecture/spec.md`。
- 存在 `docs/architecture/tasks.md`。
- 文档明确当前系统、目标架构、领域模块、API 目标契约、前端路线、测试门槛和边界。
- 未修改运行代码、前端、数据库 schema 或现有 API。

长期完成标准：

- `app.py` 缩小为 app factory、路由挂载和少量兼容层。
- 领域模块结构清楚表达系统意图。
- 核心用例可在不启动 Web 服务器、不访问真实外部服务的情况下测试。
- API 错误和成功响应具有统一契约。
- 前端 API 调用集中管理，不再由单个大文件承载主要页面所有逻辑。
- 每轮迁移都能通过现有测试。

## Open Questions

- 新 API 是否采用 `/api/v2` 前缀，还是在现有 `/api` 下逐步替换。
- 前端最终是否迁移到 React/Vite，还是只做原生模块化。
- SQLite 是否长期保留，还是在产品化阶段迁移到其他数据库。
- 旧 API endpoint 的退役策略和时间点。
