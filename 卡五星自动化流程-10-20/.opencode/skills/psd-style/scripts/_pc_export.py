# -*- coding: utf-8 -*-
"""把 PSD 里带 `out_` 前缀的图层导出成透明 PNG，并把改好的文档回存成 PSD。

替代旧 `_pp_export.py`（Photopea + 本地页面）：
    PhotoCraft 打开 PSD -> 逐个目标层做"只留它可见" -> app.save PNG -> 恢复可见
    -> 最后 app.save PSD（真文字层/图层样式原样保留，不需要 saveToOE 烘焙）

用法
----
    python .opencode/skills/psd-style/scripts/_pc_export.py <psd> <out_dir> \
        [--prefix out_] [--canvas WxH] [--texts texts.json] [--save-psd <path>] [--port 7878]

约定
----
- 目标是图层名以 `--prefix`（默认 `out_`）开头的图层**或图层组**；导出文件名 = 去掉前缀。
- 全部目标导完后把文档存回 `--save-psd`（默认就是输入的 PSD；源文件请先复制到制作副本）。
- `--canvas` 在导出前用 image.canvasSize 扩画布（居中），防止长文字超出画布被裁。
- `--texts` 的键是图层名（含前缀），值是新文字；直接改真文字层，导出即生效。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
import photocraft as PC                                    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

BAD_CHARS = re.compile(r'[\\/:*?"<>|]')


def flatten(layers, depth=0, parent_id=None, out=None):
    out = [] if out is None else out
    for L in layers or []:
        out.append({"id": L["id"], "name": L.get("name", ""), "kind": L.get("kind"),
                    "visible": bool(L.get("visible", True)),
                    "children": L.get("children") or [],
                    "depth": depth, "parent": parent_id})
        if L.get("children"):
            flatten(L["children"], depth + 1, L["id"], out)
    return out


def subtree_ids(flat, target):
    ids = [target["id"]]

    def walk(children):
        for c in children:
            ids.append(c["id"])
            walk(c.get("children") or [])
    walk(target["children"])
    return ids


def ancestors(flat, target):
    by_id = {t["id"]: t for t in flat}
    out = []
    p = by_id.get(target["parent"])
    while p:
        out.append(p["id"])
        p = by_id.get(p["parent"])
    return out


def parse_size(s):
    w, h = re.split(r"[x×,]", s.lower())
    return int(float(w)), int(float(h))


def main(argv=None):
    ap = argparse.ArgumentParser(description="PhotoCraft 导出 out_ 图层为透明 PNG + 回存 PSD")
    ap.add_argument("psd")
    ap.add_argument("out_dir")
    ap.add_argument("--prefix", default="out_")
    ap.add_argument("--canvas", help="导出前扩画布到 WxH（居中）")
    ap.add_argument("--texts", help="JSON：{图层名: 新文字}")
    ap.add_argument("--save-psd", help="回存路径（默认=输入 PSD）")
    ap.add_argument("--port", type=int)
    ap.add_argument("--no-save", action="store_true", help="只导 PNG，不回存 PSD")
    a = ap.parse_args(argv)

    psd = Path(a.psd).resolve()
    out_dir = Path(a.out_dir).resolve()
    if not psd.exists():
        raise SystemExit(f"!! 找不到 PSD：{psd}")
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    cli = PC.ensure(port=a.port)
    opened = cli.open_doc(str(psd))
    if opened.get("warnings"):
        print("  打开警告：" + "; ".join(opened["warnings"]))
    doc_index = (cli.request("ui.inspect", {}) or {}).get("session", {}).get("active")

    def activate():
        cli.engine("document.activate", {"document": doc_index})

    # ---- 可选的画布放大 / 文字改写 -----------------------------------
    if a.canvas:
        W, H = parse_size(a.canvas)
        cli.engine("image.canvasSize", {
            "width": W, "height": H, "relative": False,
            "anchor": "center", "extensionColor": "transparent"})
        print(f"  画布已放大到 {W}×{H}")

    flat = flatten(cli.inspect().get("layers") or [])
    if a.texts:
        raw = Path(a.texts).read_bytes()
        texts = None
        for enc in ("utf-8-sig", "utf-16", "utf-8", "gbk"):
            try:
                texts = json.loads(raw.decode(enc))
                break
            except Exception:
                continue
        if not isinstance(texts, dict):
            raise SystemExit(f"!! --texts 不是合法 JSON 对象：{a.texts}")
        for name, text in texts.items():
            hits = [t for t in flat if t["name"] == name]
            if not hits:
                raise SystemExit(f"!! --texts 里的图层不存在：{name}")
            if len(hits) > 1:
                raise SystemExit(f"!! --texts 图层名重复，无法唯一定位：{name}")
            cli.engine("type.edit", {"layer": hits[0]["id"], "text": text})
            print(f"  文字 {name} -> {text}")
        flat = flatten(cli.inspect().get("layers") or [])

    targets = [t for t in flat if t["name"].startswith(a.prefix)]
    if not targets:
        raise SystemExit(f"!! 没有以 {a.prefix} 开头的图层/组（先用 _rename_layer.py 加前缀）")
    targets.sort(key=lambda t: t["depth"])

    names = {}
    file_by_id = {}
    for t in targets:
        stem = t["name"][len(a.prefix):].strip() or t["name"]
        stem = BAD_CHARS.sub("_", stem)
        if stem in names:
            raise SystemExit(f"!! 导出文件名重复：{stem}（{t['name']} 与 {names[stem]}）")
        names[stem] = t["name"]
        file_by_id[t["id"]] = stem

    print(f"  目标 {len(targets)} 个：{', '.join(t['name'] for t in targets)}")

    original = {t["id"]: t["visible"] for t in flat}
    all_ids = [t["id"] for t in flat]

    def set_all(visible):
        # 逐层设置（组也设），避免只改父级导致子层状态被继承掩盖
        for lid in all_ids:
            try:
                cli.engine("layer.setProps", {"layer": lid, "visible": visible})
            except Exception:
                pass

    results = []
    try:
        for t in targets:
            keep = set(subtree_ids(flat, t)) | set(ancestors(flat, t))
            set_all(False)
            for lid in keep:
                cli.engine("layer.setProps", {"layer": lid, "visible": True})
            activate()
            dst = out_dir / (file_by_id[t["id"]] + ".png")
            cli.save_doc(str(dst))
            results.append(dst)
            print(f"    ✓ {dst.name}")
    finally:
        for lid, vis in original.items():
            try:
                cli.engine("layer.setProps", {"layer": lid, "visible": vis})
            except Exception:
                pass
        activate()

    # ---- 回存 PSD ---------------------------------------------------
    if not a.no_save:
        target = Path(a.save_psd).resolve() if a.save_psd else psd
        if target.exists():
            bak = target.with_name(target.name + ".pre-pc.bak")
            if not bak.exists():
                import shutil
                shutil.copy2(target, bak)
                print(f"  已备份旧副本 -> {bak.name}")
        cli.save_doc(str(target))
        print(f"  ★ 已回存 PSD：{target}")

    # ---- 简单校验 ----------------------------------------------------
    try:
        from PIL import Image
        from collections import Counter
    except Exception:
        Image = None
    if Image:
        print("\n  导出校验：")
        for p in results:
            im = Image.open(p).convert("RGBA")
            alpha = im.getchannel("A")
            box = alpha.getbbox()
            corners = [im.getpixel(c)[3] for c in
                       [(0, 0), (im.width - 1, 0), (0, im.height - 1),
                        (im.width - 1, im.height - 1)]]
            colors = Counter()
            for n, (rr, gg, bb, aa) in (im.getcolors(maxcolors=1 << 24) or []):
                if aa > 200:
                    colors[(rr, gg, bb)] += n
            colors = colors.most_common(3)
            hexcols = ["#%02X%02X%02X x%d" % (c[0], c[1], c[2], n) for c, n in colors]
            print(f"    {p.name:32} {im.size[0]}×{im.size[1]}  内容框={box}  "
                  f"四角α={corners}  主色={hexcols}")

    print(f"\n  完成 {len(results)} 张，用时 {time.time() - t0:.1f}s")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
