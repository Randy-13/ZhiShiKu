# 网页 API 接口与模型调用映射

本文档只整理新版 React/Vite 工作台中实际由 `frontend/workbench/src/api*.ts` 调用的接口。未被网页 API 层调用的后端接口不列入本文档。

## 模型标注口径

| 标注 | 含义 | 配置来源 |
| --- | --- | --- |
| 无模型调用 | 普通读写、文件上传、状态查询、发布自动化或配置保存，不直接触发 AI 模型。 | 不适用 |
| 当前文本模型 | 通过 `deepseek_client.py` 调用 OpenAI-compatible Chat Completions 或兼容 Anthropic 的文本接口。 | `api_settings.py` / `/api/v2/settings/api`，运行时由 `deepseek_client.current_setting()` 解析；默认模板包括 DeepSeek、OpenAI、OpenAI 兼容中转、MiniMax。 |
| 当前图片模型 | 通过 `writer_tools.generate_image()` 或其上层封装生成图片。 | `image_api_settings.py` / `/api/v2/settings/image`；默认模板包括 OpenAI 图片 API、OpenAI 兼容图片中转、MiniMax、自定义端点。 |
| 当前 ASR 模型 | 通过 `media_transcriber.py` 转写音频。 | ASR 设置接口 `/api/v2/settings/asr`；可能是本地 Whisper、OpenAI-compatible、MiniMax 或 DashScope。 |

## 通用与鉴权

前端统一通过 `apiCore.ts` 的 `requestJson()` 调用 `fetch()`，`API_BASE` 目前为空，表示同源请求；401 会触发登录失效通知。

| 前端调用位置 | 方法 | 后端路径 | 用途 | 模型调用 | 后端主要落点 |
| --- | --- | --- | --- | --- | --- |
| `apiAppShell.ts` | GET | `/api/v2/app-shell` | 获取工作台导航、工作区入口和全局库信息。 | 无模型调用 | `src/api_v2.py::app_shell` |
| `apiAuth.ts` | GET | `/api/auth/me` | 获取当前登录上下文。 | 无模型调用 | `src/api_v2.py::auth_me` |
| `apiAuth.ts` | POST | `/api/auth/login` | 登录。 | 无模型调用 | `src/api_v2.py::auth_login` |
| `apiAuth.ts` | POST | `/api/auth/register-with-invite` | 使用邀请码注册。 | 无模型调用 | `src/api_v2.py::auth_register_with_invite` |
| `apiAuth.ts` | POST | `/api/auth/logout` | 退出登录。 | 无模型调用 | `src/api_v2.py::auth_logout` |
| `apiAuth.ts` | GET | `/api/auth/admin/users` | 管理员查看用户列表。 | 无模型调用 | `src/api_v2.py::auth_admin_users` |
| `apiAuth.ts` | GET | `/api/auth/admin/invitations` | 管理员查看邀请码列表。 | 无模型调用 | `src/api_v2.py::auth_admin_invitations` |
| `apiAuth.ts` | POST | `/api/auth/admin/invitations` | 创建邀请码。 | 无模型调用 | `src/api_v2.py::auth_admin_create_invitation` |
| `apiAuth.ts` | POST | `/api/auth/admin/users/{user_id}/status` | 更新用户启用/禁用状态。 | 无模型调用 | `src/api_v2.py::auth_admin_update_user_status` |

## 收集区

