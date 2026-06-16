# GitHub 普通用户本地版发布清单

这份清单用于把当前仓库发布成“普通用户下载后在自己电脑上运行”的版本。

## 发布目标

发布后的用户应该能够：

- 从 GitHub 下载 ZIP 或 Release 压缩包
- 在任意本地目录解压项目
- 双击 `安装知识酷-首次运行.bat`
- 双击 `启动知识酷.bat`
- 在浏览器访问 `http://127.0.0.1:8000`

## 发布前检查

### 1. 不要带上本地敏感数据

重点确认这些内容没有进入提交：

- `auth/`
- `*.cookies.txt`
- `knowledge.db`
- `*.sqlite`
- `media/`
- `documents/`
- `images/`
- `writer/`
- `output/`
- `server.*.log`
- `.env`

先运行：

```powershell
git status --short --branch
```

### 2. 前端产物可用

普通用户默认不需要 Node.js，所以发布前应确认前端已构建：

```powershell
cd frontend\workbench
npm.cmd run build
```

确认这些文件存在：

- `frontend/workbench/dist/index.html`
- `frontend/dist/index.html` 或当前项目使用的其他已提供前端

### 3. 后端可启动

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe run_server.py
```

确认本地能打开：

```text
http://127.0.0.1:8000
```

### 4. 脚本路径没有写死

确认这些脚本都使用相对路径，而不是你的本机绝对路径：

- `安装知识酷-首次运行.bat`
- `启动知识酷.bat`
- `启动知识酷-本地模式.bat`
- `启动知识酷-Cloud预览.bat`
- `refresh_bilibili_cookies.bat`
- `export_bilibili_cookies_with_edge.bat`
- `start_app.cmd`
- `start_app.ps1`

## 推荐发布流程

1. 在 GitHub 仓库里准备一个清晰的 Release 版本号
2. 提交 README、脚本和发布说明
3. 运行本地打包脚本生成普通用户压缩包
4. 打 tag 或直接创建 GitHub Release
5. 在 Release 说明里写清楚：
   - 支持 Windows
   - 首次先运行 `安装知识酷-首次运行.bat`
   - 需要自行填写 `.env` 中的 API Key
   - 哪些能力依赖 Cookie 或本机外部工具

打包命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\package_local_release.ps1 -Version v0.1.0
```

默认输出：

```text
output\releases\zhishiku-local-v0.1.0.zip
```

## 推荐写在 Release 说明里的内容

可直接参考下面这段：

```text
这是知识酷的本地测试版，适合在 Windows 电脑上体验。

使用方法：
1. 下载并解压压缩包
2. 双击“安装知识酷-首次运行.bat”
3. 编辑 .env，填写你的 API Key
4. 双击“启动知识酷.bat”
5. 浏览器打开 http://127.0.0.1:8000

注意：
- 不会自动上传你的本地知识库数据
- B 站、媒体解析等能力可能需要额外配置
- 首次 OCR 可能下载模型，耗时会更久
```

## 不建议现在就承诺给普通用户的能力

这些能力更适合先写成“实验能力”或“需要额外配置”：

- B 站 Cookie 登录导出
- 依赖浏览器状态的媒体抓取
- 本地环境差异很大的 OCR / ASR 高级流程
- 云端多用户共享工作区

## 发布后回归建议

至少做一次“新目录冷启动”验证：

1. 把仓库复制到一个新目录
2. 删除旧 `.venv`
3. 运行 `安装知识酷-首次运行.bat`
4. 再运行 `启动知识酷.bat`
5. 验证首页、收集区、知识库、设置页是否都能进入
