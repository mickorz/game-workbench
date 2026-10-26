# Skill 流程详解：输入 / 中间产物 / 输出 + 全段细节

> 适用范围：FGUI 美术流程（s0~s4）。本文是对 `.opencode/skills/*/SKILL.md` 的二次整理与展开，
> 用于快速回答"这个流程吃什么、吐什么、中间有哪些产物"。
> 规矩的最高优先级 = `fgui文档/00-核心流程总纲.md`；详细手册 = `fgui文档/01-操作手册.md`。

## 一、整体流程速查

```
s0 环境配置 → s1 解析需求 → s2 改 FGUI 工程 → s3 出 PSD 还原稿 → s4 改样式切图回写
```

| 阶段 | 输入 | 主要中间产物 | 输出（交接下游/交付） |
|---|---|---|---|
| **s0 fgui-env** | `.opencode/xc_spce_info.json`（client_code_root / game_id / game_key） | —— | `.opencode/workspace.json`（`client_dir`） |
| **s1 fgui-req** | `.opencode/inbox/` 下的 Excel 需求表 | `需求.md`、`参考图/`、`参考图_1334x750/`、`施工单.md` | **`清单.json`**（`需求[]`+`资源[]`）+ `清单.md` + `施工单.md` |
| **s2 fgui-flow** | s1 的 `清单.json` + `施工单.md` | 事实底座（`facts.json`+`工程结构.md`+`美术资源清单.md`）、`方案.md`、`备份/`、`占位/`、`校验报告.md`、`修改清单.md` | **FGUI 工程文件**（`assets/`+`settings/`+`*.fairy`）+ 交付说明；并产出 **`psd-spec.json`**（s3 消费）+ `FGUI/` 快照（s3/s4 读） |
| **s3 fgui-to-psd** | s2 的 `psd-spec.json`（或手选界面 XML + 复用件清单） | `_tmp/<界面>_manifest.json`（布局清单）、空跑计划、逐层校验记录 | **`psd/还原稿/<界面名>_还原稿.psd`**（分层 PSD，文字层可编辑、复用件标 `复用_` 前缀） |
| **s4 psd-style** | s2 的 `清单.json` + 源 PSD（素材库命中 / s3 还原稿 / 用户给）+ 要改什么 | `psd/制作/<槽位名>.psd`（制作副本）、`切图/*.png`（透明 PNG） | 切图**同名覆盖**到 `FGUI/` 快照 + client 工程，清单 `状态=已替换` |

### 关键交接棒（三技能靠它串起来）

- **`清单.json`**：s1 生成 → s2/s4 回填（`psd`/`切图`/`来源`/`状态`字段）。
- **`psd-spec.json`**：s2 落位定稿后产出 → s3 自动消费（组件 XML 路径、复用件、九宫格客观事实）。
- **`FGUI/` 快照**：s2 `snapshot` 产出 → s3 读界面 XML、s4 `place` 回写切图。

### 几条核心约束

1. **s2 单一闸门**：落位完成 → 停下给人看效果；定稿前不写文档，定稿后一次性补齐。
2. **复用优先 7 级**：改属性 → 九宫格 → 拉伸/镜像 → 换相似图 → 通用件 → 文字顶图 → 才 AI 生图。
3. **源文件只读**：s3 还原稿、s4 素材库原件/输入 PSD 都不原地改，改动只写 `<需求>/psd/制作/` 副本。
4. **交付物**：FGUI 工程文件（`assets/`+`settings/`+`*.fairy`）+ 交付说明；`.opencode/` 和 `fgui文档/` 都是工作层不进交付。

---

## 二、s0 环境配置细节

### 干什么

```
s0 = ① 定位 client 工程（写 workspace.json）  ② 环境自检（提示）
```

本技能无独立脚本；定位用共享库 `.opencode/lib/workspace.py`。

### 命令

```powershell
python .opencode/lib/workspace.py env --check   # 只查：算出 client_dir 并打印 game_id/game_key
python .opencode/lib/workspace.py env           # 定位并写入 workspace.json（client_dir/game_key/game_id）
python .opencode/lib/workspace.py where         # 打印 工作区根 / out_root / 素材库根 / client_dir / game_key
```

### 定位规则（两层确认）

1. 读 `.opencode/xc_spce_info.json` 的 `project_info.client_code_root`（相对**工作区根**）。
2. **第一层**：`client_code_root` 下目录名 = `game_info.game_id` 的工程目录。
3. **第二层**：该目录 `assets/` 下存在**以 `game_info.game_key` 为前缀**的包（如 `boxKaWuXing_*`）。
4. 命中即写 `workspace.json`。

**找不到时**：脚本会列出候选目录并报错。人工确认后显式指定：

```powershell
python .opencode/lib/workspace.py env --client "相对或绝对路径"
```

