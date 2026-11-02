# CLAUDE.md

本仓库（xc-ui-flow）的开发过程文档管理规范。

## 侧边栏修改必读：`docs/zh-CN/sidebar-config.md`

**任何涉及侧边栏（品牌名/品牌图标/主导航条目）的修改，先读 `docs/zh-CN/sidebar-config.md`**，按它操作：

- 配置唯一入口：`src/renderer/sidebar-config.ts`（`SIDEBAR_BRAND` 品牌名+图标 / `SIDEBAR_ITEMS` 导航数组），改组件代码无效
- 生效方式：开发态保存即生效（vite HMR）；桌面端/生产需 `bun run build:renderer` 重新构建
- 加新页面进导航要先在 `routes.ts` 注册路由；`labelKey` 必须在 locales 已存在（TypeScript 会校验）

## 项目技能：`.claude/skills/`

本地项目技能放在 `.claude/skills/<kebab-case>/SKILL.md`（随仓库提交）。现有：

| 技能 | 用途 |
|------|------|
| `backup-template` | 把当前代码与资源打包成模板 zip；执行层为仓库根 `backup_template.py`（`--no-delivery` 不带交付包 / `--list` 看清单） |
| `create-studio` | 新增一个工作室（侧边栏工作室页 + 项目类型，12 步脚手架）；详细流程在技能内 `references/add-studio-flow.md`，改前必读 |
| `chat-text-action` | 会话聊天文本新增可点击行为（markdown linkify + 自定义协议 + 动作透传，6 步）；详细流程在技能内 `references/chat-text-action-flow.md` |
| `menu-item` | 侧边栏菜单项与新建下拉类型的显隐管理（sidebar-config + HIDDEN_PROJECT_TYPE_IDS，两落点 + 3 坑） |

**工作室 bug 同步规则**：修复任何工作室（studio / 项目类型）相关 bug 时，若根因属于「新增工作室流程会再踩的坑」（如某步骤遗漏、某文件漏改、某机制的反直觉行为），必须把坑点和修法同步进 `.claude/skills/create-studio/references/add-studio-flow.md`（补进步骤或坑位说明），防止下次创建工作室时重蹈。只影响单个工作室自身的业务 bug 不需要同步。

## FairyGUI 插件：xc-link-plugin（改插件 / 新建 FGUI 工程必读）

编辑器侧桥插件的**源码唯一真身在 `thirdparties/xc-link-plugin/`**（随 git 提交，含全部补丁；不要直接改 `dev-examples/` 或 `plugins/fairygui/editor-plugin/` 里的副本后再同步回来）。改名历史：原上游名 agent-bridge（fork 自 fairygui-agent-bridge），全局注册表目录 `~/.fgui-agent-bridge/` 为 MCP/CLI 发现协议约定保留不改。

**接入 FGUI 工程的两种方式**：

1. **开发联调（推荐）——junction 链接，修改即同步**：
   ```powershell
   thirdparties\xc-link-plugin\install-link.bat <FGUI工程根目录>
   ```
   它在 `<工程>\plugins\xc-link-plugin` 建 junction 指向源码目录（免管理员）。改 `thirdparties/xc-link-plugin/main.js` 保存即生效，无需复制；`bridge.log` 也写在源码目录。
2. **分发给他人/交付——文件复制**：
   ```powershell
   plugins\fairygui\scripts\install.bat <FGUI工程根目录>
   ```
   把 `plugins/fairygui/editor-plugin/`（分发副本，内容与源码目录对齐）复制到 `<工程>\plugins\xc-link-plugin`。

**约束**：① junction 只在本机有效，克隆仓库后需重跑 install-link.bat；② 修改插件后先 `node --check thirdparties/xc-link-plugin/main.js` 再重启编辑器；③ 三处副本（源码目录 / editor-plugin 分发副本 / 测试工程链接）内容必须保持一致，改源码目录后同步分发副本：`copy thirdparties\xc-link-plugin\main.js plugins\fairygui\editor-plugin\main.js`。

## 开发文档目录：`dev-docs/`

`dev-docs/` 是本仓库专门保存开发过程文档的目录（已在 `.gitignore` 中忽略，不进入 git 仓库）。

> 边界：仓库根 `docs/` 是**读者向**文档（随项目分发、README 链接引用）；
> `dev-docs/` 只服务开发过程，两者不混放。
> 注意：`卡五星自动化流程-10-20/docs/` 是交付包自带的过程文档（01~07 编号），属于交付内容，不要与仓库根 `docs/` 混放，也不要挪动。

### 规则

