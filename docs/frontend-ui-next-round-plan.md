# 下一轮前端 UI 修改方案

> 根据 `docs/frontend-ui-change-plan.md` 的最新修改制定。本轮方向明确：撤销凹凸新拟态，回归白色简约风。用户贴入的 shadcn / Tailwind 组件作为交互参考，不作为直接依赖和结构迁移方案。

## 1. 方向结论

### 不再继续

- 不再使用凹凸新拟态。
- 不再使用大面积双向阴影、内凹输入框、浮雕选中态。
- 不引入 Tailwind、shadcn、Radix、class-variance-authority 等新依赖，除非用户之后明确要求。
- 不把当前 Vite + React + 普通 CSS 项目改造成 shadcn 项目。

### 下一轮主方向

- 风格：白色简约知识工作台。
- 材质：白底、浅灰底、细边框、极轻阴影。
- 层级：靠布局、留白、线条、字体粗细和少量强调色区分，不靠凹凸阴影。
- 交互：按钮、输入框、上传区、侧栏保持清晰可点，状态反馈明确。
- 气质：像知识生产工具，不像营销页或组件展示页。

## 2. 技术判断

当前项目实际结构：

- 前端：`frontend/workbench`
- 栈：React 19 + Vite + TypeScript
- 样式：集中 CSS，主要在 `frontend/workbench/src/styles.css`
- 已有图标：`lucide-react`
- 已有组件目录：`frontend/workbench/src/components`
- 已有 UI 目录：`frontend/workbench/src/components/ui`
- 已有 hooks 目录：`frontend/workbench/src/hooks`

因此下一轮采用：

- 使用现有 React/Vite/TypeScript 结构。
- 使用现有 CSS token 和组件目录。
- 不新增 Tailwind。
- 不复制 shadcn 组件库结构。
- 用户提供的组件代码只抽取交互思想：
  - 图片上传：预览、拖拽、移除、重新选择。
  - 输入框：自动增长 textarea。
  - 侧边栏：更清楚的导航分组和移动端折叠思路。

## 3. 第一阶段：撤销新拟态视觉

### 目标

把当前 `styles.css` 里的新拟态材质撤回到白色简约风，减少视觉噪音。

### 修改项

- 移除或弱化以下 token：
  - `--shadow-control`
  - `--shadow-control-strong`
  - `--shadow-selected`
  - `--shadow-icon`
  - `--shadow-cta`
  - `--shadow-inset`
  - `--shadow-soft-inset`
- 改为简约 token：
  - `--bg: #f7f8f6`
  - `--surface: #ffffff`
  - `--surface-soft: #f4f5f2`
  - `--surface-2: #f8f9f6`
  - `--surface-3: #eef0eb`
  - `--line: #dde2da`
  - `--shadow: 0 1px 2px rgba(24, 30, 27, 0.06)`
  - `--shadow-raised: 0 8px 24px rgba(24, 30, 27, 0.08)`
- 全局输入框改回：
  - 白色或浅灰底。
  - 细边框。
  - 无内凹阴影。
  - focus 用清晰 outline 或 ring。
- 面板改回：
  - 白底。
  - 细边框。
  - 轻阴影或无阴影。
- 选中态改回：
  - 左侧 2px 强调线。
  - 浅色背景。
  - 不使用浮起阴影。

### 验收

- 搜索 `shadow-inset` 不应再有使用。
- 搜索 `--shadow-control` 不应再有使用。
- 页面不再出现明显凹凸浮雕感。

## 4. 第二阶段：截图上传控件

### 目标

收集区的“截图/图片”入口要更像真实上传控件，而不是普通文本区域。

### 参考用户提供组件

可借鉴：

- 点击选择文件。
- 拖拽上传。
- 图片预览。
- 显示文件名。
- 移除当前图片。
- 使用 `ImagePlus`、`Upload`、`Trash2`、`X` 等 lucide 图标。

不照搬：

- 不使用 Next `Image`。
- 不使用 Tailwind class。
- 不引入 shadcn `Button` / `Input`。
- 不只生成 object URL 而不进入真实收集流程。

### 实施方案

- 新增或改造组件：
  - 建议位置：`frontend/workbench/src/components/ImageUploadDropzone.tsx`
  - 或直接在 `CollectWorkspace.tsx` 内先局部实现，待稳定后抽组件。
