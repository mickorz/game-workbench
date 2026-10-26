# 本工程的工作规则（FairyGUI 美术流程）

> **规则层**：本文件每次会话自动加载。**详细怎么做** → `fgui文档/01-操作手册.md`；**规矩的最高优先级** → `fgui文档/00-核心流程总纲.md`；**复用手段** → `.opencode/knowledge/`（用 `knowledge.py` 现读）。
> **工作区根** = 含 `.opencode` 的那层（本工程 = `自动化流程/`）；**真实 FGUI 工程 = `client_dir`**（`assets/`+`settings/`+`*.fairy` 那层，由 s0 写进 `.opencode/workspace.json`）。**所有命令都在工作区根执行。**

## 这是什么工程

FairyGUI 工程（CocosCreator 类型，画布 1334×750，包在 `assets/<包名>/`，每个包一份 `package.xml` 资源登记）。
工作内容：把**策划需求 + 美术需求（截图）**变成 FGUI 工程里的改动，缺图走 AI 生图 / 素材库，最后**把 FGUI 工程文件交给程序**。

## 全流程 = 五步（s0~s4），一个角色从头干到尾

**s0 环境配置 → s1 解析需求 → s2 改 FGUI 工程（缺图走 AI 生图）→ 交 FGUI 工程文件给程序 → s3 出 PSD 还原稿 → s4 改样式切图回写。**
**没有"等美术出图 / 问策划确认 / 等程序回复"这种跨角色等待。**

## 硬规矩（违反＝不按流程做）

1. **复用优先（判断要看需求，不是无脑复用）**：先看需求要的**结构**能不能用现成资源顶上 —— 改大小 / 九宫拉伸(scale9grid) / 非等比拉伸(`fill="scaleFree"`) / 旋转 / 倾斜 / 镜像(`scale="-1,1"`) / 改颜色 / 改透明度 / 变灰 / 叠文字 / 用现成组件；**对得上就复用，对不上（通用件里没有该结构，如多状态卡牌）就照需求单独做**；都不行**才** AI 生图。提新图前必须**动态加载知识库**（见下面"知识库是动态的"）。
2. **美术需求（截图）为准**；与策划案文字冲突时按美术需求做，冲突记进 **s2 方案 / s1 施工单**（不默默改）。
3. **需求里已写明的不再问**（例如"要哪些标签文案"）；只有"需求没说、且会影响施工"的项才进决定清单，并且**一次问清**。
4. **运行时逻辑归程序**：什么时候显示、控制器页值怎么设 → 不写进决定清单，只写进"交付说明"。
5. **缺图＝AI 生图，且必须给全规格**：尺寸 / 透明底 / 是否九宫格 / 数量 / 命名（＝最终文件名）/ 风格参照。
6. **布局先用占位跑通，且"先保证种类是对的"**：每个待产出资源**先把"种类"定死** —— 图片 / 九宫格图 / 非等比拉伸 / **位图字体＋字形** / 组件 / 复用现成；同时把**规格定死**（最终文件名＝槽位名、尺寸、九宫格边距、字形高度、放哪个目录），再用**同规格占位**跑通（品红棋盘 `placeholder_png.py`、占位字形）。
   → 真东西到手就**同名同规格替换、不用改节点**；这张"资源种类表"**同时就是生图/出字体的方向单**（写进 `清单.json`／交付说明）。生图时机由人定，不替人排期。
7. **范围护栏**：只改需求涉及的包与组件；不碰其他包、`settings/`、工程自带脚本、业务代码；**改前先备份**到 `.opencode/work/<game_key>/<需求>/备份/`。
8. **交付物是 FGUI 工程文件**（`assets/` + `settings/` + `*.fairy` + 交付说明）；`.opencode/` 与 `fgui文档/` 是**工作层，不进交付**。
9. **只用实测事实**：节点名 / 坐标 / 资源 id / 图片尺寸一律用 `lookup.py` 或读 XML 得出，**不凭记忆**；`facts.json` 过期先重扫。

## 触发词 → 走哪条路