1. **所有开发过程文档必须放在 `dev-docs/` 目录下**，不要散落在仓库根目录或其他位置。
2. **新建文档时先判断类型**，放入对应类型的子文件夹；子文件夹不存在时按需创建。
3. 子文件夹按文档类型分类，命名使用小写英文和连字符（kebab-case），例如：

   | 类型 | 子文件夹 | 说明 |
   |------|----------|------|
   | 设计方案 | `dev-docs/design/` | 架构设计、技术方案、接口设计 |
   | 会议记录 | `dev-docs/meeting/` | 会议纪要、讨论记录 |
   | 问题排查 | `dev-docs/troubleshooting/` | Bug 分析、故障排查、复盘 |
   | 调研笔记 | `dev-docs/research/` | 技术调研、选型对比、学习笔记 |
   | 任务计划 | `dev-docs/planning/` | 任务拆解、进度计划、里程碑 |
   | 执行进度 | `dev-docs/progress/` | 阶段性进度总结、里程碑状态 |
   | 执行报告 | `dev-docs/progress-result/` | 阶段完整执行报告、验收结果（区别于 progress 的持续进度表） |
   | 使用指南 | `dev-docs/guides/` | 操作手册、环境搭建、工作流说明 |
   | 经验沉淀 | `dev-docs/experience/` | 踩坑记录、问题解决方案、经验教训 |

4. 若现有分类不适用，可新建类型子文件夹，但需保持命名风格一致，并在本文件表格中补充登记。
5. 文档统一使用 Markdown 格式，文件名应能体现内容，例如 `2026-10-03-workflow-design.md`。
6. **自动归类，无需询问**：发现 `dev-docs/` 根目录下有未归类的文档时，直接按内容判断类型并移动到对应子文件夹，不要向用户确认。

## 进度文件夹：`dev-docs/progress/` 与报告文件夹：`dev-docs/progress-result/`

`dev-docs/progress/` 专门用于记录项目阶段性执行进度；`dev-docs/progress-result/` 专门用于沉淀阶段完整执行报告（区别于 progress 的持续进度表：progress 是滚动维护的状态，progress-result 是一次成稿的阶段报告）。

### 规则

1. **阶段完成必须记录**：每完成一个阶段/里程碑，必须更新进度文档，不得只提交代码不更新进度。
2. **双文件夹同步更新**：每次执行完一个里程碑，除更新 `dev-docs/progress/` 外，还必须同步更新 `dev-docs/progress-result/` 中的对应阶段执行报告（新建或追加）。两个文件夹缺一不可。
3. **每阶段独立报告文件**：阶段报告按阶段命名（`P0-执行报告.md`、`P1-执行报告.md`、`P2-执行报告.md`...），**新阶段内容必须写入新文件，禁止向其他阶段的报告文件追加**（含 `cat >>`）。已完成阶段的报告视为只读；报告内引用其他阶段（如"P2 方向"）允许，但不承载其他阶段的执行记录。
4. **进度文档要求维护到位**：更新 `dev-docs/progress/执行进度.md`（持续维护的总进度文档）中的里程碑状态表，并视情况为该阶段新建独立进度/验收文档；记录内容包括：完成时间、交付清单、commit 记录、经验索引、遗留问题。
5. **进行中也要反映**：阶段启动、中途重要节点（如架构决策、验收通过/失败）都应同步到进度文档，保证文档与仓库实际状态一致。
6. 新的进度文档放入本文件夹，命名体现阶段或日期，例如 `P0-验收报告.md`、`2026-10-03-执行进度.md`。

## 经验文件夹：`dev-docs/experience/`

`dev-docs/experience/` 专门用于沉淀开发过程中遇到的坑点和解决方案。

### 规则

1. **遇到坑必须记录**：开发中碰到坑（如环境问题、依赖冲突、隐蔽 Bug、反直觉行为等）并解决后，将问题现象、原因分析、解决步骤记录到 `dev-docs/experience/` 下，一篇文档记录一个问题。
2. **解决问题前先查经验**：每次遇到问题时，必须先到 `dev-docs/experience/` 下查找是否之前碰到过类似问题：
   - 若有记录，优先按已有经验尝试解决，解决后视情况补充更新原记录（如新的解决方法、适用版本变化）。
   - 若无记录，解决完成后再将完整过程沉淀为新文档。
3. 经验文档建议结构：**问题现象 → 排查过程 → 根因 → 解决方案 → 预防/注意事项**，文件名体现问题关键词，例如 `node-version-conflict.md`。

## 示例目录：`dev-examples/` —— 开发期沙盒

1. 开发中的脚本试验、联调配置与临时输出一律放 `dev-examples/`（一主题一子目录，kebab-case），
   **不对读者负责**，内容可随时失效或删除，不进 README 宣传、不被其他文档引用。
2. 运行产物一律 gitignore 不提交；详细约定见 `dev-examples/README.md`。
3. 毕业路径：`dev-examples/` 里验证通过 → 合入正式代码 → 必要时在 `docs/` 落地读者向文档 → 删除沙盒里对应目录。

## opencode run 测试约定

本项目执行层使用 OpenCode（`.opencode/` 目录承载命令、技能与插件），`opencode run` 联调约定适用：

1. **并发上限：最多同时运行 2 个 `opencode run` 用例**。需要更多用例时排队分批跑。
2. 验收类长任务前先预热检查模型可用：`opencode run --model <model> "只回复 ok"`。
3. 每个 run 必须配看门狗：记录直连 PID，超时 `pkill -P $pid` + `kill $pid`；agent 链（feature-development 等）预算 ≥20 分钟，短 flow 5–8 分钟。
4. 证据优先级：journal + traceDir 文件 > stdout（stdout 可能截断或乱码，验收以落盘证据为准）。
5. 完整配方见 `dev-docs/experience/opencode-run-hang-watchdog.md`。
