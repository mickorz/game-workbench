---
name: fgui-env
description: FGUI 美术流程 s0 环境配置。当用户说"环境配置 / 定位工程 / s0 / 第一次配置 / 换机器配置 / 工程在哪"时使用。只做一件事：读 .opencode/xc_spce_info.json，按 game_id（外层目录名）+ game_key（assets 下前缀包）定位真实 client 工程目录，写进 .opencode/workspace.json（client_dir）。只做环境与定位，不改任何工程文件。
---

# s0 环境配置（`fgui-env`）

> **执行位置**：**工作区根** = 含 `.opencode` 的那层（`.xflow` 与它同级）。之后所有命令都在这层执行。
> 本技能无独立脚本；定位用共享库 `.opencode/lib/workspace.py`。

## 干什么（定位 + 自检）

```
s0 = ① 定位 client 工程（写 workspace.json）  ② 环境自检（提示）
```

### ① 定位 client 工程

```powershell
python .opencode/lib/workspace.py env --check   # 只查：算出 client_dir 并打印 game_id/game_key
python .opencode/lib/workspace.py env           # 定位并写入 workspace.json（client_dir/game_key/game_id）
python .opencode/lib/workspace.py where         # 打印 工作区根 / out_root / 素材库根 / client_dir / game_key
```

定位规则（两层确认）：
1. 读 `.opencode/xc_spce_info.json` 的 `project_info.client_code_root`（相对**工作区根**）。
2. **第一层**：`client_code_root` 下目录名 = `game_info.game_id` 的工程目录。
3. **第二层**：该目录 `assets/` 下存在**以 `game_info.game_key` 为前缀**的包（如 `boxKaWuXing_*`）。
4. 命中即写 `workspace.json`。

**找不到时**：脚本会**列出候选目录**并报错。人工确认后显式指定：
```powershell
python .opencode/lib/workspace.py env --client "相对或绝对路径"
```

### ② 环境自检（提示为主，不强退）

| 项 | 用途 | 检查 |
|---|---|---|
| Python 3.10+ | 所有脚本 | `python --version` |
| Pillow | `_fit_frames` / `_psd_preview` / `placeholder_png` / `_pc_export` | `python -c "import PIL"` |
| PhotoCraft 桌面端 | s3 搭 PSD / s4 导图 | `python .opencode/lib/photocraft.py --check`（会自动拉起） |

## 硬规矩

1. **只改 `.opencode/`**（`workspace.json`）；**不碰** client 工程内容、`.xflow`、`assets/`。
2. 定位失败**列候选、问人**，不猜；可用 `--client` 显式指定。

## 出口条件 & 交接

- 出口：`workspace.py where` 的 `client_dir` 存在于 `assets/` 有 `game_key` 前缀包。
- 交接：就绪后提示下一步 **`/s1-req`**（解析需求）。
