---
name: browser-selftest
version: 2.0.0
display_name: 浏览器实机自测
display_name_en: Browser Self-Testing
description: >
  Use chrome-use CLI to do end-to-end self-testing of the xc-ui-flow app during
  development: start the daemon and renderer, open pages in the user's real
  Chrome, snapshot refs and click UI, run assertions, archive screenshots.
  Use when a change touches UI (sidebar, workspace, studio home, dialogs) or
  daemon API and needs real-browser verification, or when first installing or
  configuring chrome-use on a machine.
description_zh: >-
  用 chrome-use CLI 对 xc-ui-flow 应用做端到端实机自测：起 daemon 与 renderer、
  在用户真实 Chrome 里开页面、快照拿 refs 并点击 UI、断言、截图存档。
  适用场景：改动触及 UI（侧边栏、工作区、工作室首页、对话框）或 daemon API 需要
  真实浏览器验证时；或首次在新机器上安装配置 chrome-use。
description_en: >-
  Use chrome-use CLI to do end-to-end self-testing of the xc-ui-flow app during
  development: start the daemon and renderer, open pages in the user's real
  Chrome, snapshot refs and click UI, run assertions, archive screenshots.
  Use when a change touches UI (sidebar, workspace, studio home, dialogs) or
  daemon API and needs real-browser verification, or when first installing or
  configuring chrome-use on a machine.
---

# 浏览器实机自测（browser-selftest）

用 **chrome-use CLI**（驱动用户真实 Chrome）对 xc-ui-flow 做端到端实机自测：
起服务 → open → snapshot 拿 refs → click --observe → 断言 → 截图存档 → done 收尾。
不使用 chrome-devtools-mcp / pi-browser-use 的 MCP 工具面；本仓库统一走 chrome-use。

## 边界

- 只做端到端实机验证（真实浏览器行为）；单元/回归断言由 `bun run test`（vitest）负责，互不替代
- **实机收尾是硬性要求**：typecheck / vitest 过 ≠ 渲染对（案例：工作区分支 JSX 插进既有
  JSX 标签内部，编译合法、渲染逻辑错）。触及 UI 的改动必须本技能实测收尾
- CLI 优先：能用 curl / daemon API 验证的（建项目、健康检查、数据清理）不驱动浏览器
- 用 `chrome-use skills get core` 加载一次用法指南再动手（CLI 自带规则，命令报错时其
  最后一行说下一步做什么，照做，不要 pipe tail / 丢 stderr）

## 一、安装与配置（每台机器一次性）

```powershell
irm https://raw.githubusercontent.com/leeguooooo/chrome-use/main/install.ps1 | iex
```

验证安装：`chrome-use status`（native host live + extension relay up）。
异常先 `chrome-use status` / `chrome-use tab list` 自诊断。

## 二、自测工作流（日常）

### 1. 起服务并探活（curl，不驱动浏览器）

双服务：daemon（API，43110）+ renderer（vite，43120，热更新）。
**改了 daemon 侧代码（含 shared/contracts.ts）必须重启 daemon**——
`dev:daemon` 是 tsx watch 但对个别变化不敏感，手动重启最保险：

```bash
curl -s -m 3 http://127.0.0.1:43110/health         # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:43120/   # 200
# 重启 daemon（只杀监听 PID，严禁 taskkill //F //IM node.exe 全杀）：
netstat -ano | grep ":43110" | grep LISTENING      # 拿 PID
taskkill //F //PID <pid>
(bun run dev:daemon > dev-examples/daemon.log 2>&1 &)
```

### 2. 造测试数据（API 优先）

```bash
# 中文 body 必须用文件传（curl 直传 Content-Length 不匹配）：
printf '{"name":"自测-xx","type":"<type>"}' > /tmp/proj.json
curl -s -X POST http://127.0.0.1:43110/projects --data-binary @/tmp/proj.json -H "Content-Type: application/json"
# 测完清理：
curl -s -X DELETE http://127.0.0.1:43110/projects/<id> -o /dev/null -w "%{http_code}"   # 204
```

### 3. 打开页面（注意启动恢复劫持）

```bash
chrome-use open "http://127.0.0.1:43120/#/<page>"
```

