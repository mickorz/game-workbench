# xc-ui-flow

卡五星 FGUI 美术自动化流程交付包：用 OpenCode Agent 流水线把「Excel 美术需求 + 参考截图」变成 FGUI 工程改动、PSD 还原稿与切图交付。

## 概述

本仓库是卡五星（武汉麻将）项目的 FGUI 美术自动化流程交付包，主体在 `卡五星自动化流程-10-20/`，内含完整的 OpenCode 工作区（`.opencode/`：命令、技能、知识库、PSD 素材库、Python 脚本库）。

核心能力：

- **s1 需求解析**：Excel 需求自动拆条目、提取参考截图、适配画布（1334x750）、机械检查错别字、生成施工单
- **s2 FGUI 落位**：扫描 FGUI 工程生成事实底座（facts.json），按复用优先 7 级决策改组件 XML，缺图先占位
- **s3 转 PSD**：把 FGUI 界面还原成美术可改图的分层 PSD
- **s4 PSD 样式**：从 PSD 素材库查可复用稿（改字/改色/改尺寸/九宫格重排），导出透明切图回填工程
- **PSD 素材库**：可复用源 PSD 的只读检索库，带索引与预览图
- **知识库**：资源复用技巧、对齐成组、素材种类等工程实测经验

## 快速开始

### 环境要求

- Windows + OpenCode（执行层，命令定义在 `卡五星自动化流程-10-20/.opencode/`）
- Python 3（部分脚本需要 Pillow：`pip install Pillow`）
- FairyGUI 编辑器（查看/校验工程改动）
- PhotoCraft 桌面端（仅 s4 切图导出需要）

### 首次配置

1. 在 `卡五星自动化流程-10-20/` 打开 OpenCode
2. 运行 `/s0-env` 定位 client 工程根，写入 `.opencode/workspace.json`
3. 参考 `卡五星自动化流程-10-20/docs/02-安装与首次配置.md` 完成素材库等配置

### 跑通一个需求

1. 把美术需求 Excel 放入 `卡五星自动化流程-10-20/.opencode/inbox/`
2. 运行 `/s1-req` 解析需求（生成清单.json + 施工单.md + 参考图_1334x750/）
3. 运行 `/s2-fgui` 落位改工程 → 人看效果定稿
4. 需要出 PSD 时运行 `/s3-to-psd`，改样式切图运行 `/s4-psd`

详细命令说明见 `卡五星自动化流程-10-20/docs/03-命令手册.md`。

## 目录结构

```text
CLAUDE.md                     开发过程文档管理规范
卡五星自动化流程-10-20/        流程交付包主体（OpenCode 工作区）
├── AGENTS.md                 Agent 硬规矩（会话自动加载）
├── docs/                     流程文档（01~07 编号）
├── fgui文档/                  核心流程总纲与操作手册
└── .opencode/                命令、技能、知识库、PSD 素材库、脚本库
docs/                         读者向文档（本目录）
dev-docs/                     开发过程文档（不进 git）
dev-examples/                 开发期沙盒（不进 git）
```
