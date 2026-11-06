---
name: browser-selftest
version: 1.0.0
display_name: 浏览器实机自测
display_name_en: Browser Self-Testing
description: >
  Use browser automation (pi-browser-use / chrome-devtools-mcp tools) to do
  end-to-end self-testing of the xc-ui-flow app during development: start the
  daemon and renderer, navigate the hash router, snapshot and click UI,
  run scripted assertions, archive screenshots. Use when a change touches UI
  (sidebar, workspace, studio home, dialogs) or daemon API and needs real-browser
  verification, or when reinstalling/configuring pi-browser-use on a machine.
description_zh: >-
  用浏览器自动化（pi-browser-use / chrome-devtools-mcp 工具）对 xc-ui-flow 应用做端到端
  实机自测：起 daemon 与 renderer、hash 路由导航、快照与点击 UI、脚本化断言、截图存档。
  适用场景：改动触及 UI（侧边栏、工作区、工作室首页、对话框）或 daemon API 需要真实
  浏览器验证时；或首次在新机器上安装配置 pi-browser-use。
description_en: >-
  Use browser automation (pi-browser-use / chrome-devtools-mcp tools) to do
  end-to-end self-testing of the xc-ui-flow app during development: start the
  daemon and renderer, navigate the hash router, snapshot and click UI,
  run scripted assertions, archive screenshots. Use when a change touches UI
  (sidebar, workspace, studio home, dialogs) or daemon API and needs real-browser
  verification, or when reinstalling/configuring pi-browser-use on a machine.
---

# 浏览器实机自测（browser-selftest）

对 xc-ui-flow 做真实浏览器端到端自测：起服务 → 导航 → 快照拿 uid → 交互 →
脚本断言 → 截图存档 → 精确停服务。承接 egret-exml-html-renderer 的 browser-selftest
模式，适配本仓库双服务与 hash 路由。

## 边界

- 只做端到端实机验证（真实浏览器行为）；单元/回归断言由 `bun run test`（vitest）负责，互不替代
- **实机收尾是硬性要求**：typecheck / vitest 过 ≠ 渲染对（案例：工作区分支 JSX 插进既有
  JSX 标签内部，编译合法、渲染逻辑错）。触及 UI 的改动必须本技能实测收尾
- CLI 优先：能用 curl / daemon API 验证的（建项目、健康检查）不驱动浏览器
- 只操作本地服务；遇到登录墙让用户手动过一次，不要重试循环

## 一、安装与配置（每台机器一次性）

```bash
pi install npm:pi-browser-use
```

默认 `persistent` 模式（自持 headless Chrome，profile 在 `~/.pi/browser-profile`）。
验证安装：`pi mcp list` 出现浏览器 server 且 connected。首次异常先 `browser_doctor`
自诊断（不碰页面）。需要登录态的站点：`browser_setup` 有头窗口人工登录一次。

## 二、自测工作流（日常）

### 1. 起服务并探活

双服务：daemon（API，43110）+ renderer（vite，43120，热更新）。
没起就起；**改了 daemon 侧代码（含 shared/contracts.ts）必须重启 daemon**——
`dev:daemon` 是 tsx watch 但对个别变化不敏感，手动重启最保险：

```bash
curl -s -m 3 http://127.0.0.1:43110/health         # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:43120/   # 200
# 重启 daemon（只杀监听 PID，严禁 taskkill //F //IM node.exe 全杀）：
netstat -ano | grep ":43110" | grep LISTENING      # 拿 PID
taskkill //F //PID <pid>
(bun run dev:daemon > dev-examples/daemon.log 2>&1 &)
# 轮询 /health 到 ok
```

### 2. 造测试数据（API 优先，不用 UI）

```bash
# 中文 body 必须用文件传（curl 直传 Content-Length 不匹配）：
printf '{"name":"自测-xx","type":"<type>"}' > /tmp/proj.json
curl -s -X POST http://127.0.0.1:43110/projects --data-binary @/tmp/proj.json -H "Content-Type: application/json"
# 测完清理：
curl -s -X DELETE http://127.0.0.1:43110/projects/<id> -o /dev/null -w "%{http_code}"   # 204
```

