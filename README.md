# 截图知识库

本地个人知识库 App：把网页、公众号、研报、资讯或社交媒体截图拖入页面，先用本地 PaddleOCR 识别文字，再用 DeepSeek 生成结构化知识簇 Markdown，并支持基于选中的知识文件生成原创选题建议。

## 快速开始

```powershell
cd E:\Invest\FigureLearning
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

在 `.env` 中填写：

```text
OCR_PROVIDER=paddleocr
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
LLM_TIMEOUT=120
LLM_MAX_RETRIES=2
PADDLE_PDX_MODEL_SOURCE=bos
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False
OCR_MODEL_SIZE=mobile
OCR_MAX_SIDE=1800
OCR_CPU_THREADS=4
OCR_OMP_THREADS=1
OCR_RECOGNITION_BATCH_SIZE=4
```

启动：

```powershell
.\.venv\Scripts\python.exe run_server.py
```

打开：

```text
http://127.0.0.1:8000
```

## 功能

- 拖拽上传截图
- 点击选择截图
- 输入框 Ctrl+V 粘贴截图
- 当前队列作为一轮完整知识输入合并分析
- 图片队列预览、删除与状态展示
- 基于图片 hash 去重
- 本地 PaddleOCR 识别截图文字
- DeepSeek 生成结构化知识簇
- Markdown 按日期归档到 `knowledge/YYYY-MM-DD/`
- SQLite 保存图片、hash、Markdown 路径和处理状态
- 多选知识文件生成原创选题建议

默认数据库保存在当前 Windows 用户目录：

```text
%LOCALAPPDATA%\FigureLearning\knowledge.db
```

PaddleOCR 模型首次运行会下载到：

```text
E:\Invest\FigureLearning\.paddle_cache
```

## OCR 速度配置

默认使用平衡模式，适合网页截图：

- `OCR_MODEL_SIZE=mobile`：速度更快、CPU 压力小；如需最高精度可改为 `server`。
- `OCR_MAX_SIDE=1800`：超大截图先等比缩放再 OCR，保留文字可读性的同时减少计算量。
- `OCR_CPU_THREADS=4`：限制 PaddleOCR 占用 CPU 线程，避免分析时电脑明显卡顿。
- `OCR_OMP_THREADS=1`：减少底层 OpenMP 额外抢占线程。

## API 设置

网页右上角有 `API 设置`：

- 可选择 DeepSeek、OpenAI 官方、OpenAI 兼容中转站模板。
- 可新增、保存、测试、删除 API 配置。
- 保存后的配置会写入本机 `%LOCALAPPDATA%\FigureLearning\api_settings.json`。
- 页面只显示脱敏 Key；编辑已有配置时，API Key 留空表示保留旧 Key。
- 生成知识和选题时会使用当前启用的 API 配置。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```
