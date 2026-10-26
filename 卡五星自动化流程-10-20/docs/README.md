# FGUI 美术流程 · 文档中心

本目录是 `.opencode` 流程包的**使用与交付文档**。目标是：拿到压缩包的人，不看聊天记录也能装好、跑通、维护、再打包给别人。

> 先读：`docs/01-总览与架构.md`，再按需要查对应章节。
> 工程规则的最高优先级仍是工作区根的 `AGENTS.md`；各技能的 `SKILL.md` 是执行细节的**唯一出处**。

## 文档导航

| 文档 | 给谁看 | 内容 |
|---|---|---|
| `01-总览与架构.md` | 所有人 | 这套东西是什么、五步流程、目录结构、核心规矩 |
| `02-安装与首次配置.md` | 接收方 / 新机器 | 前置软件、拷贝位置、s0 定位、首次自检 |
| `03-命令手册.md` | 使用者 | `/s0-env` ~ `/s4-psd` 的输入、产物、闸门与下一步 |
| `04-技能与脚本参考.md` | 使用者 / 维护者 | 5 个技能、共享库、脚本清单、退出码 |
| `05-知识库与素材库.md` | 使用者 / 美术维护 | 动态知识库怎么查、怎么加；PSD 素材库怎么维护 |
| `06-PhotoCraft与MCP配置.md` | 接收方 / 环境维护 | PhotoCraft 桌面端、控制端口、token、opencode MCP、Python 客户端 |
| `07-打包与迁移.md` | 发包方 | 哪些文件要带、哪些要清、怎么打包、接收方怎么验收 |
| `08-常见问题.md` | 所有人 | 命令不出现、定位失败、PhotoCraft/MCP 连不上等 |

## 一分钟上手

前提：Windows + Python 3.10+ + opencode；s3/s4 另需 PhotoCraft 桌面端。

```powershell
# 1. 在「含 .opencode 的那层」启动 opencode
# 2. 定位真实 FGUI 工程（写入 .opencode/workspace.json）
python .opencode/lib/workspace.py env --check
python .opencode/lib/workspace.py env

# 3. 看定位结果
python .opencode/lib/workspace.py where

# 4. 自检 PhotoCraft（s3/s4 需要；会自动拉起桌面端）
python .opencode/lib/photocraft.py --check

# 5. 在 opencode 里按顺序执行
# /s0-env  → /s1-req → /s2-fgui → /s3-to-psd → /s4-psd
```

## 打包入口

```powershell
# 生成一个干净的交付目录和 zip（默认排除 work/inbox/node_modules）
powershell -ExecutionPolicy Bypass -File docs/tools/pack_release.ps1

# 需要把某个需求的 work 产物也带上时
powershell -ExecutionPolicy Bypass -File docs/tools/pack_release.ps1 -IncludeWork

# 只出目录、不压缩
powershell -ExecutionPolicy Bypass -File docs/tools/pack_release.ps1 -SkipZip
```

详见 `07-打包与迁移.md`。

## 文档维护约定

- 文档写的是**稳定的使用口径**；具体命令参数、坑位、脚本细节以各技能 `SKILL.md` 和脚本 `--help` 为准。
- 知识库内容**不要抄进本文档**，统一用 `knowledge.py` 现读，避免知识库更新后文档过期。
- 新增技能或脚本时，同步更新 `03`、`04` 两张表；新增交付相关文件时同步更新 `07`。
