# How-To Guides

Task-oriented recipes, one section per common task.

## Parse a New Requirement (s1)

Scenario: an art-requirement Excel arrives and needs to become buildable input.

1. Put the Excel into `卡五星自动化流程-10-20/.opencode/inbox/`
2. Run `/s1-req` (or `python .opencode/skills/fgui-req/scripts/excel_to_req.py`)
3. Check outputs in `.opencode/work/<game_key>/<需求>/`: 需求.md, 清单.json, 施工单.md, 参考图_1334x750/
4. Clear the "决定清单" (section 5) in 施工单.md before moving to s2

Expected: 清单.json has a non-empty 需求[] array, each item with 名称+描述.

## Land a Requirement into the FGUI Project (s2)

Scenario: the 施工单 is confirmed; time to edit the project.

1. Run `/s2-fgui`; the agent follows 扫 → 出方案 → 占位 → 落位 → 补文档 → 交付
2. After placement, a human MUST review the result in the FairyGUI editor (the single gate)
3. Once the look is finalized, the agent writes the verification report, change list, and psd-spec.json in one pass, then snapshots via `workspace.py snapshot`

Expected: component XMLs in the client project updated; snapshot under `<需求>/FGUI/`.

## Reuse an Asset from the PSD Library (s4)

Scenario: a manifest item is "待制作"; check the library for a reusable source first.

1. `python .opencode/lib/workspace.py find-asset <需求>` (optionally `--id R1 --top 3`)
2. Compare candidate previews (`<分类>/_预览/*.png`) against the requirement reference images; confirm manually
3. Hit → the library PSD is copied to `<需求>/psd/制作/` for text/color edits; miss → placeholder or AI image generation
4. Write back: `workspace.py manifest-set <需求> --id R1 --set 来源=素材库命中`

Expected: the manifest item's 来源/状态 updated; after `workspace.py place`, 状态=已替换.

## Add a New Asset to the PSD Library

Scenario: a new reusable source PSD should join the library.

1. Structure layer groups (top-level group = 制作单元, nested group = 底图组), drop it into a category dir (`按钮/`, `标签/`, `文字/`)
2. Run `python build_index.py --write --preview` inside the library directory
3. Confirm `index.json` updated and thumbnails generated under `_预览/`

Expected: the next find-asset can hit the new asset.
