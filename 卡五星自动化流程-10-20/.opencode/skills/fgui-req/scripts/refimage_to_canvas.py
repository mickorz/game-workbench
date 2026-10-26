#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s1 参考图适配：把 `参考图/` 下的截图适配成画布尺寸（默认 1334x750）。

规则（见 08 计划）：
- **同位比** → 直接 resize 到画布；
- **异位比** → 按高缩放居中，四周填**纯黑**（不留安全边）；若按高会超宽，则改按宽缩放兜底。
- 输出到同目录的 `参考图_1334x750/`，并**回填** `清单.json` 里对应条目的 `参考图_1334x750`。

需要 **Pillow**。用法（工作区根执行）：
  python .opencode/skills/fgui-req/scripts/refimage_to_canvas.py --out .opencode/work/<game_key>/<需求>
  python .opencode/skills/fgui-req/scripts/refimage_to_canvas.py --out <需求目录> --canvas 1334x750

退出码：0 成功；1 失败。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOTOPEN = HERE.parents[2]
sys.path.insert(0, str(DOTOPEN / "lib"))
import workspace as W  # noqa: E402

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
SIZE_RE = re.compile(r"^\s*(\d+)\s*[x×]\s*(\d+)\s*$")


def setup_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def to_canvas(img, cw: int, ch: int):
    from PIL import Image

    w, h = img.size
    canvas = Image.new("RGB", (cw, ch), (0, 0, 0))
    same_ratio = abs(w * ch - h * cw) <= max(2, cw)      # 位比一致（容忍 1px 取整）
    if same_ratio:
        nw, nh = cw, ch
    else:
        nw, nh = max(1, round(w * ch / h)), ch           # 按高缩放
        if nw > cw:                                      # 过宽 → 改按宽兜底
            nw, nh = cw, max(1, round(h * cw / w))
    resized = img.convert("RGBA").resize((nw, nh), Image.LANCZOS)
    canvas.paste(resized, ((cw - nw) // 2, (ch - nh) // 2), resized)
    return canvas


def main(argv=None) -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description="参考图 → 画布尺寸（纯黑填充居中）")
    ap.add_argument("--out", required=True, help="需求目录（含 参考图/ 与 清单.json）")
    ap.add_argument("--canvas", default="1334x750", help="画布尺寸 WxH（默认 1334x750）")
    ap.add_argument("--src", default=None, help="源图目录（默认 <out>/参考图）")
    args = ap.parse_args(argv)

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        raise SystemExit("!! 需要 Pillow（pip install Pillow）")

    m = SIZE_RE.match(args.canvas)
    if not m:
        raise SystemExit(f"!! --canvas 要写成 WxH：{args.canvas}")
    cw, ch = int(m.group(1)), int(m.group(2))

    out = Path(args.out).resolve()
    if args.src:
        src = Path(args.src).resolve()
        if not src.is_dir():
            raise SystemExit(f"!! 源目录不存在：{src}")
    else:
        src = out / "参考图"
        if not src.is_dir():
            print(f"· 没有参考图目录（{src}），跳过适配（参考图可选）")
            return 0
    imgs = sorted(p for p in src.iterdir() if p.suffix.lower() in IMG_EXT)
    if not imgs:
        print(f"· {src} 里没有图片，跳过")
        return 0

    dest = out / "参考图_1334x750"
    dest.mkdir(parents=True, exist_ok=True)

    from PIL import Image
    out_names: dict[str, str] = {}
    for p in imgs:
        with Image.open(p) as im:
            canvas = to_canvas(im, cw, ch)
        target = dest / f"{p.stem}.png"
        canvas.save(target, "PNG")
        out_names[p.name] = target.name
        print(f"  ✓ {p.name} → {target.name}  ({cw}x{ch})")

    # 回填清单：需求条目里 参考图 basename 命中的，写 参考图_1334x750
    mp = out / "清单.json"
    if mp.is_file():
        data = W.load_manifest(mp)
        n = 0
        for r in data.get("需求", []):
            ref = str(r.get("参考图", "")).replace("\\", "/")
            base = Path(ref).name
            if base in out_names:
                r["参考图_1334x750"] = f"参考图_1334x750/{out_names[base]}"
                n += 1
        W.save_manifest(mp, data)
        print(f"✓ 回填清单 {n} 条：{mp}")
    else:
        print(f"· 无 清单.json，跳过回填（{mp}）")
    print(f"✓ 适配完成 {len(imgs)} 张 → {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
