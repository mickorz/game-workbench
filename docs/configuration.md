# Configuration Reference

All flow configuration lives under `.opencode/` (inside the `卡五星自动化流程-10-20/` workspace root).

## Configuration Fields

| File | Field | Default | Description |
|---|---|---|---|
| `.opencode/workspace.json` | `client_dir` | none (written by `/s0-env`) | Client project root (the layer with `assets/` + `settings/` + `*.fairy`); s2/s3/s4 read/write the project through it |
| `.opencode/workspace.json` | `game_key` | none (written by `/s0-env`) | Game identifier; requirement outputs land in `.opencode/work/<game_key>/<需求>/` |
| `.opencode/workspace.json` | `素材库根` | `.opencode/PSD素材库` | PSD asset library location, read-only for find-asset |
| `.opencode/photocraft.json` | control port etc. | see `photocraft.example.json` | PhotoCraft desktop connection, used by s4 slicing |

## Taking Effect & Verification

- `workspace.json` takes effect immediately; verify with `python .opencode/lib/workspace.py where`
- PhotoCraft check: `python .opencode/lib/photocraft.py --check` (auto-launches the desktop app)

## Upgrade

The flow itself (`.opencode/skills/`, `.opencode/lib/`) updates with the repo; after upgrading, re-run `/s0-env` and re-scan the facts base (`scan_fgui.py`).

## Uninstall

Delete `卡五星自动化流程-10-20/.opencode/`; the client project is untouched. `.opencode/work/` holds past requirement outputs — check for deliverables worth keeping before deleting.