| 前端调用位置 | 方法 | 后端路径 | 用途 | 模型调用 | 后端主要落点 |
| --- | --- | --- | --- | --- | --- |
| `apiCollect.ts` | POST | `/api/images` | 上传截图/图片素材。 | 无模型调用 | `app.py::upload_images` |
| `apiCollect.ts` | POST | `/api/images/paste` | JSON data URL 方式上传粘贴图片，作为 multipart 上传失败后的兜底。 | 无模型调用 | `app.py::upload_pasted_images` |
| `apiCollect.ts` | POST | `/api/files` | 上传文件素材。 | 无模型调用 | `app.py::upload_source_files` |
| `apiCollect.ts` | POST | `/api/files/page-info` | 获取文件页数、可解析页范围等信息。 | 无模型调用 | `app.py::source_file_page_info` |
| `apiCollect.ts` | POST | `/api/media/upload` | 上传本地音视频素材。 | 无模型调用 | `app.py::upload_media_files` |
| `apiCollect.ts` | POST | `/api/media/resolve-url` | 解析 B 站、抖音等媒体链接并生成媒体记录。 | 无模型调用；可能调用平台解析/下载工具。 | `app.py::resolve_media_url`、`media_parser.py` |
| `apiCollect.ts` | POST | `/api/v2/collect/inspect-link` | 检查网页链接类型、标题、可访问状态和推荐提取方式。 | 无模型调用 | `src/api_v2.py::inspect_link` |
| `apiCollect.ts` | POST | `/api/v2/collect/browser-extract-link` | 通过浏览器/页面读取链路提取网页正文草稿。 | 无模型调用 | `src/api_v2.py::browser_extract_link` |
| `apiCollect.ts` | POST | `/api/media/transcript` | 为媒体素材生成或补齐转写文本。 | 当前 ASR 模型；若平台已有字幕则优先使用字幕，不一定触发 ASR。 | `app.py::transcribe_media`、`media_transcriber.py` |
| `apiCollect.ts` | POST | `/api/v2/collect/raw-markdown` | 把队列素材保存为原文库 Markdown。 | 可能调用当前文本模型；截图/文档在 `ai_vision` 或 OCR 失败兜底时可能调用视觉文本能力，普通文本/链接通常不触发。 | `src/api_v2.py::collect_raw_markdown`、`_extract_queue_text`、`_polish_raw_material` |
| `apiCollect.ts` | POST | `/api/v2/collect/readable-draft` | 从队列素材生成可编辑的可读原文草稿。 | 可能调用当前文本模型；用于原文润色、截图视觉识别或文档视觉兜底。 | `src/api_v2.py::collect_readable_draft`、`_build_readable_draft` |
| `apiCollect.ts` | POST | `/api/v2/collect/raw-file` | 保存用户确认后的原文草稿。 | 无模型调用 | `src/api_v2.py::collect_raw_file` |
| `apiCollect.ts` | POST | `/api/v2/learn/refine-knowledge-cluster` | 将多个原文库文件提炼为重点库草稿。 | 当前文本模型 | `src/api_v2.py::learn_refine_knowledge_cluster`、`deepseek_client.generate_knowledge_from_text` |
| `apiCollect.ts` | POST | `/api/v2/learn/focus-file` | 保存重点库 Markdown 文件。 | 无模型调用 | `src/api_v2.py::learn_save_focus_file` |
| `apiCollect.ts` | POST | `/api/knowledge/draft-meta` | 根据草稿正文生成标题和备注。 | 当前文本模型 | `app.py::generate_knowledge_draft_meta`、`deepseek_client.generate_knowledge_draft_meta` |
| `apiCollect.ts` | POST | `/api/materials/readable-document` | 从图片、文件、媒体生成可读原文预览。 | 可能调用当前文本模型；用于清洗正文，截图/图片页可能触发视觉识别。 | `app.py::readable_document`、`deepseek_client.clean_readable_document` |
| `apiCollect.ts` | POST | `/api/knowledge/generate` | 从图片素材生成知识条目。 | 当前文本模型；图片素材在 `ai_vision` 时调用视觉识别。 | `app.py::generate_knowledge`、`deepseek_client.recognize_screenshots_with_ai`、`generate_knowledge_from_text` |
| `apiCollect.ts` | POST | `/api/knowledge/generate-from-files` | 从文件素材生成知识条目。 | 当前文本模型 | `app.py::generate_knowledge_from_files`、`deepseek_client.generate_knowledge_from_text` |
| `apiCollect.ts` | POST | `/api/knowledge/generate-from-media` | 从媒体转写生成知识条目。 | 当前文本模型；转写缺失时可能先触发当前 ASR 模型。 | `app.py::generate_knowledge_from_media`、`deepseek_client.generate_knowledge_from_text`、`media_transcriber.py` |

## 知识库、学习与挖掘