### 环境自检（提示为主，不强退）

| 项 | 用途 | 检查 |
|---|---|---|
| Python 3.10+ | 所有脚本 | `python --version` |
| Pillow | `_fit_frames` / `_psd_preview` / `placeholder_png` / `_pc_export` | `python -c "import PIL"` |
| PhotoCraft 桌面端 | s3 搭 PSD / s4 导图 | `python .opencode/lib/photocraft.py --check`（会自动拉起） |

### 硬规矩 / 出口

- **只改 `.opencode/`（`workspace.json`）**；不碰 client 工程内容、`.xflow`、`assets/`。
- 定位失败**列候选、问人**，不猜；可用 `--client` 显式指定。
- 出口：`workspace.py where` 的 `client_dir` 存在于 `assets/` 有 `game_key` 前缀包。
- 交接：就绪后提示下一步 **`/s1-req`**（解析需求）。

---

## 三、s1 解析需求细节

### 干什么（一条链）

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

### 每步怎么做（命令可直接跑）

#### 1) 从 Excel 生成需求目录

```powershell
python .opencode/skills/fgui-req/scripts/excel_to_req.py
```

- 自动扫描 `.opencode/inbox/` 下所有 Excel 文件
- **每行生成独立目录**：`.opencode/work/<game_key>/<需求名>/`
- 自动识别列名（资源名称→名称，资源说明→描述，资源类型→类型，参考图/原型图→图片）
- 提取嵌入图片 → 保存到各目录的 `参考图/`
- 每个目录生成独立的 `需求.md`（单行 markdown 表格）
- 类型自动映射（UI→UI界面，icon→图标 等）

也可指定 Excel 路径：`excel_to_req.py <excel路径>`。

#### 2) 机械检查（错别字 / 清单不一致）

```powershell
python .opencode/skills/fgui-req/scripts/check_terms.py ".opencode/work/<game_key>/<需求>/需求.md"
# 退出码 4 = 有待人工确认项；把结论写进 施工单 第一节
```

#### 3) 解析"一行一需求"进 清单.json

```powershell
python .opencode/skills/fgui-req/scripts/parse_requirement.py ".opencode/work/<game_key>/<需求>/需求.md"
```

- 需求文档里要有**表头含 `名称`+`描述`** 的表；缺 名称/描述 会报行号。
- 结果写进同目录 `清单.json` 的 `需求[]`。

#### 4) 参考图适配画布

```powershell
python .opencode/skills/fgui-req/scripts/refimage_to_canvas.py --out ".opencode/work/<game_key>/<需求>"
```

- 同位比→直接 resize；异位比→按高缩放居中、四周填纯黑。
- 输出 `参考图_1334x750/`，并回填清单。

#### 5) 生成《施工单》骨架

```powershell
python .opencode/skills/fgui-req/scripts/build_guide.py ".opencode/work/<game_key>/<需求>/需求.md"
```

- 产出同目录 `施工单.md`（结构 + 机械检查结果 + 条目搬运）。**语义部分由模型/人补**（资源分类、冲突口径、决定清单）。
- 已存在默认不覆盖，要重生成加 `--force`。

#### 6) 生成 清单.md（人读）

```powershell
python .opencode/lib/workspace.py manifest-md <需求>
```

### 多需求执行流程

- s1 一次跑完所有需求（Excel → N 个目录）。
- s2/s3/s4 按批次执行（默认每批 4 个需求，人确认后继续下一批）。

### 硬规矩 / 出口

1. **只写 `.opencode/`**：不碰 client 工程、`assets/`、`settings/`。
2. **需求里写明的不再问**；只有"没说且会影响施工"的项才进施工单第五节，**一次问清**。
3. **不编造**：机械检查/解析是脚本的确定性结果；语义判断（读懂需求、分类资源、冲突口径）由模型做，拿不准进"决定清单"。
4. **美术需求为准**：与规则描述冲突的逐条列出（施工单第四节）。
5. 出口：`清单.json` 的 `需求[]` 非空（每条有 名称+描述）；`施工单.md` 已生成。
6. 交接：提示下一步 **`/s2-fgui`**（改 FGUI 工程）。

---

## 四、s2 资源种类表字段

### 资源种类表（动工前必填的硬动作）

| 列 | 写什么 | 例子 |
|---|---|---|
| **种类** | 图片 / 九宫格图 / 非等比拉伸 / 位图字体＋字形 / 组件 / 复用现成 | 「漂」＝位图字体（不是图片，也不是普通文字） |
| **最终文件名＝槽位名** | 替换时用的名字（含目录） | `fnt/piao.fnt` ＋ `fnt/piao/p.png` |
| **规格** | 尺寸、九宫格边距、字形高度、字符表 | 字形高 69（与 `win.fnt` 对齐）、字符 `0-9`＋`p` |
| **谁产出** | 人（美术/字体）／AI 生图／复用现成 | 位图字体＝人出；标签图＝AI 生图 |

