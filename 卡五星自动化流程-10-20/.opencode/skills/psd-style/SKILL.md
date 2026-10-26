---
name: psd-style
description: 改 PSD 图层的图层样式与文字——颜色叠加/渐变叠加/描边的颜色、不透明度、角度、大小，套整套 ASL 样式，改文字内容（字数可长可短），把一个文字图层复制成多个标签图层，把整个图层组复制一份并整组换色（含栅格位图，不只是图层样式色），按"四角半径不动、只拉伸中间"的方式改按钮/形状的尺寸（矢量形状九宫格重排 + 组内栅格同映射重采样）——然后把 out_ 图层（含图层组）批量导出成透明 PNG、统一成同一画布尺寸居中，并把 PhotoCraft 里改好的分层文档存回 `<需求目录>/psd/制作/` 副本。输入是【清单】+【源 PSD】+【要改什么】，源文件必须先由用户确认才动手。用户说"把自摸改成红色""套这个样式""导出成透明图""这 8 个标签""把按钮改成天蓝色""按钮尺寸适配画布 176×86""整个组复制一个"时用这个 skill。是 FGUI 美术流程的 s4（s2 `/s2-fgui` 生成 FGUI，s3 `/s3-to-psd` 出 PSD 还原稿；本技能 = s4-psd）。
---

# PSD 图层样式编辑与透明图层导出

> **路径约定（先读）**：**工作区根 = 含 `.opencode` 的那层**，下面的命令一律在**工作区根执行**（bash 工具的 `workdir` 设为工作区根，不要靠 cd）。
> **真实 FGUI 工程根 = `client_dir`**（`assets/` + `settings/` + `*.fairy` 所在层），由 s0 写进 `.opencode/workspace.json`；先 `python .opencode/lib/workspace.py where` 看它。
> **需求产物 `<需求目录>` = `.opencode/work/<game_key>/<需求>/`**；实际路径见 `python .opencode/lib/workspace.py where --需求 <需求>`。
> **脚本住在本技能目录**：`.opencode/skills/psd-style/scripts/`（共享库在 `.opencode/lib/`）。
> **脚本零硬编码**：都可以用全路径直接调，脚本自己处理 `sys.path`；只有 `python -c` 内联命令里要手动把脚本目录插进 `sys.path`（下文已写死）。

**运行前提**：**Python 3**（只有 `_fit_frames.py`、`_psd_preview.py`、`_pc_export.py` 需要 **Pillow**，其余纯标准库）；**PhotoCraft 桌面端**（`_pc_export.py` 通过 `.opencode/lib/photocraft.py` 自动拉起，走本机控制端口，不需要浏览器/联网）。第一次用先跑 `python .opencode/lib/photocraft.py --check`。

> **与 s3 的关系**：本 skill 是 FGUI 美术流程的 **s4**。s3 `/s3-to-psd` 产出 PSD 还原稿（`<需求目录>/psd/还原稿/`）；s4 读 **s2 的清单** `<需求目录>/清单.json`，优先从 **PSD 素材库**找可复用稿（命中就改、未命中走占位），改样式/文字/尺寸、导出透明 PNG 拿回 client 工程。**源 PSD 永远只读**（含素材库原件），改动只写进 `<需求目录>/psd/制作/` 的副本。

## 一、输入：清单 + 源 PSD + 要改什么

| # | 输入 | 说明 |
|---|---|---|
| ① | **清单（`<需求目录>/清单.json`）** | 本次要产出的资源表（s2 `fgui-flow` 生成）。决定"要做什么"；本步按它**逐条取件**。**有清单就先读清单** |
| ② | **源 PSD** | 三种来源：**素材库命中**（`find-asset` 候选，人确认）/ s3 的**还原稿** / 用户直接给的 PSD。**必须由用户确认**，不自己搜、不推断 |
| ③ | **要改什么** | 目标单元（组名或 **`lyid`**）+ 逐项改动 + 要导出哪些单元（大白话，如"把按钮改成天蓝色，导出透明图"） |

调用形式随意：`/s4-psd <需求>`（读清单自动取件）、`/s4-psd 结算界面-标签.psd 把自摸改成红色，导出透明图`，或只说需求——**没说 PSD 就先问清楚是哪个文件，再谈怎么改**。

### 源 PSD（输入②）——**强制确认，不许自己搜**

