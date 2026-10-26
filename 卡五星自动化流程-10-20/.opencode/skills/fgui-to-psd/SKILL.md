---
name: fgui-to-psd
description: 把 FGUI 里某个界面的布局还原成一份 PSD——读界面 XML（连同它引用的组件、控制器/gear 页值、图片资源），算出每个节点在画布上的绝对坐标、尺寸、文字与配色，然后在 PhotoCraft 里从零搭出一份同尺寸的分层 PSD（每个节点一个图层、FGUI 的组就是图层组、文字是真·可编辑文字层、按钮的多个状态各摆一个），并给"复用了工程现有资源、不需要重新导出的图"的图层名加 `复用_` 前缀；最后存 PSD 到磁盘并逐层校验坐标。输入是【FGUI 界面 XML】+【哪些图是复用件】，XML 必须先由用户确认才动手。用户说"按 FGUI 生成 PSD""把选字界面还原成 PSD""FGUI 转 PSD""照这个界面出一份 PSD 稿""XxxMahXuanZiView 生成 PSD""出 PSD 还原稿"时用这个 skill。是 FGUI 美术流程的 s3（s2 `/s2-fgui` 生成 FGUI 工程；本技能是 s3-to-psd）。
---

# FGUI 界面 → PSD 布局还原稿

> **路径约定（先读）**：**工作区根 = 含 `.opencode` 的那层**，所有命令都在这层执行（bash 工具的 `workdir` 设为工作区根，不要靠 cd）。
> **真实 FGUI 工程根 = `client_dir`**（`assets/` + `settings/` + `*.fairy` 所在层），由 s0 写进 `.opencode/workspace.json`；先 `python .opencode/lib/workspace.py where` 看它。
> **需求产物 `<需求目录>` = `.opencode/work/<game_key>/<需求>/`**；实际路径用 `python .opencode/lib/workspace.py where --需求 <需求>` 核对。
> **脚本住在本技能目录**：`.opencode/skills/fgui-to-psd/scripts/`。
> **不写死任何工程名/路径**：`_fgui_layout.py` / `_pc_build.py` 靠"从界面 XML 位置 / 当前目录向上找 `*.fairy` + `assets/`"定位工程根（也可 `--assets` 显式指定），换工程也能用。

**一句话**：FGUI 提供**位置 + 系统文字**，图片资源已经存在于工程里，本 skill 把两者拼成一份
**PSD 还原稿**——美术能在 Photoshop 里直接看布局、直接改字、直接换图。

**运行前提**（缺一跑不动）：
- **Python 3.10+**，装 **Pillow**（`_fgui_layout.py` 读图片像素尺寸；导出校验也用它）。
- **PhotoCraft 桌面端**（本机安装）。`_pc_build.py` 会通过 `.opencode/lib/photocraft.py`
  **自动拉起**桌面端（`--control 7878` + token 文件 + 自动化读写根），不需要浏览器、不需要联网。
- 第一次用先自检：`python .opencode/lib/photocraft.py --check`（端口 / token / 文件位置都会打印）。
- 桌面端启动时带的读写根默认是：读根 = 工作区根的上一级（含素材库），写根 = 工作区根。
  如果 PSD/图片在别处，用环境变量 `PHOTOCRAFT_READ_ROOT` / `PHOTOCRAFT_WRITE_ROOT` 覆盖，
  或写进 `.opencode/photocraft.json`。

## 一、输入：两样（需求名 + psd-spec.json，或手选界面 XML）

| # | 输入 | 说明 |
|---|---|---|
| ① | **需求名 / psd-spec.json** | 优先读取 `<需求目录>/psd-spec.json`（s2 产出），**自动承接组件 XML 路径、复用件与九宫格客观事实**，无需手工声明复用件 |
| ② | **界面 XML（备用兜底）** | 若无 `psd-spec.json`，则需用户指定还原哪个界面，如 `assets/xxx/XxxView.xml`，并手动指定复用件 |