### 3. 导航（hash 路由，注意启动恢复劫持）

```text
chrome_devtools_new_page { url: "http://127.0.0.1:43120/#/<page>" }
```

**坑：应用启动会恢复上次会话**——直接开目标 hash 或整页导航会触发 reload，
被拉回上次的项目会话页，误判为路由解析失败。正确做法：等应用加载完后用
hashchange 切换（不触发 reload）：

```js
// chrome_devtools_evaluate_script（async 平铺写法，嵌套 Promise 回调易报语法错）：
async () => {
  location.hash = "#/<page>";
  await new Promise(r => setTimeout(r, 800));
  return JSON.stringify({ hash: location.hash, headings: [...document.querySelectorAll("h1,h2,h3")].map(h => h.textContent.trim()) });
}
```

### 4. 快照与交互

```text
chrome_devtools_take_snapshot    # a11y 树拿 uid（页面重渲染后 uid 失效，操作前重拍）
chrome_devtools_click / fill     # 用 uid 交互
```

### 5. 断言（三种，按需组合）

1. **脚本断言（首选）**：`evaluate_script` 返回结构化 JSON——computed style、
   innerText 片段、元素存在性。模型不支持读图时的唯一可靠断言
2. 快照/`wait_for` 文本：期望文案出现
3. 截图文件大小：纯空白页几百字节，有内容通常 >10KB

断言要点：分支接线类改动必须同时测「目标命中」与「回归无泄漏」
（案例：页面 innerText 里 grep `project.type`——泄漏即接线插错位置）。

### 6. 截图存档

```text
chrome_devtools_take_screenshot { filePath: "dev-examples/<主题>-shots/01-场景.png", format: "png" }
```

约定：存 `dev-examples/`（沙盒目录，gitignore 不进 git），文件名带序号与场景。
**截图前先刷新页面**——tsx watch 重启后浏览器仍持有旧 HTML。

### 7. 看图验证（模型不能直接看截图时）

```text
chrome_devtools_take_screenshot { filePath: "dev-examples/xx.png" }
→ zai_mcp_server_analyze_image { image_source: "dev-examples/xx.png", prompt: "具体视觉断言提问" }
```

或 `browser_save_artifact` 存文件后同样传路径给 analyze_image。提问要具体
（「九宫格中心是否填充」「侧边栏图标是否为剪贴板形状」），不要泛泛「看看对不对」。

### 8. 结束：清理与停服务

删测试项目（DELETE API）→ 关自己开的浏览器页（`close_page`）→
按需停服务（netstat 找 PID + `taskkill //F //PID <pid>`，只杀目标进程）。

## 三、常见坑

| 症状 | 原因 | 处理 |
|---|---|---|
| 导航后 URL 变成上次的项目会话 | 启动恢复逻辑劫持 | 加载完后用 hashchange 切换，不整页导航 |
| uid 失效 / stale element | 快照后页面重渲染 | 重新 take_snapshot |
| 模型不支持读图 | 模型能力限制 | evaluate_script 程序化断言 + analyze_image 看图链路 |
| 页面行为是旧代码 | 改码后服务没重启 / 浏览器持旧 HTML | daemon 手动重启；renderer 截图前刷新页面 |
| 中文 API body 报错 | curl 直传 Content-Length 不匹配 | `--data-binary @file` |
| evaluate_script 报语法错 | 嵌套 Promise 回调 + 复杂字面量 | async 平铺写法 |
| 浏览器工具报 profile already in use | 两个会话共享同一 profile | `fresh` 模式或各开 isolated context |

## 四、验证完成标准

实机自测完成 = 双服务探活 ok + 目标页面可达且命中（脚本断言返回值）+
回归断言无泄漏 + 截图存档 + 测试数据清理 + 自开的浏览器页关闭。