| 前端调用位置 | 方法 | 后端路径 | 用途 | 模型调用 | 后端主要落点 |
| --- | --- | --- | --- | --- | --- |
| `apiLibrary.ts` | GET | `/api/v2/libraries/{library}/files` | 列出原文库、重点库、视角库文件。 | 无模型调用 | `src/api_v2.py::library_files` |
| `apiLibrary.ts` | GET | `/api/v2/libraries/{library}/file?markdown_path=...` | 读取库文件全文。 | 无模型调用 | `src/api_v2.py::library_file` |
| `apiLibrary.ts` | POST | `/api/v2/libraries/{library}/file?markdown_path=...` | 修改库文件标题、备注和 Markdown 正文。 | 无模型调用 | `src/api_v2.py::update_library_file` |
| `apiLibrary.ts` | DELETE | `/api/v2/libraries/{library}/file?markdown_path=...` | 删除库文件并移入回收站。 | 无模型调用 | `src/api_v2.py::delete_library_file` |
| `apiLibrary.ts` | GET | `/api/knowledge` | 旧知识列表兼容接口。 | 无模型调用 | `app.py::list_knowledge` |
| `apiLibrary.ts` | GET | `/api/knowledge/{knowledge_id}` | 读取旧知识条目。 | 无模型调用 | `app.py::read_knowledge` |
| `apiLibrary.ts` | POST | `/api/knowledge/{knowledge_id}` | 更新旧知识条目。 | 无模型调用 | `app.py::update_knowledge` |
| `apiLibrary.ts` | POST | `/api/knowledge/delete-not-ingested` | 删除未入库知识条目。 | 无模型调用 | `app.py::delete_knowledge_not_ingested` |
| `apiLibrary.ts` | POST | `/api/knowledge/commit-draft` | 提交知识草稿到后端存储。 | 无模型调用 | `app.py::commit_knowledge_draft` |
| `apiMine.ts` | GET | `/api/v2/mine/perspectives` | 列出视角配置。 | 无模型调用 | `src/api_v2.py::mine_perspectives` |
| `apiMine.ts` | POST | `/api/v2/mine/perspectives` | 新建或更新视角配置。 | 无模型调用 | `src/api_v2.py::mine_save_perspective` |
| `apiMine.ts` | DELETE | `/api/v2/mine/perspectives/{profile_id}` | 删除视角配置。 | 无模型调用 | `src/api_v2.py::mine_delete_perspective` |
| `apiMine.ts` | POST | `/api/v2/mine/interpret` | 对选中原文按视角生成五段式解读。 | 当前文本模型 | `src/api_v2.py::mine_interpret`、`deepseek_client.interpret_from_perspective` |
| `apiMine.ts` | POST | `/api/v2/mine/expand-interpretation` | 搜索外部资料并直接扩展视角解读。 | 当前文本模型；还会读取外部网页作为资料。 | `src/api_v2.py::mine_expand_interpretation`、`deepseek_client.expand_perspective_interpretation` |
| `apiMine.ts` | POST | `/api/v2/mine/expand-preview` | 预览扩展解读会使用的外部资料。 | 无模型调用；主要搜索和读取外部来源。 | `src/api_v2.py::mine_expand_preview` |
| `apiMine.ts` | POST | `/api/v2/mine/expand-merge` | 将确认后的外部资料合并进当前视角解读。 | 当前文本模型 | `src/api_v2.py::mine_expand_merge`、`_merge_perspective_expansion` |
| `apiMine.ts` | POST | `/api/v2/mine/perspective-file` | 保存视角解读为视角库文件。 | 无模型调用 | `src/api_v2.py::mine_save_perspective_file` |

## 创作区

