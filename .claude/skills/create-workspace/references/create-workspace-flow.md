# 工作区组件流程（创建 + 修改）

前置：SKILL.md 的输入表已拿齐（key、接入形态、数据契约、只读/可编辑）。
下文 `<key>` 一律替换为目标类型 key（如 `fairygui`），`<Key>` 为首字母大写形式。

## 创建专属工作区（方案 B）

### 快速路径（接线机械化，推荐）

前置（缺一不可）：① 类型已注册（create-studio 12 步完成）；② 已确认走方案 B。

```
python .claude/skills/create-workspace/scripts/wire.py --key <key> --mode design|full [--zh <中文名>] [--dry-run]
```

脚本做：组件文件从 `templates/` 骨架渲染生成（内容区全是 TODO，只保证可编译）+
`project-shell.tsx` 接线（import 行 + 分支 JSX；full 另改排除分支）。
保护：未注册类型拒接（防 TS2367）、组件/分支已存在拒接（防重复）、锚点恰好
1 次、全过才写盘。**接线后 typecheck 必须过，但 typecheck 过 ≠ 接对（见坑 2），
必须浏览器实测分支命中**。脚本完成后从第 3 步（数据契约）继续，内容区填模板 TODO 位。

### 第 0 步：决策——真的需要专属工作区吗（必做）

三档方案，逐档判断：

| 档 | 做法 | 何时选 |
|---|---|---|
| 方案 A（不写代码） | 共享画布 + `canvas/AGENTS.md` + `canvas/schemas/` 约定组织节点 | **默认先跑这档**——大多数「想让设计页懂 XX」的诉求，定制契约就够了 |
| 方案 B（本流程） | 专属组件 + project-shell 加分支 | 有真实专属 UI 诉求：组件树、专属预览、专属编辑器、外部工具直连 |
| 方案 C（禁止） | 改 `asset-canvas-workspace.tsx` 共享画布本体做类型特化 | **不要做**：一处改动影响全部类型，且该文件 4000 行全仓库最大 |

方案 A 验证过工作流、确有专属 UI 诉求，才进方案 B。用户明确要方案 B 时直接进。

### 第 1 步：新建组件文件

`src/renderer/<key>-workspace.tsx`（完全替换型）或 `src/renderer/<key>-design-workspace.tsx`
（整页替换型，仅设计视图用）。从最小样例起步：照
`fairygui-design-workspace.tsx`（192 行）的骨架——State + 主视图 + Loading/刷新 + 返回按钮。

props 契约见 `workspace-map.md` 第三节；**两种形态的 props 面不同**：

- 整页替换型（FairyguiDesignWorkspace 模式）：`{ project, onContextChange, onLeave, initialComponent }` 等少量 props，壳的通用 props 由外层分支处的兄弟组件分担
- 完全替换型（CanvasWorkspace 模式）：接壳的全量 props
  `{ project, onProjectUpdated, workspaceRevision, openFileRequest, onSaveReady, onContextChange, chatOnRight, chatCollapsed, onHome, homeLabel, onToggleChat, ... }`

### 第 2 步：project-shell.tsx 分支接入（两种形态，选一）

四向分支在 `project-shell.tsx` 约 970~1040 行（JSX 三元链，包在 ErrorBoundary 内）。

**整页替换型**（普通会话仍走 CodingWorkspace，仅设计视图换页）——Fairygui 模式：

```tsx
project.type === "<key>" && designOpen ? (
  <KeyDesignWorkspace
    project={project}
    onContextChange={setDesignContext}
    onLeave={() => changeWorkspaceView(false)}
    initialComponent={pendingDesignComponent}
  />
) : ...
```

插在分支链最前（fairygui 分支旁）。`designOpen` 由 hash 带 `/design` 驱动。

**完全替换型**（整个会话页工作区都换）——Canvas/Playable 模式：

1. 排除法分支（分支 2）加排除：`project.type !== "interactive-story" && project.type !== "asset-canvas"` 追加 `&& project.type !== "<key>"`
2. 新增自己的分支（照 CanvasWorkspace 分支写法，含 props 全量传递）

### 第 3 步：数据契约接线

- **复用 `canvas/`（推荐）**：白得 `canvas_init` / `canvas_check` agent 工具 + 画布 CRUD
  API（`canvas-api.ts`，带 revision 乐观锁）；UI 读写 `canvas/boards|documents|tables`，
  agent 读写同一份文件