- **源 PSD 三种来源**：① **素材库命中**（`find-asset` 候选，人确认，复制到 `制作/` 再改）；② s3 的**还原稿**（`<需求目录>/psd/还原稿/`）；③ 用户直接给的 PSD。
- **用户没给、清单也没命中时**：直接问"用哪份 PSD？（给我文件名或路径）"，**不要**遍历目录、不要"目录里只有一个所以就是它"、不要从产物目录猜。搜索和推断都禁止，效率低且会改错文件。
- 用户给了名字 → 只做一次存在性检查：`Test-Path '<psd>'`。不存在就把原话回给用户要准确路径，**不要去别处搜同名文件**。
- **产物目录（`<需求目录>`）里的稿一律不当输入**（那是以前的产物）；只有用户明确说"在某个副本上继续改"才用它。
- **源文件只读**：素材库原件 / 用户给的 PSD / 还原稿都**不原地改**；改动只写进副本 `<需求目录>/psd/制作/<槽位名>.psd`。
- 图层名/组名拿不准时用 `--inspect` / `--layers` 查（这是查结构，不是找文件）；**组名可重复**时用 `lyid` 定位（见第五节坑）。

## 二、能力边界

**能做：**

| 改动 | 手段 |
|---|---|
| 颜色叠加 / 渐变叠加 / 描边 的颜色 | `_psd_lfx.py --set-color` / `--set-gradient` |
| 上述效果的 不透明度 / 角度 / 大小 / 距离 / 模糊 | `_psd_lfx.py --set-num` |
| 开关某个效果（关掉盖住目标效果的那一层） | `_psd_lfx.py --set-effect` |
| 套用 ASL 样式库里的**整套**样式 | `_apply_asl.py` |
| 改文字内容（**字数可长可短**） | `_psd_lfx.py --set-text` |
| 改图层名（用来加 `out_` 导出前缀） | `_rename_layer.py` |
| 一个图层**复制成 N 个**标签图层并各自改名 | `_psd_clone.py` |
| 整个**图层组**（分隔符 + 子层 + 组头）复制一份并给新组改名 | `_psd_group_clone.py` |
| 把整个组**换成另一种色系**——栅格位图（光泽/渐变）+ 形状填充 SoCo + 已启用效果色一起换算 | `_psd_recolor.py`（见第六节换算规则） |
| 改**按钮/形状的尺寸**：矢量路径按"四角半径不动、只拉伸中间"重排 + 组内蒙版栅格同映射重采样 | `_psd_reshape.py` |
| 把 `out_` 图层**批量**导出成每层一张透明 PNG（可放大画布、可按图层改文字、**目标是图层组也行**） | `_pc_export.py`（自动识别组） |
| 把 PhotoCraft 里改好的**分层文档存回** PSD，覆盖 `$work` 副本（`lfx2` 图层样式 / 真文字 / 组都保留） | `_pc_export.py`（默认回存；`--save-psd` 可换路径） |
| 检查制作副本的图层像素是不是真的换了（各层像素 md5 应各不相同） | 见第五节「副本打开还是旧字」 |
| 一批 PNG **统一成同一画布尺寸并居中** | `_fit_frames.py` |
| 检查自己的解析/重写有没有把 PSD 写坏 | `_psd_struct.py <psd>`（字节级自检） |
| 直接用像素/组结构做别的编辑（换色、重采样、整组克隆的底层） | `_psd_raster.py`（通道 RLE 编解码 + 图层像素读写）、`_psd_group.py`（组定位 / 成员 / clip / 可见位） |

**不做：** 不给设计建议、不自己发明配色——用户给什么就执行什么（配色只按第五节的规则做**明度/色相换算**，换算结果要写进确认清单）。**不重建素材库索引**：s4 对素材库永远**纯只读**（只读已有 `index.json` 与 `_预览/`），扫描生成素材库索引属于离线维护任务（见 `.opencode/PSD素材库/README.md`），不在需求单执行范围内。
**不动：** 素材库原件 PSD（永不原地修改）、输入 PSD、`reskin-studio/`。导出器 `_pc_export.py` 只在**加参数**时改，不改它已验证的导出协议（`out_` 前缀 → 每层一张透明 PNG）。

## 三、流程（强制顺序）

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
4. **回填清单**：`workspace.py manifest-set <需求> --id R1 --set 来源=素材库命中 --set 素材库命中=S1 --set 重组手法=换色`

> 没有清单（用户直接给了个 PSD）→ 跳过本步，直接进确认。

### 确认——没确认前不写任何文件

列成一段话回给用户，等他同意。**第 1 项是硬闸门：源文件没被用户确认，什么都不许做。**

1. **源文件（输入②）**：`xxx.psd` —— 已由用户确认（或素材库命中/还原稿）；没有就先问，不猜不搜
2. **目标单元**（组名，或 **`lyid`**——组名可重复时用 `lyid` 精确定位，如 `--组lyid 23`）
3. **逐项改动**（改前 → 改后）
   - 改颜色 → 效果名 + 现值 → 新值（现值用 `--inspect` 查出来）
   - 改文字 → 改前 → 改后（**说明字数是否变化**）
   - 套样式 → 样式名 + 该样式的参数（用 `_asl_extract.py` 查出来）