| 前端调用位置 | 方法 | 后端路径 | 用途 | 模型调用 | 后端主要落点 |
| --- | --- | --- | --- | --- | --- |
| `apiWriter.ts` | GET | `/api/writer/session` | 旧创作会话初始化。 | 无模型调用 | `app.py::writer_session` |
| `apiWriter.ts` | POST | `/api/writer/topics` | 旧流程生成选题。 | 当前文本模型 | `app.py::writer_topics`、`deepseek_client.generate_topics` |
| `apiWriter.ts` | POST | `/api/writer/article` | 旧流程生成公众号文章初稿。 | 当前文本模型 | `app.py::writer_article`、`deepseek_client.generate_wechat_article` |
| `apiWriter.ts` | POST | `/api/writer/revise` | 旧流程修订文章。 | 当前文本模型 | `app.py::writer_revise`、`deepseek_client.revise_wechat_article` |
| `apiWriter.ts` | POST | `/api/writer/publish/preflight` | 旧流程公众号发布预检。 | 无模型调用；会检查微信发布配置和素材。 | `app.py::writer_publish_preflight`、`writer_tools.publish_preflight` |
| `apiWriter.ts` | GET | `/api/writer/projects` | 列出创作项目。 | 无模型调用 | `app.py::writer_projects` |
| `apiWriter.ts` | GET | `/api/writer/writing-strategies` | 列出写作策略。 | 无模型调用 | `app.py::writer_writing_strategies` |
| `apiWriter.ts` | POST | `/api/writer/writing-strategies` | 保存写作策略。 | 无模型调用 | `app.py::writer_writing_strategy_save` |
| `apiWriter.ts` | DELETE | `/api/writer/writing-strategies/{strategy_id}` | 删除写作策略。 | 无模型调用 | `app.py::writer_writing_strategy_delete` |
| `apiWriter.ts` | GET | `/api/writer/projects/{project_id}` | 读取创作项目状态。 | 无模型调用 | `app.py::writer_project_read` |
| `apiWriter.ts` | POST | `/api/writer/projects` | 创建创作项目。 | 无模型调用 | `app.py::writer_project_create`、`writer_tools.create_project` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/knowledge` | 确认项目素材/知识来源。 | 无模型调用 | `app.py::writer_project_confirm_knowledge` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/topics` | 为项目生成选题。 | 当前文本模型 | `app.py::writer_project_generate_topics`、`deepseek_client.generate_topics` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/topic` | 选择项目选题。 | 无模型调用 | `app.py::writer_project_select_topic` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/strategies` | 保存项目写作/美编策略。 | 无模型调用 | `app.py::writer_project_update_strategies` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/draft` | 生成项目文章初稿。 | 当前文本模型 | `app.py::writer_project_generate_draft`、`deepseek_client.generate_wechat_article` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/revise` | 按指令修订项目文章。 | 当前文本模型 | `app.py::writer_project_revise`、`deepseek_client.revise_wechat_article` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/image-suggestions` | 为文章生成封面/正文配图提示词。 | 当前文本模型 | `app.py::writer_project_image_suggestions`、`deepseek_client.suggest_writer_images` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/images` | 批量生成项目封面和正文图。 | 当前图片模型 | `app.py::writer_project_generate_images`、`writer_tools.generate_writer_images` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/images/item` | 生成单张封面或正文图。 | 当前图片模型 | `app.py::writer_project_generate_image_item`、`writer_tools.generate_writer_image_item` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/format` | 生成公众号美编 HTML。 | 可能调用当前文本模型；优先内置模板渲染，配置为 API formatter 时调用 `deepseek_client.design_wechat_article_html`。 | `app.py::writer_project_format`、`writer_tools.format_article` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/confirm-design` | 确认美编结果。 | 无模型调用 | `app.py::writer_project_confirm_design` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/publish/preflight` | 项目公众号发布预检。 | 无模型调用；会检查微信发布配置和素材。 | `app.py::writer_project_publish_preflight` |
| `apiWriter.ts` | POST | `/api/writer/projects/{project_id}/publish` | 发布到微信公众号草稿箱。 | 无模型调用；调用微信发布 API。 | `app.py::writer_project_publish`、`writer_tools.publish_draft` |
| `apiWriter.ts` | GET | `/api/writer/file?path=...` | 读取创作项目产物文件。 | 无模型调用 | `app.py::writer_file` |

## 小红书

