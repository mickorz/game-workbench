# ohmygame-plugin 目录改名 执行报告

- 日期：2026-11-03
- 关联计划：`dev-docs/planning/completed/ohmygame-plugin目录改名执行文档.md`
- 决策：D1 新名 `.xcflow-plugin`；D2 内置 14 目录迁移；D3 protocol-names.md 旧名行保留改述（全部默认值）

## P1 双读发现（commit `b98923f` 前半）

- `src/shared/plugins.ts`：新增 `PLUGIN_MANIFEST_WRITE_PATH = ".xcflow-plugin/plugin.json"` 与 `PLUGIN_MANIFEST_PATHS = [新名, 旧名]`（顺序即优先级）；归档隐藏目录白名单加 `.xcflow-plugin`（旧名保留）
- 读取方双落：`local-plugins.ts readPluginManifest`（首个存在者胜）、`plugin-discovery.ts` 目录候选与 marketplace 双处、`plugin-setup.ts` draft 清单读
- 写入侧新名：`copyForAuthoring`（同时删旧名清单文件防双清单并存）、`plugin-capabilities.ts` create-mcp、`plugin-setup.ts` create-mcp
- draft updateIcon：读到哪份写回哪份（原地更新，不制造双清单）
- portability：导出写新名清单与新名 backup（`.xcflow-plugin/backup.json`）；backup 读双落（旧归档兼容）

## P2 内置目录迁移（commit `b98923f` 后半）

- 14 个 `plugins/*/.ohmygame-plugin` → `.xcflow-plugin`（git mv）
- daemon 重启冒烟：`GET /plugins` 返回 15 插件、fairygui 在列、`errors: []`

## P3 测试与文档（commit `1b91c0c`）

- `plugins-protocol.test.ts` 三场景用例：新名单独可读、旧名单独可读（存量兼容）、双存新名优先
- `docs/plugins.md`：包契约改述新名 + 旧名保留可读说明（含 backup 路径）
- `docs/protocol-names.md` 双语：`.ohmygame-plugin` 行改述为「读回落保留，写入已迁移」
- `create-studio` 技能两处路径引用更新

## 踩坑（本轮新增）

- **backup 无文件是正常场景**：双落读取改写时把「无 backup」当成错误抛出（`Plugin backup not found` → import/inspect 400）。非本应用导出的原生 ZIP 插件包本来就没有 backup，必须保持 undefined 继续。修复：`if (backupContent)` 包裹解析。
- **copyForAuthoring 双清单并存**：cp 整个旧名插件目录后又写新名清单，若不删旧名清单文件，导出归档里双清单并存。修复：写新名前删旧名 `plugin.json`（只删清单文件，不动其他结构）。

## 验证

- `bun run typecheck` exit=0（每阶段单独跑）
- 插件测试 15 文件 123 条过；剩余 5 条失败全部为基线一致的 symlink EPERM 环境性（Plugin Builder ×2、agent-tools ×2、plugin-integration ×1，基线名单里均有）
- 旧名回落由存量旧名 fixtures 测试覆盖（122 条过）+ 新增三场景用例
- daemon 运行时冒烟：15 插件全载、errors 空

## 遗留

- `.data/plugins/installed/` 存量已装插件目录保持旧名原样（设计决策：不迁移，回落读取；下次导出或 copyForAuthoring 时自然变新名）
- 上游 ohmygame 生态插件（`.ohmygame-plugin`）永久支持读取
