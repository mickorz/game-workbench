---
name: fairygui-ui
description: Create, inspect, edit, and publish FairyGUI UI components through the editor bridge, following FairyGUI authoring standards.
---

# FairyGUI UI

## 环境准备（一次性）

1. 桥不通时先装编辑器侧插件：`scripts/install.bat <UI 工程路径>`（把 `editor-plugin/` 复制到 `<工程>/plugins/agent-bridge/`）。
2. 拉起并确认就绪：`node mcp/fgui.mjs ensure '{"project":"<UI 工程绝对路径>"}'`；ping 通才继续。
3. 编辑器可最小化（桥已设 runInBackground）；多窗口时所有工具必须显式传 project 参数，避免操作错窗口。

## 制作循环

list_items 找素材 → read_component 拿子对象命名 → create_component / insert_object / set_property 摆 UI → save_all → lint → publish 出包 → 游戏侧加载验证。

组件改动一律走 MCP 工具（官方 API、可撤销），禁止手改组件 XML 与 package.xml。

实测要点（编辑器 6.1.4 验证）：

- 改尺寸用 props 里的 `width`/`height`（`size` 字符串落到 ext 通道不落盘）；
- 任何写操作后必须 `save_all`，再用 `read_component`（直接读盘）验证；
- `screenshot` 命令在部分构建被 Unity 裁剪，报错时改用 OS 级窗口截屏。

## 规范红线（违反会打不开组件或运行时事故）

- displayList 只有 10 种标签：image/graph/loader/loader3D/text/richtext/list/component/jta/group。
- extention 合法值 8 种：Button/Label/ComboBox/ProgressBar/Slider/ScrollBar/List/Tree；拼写就是 extention。
- 输入框是 text + input="true"；复选/单选是 Button mode="Check/Radio"；动画是 jta。
- 单组件 ≤ 80 个显示对象；动态重复结构用 list + defaultItem，禁止平铺 N 份。
- 颜色用 6 位 #RRGGBB + alpha="0.x"（8 位色运行时只取后 6 位）。
- 九宫格、GLoader fill、relation、controller+Gear、GList、ScrollPane、GGraph、grayed 等引擎内置能力禁手搓；九宫格先确认图能切（胶囊/圆/放射纹理禁切）。
- 子对象用语义名（btnHome/capText），扩展件遵守内置名约定（Button 的 title/icon）。

## 验证

发布前必跑：`node scripts/lint_components.mjs <工程根>`。
截图给人看：先 `open_doc` 打开目标组件，再跑
`powershell -ExecutionPolicy Bypass -File scripts/capture_editor.ps1 -OutPath "<输出.png>"`
（编辑器内置 ScreenCapture 在部分构建被裁，此脚本为 OS 级兜底，会自动激活编辑器窗口）。
发布完成后核对产物（`_fui.bytes` / 图集）在工程发布目录且 mtime 更新。