调用形式：`/s3-to-psd <需求>`（自动消费 `psd-spec.json` 并对照 `.opencode/knowledge/psd-art-spec.md` 生成规范 PSD）。

> **产物落点（先读）**：本步的还原稿与中间产物都落 `<需求目录>/` = `.opencode/work/<game_key>/<需求>/`（`psd/还原稿/`、`_tmp/`）。实际路径见 `python .opencode/lib/workspace.py where --需求 <需求>`（打印的 `out_root` = `.opencode/work`）。FGUI 工程本体与此处无关。

### 规则知识库依赖（核心）

本技能执行时，必须对照 **`.opencode/knowledge/psd-art-spec.md`**：
- 复合组件实例自动打上 `【group】<组件名>`
- 跨包/公共组件实例自动打上 `【common】<组件名>`
- 列表容器自动打上 `【列表】<列表名>`
- 九宫格资源自动打上 `【九宫】<图层名>`
- 复用切片资源打上 `复用_<图层名>`
- 背景遮罩纯色打上 `【ignore】<图层名>`
- **严禁提前包含【新】标签**（归美术制作后手动添加）

## 二、能力边界

**能做：**

| 事项 | 手段 |
|---|---|
| 解析 FGUI 界面 XML → 每个节点的**绝对坐标 / 尺寸 / 文字 / 配色 / 显隐** 清单 | `_fgui_layout.py` |
| 递归展开被引用的组件（同包 `src=` 与跨包 `pkg=+src=`），套实例覆盖 | `_fgui_layout.py`（自动） |
| 解算控制器 + gear（`gearIcon`/`gearColor`/`gearDisplay`/`gearLook`）得出"这一页长什么样" | `_fgui_layout.py`（自动） |
| 解算 `relation`（width-width / height-height / center-center / middle-middle） | `_fgui_layout.py`（自动，见第五节口径 3） |
| 从零在 PhotoCraft 里搭出分层 PSD：建文档 / 建图层组 / 置入图片 / 建**真文字层** / 建**黑白调整层** | `_pc_build.py` |
| 图层名加 `复用_` 前缀（= 不需要重新导出） | `_fgui_layout.py --reuse` |
| 搭完**逐层校验**（图层名 / 坐标 / 隐藏态 / 调整层剪贴位置） | `_pc_build.py`（自动，最后回读图层树比对） |

**不做：**
- **不反推设计**：只还原 FGUI 里写着的东西。FGUI 里没有的（描边、投影、渐变）不自己加。
- **不改 FGUI 工程**：一个字节都不动。
- **不导出切图**：本 skill 只出 PSD。要导出图层成 PNG 是 `psd-style` 的 `_pc_export.py` 的活。
- **不判断"哪个图该复用"**：FGUI 里没这个信息，只按用户给的清单标。

**不动：** `_pc_export.py`（s4 的导出链路）、`reskin-studio/`。
`_pc_build.py` 与 `_pc_export.py` 各自独立——**不合并**。

> **与 s2 的关系**：本 skill 是 FGUI 美术流程的 **s3**，吃 s2 的产物。s2 `/s2-fgui` 把需求落到 client 工程，并 `snapshot` 一份到 `<需求目录>/FGUI/`；s3 **从快照（或 client 工程根）读界面 XML**，把 PSD 还原稿产出到 `<需求目录>/psd/还原稿/`（给美术改图的源稿）。具体还原哪个界面**由用户点**，不自动全出。

## 三、流程（强制顺序）

### 确认——没确认前不写任何文件

先把界面解析出来（只读，不写产物），把结果整理成**一句话清单**回给用户：

