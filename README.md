# 知识酷

一个本地优先的个人知识库与创作工作台。项目使用 FastAPI 作为后端，React/Vite 作为新版工作台前端，SQLite 与本地 Markdown 文件共同保存原文、知识、视角和创作结果。

这个仓库当前最适合这样使用：

- 开发者直接从 GitHub 克隆源码，本地配置后运行
- 普通测试用户下载仓库或 Release 压缩包，在自己的 Windows 电脑上完成首次安装后使用

## 给普通用户

### 1. 下载

可以用两种方式获取：

- GitHub 页面点击 `Code > Download ZIP`
- GitHub Releases 下载你发布的压缩包

解压后，把整个项目放到你想保存数据的位置，例如：

```text
D:\Apps\ZhiShiKu
```

不要放进会频繁同步或权限受限的目录里。

### 2. 首次安装

双击运行：

```text
安装知识酷-首次运行.bat
```

它会自动执行这些步骤：

- 检查本机是否有 Python
- 创建 `.venv` 虚拟环境
- 安装 `requirements.txt` 里的后端依赖
- 如果缺少 `.env`，自动从 `.env.example` 复制一份
- 创建 `knowledge/`、`images/`、`documents/`、`auth/`、`output/` 等本地目录

### 3. 配置 API

首次安装后，打开项目根目录下的 `.env`，至少补上：

```text
DEEPSEEK_API_KEY=你的 DeepSeek API Key
```

如果你暂时不填，很多需要模型生成的功能会无法使用，但本地界面和部分基础流程仍然可以启动。

### 4. 启动

双击运行：

```text
启动知识酷.bat
```

或：

```text
启动知识酷-本地模式.bat
```

启动后浏览器会自动打开：

```text
http://127.0.0.1:8000
```

### 5. 更新

如果你重新从 GitHub 拉了新代码，建议再运行一次：

```text
安装知识酷-首次运行.bat
```

这样会把新增依赖补齐，但不会删除你已有的本地数据。

## 给开发者

### 环境要求

- Windows 10/11
- Python 3.10 或 3.11
- 可选：Node.js 18+，仅在你需要重新构建新版前端时使用

### 快速开始

```powershell
cd 你的项目目录
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe run_server.py
```

打开：

```text
http://127.0.0.1:8000
```

### 前端构建

仓库里通常会保留可直接运行的前端产物，普通用户不需要自己构建。

如果你修改了 `frontend/workbench/src`，再执行：

```powershell
cd frontend\workbench
npm.cmd install
npm.cmd run build
```

## 本地数据与隐私

默认运行过程中会在项目目录内使用或生成这些内容：

- `knowledge/`
- `images/`
- `documents/`
- `media/`
- `writer/`
- `output/`
- `auth/`
- `knowledge.db` 或其他本地数据库文件

这些都属于用户本地数据，不应该提交到 GitHub。

仓库已经通过 `.gitignore` 屏蔽了大部分运行数据，但发布前仍建议手动检查一次。

## 哪些功能需要额外配置

- 大模型生成：需要填写 API Key
- B 站字幕与部分媒体流程：通常需要本地 Cookie
- OCR：首次运行 PaddleOCR 时可能会下载模型
- 媒体解析、外部平台处理：依赖本机环境与外部工具状态

如果你要给普通用户发布测试版，建议优先让他们测试这些稳定能力：

- 文本收集
- 文件收集
- 原文草稿编辑与保存
- 知识库查看与编辑
- 挖掘与创作主流程

## 常用脚本

- `安装知识酷-首次运行.bat`：首次安装或更新依赖
- `启动知识酷.bat`：本地模式启动
- `启动知识酷-本地模式.bat`：显式本地模式启动
- `启动知识酷-Cloud预览.bat`：本地机器上的 cloud preview 测试
- `refresh_bilibili_cookies.bat`：尝试从 Edge 刷新 B 站 Cookie
- `export_bilibili_cookies_with_edge.bat`：打开隔离浏览器导出 B 站 Cookie

## 发布普通用户本地版建议

推荐这样发到 GitHub：

1. 源码仓库继续维护主分支
2. 每次准备测试版时，确认前端已构建
3. 检查 `.gitignore`，不要带上数据库、Cookie、日志、媒体和本地密钥
4. 运行发布打包脚本生成普通用户压缩包
5. 打一个 GitHub Release
6. 把生成的 ZIP 作为 Release 附件上传

更完整的发布步骤见：

[docs/github-local-release.md](/E:/Invest/FigureLearning/docs/github-local-release.md)

打包命令：

```powershell
 powershell -ExecutionPolicy Bypass -File .\tools\package_local_release.ps1 -Version v0.1.0
```

生成物默认在：

```text
output\releases\
```

## 验证命令

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