**为什么必须先定**：种类定错＝返工。种类＋规格定死后，① 真东西到手同名同规格替换、不用改节点；② 这张表同时就是生图/出字体的方向单。

### 清单回填（manifest-add 命令的枚举）

```
--种类      图片 | 九宫格图 | 非等比拉伸 | 位图字体 | 组件 | 复用现成
--尺寸      WxH
--九宫格    上,右,下,左          （仅九宫格图）
--字形高    N                    （仅位图字体）
--字符表    0-9,p               （仅位图字体）
--透明底    true | false
--用途      "XX节点"
--来源      AI生图 | 素材库命中 | 占位 | 复用
--状态      待制作 | 占位中 | 已替换  （s3/s4 回填）
```

s3/s4 还会回填 `psd` / `切图` / `来源` / `状态` 字段。

### 占位落两处（同规格同名）

```
<需求>/占位/<槽位名>           （留存档）
client_dir/assets/<包>/atlas/  （同名覆盖，工程要能跑）
```

```powershell
# 普通图占位
python .opencode/skills/fgui-flow/scripts/placeholder_png.py --size 96,33 --out "<需求>/占位/atlas/img_x.png" --label "TAG_X 96x33"

# 九宫格占位（把拉伸区画出来）
python .opencode/skills/fgui-flow/scripts/placeholder_png.py --size 300,120 --out "<需求>/占位/atlas/img_panel.png" --scale9 20,20,20,20

# 位图字体占位：字形放 <包>/fnt/<字体名>/<字符>.png，再写 <包>/fnt/<字体名>.fnt（照 win.fnt 的格式）
```

---

## 五、s2 事实底座与知识库

### 事实底座（project 级）

只在工程被改过之后重扫；平时定位读 `facts.json`，不重扫。事实底座落在 `.opencode/work/` 顶层（**project 级**，非需求级）。

```powershell
python .opencode/skills/fgui-flow/scripts/scan_fgui.py            # 在工作区根执行；自动定位 client_dir，输出到 .opencode/work/
python .opencode/skills/fgui-flow/scripts/lookup.py --check       # 看底座还新鲜吗（退出码 1 = 缺失/过期，重扫）
python .opencode/skills/fgui-flow/scripts/lookup.py <关键词>       # 定位（退出码 3 = 没命中）
python .opencode/skills/fgui-flow/scripts/lookup.py --comp <组件名> --nodes  # 某组件全部节点
```

产物：

- `.opencode/work/facts.json` + `工程结构.md` + `美术资源清单.md`（扫描产物，别手改）。
- 中文说明来源 = `.opencode/work/美术清单.备注.txt`（手填 `<关键词> = <说明>`）。

### 知识库（动态、唯一一份 = `.opencode/knowledge/`）

**会持续更新**（新手法、新坑、新用例随时补）。所以：

- **不许凭记忆引用知识库、更不许把它的内容抄进技能或方案**；要用时**现读**：

```powershell
python .opencode/skills/fgui-flow/scripts/knowledge.py --list            # 索引（文件 + 标题树）★主题词从这来
python .opencode/skills/fgui-flow/scripts/knowledge.py --topic 复用 --topic 九宫格   # 例子，不是全集
python .opencode/skills/fgui-flow/scripts/knowledge.py --topic 对齐 --topic 留白     # 例子，不是全集
```

涉及"这个效果该用哪种手法""要不要出新图"之前，**先跑一次 `--topic`**。

### 知识库使用纪律

- **别只查"换图"那条线**：知识库还管**排版**（对齐 / 成组 / 留白 / 间距 / 居中 / 锚点）。
  **改坐标 / 排位置 / 定间距之前，也要先跑一次排版类 `--topic`**，别凭手感摆。
- 上面的 `--topic` 只是例子：**主题词以当次 `--list` 索引里的标题词为准**（索引会自动列出可检索的小节）——
  知识库随时会多出新文件，照例子抄就会漏。
- `knowledge.py` 只读 `.opencode/knowledge/`；找不到会退回本包自带快照，不会报错。

---

## 六、s3 PhotoCraft 校验流程

### 执行链（强制顺序）

```
[a] _fgui_layout.py --spec psd-spec.json --out _tmp/manifest.json
        |  离线解析，退出码 0=干净 2=有告警
        v  有告警先解决再往下
[b] _pc_build.py manifest.json --dry-run
        |  空跑，不连 PhotoCraft，看图层顺序/坐标/组结构
        v  计划没问题
[c] _pc_build.py manifest.json --out psd/还原稿/<界面>_还原稿.psd
        |  真搭，自动拉起 PhotoCraft 桌面端
        |  跑完自动：回读图层树 → 逐层比对
        v
[d] _psd_struct.py <psd>
        |  字节级自检：合法 PSD、图层没写坏
        v
   汇报：产物路径/大小/画布尺寸/图层数 + 三段校验结论 + 复用件清单 + 口径说明
```