- **自定义契约**：定义自己的文件契约（工程目录内），**必须**同步 agent 侧
  （AGENTS.md / 专用工具 / 配套插件 Skill），否则 agent 与 UI 两端看不见对方的数据
- 外部工具直连：渲染层可直接连 `http://127.0.0.1:*`（CSP 已放行），参照
  `fairygui-bridge-status.tsx` 的连法；桥状态角标是现成先例

### 第 4 步：设计上下文联动

`onContextChange` 把「用户正在看什么」（选中组件 / 节点）传给 `setDesignContext` →
composer 的上下文 chip → 用户发消息自动带上，agent 感知设计现场。有选中态就接，没有可暂缺。

### 第 5 步：验收

1. `bun run typecheck` 通过。
2. 打开一个 `<key>` 类型项目实测：分支命中（专属 UI 出现）、返回/保存/上下文 chip 正常。
3. **回归四类既有工作区**：general/web-game（CodingWorkspace）、fairygui 设计视图
  （`#/…/design`）、asset-canvas（CanvasWorkspace）、interactive-story
  （PlayableEditorWorkspace）——其它类型不受影响才算过。
4. daemon 侧有新文件契约时重启 daemon（杀 43110 监听 PID，`bun run dev:daemon` 拉起）。
5. commit：`feat: add <key> workspace (project-shell branch + component)`；
   按仓库 CLAUDE.md 更新 dev-docs。

## 修改现有工作区（映射表）

先拿到：目标组件 + 要改什么。改前先看 `workspace-map.md` 确认改动点是否被其它类型复用。

| 要改什么 | 动哪里 | 注意 |
|---|---|---|
| 某类型的工作区换新组件 | `project-shell.tsx` 分支（同创建第 2 步） | 旧组件若无人引用则删（Deletion over addition） |
| CodingWorkspace 的文件树/代码/预览/资产 | `coding-workspace.tsx` | **导出被 CanvasWorkspace 复用**（WorkspaceCodeView 等），改导出面先 grep 消费者 |
| FairyGUI 设计页 | `fairygui-design-workspace.tsx` + `fairygui-design.css` | 内容源走编辑器桥（xc-link-plugin） |
| 互动故事编辑器 | `playable-editor-workspace.tsx` | `playable-chat.ts` 是编辑器与聊天面板的上下文桥 |
| CanvasWorkspace 外壳 | `canvas-workspace.tsx` | 画布编辑器本体在 `asset-canvas-workspace.tsx`（CanvasBoardEditor），方案 C 边界 |
| 聊天面板/时间线（全部类型共用） | `workspace-shell.tsx` / `agent-timeline.tsx` | 横切件，改前想清楚影响面 |
| 工作区页签/布局 | `workspace-tabs.tsx` / `chat-layout.ts` | 同上 |

修改的验收：同创建第 5 步（typecheck + 命中实测 + 受影响类型回归）。

## 坑清单（执行中踩到就回写）

| # | 坑 | 修法 |
|---|---|---|
| 1 | 新分支加在 ErrorBoundary **外**或 WorkspaceShell **外**，布局塌 | 分支必须在 `<ErrorBoundary key={projectId:workspaceEpoch}>` 内、`<WorkspaceShell>` 的 children 里（照现有分支缩进位置插） |
| 2 | **typecheck 过 ≠ 接对**（2026-11-06 wire.py 实测）：分支 JSX 若被插进既有 JSX 标签内部（如 `/>` 与 `</Suspense>` 之间），新分支变成 Suspense 的子内容（裸文本 + 双组件），编译合法、渲染逻辑错 | 分支插入点在两个完整 JSX 表达式**之间**（三元链的 `: ` 处）；接线后必须浏览器实测：目标类型命中新组件 + asset-canvas 回归无泄漏文本（页面 grep `project.type`） |
| 3 | 只改了排除分支没加自己的分支（或反之），类型落进 CodingWorkspace 或渲染 null | 完全替换型两处一起改：排除分支 + 新分支（wire.py full 模式已含） |
| 4 | 自定义数据契约忘了同步 agent 侧，UI 写的文件 agent 看不见 | 契约文件（AGENTS.md/schema）与工具一起交付 |
| 5 | 编辑回写直接改工程文件，与编辑器内存态/agent 并发写冲突 | 回写一律走官方 API / revision 乐观锁；只读版先行 |
