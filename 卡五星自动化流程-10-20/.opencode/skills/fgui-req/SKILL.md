---
name: fgui-req
description: FGUI 美术流程 s1 解析需求。当用户说"解析需求/s1/导入需求/这个需求怎么做"时使用。把 Excel 需求变成可施工的输入：扫描 inbox 目录 → 每行生成独立需求目录 → 机械检查 → 解析进清单 → 参考图适配 → 生成施工单。产物全部落在 .opencode/work/<game_key>/<需求>/，交接给 s2 fgui-flow 改工程。不改任何 FGUI 工程文件。
---

# s1 解析需求（`fgui-req`）

> **执行位置**：**工作区根**（含 `.opencode` 的那层）。
> 脚本住在 `.opencode/skills/fgui-req/scripts/`；共享库 `.opencode/lib/workspace.py`。
> **需求目录** = `.opencode/work/<game_key>/<需求>/`（`game_key` 从 `workspace.json` 读，如 `boxKaWuXing`）。
> 先看清落点：`python .opencode/lib/workspace.py where --需求 <需求>`。

## 干什么（一条链）

```
Excel（放 inbox）→ 每行一个目录 → 机械检查 → 解析进清单 → 参考图适配 → 施工单
```

需求目录结构（最终）：
```
.opencode/work/<game_key>/<需求>/
├─ 需求.md                     ← 正文（从 Excel 生成）
├─ 参考图/                      ← 原始截图（从 Excel 提取）
├─ 参考图_1334x750/             ← 适配后的截图
├─ 清单.json / 清单.md           ← 需求[] + 资源[]
└─ 施工单.md                    ← 施工依据（骨架 + 机械检查结果）
```

## 每步怎么做（命令可直接跑）

### 1) 从 Excel 生成需求目录

**用户把 Excel 放入 `.opencode/inbox/`，然后运行：**
```powershell
python .opencode/skills/fgui-req/scripts/excel_to_req.py
```

- 自动扫描 `.opencode/inbox/` 下所有 Excel 文件
- **每行生成独立目录**：`.opencode/work/<game_key>/<需求名>/`
- 自动识别列名（资源名称→名称，资源说明→描述，资源类型→类型，参考图/原型图→图片）
- 提取嵌入图片 → 保存到各目录的 `参考图/`
- 每个目录生成独立的 `需求.md`（单行 markdown 表格）
- 类型自动映射（UI→UI界面，icon→图标 等）

**也可以指定 Excel 路径：**
```powershell
python .opencode/skills/fgui-req/scripts/excel_to_req.py <excel路径>
```

### 2) 机械检查（错别字 / 清单不一致）
```powershell
python .opencode/skills/fgui-req/scripts/check_terms.py ".opencode/work/<game_key>/<需求>/需求.md"
# 退出码 4 = 有待人工确认项；把结论写进 施工单 第一节
```

### 3) 解析"一行一需求"进 清单.json
```powershell
python .opencode/skills/fgui-req/scripts/parse_requirement.py ".opencode/work/<game_key>/<需求>/需求.md"
```
- 需求文档里要有**表头含 `名称`+`描述`** 的表；缺 名称/描述 会**报行号**。
- 结果写进同目录 `清单.json` 的 `需求[]`。

### 4) 参考图适配画布
```powershell
python .opencode/skills/fgui-req/scripts/refimage_to_canvas.py --out ".opencode/work/<game_key>/<需求>"
```
- 同位比→直接 resize；异位比→按高缩放居中、四周填纯黑；输出 `参考图_1334x750/`，并回填清单。

### 5) 生成《施工单》骨架
```powershell
python .opencode/skills/fgui-req/scripts/build_guide.py ".opencode/work/<game_key>/<需求>/需求.md"
```
- 产出同目录 `施工单.md`（结构 + 机械检查结果 + 条目搬运）。**语义部分由模型/人补**（资源分类、冲突口径、决定清单）。
- 已存在默认不覆盖，要重生成加 `--force`。

### 6) 生成 清单.md（人读）
```powershell
python .opencode/lib/workspace.py manifest-md <需求>
```

## 多需求执行流程

- s1 一次跑完所有需求（Excel → N 个目录）
- s2/s3/s4 按批次执行（默认每批 4 个需求，人确认后继续下一批）

## 硬规矩

1. **只写 `.opencode/`**：不碰 client 工程、`assets/`、`settings/`。
2. **需求里写明的不再问**；只有"没说且会影响施工"的项才进施工单第五节，**一次问清**。
3. **不编造**：机械检查/解析是脚本的确定性结果；语义判断（读懂需求、分类资源、冲突口径）由模型做，拿不准进"决定清单"。
4. **美术需求为准**：与规则描述冲突的逐条列出（施工单第四节）。

## 出口条件 & 交接

- 出口：`清单.json` 的 `需求[]` 非空（每条有 名称+描述）；`施工单.md` 已生成。
- 交接：提示下一步 **`/s2-fgui`**（改 FGUI 工程）。
