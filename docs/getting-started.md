# Getting Started

From zero to the first successful run of the KAWUXING FGUI art automation flow.

## Prerequisites

- Windows 10/11
- OpenCode CLI on PATH (`opencode --version` works)
- Python 3.10+ with Pillow: `pip install Pillow`
- FairyGUI editor (to review client project changes)
- PhotoCraft desktop app (only needed for s4 PSD slicing)
- The KAWUXING client project on disk (with `assets/` + `settings/` + `*.fairy`)

## Install

1. Clone this repo, enter `卡五星自动化流程-10-20/` (the OpenCode workspace root, the layer containing `.opencode`)
2. Start OpenCode in that directory
3. Run `/s0-env` to locate the client project root; the result is written to `.opencode/workspace.json`

## Verify

```powershell
python .opencode/lib/workspace.py where
```

The output should contain the workspace root, the client project root (`client_dir`), and the work layer root (`.opencode/work`). All three resolve to real paths = setup OK.

## First Run

1. Put an art-requirement Excel into `.opencode/inbox/` (column layout reference: `.opencode/inbox/[测试]美术需求.xlsx`)
2. Run `/s1-req`; outputs land in `.opencode/work/<game_key>/<需求>/`: 需求.md, 参考图_1334x750/, 清单.json, 施工单.md
3. Run `/s2-fgui`; the agent scans the FGUI project, writes a plan, edits component XMLs, then stops for your review
4. Open the client project in the FairyGUI editor to check the result

## Next Steps

- Command reference: [configuration.md](configuration.md) and `卡五星自动化流程-10-20/docs/03-命令手册.md` (in the delivery package)
- Common tasks: [how-to-guides.md](how-to-guides.md)
