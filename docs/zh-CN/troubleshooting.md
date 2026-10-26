# 常见问题排查

## 安装阶段

| 症状 | 原因 / 处理 |
|---|---|
| `/s0-env` 定位不到工程 | 确认 client 工程根有 `assets/` + `settings/` + `*.fairy` 三件套；还不行用 `workspace.py env --client <路径>` 显式指定 |
| `lookup.py` 报"事实表缺失/过期"（退出码 1） | 工程被改过，重跑 `scan_fgui.py`；确实要用旧数据加 `--force` |
| 脚本中文输出乱码 | Windows 控制台默认 GBK；脚本内部已 `reconfigure(encoding="utf-8")`，用 Windows Terminal 或 `python -X utf8` 跑 |
| 需要 Pillow 的脚本报 ImportError | `pip install Pillow` |

## 运行阶段

| 症状 | 原因 / 处理 |
|---|---|
| `lookup.py <关键词>` 退出码 3（命中 0） | 脚本不猜，会列候选清单；换中文备注词或英文文件名再搜，或分开单搜看哪个词命中最多的提示 |
| s2 落位后编辑器里组件不显示 | 检查跨包引用是否写了 `pkg="<8位包id>"` 且目标组件勾了"导出"——漏任一项会静默失效 |
| 新建的包在编辑器里双击无反应 | 包 id 必须正好 8 位（`ui://` 按前 8 位切分），超长会静默查不到且无报错 |
| 新增图片在编辑器里看不到 | 文件没登记进 package.xml；必须在编辑器里导入或补登记，否则不发布 |
| PhotoCraft 连不上 | `python .opencode/lib/photocraft.py --check` 自动拉起桌面端；报"路径越界"看报错里的 automation read/write root |
| 导出 PNG 文字没变 | `_pc_export.py --texts` 的键必须是带 `out_` 前缀的完整图层名，且图层是真文字层（TySh）不是栅格像素 |
| s4 改完 PSD 打不开 | 跑 `_psd_struct.py <psd>` 字节级自检，按报错定位解析口径问题 |
| `find-asset` 全是"无候选" | 种类是硬条件（图片/组件/位图字体不同不候选）；确认清单条目的 种类/来源/状态 字段填对了 |

## 仍卡住

- 交付包内文档：`卡五星自动化流程-10-20/docs/04-技能与脚本参考.md`、`卡五星自动化流程-10-20/docs/05-知识库与素材库.md`
- 踩坑沉淀：`dev-docs/experience/`（先查有没有同类记录）
- 问题排查记录写进 `dev-docs/troubleshooting/`，跨项目可复用的经验沉淀到 `dev-docs/experience/`
