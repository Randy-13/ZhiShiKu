# 知识酷公网内测 SaaS 网页架构迭代方案

> 本文由 `project-dev-flow` 复查后形成，用于后续公网内测版本开发参考。目标是把当前本地个人知识工作台推进到可小范围公网内测的 SaaS 架构，而不是一次性重写产品。

## Summary

当前网页已经有成熟工作台雏形，但还不是可上公网的 SaaS 架构。最大问题不是页面视觉，而是前端工作流编排、后端能力边界、API 契约、任务状态、用户/权限上下文还没有形成稳定架构。

下一版应先做“公网内测架构底座 + 前端编排瘦身”，不要急着重做全部 UI。

默认决策：

- 上线形态：邀请制内测 SaaS。
- 登录方式：邀请码 + 邮箱/用户名 + 密码。
- 额度策略：必须拦截，先做简单每日次数、上传大小、存储空间和并发任务限制。
- 数据库：继续用 SQLite 支撑内测，但 schema 按未来多租户设计。
- 本地模式：保留当前个人工作台体验，通过 `FIGURELEARNING_DEPLOYMENT_MODE=local|cloud` 区分。

## Key Findings

- 前端已有好基础：`workspaces/`、`components/`、`shell/`、`api.ts` 分层存在，工作区心智也基本稳定。
- `App.tsx` 约 1446 行，承担路由、全局库、上传、生成、创作、设置、活动日志等编排，是公网化前端最大的架构压力点。
- `api.ts` 约 1295 行，同时做请求、类型适配、payload 映射、错误兜底和 legacy/v2 兼容，未来加登录、任务、额度会继续膨胀。
- `styles.css` 约 2052 行，所有页面样式集中，适合快速迭代，但不利于公网版做登录页、任务中心、账户页、设置脱敏等新表面。
- 后端 `app.py` 仍是大单体入口，`src/api_v2.py` 已经开始新契约，但旧 `/api` 和新 `/api/v2` 并存，能力边界还没真正完成迁移。
- `src/shared/app_shell.py` 已有后端导航/能力注册，但前端仍在 `App.tsx` 硬编码 nav，存在“双份产品结构真相”。
- `docs/architecture` 已有架构文档，但部分内容滞后：文档还提到“第一轮不创建 src、不迁移 React/Vite”，而当前项目已经有 `src/main.py`、`api_v2.py` 和 React/Vite 工作台。
- Playwright 审计显示桌面 6 个工作区可用，移动端导航只有图标，文本不可见，作为公网产品会降低可理解性。
- 设置页暴露本地路径、Cookie、运行日志和 API 配置，内测 SaaS 必须按角色和部署模式脱敏。

## Next Version Architecture Plan

- 建立部署模式：新增 `local|cloud` 的运行模式概念，`local` 保持当前个人工作台体验，`cloud` 启用登录、权限、额度、设置脱敏和任务队列。
- 前端先拆 `App.tsx` 编排，不重写视觉：抽出 `useWorkspaceRoute`、`useLibraryRail`、`useCollectFlow`、`useWriterFlow`、`useActivityLog`，让 `App.tsx` 只负责组合 shell 和 workspace。
- API 层拆为能力客户端：`authApi`、`libraryApi`、`collectApi`、`writerApi`、`settingsApi`、`jobsApi`，保留统一 `requestJson` 和错误处理。
- 让后端成为产品结构唯一来源：前端 nav/workspace 元信息优先从 `/api/v2/app-shell` 读取，本地 fallback 才使用硬编码。
- 新增 `AuthGate` 和账户上下文：未登录显示内测登录/邀请码页，登录后进入工作台；`local` 模式自动注入本地用户。
- 新增任务中心：把媒体解析、LLM 生成、图片生成、发布检查等长任务统一成 `jobs` 状态，不再只靠页面局部 busy state。
- 设置页分层：普通用户只看语言、额度、自己的 Key 状态和脱敏依赖状态；管理员或 local 模式才看本地路径、Cookie 文件、运行日志。
- 更新架构文档：把 `docs/architecture/spec.md` 和 `tasks.md` 修正为当前事实，明确 React/Vite 已是新版工作台，`src/` 已是迁移目标入口。
- 移动端先做结构修补：导航图标加短标签，右侧知识列表默认折叠，任务状态进入顶部或底部抽屉。
- 后端按最低风险顺序迁移：先 `auth/settings/jobs`，再 `uploads/library`，最后才动 `writer/media/graph` 这些复杂链路。

## Public Beta Foundation

公网内测版必须先补齐以下底座：

- 新增账号模型：`users`、`invitations`、`sessions`、`workspaces`、`audit_logs`。
- 密码使用 Python 标准库 `hashlib.pbkdf2_hmac` 加盐哈希，避免首版新增重量依赖。
- 登录后使用 HttpOnly session cookie；`cloud` 模式下 cookie 设置 `Secure`、`SameSite=Lax`。
- 所有 `/api` 与 `/api/v2` 写接口默认需要登录；公开接口只保留健康检查、登录、登出、邀请码验证、前端静态资源。
- 新增当前用户接口：`GET /api/auth/me`、`POST /api/auth/login`、`POST /api/auth/logout`、`POST /api/auth/register-with-invite`。
- 管理员能力先做最小集：创建邀请码、禁用用户、查看用户用量和最近错误。

