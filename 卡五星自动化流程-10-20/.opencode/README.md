# FGUI 美术流程 · opencode 版（使用说明）

> **完整文档中心：`docs/README.md`**
> 安装 / 命令 / 技能 / 知识库 / PhotoCraft MCP / 打包迁移 / 常见问题都在那里。本文只保留最短上手说明。

把"策划需求 + 美术需求（截图）"变成 FGUI 工程改动的整套流程。这套东西是 **opencode 的 agent + command + skill** 三件套，**自包含、可整包拷走**，装一次就能在任意 FGUI 工程里用。

> 交付/迁移时注意：`.opencode` 必须和**工作区根的 `AGENTS.md`**、**`docs/`** 一起带走；只拷 `.opencode` 会缺少会话级硬规矩与使用文档。打包脚本见 `docs/tools/pack_release.ps1`。

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/01-总览与架构.md` | 流程、目录结构、核心规矩 |
| `docs/02-安装与首次配置.md` | 前置软件、s0 定位、首次自检 |
| `docs/03-命令手册.md` | `/s0-env` ~ `/s4-psd` 输入/产物/闸门 |
| `docs/04-技能与脚本参考.md` | 5 个技能、共享库、脚本清单 |
| `docs/05-知识库与素材库.md` | 事实底座、动态知识库、PSD 素材库 |
| `docs/06-PhotoCraft与MCP配置.md` | 桌面端、控制端口、token、opencode MCP |
| `docs/07-打包与迁移.md` | 该带什么/该清什么、打包脚本、验收清单 |
| `docs/08-常见问题.md` | 命令、定位、PhotoCraft/MCP、路径编码 |

## 一、装在哪 / 怎么起

这套 `.opencode\` 要能跑起来，必须满足：**你在「含 `.opencode` 的那层（= 工作区根）」启动 opencode。**

```
<工作区根>\                    ← 含 .opencode 的那层；所有命令在这里跑
├─ AGENTS.md                  ← 会话硬规矩
├─ docs\                      ← 说明与使用文档中心
├─ .opencode\                 ← 把本文件夹放在这
│  ├─ xc_spce_info.json       ← 程序配置：client_code_root / game_id / game_key
│  ├─ workspace.json          ← client_dir / out_root / 素材库根（s0 写）
│  ├─ photocraft.example.json ← PhotoCraft 客户端配置模板
│  ├─ lib\  agent\  command\  skills\  knowledge\
│  ├─ PSD素材库\               ← 可选：可复用 PSD + index.json
│  └─ work\                   ← 工作层：事实底座 + <game_key>\<需求>\
└─ .xflow\...\<game_id>\       ← client 工程（client_dir）：assets\ + settings\ + *.fairy
```

- **真实 FGUI 工程不在工作区根必然的位置**：由 s0 读 `xc_spce_info.json` 定位，写进 `workspace.json` 的 `client_dir`；之后脚本都靠它找工程。
- **配置类文件改动要重启 opencode 才生效。**

前提：**Python 3.10+** 在 PATH 里（多数脚本只用标准库）；Windows PowerShell；s3/s4 要装 **PhotoCraft 桌面端**（控制协议自动拉起，不需要浏览器/联网/Node.js）。第一次跑 `python .opencode/lib/photocraft.py --check`。

## 二、怎么触发（五步命令 s0~s4）

| 命令 | 技能 | 干什么 |
|---|---|---|
| `/s0-env` | `fgui-env` | 定位 client 工程（写 `workspace.json`） |
| `/s1-req` | `fgui-req` | 扫描 `inbox/` 的 Excel / 手工兜底 → 解析进清单 → 出施工单 |
| `/s2-fgui` | `fgui-flow` | 消费 s1 的清单/施工单 → 改 client 工程（占位、方案、快照、交付） |
| `/s3-to-psd` | `fgui-to-psd` | 界面 XML → 分层 PSD 还原稿 |
| `/s4-psd` | `psd-style` | 读清单 → 查素材库 → 改样式 → 导出切图 → 回写 |

也可以自然语言："环境配置""解析需求""按流程做""出 PSD 还原稿""改样式切图" —— agent 按 `AGENTS.md` 触发词表自动对号。

命令只是"把技能说明书塞进来"，**不等于立刻改工程** —— s2 方案连贯进入落位，改完工程由**单一闸门（效果确认）**把关。

## 三、流程（s0~s4 + 单一闸门）

```
s0 环境配置   env --check 定位 client 工程 → 写 workspace.json
s1 解析需求   Excel扫描(inbox) → 每行独立目录 → 解析进 清单.json → 施工单
s2 FGUI 落位  备事实底座 → 出方案 → 定种类/占位/清单 → 落位执行 🔒单一闸门(人看效果) → 补文档 + psd-spec.json → 交程序 + 快照
s3 PSD 还原   消费 psd-spec.json + 规范知识库 → 结构化分层 PSD 还原稿
s4 改样式切图 读清单 → 查素材库 → 改样式 → 导出透明 PNG → place 回写 client 工程
```

**文档时机（省时间的关键）**：单一闸门通过、效果定稿**之前，只改工程文件，不写校验报告/修改清单/交付说明/psd-spec.json**；人点头后再一次性补齐。

## 四、为什么换工程 / 换机器不会报错

- **工作区根基准**：相对路径都以**含 `.opencode` 的那层**解析；**`out_root` 默认 `.opencode\work`**。
- **client 定位**：`workspace.py` 读 `workspace.json` 的 `client_dir`（s0 写），缺则退回"向上找 `*.fairy` + `assets/`"；也可显式 `env --client <路径>`。
- **知识库唯一一份** = `.opencode/knowledge/`（`knowledge.py` 只读这里；找不到会退回本包快照，不报错）。
- **素材库没有也能跑**：`find-asset` 未命中就全走占位，不报错。
- **换机**：把 `.opencode/` 整包拷走，只改 `workspace.json` 路径（或跑 `/s0-env`）。

## 五、脚本清单（按技能分）

| 位置 | 脚本 | 干什么 |
|---|---|---|
| `.opencode/lib/` | `workspace.py` / `photocraft.py` | 工作区/client 定位、快照、清单、素材库、回写；PhotoCraft 控制协议客户端 |
| `.opencode/skills/fgui-env/` | （无独立脚本） | s0 定位用共享库 `.opencode/lib/workspace.py` |
| `.opencode/skills/fgui-req/scripts/` | `excel_to_req.py` / `check_terms.py` / `parse_requirement.py` / `refimage_to_canvas.py` / `build_guide.py` | s1 需求链 |
| `.opencode/skills/fgui-flow/scripts/` | `scan_fgui.py` / `lookup.py` / `knowledge.py` / `placeholder_png.py` | s2 事实底座 / 定位 / 知识库 / 占位 |
| `.opencode/skills/fgui-to-psd/scripts/` | `_fgui_layout.py` / `_pc_build.py` / `_psd_*` | s3 布局解析 / 在 PhotoCraft 里搭 PSD |
| `.opencode/skills/psd-style/scripts/` | `_psd_*` / `_apply_asl.py` / `_pc_export.py` / `_fit_frames.py` / `build_index.py` | s4 改样式 / 导出 / 素材库索引 |

## 六、常见问题

- **命令敲不出来** → `.opencode\` 不在启动目录能向上找到的位置；或**没重启** opencode。
- **脚本说找不到工作区根** → 要在**含 `.opencode` 的那层**跑。
- **`/s0-env` 报 client_code_root 不存在** → 本机没有 `.xflow` → 用 `env --client <真实工程目录>` 显式指定。
- **`lookup.py --check` 报过期** → 工程改过了，跑一次 `scan_fgui.py` 重扫即可。
- **素材库未配置/为空** → 正常降级：全部走占位。要启用就配 `workspace.json` 的 `素材库根` 并建 `index.json`。
- **中文路径/输出乱码** → 脚本已 `reconfigure(utf-8)`；控制台显示乱码用编辑器看即可（文件本身没问题）。