### `[c]` 跑完自动三段校验

| 段 | 查什么 | 出错会怎样 |
|---|---|---|
| ① 置入/建层 | `app.open` → 复制 → 粘贴 → 变换 有没有报错 | 偶发 `edit.paste` 没返回 layer 会记"置入失败"，重跑一次通常好 |
| ② 图层名/坐标/隐藏态 | 每个 PSD 图层对照 manifest 是否一致 | 校验按 (父级组, 图层名) 配——叶子重名是常态，按名字取第一个会假报"偏 1000px" |
| ③ 黑白调整层剪贴 | 黑白层是否紧挨目标组上面 + 同级 + 已剪贴 | 落进组里 → 剪贴对象变成组内最上层 → 按钮不会变灰，但图层树看着"有个黑白层"（最容易悄悄错） |

### 几个关键坑（校验时容易踩）

- **坑 3 容差**：图片缩放后外框差 1px 属正常，校验容差图片 1.5px、文字 3px。
- **坑 4**：PhotoCraft 不允许删到 0 个图层，`file.new` 自带一层垫层，留在最底（不参与计划/校验，导出时隐藏）。
- **坑 9 叶子重名**：12 个按钮展开后会有 13 个 `icon`、13 个 `title`——新加图层用命令返回的 layer id，不要按名字找；只有图层组按名字找。
- **坑 5 黑白层位置**：`layer.newAdjustmentLayer.blackWhite` 后必须 `layer.moveTo {target: 组, position: "above"}` 再 `layer.createClippingMask`——落进组里就失效。

### 汇报口径

- 产物路径 / 大小 / 画布尺寸 / 图层数（含组数）
- 三段校验结论
- 复用件清单（哪些图层带 `复用_` 前缀）
- 口径说明（字体、relation 增量修正过哪几处——`_fgui_layout.py` 的 `deviations` 会列）

---

## 七、s4 换色规则

### 总原则

保持**明度/饱和度的对应关系，只换色相**，外加三条修正：

| 修正 | 原因 / 做法 |
|---|---|
| 1. 换成冷色（蓝、紫）明度要上调 | 同明度下冷色看着比暖色暗，HSL 的 L 约 **+0.04~0.08** |
| 2. 渐变两端不同色相 | 亮端＝目标色相；暗端相对往暖色偏。色环"更暖"＝ 往红走（黄→橙→红；蓝→紫→品红→红）。原稿黄→金：暗端 H53° → H42°（约 10°） |
| 3. 描边保持原明度/饱和度 | 描边是深色，深色不用跟着上调，只换色相；色相取渐变暗端再往暖走一点 |

### 实测对照表 A：标签（黄 → 蓝）

| 部位 | 正面（原稿） | 负面（蓝） |
|---|---|---|
| 渐变亮端 | `#FFF5A4` H53 S1.00 L0.82 | `#B8EFFF` H193 S1.00 L0.86 |
| 渐变暗端 | `#FFC73F` H42 S1.00 L0.62 | `#56AAFF` H210 S1.00 L0.67 |
| 描边       | `#B51B02` H8 S0.98 L0.36   | `#023EB6` H220 S0.98 L0.36 |

### 实测对照表 B：按钮（黄 → 天蓝，`选字.psd`）

| 部位 | 黄（原稿） | 天蓝（换算后） |
|---|---|---|
| 形状填充 SoCo / 亮部像素 | `#FFF289` H54 S1.00 L0.76 | `#A2ECFF` H191 S1.00 L0.81 |
| 内发光 IrGl              | `#FFDC47` H46 | `#60CBFF` H204 |
| 斜面高光 ebbl.hglC       | `#FFE64C` H47 | `#66D8FF` H201 |
| 斜面暗部 ebbl.sdwC       | `#FB8F02` H34 S0.98 L0.49 | `#024DFB` H222（深色 L 不动） |
| 投影 dropShadow          | `#BA522C` H14 S0.62 L0.45 | `#2C57BA` H222 L0.45 |
| 近黑投影                  | `#0D262B` H189 | **不变**（色相不在黄橙区间） |

### 像素级换算公式（`_psd_recolor.py` 实现）

只对 **S ≥ 0.10 且 H ∈ [15, 80]** 的像素做换算（即黄橙区间的像素）：

```
H_new = 210 + (H - 42) × (193 - 210) / (53 - 42)
```

- 钳到 **H185~222** 区间
- S 不变
- L ≥ 0.55 的亮部 **+0.05**；深色不加（保持深色感）

按钮类素材的像素往往全是 S=1.0 的黄橙，映射很干净；半透明边缘像素按同一规则走。

