# -*- coding: utf-8 -*-
"""把一个 PSD 图层复制成若干份，各起一个名字。

用法：
    python _psd_clone.py <psd> --from <图层名> --names 名1,名2,名3 [--out <输出>]

- 每份都是原图层的**完整拷贝**：图层记录、额外数据（含 lfx2 图层样式、TySh 文字）
  和通道像素数据一起复制，所以样式/文字/不透明度全都跟着走。
- 原图层本身改成第一个名字，其余是新增的副本，紧挨着它插在上方。
- `lyid`（图层 ID）会自动改成不重复的新值，避免 Photoshop 报重复 ID。
- 只改结构、重算长度字段（layer-info 段长、layer-and-mask 段长、图层数），
  不碰任何像素与效果参数。
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _psd_struct import get_block, parse, serialize, set_block

MAX_PNG = 4096


def _luni_payload(name: str) -> bytes:
    """luni 块内容：u32 字符数 + UTF-16BE（不带结尾 NUL）。"""
    return struct.pack('>I', len(name)) + name.encode('utf-16-be')


def _set_luni(layer, name: str):
    layer.extra = set_block(layer.extra, b'luni', _luni_payload(name))
    return layer


def _max_lyid(st) -> int:
    top = 0
    for L in st['layers']:
        d = get_block(L.extra, b'lyid')
        if d is not None and len(d) >= 4:
            top = max(top, struct.unpack_from('>I', d, 0)[0])
    return top


def clone(src: str, layer_name: str, names, dst: str = None):
    """把 layer_name 复制成 len(names) 份。返回 (dst, 新图层名列表)。"""
    names = [str(n) for n in names]
    if not names:
        raise SystemExit('!! --names 不能为空')
    data = Path(src).read_bytes()
    st = parse(data)
    idx = None
    for i, L in enumerate(st['layers']):
        if L.name == layer_name:
            idx = i
            break
    if idx is None:
        raise SystemExit(f'!! 找不到图层 {layer_name!r}；现有图层：'
                         f'{[L.name for L in st["layers"]]}')

    top_lyid = _max_lyid(st)
    origin = st['layers'][idx]
    _set_luni(origin, names[0])

    clones = []
    for k, nm in enumerate(names[1:], start=1):
        c = origin.copy()
        _set_luni(c, nm)
        lyid = get_block(c.extra, b'lyid')
        if lyid is not None and len(lyid) >= 4:
            c.extra = set_block(c.extra, b'lyid',
                                struct.pack('>I', top_lyid + k) + lyid[4:])
        clones.append(c)

    st['layers'][idx + 1:idx + 1] = clones
    st['count'] = (abs(st['count']) + len(clones)) * (1 if st['count'] > 0 else -1)
    st['li_pad'] = b''                       # 填充由 serialize 重算

    dst = dst or src
    Path(dst).write_bytes(serialize(st))
    return dst, names


if __name__ == '__main__':
    import argparse
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='复制 PSD 图层并改名')
    ap.add_argument('psd')
    ap.add_argument('--from', dest='src_layer', required=True, help='要复制的图层名')
    ap.add_argument('--names', required=True,
                    help='逗号分隔的新图层名，第一个给原图层，其余是副本')
    ap.add_argument('--out', help='输出 PSD（默认原地改）')
    a = ap.parse_args()

    names = [s.strip() for s in a.names.split(',') if s.strip()]
    for n in names:
        if len(n.encode('utf-16-be')) // 2 > 255:
            raise SystemExit(f'!! 图层名过长（>{MAX_PNG}）：{n!r}')
    dst, got = clone(a.psd, a.src_layer, names, a.out)
    st = parse(Path(dst).read_bytes())
    print(f'{a.src_layer!r} → {len(got)} 个图层  ->  {dst}')
    for n in got:
        print(f'   {n}')
    print(f'现共 {abs(st["count"])} 个图层：{[L.name for L in st["layers"]]}')
