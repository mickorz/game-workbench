# 聊天文本点击扩展执行流程（6 步）

下文 `<PATTERN>` 是要点击的文本模式，`<SCHEME>` 是自定义协议名（如 `fgui`），
`onXxxClick` 是点击回调名。文件路径均相对仓库根 `src/renderer/`。

## 步骤 1：markdown 预处理 linkify（markdown-content.tsx）

在 `MarkdownContent` 组件上方加三样东西：

```tsx
/** 模式特征正则的 BODY（不含定界符），排除文件路径样式 */
const PATTERN_BODY = "[A-Z][A-Za-z0-9_]{3,}"; // 按实际模式改

// 围栏代码块必须跳过；LINKED 覆盖 [`X`](url) 与 [X](url) 两种链接形态
const FENCED_CODE_RE = /\n```[\s\S]*?\n```|\n~~~[\s\S]*?\n~~~/g;
const LINKED_NAME_RE = new RegExp("\\[(`?(" + PATTERN_BODY + ")`?)\\]\\(([^)]*)\\)", "g");
const BARE_TICK_NAME_RE = new RegExp("`(" + PATTERN_BODY + ")`(?!\\]\\(" + "<SCHEME>" + "))", "g");
// ↑ 注意：BARE 的负向断言防止二次替换 linkify 自己的输出；
//   JS 字符串转义：文件源码里写 \\] \\( （即 RegExp 收到 \] \( ）

// 不会是动作目标的链接目标后缀（图片/文档/压缩包/媒体）——按需增删
const NON_ACTION_URL_RE = /\.(png|jpe?g|gif|webp|svg|md|pdf|zip|mp4|mp3|wav|json)$/i;

function linkifyXxx(text: string): string {
  return text
    .split(FENCED_CODE_RE)
    .map((part, index) => {
      if (index % 2 === 1) return part; // 围栏代码块保持原样
      let out = part.replace(LINKED_NAME_RE, (match: string, outer: string, name: string, url: string) => {
        if (url.startsWith("<SCHEME>://") || NON_ACTION_URL_RE.test(url)) return match;
        return "[`" + name + "`](<SCHEME>://action/" + name + ")";
      });
      out = out.replace(BARE_TICK_NAME_RE, (match: string, name: string) => {
        if (/[./]/.test(name)) return match;
        return "[`" + name + "`](<SCHEME>://action/" + name + ")";
      });
      return out;
    })
    .join("");
}
```

**捕获组对齐**（第一个坑）：`LINKED_NAME_RE` 有 3 个捕获组——组1=含反引号的完整名
（`` `X` `` 或 `X`）、组2=纯名、组3=url。回调签名 `(match, outer, name, url)`，
**拼接用 name（组2）**，否则嵌套链接。

## 步骤 2：a: 分支拦截 + urlTransform 放行（同文件）

```tsx
/** 放行自定义协议（react-markdown v9 默认 urlTransform 把非 http 协议清洗成空串） */
function xxxUrlTransform(url: string): string {
  return url; // 拦截与安全都在 a: 分支做，这里全放行
}

export const MarkdownContent = memo(function MarkdownContent({ text, className = "", workspacePath, baseDir,
  onOpenWorkspaceFile, onXxxClick, renderImage }: {
  // ...既有 props...
  /** 启用后文本模式变为可点击，回调收到匹配名 */
  onXxxClick?: (name: string) => void;
  // ...
}) {
  const components = useMemo<Components>(() => ({
    // ...既有 img / a / pre...
    a: ({ href, children }) => {
      if (onXxxClick && href?.startsWith("<SCHEME>://action/")) {
        const name = decodeURIComponent(href.slice("<SCHEME>://action/".length));
        return <a className="xxx-action-link" href={href}
          title={`${t("xxx.openAction")}: ${name}`}
          onClick={(event) => { event.preventDefault(); onXxxClick(name); }}>
          {children}</a>;
      }
      // ...既有 workspace 文件链接与 fallback...
    },
    pre: MarkdownCodeBlock,
  }), [workspacePath, baseDir, onOpenWorkspaceFile, onXxxClick, renderImage]); // 新 prop 进 deps！

  const linkedText = useMemo(() => (onXxxClick ? linkifyXxx(text) : text), [text, onXxxClick]);
  return (
    <div className={`markdown-content${className ? ` ${className}` : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}
        urlTransform={onXxxClick ? xxxUrlTransform : undefined}>
        {linkedText}
      </ReactMarkdown>
    </div>
  );
});
```

**第二坑（必踩）**：没有 `urlTransform` 时 react-markdown v9 的 `defaultUrlTransform`
把自定义协议清洗成 `""`，DOM 变 `<a href="" target="_blank">`，点击开空白新标签。
加了 `urlTransform` 后点击才走拦截分支。

## 步骤 3：timeline 透传（agent-timeline.tsx）

三处：Props 接口加 `onXxxClick?: (name: string) => void;`；
`WorkspaceLinkContext` 类型与 provider value 加字段；
消费处 `<MarkdownContent {...workspaceLinks} />` 已用展开，无需改。

## 步骤 4：shell 层动作（project-shell.tsx）

```tsx
const [pendingXxx, setPendingXxx] = useState<{ /* 定位结果 */ token: number }>();

