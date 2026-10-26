---
description: s3 PSD 还原 —— 把某个界面 XML 还原成分层 PSD（给美术改图的源稿）
agent: fgui-flow
---

用 `skill` 工具加载 **`fgui-to-psd`** 技能，然后**严格按它的步骤与纪律**处理下面这份输入。

本轮的输入（需求名 / 界面 XML 路径 / 复用件清单 / 要展示的按钮状态 / 字体口径 / 其它补充）：

```
$ARGUMENTS
```

规则：

- 先加载 `fgui-to-psd` 技能再动手；在**工作区根**（含 `.opencode` 的那层）执行，所有命令都在这里跑。
- 先 `python .opencode/lib/workspace.py where` 确认 `client_dir`（真实 FGUI 工程根，由 s0 写进 `.opencode/workspace.json`）。
- 优先读取 `<需求>/psd-spec.json`（s2 产出）：自动获取主界面 XML、复用件及九宫格事实，免去手工列出复用清单。
- 若有 `psd-spec.json`，严格根据 `.opencode/knowledge/psd-art-spec.md` 规范自动推导 `【group】`、`【common】`、`【列表】`、`【九宫】`、`复用_` 等标签。严禁提前添加 `【新】`。
- 若无 `psd-spec.json`：再按传统方式向我确认界面 XML 路径与复用件清单。
- **产物落 `.opencode/work/<game_key>/<需求>/`**：还原稿写 `psd/还原稿/`、中间产物写 `_tmp/`。实际路径见 `python .opencode/lib/workspace.py where --需求 <需求>`。
- 若上面是空的：不要开始跑，只回一句"这是 FGUI 美术流程的 s3（s2 是 `/s2-fgui`），给我界面 XML 和哪些图是复用件"，然后等输入。
- 用 `_pc_build.py` 在 PhotoCraft 里搭 PSD；桌面端没开会自动拉起，不需要浏览器。首次先跑 `python .opencode/lib/photocraft.py --check`。
- PSD 还原稿出来后，如果我还想改它的样式/文字/尺寸、导出透明 PNG 回工程，**提示我运行 `/s4-psd <需求>`**（s4）——只提示，不自动做。
