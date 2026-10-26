# -*- coding: utf-8 -*-
"""PSD 素材库索引半自动生成（s4 / psd-style）

遍历素材库里的 *.psd（跳过 `_原稿/`），自动抽取**结构化制作单元**：
1. 识别顶层制作单元（最外层组，如完整按钮/标签）与内部嵌套的底图子组（含矢量形状/底图）。
2. 可选自动调起 PhotoCraft 桌面端导出最外层单元的透明裁剪预览图至 `分类/_预览/`。
3. 按 `文件`（相对路径）与已有 index.json 合并，保留人工填的结构/外观/来源需求/备注。

用法（工作区根 = 含 .opencode 的那层执行）：
    python .opencode/skills/psd-style/scripts/build_index.py                     # dry-run
    python .opencode/skills/psd-style/scripts/build_index.py --write             # 落盘 index.json
    python .opencode/skills/psd-style/scripts/build_index.py --write --preview   # 落盘 index.json 并导出各单元预览图
    python .opencode/skills/psd-style/scripts/build_index.py --lib <素材库根>     # 覆盖配置
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 共享库在 .opencode/lib（本脚本在 .opencode/skills/psd-style/scripts/）
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import workspace as W  # noqa: E402

SAFE_NAME_RE = re.compile(r'[/\\?%*:|"<>\s]+')


def load_psd_modules():
    """PSD 解析脚本就在本目录（_psd_struct / _psd_group）。"""
    scripts = Path(__file__).resolve().parent
    if not (scripts / "_psd_struct.py").is_file():
        raise SystemExit(f"!! 找不到 PSD 解析脚本（_psd_struct.py）：{scripts}")
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import _psd_struct as S  # noqa: E402
    import _psd_group as G  # noqa: E402
    return S, G


def layer_lyid(L, S):
    b = S.get_block(L.extra, b"lyid")
    return struct.unpack(">I", b)[0] if b else None


def inspect_psd_units(p: Path, S, G) -> tuple[dict, list[dict]]:
    """解析 PSD 画布信息以及最外层制作单元（含嵌套底图子组与文本）。"""
    data = p.read_bytes()
    st = S.parse(data)
    h = struct.unpack_from(">I", data, 14)[0]
    w = struct.unpack_from(">I", data, 18)[0]
    layers = st["layers"]

    units = []
    stack = []

    # PSD layers 从底到顶排列，逆序遍历即从顶到底
    for L in reversed(layers):
        typ = G.lsct_type(L)
        name = L.name
        lyid = layer_lyid(L, S)
        if typ in (1, 2):  # 组头
            grp = {
                "名": name,
                "lyid": lyid,
                "texts": [],
                "shapes": [],
                "subgroups": [],
            }
            if not stack:
                units.append(grp)
            else:
                stack[-1]["subgroups"].append(grp)
            stack.append(grp)
        elif typ == 3:  # 组尾
            if stack:
                stack.pop()
        else:  # 普通图层
            has_tysh = S.get_block(L.extra, b"TySh") is not None
            has_vmsk = S.get_block(L.extra, b"vmsk") is not None
            if stack:
                if has_tysh:
                    stack[-1]["texts"].append(name)
                if has_vmsk:
                    stack[-1]["shapes"].append(name)

    # 规范化单元结构
    formatted_units = []
    all_shapes = []
    all_texts = []
    for u in units:
        all_texts.extend(u["texts"])
        all_shapes.extend(u["shapes"])
        bg_group = None
        # 若有子组，按规则优先将包含形状的子组认定为底图组
        if u["subgroups"]:
            # 优先选含形状的子组，否则选第一个子组
            cand_bgs = [sg for sg in u["subgroups"] if sg["shapes"]]
            bg = cand_bgs[0] if cand_bgs else u["subgroups"][0]
            bg_ways = []
            if bg["shapes"]:
                bg_ways.append("改尺寸")
            bg_ways.append("换色")
            bg_group = {
                "lyid": bg["lyid"],
                "名": bg["名"],
                "包含形状": bg["shapes"],
                "支持可复用方式": bg_ways,
            }
            all_texts.extend(bg["texts"])
            all_shapes.extend(bg["shapes"])

        u_ways = ["复制组"]
        if u["texts"] or (bg_group and bg_group.get("包含形状")):
            u_ways.append("改文字")
        if bg_group and "改尺寸" in bg_group.get("支持可复用方式", []):
            u_ways.append("改尺寸")
        if bg_group and "换色" in bg_group.get("支持可复用方式", []):
            u_ways.append("换色")

        unit_dict = {
            "lyid": u["lyid"],
            "名": u["名"],
            "预览图": "",
            "文字内容": u["texts"],
            "底图组": bg_group,
            "可复用方式": sorted(list(set(u_ways))),
        }
        formatted_units.append(unit_dict)

    summary = {
        "画布": f"{w}x{h}",
        "单元数": len(formatted_units),
        "文字层数": len(all_texts),
        "形状层数": len(all_shapes),
    }
    return summary, formatted_units


def export_previews_for_psd(psd_path: Path, units: list[dict], asset_id: str, lib_root: Path) -> dict[int, str]:
    """调起 PhotoCraft 导出各顶层单元的独立透明预览图至各分类下的 `_预览/` 目录。"""
    try:
        from PIL import Image
        import photocraft as PC
    except Exception as e:
        print(f"    ! 无法加载 PhotoCraft 或 PIL，跳过预览图导出: {e}")
        return {}

    category = psd_path.relative_to(lib_root).parts[0] if len(psd_path.relative_to(lib_root).parts) > 1 else ""
    preview_dir = (lib_root / category / "_预览") if category else (lib_root / "_预览")
    preview_dir.mkdir(parents=True, exist_ok=True)

    cli = PC.ensure()
    try:
        cli.open_doc(str(psd_path.resolve()))
    except Exception as e:
        print(f"    ! 打开 PSD 失败: {e}")
        return {}

    insp = cli.inspect()
    layers = insp.get("layers", [])

    results = {}
    for u in units:
        ly_name = u["名"]
        ly_id = u["lyid"]
        # 在 PhotoCraft 中按名称寻找顶层匹配组
        matches = [L for L in layers if L.get("name") == ly_name and L.get("kind") == "Group"]
        if not matches:
            # 容错：按图层名称匹配
            matches = [L for L in layers if L.get("name") == ly_name]
        if not matches:
            continue

        target_layer = matches[0]

        # 隐藏所有顶层图层
        for L in layers:
            try:
                cli.engine("layer.setProps", {"layer": L["id"], "visible": False})
            except Exception:
                pass

        # 只开启目标顶层组
        try:
            cli.engine("layer.setProps", {"layer": target_layer["id"], "visible": True})
        except Exception:
            continue

        safe_name = SAFE_NAME_RE.sub("_", ly_name).strip("_")
        png_name = f"{asset_id}_lyid{ly_id}_{safe_name}.png"
        out_png = preview_dir / png_name

        try:
            cli.save_doc(str(out_png.resolve()), fmt="png")
            # 裁剪透明空白边缘
            if out_png.is_file():
                im = Image.open(out_png)
                bbox = im.getchannel("A").getbbox()
                if bbox:
                    cropped = im.crop(bbox)
                    cropped.save(out_png)
            rel_png = out_png.relative_to(lib_root).as_posix()
            results[ly_id] = rel_png
        except Exception as e:
            print(f"    ! 导出单元 [{ly_name}] 失败: {e}")

    try:
        cli.engine("file.close", {})
    except Exception:
        pass

    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="PSD 素材库索引生成与分类预览图导出")
    ap.add_argument("--root")
    ap.add_argument("--lib", help="素材库根（默认取 workspace.json）")
    ap.add_argument("--write", action="store_true", help="落盘 index.json")
    ap.add_argument("--preview", action="store_true", help="通过 PhotoCraft 导出各制作单元的分类预览图")
    ap.add_argument("--skip", default="_原稿", help="跳过的顶层目录名（逗号分隔，默认 _原稿）")
    args = ap.parse_args(argv)

    root = W.find_workspace_root(args.root)
    cfg = W.load_config(root)
    lib = W.get_lib_root(root, cfg, args.lib)
    if not lib.is_dir():
        raise SystemExit(f"!! 素材库不存在：{lib}（先建目录或改 workspace.json）")
    idx = lib / "index.json"

    old = {}
    if idx.is_file():
        for e in json.loads(idx.read_text(encoding="utf-8-sig")).get("素材", []):
            old[str(e.get("文件", "")).replace("\\", "/")] = e

    skip_dirs = {s.strip() for s in args.skip.split(",") if s.strip()}
    S, G = load_psd_modules()

    psds = sorted(p for p in lib.rglob("*.psd")
                  if not (skip_dirs & set(p.relative_to(lib).parts)))
    print(f"· 素材库：{lib}")
    print(f"· 找到 {len(psds)} 个 PSD（跳过 {sorted(skip_dirs)}）")

    seen = set()
    entries = []
    need_tag = []
    n = 1
    for p in psds:
        rel = p.relative_to(lib).as_posix()
        seen.add(rel)
        try:
            summary, units = inspect_psd_units(p, S, G)
        except Exception as e:
            print(f"  ! 解析失败 {rel}: {e}")
            continue

        base = old.get(rel, {})
        if not base.get("id"):
            while f"S{n}" in {e.get("id") for e in entries}:
                n += 1
            base["id"] = f"S{n}"

        asset_id = base.get("id")

        # 检查是否已有旧单元预览图映射
        old_units_map = {u.get("lyid"): u.get("预览图", "") for u in base.get("制作单元", []) if u.get("lyid")}

        # 导出分类预览图
        if args.preview:
            print(f"  ▶ 正在为 {asset_id} ({rel}) 导出分类预览图...")
            preview_map = export_previews_for_psd(p, units, asset_id, lib)
            for u in units:
                if u["lyid"] in preview_map:
                    u["预览图"] = preview_map[u["lyid"]]
                elif u["lyid"] in old_units_map:
                    u["预览图"] = old_units_map[u["lyid"]]
        else:
            # 继承已有预览图路径
            for u in units:
                if u["lyid"] in old_units_map:
                    u["预览图"] = old_units_map[u["lyid"]]

        category = p.relative_to(lib).parts[0] if len(p.relative_to(lib).parts) > 1 else ""

        entry = {
            "id": asset_id,
            "文件": rel,
            "分类": category,
            "种类": base.get("种类") or "图片",
            "结构": base.get("结构") or [],
            "尺寸": summary["画布"],
            "外观": base.get("外观") or [],
            "制作单元": units,
            "来源需求": base.get("来源需求") or "",
            "备注": base.get("备注") or "",
            "_自动": summary,
        }
        entries.append(entry)
        if not entry["结构"] or not entry["外观"]:
            need_tag.append(rel)
        print(f"  + {entry['id']} {rel}  画布={summary['画布']} 制作单元={summary['单元数']} "
              f"文字={summary['文字层数']} 形状={summary['形状层数']}")

    # 保留已消失的历史条目
    for rel, e in old.items():
        if rel not in seen:
            print(f"  ~ 库里已无此文件，保留旧条目：{rel}")
            entries.append(e)

    payload = {"素材": entries}
    if args.write:
        idx.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✓ 已写入 {idx}")
    else:
        print("· dry-run（加 --write 落盘）")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:1200])

    if need_tag:
        print("\n⚠ 以下素材还没标 `结构`/`外观`（匹配质量靠它，请人工补）：")
        for rel in need_tag:
            print(f"  - {rel}")


if __name__ == "__main__":
    main()