| 用户说 | 走法 |
|---|---|
| "新需求：…" / "按流程做…" / `/s2-fgui` | s2 FGUI 落位（**先有 s1 的清单/施工单**，没有就先跑 s1） |
| "解析需求" / "拉需求" / `/s1-req` | s1：Excel 扫描 → 解析进清单 → 出施工单 |
| "环境配置" / "定位工程" / `/s0-env` | s0：定位 client 工程（写 `workspace.json`） |
| "出 PSD 还原稿" / "还原成 PSD" / `/s3-to-psd` | s3：界面 XML → 分层 PSD 还原稿 |
| "改样式" / "切图" / "导出透明图" / `/s4-psd` | s4：读清单 → 查素材库 → 改样式 → 导出切图 → 回写 |
| "重扫工程" / "工程改过了" | `scan_fgui.py` 重扫事实底座（`.opencode/work/` 下 `facts.json` + 2 份 md） |
| "这个节点在哪 / 什么值" | `lookup.py` 查（**不要重扫**） |
| "要不要出新图" / "要不要新建组件" | 先动态加载知识库 → 过复用决策顺序（7 级）；**第 5 级＝通用件**：先看工程现成的通用控件能不能直接顶上（`knowledge.py --topic 通用件`）。**能不能复用要看需求本身**——结构与需求对得上（比如普通按钮＝底图+文字）就复用；需求要的东西通用件里没有（比如**多状态卡牌 / 要按状态换图换色、带状态显隐的控件**），就照需求单独建，不要硬套 |

## 知识库是动态的（重要）

`.opencode/knowledge/*.md` **会持续更新**（新手法、新坑、新用例随时补）。所以：

- **不许凭记忆引用知识库、更不许把它的内容抄进技能或方案**；要用时**现读**：
  ```powershell
  python .opencode/skills/fgui-flow/scripts/knowledge.py --list            # 索引（文件 + 标题树）★主题词从这来
  python .opencode/skills/fgui-flow/scripts/knowledge.py --topic 复用 --topic 九宫格   # 例子，不是全集
  python .opencode/skills/fgui-flow/scripts/knowledge.py --topic 对齐 --topic 留白     # 例子，不是全集
  python .opencode/skills/fgui-flow/scripts/knowledge.py --path 复用技巧   # 整份文件
  ```
- 涉及"这个效果该用哪种手法""要不要出新图"之前，**先跑一次 `--topic`**。
- **别只查"换图"那条线**：知识库还管**排版**（对齐 / 成组 / 留白 / 间距 / 居中 / 锚点）。
  **改坐标 / 排位置 / 定间距之前，也要先跑一次排版类 `--topic`**，别凭手感摆。
- 上面的 `--topic` 只是例子：**主题词以当次 `--list` 索引里的标题词为准**（索引会自动列出可检索的小节）——
  知识库随时会多出新文件，照例子抄就会漏。
- 知识库**唯一一份** = `.opencode/knowledge/`（`knowledge.py` 只读这里；找不到会退回本包快照，不报错）。

## 目录地图

```
<工作区根>/                     ← 含 .opencode 的那层（本工程 = 自动化流程/）；所有命令在这里跑
├─ .opencode/                   ← 【自包含、可整包拷走】
│  ├─ xc_spce_info.json         ← 程序配置：client_code_root / game_id / game_key
│  ├─ workspace.json            ← 工程级配置：client_dir / out_root / 素材库根 / 快照范围（s0 写）
│  ├─ inbox/                    ← 用户放入 Excel 需求文件，s1 自动扫描处理
│  ├─ lib/                      ← 共享库（workspace.py 等，≥2 技能共用）
│  ├─ agent/ command/ skills/   ← 流程本体（命令 s0-env / s1-req / s2-fgui / s3-to-psd / s4-psd）
│  ├─ knowledge/                ← 知识库（唯一一份）
│  └─ work/                     ← 工作层：事实底座（facts.json/工程结构.md/美术资源清单.md）+ <game_key>/<需求>/
├─ .xflow/.../<game_id>/        ← client 工程（client_dir）：assets/ + settings/ + *.fairy（交付本体）
└─ fgui文档/                    ← 人类文档（不进 .opencode、不进交付）：00-核心流程总纲 / 01-操作手册 / 使用文档 / 计划
```

一次需求的产物都在 `.opencode/work/<game_key>/<需求>/`：`需求.md`、`参考图/`、`参考图_1334x750/`、`清单.json`、`清单.md`、`施工单.md`、`方案.md`、`校验报告.md`、`修改清单.md`、`备份/`、`占位/`、`psd/`、`切图/`、`_tmp/`、`FGUI/`（快照）。

