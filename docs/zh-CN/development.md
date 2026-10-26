# 贡献者指南

面向要改流程本体（技能/脚本）的贡献者。开发过程文档放 `dev-docs/`（不进 git），规范见根目录 `CLAUDE.md`。

## 环境与常用命令

- Python 3.10+（标准库优先，仅图像脚本用 Pillow）
- 事实底座：`python .opencode/skills/fgui-flow/scripts/scan_fgui.py`
- 新鲜度自查：`python .opencode/skills/fgui-flow/scripts/lookup.py --check`
- 关键词定位：`python .opencode/skills/fgui-flow/scripts/lookup.py <关键词>`
- 全部脚本零硬编码路径，统一经 `.opencode/lib/workspace.py` 定位

## 架构速览

- `.opencode/command/s0~s4*.md`：用户入口命令（斜杠命令），各自加载对应技能
- `.opencode/skills/fgui-req|fgui-flow|fgui-to-psd|psd-style/`：四个阶段技能（SKILL.md 定义行为 + scripts/ 可跑脚本）
- `.opencode/lib/workspace.py`：共享库（路径定位、清单管理、find-asset 打分、snapshot/place）
- `.opencode/knowledge/`：运行时知识库，`knowledge.py --topic` 现读，不凭记忆
- `.opencode/PSD素材库/`：只读素材库，`build_index.py` 离线维护索引与预览图

流程链路：s1 解析需求 → s2 改 FGUI 工程 → s3 出 PSD 还原稿 → s4 改样式切图回填。细节见 `卡五星自动化流程-10-20/docs/01-总览与架构.md`。

## 测试

- 脚本改动后先跑对应技能的自查命令（如 `lookup.py --check`、`_psd_struct.py <psd>` 字节级自检）
- 新建脚本要求：纯文本可 `--help` 验证；涉及解析/重写的必须有字节级或结构自检
- 联调用 `opencode run`，并发上限 2、必配看门狗，见根目录 `CLAUDE.md` 的测试约定

## 本地开发循环

1. 改技能 SKILL.md 或脚本 → 2. 用小需求走一遍 s1→s4 链路 → 3. 检查 `.opencode/work/` 产物与 client 工程改动 → 4. 沉淀踩坑进 `dev-docs/experience/`（毕业后并入 `.opencode/knowledge/`）

## 发布

交付以仓库为单位；给美术/程序交付的是 `卡五星自动化流程-10-20/` 内的产物（FGUI 工程文件、PSD、切图），`.opencode/` 与 `dev-docs/`、`dev-examples/` 不进交付。