4. **要导出哪些图层** + **输出文件名** + **成图尺寸规则**——尺寸是确认项，必须问到位：
   - 只出一组：统一成多大（按哪张内容框算，或直接给 `WxH`）、内容怎么放（居中？）
   - **多组（不同字体/不同图层各一组）**：**逐组**问清楚每组的目标尺寸 `WxH`，尤其是
     **两组要不要同一个画布高度**、要不要同宽，以及内容居中还是对齐基线。
     "两组各自统一"这句话**不够**（各自按自己的内容框算，出来往往不同高、贴同一锚点会错位）——必须落到具体数字或明确说"同高 = 多少"。
   - 尺寸定错了不会毁 PSD：内容没动，回头 `_fit_frames.py <目录> --size WxH` 补/裁留白即可，但要重跑一遍校验。
5. **一个 PSD 多个标签时**：说明是"复制成 N 个图层"还是"改现有 N 个图层"
6. **改按钮/形状尺寸时**：先量**剪切基底**（组内 `clip=0` 那一层）的内容框当"改前尺寸"——**别把 `clip=1` 剪切蒙版层的溢出算进去**（组内容并集往往更大且偏位，用户会当场指出），见第五节；确认新的 bbox `x0,y0,x1,y1`（或目标 W×H + 摆放）、确认**圆角半径是保持原值还是按比例放大**（默认保持），并说明**图层效果参数默认不动**（斜面 53% 是相对图层尺寸的、会随按钮变大而变宽；投影是 px 不变）
7. **整组复制时**：新组名、复制到原组正上方、组内子层名保持原样；并说明副本里两个按钮是**重叠**在同一位置的

**改颜色前必须先看 `--inspect` 里的 `[开]` / `[未用]`：** 叠加类效果（渐变叠加 / 颜色叠加 / 图案叠加）互相遮盖，渐变叠加开着的时候只改颜色叠加的颜色，画面上根本看不出来。这时要在确认清单里问清用户：**关掉渐变叠加，还是连渐变的颜色一起改**。

例：
> 按 `结算界面-标签.psd` 处理：把 `自摸` 复制成 8 个图层（名字 = 输出文件名），正面 4 个只改文字，负面 4 个文字 + 渐变改 #B8EFFF→#56AAFF、描边改 #023EB6；导出 8 张透明 PNG，统一成同一尺寸、内容居中。对吗？

### 执行——按顺序调脚本

```powershell
# 先确认 <需求目录> 实际路径（默认 .opencode/work/<game_key>/<需求>）
python .opencode/lib/workspace.py where --需求 <需求>

# a) 源文件（必须已由用户确认；只读，改的是副本）。
#    命中素材库：源 = 素材库里的 PSD；未命中/手工：源 = 还原稿或用户给的 PSD
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
#     先按确认好的 bbox 重排形状（四角半径保持、只拉伸中间，含组内蒙版栅格），
#     再整组复制（两个按钮因此天然同尺寸），最后只给新组换色
#     ★ 组名可重复（素材库 PSD 常见）时用 --组lyid 精确定位；按组名也行（与 --组lyid 二选一）
python .opencode/skills/psd-style/scripts/_psd_reshape.py    $work --组lyid 23 --bbox 2,2,174,84 --out $work
python .opencode/skills/psd-style/scripts/_psd_group_clone.py $work --组lyid 23 --name img_zi_card_blue --out $work
python .opencode/skills/psd-style/scripts/_psd_recolor.py    $work --组lyid 23 --target blue --out $work

# e3) 导出切图前：把目标单元**自动加上 out_ 前缀**（素材库原件本就不带，运行时补）
python .opencode/skills/psd-style/scripts/_rename_layer.py $work - out_<槽位名> --lyid 23 --out $work

# f) 改完先自检：解析→重写必须与原文件逐字节一致，不一致就是解析口径错了
python .opencode/skills/psd-style/scripts/_psd_struct.py $work

# g) 批量导出 + 回存（自动拉起 PhotoCraft；不需要浏览器）
#    --texts   ：导出前改**真文字层**（导出立即按新字重排，不需要额外烘焙）
#    --canvas  ：导出前放大画布，防止长文字超出原画布被裁
#    目标是**图层组也行**（脚本自动识别，不用再加 --groups）
#    默认把文档存回 $work；要换路径用 --save-psd，只导 PNG 用 --no-save
python .opencode/skills/psd-style/scripts/_pc_export.py $work "<需求目录>/切图" --canvas 400x160 --texts "<需求目录>/_tmp/texts.json"

# h) 统一成同一画布尺寸 + 内容居中（默认取"最大的那张内容框"）
python .opencode/skills/psd-style/scripts/_fit_frames.py "<需求目录>/切图" --files img_a.png,img_b.png,img_c.png

# h2) 多组输出时，**按确认环节跟用户确认好的尺寸**逐组统一（别默认"各自取最大内容框"）
#     尺寸是确认项、不是硬规则：两组要不要同高由用户定，要同高就显式给 --size
python .opencode/skills/psd-style/scripts/_fit_frames.py "<需求目录>/切图/文字"                # → 用户确认的尺寸，如 71×81
python .opencode/skills/psd-style/scripts/_fit_frames.py "<需求目录>/切图/数字" --size 50x81   # → 用户确认的尺寸；要两组对齐就给同高

# i) 确认每张图真的不同：内容框/主色不一样（全一样 = 文字没改成功）
#    `_pc_export.py` 尾部已经自动打印这些数；要单独复查就重跑它的校验段。

# j) 定稿后回写：切图**同名覆盖** s2 快照与 client 工程根，清单状态=已替换
python .opencode/lib/workspace.py place <需求> [--id R1]
```

