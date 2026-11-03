# ohmygame 残留盘点（文件名 / 文件夹 / 文件内容）

> 背景：本仓库（xc-ui-flow）由上游 ohmygame（WhiteTowerAI/ohmygame）复制源码而来，品牌仅做了表层改名（侧边栏品牌、仓库名）。
> 上游源码作为子模块参照保留在 `thirdparties/ohmygame`。本文盘点仓库内（排除子模块与运行时数据）所有 ohmygame 痕迹，作为后续品牌清理的底账。
> 盘点日期：2026-11-02；范围：文件名、文件夹名、文件内容（grep -ri，排除 `thirdparties/`、`node_modules/`、`.git/`、`.data/`、`.runtime/`、构建产物）。

## 一、总量

| 范围 | 含 ohmygame 的文件数 | 说明 |
|------|------|------|
| 全仓（除子模块/运行时数据） | 约 380 | 文件内容含 `ohmygame`（大小写不敏感） |
| `src/`（daemon + desktop + renderer + shared + story-web） | 157 | 代码与注释 |
| `test/` | 181 | 测试断言/夹具（跟随 src 引用） |
| `docs/` + 根级 md（README/CONTRIBUTING/CHANGELOG/SECURITY） | 24+ | 读者向文档 |
| `scripts/` + 构建配置 | 11+ | 构建与测试脚本 |
| `plugins/`（除 fairygui 新写内容） | 7 | 上游插件残留 |
| 高频标识形态 | 1446 处 `ohmygame` 裸词 | 变体见下文分类 |

## 二、分类清单

### A. 刻意保留（勿动）

| 项 | 位置 | 说明 |
|------|------|------|
| 上游子模块 | `thirdparties/ohmygame/`（.gitmodules 登记锁 `ca2df72`） | 参照真身，与仓库根同名目录是复制出来的工作副本 |
| 上游仓库引用 | `package.json` bugs/repository url（github.com/WhiteTowerAI/ohmygame）、CHANGELOG 历史 | 出处追溯 |

### B. 目录/文件名残留（git 跟踪）

| 项 | 位置 | 性质 |
|------|------|------|
| 插件清单目录 `.ohmygame-plugin/` | 15 个插件（aseprite/blender/cocos-creator/…/fairygui） | **协议约定**：`src/shared/plugins.ts` 的 `PLUGIN_MANIFEST_PATH = ".ohmygame-plugin/plugin.json"`，daemon 按此发现插件；改名需同步全部插件与存量工程 |
| 插件技能目录 `integrations/skills/ohmygame-studio/` | 仓库根 + 子模块镜像 | agent 技能，名字含上游品牌 |
| 品牌 SVG | `src/shared/assets/ohmygame-mark-v2.svg`、`ohmygame-mark-dark-v2.svg` | 侧边栏/加载页旧品牌图（已被 xc-ui-flow 品牌替换使用与否需确认） |

### C. 产品/品牌标识（用户可见，品牌不一致的重灾区）

| 项 | 位置 | 当前值 |
|------|------|------|
| 包名 | `package.json` `"name": "ohmygame"` | npm/bun 包标识 |
| 桌面端产品名 | `electron-builder.yml` `productName: OhMyGame`、`appId: ai.ohmygame.desktop`、artifactName `OhMyGame-*` | 安装包/开始菜单/进程名 |
| 安装器函数名 | `build/installer.nsh` `OhMyGameInstallProgressStart/Finish/Update` | NSIS 内部符号（用户不可见，但改名成本为零） |
| 环境变量前缀 | `.env.example` `OHMYGAME_FFMPEG_PATH`、更新源 `https://updates.ohmygame.ai/desktop` | 桌面更新协议 |
| UI 文案 | `src/renderer/locales/en.ts` / `zh-CN.ts`：`Welcome to OhMyGame`、`Preparing OhMyGame`、`OhMyGame account`、`ohMyGameAccount` 等（约 10+ 条） | **用户直接可见** |
| README 下载徽章 | `README.md` / `README.zh-CN.md` 指向 `ohmygame.ai/download/*` | 下载入口 |
| 更新域名 | `docs/desktop-releases.md` `updates.ohmygame.ai` | 文档+内置 feed |
| GitHub 工作流/模板 | `.github/workflows/release-desktop.yml`、issue 模板 | 发布流水线引用产品名 |

