#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 s2 -> s3 衔接文档 psd-spec.json。

用途：
  在 s2 落位执行并经人确认效果后，提取主界面组件 XML 与 清单.json 的客观事实，
  输出规范化的 `<需求>/psd-spec.json`。
  该文档作为 s3 生成结构化 PSD 的唯一事实来源，严禁包含美术后置标签（如【新】）。

用法（工作区根执行）：
  python .opencode/skills/fgui-flow/scripts/generate_psd_spec.py <需求名> [--view <组件XML路径>]
  python .opencode/skills/fgui-flow/scripts/generate_psd_spec.py --req-dir <需求目录> [--view <组件XML路径>]

退出码：0 成功；1 失败。
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOTOPEN = HERE.parents[2]
sys.path.insert(0, str(DOTOPEN / "lib"))
import workspace as W  # noqa: E402

# 引入 _fgui_layout 的工程查找与解析能力
S3_SCRIPTS = DOTOPEN / "skills" / "fgui-to-psd" / "scripts"
sys.path.insert(0, str(S3_SCRIPTS))
try:
    import _fgui_layout as FL  # noqa: E402
except ImportError as e:
    raise SystemExit(f"!! 无法加载 _fgui_layout.py: {e}")


def setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def find_view_xml_candidate(req_dir: Path, client_dir: Path) -> Path | None:
    """自动推断关联的主界面 XML：
    1. 查方案.md 里提及的 View / xml
    2. 查快照 FGUI/assets/ 下的 *View.xml
    3. 查 client_dir 下同名包或主包下的组件
    """
    plan_md = req_dir / "方案.md"
    if plan_md.is_file():
        txt = plan_md.read_text(encoding="utf-8", errors="replace")
        for line in txt.splitlines():
            if ".xml" in line:
                for token in line.replace("`", " ").split():
                    if token.endswith(".xml") and ("View" in token or "Layer" in token):
                        cand = client_dir / token if not Path(token).is_absolute() else Path(token)
                        if cand.is_file():
                            return cand

    snapshot_dir = req_dir / "FGUI" / "assets"
    if snapshot_dir.is_dir():
        views = list(snapshot_dir.rglob("*View.xml")) or list(snapshot_dir.rglob("*.xml"))
        if views:
            return views[0]

    return None


def build_psd_spec(req_dir: Path, view_xml: Path, client_dir: Path) -> dict:
    manifest_json = req_dir / "清单.json"
    manifest_data = {}
    if manifest_json.is_file():
        try:
            manifest_data = json.loads(manifest_json.read_text(encoding="utf-8-sig"))
        except Exception:
            pass

    resources = manifest_data.get("资源", [])
    reuse_names = set()
    scale9_names = set()
    for r in resources:
        slot = r.get("槽位名", "")
        name = Path(slot).name if slot else r.get("名称", "")
        if r.get("来源") == "复用现成":
            reuse_names.add(name)
        if r.get("种类") in ("九宫格图", "九宫格"):
            scale9_names.add(name)

    assets_dir = client_dir / "assets" if (client_dir / "assets").is_dir() else client_dir
    layout_data = FL.build_manifest(
        view_xml,
        assets_dir,
        reuse=reuse_names,
        state_default={},
        state_over={},
        scale9_names=scale9_names,
    )

    canvas = layout_data.get("canvas", {})
    raw_nodes = layout_data.get("nodes", [])

    nodes = []
    for layer in FL.iter_nodes(raw_nodes):
        node_name = layer.get("name", "")
        kind = layer.get("kind", "")
        res_file = (layer.get("asset") or {}).get("name") or layer.get("file") or ""

        is_reuse = bool(layer.get("reused") or (res_file in reuse_names) or (node_name in reuse_names))
        is_scale9 = bool(layer.get("scale9") or (res_file in scale9_names) or (node_name in scale9_names))

        rect = layer.get("rect", [0, 0, 0, 0])
        node_info = {
            "name": node_name,
            "kind": kind,
            "x": rect[0],
            "y": rect[1],
            "w": rect[2],
            "h": rect[3],
            "is_reuse": is_reuse,
            "is_scale9": is_scale9,
            "visible": layer.get("visible", True),
        }

        if kind == "text":
            node_info["text"] = layer.get("text", "")
            node_info["fontSize"] = layer.get("fontSize", 20)
            node_info["color"] = layer.get("color", {}).get("hex", "#FFFFFF") if isinstance(layer.get("color"), dict) else layer.get("color", "#FFFFFF")
            node_info["bold"] = layer.get("bold", False)
        elif kind == "image":
            node_info["file"] = res_file
            node_info["url"] = layer.get("url", "")
        elif kind == "rect":
            node_info["shape"] = layer.get("shape", "rect")
            node_info["fillColor"] = layer.get("fill", {}).get("hex", "#000000") if isinstance(layer.get("fill"), dict) else layer.get("fill", "#000000")
            node_info["opacity"] = layer.get("fill", {}).get("alpha", 1.0) if isinstance(layer.get("fill"), dict) else 1.0
        elif kind == "group":
            node_info["is_component"] = layer.get("is_component", False)
            node_info["is_common_pkg"] = layer.get("is_common_pkg", False)
            node_info["is_list"] = layer.get("is_list", False)

        nodes.append(node_info)

    return {
        "需求名": req_dir.name,
        "view_xml": str(view_xml.relative_to(client_dir)) if view_xml.is_relative_to(client_dir) else str(view_xml),
        "canvas_size": {"w": canvas.get("w", 1334), "h": canvas.get("h", 750)},
        "created_at": W.now_str(),
        "total_nodes": len(nodes),
        "nodes": nodes,
    }


def main(argv=None) -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description="生成 s2->s3 衔接文档 psd-spec.json")
    ap.add_argument("req_name", nargs="?", help="需求名（对应 .opencode/work/<game_key>/<需求名>）")
    ap.add_argument("--req-dir", help="显式指定需求目录路径")
    ap.add_argument("--view", help="主界面组件 XML 路径（缺省时自动推导）")
    ap.add_argument("--root", help="工作区根")
    args = ap.parse_args(argv)

    ws = W.find_workspace_root(getattr(args, "root", None))
    cfg = W.load_config(ws)
    client_dir = Path(cfg.get("client_dir") or ws)

    if args.req_dir:
        req_dir = Path(args.req_dir).resolve()
    elif args.req_name:
        req_dir = W.req_dir(ws, cfg, args.req_name, args)
    else:
        raise SystemExit("!! 必须提供需求名或 --req-dir")

    if not req_dir.is_dir():
        raise SystemExit(f"!! 需求目录不存在：{req_dir}")

    if args.view:
        view_xml = Path(args.view)
        if not view_xml.is_file():
            view_xml = client_dir / args.view
        if not view_xml.is_file():
            raise SystemExit(f"!! 找不到指定的组件 XML：{args.view}")
    else:
        view_xml = find_view_xml_candidate(req_dir, client_dir)
        if not view_xml or not view_xml.is_file():
            raise SystemExit(
                f"!! 未能自动推导主界面组件 XML，请显式提供 --view 参数。"
                f"\n   需求目录：{req_dir}"
            )

    spec_data = build_psd_spec(req_dir, view_xml, client_dir)
    out_file = req_dir / "psd-spec.json"
    out_file.write_text(json.dumps(spec_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ 已生成衔接文档：{out_file}")
    print(f"  界面 XML: {view_xml}")
    print(f"  节点总数: {spec_data['total_nodes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
