---
name: menu-item
version: 1.0.0
display_name: 菜单项显隐管理
display_name_en: Menu Item Visibility
description: >
  Show or hide sidebar menu items and new-project type dropdowns in the
  xc-ui-flow app, by editing the sidebar config and the project type filter.
  Use when the user asks to hide, show, or restore sidebar entries (home,
  projects, library, plugins, community, studio items) or to hide types from
  the new-project dropdown.
description_zh: >-
  通过改侧边栏配置与项目类型过滤，控制 xc-ui-flow 应用侧边栏菜单项和新建项目
  类型下拉的显示与隐藏。用户说「隐藏侧边栏某项 / 隐藏新建下拉里的某类型 /
  恢复显示某个工作室 / 只保留某几个工作室」时使用。
description_en: >-
  Control visibility of sidebar entries and new-project type options in the
  xc-ui-flow app by editing the sidebar config and the project type filter.
  Use when asked to hide, show, or restore sidebar items or dropdown types.
---

# 菜单项显隐管理（menu-item）

隐藏/恢复应用的两个入口面：**侧边栏菜单**（`src/renderer/sidebar-config.ts`）
与**新建项目类型下拉**（`src/renderer/project-types.tsx`）。只改入口可见性，
不删代码、不断路由、不动数据——全部可逆。

## 落点（就两处）

### 1. 侧边栏：`src/renderer/sidebar-config.ts`

`SIDEBAR_ITEMS` 数组，给目标项加 `visible: false`（恢复则删掉该字段）。
详细字段说明见读者文档 `docs/zh-CN/sidebar-config.md`。

### 2. 新建下拉：`src/renderer/project-types.tsx`

`HIDDEN_PROJECT_TYPE_IDS` 集合增删类型 id（类型 id 用 `contracts.ts` 的
`PROJECT_TYPE_IDS` 成员，如 `"godot-game"`）。该集合被 `GAME_PROJECT_TYPES`
消费，统一控制首页新建对话框与提示词创建器的类型下拉。

**注意两个常量的消费面不同**：

| 常量 | 消费点 | 隐藏影响 |
|---|---|---|
| `SIDEBAR_ITEMS.visible` | 侧边栏渲染 | 只藏菜单项 |
| `HIDDEN_PROJECT_TYPE_IDS` → `GAME_PROJECT_TYPES` | `home.tsx` 下拉 + 创建对话框 | 只藏新建入口 |
| `PROJECT_TYPES` | 项目页筛选下拉 | **不要动**——历史项目筛选需要全类型 |

## 必须向用户说明的两点（每次都要说）

1. **隐藏 ≠ 禁用**：路由仍可达（`#/web-game` 等直接输 hash 能进），历史项目
   仍可从「项目」页打开。入口可见性≠能力禁用。
2. **恢复方式**：删 `visible: false` / 从集合删成员，一句话可逆。

## 坑清单（实战踩过）

| # | 坑 | 修法 |
|---|---|---|
| 1 | `Set` 字面量类型过窄：`new Set([...]? as const)` 后 `.has(value)` 报 TS2345（集合类型缺新类型成员） | 声明为 `ReadonlySet<ProjectType>`，成员不带 `as const` |
| 2 | **管道退出码陷阱**：`bun run typecheck 2>&1 \| tail -1` 的退出码是 tail 的 0，typecheck 报错也会被 `&&` 链放行，错误状态被 commit | typecheck 与 commit **分开跑**；或命令前加 `set -o pipefail`。commit 后必须复核 `git status` 与最近一次 typecheck 输出 |
| 3 | 侧边栏与下拉是**两个独立落点**，只改一个用户会发现另一半还在 | 隐藏工作室时默认两处一起改（先确认用户范围） |

## 验收

1. `bun run typecheck` 通过（**单独跑**，确认无输出）。
2. 刷新页面：侧边栏目标项消失、新建下拉不含目标类型。
3. 路由直输 `#/<隐藏项>` 仍可达（预期行为，不是 bug）。
4. commit + push；提交信息写明「隐藏（可逆）」与涉及类型。

## 参照物

- 读者文档：`docs/zh-CN/sidebar-config.md`（sidebar-config 的权威指南）
- 实战样例：`git log --grep="侧边栏隐藏\|新建下拉隐藏"`（2026-11-02，FairyGUI 工具化时隐藏 4 个工作室）
