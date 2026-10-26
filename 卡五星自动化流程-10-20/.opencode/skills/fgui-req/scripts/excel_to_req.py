#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Excel → 多个需求目录：每行一个独立目录，各自走完整流程。

两种模式：
1. 扫描模式（无参数）：扫描 .opencode/inbox/ 下所有 Excel 文件
2. 指定模式（有参数）：处理指定的 Excel 文件

输入：.xlsx 文件，每行一个需求，图片嵌入在单元格内。
输出：每行生成独立目录 `.opencode/work/<game_key>/<需求名>/`：
  - 需求.md（单行需求的 markdown 表格）
  - 参考图/（该行的嵌入图片）

列名自动匹配（支持别名）：
  - 名称：资源名称 / 名称 / 需求名 / 需求
  - 描述：资源说明 / 描述 / 说明
  - 类型：资源类型 / 类型
  - 原型图/参考图：图片列

用法（工作区根执行）：
  python .opencode/skills/fgui-req/scripts/excel_to_req.py              # 扫描 inbox
  python .opencode/skills/fgui-req/scripts/excel_to_req.py <excel路径>  # 指定文件
  python .opencode/skills/fgui-req/scripts/excel_to_req.py --force      # 覆盖已存在

退出码：0 成功；1 失败。
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOTOPEN = HERE.parents[2]
sys.path.insert(0, str(DOTOPEN / "lib"))
import workspace as W  # noqa: E402

try:
    import openpyxl
except ImportError:
    raise SystemExit("!! 缺少 openpyxl，请运行：pip install openpyxl")

COL_ALIASES = {
    "名称": ["资源名称", "名称", "需求名", "需求", "name"],
    "描述": ["资源说明", "描述", "说明", "desc", "description"],
    "类型": ["资源类型", "类型", "type"],
    "原型图": ["原型图", "prototype"],
    "参考图": ["参考图", "参考", "图片", "截图", "image", "screenshot"],
}

TYPE_MAP = {
    "UI": "UI界面",
    "ui": "UI界面",
    "图标": "图标",
    "icon": "图标",
    "场景": "场景",
    "scene": "场景",
}


def setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def match_columns(headers: list[str]) -> dict[str, int | None]:
    """按表头名自动匹配列索引（1-indexed），返回 {字段名: 列号}。"""
    result: dict[str, int | None] = {}
    for field, aliases in COL_ALIASES.items():
        result[field] = None
        for col_idx, header in enumerate(headers, 1):
            if header and any(alias == header.strip() for alias in aliases):
                result[field] = col_idx
                break
    return result


def normalize_type(typ: str) -> str:
    """规范化类型字段。"""
    if not typ:
        return ""
    return TYPE_MAP.get(typ.strip(), typ.strip())


def extract_images_from_xlsx(xlsx_path: Path) -> tuple[dict[tuple[int, int], bytes], dict[tuple[int, int], str]]:
    """从 xlsx 提取嵌入图片，返回 (图片数据映射, 扩展名映射)。"""
    img_data_map: dict[tuple[int, int], bytes] = {}
    img_ext_map: dict[tuple[int, int], str] = {}

    with zipfile.ZipFile(xlsx_path, "r") as zf:
        media_files = [n for n in zf.namelist() if n.startswith("xl/media/")]
        media_data: dict[str, bytes] = {}
        for media_name in media_files:
            media_data[Path(media_name).name] = zf.read(media_name)

    if not media_data:
        return img_data_map, img_ext_map

    try:
        wb = openpyxl.load_workbook(xlsx_path)
        ws = wb.active
        for img in ws._images:
            anchor = img.anchor
            if hasattr(anchor, "_from"):
                row = anchor._from.row + 1
                col = anchor._from.col + 1
                data = img._data()
                ext = ".png"
                for name, d in media_data.items():
                    if d == data:
                        ext = Path(name).suffix or ".png"
                        break
                img_data_map[(row, col)] = data
                img_ext_map[(row, col)] = ext
    except Exception as e:
        print(f"  ! 图片锚点解析失败：{e}")

    return img_data_map, img_ext_map


def sanitize_filename(name: str) -> str:
    """清理文件名中的非法字符。"""
    invalid_chars = '<>:"/\\|?*'
    for c in invalid_chars:
        name = name.replace(c, "_")
    return name.strip()


