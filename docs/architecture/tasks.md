# FigureLearning 公网内测 SaaS 架构任务清单

本清单记录当前公网内测架构迭代的完成状态。长期领域拆分仍会继续，但本阶段验收重点是 cloud/local 模式、登录、权限隔离、额度、任务中心、设置脱敏和关键体验验证。

## Phase 1: 版本与模式底座

- [x] 创建公网内测架构方案文档。
- [x] 保留 `codex/web-version-agents-management` 分支作为本阶段工作分支。
- [x] 新增 `FIGURELEARNING_DEPLOYMENT_MODE=local|cloud`。
- [x] 新增本地 cloud 预览 Secure Cookie 开关。
- [x] 新增管理员 bootstrap 命令：`tools/bootstrap_cloud_auth.py`。
- [x] 新增本地/cloud 启动 bat。

## Phase 2: Auth / Workspace / Quota / Jobs

- [x] 新增用户、邀请码、session、workspace、audit log schema。
- [x] 新增 `src/auth.py`。
- [x] 新增 auth API：`/api/auth/me`、login、logout、register-with-invite。
- [x] 新增 `src/quotas.py` 与 quota status API。
- [x] 新增 `src/jobs.py` 与 `/api/jobs`。
- [x] 支持 job list/detail/create/cancel。
- [x] 支持并发任务限制。
- [x] 支持每日链接解析和每日 LLM 额度。

## Phase 3: Frontend Orchestration

- [x] 拆分前端 API 能力客户端。
- [x] 新增 `AuthGate`。
- [x] 新增 `JobCenter`。
- [x] 工作台从 `/api/v2/app-shell` 获取结构元数据。
- [x] 移动端导航保留文字。
- [x] favicon 和基础公开页面已补。

## Phase 4: Cloud Data Isolation

- [x] 原文库 owner/workspace 写入与读取过滤。
- [x] 重点库 owner/workspace 写入与读取过滤。
- [x] 视角库 owner/workspace 写入与读取过滤。
- [x] 视角 profile owner/workspace 隔离。
- [x] 媒体 source owner 隔离。
- [x] 挖掘项目 owner/workspace 隔离。
- [x] 创作项目 owner/workspace 隔离。
- [x] 旧 writer 路径在 cloud 下按项目归属收口。

## Phase 5: Settings And High-Risk Capability Controls

- [x] cloud 普通成员设置页隐藏本地路径、运行日志和 trash 真实路径。
- [x] B 站 Cookie 状态普通成员脱敏。
- [x] B 站 Cookie 登录窗口仅 local/admin。
- [x] 公众号发布、发布预检、IP 检查、token refresh 限制为 local/admin。
- [x] v2 writer publish/preflight 限制为 local/admin。

## Phase 6: High-Cost Flow Jobification

- [x] `readable_draft`：生成可读原文草稿。
- [x] `learn_refine`：重点提炼。
- [x] `mine_interpret`：视角解读。
- [x] `writer_topics`：创作选题。
- [x] `writer_article`：文章初稿。
- [x] `writer_revise`：文章修订。
- [x] `media_transcript`：音视频转写。
- [x] `image_generate`：批量配图。
- [x] `writer_image_item`：单张配图。
- [x] `publish_preflight`：发布预检任务化，不触发真实发布。
- [x] 图片部分成功结果保留。

## Phase 7: Verification

- [x] v2 contract tests。
- [x] legacy app API tests。
- [x] media parser tests。
- [x] encoding check。
- [x] frontend production build to `dist-codex-verify`。
- [x] cloud mode Playwright smoke with current Vite source。

已通过的关键命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_api_v2_contracts.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_app_api.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_media_parser.py -q
.\.venv\Scripts\python.exe tools\check_encoding.py
cd frontend\workbench
npm.cmd run build -- --outDir dist-codex-verify
```

Playwright smoke 覆盖：

- 管理员登录。
- 6 个工作区。
- 任务中心。
- 设置页额度卡。
- 邀请码注册普通成员。
- 移动端普通成员设置页脱敏。

## Known Follow-Ups

- [ ] 解决当前 Windows 环境下默认 `frontend/workbench/dist` 构建清理时的 `EPERM`，或调整验证/发布流程显式使用干净 outDir。
- [ ] 将本阶段变更整理成提交并推送到 `codex/web-version-agents-management`。
- [ ] 后续继续做领域拆分：settings、uploads、library、writer、media、graph。
- [ ] 正式公网部署前补 HTTPS、反向代理、备份、日志脱敏、管理员用户管理 UI 和更完整的审计查看。