## Data And File Isolation

- 新增 `owner_user_id`、`workspace_id` 到知识、source_files、media_sources、mining、writer project、perspective profiles 等核心表。
- 新数据必须写入当前用户 workspace；查询、读取、更新、删除都必须带 owner 过滤。
- 运行文件按用户隔离：
  - `data/runtime/users/{user_id}/images`
  - `data/runtime/users/{user_id}/documents`
  - `data/runtime/users/{user_id}/media`
  - `data/runtime/users/{user_id}/raw_materials`
  - `data/runtime/users/{user_id}/knowledge`
  - `data/runtime/users/{user_id}/mining`
  - `data/runtime/users/{user_id}/writer`
- `local` 模式自动使用一个内置本地用户，保持现有单人体验不需要登录。
- 旧数据迁移为本地默认用户所有；迁移只补字段和归属，不移动用户原始数据目录。
- 所有 `resolve_root_path`、文件读取、下载、删除、trash 操作必须校验路径属于当前用户目录或当前 workspace。

## Quota And Jobs

- 新增 `usage_counters`、`jobs`、`job_events` 表。
- 首版额度：
  - 每用户每日链接解析 30 次。
  - 每用户每日 LLM 生成 50 次。
  - 单文件上传最大 100 MB。
  - 每用户总存储默认 2 GB。
  - 每用户同时运行任务最多 2 个。
- 高成本接口改成任务化或支持任务化：媒体解析、字幕/ASR、原文生成、重点提炼、视角解读、创作生成、图片生成、发布预检。
- 新增任务接口：
  - `POST /api/jobs` 创建任务，payload 包含 `kind` 和参数。
  - `GET /api/jobs/{job_id}` 查询状态。
  - `GET /api/jobs` 查询当前用户任务列表。
  - `POST /api/jobs/{job_id}/cancel` 取消排队或可中断任务。
- 前端任务队列从“显示状态”升级为真实任务中心：排队中、处理中、成功、失败、可重试、已取消。
- 失败结果必须保留部分成功产物，例如图片生成部分成功不能被后续失败覆盖。

## Cloud Settings UX

- `cloud` 模式下普通用户设置页只显示：
  - 语言。
  - 文本提取方式。
  - 额度/存储用量。
  - 自己的 API Key 配置状态，Key 仅可写入、不可读回。
  - B 站 Cookie 是否配置，不展示服务器路径和完整 cookie 信息。
- 本地路径、数据库路径、trash 真实路径、运行日志、Cookie 文件路径只对管理员或 `local` 模式展示。
- API/ASR/图片配置改成用户级或管理员级两层：
  - 用户未配置时使用管理员默认模型配置。
  - 用户配置自己的 Key 时只影响本人任务。
- 公众号发布 Token、B 站 Cookie、浏览器 profile、服务端日志必须从普通用户 API 响应中移除或脱敏。
- 错误响应统一返回用户可理解消息；堆栈、本地路径、命令参数只写入服务端日志和审计日志。

## Commercial Entry UX

- 首页在 `cloud` 模式改成登录前营销/申请入口；登录后进入工作台。
- 收集页首屏调整为“一输入即产出”：
  - 大输入区支持链接、文本、上传。
  - 一个主按钮“生成可读原文”。
  - 任务结果页展示摘要、原文 Markdown、来源信息、下一步“提炼重点/进入创作”。
- 移动端导航保留文字标签，避免只有图标。
- 右侧知识列表在窄屏默认折叠；桌面可保留但降低视觉权重。
- 修复 `favicon.ico` 404，并补基础页面 title、description、错误页、404 页。
- 增加“内测说明/隐私说明/数据保存说明”，明确上传内容、模型调用和第三方平台 Cookie 的边界。

## Test Plan

- 前端构建：`cd frontend\workbench && npm.cmd run build`
- 后端回归：`.\.venv\Scripts\python.exe -m pytest tests\test_app_api.py`
- v2 契约：`.\.venv\Scripts\python.exe -m pytest tests\test_api_v2_contracts.py`
- 媒体回归：`.\.venv\Scripts\python.exe -m pytest tests\test_media_parser.py -q`
- Playwright 检查：登录页、收集页、任务中心、设置页，分别测 1440px 和 390px。
- 架构验收：`App.tsx` 不再直接承载所有业务流程，新增公网能力必须通过 auth/user/job 上下文，而不是散落在工作区组件里。

## Assumptions

- 下一版本目标仍是邀请制内测 SaaS，不是完全公开注册。
- 不引入重型前端状态库，先用 hooks 和能力客户端降低复杂度。
- 不一次性重写 `app.py`，只把公网必需的新能力放进 `src/` 新结构。
- 保留本地个人模式，避免公网化改造破坏当前日常工作流。
- 管理员默认模型配置可以被普通用户使用，但必须受额度限制。
- B 站 Cookie、公众号发布、浏览器自动化属于高风险能力，`cloud` 模式默认仅管理员可配置，普通用户只看脱敏可用状态。
