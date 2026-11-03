# ohmygame 品牌清理 执行报告

- 日期：2026-11-02
- 关联计划：`dev-docs/planning/completed/ohmygame品牌清理执行文档.md`、盘点底账 `dev-docs/research/ohmygame残留盘点.md`
- 决策：D1 产品名 XC-UI-Flow；D2 appId com.xc.uiflow；D3 无自有域名，下载/更新链接改 GitHub Releases；D4 包名 xc-ui-flow；D5 UI 文案跟 D1；D6 协议名 `.ohmygame-plugin` 等冻结不改

## P0 零风险改名（commit `8ed1349`）

- SVG 资产改名 `xcflow-mark(-dark)-v2.svg`（含内部 mask id）+ 7 处 import
- `build/installer.nsh`：`OhMyGameInstallProgress*` → `XcFlowInstallProgress*`
- `vite.config.ts` project 名、`vite.sandbox.config.ts` 沙盒窗名
- 备注：`ohmygame-studio` 目录名即 EXTERNAL_MCP_SERVER_NAME 协议 id，P0 未改名，冻结进 P2 文档

## P1 用户可见品牌统一（commit `8c7c9f0`，142 文件）

- `package.json` name/repository、`electron-builder.yml` productName/appId/artifactName
- locales en/zh-CN **只改 value 不改 key**；i18n key `includedWithOhMyGame` 随符号级统一为 `includedWithXcFlow`（两侧同步）
- README/docs/workflows/SECURITY 等全部 `OhMyGame` → `XC-UI-Flow`；下载/更新链接 → GitHub Releases；`DESKTOP_UPDATE_URL` 置空
- env：`XCUIFLOW_FFMPEG_PATH` 优先 + `OHMYGAME_FFMPEG_PATH` fallback（`src/daemon/publish/media.ts`、`.env.example`）；`projectProcessEnvironment` 同步过滤 `XCUIFLOW_` 前缀
- 符号重命名（驼峰误伤修复后定型）：`onOhMyGame`→`onXcFlow`、`ensureOhMyGamePiEnvironment`→`ensureXcFlowPiEnvironment`、`readOhMyGameManifest`→`readXcFlowManifest` 等
- **升级兼容**：向导模板内容变化，旧 hash 进 `PROJECT_GUIDE_UPGRADES`（AGENTS.md/README.md 各 +1），存量工程向导可升级
- 踩坑（详见 dev-docs/experience/批量替换误伤标识符.md，若未落盘见下方经验索引）：批量替换 `OhMyGame`→`XC-UI-Flow` 会误伤驼峰标识符（连字符非法）与 `${` 模板相邻品牌词；修复用「标识符上下文正则 → XcFlow」二轮收敛

## P2 协议 id 冻结落盘（commit `064c773`）

- 新增双语 `docs/protocol-names.md` + `docs/zh-CN/protocol-names.md`：冻结原因、全清单（11 类）、改名政策（新 id 用 `XCUIFLOW_`/`xcflow-`，旧名是兼容面不是债，改名必须配 fallback+迁移单独发版）
- 冻结 id 定义处加来历注释：`GODOT_MCP_SERVER_ID`、`OHMYGAME_MARKETPLACE`、`EXTERNAL_MCP_SERVER_NAME`
- docs/README.md 挂索引

## P3 扫尾（commit `a061ff4`）

- installer 内部符号 `OhMyGameExtractProgress` → `XcFlowExtractProgress`（nsh + fixture 同步）
- 上游插件（game-studio/threejs-world/web-game-studio/taptap-maker）SKILL 文案与脚本提示语 → XC-UI-Flow
- `docs/desktop-releases.md` 示例桶/Sentry/输出名 → xcflow；`docs/contributing.zh-CN.md` clone 命令 → xc-ui-flow
- 残留收敛到白名单：协议 id（`ohmygame:*`、`.ohmygame-plugin`、`OHMYGAME_*`、`ohmygame-*` 参数/entry/前缀等）+ 上游出处（WhiteTowerAI/ohmygame、ohmygame-cloud、ohmygame-examples）

## 验证

- `bun run typecheck` exit=0（每个阶段单独跑、看退出码）
- vitest（真 runner 为 `bun run test`，**不是 `bun test`**）全量基线对比：改后失败集与干净基线一致（41↔39 条均为环境性：Windows symlink EPERM、tasklist 冒烟、隐藏工作室遗留 project-types 3 条）
- `bun run build:renderer` exit=0
- 插件加载冒烟：preinstalled-plugins/plugin-catalog 通过，`.ohmygame-plugin` 发现协议未破坏

## 遗留问题

- `test/project-types.test.ts` 2 条 + `test/bundled-plugins.test.ts` 1 条失败：**隐藏工作室（menu-item）特性的断言未同步**，与品牌清理无关（基线同样失败），待单独修
- runner 坑：`bun test`（bun 自带 runner）与 `bun run test`（vitest）行为不同——bun test 会扫进 `thirdparties/` 子模块测试且缺 `vi.waitFor`，验收一律用 `bun run test`
