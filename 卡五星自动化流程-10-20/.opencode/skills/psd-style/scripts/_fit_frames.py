# -*- coding: utf-8 -*-
"""把一批透明 PNG 统一成同一个画布尺寸，内容居中。

用法：
    python _fit_frames.py <目录> [--files a.png,b.png] [--pad 0] [--size 240x60] [--suffix ""]

- 每张先按 alpha 通道裁到内容框（透明的投影也算内容），
- 画布尺寸默认取"最大的那张内容框"（`--size` 可指定固定尺寸），
- 再把每张内容贴到画布正中，所以各张的视觉中心互相对齐。
- 默认原地覆盖；`--suffix` 可输出成新名字（如 `--suffix _fit`）。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')


def content_box(im: Image.Image):
    """透明 PNG 的内容框（按 alpha 判断）。"""
    a = im.convert('RGBA').getchannel('A')
    return a.getbbox(), im.convert('RGBA')


def fit(paths, pad=0, size=None, suffix=''):
    """统一尺寸并居中；返回 [(路径, 内容尺寸, 画布尺寸)]。"""
    items = []
    for p in paths:
        im = Image.open(p).convert('RGBA')
        box, im = content_box(im)
        if box is None:
            raise SystemExit(f'!! {p} 整张全透明，没有内容可对')
        items.append([Path(p), im.crop(box), (box[2] - box[0], box[3] - box[1])])

    if size:
        W, H = size
        for p, crop, (w, h) in items:
            if w > W or h > H:
                raise SystemExit(f'!! {p.name} 内容 {w}×{h} 超过指定画布 {W}×{H}')
    else:
        W = max(w for _, _, (w, h) in items) + 2 * pad
        H = max(h for _, _, (w, h) in items) + 2 * pad

    out = []
    for p, crop, (w, h) in items:
        canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        canvas.paste(crop, ((W - w) // 2, (H - h) // 2))
        dst = p.with_name(p.stem + suffix + p.suffix) if suffix else p
        canvas.save(dst)
        out.append((dst, (w, h), (W, H)))
    return out


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description='一批透明 PNG 统一画布尺寸并居中')
    ap.add_argument('dir')
    ap.add_argument('--files', help='逗号分隔的文件名；不给就取目录里全部 png')
    ap.add_argument('--pad', type=int, default=0, help='内容四周留白像素')
    ap.add_argument('--size', metavar='WxH', help='固定画布尺寸（默认取最大的内容框）')
    ap.add_argument('--suffix', default='', help='输出文件名后缀（默认原地覆盖）')
    a = ap.parse_args(argv)

    d = Path(a.dir)
    if a.files:
        paths = [d / s.strip() for s in a.files.split(',') if s.strip()]
    else:
        paths = sorted(d.glob('*.png'))
    if not paths:
        raise SystemExit(f'!! {d} 里没有 PNG')
    for p in paths:
        if not p.exists():
            raise SystemExit(f'!! 找不到 {p}')

    size = None
    if a.size:
        w, h = a.size.lower().replace('×', 'x').split('x')
        size = (int(w), int(h))

    print(f'待处理 {len(paths)} 张  留白 {a.pad}px  '
          f'目标尺寸 {a.size or "取最大内容框"}')
    res = fit(paths, a.pad, size, a.suffix)
    for p, (w, h), (W, H) in res:
        print(f'  {p.name:36} 内容 {w:4}×{h:<4} → 画布 {W}×{H}  '
              f'居中偏移 ({(W - w) // 2}, {(H - h) // 2})')
    sizes = {(W, H) for _, _, (W, H) in res}
    print(f'尺寸种类：{len(sizes)}  {"一致 ✓" if len(sizes) == 1 else "不一致 ✗"}  {sizes}')
    return 0 if len(sizes) == 1 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
