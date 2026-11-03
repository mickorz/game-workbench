我建议你把 Canva MCP 接入现有 UI 工作台，但不要简单地把 Canva 当成一个新的 MCP 工具集合，而是把它作为 UI 工作台中的一个独立设计能力层（Design Capability Layer）。

结合你现在的 `pi-agentic-workflow`、`fairygui-html-renderer`，以及正在规划的 FairyGUI UI 工作台，我认为可以把整个系统设计成：

自然语言需求 → AI 设计 Agent → Canva 设计能力 / FairyGUI 组件能力 → UI 中间模型 → 预览与导出。

这里有一个重要原则：

- Canva 负责设计表达、视觉素材、模板和设计资产。
- FairyGUI 负责游戏 UI 组件、布局、工程结构和最终运行时交付。
- AI 工作台负责理解需求、协调工具、维护上下文和执行审批。

不要让 Canva 成为 FairyGUI 的上游依赖，两者应该是可以独立使用、也可以组合使用的能力。

## 1. 先拆解 Canva MCP 的分层能力

这里需要区分两种能力，它们对你的 UI 工作台有不同价值。

[レイヤー | Canva](https://images.openai.com/static-rsc-4/3S5Pt13kx3ZIhmSglt1fUHlIDvftTguvCF8CyuYpJ-2kBvtetce-9BVlOEeGWBS8huaoeizqijxfnwEXN2fclEquiVImBQcwEGL6RH9z4I4GfbBq4wbTEWhPaRsjQQRotWM9quTKz04xQbm2KvfCDOCynjC4v5umWjJVwt7KC0Y?purpose=inline)

A. 设计元素分层（Design Layers）

读取、修改已有 Canva 设计中的元素，例如文字、图片、背景、图形、页面等。

用途：修改 UI 视觉稿、调整元素、复用模板。

[複数画像レイヤー同時生成できるAI「LayerDiffuse」、MML対応音楽生成AI「ChatMusician」、高性能なリップシンクAI「EMO」など重要論文5本を解説（生成AIウィークリー） | テクノエッジ TechnoEdge](https://images.openai.com/static-rsc-4/HS1hg39sg0mUPigoKHqk_9ercdbdsH9qBeDWyKbz_OqZCl8rSFPP3v9hGbRuoZwJgblHSfS5EAcI4kg0cMj6xYlWr7E7IX0vkJd-WgGut30CqUd7hT10JLeohtD_uuWEbCN3Hmhkm8Y9wUW0YDwr6jqHUsngb4_aH9qjkdlfdE8?purpose=inline)

B. 图片智能拆层（Image Layer Separation）

通过 `separate-image-layers` 将一张扁平图片拆成多个可编辑图层。

用途：将游戏 UI 参考图拆成背景、主体、装饰等素材，方便后续编辑和重组。

Canva 官方 MCP 目前已经提供这两类相关能力，包括设计编辑事务、图片拆层、背景移除、图片生成等。

Canva Developers SDK Documentation+2



我认为 B 对你的 FairyGUI 工作台尤其有价值。

你之前遇到的一个问题是：AI 能够生成很好的 HTML，但从一张完整 UI 图片中提取可复用组件、图片和布局信息并不容易。

图片拆层可以成为这条链路的前置能力。

但需要注意：图片拆层不等于自动识别游戏 UI 的语义组件。它可能得到多个视觉图层，却不一定知道哪个是按钮、头像框、血条或者背包格子。

## 2. 推荐的整体架构

我建议在你原有的 UI 工作台中增加一个 Canva Provider，而不是直接把 Canva MCP 的工具全部暴露给 Agent。

UI Workbench

自然语言需求 / 参考图片 / 工程上下文

UI Design Agent

需求理解 · 任务规划 · 工具路由 · 审批

Canva Capability

视觉设计能力

设计生成

设计元素编辑

图片拆层

背景移除

模板与素材管理

导出

FairyGUI Capability

游戏 UI 工程能力

工程读取

组件检索

XML 解析

HTML 渲染

组件编辑

XML 导出

UI Intermediate Model

统一设计描述、元素层级、坐标、素材引用、组件语义

设计预览

HTML / React

游戏交付

FairyGUI XML / Assets

这里最重要的是 UI Intermediate Model。

不要让 Canva 的数据结构直接进入 FairyGUI，也不要让 FairyGUI XML 反过来成为 Canva 的数据结构。

两边都通过中间模型交换信息，这样未来即使换成 Photoshop、Figma 或其他设计工具，也不需要重写整个工作台。

## 3. Canva MCP 应该怎么接入？

建议采用三层结构。

### 第一层：MCP Adapter

负责和 Canva 官方 MCP 通信。

官方提供 Remote MCP，使用 Streamable HTTP：

[`https://api.canva.com/connect/v1/mcp`](https://api.canva.com/connect/v1/mcp)

接入需要在 Canva Developer Portal 创建应用，启用 Canva MCP，并配置 OAuth。每个用户都需要用自己的 Canva 账号授权，不能假设有一个全局服务账号替所有人操作。

Canva Developers Blog+1



我建议你的项目结构类似这样：

```
ui-workbench/
├── packages/
│   ├── ui-core/
│   │   ├── intermediate-model/
│   │   ├── design-document/
│   │   └── asset-registry/
│   │
│   ├── providers/
│   │   ├── canva/
│   │   │   ├── client.ts
│   │   │   ├── auth.ts
│   │   │   ├── design.ts
│   │   │   ├── image-layers.ts
│   │   │   └── export.ts
│   │   │
│   │   └── fairygui/
│   │       ├── project.ts
│   │       ├── component.ts
│   │       └── exporter.ts
│   │
│   ├── workflows/
│   │   ├── image-decompose/
│   │   ├── ui-reconstruction/
│   │   └── ui-generation/
│   │
│   └── agents/
│       └── ui-design-agent/
```

注意：这是建议的代码组织方式，不是要求你把现有项目全部重构成这个结构。

### 第二层：Capability Registry

这是我认为最值得做的一层。

不要把 Canva MCP 的几十个工具直接塞进 Agent 的上下文。

应该将它们抽象为你的工作台自己的能力接口。


| 工作台能力                                 | Canva 对应能力            |
| ------------------------------------- | --------------------- |
| design.create                         | create-design         |
| [design.search](http://design.search) | search-designs        |
| [design.read](http://design.read)     | get-design            |
| design.edit                           | 编辑事务                  |
| image.generate                        | generate-image        |
| image.decompose                       | separate-image-layers |
| image.remove-background               | remove-background     |
| asset.upload                          | upload-asset-from-url |
| design.export                         | export-design         |
| design.template                       | 品牌模板相关工具              |


这样 UI Agent 不需要知道 Canva 的内部工具细节，只需要知道自己有哪些设计能力。

未来接入 Photoshop 时，可以复用同一套 Capability 接口。

### 第三层：Workflow Orchestration

负责将多个能力组合起来。

例如：

用户说：

> 帮我把这个 RPG 游戏背包界面拆成可编辑的 UI 素材。

Agent 不应该直接调用一次 Canva MCP 就结束，而应该执行一条工作流：

## UI 图片拆解工作流

1. 导入参考图片

   保存原图、尺寸、来源和项目关联信息。
2. 图片智能拆层

   调用 Canva separate-image-layers，等待异步任务完成。
3. 图层资产整理

   提取各图层、预览、透明通道和尺寸信息。
4. AI 语义识别

   识别背景、装饰、按钮、图标、面板等视觉元素。
5. 生成 UI Intermediate Model

   建立图层坐标、父子关系、资源引用和语义标签。
6. HTML 预览

   使用你现有的 fairygui-html-renderer 或独立 HTML Renderer。
7. 人工确认与 FairyGUI 导出

   确认元素边界、层级和组件映射后，再生成 FairyGUI XML。

这里建议把 AI 语义识别和图片拆层分开。

Canva 负责提供拆分后的视觉素材；你的 Agent 负责理解这些素材的含义。

这可以避免把 Canva 的拆层结果直接当成 FairyGUI 组件。

## 4. 最值得先做的三个应用场景

我会按下面的优先级开发。

[This item is unavailable - Etsy](https://images.openai.com/static-rsc-4/jsWbQAH4kY2eO3-mlYLZLTS3VUMnYWZ10k1AWctXAtcjkcwaf33D29GZIUqsDowAsIwHd1KtN3M5BTHN5FS3scvXJ-0Zt7VGjhOQ5UEaAvz04B4LcKS77jvfbBPoTcpdHErODJf959PMtNL3ZNxF07QVZ_esstf8-9YfH4-sL2Y?purpose=inline)

P0 · 优先开发

游戏 UI 图片拆层

输入一张完整游戏 UI 截图，拆成多个可编辑素材，再交给现有 UI 工作台做语义识别、HTML 重建和 FairyGUI 转换。

这是 Canva 能力与现有项目结合最直接的地方。

[Meowa UGC Gallery | Public AI Pixel Art, Sprite, and Asset Prompts](https://images.openai.com/static-rsc-4/RTQd6mZ8T5_5T4uKJzGSrPcYateZMSY6cUe3YMCE2cUSqPFPFObnYGt-p5E5WSiZ0wAwvw9aeCEHU1WnkgZBKC2tnIgVCEJQw7vqyqO5lldW8BFwSMfdO425hdpTRI6hPE7u7LOypWrLl8dkhj4ZSxcKDqAFQWIVzUBzIJx887o?purpose=inline)

P1 · 素材生产

游戏 UI 素材生成

通过 Canva 生成背景、装饰、按钮、图标等视觉素材，再整理进你的 Asset Library。

可以逐步形成可搜索、可复用的游戏 UI 素材库。

[Video Game Art Services by Video Game Artists | Fiverr](https://images.openai.com/static-rsc-4/NlRqlvWy-jr3hYaBRT3idmRsrTuX0cv6XErPClnuDmwi6eLSSkEmjAymX3f9dGcwQvsuW8eRJT8Ovhsm5OZ71y31QNdjOJ0eOeQktWW4Dp9jd9akK-nm3UhkQ52LbJ7p7A3PpZhOOshPrjTSoNeVWAUg-E7GmtBY0rbYps9Or8Q?purpose=inline)

P2 · 设计协作

UI 方案与视觉稿管理

Canva 用来生成设计方案、调整配色、管理视觉模板，设计师可以继续在 Canva 中手动修改，工作台读取更新后的设计。

## 5. 有几个技术问题需要提前处理

① Canva 的图层不等于 FairyGUI 的组件。

例如拆出一个头像框，可能得到背景、装饰边缘、发光效果三个图层。

但 FairyGUI 中它们可能需要组合成一个组件，也可能需要拆成三个独立资源。

所以中间模型至少需要区分：

- `VisualLayer`：视觉图层。
- `UIElement`：界面元素。
- `UIComponent`：可复用的 UI 组件。

三者不能混为一谈。

② 异步任务需要统一管理。

Canva 图片拆层、设计生成可能不是立即返回结果。要保留 job ID、轮询状态、失败重试和结果归档。官方也建议对长时间运行的任务采用异步轮询，并在成功后返回设计链接。

Canva Developers Blog+1



③ 素材需要有统一的资产格式。

建议工作台统一保存：

```
asset-bundle/
├── original.png
├── preview.png
├── layers/
│   ├── layer-001.png
│   ├── layer-002.png
│   └── layer-003.png
├── manifest.json
└── metadata.json
```

`manifest.json` 记录图层 ID、文件路径、尺寸、坐标、来源和透明度等信息。具体能否取得完整的坐标和透明度，要根据 Canva 返回结果验证，缺失的信息需要你自己的图像处理流程补齐。

④ 权限和成本要做隔离。

Canva 官方对工具有调用频率限制。例如图片生成是 10 次/分钟，设计导出是 20 次/分钟；品牌模板和 Resize 等部分能力需要 Pro 及以上套餐。

Canva Developers SDK Documentation+1



因此建议在 Capability 层统一做限流、任务队列、用户授权和审批，不要让 Agent 无限重试。

## 6. 我建议的实际开发顺序

不要一开始就做完整的 Canva 工作台。先验证最有价值的能力。


| 阶段   | 开发内容         | 验收目标                  |
| ---- | ------------ | --------------------- |
| P0.1 | Canva MCP 连接 | OAuth、工具发现、调用成功       |
| P0.2 | 图片拆层         | 一张 UI 图片拆出多个素材        |
| P0.3 | Asset Bundle | 素材统一入库、预览、管理          |
| P0.4 | AI 语义识别      | 识别素材类型和视觉关系           |
| P0.5 | HTML 重建      | 利用现有 Renderer 还原 UI   |
| P1   | FairyGUI 导出  | HTML/中间模型转换成 XML      |
| P2   | 设计生成与编辑      | Canva 和 FairyGUI 双向协作 |


P0 最重要的验收案例：

找一张复杂的 RPG 游戏背包界面截图，要求：

1. 上传图片。
2. Canva MCP 自动拆层。
3. 工作台展示所有拆出来的图层。
4. AI 给每个图层标记语义。
5. 可以单独隐藏、替换、调整图层。
6. 最后在 HTML 中重新组合成原始界面。

如果这条链路跑通，就证明 Canva 的能力确实补足了你现有 UI 工作台的一个重要短板。

## 7. 我的最终建议

我认为你未来的 UI 工作台可以逐渐形成三套相互独立的资产体系：


| 资产体系              | 核心内容                        |
| ----------------- | --------------------------- |
| Design Library    | Canva 设计稿、视觉模板、设计方案         |
| Asset Library     | PNG、SVG、拆分图层、背景、图标          |
| Component Library | FairyGUI 组件、HTML 组件、UI 语义描述 |


三套库由 UI Intermediate Model 连接。

这样你的 UI 工作台就不只是一个通过聊天操作 FairyGUI 的工具，而是逐步变成一个：

AI 驱动的游戏 UI 设计、素材生产、组件复用和工程交付平台。

相关官方文档：

- [Canva MCP 官方能力介绍](https://www.canva.dev/docs/apps/mcp/?utm_source=chatgpt.com)
- [Canva MCP 完整工具清单](https://www.canva.dev/docs/apps/mcp/tools/?utm_source=chatgpt.com)
- [Canva MCP 集成开发指南](https://www.canva.dev/blog/developers/canva-mcp-ga/?utm_source=chatgpt.com)

我建议下一步直接给你的 UI 工作台设计一份 《Canva MCP 能力接入与 UI 设计工作流执行方案 V1.0》。

重点先做 P0：Canva 图片拆层 → Asset Library → AI 语义识别 → HTML 预览。先不动现有 FairyGUI 核心架构，等这条链路验证成功，再接入 XML 导出。