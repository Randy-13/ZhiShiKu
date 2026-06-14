# 知识酷公网内测 SaaS 网页架构迭代方案

本文记录“知识酷 / FigureLearning”从本地个人知识工作台推进到邀请制公网内测 SaaS 的当前架构目标、已完成范围和剩余工作。目标不是一次性重写产品，而是在保留本地模式可用性的前提下，补齐账号、权限、额度、任务中心、设置脱敏和关键工作流隔离。

## 当前结论

- 上线形态：邀请制公网内测 SaaS。
- 部署模式：通过 `FIGURELEARNING_DEPLOYMENT_MODE=local|cloud` 区分本地个人模式和 cloud 内测模式。
- 登录方式：邀请码注册，邮箱/用户名 + 密码登录。
- 存储：继续使用 SQLite 与本地 Markdown 文件，但核心数据写入 `owner_user_id` 和 `workspace_id`。
- 高风险能力：公众号发布、发布预检、B 站 Cookie 登录窗口、服务器路径和运行日志只对 local 或 cloud 管理员开放。
- 长任务：高成本生成和解析能力逐步进入 `/api/jobs`，不再只依赖页面局部 busy state。

## 已完成范围

### 公网内测底座

- 新增账号与会话：`users`、`invitations`、`sessions`、`workspaces`、`audit_logs`。
- 新增认证接口：`GET /api/auth/me`、`POST /api/auth/login`、`POST /api/auth/logout`、`POST /api/auth/register-with-invite`。
- 新增管理员 bootstrap 工具：`tools/bootstrap_cloud_auth.py`。
- 新增本地启动脚本：
  - `启动知识酷-本地模式.bat`
  - `启动知识酷-Cloud预览.bat`
- cloud 本地预览可关闭 Secure Cookie：`FIGURELEARNING_SESSION_COOKIE_SECURE=false`。

### 前端结构

- React/Vite 工作台已经是当前新版前端，位于 `frontend/workbench`。
- API 层已拆分为能力客户端：
  - `apiCore.ts`
  - `apiAuth.ts`
  - `apiAppShell.ts`
  - `apiCollect.ts`
  - `apiLibrary.ts`
  - `apiMine.ts`
  - `apiWriter.ts`
  - `apiSettings.ts`
  - `apiJobs.ts`
  - `apiQuota.ts`
- 工作台入口已接入 `AuthGate`、任务中心、后端 app-shell 元数据和 cloud/local 上下文。
- 移动端导航保留文字标签，任务中心可作为抽屉打开。

### 数据与权限隔离

- 原文库、重点库、视角库、媒体、挖掘项目、创作项目、视角 profile 等关键数据已写入或校验 owner/workspace。
- cloud 普通用户只能读写自己的数据。
- local 模式自动使用本地身份，保持原个人工作台体验。
- 设置页在 cloud 普通成员下隐藏本地路径、运行日志、真实 Cookie 文件路径和高风险操作。

### 额度与任务中心

- 新增 `usage_counters`、`jobs`、`job_events`。
- 已实现额度：
  - 每日链接解析。
  - 每日 LLM 生成。
  - 并发任务数。
  - 单文件上传大小。
  - 存储用量查询。
- 已任务化能力：
  - `readable_draft`：生成可读原文草稿。
  - `learn_refine`：学习区重点提炼。
  - `mine_interpret`：挖掘区视角解读。
  - `writer_topics`：创作选题。
  - `writer_article`：文章初稿。
  - `writer_revise`：文章修订。
  - `media_transcript`：音视频转写。
  - `image_generate`：创作项目批量配图。
  - `writer_image_item`：单张配图。
  - `publish_preflight`：发布预检，只做检查，不触发真实发布。
- 图片任务保留部分成功产物，不因后续失败覆盖已生成图片。

### 商业入口与基础页面

- cloud 未登录时显示内测登录/邀请码注册入口。
- 已补基础公开说明页：内测说明、隐私说明、数据保存说明。
- 已补 favicon 与基础前端元信息。

## 当前验证证据

最近一轮已通过：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_api_v2_contracts.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_app_api.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_media_parser.py -q
.\.venv\Scripts\python.exe tools\check_encoding.py
cd frontend\workbench
npm.cmd run build -- --outDir dist-codex-verify
```

Playwright smoke 已验证：

- cloud 管理员登录。
- 6 个工作区可见。
- 任务中心可打开。
- 设置页额度卡可见。
- 邀请码注册普通成员。
- 390px 移动端普通成员设置页不显示本地路径/运行日志。

截图输出：

- `output/playwright/cloud-admin-job-center.png`
- `output/playwright/cloud-admin-settings.png`
- `output/playwright/cloud-member-settings-mobile.png`

## 已知限制

- 默认 `frontend/workbench/dist` 构建时在当前 Windows 环境下遇到 `EPERM`，不能强行清理；当前源码已通过 `dist-codex-verify` 构建和 Vite dev server Playwright smoke。
- 旧 `/api` 与新 `/api/v2` 仍并存；本轮目标是公网内测底座，不是完全拆完后端领域模块。
- 数据文件物理目录仍保留现有结构，cloud 隔离主要由 owner/workspace 元数据和读写校验保障；未来可再迁移到用户目录分区。

## 剩余建议

- 版本管理：将本阶段 SaaS 架构迭代形成可读提交并推送到 `codex/web-version-agents-management`。
- 后续重构：继续把 `settings`、`uploads`、`library`、`writer`、`media` 等领域从 `app.py` / `src/api_v2.py` 拆入更清晰的 service/repository。
- 运维准备：正式公网部署前补 HTTPS、反向代理、备份策略、日志脱敏、管理员用户管理页和更完整的审计查看。
