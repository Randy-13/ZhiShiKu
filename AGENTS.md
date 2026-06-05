# AGENTS.md

这份文件写给后续参与本项目的编码代理，也方便我自己修改项目规则。

本项目是“知识酷 / FigureLearning”：一个本地个人知识库与创作工作台。它用 FastAPI 做后端，用 React/Vite 做新版工作台，用 SQLite 和本地 Markdown 文件保存素材、知识、图谱和创作结果。

## 项目目标

- 以真实任务流为核心，而不是堆叠演示功能。
- 前端要让用户知道：我在哪里、选中了什么、下一步做什么。
- 每个工作区只围绕一个主要任务展开。
- 暂未接入真实逻辑的能力，不要伪装成可用按钮。
- 优先复用旧后端已有能力，不轻易重写后端或数据库结构。
- 中文是第一体验；英文切换作为补充能力保留。

## 目录说明

- `app.py`：FastAPI 主入口，集中放主要 HTTP API。
- `storage.py`：SQLite 数据读写、本地文件路径、知识文件管理。
- `schemas.py`：后端结构化模型。
- `deepseek_client.py`：LLM 调用和知识/创作生成逻辑。
- `ocr_client.py`：本地 OCR 相关逻辑。
- `document_parser.py`：文档解析。
- `media_parser.py`、`media_transcriber.py`：音视频和链接解析。
- `writer_tools.py`：创作工作区相关的项目、文章、配图、美编、发布检查文件管理。
- `frontend/workbench/src`：新版 React/Vite 工作台。
- `frontend/workbench/src/workspaces`：各个工作区页面。
- `frontend/workbench/src/api.ts`：前端集中 API 层，页面不要直接散写 `fetch`。
- `frontend/workbench/src/i18n.ts`：中英文文案字典。
- `tests/test_app_api.py`：主要后端 API 回归测试。
- `tools/check_encoding.py`：编码和乱码检查。

## 前端工作区原则

左侧导航的核心工作区是：

- `收集`：文本输入、截图拖入/粘贴、文件上传、音视频上传、媒体链接解析、网页链接解析。
- `学习`：从素材提取原文、规划分段、生成知识草稿、确认入库。
- `挖掘`：围绕已有知识进行视角挖掘和问题分析。
- `创作`：知识确认、选题、初稿、修订、配图、美编、发布检查、发布。
- `知识库`：知识文件列表与编辑。
- `设置`：语言、OCR/API 提取方式、模型、存储、全局运行日志。

页面设计规则：

- 每个工作区只保留一个主要任务。
- 每个工作区首屏尽量只有一个主按钮。
- 次要动作最多保留少数几个，不能喧宾夺主。
- 不要在一个页面同时展示所有能力。
- 不要用大量卡片把信息铺满，让用户不知道从哪开始。
- 按钮必须有真实效果：状态变化、路由跳转、API 调用、文件写入或明确空状态。
- 禁用按钮必须说明原因。

## 知识库工作区规则

知识库工作区尤其重要，后续修改必须遵守：

- 点击左侧 `知识库` 后进入知识库工作区。
- 知识库分为三库：
  - `原文库`：保存从材料输入中读取到的原文，不做任何加工。
  - `重点库`：保存从原文件提取核心知识簇后生成的重点文件。
  - `视角库`：保存针对原文件、按不同视角挖掘后生成的视角文件。
- 右栏提供三库切换，默认展示 `原文库`。
- 现阶段所有已有文件先归入 `原文库`，不要私自改动底层分类存储。
- 右栏不要放预览、图谱状态、入图谱尾部信息或其它复杂上下文。
- 中间主区域是文件编辑区。
- 中间编辑区必须能修改选中文件的：
  - 标题
  - 备注
  - 正文 Markdown
- 保存必须真实写回后端：
  - 更新数据库里的标题/备注等字段。
  - 更新对应 Markdown 文件正文。
- 如果列表里只有知识元数据，选中文件后应自动读取 Markdown 全文再编辑。

## 后端原则

- 优先沿用现有 FastAPI API 和 `storage.py` 能力。
- 新增 API 前先检查是否已有类似接口。
- 知识文件内容以 Markdown 文件为准。
- 保存知识时要同时处理：
  - SQLite 记录
  - Markdown 文件路径
  - 错误状态
- 不要为了前端方便绕过后端真实存储。
- 不要新增重量级依赖，除非用户明确要求。

## React / TypeScript 规则

- 页面组件放在 `frontend/workbench/src/workspaces`。
- 通用组件放在 `frontend/workbench/src/components`。
- Shell 相关组件放在 `frontend/workbench/src/shell`。
- 跨工作区类型放在 `domain.ts`。
- API 请求集中放在 `api.ts`。
- 文案放在 `i18n.ts`，新增中文 key 时也要补英文 key。
- 本地 UI 状态优先留在对应 workspace。
- 跨工作区状态只保留必要内容，例如当前素材、当前知识、当前作品、语言、任务状态。
- 派生数据用 `useMemo`。
- 事件回调用 `useCallback`，尤其是会传给子组件的操作。

## 编码规则

- 所有源码、Markdown、JSON、HTML、CSS、JS 文件统一使用 UTF-8。
- 修改中文文件时优先使用 `apply_patch`。
- 不要用 PowerShell 的 `Set-Content` / `Out-File` 写入中文文件，除非显式指定 UTF-8 并确认结果。
- 不要把命令行输出里的乱码复制回源码。
- 不要回滚用户自己改过的文件。
- 不要做无关重构。
- 不要删除用户数据目录里的内容，例如：
  - `knowledge/`
  - `images/`
  - `documents/`
  - `media/`
  - `writer/`
  - `raw_materials/`
  - `knowledge.db`

## 常用验证命令

后端语法检查：

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py tests\test_app_api.py
```

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_app_api.py
```

只跑某个测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_app_api.py -k 测试名片段 -q
```

前端构建：

```powershell
cd frontend\workbench
npm.cmd run build
```

编码检查：

```powershell
.\.venv\Scripts\python.exe tools\check_encoding.py
```

启动后端：

```powershell
.\.venv\Scripts\python.exe run_server.py
```

或使用：

```powershell
.\重启知识酷后端.bat
```

## 开发注意事项

- 浏览器页面空白时，先检查 Vite 构建和 FastAPI 是否加载了最新前端资源。
- 新增后端 API 后，如果浏览器仍报 404，优先重启后端。
- 修改截图粘贴、上传、OCR、媒体解析链路时，要覆盖真实文件或真实请求路径，不要只做本地假状态。
- 修改创作流程时，要尽量参考旧后端和 `writer_tools.py`，保证知识确认、选题、初稿、修订、配图、美编、发布检查、发布可以连起来。
- 设置页要保留全局运行日志入口。
- 设置页要保留“本地 OCR 提取 / API 视觉提取”的可配置项。

## 交付前自检

交付前至少确认：

- 用户请求的页面或接口真的改到了。
- 没有留下装饰性按钮或假入口。
- 中英文切换不会出现裸 key。
- 桌面宽度下没有明显重叠。
- 相关后端测试或前端构建已经跑过。
- 如果没能跑某项验证，要在最终回复里说明。