### 重要陷阱（必须知道）

- **按钮类素材的黄色主要来自栅格位图（光泽/渐变层），图层样式色只占很小一部分** → 必须用 `_psd_recolor.py` 做像素级换色；只改 SoCo/效果色在画面上**根本看不出来**。
- **叠加效果互相遮盖**：渐变叠加开着时只改颜色叠加的颜色，画面上看不出变化——必须先 `--inspect` 看 `[开]`/`[未用]`，确认清单里问清"关掉渐变叠加，还是连渐变的颜色一起改"。
- **HSL 别只看 H**：色环首尾相接，"提高/降低 H"判断不了冷暖，只能按"相对往哪个方向偏"说。

---

## 八、s4 取件与回写链路

### 取件——读清单 + 查素材库（有清单时）

1. **读清单**：`<需求目录>/清单.json`（先 `workspace.py where --需求 <需求>` 确认实际路径）。
2. **查素材库**：逐条"待制作"资源匹配可复用稿（`种类` 硬条件 → `结构` → `尺寸` → `外观` 打分，定位到具体的**制作单元及其底图组**）：

```powershell
python .opencode/lib/workspace.py find-asset <需求> [--id R1] [--top 3]
```

   - 候选输出会列出每个制作单元的 `名 (lyid)`、包含的 `文本`、嵌套的 `底图组 (lyid)`，以及分类独享的**预览图路径**（`分类/_预览/*.png`）。
   - **务必核对预览图**：模型或人工应优先查看对应的分类预览图，与参考图/需求进行外观比对确认。

3. **逐条决策（人确认）**：
   - **命中** → 把素材库那份 PSD **复制**到 `<需求目录>/psd/制作/<槽位名>.psd`（**原件不动**）。最外层制作单元负责整体复用与导出，嵌套底图组负责改尺寸（`_psd_reshape`）或换色（`_psd_recolor`）；进确认、再执行。
   - **未命中** → 保留占位（清单 `来源=占位`、`状态=占位中`），报"待 AI 生图"。

4. **回填清单**：

```powershell
python .opencode/lib/workspace.py manifest-set <需求> --id R1 --set 来源=素材库命中 --set 素材库命中=S1 --set 重组手法=换色
```

> 没有清单（用户直接给了个 PSD）→ 跳过本步，直接进确认。

### 源 PSD 三种来源——**强制确认，不许自己搜**

| # | 来源 | 处理 |
|---|---|---|
| ① | **素材库命中** | `find-asset` 候选，人确认，复制到 `制作/` 再改 |
| ② | s3 的**还原稿** | `<需求目录>/psd/还原稿/` |
| ③ | 用户直接给的 PSD | 由用户确认 |

- 用户没给、清单也没命中时：直接问"用哪份 PSD？（给我文件名或路径）"，**不遍历目录、不推断**。
- 用户给了名字 → 只做一次存在性检查 `Test-Path`。不存在就把原话回给用户要准确路径，**不要去别处搜同名文件**。
- **产物目录（`<需求目录>`）里的稿一律不当输入**（那是以前的产物）；只有用户明确说"在某个副本上继续改"才用它。
- **源文件只读**：素材库原件/用户给的 PSD/还原稿都**不原地改**；改动只写进副本 `<需求目录>/psd/制作/<槽位名>.psd`。

### 执行——按顺序调脚本

