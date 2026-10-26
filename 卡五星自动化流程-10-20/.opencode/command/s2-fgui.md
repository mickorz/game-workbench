---
description: s2 FGUI 落位 —— 消费 s1 的清单/施工单，改 client 工程 + 占位 + 快照
agent: fgui-flow
---

用 `skill` 工具加载 **`fgui-flow`** 技能，然后**严格按它的步骤与纪律**处理下面这份需求。

本轮的输入（需求名 / 需求原文或美术需求截图路径 / 补充说明）：

```
$ARGUMENTS
```

规则：

- 先加载 `fgui-flow` 技能再动手；在**工作区根**（含 `.opencode` 的那层）执行，所有命令都在这里跑。
- 先 `python .opencode/lib/workspace.py where` 确认 `client_dir`（真实 FGUI 工程根，由 s0 写进 `.opencode/workspace.json`）；**要改的是 client 工程，不是工作区根**。
- 需求产物一律落 **`.opencode/work/<game_key>/<需求>/`**（清单/施工单/占位/快照都在里面）；用 `python .opencode/lib/workspace.py where --需求 <需求>` 核对实际路径。
- **先消费 s1 的产物**：`.opencode/work/<game_key>/<需求>/清单.json`（机器真源）+ `施工单.md`（人读）。没有就先跑 `/s1-req`，**不要**自己手抄需求截图。
- 若上面是空的：**不要开始改工程**，只用一句话复述你理解的 5 环节与硬规矩，然后问我"需求是什么 / 需求名是什么"。
- 需求里写明的不再问；只有"需求没说且会影响施工"的项才进决定清单，一次问清。
- 只有一道闸门（落位完成时），此时必须停下来给我看，确认效果后才补文档并生成 `<需求>/psd-spec.json`，不要一路自己拍。
- 交付 FGUI 工程前跑 `python .opencode/lib/workspace.py snapshot <需求>` 建工程快照（落 `<需求>/FGUI/`）；`.opencode/`、`fgui文档/` 都**不进交付**。
- 交付后如果我还需要给美术出 PSD 还原稿，**提示我运行 `/s3-to-psd <需求>`**（s3 自动消费 `psd-spec.json`）——只提示，不自动做。