`--texts` 的 JSON 长这样（键 = 图层名，值 = 新文字；用 UTF-8 写文件，别在命令行里塞中文）：

```json
{ "out_a": "自摸", "out_b": "捉炮胡" }
```

关于回存 PSD：`_pc_export.py` **默认就会回存**（存回输入的 `$work`），不用再单独加参数。

- `--texts` 改的是 PhotoCraft 里的**真文字层**，导出和回存都是新字；不再有"只改 TySh、像素还是旧字"的问题。
- 回存是 PhotoCraft 自己写的 PSD：`lfx2` 图层样式、`TySh`、组、图层名和顺序都保留，`_psd_struct.py` 对它同样报"逐字节一致 ✓"。
- 覆盖前会自动备份成 `$work.pre-pc.bak`（只备份第一次）。
- **副本里的 `out_` 前缀保留**（那是导出协议的选层标记）；导出 PNG 的文件名自动去掉前缀。

### 汇报

- 输入 PSD（哪个，来源：素材库命中 / 还原稿 / 用户给）+ **制作副本路径**（`<需求目录>/psd/制作/`）
- 每个 PNG 的**路径 / 尺寸 / 透明占比 / 主色**（用下面的校验命令）
- **副本内容校验**：导出 PNG 的内容框/主色是否各自不同（全一样 = 文字没改成功）
- **多组同时输出时**：按确认环节定好的尺寸逐组核对；顺带报各组的**内容中线 y**（便于用户确认两组摆放是否对齐）
- **"两个要一样大"这类要求**：别只说尺寸相同——直接比两张 PNG 的 **alpha 通道是否逐像素相同**（`ImageChops.difference` 最大差值 0 才算真的一样大），并报各自的**实体框（alpha>250）**
- **改过按钮/形状尺寸时**：报重排后的 **vmsk 形状 bbox** 与导出 PNG 的实测内容框是否吻合；PhotoCraft 存 PSD 时形状层是 **vmsk + vogk + SoCo 的矢量层**（图层仍可二次编辑），导出 PNG 按实时渲染，属正常
- 哪一步失败就说清卡在哪，不编造结果
- **切图落点与回写**：切图在 `<需求目录>/切图/`；定稿后 `workspace.py place <需求>` 已把它**同名覆盖**到快照（`<需求目录>/FGUI/`）与工程根，清单 `状态=已替换`

校验 PNG（必须做，至少确认 8 张尺寸一致 + 四角透明 + 主色对不对）：

```powershell
python -c "from PIL import Image; from collections import Counter; import glob;
[ (lambda im: (lambda r: print(p, r.size, '内容框=', r.getchannel('A').getbbox(), '四角alpha=', [r.getpixel(c)[3] for c in [(0,0),(r.size[0]-1,0),(0,r.size[1]-1),(r.size[0]-1,r.size[1]-1)]], '主要颜色=', ['#%02X%02X%02X x%d'%(c[0],c[1],c[2],n) for c,n in Counter([q[:3] for q in r.getdata() if q[3]>200]).most_common(3)]))(im.convert('RGBA')))(Image.open(p)) for p in sorted(glob.glob('<需求目录>/切图/*.png'))]"
```

**注意**：
- 校验前一律 `convert('RGBA')`（PhotoCraft 导出的 PNG 通常已是 RGBA，但统一转换不亏）。
- **同一批图的尺寸必须一致**：`_fit_frames.py` 会打印"尺寸种类：1 一致 ✓"，不是 1 就说明没统一。
- **内容框宽度要能区分不同字数**：如果 8 张内容框完全一样大，几乎肯定是 `--texts` 没生效（见第五节第一条）。

## 四、脚本调用速查

脚本都在 `.opencode/skills/psd-style/scripts/`；下面写成全路径（`P` 代指该目录，实际照抄即可）。