1. **画布**尺寸（来自界面 XML 根节点的 `size`）
2. **图层树**：每个节点 → 一层；FGUI 的 `<group>` 与组件实例 → 图层组
3. **文字**：内容 / 字号 / 颜色 / 中心坐标（FGUI 是**系统文字**，PSD 里做真文字层）
4. **复用标记**：哪几张图会被加 `复用_` 前缀
5. **需求名 + 产物落点**：`<需求目录>/psd/还原稿/`（先 `workspace.py where --需求 <需求>` 确认实际路径）
6. **三个必须问清楚的**（不问就会返工）：
   - **按钮的多个状态**：组件控制器有几种状态（如 `C_ZiState` = 待选择/他人已选/自己选中），
     **不能全按一个状态画**——挑几个按钮把状态**都展示出来**（用户口径：前 3 个按钮分别演示 3 个状态，
     其余走默认态）。"变灰"用**黑白调整图层**实现，不要自己去改图片像素。
   - **文字字体**：FGUI 的 `settings/Common.json` 里 `font=""` 是**运行时默认字体**，
     **推不出具体字体名**。按本仓先例用「系统字体近似」（见第五节坑 6），或按用户指定。
   - **确认项落成数字**：多组尺寸/坐标类的分歧要落到具体数值，别用"大致居中"这种话。

**没得到用户确认，不进入执行。**

### 执行——按顺序跑

```powershell
# 先确认 <需求目录> 实际路径（默认 .opencode/work/<game_key>/<需求>）
python .opencode/lib/workspace.py where --需求 <需求>

# a) 自检 PhotoCraft 是否可用（没开会自动拉起；只在第一次/换机器时跑）
python .opencode/lib/photocraft.py --check

# b) 解析 FGUI -> 布局清单（离线，不依赖 PhotoCraft）
#    ★ 优先使用 s2 产出的 psd-spec.json：
python .opencode/skills/fgui-to-psd/scripts/_fgui_layout.py `
  --spec "<需求目录>/psd-spec.json" `
  --state-default C_ZiState=0 `
  --out "<需求目录>/_tmp/xuanzi_manifest.json"

#    （兜底手选 XML 模式，无 psd-spec 时）：
# python .opencode/skills/fgui-to-psd/scripts/_fgui_layout.py "<界面 XML>" `
#   --reuse img_zi_check.png,img_xuanzi_btn_ok.png `
#   --state-default C_ZiState=0 `
#   --out "<需求目录>/_tmp/xuanzi_manifest.json"

# c) 先空跑一遍看计划（不连 PhotoCraft，确认图层顺序/坐标/组结构没问题）
python .opencode/skills/fgui-to-psd/scripts/_pc_build.py "<需求目录>/_tmp/xuanzi_manifest.json" --dry-run

# d) 真搭 + 存 PSD（自动拉起 PhotoCraft；几百个节点会跑几分钟，别中途 kill）
python .opencode/skills/fgui-to-psd/scripts/_pc_build.py "<需求目录>/_tmp/xuanzi_manifest.json" `
  --out "<需求目录>/psd/还原稿/<界面名>_还原稿.psd"
#    -> 跑完自动：回读图层树 -> 逐层比对坐标/父级/隐藏/剪贴 -> 存 PSD

# e) 结构复验（确认写出来的确实是合法 PSD、图层没写坏）
python .opencode/skills/fgui-to-psd/scripts/_psd_struct.py "<需求目录>/psd/还原稿/<界面名>_还原稿.psd"
```

### 汇报

- **产物**：还原稿 PSD 路径（`<需求目录>/psd/还原稿/`）/ 大小 / 画布尺寸 / 图层数（含组数）
- **校验结论**：`_pc_build.py` 尾部自动打的三种结论 —— ①置入/建层有无报错 ②图层名/坐标/隐藏态是否全对
  ③黑白调整层有没有紧挨在目标组上面且已剪贴（这条最容易悄悄错，见第五节坑 5）
