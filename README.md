# Game Workbench

<div align="center">

**A local-first desktop workbench where AI agents build your game assets, UI, and projects.**

<p>
  <a href="https://github.com/mickorz/game-workbench/releases"><img src="https://img.shields.io/badge/Download-Releases-0078D4?style=for-the-badge&logo=github&logoColor=white" alt="Download from Releases" /></a>
</p>

<p>
  <a href="docs/README.md"><img src="https://img.shields.io/badge/built%20on-Pi-7c3aed?style=flat-square" alt="Built on Pi" /></a>
  <a href="#models-bring-your-own-key"><img src="https://img.shields.io/badge/models-40%2B%20providers%20%C2%B7%20BYOK-black?style=flat-square" alt="40+ model providers, bring your own key" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square" alt="License Apache 2.0" /></a>
</p>

<p>
  <b>English</b> · <a href="README.zh-CN.md">简体中文</a>
</p>

</div>

> [!NOTE]
> Game Workbench is in beta. Expect rough edges.

## What it is

Game Workbench is a local-first desktop app for building games with AI
agents. You describe what you want in a chat, and agents work inside
dedicated studios: drafting requirement specs, editing FairyGUI UI on a live
design page, arranging assets on canvases, and running previews to verify
the result. Your model keys stay on your machine, and there are no per-run
credits.

## Studios

The sidebar opens into task-focused studios, each with its own workspace and
tooling:

- **FairyGUI studio** — chat-driven UI editing for FairyGUI projects. The
  agent drives a bridge plugin inside the FairyGUI editor: opens components
  on a design page, reads the component tree, captures rendered screenshots,
  and edits XML with verification.
- **Requirement Check studio** — turns a one-line request into a structured
  requirement spec, a check plan, and a per-criterion check result, with
  open questions settled through a questionnaire gate before anything is
  assumed.
- **Asset Canvas** — a canvas workspace where generated and imported assets
  sit side by side, ready to be referenced by agents and projects.

## Agent core

- **Any model, your keys.** Runs on [Pi](docs/README.md) with 40+ model
  providers — Anthropic, OpenAI, DeepSeek, Qwen, and more. Configure your
  own API keys; nothing is billed per run.
- **Coding agents as drivers.** Sessions can be driven by Claude Code,
  Codex, or OpenCode in addition to the built-in Pi runtime.
- **External agent access.** Game Workbench exposes an MCP server so
  external agents can operate projects, assets, and sessions.

## Workbench features

- **Live preview and playtest** — run web games in a local preview or a
  native window while the agent watches and verifies.
- **Checkpoints and undo** — every turn records file changes; step back
  without losing history.
- **Plugins and skills** — extend the daemon with plugin packages, or teach
  agents new workflows through project skills.
- **Project archives** — export and import projects with their assets.
- **Desktop app** — Electron packaging with auto-update, bilingual UI
  (English and 简体中文).

## How it's built

A React renderer talks to a local Fastify daemon over HTTP and SSE. The
daemon owns agent sessions, workspaces, assets, previews, and publishing;
Electron owns desktop lifecycle and native game windows; shared modules
define the contracts. See the [module map](docs/README.md) for code entry
points per area.

## Getting started (development)

Prerequisites: [Bun](https://bun.sh), Node.js 20+.

```bash
bun install
bun run dev
```

This starts the daemon on `http://127.0.0.1:43110` and the renderer on
`http://127.0.0.1:43120`. Open the renderer URL in a browser, or run the
desktop shell with `bun run dev:desktop`. Setup, verification, and
contribution workflow are documented in
[CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

Game Workbench started as a fork of
[OhMyGame](https://github.com/WhiteTowerAI/ohmygame) (Apache-2.0) and has
been reworked in its own direction. Thank you, OhMyGame.

## License

[Apache-2.0](LICENSE)
