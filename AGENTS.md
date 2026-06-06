# AGENTS.md

这份文件写给后续参与本项目的编码代理，也方便维护“知识酷 / FigureLearning”的项目规则。

本项目是一个本地个人知识库与创作工作台：FastAPI 后端、React/Vite 新版工作台、SQLite 和本地 Markdown 文件共同保存素材、知识、视角、图谱和创作结果。

## 项目目标

- 以真实任务流为核心，不堆演示功能。
- 前端必须让用户知道：我在哪里、选中了什么、下一步做什么。
- 每个工作区围绕一个主要任务展开。
- 未接入真实逻辑的能力不要伪装成可用按钮。
- 优先复用旧后端已有能力，不轻易重写后端或数据库结构。
- 中文是第一体验；英文切换作为补充能力保留。

## 目录说明

- `app.py`：FastAPI 主入口，集中放主要 HTTP API。
- `storage.py`：SQLite 数据读写、本地文件路径、知识文件管理。
- `deepseek_client.py`：LLM 调用和知识/创作生成逻辑。
- `document_parser.py`：文档解析，PDF 图片页需要优先考虑视觉/API 兜底。
- `media_parser.py`、`media_transcriber.py`：音视频、B 站/抖音等链接解析和转写。
- `writer_tools.py`：创作项目、文章、配图、美编、发布检查文件管理。
- `frontend/workbench/src`：新版 React/Vite 工作台。
- `frontend/workbench/src/workspaces`：各工作区页面。
- `frontend/workbench/src/api.ts`：前端集中 API 层，页面不要直接散写 `fetch`。
- `frontend/workbench/src/i18n.ts`：中英文文案字典。
- `tests/test_app_api.py`：主要后端 API 回归测试。
- `tests/test_media_parser.py`：媒体解析和 B 站 Cookie 相关回归测试。
- `tools/check_encoding.py`：编码和乱码检查。
- `tools/playwright_cli.ps1`：本项目使用的 Playwright CLI 包装脚本，默认可配合系统 Edge。
- `tools/export_bilibili_cookies_with_playwright.js`：打开专用 Edge 登录窗口并导出 B 站 Cookie。

## 工作区原则

- 左侧核心工作区：`收集`、`学习`、`挖掘`、`创作`、`知识库`、`设置`。
- 页面首屏尽量只有一个主按钮，次要动作不要喧宾夺主。
- 按钮必须有真实效果：状态变化、路由跳转、API 调用、文件写入或明确空状态。
- 禁用按钮必须说明原因。
- 新增 API 前先检查是否已有类似接口。

## 收集区规则

- 收集区只围绕一个任务：把外部素材整理成可保存的 `原文`。
- 支持文本、截图/图片、文件、音视频、本地媒体、媒体链接、网页链接。
- 所有入口都必须进入同一个待处理队列，并展示标题/来源、类型、状态、错误信息或禁用原因。
- 链接类素材必须先做真实解析或检查，不要只把 URL 当普通文本。
- 截图、文件、音视频素材必须走真实上传或真实后端解析路径。
- “生成可读原文草稿”必须调用集中 API 层。
- 生成草稿后，用户必须能编辑标题、备注、正文 Markdown。
- 保存草稿必须真实写入原文库：数据库记录和 Markdown 文件都要更新。
- 保存后的原文不自动提炼知识、不自动入图谱、不自动进入创作流程。

## B 站链接与 Cookie 规则

- B 站字幕提取走 `yt-dlp`，优先使用 `FIGURELEARNING_YTDLP_COOKIES_FILE` 指定的 Netscape Cookie 文件。
- 默认 Cookie 文件是 `auth/bilibili.cookies.txt`，该目录受 `.gitignore` 保护，绝不能提交 Cookie 内容。
- 设置页必须提供 B 站 Cookie 检查：文件是否存在、格式是否可读、是否包含 `SESSDATA`、`DedeUserID`、`bili_jct`。
- 设置页必须提供“登录获取 Cookie”动作，调用后端接口打开专用 Edge 窗口并导出 Cookie。
- 如果 `yt-dlp --cookies-from-browser edge` 失败，不要依赖浏览器数据库读取；优先使用 Playwright 专用登录窗口导出到文件。
- 字幕转写文件路径必须使用 `storage.storage_relative(...)`，不要用 `path.relative_to(storage.ROOT)` 处理运行存储目录下的文件。
- Cookie 检查只做本地结构检查；真正字幕可下载性在收集区执行提取时验证。

## 挖掘区规则

