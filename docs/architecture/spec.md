# Spec: FigureLearning 公网内测 SaaS 架构

## Objective

FigureLearning 当前目标是从本地个人知识库与创作工作台，推进到可小范围公网内测的邀请制 SaaS。架构迭代必须同时满足两件事：

- `local` 模式继续保留现有个人工作台体验。
- `cloud` 模式启用登录、权限、额度、任务队列、设置脱敏和高风险能力收口。

本规格以当前事实为准：React/Vite 工作台和 `src/` 后端入口已经存在，`app.py` 与 `/api` 旧接口仍作为兼容层保留，新公网能力优先放入 `src/` 和 `/api/v2`。

## Current Stack

- Backend: FastAPI / Uvicorn / Pydantic / SQLite。
- Frontend: React + Vite，路径为 `frontend/workbench`。
- Storage: SQLite + 本地 Markdown / 图片 / 文档 / 媒体文件。
- Auth: HttpOnly session cookie，cloud 模式默认 Secure，可通过本地预览环境变量关闭。
- Jobs: SQLite backed `jobs` / `job_events`。

## Runtime Modes

- `FIGURELEARNING_DEPLOYMENT_MODE=local`：自动注入本地用户和 workspace，不要求登录。
- `FIGURELEARNING_DEPLOYMENT_MODE=cloud`：写接口需要登录，普通成员只可访问自己的数据。
- `FIGURELEARNING_SESSION_COOKIE_SECURE=false`：仅用于本地 HTTP cloud 预览。

## Backend Shape

当前入口：

- `src/main.py`：app factory。
- `src/api_v2.py`：当前 v2 合约、auth、jobs、quota、settings、library、collect、learn、mine、writer 等公网内测能力入口。
- `src/auth.py`：用户、邀请码、session、workspace、cloud/local 上下文。
- `src/jobs.py`：任务表和事件表服务。
- `src/quotas.py`：额度检查与计数。
- `src/shared/responses.py`：统一成功响应。
- `src/shared/app_shell.py`：后端工作台结构元数据。
- `app.py`：旧接口与兼容路由，仍保留并逐步收口高风险能力。

长期方向仍是：

```text
api/controller -> service/usecase -> repository/gateway interfaces -> infrastructure implementations
```

但当前阶段允许 `src/api_v2.py` 承担适度编排，以避免一次性重写核心链路。

## Auth And Tenancy

必须存在：

- `users`
- `invitations`
- `sessions`
- `workspaces`
- `audit_logs`

认证接口：

- `GET /api/auth/me`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/register-with-invite`
- `POST /api/auth/admin/invitations`

数据规则：

- 新数据优先写入 `owner_user_id` 和 `workspace_id`。
- cloud 普通成员读取/更新/删除时必须校验 owner。
- cloud 管理员和 local 模式可查看 ownerless 历史数据。
- Cookie、数据库、媒体、运行文件、截图和本地密钥不得提交。

## Jobs And Quotas

任务接口：

- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/cancel`

当前支持的任务类型：

- `readable_draft`
- `learn_refine`
- `mine_interpret`
- `writer_topics`
- `writer_article`
- `writer_revise`
- `media_transcript`
- `image_generate`
- `writer_image_item`
- `publish_preflight`

额度策略：

- cloud 模式启用每日链接解析、每日 LLM 生成、并发任务、单文件上传和存储用量限制。
- LLM 类任务创建时即检查并消耗额度。
- `publish_preflight` 只允许 local 或 cloud 管理员创建。
- 图片生成失败必须保留部分成功图片和错误列表。

## Frontend Shape

当前前端以 React/Vite 工作台为准：

```text
frontend/workbench/src
  apiCore.ts
  apiAuth.ts
  apiAppShell.ts
  apiCollect.ts
  apiLibrary.ts
  apiMine.ts
  apiWriter.ts
  apiSettings.ts
  apiJobs.ts
  apiQuota.ts
  components/
  hooks/
  shell/
  workspaces/
```

要求：

- 页面不得直接散写 `fetch`，API 请求集中在能力客户端。
- `AuthGate` 管理 cloud 登录/注册入口。
- `JobCenter` 展示真实任务状态。
- 设置页按角色脱敏。
- 移动端导航必须保留文字标签。

## High-Risk Capability Rules

以下能力在 cloud 普通成员下必须禁止或脱敏：

- 公众号发布。
- 公众号发布预检。
- 公众号 token refresh。
- 服务器 IP 检查。
- B 站 Cookie 登录窗口。
- 真实 Cookie 文件路径。
- 本地存储路径、数据库路径、运行日志、trash 真实路径。

## Testing Gates

交付前至少运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_api_v2_contracts.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_app_api.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_media_parser.py -q
.\.venv\Scripts\python.exe tools\check_encoding.py
cd frontend\workbench
npm.cmd run build -- --outDir dist-codex-verify
```

需要 UI 验证时，优先用 Vite dev server + Playwright smoke，覆盖 cloud 登录、任务中心、设置页和移动端脱敏。

## Success Criteria For This Iteration

- cloud/local 模式可切换。
- cloud 可邀请码注册和登录。
- 普通成员数据隔离成立。
- 设置页普通成员脱敏成立。
- 高风险发布能力普通成员不可用。
- 高成本流程进入任务中心。
- 关键回归测试、编码检查、前端构建和 Playwright smoke 通过。
- 文档反映当前事实，不再描述“尚未创建 src / 尚未迁移 React/Vite”的旧状态。