| 目的 | 命令 |
|---|---|
| 列出图层 | `python .opencode/skills/psd-style/scripts/_psd_lfx.py --layers <psd>` |
| 查某图层全部样式现值 | `python .opencode/skills/psd-style/scripts/_psd_lfx.py --inspect <psd> <图层名>` |
| 查样式库有哪些样式 | `python .opencode/skills/psd-style/scripts/_asl_extract.py <库.asl> --list` |
| 改颜色 | `python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-color <psd> <图层> <效果> <RRGGBB> --out <out>` |
| 改渐变两端 | `python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-gradient <psd> <图层> <亮端> <暗端> --out <out>` |
| 改数值参数 | `python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-num <psd> <图层> <效果> <参数> <值> --out <out>` |
| 开关效果槽 | `python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-effect <psd> <图层> <效果> on\|off --out <out>` |
| 改文字（可长可短） | `python .opencode/skills/psd-style/scripts/_psd_lfx.py --set-text <psd> <图层> <新文字> --out <out>` |
| 套整套 ASL | `python .opencode/skills/psd-style/scripts/_apply_asl.py --psd <psd> --asl <库> --style <样式名或序号> --layer <图层> --out <out>` |
| 改图层名（加 `out_` 前缀） | `python .opencode/skills/psd-style/scripts/_rename_layer.py <psd> <图层名> <新名>`；按 lyid：`_rename_layer.py <psd> - <新名> --lyid <n>` |
| 复制图层成 N 份 | `python .opencode/skills/psd-style/scripts/_psd_clone.py <psd> --from <图层名> --names a,b,c --out <out>` |
| 复制**整组**（含子层/分隔符/组头）并改名 | `python .opencode/skills/psd-style/scripts/_psd_group_clone.py <psd> --group <组名>|--组lyid <n> --name <新组名> --out <out>` |
| 整组换色（栅格位图 + SoCo + 已启用效果色，黄→天蓝） | `python .opencode/skills/psd-style/scripts/_psd_recolor.py <psd> --group <组名>|--组lyid <n> --out <out>` |
| 改形状/按钮**尺寸**（九宫格重排矢量点 + 蒙版栅格重采样） | `python .opencode/skills/psd-style/scripts/_psd_reshape.py <psd> --group <组名>|--组lyid <n> --bbox x0,y0,x1,y1 [--radius 5] --out <out>` |
| 看组的成员/剪切关系/可见位 | `python -c "import sys;sys.stdout.reconfigure(encoding='utf-8');sys.path.insert(0,r'.opencode/skills/psd-style/scripts');import _psd_struct as S;from _psd_group import find_group,describe;st=S.parse(open(r'<psd>','rb').read());print(describe(st,find_group(st,'<组名>')))"`（不写 `reconfigure` 中文在控制台会花屏） |
| 结构自检（字节级） | `python .opencode/skills/psd-style/scripts/_psd_struct.py <psd>` |
| 导出透明 PNG + **回存 PSD** | `python .opencode/skills/psd-style/scripts/_pc_export.py <psd> <out目录> [--prefix out_] [--canvas WxH] [--texts 清单.json] [--save-psd 副本路径] [--no-save]` |
| 统一尺寸 + 居中 | `python .opencode/skills/psd-style/scripts/_fit_frames.py <目录> [--files a.png,b.png] [--pad 0] [--size 240x60] [--suffix ""]` |
| 查 TySh / EngineData 细节 | `python .opencode/skills/psd-style/scripts/_psd_tysh.py <psd> [图层名]` |
| 不开 PhotoCraft 直接看图层长什么样 | `python .opencode/skills/psd-style/scripts/_psd_preview.py <psd> [输出目录]`（解码通道出预览 + 打印渐变色标） |

**效果名**（`<效果>` 参数）：`颜色叠加` / `渐变叠加` / `描边` / `外发光` / `内阴影`（也可直接写 lfx2 槽名 `solidFillMulti` / `GrFl` / `FrFX` / `OrGl`）。
**数值参数**（`<参数>`）：`不透明度` / `角度` / `大小` / `距离` / `模糊` / `阻塞` / `杂色`。

**长度字段谁来修**：
- 颜色 / 数值 / 等长文字 = 等长替换，不动任何长度字段。
- `--set-text`（字数变化）、`_psd_clone`、`_rename_layer`、`_apply_asl` 会变长度，它们自己重算：TySh 块长、EngineData 长度、图层额外数据长度、layer-info 段长、layer-and-mask 段长（`_psd_struct.py` 统一负责，先用它自检再动真格）。

## 五、实测经验与故障排查（都是踩过的坑）