- 挖掘区用于把原文库文件按不同视角解读为可保存的视角库文件。
- 主区域采用两栏：左侧视角管理，右侧视角解读。
- 视角由四个字段组成：视角名、定位、核心目标、立场。
- 新建/编辑视角必须使用弹窗或临时编辑控件，不要把表单常驻在第一层页面。
- 视角解读来源必须来自右侧原文库勾选文件。
- 解读必须遵循 RTFC：Rule、Target、Fact、Conclusion。
- 输出采用固定五段式：立场与标准、原文信息提炼、专属分析、风险疑问、结论建议。
- 保存视角解读必须写入后端和 Markdown 文件，并能在视角库查看。
- 视角库路径统一使用 `storage.storage_relative(...)`。

## 创作区规则

- 创作流程要能串起：知识确认、选题、初稿、修订、配图、美编、发布检查、发布。
- 创作项目优先参考 `writer_tools.py` 和旧后端能力。
- 图片生成失败不能抹掉已成功图片；应保留部分成功结果和错误列表。
- 发布预检遇到摘要过长时应自动截断到平台限制内。
- 美编排版不能只是把文字和图片堆进 HTML；优先调用可用的 API/策略生成更完整的公众号排版。
- 美编策略可以来自本机 skills，但必须审核用途，不是所有 `pm-*` skill 都是美编工具。

## 设置页规则

- 设置页保留语言、OCR/API 提取方式、API 配置、本地存储、全局运行日志入口。
- 设置页要展示依赖检查，当前至少包括 B 站 Cookie 状态。
- API 请求必须放在 `frontend/workbench/src/api.ts`。
- “登录获取 Cookie”等按钮必须调用真实后端接口，不要只做前端提示。

## 知识库规则

- 知识库分为原文库、重点库、视角库。
- 中间主区域是文件编辑区，必须能修改标题、备注、正文 Markdown。
- 保存必须真实写回后端和 Markdown 文件。
- 如果列表里只有元数据，选中文件后应自动读取 Markdown 全文再编辑。
- 右栏不要塞复杂上下文、图谱状态尾巴或无关预览。

## 后端原则

- 优先沿用 `storage.py` 和现有 FastAPI API。
- 知识文件内容以 Markdown 文件为准。
- 保存知识时同时处理 SQLite 记录、Markdown 路径和错误状态。
- 不要为前端方便绕过后端真实存储。
- 不要新增重量级依赖，除非用户明确要求。
- 文件路径保存优先使用 `storage.storage_relative(...)`。

## React / TypeScript 规则

- 页面组件放在 `frontend/workbench/src/workspaces`。
- 通用组件放在 `frontend/workbench/src/components`。
- Shell 相关组件放在 `frontend/workbench/src/shell`。
- 跨工作区类型放在 `domain.ts`。
- API 请求集中放在 `api.ts`。
- 文案放在 `i18n.ts`，新增中文 key 时也补英文 key。
- 本地 UI 状态优先留在对应 workspace。
- 派生数据用 `useMemo`；会传给子组件的事件回调用 `useCallback`。

## Playwright 规则

- 本项目优先使用 `tools/playwright_cli.ps1`，它会配置 bundled Node 的 pnpm 依赖路径。
- 默认用系统 Edge：可设置 `PLAYWRIGHT_CHANNEL=msedge`。
- Playwright 产物放在 `output/playwright/`，该目录不提交。
- 需要登录 B 站时，优先使用 `export_bilibili_cookies_with_edge.bat` 打开隔离 Edge profile，不读取用户日常 Edge 数据库。

## 编码与数据安全

- 源码、Markdown、JSON、HTML、CSS、JS 文件统一使用 UTF-8。
- 修改中文文件优先使用 `apply_patch`。
- 不要用 PowerShell 的 `Set-Content` / `Out-File` 写中文文件，除非显式 UTF-8 并确认结果。
- 不要把命令行乱码复制回源码。
- 不要回滚用户自己改过的文件。
- 不要删除用户数据目录内容，例如 `knowledge/`、`images/`、`documents/`、`media/`、`writer/`、`raw_materials/`、`knowledge.db`、`auth/`。
- 不要提交 Cookie、数据库、运行媒体、截图产物和本地密钥。

## 常用验证命令

后端语法检查：

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py tests\test_app_api.py
```

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_app_api.py
```

媒体解析测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_media_parser.py -q
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
.\启动知识酷.bat
```

导出 B 站 Cookie：

```powershell
.\export_bilibili_cookies_with_edge.bat
```

## 交付前自检

- 用户请求的页面或接口真的改到了。
- 没有留下装饰性按钮或假入口。
- 中英文切换不出现裸 key。
- 桌面宽度没有明显重叠。
- 相关后端测试或前端构建已经跑过。
- 没能跑的验证要在最终回复里说明。
