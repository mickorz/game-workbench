# 配置参考

流程的全部配置集中在 `.opencode/` 下的几个文件里（均在 `卡五星自动化流程-10-20/` 工作区根）。

## 配置字段

| 文件 | 字段 | 默认 | 说明 |
|---|---|---|---|
| `.opencode/workspace.json` | `client_dir` | 无（`/s0-env` 写入） | client 工程根（`assets/` + `settings/` + `*.fairy` 所在层），s2/s3/s4 读写工程都靠它 |
| `.opencode/workspace.json` | `game_key` | 无（`/s0-env` 写入） | 游戏标识，需求产物落在 `.opencode/work/<game_key>/<需求>/` |
| `.opencode/workspace.json` | `素材库根` | `.opencode/PSD素材库` | PSD 素材库位置，find-asset 只读检索 |
| `.opencode/photocraft.json` | 控制端口等 | 参考 `photocraft.example.json` | PhotoCraft 桌面端连接配置，s4 导出切图用 |

## 生效与验证

- `workspace.json` 改完立刻生效，验证：`python .opencode/lib/workspace.py where`
- PhotoCraft 连接验证：`python .opencode/lib/photocraft.py --check`（会自动拉起桌面端）

## 升级

流程本体（`.opencode/skills/`、`.opencode/lib/`）随仓库更新；升级后建议重跑 `/s0-env` 并重扫事实底座（`scan_fgui.py`）。

## 卸载

删除 `卡五星自动化流程-10-20/.opencode/` 即可，不影响 client 工程；`.opencode/work/` 里是历史需求产物，删前先确认没有要留档的交付物。
