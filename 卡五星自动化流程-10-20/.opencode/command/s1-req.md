---
description: s1 解析需求 —— Excel 扫描 → 解析进清单 → 施工单骨架
agent: fgui-flow
---

用 `skill` 工具加载 **`fgui-req`** 技能，然后**严格按它的步骤与纪律**执行。

本轮的输入（补充说明）：

```
$ARGUMENTS
```

规则：

- 在**工作区根**（含 `.opencode` 的那层）执行；需求目录 = `.opencode/work/<game_key>/<需求>/`。
- 先确认落点：`python .opencode/lib/workspace.py where --需求 <需求>`。
- 顺序：扫描 inbox（`excel_to_req.py`）→ `check_terms.py` 机械检查 → `parse_requirement.py` 解析进清单 → `refimage_to_canvas.py` 适配 → `build_guide.py` 出施工单 → `manifest-md` 出清单。
- **只写 `.opencode/`**；不碰 client 工程、`assets/`、`settings/`。
- 需求里写明的不再问；只有"没说且会影响施工"的项才进施工单决定清单，**一次问清**。
- 完成后提示下一步可运行 **`/s2-fgui`**。
