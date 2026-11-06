# 工作区组件全景与契约速查（自包含副本）

> 来源：`dev-docs/research/2026-11-06-workspace-components-map.md`（dev-docs 不随 git，
> 此处为技能自包含精简版；机制演进时以源码为准并回写本文件）。

## 一、分发入口：project-shell.tsx（约 970~1040 行）

`ProjectShell` 的 JSX 三元链（包在 `<ErrorBoundary>` 内、`<WorkspaceShell>` 的 children 里），按序判定：

| # | 条件（project.type） | 渲染组件 | 加载方式 |
|---|---|---|---|
| 1 | `fairygui` **且** `designOpen`（hash 带 `/design`） | `FairyguiDesignWorkspace` | 直接 import |
| 2 | 非 `interactive-story` 且非 `asset-canvas`（**排除法：新类型自动落这里**） | `CodingWorkspace` | 直接 import |
| 3 | `asset-canvas` | `CanvasWorkspace` | `lazy()` + Suspense |
| 4 | 兜底（即 `interactive-story`） | `PlayableEditorWorkspace` | 直接 import |

## 二、类型 → 工作区速查

| 项目类型 | 会话页工作区 | 设计视图（/design） |
|---|---|---|
| `general` / `web-game` | CodingWorkspace（含 web 预览） | 共享画布（CodingWorkspace 内嵌） |
| `godot-game` | CodingWorkspace（onClose 特判收起） | 同上 |
| `fairygui` | CodingWorkspace | **FairyguiDesignWorkspace**（专属，整页替换型） |
| `requirement-check` 等新类型 | CodingWorkspace（排除法自动落位） | 共享画布 |
| `asset-canvas` | CanvasWorkspace（lazy，单板模式） | - |
| `interactive-story` | PlayableEditorWorkspace（完全替换型） | 内嵌设计态 |

## 三、组件清单与 props 契约

### CodingWorkspace（通用代码工作区，主力）

- `coding-workspace.tsx`（约 1613 行）
- 内含/导出：`WorkspaceFileBrowser` / `WorkspaceCodeView` / `PreviewView` / `AssetsView` /
  `playerViewport` / `workspaceFileTree`（**导出被 CanvasWorkspace 复用**）
- 关联：`WorkspaceTabs`、`PublishDialog`、`GitChangesList`、`useWebGamePlayer`、
  `DesktopGamePreview`、`useRuntimeConnection`、`useWorkspaceAssetUrl`
- `publishingUnavailable`：godot-game / fairygui / requirement-check 类型禁发布

### FairyguiDesignWorkspace（专属设计页，最小样例 192 行）

- `fairygui-design-workspace.tsx`，整页替换型 props：`{ project, onContextChange, onLeave, initialComponent }`
- 内容源：编辑器桥（xc-link-plugin，MCP）；`fairygui-design.css`

### CanvasWorkspace（共享画布外壳，lazy，248 行）

- `canvas-workspace.tsx`，完全替换型 props（**壳的全量契约参照**）：
  `{ project, onProjectUpdated, workspaceRevision, openFileRequest, initialNodeId,
     onInitialNodeHandled, onSaveReady, onContextChange, chatOnRight, chatCollapsed,
     onHome, homeLabel, onToggleChat }`
- 复用 `CanvasBoardEditor`（asset-canvas-workspace.tsx）+ `WorkspaceCodeView`（coding-workspace.tsx）
- 数据层：`canvas-api.ts`、`canvas-board-storage.ts`、`use-canvas-documents.ts`、`use-canvas-tables.ts`

### PlayableEditorWorkspace（互动故事编辑器，约 1298 行）

- `playable-editor-workspace.tsx`，完全替换型
- 关联：`playable-chat.ts`（编辑器与聊天面板的上下文桥）、发布链路同 CodingWorkspace

### 引擎库（不是分支目标，是被复用的）

- `asset-canvas-workspace.tsx`（约 4004 行，全仓库最大）：导出 `CanvasBoardEditor`
  （画布节点编辑器核心）——CanvasWorkspace 的引擎；**类型特化禁止**（方案 C 边界）
- `asset-canvas-home.tsx`：素材画布**工作室首页**（`#/asset-canvas` 路由），与 Workspace 无关

## 四、共享外壳与横切件

| 文件 | 导出 | 说明 |
|---|---|---|
| `workspace-shell.tsx` | `WorkspaceShell` / `WorkspaceAgentPane` / `WorkspaceBackButton` | 布局外壳（左工作区/右聊天可折叠）+ 聊天面板容器 |
| `agent-timeline.tsx` | `AgentTimeline` | 消息时间线（thinking/问卷/todo 卡片），渲染在 WorkspaceAgentPane 内 |
| `workspace-version.ts` | `workspaceVersion` / `observeWorkspaceVersion` | 工作区文件版本号（agent 改文件后驱动刷新） |
| `use-workspace-asset-url.ts` | `useWorkspaceAssetUrl` / `CanvasAssetProvider` | 工作区资产 URL 解析 |
| `workspace-tabs.tsx` | `WorkspaceTabs` | 画布/代码/预览页签 |
| `workspace-git-changes.tsx` | `GitChangesList` / `WorkspaceGitDiff` | 变更列表与 diff |
| `chat-layout.ts` | `ChatLayout` | 聊天在左/右布局枚举 |

## 五、设计视图数据契约（复用 canvas/ 时）

| 文件 | 内容 | 谁写 |
|---|---|---|
| `canvas/index.json` | 画板/文档/表格索引（TypeBox schema 校验） | UI 与 agent |
| `canvas/boards/<id>.json` | 画板（节点树 + 编辑器布局） | UI 与 agent |
| `canvas/documents/<id>.md` | Markdown 文档节点 | UI 与 agent |
| `canvas/tables/<id>.json` | 结构化表格 | UI 与 agent |
| `canvas/AGENTS.md` + `canvas/schemas/` | agent 操作契约 | `canvas_init` 工具生成 |

daemon 侧：`canvas-routes.ts`（画布 CRUD，revision 乐观锁）、`agent-tools.ts`
（`canvas_init` 幂等初始化 / `canvas_check` 只读校验）。
