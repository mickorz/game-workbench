---
name: create-workspace
version: 1.0.0
display_name: 工作区组件管理
display_name_en: Create Workspace
description: >
  Create a dedicated workspace component for a project type in the xc-ui-flow app
  (a new branch in project-shell's viewer dispatch), or modify an existing
  workspace component (CodingWorkspace / FairyguiDesignWorkspace / CanvasWorkspace /
  PlayableEditorWorkspace). Use when the user asks to give a studio type its own
  design page or workspace UI, or to change an existing workspace component.
description_zh: >-
  在 xc-ui-flow 应用里给某个项目类型创建专属工作区组件（project-shell 分支新加一向），
  或修改现有工作区组件（CodingWorkspace / FairyguiDesignWorkspace / CanvasWorkspace /
  PlayableEditorWorkspace）。用户说「给 XX 类型做专属设计页 / 专属工作区 /
  换掉 XX 类型的设计页 / 改 XX 工作区组件」时使用。
description_en: >-
  Create a dedicated workspace component for a project type in the xc-ui-flow app
  (adding a branch to project-shell's viewer dispatch), or modify an existing
  workspace component. Use when asked to give a studio type its own design page
  or workspace UI, or to change an existing workspace component.
---

# 工作区组件管理（create-workspace）

给某个项目类型的会话页做**专属工作区组件**（project-shell 四向分支新加一向），
或**修改现有工作区组件**。本技能是 create-studio「可选步骤：定制设计页」的独立技能化。

## 与相邻技能的分界（先看这里）

| 技能 | 层 | 管 |
|---|---|---|
| create-studio | 工作室壳层 | 类型注册 / 路由 / 侧边栏 / 文案 / 图标（12 步脚手架） |
| **create-workspace（本技能）** | 工作区组件层 | project-shell 分支接入 + 专属工作区组件 + 现有工作区修改 |
| menu-item | 入口显隐层 | 侧边栏 / 新建下拉的隐藏与恢复 |

新类型**默认落 CodingWorkspace**（project-shell 排除法分支），注册类型不需要本技能；
只有要**专属 UI**（专属设计页 / 组件树 / 专属编辑器）才进本技能。

## 输入（开工前必须拿到）

| 输入 | 例 | 缺省策略 |
|---|---|---|
| 目标类型 key | `fairygui` | 问用户 |
| 接入形态 | 整页替换型 / 完全替换型 | 问用户（见流程第 2 步两种形态） |
| 数据契约 | 复用 `canvas/` / 自定义文件 | 默认复用 `canvas/`（canvas_init / canvas_check 白得） |
| 只读 or 可编辑 | 只读预览先行 | 默认只读版（编辑回写面对 revision / 撤销 / agent 并发，二期工程） |

## 边界

- **做**：新工作区组件、project-shell 分支接入、数据契约接线、设计上下文联动、
  现有工作区组件（CodingWorkspace / FairyguiDesignWorkspace / CanvasWorkspace /
  PlayableEditorWorkspace）的修改。
- **不做**：工作室壳（create-studio）；共享画布本体（`asset-canvas-workspace.tsx` 的
  `CanvasBoardEditor`）的类型特化——一处改动影响全部类型，要特化走新分支。
- **改不动**：既有类型的既有行为（新分支只在 `type === "<key>"` 命中时生效）。

## 主流程

进入 `references/create-workspace-flow.md`：

- **创建**：**快速路径（推荐）**——接线用脚本一步完成：
  `python .claude/skills/create-workspace/scripts/wire.py --key <key> --mode design|full [--zh <中文名>]`
  （组件骨架生成 + project-shell 接线，含未注册/已接线/锚点漂移三重保护；
  骨架只保证可编译，内容区是 TODO）。之后走第 0 步决策确认 + 第 3 步起填语义内容。
- **修改**：映射表定位落点 → 改 → 回归。

组件全景、props 契约速查在 `references/workspace-map.md`（自包含，不依赖 dev-docs）。

## 关键规则

1. **props 契约照现有组件接**（见 workspace-map.md），不要自造接入面。
2. 数据契约优先复用 `canvas/`；自定义契约必须同步 agent 侧（AGENTS.md / 工具）。
3. **先只读后编辑**：编辑回写是独立二期（FairyGUI 案例结论：回写一律走桥的官方 API）。
4. 每步 `bun run typecheck`；完成后回归四类既有工作区（其它类型不受影响才算过）。
5. 完成后按仓库 CLAUDE.md 更新 `dev-docs/progress/` 与 `dev-docs/progress-result/`。

## 参照物

| 文件 | 内容 |
|---|---|
| `references/create-workspace-flow.md` | 创建 / 修改主流程（主文档） |
| `references/workspace-map.md` | 工作区组件全景 + props 契约速查（自包含） |
| `scripts/wire.py` | 接线脚本：组件骨架生成 + project-shell 分支接入（前置/幂等/锚点保护，--dry-run 预览） |
| `templates/` | 组件骨架（design/full 两形态）+ 分支 JSX 片段 + 骨架生成源，手动接线时直接取用 |
| 活参照（代码，随仓库走） | `src/renderer/fairygui-design-workspace.tsx`（192 行最小样例）、`src/renderer/canvas-workspace.tsx`（props 契约源）、`src/renderer/project-shell.tsx` 970~1040 行（四向分支） |

## 执行回写约定

本技能执行中踩到的坑与经验，按 create-studio 同款约定回写
`references/create-workspace-flow.md` 的坑清单，防止下次重蹈。
