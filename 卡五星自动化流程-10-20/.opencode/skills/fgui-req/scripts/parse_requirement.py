#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s1 解析需求：把"一行一需求"表解析进 `清单.json` 的 `需求[]`。

需求原文里要有一张表，**表头含 `名称` 和 `描述`**（列：名称 | 描述 | 类型 | 参考图，后两列可省）：

    | 名称 | 描述 | 类型 | 参考图 |
    |---|---|---|---|
    | 自摸标签 | 结算界面标签改色 | 图标 | 参考图/参考图_01.png |
    | 结算面板 | 面板底图换新 | UI界面 |  |

- `名称`、`描述` **必填**；缺了报错并指出**行号**。
- `类型` 只允许 `UI界面 / 图标 / 场景`；`参考图` 可省。
- 结果写入与需求文档同目录的 `清单.json`（即 `.opencode/work/<game_key>/<需求>/清单.json`）；同名条目跳过。

用法（工作区根执行）：
  python .opencode/skills/fgui-req/scripts/parse_requirement.py .opencode/work/<game_key>/<需求>/需求.md
  python .opencode/skills/fgui-req/scripts/parse_requirement.py 需求.md --out <需求目录>

退出码：0 成功；1 失败。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOTOPEN = HERE.parents[2]
sys.path.insert(0, str(DOTOPEN / "lib"))
import workspace as W  # noqa: E402

HEADER_NAMES = {"名称", "需求名", "需求"}


def setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def split_cells(raw: str) -> list[str]:
    """把 `| a | b |` 拆成 ['a','b']；不是表格行返回 []。"""
    s = raw.strip()
    if not s.startswith("|"):
        return []
    parts = s.strip("|").split("|")
    return [c.strip() for c in parts]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(set(c) <= set("-: ") and c for c in cells)


def parse_items(text: str) -> list[dict]:
    lines = text.splitlines()
    header_idx, cols = None, []
    for i, raw in enumerate(lines):
        cells = split_cells(raw)
        if not cells:
            continue
        if cells[0] in HEADER_NAMES and "描述" in cells:
            header_idx, cols = i, cells
            break
    if header_idx is None:
        raise SystemExit("!! 找不到 `| 名称 | 描述 | ... |` 表头；需求文档需按“一行一需求”写")

    idx = {c: k for k, c in enumerate(cols)}

    def cell(cells: list[str], col: str) -> str:
        k = idx.get(col)
        return cells[k] if k is not None and k < len(cells) else ""

    items: list[dict] = []
    for j in range(header_idx + 1, len(lines)):
        raw = lines[j]
        if not raw.strip().startswith("|"):
            break                       # 表格结束
        cells = split_cells(raw)
        if is_separator(cells):
            continue                    # 表头下的 |---|---| 分隔行
        lineno = j + 1
        name = cell(cells, "名称") or (cells[0] if cells else "")
        desc = cell(cells, "描述") or (cells[1] if len(cells) > 1 else "")
        typ = cell(cells, "类型")
        img = cell(cells, "参考图")
        if not name:
            raise SystemExit(f"!! 第 {lineno} 行：缺“名称”")
        if not desc:
            raise SystemExit(f"!! 第 {lineno} 行：缺“描述”")
        if typ:
            W.validate_enum("类型", typ, W.ENUM_需求类型)
        items.append({"名称": name, "描述": desc, "类型": typ, "参考图": img})
    if not items:
        raise SystemExit("!! 表里没有任何需求行（只有表头？）")
    return items


def main(argv=None) -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description="解析“一行一需求”表 → 清单.json 的 需求[]")
    ap.add_argument("reqmd", help="需求原文 md（含 名称/描述 表）")
    ap.add_argument("--out", help="需求目录（默认取需求 md 所在目录）")
    ap.add_argument("--需求", help="清单里的需求名（默认取需求目录名）")
    args = ap.parse_args(argv)

    reqmd = Path(args.reqmd)
    if not reqmd.is_file():
        raise SystemExit(f"!! 需求文档不存在：{reqmd}")
    out = Path(args.out).resolve() if args.out else reqmd.resolve().parent
    name = args.需求 or out.name

    items = parse_items(reqmd.read_text(encoding="utf-8-sig"))

    mp = out / "清单.json"
    if mp.is_file():
        data = W.load_manifest(mp)
    else:
        data = {"需求名": name, "facts_hash": "", "创建": W.now_str(), "需求": [], "资源": []}
    if not data.get("需求名"):
        data["需求名"] = name

    existing = {r.get("名称") for r in data["需求"]}
    added = 0
    for it in items:
        if it["名称"] in existing:
            print(f"  · 已有同名条目，跳过：{it['名称']}")
            continue
        data["需求"].append({
            "名称": it["名称"],
            "描述": it["描述"],
            "类型": it["类型"],
            "参考图": it["参考图"],
            "参考图_1334x750": "",
        })
        existing.add(it["名称"])
        added += 1

    W.save_manifest(mp, data)
    print(f"✓ 解析 {len(items)} 条 → 新增 {added} 条；清单：{mp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
