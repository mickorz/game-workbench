# 侧边栏配置使用指南（sidebar-config）

> 读者向：给要改侧边栏品牌/导航的人用。原理分析见 `dev-docs/design/侧边栏主导航可配置化分析.md`。

## 配置文件在哪里

**唯一入口**：`src/renderer/sidebar-config.ts`

这个文件集中管理左侧栏的两块内容，改别处无效：

| 配置项 | 管什么 | 类型 |
|---|---|---|
| `SIDEBAR_BRAND` | 品牌名 + 品牌图标 | 常量对象 |
| `SIDEBAR_ITEMS` | 主导航的全部条目（顺序/分组/显隐/图标/文案） | 数组 |

页面组件 `app-sidebar.tsx` 只负责渲染，不写任何具体条目——改配置即可，**不需要动组件代码**。

## 配置项怎么改

### 品牌名与图标（SIDEBAR_BRAND）

```ts
export const SIDEBAR_BRAND = {
  name: "xc-ui-flow",          // 品牌名：侧边栏文字 + 图标 alt
  mark: brandMark as string,   // 图标 URL：静态资源路径或 data URI
} as const;
```

- **改名**：改 `name` 字符串即可
- **换图标**：`mark` 填任意图片 URL。三种写法：
  - import 一个 SVG/PNG：`mark: myLogo as string`（文件顶部加 import）
  - 公开路径：`mark: "/my-logo.png"`（放 `public/` 等静态目录）
  - data URI：`mark: "data:image/svg+xml,..."`（内嵌，不依赖文件）

### 导航条目（SIDEBAR_ITEMS）

```ts
export const SIDEBAR_ITEMS: SidebarItemConfig[] = [
  { id: "home",      labelKey: "sidebar.home",      icon: "home",      group: "main" },
  { id: "projects",  labelKey: "sidebar.projects",  icon: "project",   group: "main" },
  // ...
  { id: "web-game",  labelKey: "projectType.web-game", icon: "web-game", group: "studios" },
];
```

常用操作对照：

| 想做什么 | 怎么改 |
|---|---|
| 隐藏某项 | 该条加 `visible: false`（路由仍可直达，只是侧边栏不显示） |
| 彻底删除 | 删掉那一行 |
| 调整顺序 | 移动数组元素位置（渲染按数组顺序） |
| 移动分组 | 改 `group`：`"main"`（主导航区）/ `"studios"`（「工作室」标题下） |
| 换文案 | 改 `labelKey` 指向的 i18n key（key 必须在 `src/renderer/locales/zh-CN.ts` 和 `en.ts` 里已存在，TypeScript 会校验） |
| 换图标 | 改 `icon`，只能取已注册的枚举值：home / project / library / plugins / community / interactive-story / asset-canvas / web-game / godot / general |

**约束**：`id` 只能是 `SidebarPage` 联合类型的成员（见 `src/renderer/routes.ts`），新页面 id 需要先在路由层注册才能进侧边栏。

## 改了以后如何生效

分两种运行方式：

### 开发模式（bun run dev:renderer，本机 http://127.0.0.1:43120）

**保存即生效，什么都不用做**。vite HMR 监听源码变化，保存 `sidebar-config.ts` 后约 1 秒内：

```
[vite] hmr update /src/renderer/sidebar-config.ts → app-sidebar.tsx → 浏览器自动重渲染
```

浏览器不刷新（保留当前页面状态），直接看到新品牌名/新导航。

### 桌面端 / 生产构建（bun run start:desktop 或打包产物）

**没有热更新，需要重新构建**：

```bash
bun run build:renderer    # 重新构建渲染层（或 build:desktop-app 全量）
```

Electron 壳里重开应用即可看到。配置是编译期打进产物的前端代码，不是运行时配置文件——所以生产包里改配置 = 重新出包。

### 一句话记忆

> **开发态：Ctrl+S 即所见；生产态：改配置 = 改代码 = 重新构建。**

## 常见问题

| 问题 | 原因/处理 |
|---|---|
| 改了 `labelKey` 编译报错 | key 不在 locales 里；去 `src/renderer/locales/zh-CN.ts`、`en.ts` 同步补 key |
| 图标填了 URL 不显示 | 开发态相对路径以项目根解析；优先 import 方式（走 vite 资源管道，最稳） |
| 想加全新页面进导航 | 侧边栏配置管不了路由：先在 `routes.ts` 加页面 id 与 hash 解析，再在 `app.tsx` 挂页面组件，最后配置里加条目 |
| 桌面端改了没变化 | 桌面端加载的是构建产物，重跑 `bun run build:renderer`（或完整 `build:desktop-app`）再启动 |

## 相关文件

- `src/renderer/sidebar-config.ts` —— 配置本体（改这里）
- `src/renderer/app-sidebar.tsx` —— 渲染组件（一般不用动）
- `src/renderer/routes.ts` —— 页面 id 定义与 hash 路由（加新页面才动）
- `src/renderer/locales/{zh-CN,en}.ts` —— 导航文案（改字面文字才动）
- `src/renderer/styles.css` —— `.home-nav-icon-*` 图标 mask（新增图标种类才动）