| 前端调用位置 | 方法 | 后端路径 | 用途 | 模型调用 | 后端主要落点 |
| --- | --- | --- | --- | --- | --- |
| `apiXhs.ts` | GET | `/api/xhs/account-profiles` | 列出小红书账号画像。 | 无模型调用 | `app.py::xhs_account_profiles` |
| `apiXhs.ts` | POST | `/api/xhs/account-profiles` | 创建账号画像。 | 无模型调用 | `app.py::xhs_account_profile_create`、`xhs_tools.create_account_profile` |
| `apiXhs.ts` | PUT | `/api/xhs/account-profiles/{profile_id}` | 更新账号画像。 | 无模型调用 | `app.py::xhs_account_profile_update` |
| `apiXhs.ts` | DELETE | `/api/xhs/account-profiles/{profile_id}` | 删除账号画像。 | 无模型调用 | `app.py::xhs_account_profile_delete` |
| `apiXhs.ts` | GET | `/api/xhs/carousel-strategies` | 列出轮播策略。 | 无模型调用 | `app.py::xhs_carousel_strategies` |
| `apiXhs.ts` | POST | `/api/xhs/carousel-strategies` | 保存轮播策略。 | 无模型调用 | `app.py::xhs_carousel_strategy_save` |
| `apiXhs.ts` | DELETE | `/api/xhs/carousel-strategies/{strategy_id}` | 删除轮播策略。 | 无模型调用 | `app.py::xhs_carousel_strategy_delete` |
| `apiXhs.ts` | GET | `/api/xhs/projects` | 列出小红书项目。 | 无模型调用 | `app.py::xhs_projects` |
| `apiXhs.ts` | GET | `/api/xhs/projects/{project_id}` | 读取小红书项目状态。 | 无模型调用 | `app.py::xhs_project_read` |
| `apiXhs.ts` | POST | `/api/xhs/projects` | 创建小红书图文项目。 | 无模型调用 | `app.py::xhs_project_create`、`xhs_tools.create_project` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/knowledge` | 确认项目素材。 | 无模型调用 | `app.py::xhs_project_knowledge` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/topics` | 生成小红书选题。 | 当前文本模型 | `app.py::xhs_project_topics`、`xhs_tools.generate_topics`、`deepseek_client.parse_json_model` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/topic` | 选择小红书选题。 | 无模型调用 | `app.py::xhs_project_select_topic` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/config` | 保存图文/轮播配置。 | 无模型调用 | `app.py::xhs_project_config` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/draft` | 生成小红书标题、正文和 slide plan。 | 当前文本模型 | `app.py::xhs_project_draft`、`xhs_tools.generate_draft`、`deepseek_client.parse_json_model` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/draft/confirm` | 确认小红书文案草稿。 | 无模型调用 | `app.py::xhs_project_confirm_draft` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/revise` | 修订小红书文案。 | 当前文本模型 | `app.py::xhs_project_revise`、`xhs_tools.revise_draft` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/image-suggestions` | 生成小红书封面和轮播图提示词。 | 当前文本模型 | `app.py::xhs_project_image_suggestions`、`xhs_tools.suggest_images` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/image-suggestions/confirm` | 确认图片提示词。 | 无模型调用 | `app.py::xhs_project_confirm_image_suggestions` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/images` | 批量生成封面和轮播图。 | 当前图片模型 | `app.py::xhs_project_images`、`xhs_tools.generate_images` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/images/item` | 生成单张小红书图片。 | 当前图片模型 | `app.py::xhs_project_image_item`、`xhs_tools.generate_image_item` |
| `apiXhs.ts` / `apiSettings.ts` | GET | `/api/xhs/auth/status` | 检查小红书登录状态。 | 无模型调用 | `app.py::xhs_auth_status`、`xhs_tools.login_status` |
| `apiXhs.ts` / `apiSettings.ts` | POST | `/api/xhs/auth/logout` | 退出小红书登录。 | 无模型调用 | `app.py::xhs_auth_logout`、`xhs_tools.logout_auth` |
| `apiSettings.ts` | POST | `/api/xhs/auth/qrcode` | 获取小红书二维码登录信息。 | 无模型调用 | `app.py::xhs_auth_qrcode`、`xhs_tools.auth_qrcode` |
| `apiSettings.ts` | POST | `/api/xhs/auth/wait-login` | 等待小红书扫码登录完成。 | 无模型调用 | `app.py::xhs_auth_wait_login`、`xhs_tools.wait_login` |
| `apiXhs.ts` | POST | `/api/xhs/publish/preflight` | 小红书发布预检。 | 无模型调用 | `app.py::xhs_publish_preflight` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/export-package` | 导出发布包。 | 无模型调用 | `app.py::xhs_project_export_package` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/publish/fill` | 填入小红书发布页。 | 无模型调用；调用本机小红书自动化 CLI。 | `app.py::xhs_project_publish_fill`、`xhs_tools.fill_publish` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/publish/confirm` | 用户确认后点击发布。 | 无模型调用；调用本机小红书自动化 CLI。 | `app.py::xhs_project_publish_confirm` |
| `apiXhs.ts` | POST | `/api/xhs/projects/{project_id}/publish/save-draft` | 发布取消时保存草稿。 | 无模型调用；调用本机小红书自动化 CLI。 | `app.py::xhs_project_publish_save_draft` |
| `apiXhs.ts` | GET | `/api/xhs/file?path=...` | 读取小红书项目产物文件。 | 无模型调用 | `app.py::xhs_file` |