```powershell
# 先确认 <需求目录> 实际路径（默认 .opencode/work/<game_key>/<需求>）
python .opencode/lib/workspace.py where --需求 <需求>

# a) 源文件（必须已由用户确认；只读，改的是副本）
$psd  = '<源 PSD：素材库命中的 / 还原稿 / 用户给的>'
$work = "<需求目录>/psd/制作/<槽位名>.psd"
New-Item -ItemType Directory -Force "<需求目录>/psd/制作", "<需求目录>/切图", "<需求目录>/_tmp" | Out-Null
Copy-Item $psd $work

# b) 一个图层变多个标签：复制 + 改名（名字就是输出文件名，导出时自动等于 PNG 名）
python .opencode/skills/psd-style/scripts/_psd_clone.py $work --from 自摸 --names out_a,out_b,out_c

# c) 改文字（字数可长可短）
python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-text $work out_b 捉炮胡 --out $work

# d) 改颜色 / 渐变 / 数值参数 / 开关效果
python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-color    $work out_b 颜色叠加 FB1D1D --out $work
python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-gradient $work out_b B8EFFF 56AAFF  --out $work
python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-num      $work out_b 描边 大小 6      --out $work
python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-effect   $work out_b 渐变叠加 off      --out $work

# e) 套整套 ASL 样式（会关掉样式库里没有的效果，只保留样式定义的）
python .opencode/skills/psd-style/scripts/_apply_asl.py --psd $work --asl .opencode/skills/psd-style/scripts/test.asl --style 0 --layer out_b --out $work

# e2) 整组流程（按钮/label 这类"一个组 = 一个图"）：**顺序不能颠倒**
#     先按确认好的 bbox 重排形状（四角半径保持、只拉伸中间，含组内蒙版栅格）
#     再整组复制（两个按钮因此天然同尺寸），最后只给新组换色
#     ★ 组名可重复（素材库 PSD 常见）时用 --组lyid 精确定位；按组名也行（与 --组lyid 二选一）
python .opencode/skills/psd-style/scripts/_psd_reshape.py    $work --组lyid 23 --bbox 2,2,174,84 --out $work
python .opencode/skills/psd-style/scripts/_psd_group_clone.py $work --组lyid 23 --name img_zi_card_blue --out $work
python .opencode/skills/psd-style/scripts/_psd_recolor.py    $work --组lyid 23 --target blue --out $work

# e3) 导出切图前：把目标单元自动加上 out_ 前缀（素材库原件本就不带，运行时补）
python .opencode/skills/psd-style/scripts/_rename_layer.py $work - out_<槽位名> --lyid 23 --out $work

# f) 改完先自检：解析→重写必须与原文件逐字节一致，不一致就是解析口径错了
python .opencode/skills/psd-style/scripts/_psd_struct.py $work

# g) 批量导出 + 回存（自动拉起 PhotoCraft；不需要浏览器）
#    --texts   ：导出前改真文字层（导出立即按新字重排，不需要额外烘焙）
#    --canvas  ：导出前放大画布，防止长文字超出原画布被裁
#    目标是图层组也行（脚本自动识别，不用再加 --groups）
#    默认把文档存回 $work；要换路径用 --save-psd，只导 PNG 用 --no-save
python .opencode/skills/psd-style/scripts/_pc_export.py $work "<需求目录>/切图" --canvas 400x160 --texts "<需求目录>/_tmp/texts.json"

# h) 统一成同一画布尺寸 + 内容居中（默认取"最大的那张内容框"）
python .opencode/skills/psd-style/scripts/_fit_frames.py "<需求目录>/切图" --files img_a.png,img_b.png,img_c.png

# h2) 多组输出时，按确认环节跟用户确认好的尺寸逐组统一（别默认"各自取最大内容框"）
python .opencode/skills/psd-style/scripts/_fit_frames.py "<需求目录>/切图/文字"
python .opencode/skills/psd-style/scripts/_fit_frames.py "<需求目录>/切图/数字" --size 50x81

# i) 确认每张图真的不同：内容框/主色不一样（全一样 = 文字没改成功）

# j) 定稿后回写：切图同名覆盖 s2 快照与 client 工程根，清单状态=已替换
python .opencode/lib/workspace.py place <需求> [--id R1]
```

`--texts` 的 JSON 长这样（键 = 图层名，值 = 新文字；用 UTF-8 写文件，别在命令行里塞中文）：

```json
{ "out_a": "自摸", "out_b": "捉炮胡" }
```

### 回存 PSD 的口径

- `_pc_export.py` **默认就会回存**（存回输入的 `$work`），不用再单独加参数。
- `--texts` 改的是 PhotoCraft 里的**真文字层**，导出和回存都是新字；不再有"只改 TySh、像素还是旧字"的问题。
- 回存是 PhotoCraft 自己写的 PSD：`lfx2` 图层样式、`TySh`、组、图层名和顺序都保留，`_psd_struct.py` 对它同样报"逐字节一致 ✓"。
- 覆盖前会自动备份成 `$work.pre-pc.bak`（只备份第一次）。
- **副本里的 `out_` 前缀保留**（那是导出协议的选层标记）；导出 PNG 的文件名自动去掉前缀。

### 汇报口径

- 输入 PSD（哪个，来源：素材库命中 / 还原稿 / 用户给）+ **制作副本路径**（`<需求目录>/psd/制作/`）。
- 每个 PNG 的**路径 / 尺寸 / 透明占比 / 主色**（用校验命令）。
- **副本内容校验**：导出 PNG 的内容框/主色是否各自不同（全一样 = 文字没改成功）。
- **多组同时输出时**：按确认环节定好的尺寸逐组核对；顺带报各组的**内容中线 y**（便于用户确认两组摆放是否对齐）。
- **"两个要一样大"这类要求**：别只说尺寸相同——直接比两张 PNG 的 **alpha 通道是否逐像素相同**（`ImageChops.difference` 最大差值 0 才算真的一样大），并报各自的**实体框（alpha>250）**。
- **改过按钮/形状尺寸时**：报重排后的 **vmsk 形状 bbox** 与导出 PNG 的实测内容框是否吻合；PhotoCraft 存 PSD 时形状层是 **vmsk + vogk + SoCo 的矢量层**（图层仍可二次编辑），导出 PNG 按实时渲染，属正常。
- 哪一步失败就说清卡在哪，不编造结果。
- **切图落点与回写**：切图在 `<需求目录>/切图/`；定稿后 `workspace.py place <需求>` 已把它**同名覆盖**到快照（`<需求目录>/FGUI/`）与工程根，清单 `状态=已替换`。

