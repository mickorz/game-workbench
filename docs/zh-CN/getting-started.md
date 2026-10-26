# 快速开始

从零到第一次跑通卡五星美术自动化流程。

## 前提条件

- Windows 10/11
- OpenCode（CLI 已在 PATH 中，`opencode --version` 可执行）
- Python 3.10+，且安装 Pillow：`pip install Pillow`
- FairyGUI 编辑器（打开 client 工程校验效果用）
- PhotoCraft 桌面端（仅 s4 PSD 切图需要）
- 本机已放置卡五星 client 工程（含 `assets/` + `settings/` + `*.fairy`）

## 安装

1. 克隆本仓库，进入 `卡五星自动化流程-10-20/`（OpenCode 工作区根，含 `.opencode` 的那层）
2. 在该目录启动 OpenCode
3. 运行 `/s0-env` 做环境配置：定位 client 工程根，结果写入 `.opencode/workspace.json`

## 验证

```powershell
python .opencode/lib/workspace.py where
```

输出应包含工作区根、client 工程根（client_dir）与工作层 out_root（`.opencode/work`）。三者都能解析出真实路径即配置成功。

## 第一次运行

1. 把一份美术需求 Excel 放入 `.opencode/inbox/`（参考 `.opencode/inbox/[测试]美术需求.xlsx` 的列结构）
2. 运行 `/s1-req`，产物落在 `.opencode/work/<game_key>/<需求>/`：需求.md、参考图_1334x750/、清单.json、施工单.md
3. 运行 `/s2-fgui`，Agent 会扫描 FGUI 工程、出方案、改组件 XML；落位后停下来等你确认效果
4. 在 FairyGUI 编辑器里打开 client 工程核对效果

## 下一步

- 命令逐条说明：[configuration.md](configuration.md) 与交付包内 `卡五星自动化流程-10-20/docs/03-命令手册.md`
- 常用操作任务：[how-to-guides.md](how-to-guides.md)