## 常用命令

```powershell
# 工作区 / 工程定位（s0）
python .opencode/lib/workspace.py where [--需求 X]                 # 工作区根 / client_dir / out_root / game_key
python .opencode/lib/workspace.py env --check                      # 定位 client 工程（无 .xflow 时用 --client 指定）

# s1 需求链
python .opencode/skills/fgui-req/scripts/excel_to_req.py <excel>          # Excel → 每行一个独立需求目录
python .opencode/skills/fgui-req/scripts/check_terms.py "<需求目录>/需求.md"      # 错别字/矛盾（退出码 4＝有待确认项）
python .opencode/skills/fgui-req/scripts/parse_requirement.py "<需求目录>/需求.md" # 一行一需求 → 清单.json
python .opencode/skills/fgui-req/scripts/refimage_to_canvas.py --out "<需求目录>"  # 参考图 → 1334x750
python .opencode/skills/fgui-req/scripts/build_guide.py "<需求目录>/需求.md"       # 出施工单骨架

# s2 事实底座 / 定位 / 占位 / 快照 / PSD衔接
python .opencode/skills/fgui-flow/scripts/scan_fgui.py                              # 重扫事实底座 → .opencode/work/
python .opencode/skills/fgui-flow/scripts/lookup.py <关键词> [--comp X --nodes]     # 定位节点/资源（--check 看新鲜度）
python .opencode/skills/fgui-flow/scripts/knowledge.py --list                      # 加载知识库（索引）
python .opencode/skills/fgui-flow/scripts/placeholder_png.py --size 96,33 --out <路径> --label TAG
python .opencode/skills/fgui-flow/scripts/generate_psd_spec.py <需求> [--view X]   # 落位定稿后导出 psd-spec.json
python .opencode/lib/workspace.py snapshot <需求> [--packages a,b]                 # 建工程快照 → <需求>/FGUI/

# s3 PSD还原（自动消费 psd-spec.json + 遵照 psd-art-spec.md 规范）
python .opencode/skills/fgui-to-psd/scripts/_fgui_layout.py --spec "<需求目录>/psd-spec.json" --out "<需求目录>/_tmp/manifest.json"

# 清单 / 素材库 / 回写（三技能交接棒）
python .opencode/lib/workspace.py manifest-init <需求>
python .opencode/lib/workspace.py manifest-add <需求> --槽位名 assets/<包>/atlas/img_x.png --种类 图片 --尺寸 96x33 --来源 AI生图
python .opencode/lib/workspace.py manifest-md <需求>
python .opencode/lib/workspace.py find-asset <需求>                                 # 查 PSD 素材库（空→占位）
python .opencode/lib/workspace.py place <需求>                                      # 定稿：切图同名回写 快照 + client 工程
python .opencode/skills/psd-style/scripts/build_index.py --lib <素材库根> --write    # 刷新素材库 index.json（半自动）
```

## 工作层 `.opencode/work/`（不进交付）

产物（清单 / 工程快照 / PSD / 切图 / 占位 / 事实底座）都落**工作区根下的 `.opencode/work/`**（`out_root`，配 `.opencode/workspace.json`）。

- **事实底座**（project 级）：`.opencode/work/facts.json` + `工程结构.md` + `美术资源清单.md`（扫描产物，别手改）；中文说明来源 = `.opencode/work/美术清单.备注.txt`（手填 `<关键词> = <说明>`）。
- **需求产物**：`.opencode/work/<game_key>/<需求>/`（见上"目录地图"）。
- **三技能交接棒** = 清单 `<需求>/清单.json`（s1 生成、s2/s4 回填；`清单.md` 由它生成）。
- **素材库**：`.opencode/PSD素材库` 归纳可复用源 PSD + `index.json`；支持最外层制作单元与嵌套底图组结构，各分类自带 `_预览/`；组用 **`lyid`** 定位（组名可重复）；`build_index.py --write --preview` 生成索引及分类预览图。
- `.opencode/`、`.opencode/work/`、`fgui文档/` 都是**工作层，不进交付**；交付物 = client 工程的 `assets/` + `settings/` + `*.fairy` + 交付说明。
- 设计/口径见 `fgui文档/计划/08-流程细分与s0环境配置.md`；逐条任务见 `fgui文档/计划/09-流程细分实现任务清单.md`。