- **复用件清单**：哪些图层带了 `复用_` 前缀（= 这几个不用美术重新出图）
- **口径说明**：文字用的字体、relation 增量修正过哪几处（`_fgui_layout.py` 的 `deviations` 会列）
- **落点与交接**：还原稿落 `<需求目录>/psd/还原稿/`（给美术改图的源稿）。清单里 per-资源的 `psd` 字段留给 s4 `psd-style` 的**制作稿**，本步**不自动回填清单**。

## 四、脚本调用速查

脚本都在 `.opencode/skills/fgui-to-psd/scripts/`。

| 脚本 | 一句话 | 关键参数 |
|---|---|---|
| `.opencode/skills/fgui-to-psd/scripts/_fgui_layout.py` | FGUI 界面 XML → 布局清单 JSON（**离线**） | `<view.xml>`；`--assets`（给就优先，不给就从 XML 位置/当前目录向上找工程根）、`--out`、`--reuse`、`--state-default 控制器=页`、`--state 节点名=控制器:页`、`--quiet` |
| `.opencode/skills/fgui-to-psd/scripts/_pc_build.py` | 按清单在 PhotoCraft 里搭分层 PSD 并保存（自动拉起桌面端） | `<manifest.json>`、`--out <psd>`、`--port`、`--dry-run`（只打印计划）、`--no-verify` |
| `.opencode/skills/fgui-to-psd/scripts/_psd_layerinfo.py` | 列 PSD 的图层结构（复验产物） | `<psd>` |
| `.opencode/skills/fgui-to-psd/scripts/_psd_struct.py` | PSD 结构字节级自检 | `<psd>` |

- `_fgui_layout.py` 退出码 **0 = 无告警，2 = 有告警**（告警打印在 stderr）。**有告警要先解决再往下走。**
- `--dry-run` 不连 PhotoCraft，改完清单先用它确认计划。

## 五、实测经验与故障排查（都是踩过的坑）

### 1. PhotoCraft 走本机控制协议，不联网、不开浏览器
`_pc_build.py` 通过 `.opencode/lib/photocraft.py` 连 `127.0.0.1:7878`（JSON 行协议），
需要时自动拉起桌面端。不要再用 Photopea 那套"起本地页面 + 用户开浏览器"的做法。

### 2. 自动化读写根必须覆盖所有输入/输出
桌面端启动时带 `--automation-read-root` / `--automation-write-root`：
- 读根要包含 **FGUI 工程**和 **PSD 素材库**（默认 = 工作区根的上一级）；
- 写根要包含 `<需求目录>`（默认 = 工作区根）。
路径越界会被拒（`automation read ... failed`）。要换根就设 `PHOTOCRAFT_READ_ROOT` /
`PHOTOCRAFT_WRITE_ROOT`，或写 `.opencode/photocraft.json`，再重启桌面端。

### 3. 图片没有"置入"命令：app.open → 复制 → 粘贴 → 变换
`file.placeEmbedded` 之类带路径的命令在 bridge 模式被禁用，只有 `app.open` / `app.save` 是
capability-scoped。`_pc_build.py` 的口径：
`app.open(图片)` → `select.all` → `edit.copy` → 回目标文档 `edit.paste` →
`edit.transform {rect, quad}` 拉到清单矩形 → 关掉临时图片文档。
缩放后外框可能差 1px（重采样边缘），校验容差图片 1.5px、文字 3px。

### 4. PhotoCraft 不允许删到 0 个图层
`file.new` 自带一个空像素层；删它会报 `a document must keep at least one layer`。
`_pc_build.py` 把它留在最底下当垫层（不参与计划/校验，导出时隐藏）。

### 5. 黑白调整层必须**紧挨在目标组上面、且同级**，再剪贴
`layer.newAdjustmentLayer.blackWhite` 建好后 `layer.moveTo {target: 组, position: "above"}`，
再 `layer.createClippingMask`。落进组里面的话剪贴对象就变成组内最上层 → 按钮不会变灰，
但图层树看上去"有个黑白层"。`_pc_build.py` 的校验专门查 `clipped` 与相邻位置。