**坑：应用启动会恢复上次会话**——整页加载时可能被拉回上次的项目会话页，
误判为路由解析失败。打开后先 `chrome-use get url` 确认落在目标页；
被劫持则加载完后改 hash（不触发 reload）：

```bash
chrome-use eval "location.hash = '#/<page>'"
chrome-use wait --text "<目标标题文案>"
```

### 4. 快照与交互（核心循环）

```bash
chrome-use snapshot -i -c          # 紧凑快照拿 @eN refs
chrome-use click @eN --observe     # 点击 + 自动观察（fill/select/press/hover 同样支持 --observe）
```

- refs 从最新快照复制，**不要猜编号**；页面替换后 refs 重置（--observe 会给出新快照）
- `--observe` 的 `observed.snapshot` / `observed.changes` / `observed.text`
  通常已够断言，小页面不必每次 click 后单独 snapshot
- 等内容用条件等待（`wait --text "<文案>"` / `wait --url <url>`），不要 sleep；
  **wait 超时 ≠ 失败**——先 snapshot 看页面实际状态（文本可能大小写不同或不存在）

### 5. 断言（按优先级）

1. `--observe` 的 observed.text / observed.changes（点击链路自带）
2. `get text <sel>` / `get count <sel>` / `extract --schema '{...}'`（表格/结构化）
3. `eval` 最后手段（页全局、computed style、返回 JSON）——eval 前先查 core 的替代表
4. 截图文件大小：纯空白页几百字节，有内容通常 >10KB

断言要点：分支接线类改动必须同时测「目标命中」与「回归无泄漏」
（案例：`get text body` 里 grep `project.type`——泄漏即接线插错位置）。

### 6. 截图存档（位置参数，不是 --path）

```bash
chrome-use screenshot "dev-examples/<主题>-shots/01-场景.png"
```

约定：存 `dev-examples/`（沙盒目录，gitignore 不进 git），文件名带序号与场景。
**截图前先刷新**（`chrome-use reload --observe`）——tsx watch 重启后浏览器仍持旧 HTML。

### 7. 看图验证（模型不能直接看截图时）

```bash
chrome-use screenshot "dev-examples/xx.png"
```

→ `zai_mcp_server_analyze_image` 传截图路径 + **具体**视觉断言提问
（「九宫格中心是否填充」，不要泛泛「看看对不对」）。

### 8. 结束：done 收尾

```bash
chrome-use done              # 自动关本次开的 tab（用户还要看的页面用 --keep <tab>）
```

再删测试项目（DELETE API）、按需停服务（netstat 找 PID + `taskkill //F //PID <pid>`）。

## 三、常见坑

| 症状 | 原因 | 处理 |
|---|---|---|
| `screenshot: unknown option '--path'` | 参数是**位置参数** | `chrome-use screenshot "<路径>"` |
| `tab_reset_failed` / relay timeout | tab 的 CDP 调试通道重置 | 按错误诊断走：`status` + `tab list` 确认 → `open` 重开 tab → 重试（screenshot 只读可重试；send/submit 类先确认效果再决定） |
| `wait --text` 超时 | 文案大小写不符 / 页面未到该状态 / 应用被劫持到别的页 | 先 `snapshot` 看实际状态；`get url` 确认没被劫持 |
| open 后 URL 变成上次的项目会话 | 启动恢复劫持 | `get url` 发现后 `eval` 改 hash，不整页导航 |
| refs 失效 / 编号对不上 | 页面替换重置 refs / 用了旧快照 | 重新 `snapshot -i`，从新快照复制 refs |
| 命令报 daemon still busy | chrome-use 侧忙碌 | 等待后重查；不要重放副作用命令 |
| 页面行为是旧代码 | daemon 没重启 / 浏览器持旧 HTML | daemon 手动重启；截图前 `reload --observe` |
| 中文 API body 报错 | curl 直传 Content-Length 不匹配 | `--data-binary @file` |

## 四、验证完成标准

实机自测完成 = 双服务探活 ok + 目标页面可达且命中（observe/get text 断言）+
回归断言无泄漏 + 截图存档 + `chrome-use done` 收尾 + 测试数据清理。