def process_excel(xlsx_path: Path, work_root: Path, force: bool) -> list[str]:
    """处理单个 Excel 文件，返回创建的目录名列表。"""
    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb.active

    headers = [sheet.cell(1, col).value for col in range(1, sheet.max_column + 1)]
    col_map = match_columns(headers)

    if not col_map.get("名称"):
        print(f"  !! 找不到「名称」列，表头：{headers}")
        return []
    if not col_map.get("描述"):
        print(f"  !! 找不到「描述」列，表头：{headers}")
        return []

    print(f"  · 列映射：{col_map}")
    print(f"  · 数据行：{sheet.max_row - 1} 行")

    img_data_map, img_ext_map = extract_images_from_xlsx(xlsx_path)
    print(f"  · 提取图片：{len(img_data_map)} 张")

    img_cols = [col_map.get("原型图"), col_map.get("参考图")]
    img_cols = [c for c in img_cols if c]

    created_dirs: list[str] = []
    for row in range(2, sheet.max_row + 1):
        name = sheet.cell(row, col_map["名称"]).value if col_map["名称"] else ""
        desc = sheet.cell(row, col_map["描述"]).value if col_map["描述"] else ""
        typ = sheet.cell(row, col_map["类型"]).value if col_map.get("类型") else ""
        if not name or not desc:
            continue
        name = str(name).strip()
        desc = str(desc).strip().replace("\n", " ")
        typ = normalize_type(str(typ).strip() if typ else "")

        dir_name = sanitize_filename(name)
        out_dir = work_root / dir_name

        if out_dir.exists() and not force:
            print(f"    · 跳过（已存在）：{dir_name}")
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        img_dir = out_dir / "参考图"
        img_dir.mkdir(exist_ok=True)

        img_path = ""
        for img_col in img_cols:
            key = (row, img_col)
            if key in img_data_map:
                ext = img_ext_map.get(key, ".png")
                img_file = img_dir / f"参考图_01{ext}"
                img_file.write_bytes(img_data_map[key])
                img_path = f"参考图/参考图_01{ext}"
                break

        lines = ["# 需求清单", ""]
        lines.append("| 名称 | 描述 | 类型 | 参考图 |")
        lines.append("|---|---|---|---|")
        lines.append(f"| {name} | {desc} | {typ} | {img_path} |")
        lines.append("")

        reqmd = out_dir / "需求.md"
        reqmd.write_text("\n".join(lines), encoding="utf-8")
        created_dirs.append(dir_name)
        print(f"    ✓ {dir_name}")

    return created_dirs


def main(argv=None) -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description="Excel → 多个需求目录（每行一个）")
    ap.add_argument("xlsx", nargs="?", help="Excel 文件路径（不指定则扫描 inbox）")
    ap.add_argument("--root", help="工作区根（含 .opencode 的那层）")
    ap.add_argument("--force", action="store_true", help="已存在也覆盖")
    args = ap.parse_args(argv)

    ws = W.find_workspace_root(getattr(args, "root", None))
    cfg = W.load_config(ws)
    game_key = cfg.get("game_key", "default")
    work_root = ws / ".opencode" / "work" / game_key
    inbox_dir = ws / ".opencode" / "inbox"

    all_created: list[str] = []

    if args.xlsx:
        xlsx_path = Path(args.xlsx)
        if not xlsx_path.is_file():
            raise SystemExit(f"!! Excel 文件不存在：{xlsx_path}")
        print(f"处理：{xlsx_path.name}")
        all_created = process_excel(xlsx_path, work_root, args.force)
    else:
        if not inbox_dir.is_dir():
            inbox_dir.mkdir(parents=True, exist_ok=True)
            print(f"已创建 inbox 目录：{inbox_dir}")
            print(f"请把 Excel 文件放入该目录后重跑本脚本")
            return 0

        xlsx_files = list(inbox_dir.glob("*.xlsx")) + list(inbox_dir.glob("*.xls"))
        if not xlsx_files:
            print(f"inbox 目录为空：{inbox_dir}")
            print(f"请把 Excel 文件放入该目录后重跑本脚本")
            return 0

        print(f"扫描 inbox：找到 {len(xlsx_files)} 个 Excel 文件")
        for xlsx_path in xlsx_files:
            print(f"\n处理：{xlsx_path.name}")
            created = process_excel(xlsx_path, work_root, args.force)
            all_created.extend(created)

    print(f"\n✓ 共创建 {len(all_created)} 个需求目录")
    for d in all_created:
        print(f"    .opencode/work/{game_key}/{d}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
