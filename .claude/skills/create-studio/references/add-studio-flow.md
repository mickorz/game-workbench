# 新增工作室执行流程（12 步）

前置：SKILL.md 的输入表已拿齐（key、中英文名、文案、图标 SVG）。
下文 `<key>` 一律替换为工作室 key（如 `fairygui`），`<Key>` 为首字母大写形式。

执行顺序固定：**先加 shared 契约，让编译器报出强制改动点，再逐个补渲染层**。

## 步骤 1：类型契约（一切的前提）

`src/shared/contracts.ts`：

```ts
export const PROJECT_TYPE_IDS = [..., "<key>"] as const;
```

改完立即 `bun run typecheck`。预期报错：

- `game-studio-home.tsx` TS7053：`GAME_STUDIOS` 缺条目（步骤 2 补）
- `project-types.tsx` TS2345：`projectType.<key>` 文案 key 缺失（步骤 3 补）

这两条报错是护航机制在工作，**不要绕过**（不要 as any）。

## 步骤 2：工作室条目

`src/renderer/studios.ts` 的 `GAME_STUDIOS` 末尾加：

```ts
<key>: {
  page: "<key>",
  title: t("studio.<key>.title"),
  placeholder: t("studio.<key>.placeholder"),
  newLabel: t("studio.<key>.new"),
},
```

注意 `GameStudioType = Exclude<ProjectType, "asset-canvas">`——新类型不加条目编译必炸。

## 步骤 3：双语文案

`src/renderer/locales/zh-CN.ts` 两处：

- `projectType` 块：`<key>: "<中文名>",`
- `studio` 块：`<key>: { title, placeholder, new }`

`src/renderer/locales/en.ts` 同位置补英文。两个文件必须同 commit 改完。

## 步骤 4：路由

`src/renderer/routes.ts` 两处：

- `SidebarPage` 联合类型加 `| "<key>"`
- `SIDEBAR_PAGES` 白名单集合加 `"<key>"`（与其它工作室成员相邻）

白名单成员即自动可解析 `#/<key>`，**不需要**像 projects/plugins 那样写专属正则。

## 步骤 5：侧边栏菜单项

`src/renderer/sidebar-config.ts` 两处：

- `SidebarIcon` 联合加 `| "<key>"`
- `SIDEBAR_ITEMS` 工作室组（`group: "studios"`）加一条，放在合适位置：

```ts
{ id: "<key>", labelKey: "projectType.<key>", icon: "<key>", group: "studios" },
```

## 步骤 6：侧边栏图标（CSS mask）

放 `src/renderer/assets/sidebar/<key>.svg`（单色镂空、纯形状、viewBox），
`src/renderer/styles.css` 在 `home-nav-icon-*` 系列处加：

```css
.home-nav-icon-<key> {
  mask-image: url("./assets/sidebar/<key>.svg");
  -webkit-mask-image: url("./assets/sidebar/<key>.svg");
}
```

坑：只有 `web-game` 和 `general` 走内联 SVG 三元分支，其它都走 CSS mask；
SVG 若是多色/带脚本则 mask 出来是黑块。

**图标怎么选、怎么快速造（项目无图标库，2026-11-06 需求检查工作室实测）**：

- 仓库不依赖任何图标库（无 lucide/iconify），既有做法就是本地 SVG 文件，不要为此新加依赖。
- **选型**：按工作室业务语义到 Lucide 图标库（lucide.dev/icons）找同名/同义线性图标，
  直接抄它的 path（MIT 许可）。例：需求检查 → `clipboard-check`（剪贴板+勾）。
- **格式**：按现有文件格式改写——`viewBox="0 0 24 24"`、`fill="none"`、
  `stroke="black"`、`stroke-width="1.5"`（参照 `assets/sidebar/assets.svg`）。
  mask 只取形状，颜色无所谓，多色反而出黑块。
- **两处文件内容相同**：步骤 8 的 `assets/<key>.svg` 直接 `cp` 侧边栏这份，不要写两遍。

## 步骤 7：页面分发

`src/renderer/app.tsx` 工作室分支（约 69 行）：

- 条件链加 `|| route.page === "<key>"`
- `<key>` 与类型同名时直接走 `route.page`（不需要 godot 那种三元映射）

## 步骤 8：项目类型图标

1. 复制 SVG 到 `src/renderer/assets/<key>.svg`
2. `src/renderer/styles.css` 仿 `.project-type-godot-icon` 加 `.project-type-<key>-icon`
3. `src/renderer/project-types.tsx` 的 `ProjectTypeIcon` 加分支：

```tsx
if (type === "<key>") return <span className="project-type-<key>-icon" style={{ width: size, height: size }} aria-hidden="true" />;
```

（若图标需要品牌彩图而非单色，仿 `godot-icon.tsx` 建 `<key>-icon.tsx` 组件。）