| 症状 | 原因 / 处理 |
|---|---|
| **制作副本打开还是旧内容**（文字属性改了，画面没变） | 只做字节级 `--set-text` 时，PSD 里存的是 TySh + 旧光栅。现在统一走 `_pc_export.py --texts`：它在 PhotoCraft 里改**真文字层**，导出的 PNG 与回存的 PSD 都是新字 |
| **导出的字形不对** | PhotoCraft 用 **Windows 系统字体**（不像 Photopea 要加载 TTF）。确认图层用的字体本机已安装；不确定就用 `type.fonts` 查，或改成微软雅黑 |
| 回存后文件打不开 / 不是 PSD | 先跑 `_psd_struct.py <psd>` 自检；PhotoCraft 的 `app.save` 失败会带 `warnings`，把错误原样报出来，别猜 |
| 两组图贴同一锚点，y 对不齐 | 先看确认环节的记录：**成图尺寸定的是什么**。多组时各自"取最大内容框"会得到不同画布高度（例：数字组 66 高、文字组 81 高），贴同一锚点内容就错位。处理：**回确认环节跟用户定高度**，再用 `_fit_frames.py <目录> --size 50x81` 补留白（内容不用重导）。⚠️ 同高不是硬规则 —— 用户要两组不同高就照做，只要确认过；错的是"尺寸没确认清楚就开跑"。校验：两组 `内容中线y` 一致（0.5px 属整数取整的正常误差） |
| **8 张导出来文字全一样**（内容框尺寸完全相同） | `--texts` 没生效：键必须是**带 `out_` 前缀的完整图层名**；且图层必须是 Type 图层（不是已栅格化的像素层）。脚本会打印每条 `文字 xxx -> 新值`，没有就是没命中 |
| **长文字被切掉一截** | 原画布不够宽（如 160px 画布放不下 4 个字 ≈196px）。给 `_pc_export.py` 加 `--canvas 400x160`，导出前用 `image.canvasSize` 扩画布；最终成图尺寸靠 `_fit_frames.py` 统一 |
| 各张图尺寸不齐 | 没做统一：跑 `_fit_frames.py <目录> --files ...`，它会打印"尺寸种类：1 一致 ✓" |
| PhotoCraft 连不上 | 先 `python .opencode/lib/photocraft.py --check`；会自动拉起桌面端。**路径越界**会被拒（automation read/write root），看报错里的路径 |
| 导出 0 张图 | PSD 里没有 `out_` 开头的图层 —— 用 `_psd_clone.py`/`_rename_layer.py` 加 `out_` 名（组名重复时用 `_rename_layer.py <psd> - out_xxx --lyid <n>` 按 lyid 加） |
| 改文字报错 | 目标不是文字图层（没有 TySh：可能已被栅格化）或图层名写错；`--layers` 核对真名 |
| PS 打不开改完的 PSD | 长度字段没修正。跑 `python .opencode/skills/psd-style/scripts/_psd_struct.py <psd>`，它必须报"逐字节一致 ✓" |
| 颜色没变（看着还是旧的） | 效果是禁用状态 —— 脚本已自动把 `enab`/`present` 置 true，若仍不变用 `--inspect` 确认改的是哪个槽 |
| 改了颜色但 PNG 上看不出来 | 被别的叠加效果盖住了（渐变叠加/图案叠加/描边）；用 `--set-effect <效果> off` 关掉，或把它也一起改 |
| 找不到图层 | `--layers` 看真实图层名；`--inspect` 报错会列出全部图层名。注意 `match_layer` 支持子串匹配，短名字可能命中长名字 |
| **组名重复 / 改错组**（同色按钮一堆，PSD 允许同名组） | 组名不可靠 → 用 **`lyid`** 定位：`--组lyid <n>`（`_psd_recolor` / `_psd_reshape` / `_psd_group_clone`）、`_rename_layer.py <psd> - <新名> --lyid <n>`。`lyid` 每层唯一，`build_index` 已把 `组:[{名,lyid}]` 抽出来 |
| **导出图层组得到空图 / 只导出一片空白** | `_pc_export.py` 自动做子树感知：目标自身 + 其后代 + 其祖先可见，其余隐藏。若还是空，先确认组名带 `out_` 前缀，且组里不是全隐藏层 |
| **量按钮尺寸量错**（内容框又大又偏、边距不对） | 组里 `clip=1` 的**剪切蒙版层**（光泽/高光）像素会溢出基底，组内容的并集比按钮真实尺寸大且偏位。**要量的是剪切基底**（组内 `clip=0` 那层）的 alpha 内容框，或者干脆用矢量形状的 bbox（`vmsk`）。实测教训：`选字.psd` 组内容并集 161×72/偏左上，而真身基底只有 144×51 且基本居中 |
| **改按钮尺寸：整张等比拉伸后圆角变椭圆、光泽糊掉** | 这类按钮是**矢量形状层 + 剪切蒙版光泽**，不能整张缩放。正解是九宫格重排：`_psd_reshape.py` 把 vmsk 的 8 个结点按"四角半径不动、只拉伸中间段"的新坐标重算 + 同步改 vogk 的 `keyOriginShapeBBox`，组内蒙版栅格用**同一分段线性映射**重采样（见第七节口径） |
| **改完尺寸后预览里形状层看不到像素 / 0×0** | 形状层是 **vmsk + vogk + SoCo** 的矢量层（仍可二次编辑）；`_psd_preview.py` 只解位图，看不到它属正常。导出的 PNG 依然按实时渲染 |
| **`enab`/`present` 都改了，画面还是黄的**（按钮类） | 这类按钮的黄色**主要来自栅格位图**（光泽/渐变层），图层样式色只占很小一部分。必须做**像素级换色**：`_psd_recolor.py`（HSL 只换色相，规则见第六节），只改 SoCo/效果色是看不出来的 |
| **图层"可见位"读反，得出"所有层都是隐藏的"** | 图层记录 flags 字节的 **bit1（0x02）是隐藏位：置位 = 隐藏**（规范里"bit 1 = visible"极易读反）。实测校对：`源文件\选字.psd` 里用户确认隐藏的 `图层 0` 是 `0x0a`（置位），可见的按钮各层是 `0x08`。`_psd_group.py` 的 `visible()` 已按这个口径写死并注释 |
| **回存后副本里所有图层都可见、两个按钮重叠在一起** | 旧 Photopea 流程会这样；现在的 `_pc_export.py` 导出后会**恢复原可见性**再回存，不会把隐藏层全打开 |
| **形状层的矢量块找不到路径坐标**（vmsk 里的数全是 0.0x 这种小数） | 这些 PSD 的 vmsk 路径是**按画布尺寸归一化**存的（×宽/×高才是文档坐标），vogk 里还并存一份 `keyOriginShapeBBox`（文档坐标的 double）。改动后两处都要写、写成一致；改完用 `vmsk` 解出的 bbox 和导出的 PNG 实测内容框对一下。细节见第七节 |
| 模块找不到（`_drop_block` 等） | 那些是已删的可选依赖，正常流程用不到；`--drop-lrfx` 不要加 |

