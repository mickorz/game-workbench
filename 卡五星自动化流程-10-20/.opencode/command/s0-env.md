---
description: s0 环境配置 —— 定位 client 工程（写 workspace.json）
agent: fgui-flow
---

用 `skill` 工具加载 **`fgui-env`** 技能，然后**严格按它的步骤与纪律**执行。

本轮的输入（可选：`--client <工程目录>` / 补充说明）：

```
$ARGUMENTS
```

规则：

- 在**工作区根**（含 `.opencode` 的那层）执行，所有命令都在这里跑。
- 定位 client 工程（`workspace.py env`）。
- **只改 `.opencode/`** 下的 `workspace.json`；不碰 client 工程、`.xflow`、`assets/`。
- 定位不到时**列出候选并问我**，不要猜；我给你路径就用 `workspace.py env --client <路径>`。
- 完成后提示下一步可运行 **`/s1-req`**。