### 6. 文字是真文字层，字体用系统字体
`type.create` 建的是可二次编辑的文字层；PhotoCraft 直接读 Windows 系统字体，
不需要像 Photopea 那样"先加载 TTF"。本仓默认 **微软雅黑**（粗体用 `fauxBold`），
字号按 px（72dpi 下 1pt = 1px）。FGUI 的 `font=""` 推不出字体名，字体仍是确认项。

### 7. 叶子图层**重名是常态**，只有组名唯一
12 个按钮展开后会有 13 个 `icon`、13 个 `title`。所以：
- 新加的图层用命令返回的 **layer id**，**不要按名字找**；
- 只有图层组按名字找；
- 叶子重名没关系：它们在各自的组里，这正是 PSD 该有的样子。

### 8. FGUI 的几条几何口径（与渲染后端无关，别丢）
- `anchor="true"` 时 `xy` 是 **pivot 点**，不是左上角；写成左上角会整体偏半个尺寸。
- `relation` 是**增量**语义：`新值 = 设计值 + (父级新尺寸 − 父级设计尺寸) × 系数`。
- `gearDisplay` 只写 `pages` 时：命中页要**显式置 True**，否则"对勾任何状态都不显示"。

### 9. 逐层校验必须按 **(父级组, 图层名)** 配
只按名字取第一个会拿到别的按钮那一份，校验就满屏"偏 1000px"的假报错。
`_pc_build.py::verify()` 先按前序 + depth 还原父级，再用 `(父级, 名字)` 配对。

### 10. 偶发 `edit.paste` 没返回 layer
`app.open`/剪贴板偶发慢半拍时，`edit.paste` 可能回空/无 `layer` 键。
`_pc_build.py` 会把它记成"置入失败"并继续；重跑一次通常就好。批量跑时别中途 kill，
PhotoCraft 里会留下半成品文档（不影响磁盘上的 PSD）。

## 六、FGUI XML → PSD 语义对照

| FGUI | PSD |
|---|---|
| `<component size="W,H">`（根） | 画布尺寸 |
| `displayList` 里的顺序 | **从下到上**（第一个在最底）→ PSD 里新层加在最上面，按序加即得正确叠放 |
| `<group>` | 图层组 |
| `<component src=...>` 实例 | 图层组（递归展开成子层） |
| `<text>` | **真·可编辑文字层**（内容/字号/颜色/加粗） |
| `<image>` / `<loader url=...>` | 置入图片层（`ui://` 解引用到 `assets/` 真实文件） |
| `<graph type="rect" fillColor="#AARRGGBB">` | 铺满的纯色图层 + **图层不透明度 = AA/255**（本例 `#b2000000` → 黑，69.8%） |
| `visible="false"` / `gearDisplay` 未命中 | 图层**保留但设为隐藏**（美术能自己打开看） |
| `gearLook` 的 `grayed` | 给该组盖一个**黑白调整图层**（剪贴到组） |
| `ui://` 前 8 位 = 包 id、后 5 位 = 资源 id | 查该包 `package.xml` 的 `<resources>` 得到真实文件名与路径 |
| 复用件（用户指定） | 图层名前缀 `复用_` |

**已知不支持的**（`_fgui_layout.py` 会**明确告警**，不静默算错）：
`gearXY`/`gearSize`/`gearText`/`gearFontSize`/`gearAni` 等 gear；
`left-right`/`right-right`/`bottom-bottom` 等 relation 组合；
`list`/`movieclip`/`loader3D` 等节点类型。
遇到告警**先回来确认怎么处理**，别硬跑。

## 七、可选的下游（s4）

PSD 还原稿出来后，如果还要**改它的样式/文字/尺寸、并导出透明 PNG 拿回 client 工程**，**提示用户可以跑 s4**：运行 `/s4-psd <源 PSD> 要改什么`（加载 `psd-style` 技能）。**只提示，不自动做** —— 改哪个 PSD、改什么，由用户点。
