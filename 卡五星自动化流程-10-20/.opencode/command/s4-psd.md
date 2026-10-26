---
description: s4 改样式/切图 —— 改 PSD 图层样式/文字/尺寸，导出透明 PNG 回 client 工程
agent: fgui-flow
---

用 `skill` 工具加载 **`psd-style`** 技能，然后**严格按它的步骤与纪律**处理下面这份输入。

本轮的输入（需求名 / 源 PSD 路径 / 目标图层 / 逐项改动 / 要导出哪些图层 / 成图尺寸）：

```
$ARGUMENTS
```

规则：

- 先加载 `psd-style` 技能再动手；在**工作区根**（含 `.opencode` 的那层）执行，所有命令都在这里跑。
- 先 `python .opencode/lib/workspace.py where` 确认 `client_dir`（真实 FGUI 工程根，由 s0 写进 `.opencode/workspace.json`）。
- **有清单就先读清单**：`/s4-psd <需求>` → 读 `.opencode/work/<game_key>/<需求>/清单.json`，`python .opencode/lib/workspace.py find-asset <需求>` 查 PSD 素材库。候选会列出最外层制作单元、底图组以及分类独享的预览图路径（`分类/_预览/*.png`），需优先比对参考图外观后再**人确认**；产物落 `<需求>/psd/制作/`、`<需求>/切图/`。
- **源 PSD 三来源**（素材库命中 / 还原稿 / 用户给），**必须由用户确认**：没说文件就直接问"改哪个 PSD（给文件名或路径）"，**不要**遍历目录猜、别拿产物目录里的当输入。
- **源文件只读**（含素材库原件）：s4 对素材库**纯只读消费**，绝不重建/修改素材库索引；改动只写进需求副本 `<需求>/psd/制作/<槽位名>.psd`；没确认前不写任何文件。**组名可重复时用 `--组lyid` 定位。**
- **给用户改动/配色只做换算，不做设计**；配色换算结果要写进确认清单。
- 导出/回存用 `_pc_export.py`（自动拉起 PhotoCraft，不需要浏览器）；首次先跑 `python .opencode/lib/photocraft.py --check`。
- 定稿后 `python .opencode/lib/workspace.py place <需求>` 把切图**同名回写** s2 快照（`<需求>/FGUI/`）与 client 工程根。
- 若上面是空的：不要开始跑，只回一句"这是 FGUI 美术流程的 s4（s2 `/s2-fgui`、s3 `/s3-to-psd`），给我要改的 PSD 和改什么（或直接给需求名读清单）"，然后等输入。