**校验制作副本到底有没有改内容**：不再看 PSD 里的像素 md5（文字层存的是 TySh，比较 md5 没意义）；
直接看导出的 PNG —— 各张的**内容框宽度 / 主色**必须各不相同：

```powershell
python -c "from PIL import Image; import glob,os;
[print(os.path.basename(p), Image.open(p).size, Image.open(p).convert('RGBA').getchannel('A').getbbox()) for p in sorted(glob.glob(r'<需求目录>/切图/*.png'))]"
```

若各张内容框完全一样，回到 `--texts` 检查键名（要带 `out_` 前缀）和图层类型。

## 六、配色知识库（只做换算，不做设计）

把一套颜色换成另一套（如"黄→金"换成"蓝"）时的规则，**保持明度/饱和度的对应关系，只换色相**，另加两条修正：

1. **冷色（蓝、紫）在同明度下看着比暖色暗** → 换成蓝/紫时明度要**整体上调**（HSL 的 L 约 +0.04~0.08）。同明度硬换会显"发闷"。
2. **渐变两端不要取同一色相**：亮端保持目标色相，**暗端相对往暖色偏**。色环上"更暖"= 往红走：黄 → 橙 → 红；蓝 → 紫 → 品红 → 红（所以蓝的暗端偏紫，不是偏青）。原稿黄→金就是暗端从 H53° 偏到 H42°（约 10°）。
3. **描边**通常保持原稿描边的 明度/饱和度（它是"深色"，深色不用跟着上调），只换色相；色相取渐变暗端再往暖走一点。

本项目标签的实测对照（可直接复用）：

| 部位 | 正面（原稿） | 负面（蓝） |
|---|---|---|
| 渐变亮端 | `#FFF5A4` H53 S1.00 L0.82 | `#B8EFFF` H193 S1.00 L0.86 |
| 渐变暗端 | `#FFC73F` H42 S1.00 L0.62 | `#56AAFF` H210 S1.00 L0.67 |
| 描边 | `#B51B02` H8 S0.98 L0.36 | `#023EB6` H220 S0.98 L0.36 |

换算用 HSL/HSB 都行，但**别只看 H**：色环是首尾相接的，"提高/降低 H"判断不了冷暖，只能按"相对往哪个方向偏"说。

本项目**按钮**的实测对照（`选字.psd`，黄 → 天蓝；`_psd_recolor.py` 就是按这套锚点实现的）：

