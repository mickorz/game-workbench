# 操作指南

按任务组织的常用操作，每节一个任务。

## 解析一份新需求（s1）

场景：美术给了新的 Excel 需求，要变成可施工的输入。

1. Excel 放入 `卡五星自动化流程-10-20/.opencode/inbox/`
2. 运行 `/s1-req`（或 `python .opencode/skills/fgui-req/scripts/excel_to_req.py`）
3. 检查产物：`.opencode/work/<game_key>/<需求>/` 下的需求.md、清单.json、施工单.md、参考图_1334x750/
4. 施工单第五节"决定清单"清零后再进入 s2

预期结果：清单.json 的 需求[] 非空，每条有 名称+描述。

## 改 FGUI 工程落一个需求（s2）

场景：施工单已确认，要把需求落成工程改动。

1. 运行 `/s2-fgui`，Agent 按"扫 → 出方案 → 占位 → 落位 → 补文档 → 交付"推进
2. 落位完成后**必须**在 FairyGUI 编辑器里人看效果（唯一闸门）
3. 效果定稿后 Agent 一次性补齐校验报告、修改清单、psd-spec.json，然后 `workspace.py snapshot` 建快照

预期结果：client 工程的组件 XML 已更新，快照在 `<需求>/FGUI/`。

## 从 PSD 素材库复用一份资源（s4）

场景：清单里有"待制作"资源，想先查素材库有没有可复用稿。

1. `python .opencode/lib/workspace.py find-asset <需求>`（可 `--id R1 --top 3`）
2. 对照候选的预览图（`<分类>/_预览/*.png`）与需求参考图，人工确认命中
3. 命中 → 素材库 PSD 复制到 `<需求>/psd/制作/` 后改字改色；未命中 → 占位或报 AI 生图
4. 回填清单：`workspace.py manifest-set <需求> --id R1 --set 来源=素材库命中`

预期结果：清单该条 来源/状态 更新，切图经 `workspace.py place` 回填工程后 状态=已替换。

## 往 PSD 素材库添加新素材

场景：有新的通用美术源 PSD 要纳入复用库。

1. 整理图层组结构（最外层组=制作单元，嵌套子组=底图组），放入对应分类目录（`按钮/`、`标签/`、`文字/`）
2. 在素材库目录运行 `python build_index.py --write --preview`
3. 确认 `index.json` 更新且 `_预览/` 生成了缩略图

预期结果：下次 find-asset 能命中新素材。