- 行为：
  - 点击区域触发隐藏 file input。
  - 支持 `accept="image/*"`。
  - 支持拖拽进入、离开、投放状态。
  - 投放图片后调用现有收集区文件处理逻辑，进入素材队列。
  - 可显示本地预览，但保存仍必须走现有真实上传/队列逻辑。
- 状态：
  - 空状态：图标 + “点击选择或拖入截图/图片”。
  - 拖拽中：边框强调。
  - 已选择：缩略图 + 文件名 + 移除按钮。
  - 错误：显示不支持格式或上传失败原因。

### 验收

- 上传图片能真实进入素材队列。
- 移除只移除当前待选预览，不误删已入库素材。
- 不出现纯演示状态。

## 5. 第三阶段：自动增长输入框

### 目标

长文本输入区减少固定大块空白，输入时自动增长，适合笔记、原文、备注。

### 参考用户提供组件

可借鉴：

- `useAutoResizeTextarea`
- `minHeight`
- `maxHeight`
- 输入时根据 scrollHeight 调整高度。

### 实施方案

- 新增 hook：
  - `frontend/workbench/src/hooks/useAutoResizeTextarea.ts`
- 新增可复用组件：
  - `frontend/workbench/src/components/ui/AutoResizeTextarea.tsx`
- 优先接入：
  - 收集区文本材料输入。
  - 原文草稿正文。
  - 知识库正文编辑器要谨慎，正文编辑器可能仍需要稳定的大编辑区。

### 验收

- 输入多行时高度自然增长。
- 超过最大高度后内部滚动，不撑破页面。
- 清空内容后高度回到最小值。

## 6. 第四阶段：侧边栏与移动端导航

### 目标

侧边栏保持知识工作流导航，不做复杂营销式导航菜单。

### 参考用户提供组件

可借鉴：

- 移动端折叠导航思路。
- 菜单分组思路。
- 清楚的 active 状态。

不照搬：

- 不引入 Radix dropdown/navigation/sheet。
- 不做多级 mega menu。
- 不使用网格装饰卡片。

### 实施方案

- 桌面侧栏：
  - 继续保留 `收集、学习、挖掘、创作、知识库、设置`。
  - active 使用左侧线 + 浅背景。
  - hover 使用浅灰背景，不使用浮起阴影。
- 移动端：
  - 保留横向可滚动工作区导航。
  - 右侧知识栏折叠按钮保持简洁。
  - 不引入抽屉依赖。

### 验收

- 用户能一眼知道当前工作区。
- 移动端导航不换行、不重叠。
- 不出现无效菜单项。

## 7. 第五阶段：右侧知识栏简化

### 目标

右侧知识栏服务“选择来源”，不能抢主工作区注意力。

### 修改方案

- 分桶 tab：
  - 白底容器。
  - 选中 tab 浅灰背景。
  - 细边框。
- 列表行：
  - 行式布局。
  - 轻边框或分隔线。
  - 选中行左侧强调线。
  - 不使用浮起卡片。
- 删除按钮：
  - 默认低权重。
  - 有选中项时才明显。

### 验收

- 右栏看起来是辅助选择器，不是主内容卡片墙。
- 选中文件明确。
- 删除动作不喧宾夺主。

## 8. 第六阶段：收尾检查

### 静态检查

```powershell
Select-String -Path frontend\workbench\src\styles.css -Pattern 'backdrop-filter|transition: all|shadow-inset|shadow-control|shadow-selected|shadow-icon|shadow-cta'
```

### 构建

```powershell
cd frontend\workbench
npm.cmd run build
```

### 编码检查

```powershell
.\.venv\Scripts\python.exe tools\check_encoding.py
```

## 9. 执行顺序

1. 先撤销新拟态 token 和阴影使用。
2. 再实现截图上传控件。
3. 再实现自动增长输入框。
4. 再整理侧栏和移动端导航。
5. 最后收右侧知识栏和整体细节。

## 10. 风险

- 用户文档中贴入的外部组件依赖较多，不能直接复制到当前项目，否则会引入 Tailwind/shadcn/Radix 迁移成本。
- 截图上传必须接入现有收集队列，不能只做前端预览。
- 自动增长 textarea 不能破坏知识库长文编辑体验。
- 撤销新拟态时要避免把已完成的工作流层级一起抹掉。