## 步骤 9：工作区边界

`src/renderer/coding-workspace.tsx` 的 `publishingUnavailable` 加 `project?.type === "<key>"`。
Web 预览不用管：`isWebRuntimeProjectType` 只认 `web-game`/`general`，新类型天然无预览入口。

## 步骤 10：配套插件（若有）

配套插件包的 `plugins/<key>/.xcflow-plugin/plugin.json`（新名；旧名 `.ohmygame-plugin/plugin.json` 仅作存量回落，不再用于新建）：
`interface.projectTypes` 加 `"<key>"`。
若插件包尚未存在，本步骤跳过（壳不依赖插件也能跑）。

## 步骤 11：daemon 文案

`src/daemon/plugin-authoring.ts` 中 projectTypes 合法值清单（grep `asset-canvas` 定位）
补 `<key>`——这是 AI 建插件的提示词，漏了不影响运行。

## 步骤 12：首页类型下拉（决策点）

首页创建对话框用 `GAME_PROJECT_TYPES`（自动含新类型）。
**默认不过滤**；若用户不希望首页「新建游戏」出现该类型，
在 `home.tsx` 显式 `.filter(({ value }) => value !== "<key>")` 并告知用户。

**初始可见性与 `HIDDEN_PROJECT_TYPE_IDS` 的关系（2026-11-06 补）**：
新建类型只要不进 `project-types.tsx` 的 `HIDDEN_PROJECT_TYPE_IDS` 集合就自动可见，
侧边栏/首页下拉两处都是——即默认可见时本步零改动。若用户要默认隐藏，
用 `menu-item` 技能两落点一起改（`SIDEBAR_ITEMS` 加 `visible: false` + 集合加成员），
不要只改一半。集合声明须为 `ReadonlySet<ProjectType>`（否则下次新增类型时 `.has()` 报 TS2345）。

## 可选步骤：定制设计页

新工作室默认复用共享画布（`CanvasWorkspace`，数据在工程 `canvas/` 目录，agent 用
`canvas_init`/`canvas_check` 工具协作），无需写代码。若需要该类型专属的设计页
（如 FairyGUI 组件树 + 预览），照 `dev-docs/design/设计页面机制分析与自定义指南.md`
的方案 B：新建工作区组件（props 契约参照 `canvas-workspace.tsx`），在
`project-shell.tsx` 的三向分支处加第四向。这是独立决策，不阻塞脚手架验收。

## 验收（全部通过才算完成）

1. `bun run typecheck` 通过。
2. 重启 daemon。具体命令（只杀监听 PID，禁止 `taskkill //F //IM node.exe` 这种全杀）：
   `netstat -ano | grep ":43110" | grep LISTENING` 拿 PID →
   `taskkill //F //PID <pid>` → `bun run dev:daemon` 后台拉起 →
   轮询 `curl http://127.0.0.1:43110/health` 到 ok。
   注：`dev:daemon` 是 tsx --watch 模式，改 daemon/shared 代码通常自动重启，
   但验收前手动重启一次最保险（watch 对个别变化不敏感）。
3. `GET http://127.0.0.1:43110/plugins`：配套插件（若有）projectTypes 含新类型。
4. `POST /projects`（body 用文件 `--data-binary @file`，含中文时 curl 直传会
   Content-Length 不匹配）：`{"name":"...","type":"<key>","workspacePath":"..."}` 返回 200。
5. 浏览器（或 Chrome DevTools MCP）验证 `http://127.0.0.1:43120/#/<key>`：
   - **坑：启动恢复会劫持导航（2026-11-06 踩）**：直接开 `#/<key>` 或整页 navigate
     会触发 reload → 应用「恢复上次会话」逻辑把 URL 拉回上次的项目会话页，
     误判为路由解析失败。正确做法：等应用加载完后用 hashchange 切换
     （`location.hash = "#/<key>"`，不触发 reload）。
   - DevTools MCP 的 `evaluate_script` 用 `async () => { ...; await new Promise(r => setTimeout(r, 800)); ... }`
     平铺写法；嵌套 Promise 回调 + 复杂字面量容易报语法错（missing ) after argument list）。
   - 检查点：侧边栏工作室组出现新菜单项、图标正常（computed style 的 mask-image 有 data URI）；
     首页标题/提示语/新建按钮文案正确；「查看全部」跳 `#/projects?type=<key>`；
     新建的项目卡片出现。
6. 回归：既有工作室（网页游戏/互动故事/Godot/素材画布/通用）页面正常。

## 提交与文档

- 一个 commit：`feat: add <key> studio (project type + sidebar + boundaries)`。
- 按仓库 CLAUDE.md：更新 `dev-docs/progress/执行进度.md` 里程碑表，
  新建 `dev-docs/progress-result/<阶段>-执行报告.md`（新阶段新文件，禁止追加他人）。
