---
name: create-studio
version: 1.0.0
display_name: 新增工作室
display_name_en: Create Studio
description: >
  Scaffold a new studio (sidebar workspace page + project type) in the xc-ui-flow
  app, modeled on the Godot and FairyGUI studios. Use when the user asks to add a
  new studio, a new workspace entry in the sidebar studios group, or a new project
  type with its studio home page.
description_zh: >-
  在 xc-ui-flow 应用里脚手架搭建一个新工作室（侧边栏工作室页 + 项目类型），
  以 Godot 和 FairyGUI 工作室为模板。用户说「新增工作室 / 加一个工作室 /
  侧边栏加一个 XX 工作室 / 新增项目类型并配首页」时使用。
description_en: >-
  Scaffold a new studio (sidebar studios-group page plus project type) in the
  xc-ui-flow app, using the Godot and FairyGUI studios as the template. Use when
  asked to add a new studio or a new project type with its studio home page.
---

# 新增工作室（create-studio）

给本应用（ohmygame 宿主）新增一个「工作室」：侧边栏工作室组多一个菜单项，
`#/<key>` 出现工作室首页（标题 + 提示词 + 最近项目卡片），项目按新类型过滤。

本技能只搭**壳**（类型/路由/侧边栏/文案/图标/边界），不写工作室的业务逻辑——
业务能力由配套插件（Skills + MCP）提供，壳只负责把项目、类型、插件拼在一起。

## 输入（开工前必须拿到）

| 输入 | 例 | 缺省策略 |
|---|---|---|
| `key`（类型 id，小写连字符） | `fairygui` | 问用户；同时用作侧边栏 page id（避免 godot 那种两处不同名的心智负担） |
| 中文名 + 英文名 | FairyGUI / FairyGUI | 用 key 首字母大写兜底 |
| 工作室标题/占位/新建按钮文案（中英） | 「要做哪个界面的 UI？」 | 按 key 语义生成草案，交付时列出供用户改 |
| 图标 SVG（单色镂空，可作 mask） | `fairygui.svg` | 无则按业务语义到 Lucide 图标库选同义线性图标（如需求检查 → clipboard-check）抄 path 改成仓库格式（24x24、stroke 1.5），两处文件相同直接 cp |

## 边界

- **做**：shared 类型契约、工作室表、双语文案、路由白名单、侧边栏配置、
  CSS mask 图标、app.tsx 分发、类型图标、发布/预览边界、（若有配套插件）其 projectTypes。
- **不做**：工作室页内业务逻辑、daemon 新接口、插件包本身（那是另一个技能/流程的事）。
- **改不动的东西**：`PROJECT_TYPE_IDS` 只加不减；不动既有工作室的任何行为。

## 主流程

进入 `references/add-studio-flow.md`，按序执行 12 步。
**顺序本身就是方法论**：第 1 步先加 shared 类型契约，让 TS 编译器强制报出
所有待补点（GAME_STUDIOS、locales 等），逐个补齐后 typecheck 通过即结构完整。

每步改完跑 `bun run typecheck`；全部完成后按流程文档的「验收」节实测
（daemon 重启 → 插件/项目 API → 浏览器 `#/<key>`）。

## 关键规则

1. **每步后 typecheck**，报错清单就是下一步待办，不要凭记忆找改动点。
2. **每个 commit 可运行**：类型先加但 `projectTypes` 后补时要保证两个 commit 各自不炸
   （参照 FairyGUI 的做法：插件 projectTypes 分两次提交）。
3. 图标两处都要：`assets/sidebar/<key>.svg`（侧边栏 mask）+ `assets/<key>.svg`（项目类型），CSS 类名
   `home-nav-icon-<key>` 与 `project-type-<key>-icon`。
4. 双语文案 `locales/zh-CN.ts` 和 `locales/en.ts` 必须同改，key 漏一边编译不报错但运行时缺文案。
5. 完成后按仓库 CLAUDE.md 约定更新 `dev-docs/progress/` 与 `dev-docs/progress-result/`。

## 参照物（全部在技能内 references/，自包含，不依赖仓库其它路径）

| 文件 | 内容 |
|---|---|
| `references/add-studio-flow.md` | 12 步执行流程（主文档） |
| `references/case-fairygui-design.md` | 案例设计分析（工作室机制四要素、方案对比、改动清单） |
| `references/case-fairygui-execution.md` | 案例执行文档（P0~P3 全阶段步骤与实测结论，含桥补丁背景） |
| `references/case-fairygui-p2-report.md` | 案例工作室壳落地报告（12 处改动逐项核对表） |

另两个活参照（代码本身，随仓库走不会被删）：`src/renderer/studios.ts` 里 Godot 与
FairyGUI 两个条目、`plugins/fairygui/.xcflow-plugin/plugin.json` 的 interface 写法。

注意：案例文档是快照；机制若因宿主演进变化，以源码 + 本技能流程为准，并回写流程文档。