校验 PNG（必须做，至少确认 8 张尺寸一致 + 四角透明 + 主色对不对）：

```powershell
python -c "from PIL import Image; from collections import Counter; import glob;
[ (lambda im: (lambda r: print(p, r.size, '内容框=', r.getchannel('A').getbbox(), '四角alpha=', [r.getpixel(c)[3] for c in [(0,0),(r.size[0]-1,0),(0,r.size[1]-1),(r.size[0]-1,r.size[1]-1)]], '主要颜色=', ['#%02X%02X%02X x%d'%(c[0],c[1],c[2],n) for c,n in Counter([q[:3] for q in r.getdata() if q[3]>200]).most_common(3)]))(im.convert('RGBA')))(Image.open(p)) for p in sorted(glob.glob('<需求目录>/切图/*.png'))]"
```

校验注意：

- 校验前一律 `convert('RGBA')`（PhotoCraft 导出的 PNG 通常已是 RGBA，但统一转换不亏）。
- **同一批图的尺寸必须一致**：`_fit_frames.py` 会打印"尺寸种类：1 一致 ✓"，不是 1 就说明没统一。
- **内容框宽度要能区分不同字数**：如果 8 张内容框完全一样大，几乎肯定是 `--texts` 没生效。

---

## 九、s2 复用优先 7 级决策（补充）

成本从低到高，**走到底才生图**：

```
1. 改现有节点的尺寸/位置/颜色/透明度
2. 九宫格拉伸（先看 package.xml 有没有 scale9grid）
3. 非等比拉伸 fill="scaleFree" / 缩放 / 镜像 / 旋转 / 变色 gearColor
4. 换一张已有的相似图
5. 复用现成的通用件（组件）
6. 用文字节点顶掉图
7. 以上都不行才 AI 生图
```

### 第 5 级的判断口径：拿需求要的"结构"去对通用件的"结构"

不是看"是不是按钮"这个词，而是看需求要的东西在通用件里有没有。

- **对得上 → 复用**：需求要的只是通用件已有的东西（底图 + 居中文字，换个字/换张图/改个色都算）。
  典型：确认 / 取消 / 关闭 / 继续 这类普通方按钮 → 直接在**实例**上覆盖 `icon` / `title` / `titleColor` / `titleFontSize`，**不改通用件本身**。
- **对不上 → 照需求单独建组件**，别把需求硬塞进通用件。
  典型：**多状态卡牌**（按状态换图 / 换字色 / 显隐角标）。硬套通用件＝**把状态结构丢掉**。
- **拿不准就把两边结构摆出来问一句**，别默认复用。

### 第 5 级容易忽略的坑

- **跨包引用要写 `pkg="<8位包 id>"`，且目标组件要勾「导出」** —— 漏任一项会**静默失效**（不报错、什么都不显示，很难查）。
- **复用白拿的东西**：底图随 `size` 自动铺满、文字自动居中、按下反馈、控制器页值。
- 改共用图/通用件前先查引用（`lookup.py Button9Scale`），共用资源一改会影响**所有**引用它的界面。
- 报新图时必须说清"试过哪几种手段、为什么不行"。

---

## 十、FGUI XML → PSD 语义对照（补充）

| FGUI | PSD |
|---|---|
| `<component size="W,H">`（根） | 画布尺寸 |
| `displayList` 里的顺序 | **从下到上**（第一个在最底）→ PSD 里新层加在最上面，按序加即得正确叠放 |
| `<group>` | 图层组 |
| `<component src=...>` 实例 | 图层组（递归展开成子层） |
| `<text>` | **真·可编辑文字层**（内容/字号/颜色/加粗） |
| `<image>` / `<loader url=...>` | 置入图片层（`ui://` 解引用到 `assets/` 真实文件） |
| `<graph type="rect" fillColor="#AARRGGBB">` | 铺满的纯色图层 + **图层不透明度 = AA/255** |
| `visible="false"` / `gearDisplay` 未命中 | 图层**保留但设为隐藏**（美术能自己打开看） |
| `gearLook` 的 `grayed` | 给该组盖一个**黑白调整图层**（剪贴到组） |
| `ui://` 前 8 位 = 包 id、后 5 位 = 资源 id | 查该包 `package.xml` 的 `<resources>` 得到真实文件名与路径 |
| 复用件（用户指定） | 图层名前缀 `复用_` |

### 已知不支持（`_fgui_layout.py` 会明确告警，不静默算错）