| 部位 | 黄（原稿） | 天蓝（换算后） |
|---|---|---|
| 形状填充 SoCo / 亮部像素 | `#FFF289` H54 S1.00 L0.76 | `#A2ECFF` H191 S1.00 L0.81 |
| 内发光 IrGl | `#FFDC47` H46 | `#60CBFF` H204 |
| 斜面高光 ebbl.hglC | `#FFE64C` H47 | `#66D8FF` H201 |
| 斜面暗部 ebbl.sdwC | `#FB8F02` H34 S0.98 L0.49 | `#024DFB` H222（深色 L 不动） |
| 投影 dropShadow | `#BA522C` H14 S0.62 L0.45 | `#2C57BA` H222 L0.45 |
| 近黑投影 | `#0D262B` H189 | **不变**（色相不在黄橙区间） |

像素级换算的实测口径：`_psd_recolor.py` 对 **S ≥ 0.10 且 H 在 15~80** 的像素/颜色做
`H_new = 210 + (H-42)×(193-210)/(53-42)`，再钳到 H185~222；S 不变，L ≥ 0.55 的亮部 +0.05（深色不加）。
按钮类素材的像素往往**全是 S=1.0 的黄橙**，映射很干净；半透明的边缘像素按同一规则走即可。

## 七、矢量形状层的结构口径（改尺寸 / 改形状必读）

一个"圆角矩形按钮"在文件里是三层数据；改形状要同时动前两层，第三层是像素：

**1. `vmsk`（矢量蒙版 = 形状路径）** = `u32 版本(3) + u32 flags + Path`

```
Path    = 一串记录，每条 = u16 selector + 24 字节载荷（末尾可能有 <26 字节的 4 字节对齐填充）
selector（PathResourceID）：0 封闭子路径长度 / 1 封闭结点(相连) / 2 封闭结点(不相连)
                          3 开放子路径长度 / 4 开放结点(相连) / 5 开放结点(不相连)
                          6 路径填充规则 / 7 剪贴板 / 8 初始填充规则
子路径（0/3）载荷 = u16 结点数 + i16 operation + u16 + u32 + u32 + 10 字节
结点（1/2/4/5）载荷 = 3 个点 × (i32 y, i32 x)，8.24 定点
                     3 个点 = 前控点 / 锚点 / 后控点（直线段的后控点 = 锚点）
```

**坐标是按画布尺寸归一化的**：文档坐标 = 存的值 / `0x01000000` × (画布宽, 画布高)。
实测：`选字.psd` 的路径 ×176 / ×86 后与 vogk 的 bbox 完全吻合（15.7812, 15.6562）-
(158.5000, 65.2188)，圆角半径 5px。

**2. `vogk`（实时形状元数据）** = 描述符，含 `keyOriginRRectRadii`（四角半径，#Pxl 双精度）、
`keyOriginShapeBBox`（Top/Left/Btom/Rght，**文档坐标** double）、`keyOriginResolution`、`keyOriginIndex`。
三个坑：

- 找 bbox 的 `Left` **不能全 buffer 搜** `Left + UntF#Pxl` —— 会撞上半径里的 `topLeft`/`bottomLeft`；
  要先锚定 `keyOriginShapeBBox` 再在它之后找（`_psd_reshape.py::vogk_slots` 已这么写）。
- "半径保持" = 只改 bbox、**不动 radii**；要按比例放大半径才改 `keyOriginRRectRadii` 的那 4 个 double。
- **两处都改到一致**，才不会因为"Photopea/PS 到底读哪个"而翻车（实测 Photopea 按 vmsk + SoCo 渲染）。

**3. 组内栅格 + 剪切**：基底是组内 `clip=0` 那层，上面几层是 `clip=1` 的剪切蒙版层（光泽/高光），
像素会溢出基底。改形状时它们要按**同一分段线性映射**九宫格重采样（角区刚性平移、中间段拉伸、
bbox 之外按最近段斜率刚性外推），图层 rect 与通道长度字段一起重算。

**改尺寸的正解顺序（别颠倒）**：`_psd_reshape.py` 重排 → `_psd_group_clone.py` 整组复制 →
`_psd_recolor.py` 只给新组换色。这样两个按钮天然同尺寸，换色也只作用于副本。

**两条通用口径**：

- `lyid`（图层 ID）不能重复：克隆图层/组时新副本要重新发号（`_psd_clone.py` / `_psd_group_clone.py` 都做了）。
- 通道数据 = `u16 压缩标志（0 原始 / 1 RLE）+ 数据`；RLE 是 PackBits（`n>=0` 复制 n+1 字节、
  `n<0` 重复 `1-n` 次）+ 高×u16 行字节数表。改像素必须**同步改图层记录里的 `(cid, clen)` 通道表**——
  `_psd_raster.py` 负责重建 head，别只换数据不改长度。