## 设置与依赖

| 前端调用位置 | 方法 | 后端路径 | 用途 | 模型调用 | 后端主要落点 |
| --- | --- | --- | --- | --- | --- |
| `apiSettings.ts` | GET | `/api/health` | 后端健康检查。 | 无模型调用 | `app.py::health` |
| `apiSettings.ts` | GET | `/api/workbench-settings` | 读取工作台设置。 | 无模型调用 | `app.py::list_workbench_settings` |
| `apiSettings.ts` | POST | `/api/workbench-settings` | 保存工作台设置。 | 无模型调用 | `app.py::save_workbench_settings` |
| `apiSettings.ts` | GET | `/api/media/bilibili-cookies` | 检查 B 站 Cookie 文件结构。 | 无模型调用 | `app.py::bilibili_cookie_status` |
| `apiSettings.ts` | POST | `/api/media/bilibili-cookies/login` | 打开专用浏览器登录并导出 Cookie。 | 无模型调用 | `app.py::open_bilibili_cookie_login` |
| `apiSettings.ts` | GET | `/api/media/dependencies` | 检查媒体解析、ASR 等依赖状态。 | 无模型调用 | `app.py::media_dependencies` |
| `apiSettings.ts` | POST | `/api/v2/settings/html-grab-check` | 检查网页抓取浏览器连接和授权状态。 | 无模型调用 | `src/api_v2.py::settings_html_grab_check` |
| `apiSettings.ts` | POST | `/api/v2/settings/html-grab-authorize` | 打开网页抓取授权页面。 | 无模型调用 | `src/api_v2.py::settings_html_grab_authorize` |
| `apiSettings.ts` | GET | `/api/v2/settings/asr` | 读取 ASR 配置列表和当前配置。 | 无模型调用；返回当前 ASR 模型配置。 | `src/api_v2.py::settings_asr` |
| `apiSettings.ts` | POST | `/api/v2/settings/asr` | 保存 ASR 配置。 | 无模型调用 | `src/api_v2.py::save_settings_asr` |
| `apiSettings.ts` | POST | `/api/v2/settings/asr/active` | 切换当前 ASR 配置。 | 无模型调用 | `src/api_v2.py::activate_settings_asr` |
| `apiSettings.ts` | DELETE | `/api/v2/settings/asr/{setting_id}` | 删除 ASR 配置。 | 无模型调用 | `src/api_v2.py::delete_settings_asr` |
| `apiSettings.ts` | POST | `/api/v2/settings/asr/test` | 测试 ASR 配置。 | 当前 ASR 模型；测试时可能调用 `transcribe_audio_url` 或 `transcribe_audio`。 | `src/api_v2.py::test_settings_asr`、`media_transcriber.py` |
| `apiSettings.ts` | GET | `/api/v2/settings/api` | 读取文本模型 API 配置。 | 无模型调用；返回当前文本模型配置。 | `src/api_v2.py::settings_api` |
| `apiSettings.ts` | POST | `/api/v2/settings/api` | 保存文本模型 API 配置。 | 无模型调用 | `src/api_v2.py::save_settings_api` |
| `apiSettings.ts` | POST | `/api/v2/settings/api/active` | 切换当前文本模型配置。 | 无模型调用 | `src/api_v2.py::activate_settings_api` |
| `apiSettings.ts` | DELETE | `/api/v2/settings/api/{setting_id}` | 删除文本模型 API 配置。 | 无模型调用 | `src/api_v2.py::delete_settings_api` |
| `apiSettings.ts` | POST | `/api/v2/settings/api/test` | 测试文本模型配置。 | 当前文本模型；通过诊断请求验证连通性。 | `src/api_v2.py::test_settings_api`、`deepseek_client.diagnose` |
| `apiSettings.ts` | GET | `/api/v2/settings/image` | 读取图片模型 API 配置。 | 无模型调用；返回当前图片模型配置。 | `src/api_v2.py::settings_image` |
| `apiSettings.ts` | POST | `/api/v2/settings/image` | 保存图片模型 API 配置。 | 无模型调用 | `src/api_v2.py::save_settings_image` |
| `apiSettings.ts` | POST | `/api/v2/settings/image/active` | 切换当前图片模型配置。 | 无模型调用 | `src/api_v2.py::activate_settings_image` |
| `apiSettings.ts` | DELETE | `/api/v2/settings/image/{setting_id}` | 删除图片模型 API 配置。 | 无模型调用 | `src/api_v2.py::delete_settings_image` |
| `apiSettings.ts` | POST | `/api/v2/settings/image/test` | 测试图片模型配置。 | 可选当前图片模型；`real_test=false` 时只验证配置，`real_test=true` 时生成测试图。 | `src/api_v2.py::test_settings_image`、`writer_tools.generate_image` |
| `apiSettings.ts` | GET | `/api/v2/settings/trash` | 获取回收站状态。 | 无模型调用 | `src/api_v2.py::settings_trash_status` |
| `apiSettings.ts` | DELETE | `/api/v2/settings/trash` | 清空回收站。 | 无模型调用 | `src/api_v2.py::clear_settings_trash` |
| `apiSettings.ts` | POST | `/api/v2/settings/trash/delete` | 删除选中的回收站文件。 | 无模型调用 | `src/api_v2.py::delete_selected_trash_files` |
| `apiSettings.ts` | POST | `/api/v2/settings/trash/restore` | 恢复选中的回收站文件。 | 无模型调用 | `src/api_v2.py::restore_selected_trash_files` |
| `apiSettings.ts` | GET | `/api/v2/admin/database/status` | 查看数据库和存储诊断状态。 | 无模型调用 | `src/api_v2.py::admin_database_status` |
| `apiSettings.ts` | GET | `/api/settings/wechat-publisher` | 读取微信公众号发布绑定。 | 无模型调用 | `app.py::get_wechat_publisher_binding` |
| `apiSettings.ts` | POST | `/api/settings/wechat-publisher` | 保存微信公众号发布绑定。 | 无模型调用 | `app.py::save_wechat_publisher_binding` |
| `apiSettings.ts` | POST | `/api/settings/wechat-publisher/token/refresh` | 刷新微信公众号 access token。 | 无模型调用；调用微信接口。 | `app.py::refresh_wechat_publisher_binding_token` |

## 任务与配额

| 前端调用位置 | 方法 | 后端路径 | 用途 | 模型调用 | 后端主要落点 |
| --- | --- | --- | --- | --- | --- |
| `apiJobs.ts` | GET | `/api/jobs?limit=...` | 列出异步任务。 | 无模型调用 | `src/api_v2.py::jobs_list` |
| `apiJobs.ts` | POST | `/api/jobs` | 创建异步任务。 | 取决于任务类型；`learn_refine`、`mine_interpret`、`writer_topics`、`writer_article`、`writer_revise` 调用当前文本模型，`media_transcript` 调用当前 ASR 模型，`writer_images` 和 `writer_image_item` 调用当前图片模型。 | `src/api_v2.py::jobs_create`、`_execute_job` |
| `apiJobs.ts` | GET | `/api/jobs/{job_id}` | 查看任务详情。 | 无模型调用 | `src/api_v2.py::jobs_detail` |
| `apiJobs.ts` | POST | `/api/jobs/{job_id}/cancel` | 取消任务。 | 无模型调用 | `src/api_v2.py::jobs_cancel` |
| `apiQuota.ts` | GET | `/api/v2/quotas/me` | 查看当前配额状态。 | 无模型调用 | `src/api_v2.py::quota_status` |
