# Troubleshooting

## Installation

| Symptom | Cause / Fix |
|---|---|
| `/s0-env` cannot locate the project | The client root needs all three: `assets/` + `settings/` + `*.fairy`; otherwise pass it explicitly via `workspace.py env --client <path>` |
| `lookup.py` reports facts base missing/stale (exit code 1) | The project changed; re-run `scan_fgui.py`. To force old data, use `--force` |
| Garbled Chinese output | Windows console defaults to GBK; scripts already `reconfigure(encoding="utf-8")` internally — use Windows Terminal or `python -X utf8` |
| ImportError on scripts needing Pillow | `pip install Pillow` |

## Runtime

| Symptom | Cause / Fix |
|---|---|
| `lookup.py <keywords>` exits 3 (0 hits) | The script never guesses; it lists candidates. Try note-file wording or English file names, or search keywords separately (it prints which keyword hit most) |
| Component invisible in the editor after s2 | Cross-package refs need `pkg="<8-char pkg id>"` AND the target component must be exported — missing either fails silently |
| New package won't open on double-click in the editor | Package id must be exactly 8 chars (`ui://` splits on the first 8); longer ids silently resolve to nothing |
| Newly added image invisible in the editor | Not registered in package.xml; import/register it in the editor or it won't publish |
| PhotoCraft won't connect | `python .opencode/lib/photocraft.py --check` auto-launches the desktop app; on "path outside root" errors check the automation read/write root in the message |
| Exported PNG text unchanged | `_pc_export.py --texts` keys must be the full layer name with the `out_` prefix, and the layer must be a real text layer (TySh), not rasterized pixels |
| Edited PSD won't open (s4) | Run `_psd_struct.py <psd>` byte-level self-check and follow its report |
| `find-asset` returns no candidates | 种类 is a hard filter (image/component/font never cross-match); check the manifest item's 种类/来源/状态 fields |

## Still Stuck

- Delivery-package docs: `卡五星自动化流程-10-20/docs/04-技能与脚本参考.md`, `卡五星自动化流程-10-20/docs/05-知识库与素材库.md`
- Pitfall notes: `dev-docs/experience/` (search for a similar record first)
- Write new investigations to `dev-docs/troubleshooting/`; promote cross-project lessons to `dev-docs/experience/`
