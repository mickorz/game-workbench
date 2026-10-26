# FairyGUI 工作室 P0 探活记录

日期：2026-10-26 | 编辑器：FairyGUI-Editor 6.1.4（`D:\FairyGUI-Editor_6.1.4`）| 测试工程：`dev-examples/fairygui-test-project`（`mini.fairy`，CocosCreator 型，88 包）

## 结论总表

| 命令 | 结果 | 说明 |
|---|---|---|
| `ping` / `project_info` | 可用 | 返回版本/端口/工程路径/工程名 |
| `list_packages` | 可用 | 88 包全列出（id/name/basePath） |
| `list_items` | **可用（打补丁后）** | 上游 bug：空目录 `children` 为 null 导致递归崩溃，加判空补丁修复 |
| `read_component` | 可用 | 直接读盘 XML，与工程文件一致 |
| `open_doc` | **可用** | 与上游作者的构建不同，6.1.4 里 `OpenDocument` 正常（返回 opened/url）——**截图验收链路可以走「打开组件→截屏」** |
| `screenshot` | **不可用** | `ScreenCapture` 系列在此构建被 Unity 裁掉；退路 = OS 级窗口截屏（PowerShell CopyFromScreen） |
| `create_component` | 可用 | 返回 id/url/file/openable，package.xml 自动登记 |
| `set_property` | **可用（有坑）** | `width`/`height` 分开写生效；`size:"x,y"` 字符串落到 ext 通道**不落盘**（上游 README 声称支持，实际不行） |
| `save_all` | 可用 | set_property 后必须 save_all，否则 read_component（读盘）看不到 |
| `delete_item` | 可用 | 往返干净，组件从资源树消失 |

## 对插件设计的最终影响

1. **P3 截图验收可做**：`open_doc` 可用 + OS 级截屏（`ScreenCapture` 不可用），Skill 里写「打开组件 → PowerShell 截编辑器窗口 → 给人看」。
2. **收编 plugin/main.js 时带上两个本地补丁**（详见 `dev-docs/experience/fairygui-agent-bridge-local-patches.md`）：
   - `list_items` 空目录判空（否则遍历必崩，真实工程全是空目录）；
   - Timers 兜底泵 + 心跳日志（本次探活中发现编辑器重开后 `add_onUpdate` 即正常，兜底保留以防万一）。
3. **Skill 规范补两条**：改尺寸用 `width`/`height` 不用 `size`；写后 `save_all`。

## 遗留

- 首次启动时桥曾出现「TCP 通、命令不执行」的挂起（编辑器旧进程），重启编辑器后未复现；Timers 兜底泵即为保险。若再复现按经验文档排查。
