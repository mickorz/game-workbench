# Protocol names and identifiers

XC-UI-Flow was forked from the open-source
[ohmygame](https://github.com/WhiteTowerAI/ohmygame) project and rebranded.
All **user-visible** names now say XC-UI-Flow, but a fixed set of protocol
names and identifiers deliberately keep the old `ohmygame` spelling. This page
records each one, why it is frozen, and what changing it would cost.

## Why names are frozen

A protocol name only works if every side agrees on the same string. Existing
installations, saved projects, installed plugins, and registered external
agents already contain these strings on disk. Renaming them would break every
existing project and plugin unless we also ship a migration that reads old
names — high risk, zero user value.

## The frozen list

| Identifier | Where | Why it must stay |
| --- | --- | --- |
| `.ohmygame-plugin/` | Plugin folders under `plugins/` | Plugin discovery protocol; 15 bundled and third-party plugins plus existing projects are addressed by this folder name. Like `.git`, the directory name is a contract. |
| `ohmygame-godot` | `GODOT_MCP_SERVER_ID` in `src/shared/mcp.ts` | MCP server id matched on both the daemon and plugin sides. |
| `ohmygame` | Marketplace index id in `src/shared/plugins.ts` | Plugin catalog lookups key on this id. |
| `ohmygame-studio` | External MCP server name (`EXTERNAL_MCP_SERVER_NAME`), skill folder name | The name external CLIs registered in `~/.claude.json` and used in the MCP handshake. Renaming would orphan existing registrations. |
| `ohmygame:*` | Electron IPC channel names (`src/desktop/main.ts`, `preload.cts`) | Renderer and main agree on these strings; both sides ship together, but saved sessions and tests reference them. |
| `ohMyGameDesktop` | `contextBridge` key in `preload.cts` | Same contract as IPC channels, exposed to web game pages. |
| `OHMYGAME_*` env vars | `OHMYGAME_RENDERER_URL`, legacy `OHMYGAME_FFMPEG_PATH`, daemon token/data dir vars | Environment variables configured by users or launchers outside our control. New variables use the `XCUIFLOW_` prefix with `OHMYGAME_` fallbacks where read (see `.env.example`, `src/daemon/project-process.ts`). |
| `ohmygame-*` URL params | Story web runtime (`src/story-web/runtime.ts`, e.g. `ohmygame-policy`, `ohmygame-save`) | Query-string protocol between published stories and the runtime. |
| `ohmygame-pruned.json`, `ohmygame-workspace-`, `ohmygame-checkpoint*` | Checkpoint files and temp directory prefixes under `.data/` | Existing data on disk is addressed by these names. |
| `ohmygame-check-process.cmd` | `build/` installer scripts | Installer internals; changing requires rebuilding installers with no benefit. |
| `~/.fgui-agent-bridge/` | FairyGUI bridge plugin registry (see `thirdparties/xc-link-plugin/`) | MCP/CLI discovery convention kept from the upstream `fairygui-agent-bridge` fork. |

## Policy

- New identifiers use the new brand (`XCUIFLOW_` env prefix, `xcflow-` symbol
  prefixes where needed).
- Old names are **compatibility surface**, not debt. Do not rename them in a
  cleanup pass.
- If a rename ever becomes necessary, it must ship with a read-old-name
  fallback plus a data migration, in its own release.

The fork origin and per-file patches for the FairyGUI bridge are recorded in
[`plugins/fairygui/assets/NOTICE.md`](../plugins/fairygui/assets/NOTICE.md).
