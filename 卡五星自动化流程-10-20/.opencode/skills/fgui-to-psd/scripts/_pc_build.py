# -*- coding: utf-8 -*-
"""按 _fgui_layout.py 出的清单，在 PhotoCraft 里从零合成一份分层 PSD。

与旧 `_pp_build.py` 的差别
--------------------------
旧版靠 Photopea 的 ExtendScript + 用户浏览器；本版走 PhotoCraft 控制协议
（`.opencode/lib/photocraft.py`），不需要浏览器、不需要开页面：

    app.open(图片) -> 全选复制 -> 回目标文档粘贴 -> edit.transform 摆到精确矩形
    type.create 建**真文字层**（可二次编辑，导出时光栅化由 PhotoCraft 负责）
    layer.newAdjustmentLayer.blackWhite + createClippingMask 做"变灰"

图层顺序口径不变：FGUI 的 displayList 是从下到上，PSD 新层总在最上面，
所以按清单顺序（下 -> 上）依次添加即可；组用 moveTo into 收子层。

用法
----
    python .opencode/skills/fgui-to-psd/scripts/_pc_build.py <manifest.json> --out <x.psd> [--dry-run]

前置：PhotoCraft 桌面端可由本脚本自动拉起（见 lib/photocraft.py），
      启动时带 --automation-read-root / --automation-write-root。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import photocraft as PC                                    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

DOC_NAME = "FGUI还原稿"          # 前缀；实际名字会加时间戳，避免撞上 PhotoCraft 恢复的旧文档
FONT_FAMILY = "Microsoft YaHei"
TOL_IMG = 1.5
TOL_TEXT = 3.0


# ---------------------------------------------------------------- 小工具
def hex_rgb(h: str):
    h = (h or "#000000").lstrip("#")
    if len(h) == 8:
        h = h[:6]
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _iter(nodes):
    for n in nodes:
        yield n
        children = n.get("children") or []
        if children:
            yield from _iter(children)


def _flatten(layers, depth=0, parent=None, out=None):
    """doc_inspect 的 layers 树 -> 前序扁平表（与旧 verify 的口径一致）。"""
    out = [] if out is None else out
    for L in layers or []:
        out.append({"depth": depth, "name": L.get("name"), "box": L.get("bounds"),
                    "visible": L.get("visible", True), "opacity": L.get("opacity", 1.0),
                    "kind": L.get("kind"), "group": bool(L.get("children")),
                    "clipped": bool(L.get("clipped")), "id": L.get("id"),
                    "parent": parent})
        if L.get("children"):
            _flatten(L["children"], depth + 1, L.get("name"), out)
    return out


def _find_doc(cli, name=DOC_NAME):
    docs = (cli.request("ui.inspect", {}) or {}).get("session", {}).get("documents", [])
    for d in docs:
        if d.get("name") == name:
            return d["index"]
    return None


# ---------------------------------------------------------------- 合成
class Builder:
    def __init__(self, cli: PC.Client, manifest: dict, verbose=True):
        self.cli = cli
        self.m = manifest
        self.verbose = verbose
        self.doc = None
        self.doc_name = (f"{DOC_NAME}_{time.strftime('%H%M%S')}"
                         f"_{time.time_ns() % 1000:03d}")
        self.plan = []
        self.errors = []
        self._asset_docs = 0

    # -- 基础 ---------------------------------------------------------
    def say(self, msg):
        if self.verbose:
            print("   " + msg, flush=True)

    def engine(self, cmd, params=None):
        return self.cli.engine(cmd, params or {})

    def _doc_list(self):
        return (self.cli.request("ui.inspect", {}) or {}).get("session", {}).get("documents", [])

    def refresh_doc(self):
        """按文档名重新定位目标文档（关掉临时图片文档后 index 会移位）。"""
        for d in self._doc_list():
            if d.get("name") == self.doc_name:
                self.doc = d["index"]
                return True
        return False

    def activate(self):
        self.cli.engine("document.activate", {"document": self.doc})

    def rename(self, layer, name):
        self.engine("layer.renameLayer", {"layer": layer, "name": name})

    def move_into(self, layer, parent_id):
        if parent_id is not None:
            self.engine("layer.moveTo", {"layer": layer, "target": parent_id,
                                         "position": "into"})

    def set_visible(self, layer, visible):
        self.engine("layer.setProps", {"layer": layer, "visible": bool(visible)})

    def set_opacity(self, layer, alpha):
        if alpha is not None and abs(alpha - 1.0) > 0.001:
            self.engine("layer.setProps", {"layer": layer, "opacity": float(alpha)})

    # -- 建文档 -------------------------------------------------------
    def new_document(self):
        c = self.m["canvas"]
        r = self.engine("file.new", {
            "width": int(round(c["w"])), "height": int(round(c["h"])),
            "mode": "rgb", "depth": 8, "background": "transparent",
            "name": self.doc_name,
        })
        self.doc = r["document"]
        self.activate()
        # PhotoCraft 不允许删到 0 层：file.new 自带的空像素层留在最底下当垫层
        # （不参与计划/校验；导出时被隐藏，不影响成图）
        self.say(f"新文档 {c['w']:g}×{c['h']:g}（index {self.doc}）")

    # -- 组 -----------------------------------------------------------
    def add_group(self, node, parent_id):
        gid = self.engine("layer.new.group", {"name": node["layer"]})["layer"]
        self.move_into(gid, parent_id)
        self.set_visible(gid, node.get("visible", True))
        self.set_opacity(gid, node.get("alpha", 1.0))
        self.plan.append({"name": node["layer"], "kind": "group",
                          "parent": node.get("_parent_name"), "rect": None,
                          "visible": node.get("visible", True), "id": gid})
        return gid

    # -- 图片 ---------------------------------------------------------
    def add_image(self, node, parent_id):
        a = node.get("asset") or {}
        src = a.get("file")
        if not src:
            return
        src = str(Path(src).resolve())
        if not Path(src).exists():
            self.errors.append(f"图片不存在：{src}")
            self.say(f"!! 图片不存在 {src}")
            return
        r = [float(v) for v in node["rect"]]
        img_idx = None
        try:
            self.activate()
            before = {d["index"] for d in self._doc_list()}
            img = self.cli.open_doc(src)
            # 只有确实新开了文档才关；app.open 碰到已打开的图只会激活它
            img_idx = next((d["index"] for d in self._doc_list()
                            if d["index"] not in before), None)
            self.engine("select.all")
            self.engine("edit.copy")
            # ★ 先关临时图片文档、再重新定位目标文档：index 会因关闭而整体前移
            if img_idx is not None:
                self.engine("file.close", {"document": img_idx})
                img_idx = None
                self.refresh_doc()
            self.activate()
            pasted = {}
            for attempt in range(3):
                pasted = self.engine("edit.paste",
                                     {"center": [r[0] + r[2] / 2, r[1] + r[3] / 2]})
                if isinstance(pasted, dict) and pasted.get("layer"):
                    break
                time.sleep(0.3)
                self.activate()
            if not isinstance(pasted, dict) or not pasted.get("layer"):
                raise RuntimeError(f"edit.paste 没有返回图层：{pasted}")
            lid = pasted["layer"]
            b = self._layer(lid).get("bounds") or [r[0], r[1], r[2], r[3]]
            if b[2] == 0 and b[3] == 0:
                b = [r[0], r[1], r[0] + r[2], r[1] + r[3]]
            else:
                b = [b[0], b[1], b[0] + b[2], b[1] + b[3]]
            if any(abs(b[i] - v) > 0.01 for i, v in enumerate(
                    [r[0], r[1], r[0] + r[2], r[1] + r[3]])):
                self.engine("edit.transform", {
                    "layer": lid, "rect": b,
                    "quad": [[r[0], r[1]], [r[0] + r[2], r[1]],
                             [r[0] + r[2], r[1] + r[3]], [r[0], r[1] + r[3]]],
                    "interpolation": "bicubic",
                })
            self.rename(lid, node["layer"])
            self.set_visible(lid, node.get("visible", True))
            self.set_opacity(lid, node.get("alpha", 1.0))
            self.move_into(lid, parent_id)
            self.plan.append({"name": node["layer"], "kind": "image",
                              "parent": node.get("_parent_name"), "rect": r,
                              "asset": a.get("name"),
                              "visible": node.get("visible", True), "id": lid})
            self.say(f"图片 {node['layer']} <- {a.get('name')} ({img.get('name')})")
        except Exception as e:
            self.errors.append(f"置入失败 {node['layer']}: {e}")
            self.say(f"!! 置入失败 {node['layer']}: {e}")
        finally:
            if img_idx is not None:
                try:
                    self.engine("file.close", {"document": img_idx})
                except Exception:
                    pass
                self.refresh_doc()
            # 关闭临时图片文档后回到目标文档（index 可能已变，按名字重定位）
            try:
                self.activate()
            except Exception:
                pass

    # -- 文字 ---------------------------------------------------------
    def add_text(self, node, parent_id):
        r = [float(v) for v in node["rect"]]
        cx, cy = r[0] + r[2] / 2.0, r[1] + r[3] / 2.0
        col = node.get("color") or {}
        hexv = col.get("hex") or "#000000"
        alpha = float(col.get("alpha", 1.0))
        size = float(node.get("fontSize") or 12)
        created = self.engine("type.create", {
            "x": cx, "y": cy, "text": node.get("text") or "",
            "font": FONT_FAMILY, "size": size, "color": hexv,
            "name": node["layer"], "align": "center",
        })
        lid = created["layer"]
        if node.get("bold"):
            self.engine("type.setStyle", {"layer": lid, "fauxBold": True})
        if alpha < 0.999:
            rr, gg, bb = hex_rgb(hexv)
            self.engine("type.setStyle", {"layer": lid,
                                          "color": [rr / 255, gg / 255, bb / 255, alpha]})
        # 按实际墨迹外框把中心对准目标中心（不同字体的基线不同）
        info = self.engine("type.info", {"layer": lid})
        b = info.get("bounds")
        if b and b[2] > b[0] and b[3] > b[1]:
            dx = round(cx - (b[0] + b[2]) / 2.0)
            dy = round(cy - (b[1] + b[3]) / 2.0)
            if dx or dy:
                self.engine("layer.translate", {"layer": lid, "dx": dx, "dy": dy})
        self.set_visible(lid, node.get("visible", True))
        self.move_into(lid, parent_id)
        self.plan.append({"name": node["layer"], "kind": "text",
                          "parent": node.get("_parent_name"), "rect": r,
                          "center": [cx, cy], "text": node.get("text"),
                          "visible": node.get("visible", True), "id": lid})
        self.say(f"文字 {node['layer']} \"{node.get('text')}\" {size:g}px @({cx:g},{cy:g})")

    # -- graph 纯色块 --------------------------------------------------
    def add_rect(self, node, parent_id):
        r = [float(v) for v in node["rect"]]
        fill = node.get("fill") or {"hex": "#000000", "alpha": 1.0}
        hexv = fill.get("hex") or "#000000"
        lid = self.engine("shape.create", {
            "kind": "rect", "rect": r, "fill": hexv, "name": node["layer"],
        })["layer"]
        self.set_opacity(lid, fill.get("alpha", 1.0))
        self.set_visible(lid, node.get("visible", True))
        self.move_into(lid, parent_id)
        self.plan.append({"name": node["layer"], "kind": "mask",
                          "parent": node.get("_parent_name"), "rect": r,
                          "visible": node.get("visible", True), "id": lid})
        self.say(f"色块 {node['layer']} {hexv} α{fill.get('alpha', 1):g}")

    # -- 变灰（黑白调整层，剪贴到组） -----------------------------------
    def add_bw(self, group_node, parent_id):
        adj = self.engine("layer.newAdjustmentLayer.blackWhite", {})["layer"]
        self.rename(adj, "黑白")
        self.engine("layer.moveTo", {"layer": adj, "target": group_node["_gid"],
                                     "position": "above"})
        self.engine("layer.createClippingMask", {"layer": adj})
        self.plan.append({"name": "黑白", "kind": "adjust",
                          "parent": group_node.get("_parent_name"),
                          "rect": None, "clip_to": group_node["layer"], "id": adj})
        self.say(f"黑白调整层 -> {group_node['layer']}")

    # -- 遍历 ---------------------------------------------------------
    def walk(self, nodes, parent_id=None, parent_name=None):
        for n in nodes:
            n["_parent_name"] = parent_name
            kind = n.get("kind")
            if kind == "group":
                gid = self.add_group(n, parent_id)
                n["_gid"] = gid
                self.walk(n.get("children") or [], gid, n["layer"])
                if any(c.get("grayed") for c in (n.get("children") or [])):
                    self.add_bw(n, parent_id)
            elif kind == "image":
                self.add_image(n, parent_id)
            elif kind == "text":
                self.add_text(n, parent_id)
            elif kind == "rect":
                self.add_rect(n, parent_id)
            else:
                self.say(f"跳过未知节点 {kind} {n.get('layer')}")

    def _layer(self, lid):
        def find(ls):
            for L in ls:
                if L.get("id") == lid:
                    return L
                r = find(L.get("children") or [])
                if r:
                    return r
            return None
        return find(self.cli.inspect().get("layers") or []) or {}

    # -- 主流程 -------------------------------------------------------
    def build(self, out_psd: Path):
        self.new_document()
        self.walk(self.m.get("nodes") or [])
        self.activate()
        tree = _flatten(self.cli.inspect().get("layers") or [])
        return tree


# ---------------------------------------------------------------- 校验
def verify(plan, flat, tol_img=TOL_IMG, tol_text=TOL_TEXT):
    print("\n" + "=" * 74)
    print("  产物校验（计划 vs PhotoCraft 实际图层树）")
    print("=" * 74)
    by_key = {}
    for t in flat:
        by_key.setdefault((t["parent"], t["name"]), []).append(t)

    bad = []
    for p in plan:
        key = (p.get("parent"), p["name"])
        cands = by_key.get(key) or []
        if not cands:
            bad.append(f"缺图层 {p['name']}（父级 {p.get('parent')}，计划 {p['kind']}）")
            continue
        t = cands[0]
        if p["kind"] in ("image", "mask", "text") and p.get("rect"):
            r = p["rect"]
            want = [r[0], r[1], r[0] + r[2], r[1] + r[3]]
            b = t.get("box")
            if not b:
                bad.append(f"{p['name']}@{p.get('parent')} 没有像素外框")
                continue
            act = [b[0], b[1], b[0] + b[2], b[1] + b[3]]
            if p["kind"] == "text":
                cx, cy = p["center"]
                dx = (act[0] + act[2]) / 2 - cx
                dy = (act[1] + act[3]) / 2 - cy
                if abs(dx) > tol_text or abs(dy) > tol_text:
                    bad.append(f"文字 {p['name']}@{p.get('parent')} "
                               f"中心偏 ({dx:+.1f},{dy:+.1f}) 超过 {tol_text}px")
            else:
                d = max(abs(act[i] - want[i]) for i in range(4))
                if d > tol_img:
                    bad.append(f"{p['name']}@{p.get('parent')} 外框偏 {d:.1f}px "
                               f"(实际 {act} 计划 {[round(v, 1) for v in want]})")

    for p in plan:
        if p.get("visible") is False:
            c = [t for t in (by_key.get((p.get("parent"), p["name"])) or [])
                 if not t["visible"]]
            if not c:
                bad.append(f"{p['name']}@{p.get('parent')} 计划里是隐藏的，实际却没隐藏")

    for p in plan:
        if p["kind"] != "adjust":
            continue
        gname = p["clip_to"]
        a = (by_key.get((p.get("parent"), p["name"])) or [None])[0]
        g = next((t for t in flat if t["name"] == gname and t["group"]), None)
        if a is None:
            bad.append(f"缺调整层「{p['name']}」（父级 {p.get('parent')}）")
        elif g is None:
            bad.append(f"找不到剪贴目标 {gname}")
        else:
            ia, ig = flat.index(a), flat.index(g)
            if not (a["parent"] == g["parent"] and ia == ig - 1 and a["clipped"]):
                bad.append(f"调整层「{p['name']}」没剪贴到 {gname} 正上方"
                           f"（父级={a['parent']} 序号{ia}；目标父级={g['parent']} 序号{ig} clipped={a['clipped']}）")

    print(f"  实际图层 {len(flat)} 个（组 {sum(1 for t in flat if t['group'])} 个）；"
          f"计划 {len(plan)} 项")
    if bad:
        print(f"\n  !! {len(bad)} 处对不上：")
        for b in bad:
            print("     -", b)
    else:
        print("  ✓ 图层名 / 父级 / 坐标 / 隐藏态 / 剪贴位置 全部对得上")
    return len(bad)


def print_tree(flat):
    print("\n" + "=" * 74)
    print("  PhotoCraft 里实际搭出来的图层树")
    print("=" * 74)
    for t in flat:
        pad = "  " * t["depth"]
        b = t.get("box")
        box = "" if not b else "(%g,%g) %g×%g" % (b[0], b[1], b[2], b[3])
        flags = []
        if t["group"]:
            flags.append("组")
        if not t["visible"]:
            flags.append("隐藏")
        if t.get("clipped"):
            flags.append("剪贴")
        op = t.get("opacity")
        if op is not None and abs(op - 1.0) > 0.0005:
            flags.append(f"不透明度{op * 100:g}%")
        print(f"  {pad}{'▸' if t['group'] else '·'} {t['name']:<20} {box:<26} {' '.join(flags)}")


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description="FGUI 清单 -> PhotoCraft 合成分层 PSD")
    ap.add_argument("manifest")
    ap.add_argument("--out", help="PSD 输出路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不连 PhotoCraft")
    ap.add_argument("--port", type=int, help="control 端口（默认 7878）")
    ap.add_argument("--no-verify", action="store_true")
    a = ap.parse_args(argv)

    m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    canvas = m["canvas"]
    total = list(_iter(m.get("nodes") or []))

    print("=" * 74)
    print(f"  清单：{a.manifest}")
    print(f"  画布：{canvas['w']:g}×{canvas['h']:g}   节点 {len(total)} 个")
    print("=" * 74)
    if a.dry_run:
        def w(nodes, d=0):
            for n in nodes:
                print(f"  {'  ' * d}{n.get('kind'):<6} {n.get('layer'):<20}"
                      f" rect={n.get('rect')}")
                w(n.get("children") or [], d + 1)
        w(m.get("nodes") or [])
        return 0

    if not a.out:
        raise SystemExit("!! 需要 --out 指定 PSD 输出路径（或先 --dry-run）")
    out = Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    bak = out.with_name(out.name + ".pre-build.bak")
    if out.exists() and not bak.exists():
        shutil.copy2(out, bak)
        print(f"  已备份旧产物 -> {bak}")

    cli = PC.ensure(port=a.port)
    b = Builder(cli, m)
    t0 = time.time()
    try:
        flat = b.build(out)
    finally:
        pass

    if b.errors:
        print(f"\n  !! {len(b.errors)} 个资源问题：")
        for e in b.errors:
            print("     -", e)

    if not a.no_verify:
        print_tree(flat)
        bad = verify(b.plan, flat)
    else:
        bad = 0

    cli.save_doc(str(out))
    print(f"\n  ★ PSD：{out}  {out.stat().st_size} 字节  ({time.time() - t0:.1f}s)")
    print("=" * 74)
    ok = (not b.errors) and bad == 0 and out.exists()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
