# Install & Run Acceptance Checklist

## Overview

Goal: the OpenCode workspace locates the client project, the s1→s2 chain runs end to end, and outputs land in the right places.

## Installation Checks

- [ ] `opencode --version` works
- [ ] `python --version` shows 3.10+, `python -c "import PIL"` imports fine
- [ ] Starting OpenCode in `卡五星自动化流程-10-20/` loads the s0~s4 commands from `.opencode/command/`
- [ ] After `/s0-env`, `.opencode/workspace.json` has client_dir and game_key filled

## Smoke Test

- [ ] `python .opencode/lib/workspace.py where` resolves all three paths
- [ ] `python .opencode/skills/fgui-flow/scripts/scan_fgui.py` produces `.opencode/work/facts.json`; `lookup.py --check` reports the facts base usable
- [ ] `python .opencode/skills/fgui-req/scripts/excel_to_req.py` (with the test Excel in inbox) creates the requirement dirs including 参考图_1334x750/
- [ ] `python .opencode/lib/photocraft.py --check` connects (s4 only)

## Final Checklist

- [ ] s1 outputs (清单.json/施工单.md) are complete (every requirement has 名称+描述)
- [ ] s2 touched only files listed in the plan; zero changes elsewhere in the client project
- [ ] Backups in `<需求>/备份/`, snapshot in `<需求>/FGUI/`
- [ ] Docs and delivery written only after the human signed off the look
