# 服务商分组配置指南（provider-groups）

> 读者向：给要调整 onboarding「连接 AI」步骤里 LLM 服务商分组和排序的人用。
> 设计与分析过程见 `dev-docs/design/2026-11-09-本地凭据自动导入方案.md` 与
> `dev-docs/design/2026-11-09-grasp设置面板分析与apikey设置步骤方案.md`。

## 分组效果

「连接 AI」步骤的服务商列表按以下顺序渲染，每组带一个组头：

1. **已连接的服务商**（固定第一，无需配置）
2. **配置的自定义组**（来自 JSON 配置，按文件顺序；当前内置一个「国内常用」组）
3. **热门服务商**（顺序来自配置的 `popularOrder`）
4. **更多服务商**（其余全部，折叠展示）

## 配置文件在哪里

**唯一入口**：`src/renderer/provider-groups.config.json`

改这个文件即可调整分组与优先级，**不需要动组件代码**。`src/renderer/provider-groups.ts`
读取它并完成分组计算。

> 注意作用域：该配置**只影响 onboarding 引导页**的服务商列表；设置页
> （Providers & Models）保持原有分组行为不受影响。

## 配置结构

```json
{
  "groups": [
    {
      "id": "china",
      "providers": [
        "deepseek",
        "zai",
        "zai-coding-cn",
        "moonshotai",
        "moonshotai-cn",
        "kimi-coding",
        "qwen-token-plan",
        "qwen-token-plan-cn",
        "minimax",
        "minimax-cn"
      ]
    }
  ],
  "popularOrder": [
    "openai",
    "anthropic",
    "openrouter",
    "google",
    "deepseek",
    "meshy",
    "tripo"
  ]
}
```

| 字段 | 管什么 |
|---|---|
| `groups` | 自定义显示组数组；**数组顺序 = 组的显示优先级**，可定义任意多个 |
| `groups[].id` | 组标识，同时用于组头文案的 i18n key（`providers.group.<id>`） |
| `groups[].providers` | 组成员的服务商 id；**数组顺序 = 组内显示顺序** |
| `popularOrder` | 「热门服务商」组的成员与顺序 |

## 常用操作对照

| 想做什么 | 怎么改 |
|---|---|
| 新增一个组 | 在 `groups` 数组加一个 `{ "id": "...", "providers": [...] }` 对象，并按下面「组头文案」补两行 i18n |
| 调整组的先后 | 上下移动 `groups` 数组元素 |
| 调整组内排序 | 移动该组 `providers` 数组元素 |
| 把服务商从组里移除 | 从 `providers` 数组删掉该 id（会落回「热门服务商」或「更多服务商」） |
| 调整热门排序 | 改 `popularOrder` 数组顺序 |
| 不想要自定义组 | 删掉对应组对象（或清空 `groups` 数组） |

## 组头文案（i18n）

组头文案按 `providers.group.<id>` 从双语文案文件解析：

- `src/renderer/locales/zh-CN.ts`
- `src/renderer/locales/en.ts`

新增组时**两个文件都要加**（仓库约定：UI 文案双语同步），例如：

```ts
// en.ts
china: "Popular in China",
// zh-CN.ts
china: "国内常用",
```

`id` 没有对应 i18n key 时组头会直接显示 id 字符串，不会报错——所以临时调整
可以不加文案，但正式发布前请补齐。

## 服务商 id 怎么查

内置服务商 id 以 Pi 目录为准，用一条命令查全量：

```bash
curl http://127.0.0.1:43110/settings/providers
```

返回 JSON 数组，取每项的 `id` 字段。常见内置 id：`anthropic`、`openai`、
`google`、`deepseek`、`openrouter`、`zai`（智谱 GLM）、`moonshotai`（Kimi）、
`qwen-token-plan`（通义）、`minimax` 等。

注意：用户自建的自定义服务商（id 形如 `custom-<uuid>`）不写在配置里，它们
连接后会自动进入「已连接的服务商」组。

## 分组规则（组件行为）

- **已连接的服务商永远第一**，与配置无关
- 被 `groups` 认领的服务商会从「热门服务商」和「更多服务商」中移除——同一个
  服务商只会出现在一个组里
- 配置里写了但当前目录不存在（或已连接）的 id 会被忽略，不会报错
- 「更多服务商」折叠按钮只在有可折叠成员时显示

## 改了以后如何生效

### 开发模式（bun run dev，本机 http://127.0.0.1:43120）

**保存即生效**：vite HMR 监听 JSON 与源码变化，保存后浏览器自动重渲染，
重新打开引导第 2 步即可看到新分组。

### 桌面端 / 生产构建

需要重新构建渲染层：

```bash
bun run build:renderer
```

## 原理速查

- 分组计算：`src/renderer/provider-groups.ts`（`groupProviders` 函数，
  `priorityGroups` 参数接收配置组，未传时为空——设置页因此不受影响）
- 渲染入口：`src/renderer/onboarding.tsx`（`ProviderPicker` 组件）
- 组件行为测试：`test/provider-groups.test.ts`、`test/onboarding-renderer.test.tsx`