`gearXY`/`gearSize`/`gearText`/`gearFontSize`/`gearAni` 等 gear；
`left-right`/`right-right`/`bottom-bottom` 等 relation 组合；
`list`/`movieclip`/`loader3D` 等节点类型。
遇到告警**先回来确认怎么处理**，别硬跑。

---

## 十一、s4 矢量形状 vmsk 结构口径（补充）

一个"圆角矩形按钮"在文件里是**三层数据**；改形状要同时动前两层，第三层是像素：

### 1. `vmsk`（矢量蒙版 = 形状路径）

```
vmsk = u32 版本(3) + u32 flags + Path

Path     = 一串记录，每条 = u16 selector + 24 字节载荷
selector ：0 封闭子路径长度 / 1 封闭结点(相连) / 2 封闭结点(不相连)
           3 开放子路径长度 / 4 开放结点(相连) / 5 开放结点(不相连)
           6 路径填充规则 / 7 剪贴板 / 8 初始填充规则
子路径（0/3）载荷 = u16 结点数 + i16 operation + u16 + u32 + u32 + 10 字节
结点（1/2/4/5）载荷 = 3 个点 × (i32 y, i32 x)，8.24 定点
                      3 个点 = 前控点 / 锚点 / 后控点（直线段的后控点 = 锚点）
```

**坐标按画布尺寸归一化**：文档坐标 = 存的值 / `0x01000000` × (画布宽, 画布高)。

实测：`选字.psd` 的路径 ×176 / ×86 后与 vogk 的 bbox 完全吻合
（15.7812, 15.6562）-（158.5000, 65.2188），圆角半径 5px。

### 2. `vogk`（实时形状元数据）

描述符，含 `keyOriginRRectRadii`（四角半径，`#Pxl` 双精度）、
`keyOriginShapeBBox`（Top/Left/Btom/Rght，**文档坐标** double）、`keyOriginResolution`、`keyOriginIndex`。

三个坑：

- 找 bbox 的 `Left` **不能全 buffer 搜** `Left + UntF#Pxl` —— 会撞上半径里的 `topLeft`/`bottomLeft`；
  要先锚定 `keyOriginShapeBBox` 再在它之后找（`_psd_reshape.py::vogk_slots` 已这么写）。
- "半径保持" = 只改 bbox、**不动 radii**；要按比例放大半径才改 `keyOriginRRectRadii` 的那 4 个 double。
- **两处都改到一致**，才不会因为"Photopea/PS 到底读哪个"而翻车（实测 Photopea 按 vmsk + SoCo 渲染）。

### 3. 组内栅格 + 剪切

基底是组内 `clip=0` 那层，上面几层是 `clip=1` 的剪切蒙版层（光泽/高光），
像素会溢出基底。改形状时它们要按**同一分段线性映射**九宫格重采样（角区刚性平移、中间段拉伸、
bbox 之外按最近段斜率刚性外推），图层 rect 与通道长度字段一起重算。

### 改尺寸的正解顺序（别颠倒）

```
_psd_reshape.py     矢量形状九宫格重排（四角半径不动，只拉伸中间）+ 组内栅格同映射重采样
       ↓
_psd_group_clone.py 整组复制（两个按钮天然同尺寸）
       ↓
_psd_recolor.py     只给新组换色
```

### 两条通用口径

- `lyid`（图层 ID）不能重复：克隆图层/组时新副本要重新发号（`_psd_clone.py` / `_psd_group_clone.py` 都做了）。
- 通道数据 = `u16 压缩标志（0 原始 / 1 RLE）+ 数据`；RLE 是 PackBits（`n>=0` 复制 n+1 字节、`n<0` 重复 `1-n` 次）
  + 高×u16 行字节数表。改像素必须**同步改图层记录里的 `(cid, clen)` 通道表**——
  `_psd_raster.py` 负责重建 head，别只换数据不改长度。

---

## 十二、引用说明

本文整理自以下 SKILL.md（项目工作层，不进交付）：

- s0 环境配置：`.opencode/skills/fgui-env/SKILL.md`
- s1 解析需求：`.opencode/skills/fgui-req/SKILL.md`
- s2 改 FGUI 工程：`.opencode/skills/fgui-flow/SKILL.md`
- s3 出 PSD 还原稿：`.opencode/skills/fgui-to-psd/SKILL.md`
- s4 改样式切图回写：`.opencode/skills/psd-style/SKILL.md`

配套的人类文档（不进交付）：

- 规矩最高优先级：`fgui文档/00-核心流程总纲.md`
- 详细操作手册：`fgui文档/01-操作手册.md`
- 本仓已有的章节式文档：`docs/01-总览与架构.md` ~ `docs/08-常见问题.md`

规则源（每次会话自动加载）：

- 工作区根 `AGENTS.md`