const openXxx = useCallback(async (name: string): Promise<void> => {
  try {
    // 可选：先查本地服务定位目标（搜不到可 fallback 第二种搜索）
    const target = await locateByName(name);
    if (!target) return;                 // 静默降级，不打断会话阅读
    setPendingXxx({ ...target, token: Date.now() });
    changeWorkspaceView(true);           // 切到目标视图（hash 驱动）
  } catch {
    return;                              // 服务不通也静默
  }
}, [changeWorkspaceView]);

// AgentTimeline 传参（按需限定生效范围，如仅某项目类型）
onXxxClick={project?.type === "<type>" ? (name) => void openXxx(name) : undefined}
```

目标视图组件加 `initialXxx` prop（含 token），`useEffect` 监听 token 变化执行选中。

## 步骤 5：（可选）本地服务搜索命令

若定位需要查本地服务（如编辑器桥/daemon），给服务加一条只读搜索命令，
**必须带两层**：精确名直查 + 名字搜不到时扫内容/元数据找宿主（子对象 → 父组件）。
返回截断上限（如 20 条）防大工程拖垮。参考实现见案例文件的
`search_component` / `search_component_in_xml`。

改完服务端代码后 `node --check` + 重启服务再测。

## 步骤 6：单测脚本 + 验收

**单测**（先写，防转义污染）：用 write 工具写 `dev-examples/test-xxx.mjs`
（**绝不**用 bash inline 脚本/heredoc 生成含反引号与正则的代码——shell 会吃转义，
见坑 5），覆盖五种输入形态：

1. 带反引号链接 `` [`X`](url) `` → 应命中
2. 空链接 `` [`X`]() `` → 应命中
3. 无反引号链接 `[X](url)` → 视模式而定
4. 裸反引号 `` `X` `` → 应命中
5. 围栏代码块内 → **不**命中；图片/文档链接 → **不**命中

**浏览器端到端**：
1. `bun run typecheck` 通过；硬刷新（ignoreCache）页面
2. 打开含模式文本的会话，确认 DOM：`document.querySelectorAll("a.<class>")` 有命中、
   `href` 是 `<SCHEME>://` 完整值（不是空串！）
3. 点击 → 动作执行（视图切换/选中/服务调用）
4. 回归：普通 markdown 链接、文件链接、代码块渲染不变

## 坑清单（5 个，全部实战踩过）

| # | 坑 | 现象 | 根因 | 修法 |
|---|---|---|---|---|
| 1 | urlTransform 清洗 | 点击开空白新标签；DOM `<a href="" target="_blank">` | react-markdown v9 默认只放行 http/https 等 | 传 `urlTransform={(url) => url}`，拦截放 a: 分支 |
| 2 | 捕获组错位 | 嵌套链接 `` [[`X`](fgui...)​](url) `` | 正则多个捕获组，回调参数少写/错位 | 数清捕获组；单测脚本验证输出形态 |
| 3 | 链接形态多样 | 只命中部分文本 | agent 输出有裸反引号/带链接/空链接多种形态 | LINKED（反引号可选）+ BARE（负向断言防二次替换）双正则 |
| 4 | 代码块污染 | 代码块内容被替换成链接文本 | linkify 对整篇 text 全局替换 | FENCED_CODE_RE split，奇数段跳过 |
| 5 | shell 反引号污染 | 生成的代码正则残缺/换行错乱 | bash -e / heredoc 对含反引号与 `\\` 的代码多层转义 | 一律 write 工具写脚本文件再执行；修转义用「write python + chr() 构造」或 od 查字节 |

## 验收后的提交与文档

- commit：`feat: clickable <PATTERN> in chat replies (linkify + <SCHEME>:// protocol)`
- 按仓库 CLAUDE.md 更新 `dev-docs/progress/` 与 `progress-result/`。
