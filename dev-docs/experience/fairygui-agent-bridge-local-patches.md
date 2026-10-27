# fairygui-agent-bridge 本地补丁与探活踩坑（编辑器 6.1.4）

## 问题现象

探活过程中依次遇到四个问题，全部定位并解决：

1. **桥挂起**：编辑器打开、日志显示 `listening on http://localhost:7531/`，但 curl 请求 TCP 能连上（netstat 显示 ESTABLISHED→CLOSE_WAIT）且永不返回。
2. **补丁后插件完全不加载**：改完 main.js 重启编辑器，插件无声消失（无日志、无监听端口）。
3. **`list_items` 递归崩溃**：`Cannot read properties of null (reading 'Count')`，任何 depth>1 的遍历都炸。
4. **`set_property` 的 `size` 不生效**：返回 `applied:["size:ext"]`，save_all 后 XML 里还是旧值。

## 排查过程

1. 用 `netstat -ano | grep 7531` 确认：监听在 `[::1]:7531`（IPv6 回环），连接能建立但服务端不处理 → 请求进了 `Bridge.queue` 但 `stepQueue` 没人调用 → `App.add_onUpdate` 回调没跑。
2. 给 main.js 打补丁时误用了 **Lua 冒号语法** `CS.FairyGUI.Timers.inst:Add(...)`——该插件是 Jint JS，必须点号 `.Add`。语法错误导致整个 main.js 解析失败、插件静默不加载。**先 `node --check main.js` 再重启编辑器**，能提前拦住这类错。
3. 读 main.js 的 `itemInfo`：`var ch = item.children; for (i < ch.Count)` —— 空目录的 `children` 是 null，真实工程（88 包、含大量空目录）必崩。
4. 对比上游 README（声称 `size:"w,h"` 自动拆分）与实测：落到 ext 扩展属性通道，不写 XML。

## 根因

1. 桥挂起根因未最终定位（怀疑该编辑器构建里 `add_onUpdate` 在特定启动时序下不回调）；重启编辑器后 `add_onUpdate` 正常，日志报 `pump via App.add_onUpdate OK`。兜底方案已固化。
2. 语法错误 = 插件静默死（编辑器不报错框，bridge.log 也不会有记录——日志函数本身在死文件里）。
3/4. 上游 bug / 上游文档与实现不符。

## 解决方案（已打进 dev-examples 工程内的插件副本）

- 补丁 1（必带）：`itemInfo` 里 `if (ch == null) return o;` 空目录判空。
- 补丁 2（保险）：`boot()` 同时注册 `App.add_onUpdate` 与 `CS.FairyGUI.Timers.inst.Add(0.1, 0, onUpdate)` 双泵，带一次性心跳日志（谁先回调报谁名）。
- 规范：改组件尺寸用 `props:{width, height}`，不用 `size` 字符串；改完必须 `save_all` 才落盘。

## 追加（P1 期间复现并根治）

桥挂起问题在 P1 复现：编辑器长时间空闲后 onUpdate 停跑（TCP 通、命令不执行），重启即恢复。
根因与 FairyGUI-MCP 注释一致：`runInBackground` 被编辑器反复覆盖，agent-bridge 只在 boot 时设一次。
**补丁 3（根治）**：`onUpdate()` 每帧重设 `CS.UnityEngine.Application.runInBackground = true`。已打进
`plugins/fairygui/editor-plugin/main.js` 与 dev-examples 工程副本，重启后未再复现。

## 追加（P3：宿主 CSP 挡住渲染层探活）

工作室首页桥状态角标首版轮询 `http://localhost:7531/` 永远「未连接」，浏览器 console 报
CSP 违规：宿主 `connect-src` 只放行 `http://127.0.0.1:*`；且桥的 HttpListener 用 `localhost`
前缀时仅绑 IPv6 `[::1]`，`127.0.0.1` 直连被拒。双重原因导致渲染层永远连不上。

**补丁 4**：`startServer()` 在同一 listener 上补加 `http://127.0.0.1:<port>/` 前缀
（实测免管理员可用，失败则记日志降级）；渲染层探活固定用 `127.0.0.1`。

## 预防 / 注意事项

- 改插件 JS 后必跑 `node --check main.js`；**别用 Lua 冒号语法**。
- 编辑器侧排障三板斧：`tasklist | grep FairyGUI` 看进程、`netstat -ano | grep 7531` 看监听/连接状态、`tail plugins/agent-bridge/bridge.log` 看日志。
- 监听只绑 IPv6 `[::1]`，`127.0.0.1` 连不上是正常的，用 `localhost`。
- `screenshot` 在 6.1.4 被 Unity 裁剪（`ScreenCapture` 不可用，且 truthy 但不可调用），退路 OS 级截屏；`open_doc` 反而可用（上游作者构建里被裁）——**构建差异大，每条命令都要实测**。
