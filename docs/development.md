# Contributor Guide

For contributors changing the flow itself (skills/scripts). Dev-process docs go to `dev-docs/` (not in git), see root `CLAUDE.md` for the convention.

## Environment & Common Commands

- Python 3.10+ (stdlib first; only image scripts need Pillow)
- Facts base: `python .opencode/skills/fgui-flow/scripts/scan_fgui.py`
- Freshness check: `python .opencode/skills/fgui-flow/scripts/lookup.py --check`
- Keyword lookup: `python .opencode/skills/fgui-flow/scripts/lookup.py <keywords>`
- All scripts are path-agnostic; they locate the project via `.opencode/lib/workspace.py`

## Architecture at a Glance

- `.opencode/command/s0~s4*.md`: user entry slash commands, each loading its skill
- `.opencode/skills/fgui-req|fgui-flow|fgui-to-psd|psd-style/`: four stage skills (SKILL.md defines behavior + scripts/ runnable tools)
- `.opencode/lib/workspace.py`: shared library (path resolution, manifest, find-asset scoring, snapshot/place)
- `.opencode/knowledge/`: runtime knowledge base, read live via `knowledge.py --topic`, never from memory
- `.opencode/PSD素材库/`: read-only asset library; `build_index.py` maintains index + previews offline

Flow chain: s1 parse requirement → s2 edit FGUI project → s3 PSD restoration → s4 restyle/slice and write back. Details: `卡五星自动化流程-10-20/docs/01-总览与架构.md`.

## Tests

- After changing a script, run that skill's self-check first (`lookup.py --check`, `_psd_struct.py <psd>` byte-level check, etc.)
- New scripts: must support `--help`; anything parsing/rewriting files must have a byte-level or structural self-check
- Integration via `opencode run`: concurrency cap 2, watchdog required, see root `CLAUDE.md`

## Local Development Loop

1. Edit SKILL.md or scripts → 2. run a small requirement through s1→s4 → 3. inspect `.opencode/work/` outputs and client project diffs → 4. record pitfalls in `dev-docs/experience/` (promote into `.opencode/knowledge/` once proven)

## Release

Delivery unit = the repo; what ships to artists/programmers are the artifacts inside `卡五星自动化流程-10-20/` (FGUI project files, PSDs, slices). `.opencode/`, `dev-docs/`, `dev-examples/` are not part of deliveries.
