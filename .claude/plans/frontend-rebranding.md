# Frontend Rebranding: FlowAI → FlowAI

## 当前状态: Phase 1-4 基本完成

---

## ✅ Phase 1: 品牌更名

- [x] 新 Logo `public/flowai.svg` — 流动曲线 + 三节点抽象设计，青蓝→靛蓝渐变
- [x] 删除 `public/flowagent.svg`、`pi.svg`、`vite.svg`、`react.svg`
- [x] `index.html` — favicon/title/meta/theme-color 全部更新
- [x] `LoginPage.tsx` — 标题 + 闪电图标替换为 FlowAI logo
- [x] `EditorPage.tsx` — brand-mark 改为新 logo，"FlowAI"→"FlowAI"
- [x] 路径别名 `@/` → `./src`（vite.config.ts + tsconfig.app.json）

## ✅ Phase 2: 暗色主题系统

- [x] `src/hooks/useDarkMode.ts` — 跟随系统 + localStorage 覆盖 + 导出 toggleDarkMode
- [x] `src/App.tsx` — antd v6 `darkAlgorithm`，定制 token + Button 组件 token
- [x] `src/index.css` — 42 个 CSS 变量，:root 亮色 + .dark 暗色，自动过渡
- [x] `index.html` 内联脚本 — 预加载暗色 class，消除闪白
- [x] 暗色调为柔和深灰蓝（#1a1f2e）而非纯黑

## ✅ Phase 3: 布局重新设计

```
┌──────┬──────────────────────────────────────────────────────┐
│ Topbar (64px): [←][logo][name] [desc][Engine▼][save][debug] [☀][⛶][user] │
├──────┼──────────────────────────────────────────────────────┤
│168px │                  Canvas (dot-grid)                   │
│ side │  ┌──────────┐              ┌──────────────────┐     │
│ bar  │  │ Node Lib │              │  Config Panel    │     │
│      │  │ (flyout) │              │  (slide right)   │     │
│      │  └──────────┘              └──────────────────┘     │
└──────┴──────────────────────────────────────────────────────┘
```

- [x] 168px 左侧导航栏（带文字标签）— 仪表盘 / 节点库 / 知识库 / MCP / 模型配置 / 新建 / 加载
- [x] 节点库浮动滑出面板
- [x] 配置面板滑入式覆盖层（点击遮罩关闭）
- [x] 画布 dot-grid 背景图案
- [x] 全屏按钮 + 深浅色切换按钮
- [x] 编辑器返回仪表盘按钮、知识库/MCP 返回上一页

## ✅ Phase 4: 仪表盘首页

- [x] `src/pages/DashboardPage.tsx` — 统计卡片（总数/DAG/LangGraph）+ 工作流列表
- [x] 路由 `/` → Dashboard，`/editor` → Editor
- [x] 工作流卡片可点击进入编辑器，hover 显示箭头
- [x] "进入编辑器" + "创建新工作流" 双入口

## ✅ 附加修复

- [x] 编辑器描述字段 — 保存/加载/新建均支持
- [x] 调试按钮浅色/深色均可见
- [x] 描述框与引擎/保存等按钮同高
- [x] 时间显示改为具体日期而非相对时间
- [x] Zustand SPA 状态残留修复 — 进入 /editor 无 id 时重置
- [x] ReactFlow Controls/Minimap 暗色适配

## 待定

- [ ] 设置页
- [ ] 键盘快捷键
- [ ] 工作流模板
