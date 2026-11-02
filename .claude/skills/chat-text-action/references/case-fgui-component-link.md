# 实战案例：FGUI 组件名点击 → 设计页直达

> 2026-11-02 落地于本仓库，是 chat-text-action 模式的原型案例。
> 源码：`src/renderer/markdown-content.tsx`、`agent-timeline.tsx`、`project-shell.tsx`、
> `fairygui-design-workspace.tsx`；服务端：`plugins/fairygui/editor-plugin/main.js`。

## 需求

agent 回复里的组件名（如 `` `KW_BTN_ACTIVITY` ``）加下划线可点击，点击后
等同在设计页点该组件：定位包/组件 → 打开渲染截图 + XML → 注入设计上下文。

## 落地形态（对应流程 6 步）

| 步骤 | 实际实现 |
|---|---|
| 1 linkify | 协议 `fgui://component/<name>`；BODY `[A-Z][A-Za-z0-9_]{3,}`；链接目标排除图片/md/pdf 等后缀 |
| 2 拦截 | `a.fgui-component-link`，title「在设计页查看：名字」 |
| 3 透传 | AgentTimeline `onComponentClick` 进 WorkspaceLinkContext |
| 4 动作 | `openDesignComponent`：桥 `search_component` 直查 → 搜不到 fallback `search_component_in_xml` 扫包 XML 找宿主组件 → `setPendingDesignComponent` + `changeWorkspaceView(true)`；仅 `project?.type === "fairygui"` 启用 |
| 5 服务 | 桥两命令：`search_component`（遍历 allPackages 的 component items，EnsureOpen，上限 20 条）；`search_component_in_xml`（GetFiles 全目录扫组件 XML 找 `name="X"`，去重，上限 10 条）——**两层缺一不可**：很多"组件名"其实是子对象（按钮/控制器），不是独立组件 |
| 6 验收 | dev-examples/test-linkify.mjs 五形态单测 + 浏览器端到端（本会话 89 个链接全中，点 `C_LoginBtn` 落到 `login/LoginView`） |

## 本案例特有的坑（流程文档 5 坑之外）

| 坑 | 细节 |
|---|---|
| `GetScreenShot` 调用对象 | 在 `doc.content.displayObject`（DisplayObject）上，不在 GComponent 上；直接 `doc.content.GetScreenShot` 报 not a function |
| 设计页点击与编辑器联动 | `open_doc` 的天然副作用：编辑器里同步选中。设计页点组件 → 编辑器跟着选，免费的双向联动 |
| 编辑器桥单线程队列 | 设计页勿在挂载时串行拉全部包资源树（88 包会占满队列，agent 的桥调用排队超时）——按包懒加载 |
| 宿主 CSP | `connect-src` 只放行 `127.0.0.1:*`；桥 HttpListener 的 `localhost` 前缀仅绑 IPv6。渲染层 fetch 固定用 `127.0.0.1`，桥补双前缀 |

## 验证过的输出样例（linkify 单测）

输入（混合形态）→ 输出：

```text
输入: 表格里 [`KW_BTN_ACTIVITY`](LobbyBottomView.xml) 和 [`C_LoginBtn`]()
输出: 表格里 [`KW_BTN_ACTIVITY`](fgui://component/KW_BTN_ACTIVITY) 和 [`C_LoginBtn`](fgui://component/C_LoginBtn)

输入: 裸反引号 `GameFirstWinView` 与文字
输出: 裸反引号 [`GameFirstWinView`](fgui://component/GameFirstWinView) 与文字

输入: [规则图](design/x.jpg)（图片链接）
输出: 不动

输入: 围栏代码块内 <image name="X"/>
输出: 不动
```

单测脚本：`dev-examples/test-linkify.mjs`（write 工具生成，不经 shell）。
