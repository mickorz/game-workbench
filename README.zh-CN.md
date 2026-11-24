# Game Workbench

<div align="center">

**本地优先的桌面工作台，AI agent 在这里帮你构建游戏资产、UI 和项目。**

<p>
  <a href="https://github.com/mickorz/game-workbench/releases"><img src="https://img.shields.io/badge/Download-Releases-0078D4?style=for-the-badge&logo=github&logoColor=white" alt="从 Releases 下载" /></a>
</p>

<p>
  <a href="docs/README.md"><img src="https://img.shields.io/badge/built%20on-Pi-7c3aed?style=flat-square" alt="基于 Pi 构建" /></a>
  <a href="#模型自带密钥byok"><img src="https://img.shields.io/badge/models-40%2B%20providers%20%C2%B7%20BYOK-black?style=flat-square" alt="40 多家模型服务商，自带密钥" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="Apache 2.0 许可证" /></a>
</p>

<p>
  <a href="README.md">English</a> · <b>简体中文</b>
</p>

</div>

> [!NOTE]
> Game Workbench 目前处于 Beta 阶段，难免还有粗糙的地方。

## 这是什么

Game Workbench 是一个本地优先的桌面应用，用 AI agent 构建游戏。你在会话里描述想要的东西，agent 在专属工作室里干活：起草需求规格、在实时设计页上编辑 FairyGUI UI、在画布上整理资产、跑预览验证结果。模型密钥保存在你自己的机器上，没有按次计费。

## 工作室

侧边栏按任务划分工作室，每个工作室有独立的工作区和工具：

- **FairyGUI 工作室** — 会话驱动的 FairyGUI 项目 UI 编辑。agent 通过桥插件驱动 FairyGUI 编辑器：在设计页打开组件、读取组件树、截取渲染截图、编辑 XML 并做验证。
- **需求核对工作室** — 把一句话需求变成结构化的需求规格、核对计划和逐条验收标准的核对结果；未定的疑点必须先经过问卷门确认，不允许擅自假设。
- **资产画布** — 画布工作区，生成的与导入的资产并列摆放，供 agent 和项目直接引用。

## Agent 核心

- **任意模型，自带密钥。** 基于 [Pi](docs/README.md) 运行，支持 40 多家模型服务商——Anthropic、OpenAI、DeepSeek、Qwen 等。配置自己的 API 密钥，没有按次计费。
- **编码 agent 作为驱动。** 除内置 Pi 运行时外，会话还可以由 Claude Code、Codex 或 OpenCode 驱动。
- **外部 agent 接入。** Game Workbench 提供 MCP server，外部 agent 可以操作项目、资产和会话。

## 工作台功能

- **实时预览与试玩** — 在本地预览或原生窗口中运行网页游戏，agent 可以边看边验证。
- **检查点与撤销** — 每个回合记录文件变更，可以回退且不丢历史。
- **插件与技能** — 用插件包扩展 daemon，或通过项目技能教会 agent 新的工作流。
- **项目归档** — 连同资产一起导出、导入项目。
- **桌面应用** — Electron 打包与自动更新，双语界面（English 与简体中文）。

## 实现方式

React 渲染层通过 HTTP 和 SSE 与本地 Fastify daemon 通信。daemon 负责 agent 会话、工作区、资产、预览和发布；Electron 负责桌面生命周期和原生游戏窗口；共享模块定义契约。各领域的代码入口见[模块地图](docs/README.md)。

## 开发环境上手

前置要求：[Bun](https://bun.sh)、Node.js 20+。

```bash
bun install
bun run dev
```

这会在 `http://127.0.0.1:43110` 启动 daemon，在 `http://127.0.0.1:43120` 启动渲染层。用浏览器打开渲染层地址，或用 `bun run dev:desktop` 启动桌面壳。环境搭建、验证与贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 致谢

Game Workbench 起源于 [OhMyGame](https://github.com/WhiteTowerAI/ohmygame)（Apache-2.0）的 fork，并已朝自己的方向重做。感谢 OhMyGame。

## 许可证

[Apache-2.0](LICENSE)
