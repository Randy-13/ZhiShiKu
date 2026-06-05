# 编码规则

本项目所有源码、Markdown、JSON、HTML、CSS、JS 文件统一使用 UTF-8。

## 开发规则

- 新增或修改中文 UI 文案时，优先使用 `apply_patch`。
- 如果必须通过 PowerShell 调用脚本写入中文，脚本内容中不要直接放中文字符串；使用 `\uXXXX` Unicode escape 后在 Python 内解码。
- 不使用 PowerShell 的 `Set-Content` / `Out-File` 写入含中文文件，除非显式指定 `-Encoding utf8` 并确认结果。
- 不把命令输出中的中文再复制回源码。
- 静态资源变更后更新 `static/index.html` 中的 `app.js?v=` 和 `styles.css?v=`，避免浏览器缓存旧乱码。

## 提交前检查

运行：

```powershell
.\.venv\Scripts\python.exe tools\check_encoding.py
```

脚本会扫描常见乱码指纹，例如 `????`、`锛`、`鑺`、替换符 `�`，并忽略 JavaScript 合法语法里的 `??`、`?.`、三元表达式。

若脚本失败，先修复乱码再启动服务。
