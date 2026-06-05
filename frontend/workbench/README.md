# 知识酷 Workbench

这是一个不依赖旧前端代码的新网页开发环境，用来连续迭代“知识酷”研究与创作工作台。

## Product Thesis

知识酷不是普通收藏型知识库，而是一个从多模态素材进入、AI 辅助加工、多视角挖掘，到内容创作发布的个人研究生产系统。

核心闭环：

```text
材料进入 -> AI 解析 -> 人工确认 -> 多视角挖掘 -> 沉淀知识卡 -> 生成选题 -> 写作发布 -> 复盘反哺知识库
```

## IA Baseline

- `Overview`：查看端到端知识生产闭环和优先行动。
- `Inbox`：文本、截图、文档、音视频、链接等所有材料入口。
- `Material Packs`：把多份材料组织成一次研究任务。
- `Processing`：格式解析、知识切分、卡片提炼。
- `Perspective Mining`：从作家、投资人、散户、机构、创业者、研究员等身份分析信息。
- `Knowledge Library`：沉淀摘要卡、知识卡、观点卡、证据卡、问题卡。
- `Creation Studio`：选题、写作、修改、配图、美编、发布检查、发布草稿。

## Development

```bash
npm run dev
npm run build
npm run preview
```

当前应用使用 Vite + React，依赖版本与上层 `frontend` 项目保持一致，避免重新联网安装。

## Design Rules

- 采用专业研究工作台风格，高信息密度、少装饰、明确状态。
- 左侧导航切换右侧独立工作区，不把所有功能堆在一个长页面。
- 卡片只用于重复对象和工具面板，不做营销式大卡片堆叠。
- AI 输出必须进入候选区，提供采用、修改后采用、忽略，不自动覆盖人工内容。
- 筛选、搜索、状态、空态、错误态都要成为第一版能力，不后补。

## React Rules

- 未来迁移到 TypeScript 时，先固化核心对象：`Material`、`MaterialPack`、`KnowledgeCard`、`PerspectiveInsight`、`Draft`。
- 重型编辑器、图谱、证据链动态加载。
- 大型列表使用分页或虚拟化。
- 筛选状态放入 URL query，便于恢复、分享和测试。

## Verification Checklist

- 桌面和移动视口无重叠、无横向溢出。
- 2 次点击内能进入导入、材料包、视角挖掘、创作流程。
- 收件箱、材料包、加工台、视角挖掘、知识库、创作台都能一眼看懂“这里做什么”。
- 控制台无 React/Vite 运行错误。