### D. 协议/存储/接口约定（改名 = 破坏兼容，需迁移）

| 项 | 位置 | 影响 |
|------|------|------|
| MCP server id | `src/shared/mcp.ts` `GODOT_MCP_SERVER_ID = "ohmygame-godot"` | Godot 插件 MCP 标识 |
| 插件市场 id | `src/shared/plugins.ts` `OHMYGAME_MARKPLACE id "ohmygame"` | 插件市场索引 |
| 检查点文件名 | `.data/projects/*/checkpoints/ohmygame-pruned.json`、`ohmygame-stat-cache.json`、`ohmygame-unfinished.json` | 存量项目数据按名寻址（daemon 生成，改名需兼容读旧名） |
| 临时目录前缀 | `ohmygame-workspace-`、`ohmygame-playable-publish-*`、`ohmygame-thumbnails-` 等（src/daemon 多处） | 系统临时文件命名 |
| 类/接口/事件名 | `ohmygamepienvironment`、`ohmygamemanagedpipackages`、`ohmygameplaytest`、`ohmygame-install-pending` 等（约 10 个驼峰符号，src/daemon + test） | 代码符号，改名要同步测试 |
| Vite/sentry project 名 | `vite.config.ts` `project: "ohmygame"`、`vite.sandbox.config.ts` `OhMyGamePlayableSandbox` | 遥测项目名/构建 target |

### E. 代码注释、测试、文档提及（无行为影响）

- `src/` 大量注释（如 `src/shared/contracts.ts` "Internal OhMyGame data…"）
- `test/` 181 个文件的断言、夹具路径（跟随 D 类符号）
- `docs/` 24 篇 + 根级 md 的上游链接与历史叙述
- `plugins/game-studio`、`web-game-studio`、`threejs-world`、`taptap-maker` 技能与脚本内提及
- `dev-docs/`、`.claude/skills/`（本项目过程文档，记录上游历史，保留）

### F. 运行时/本地数据（不算残留，无需清理）

`.data/`（marketplace 缓存、项目检查点）、`.runtime/examples/`（示例运行时目录，gitignore）、`bun.lock`（包名锁）、`dev-examples/daemon.log`。

## 三、处理建议（分级）

1. **必须决策**（品牌不一致，用户可见）：C 类全部——productName/appId/包名/locales 文案/README 徽章/更新域名。当前「xc-ui-flow 仓库 + OhMyGame 界面」是分裂状态。
2. **要改需带迁移**（破坏兼容）：D 类——`.ohmygame-plugin` 目录约定、MCP id、marketplace id、检查点文件名。建议单独一个 PR 做，且保留旧名兼容读。
3. **随手可改**（零风险）：B 类 SVG 资产名、`integrations/skills/ohmygame-studio` 目录名、installer.nsh 符号、E 类注释。
4. **永不动**：A 类上游子模块与出处链接。

## 四、类比理解

把仓库想成一家换过招牌的店：门头（侧边栏品牌）换了 xc-ui-flow，但营业执照（package.json）、包装盒（安装包名）、会员卡系统（插件市场 id）、仓库货架编号（`.ohmygame-plugin`）全还是旧店名——顾客看门面是新店，拿到的收据还是旧店。清理 = 按上面四级清单逐层换证，货架编号（D 类）不能一刀切，要留旧编号对照表。

## 引用说明

- 上游仓库：https://github.com/WhiteTowerAI/ohmygame
- 本仓品牌改名历史：`dev-docs/design/侧边栏主导航可配置化分析.md`、`dev-docs/progress/执行进度.md`
- 插件发现协议：`src/shared/plugins.ts`（`PLUGIN_MANIFEST_PATH`）
- 桌面更新源：`docs/desktop-releases.md`
