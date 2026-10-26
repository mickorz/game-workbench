# -*- coding: utf-8 -*-
"""九宫格式重排矢量形状 + 同映射重采样组内栅格（把按钮从 A 尺寸改成 B 尺寸）。

为什么不直接"整张拉伸"：`圆角矩形 5` 是**矢量形状层**，圆角半径写死在路径上
（vmsk 的 8 个结点）+ vogk 的实时形状元数据里。整张等比拉伸会把圆角拉成椭圆、
把光泽一起糊掉。正确做法（用户口径）：

    四角圆弧保持原半径、只把角点外移；**只拉伸中间那段**（栅格同样按这个分段线性映射重采样）

映射（分段线性，逐轴独立）：

    源 [s0, s0+r] → [t0, t0+r]      刚性（角区，整体平移）
    源 [s0+r, s1-r] → [t0+r, t1-r]  中间段拉伸
    源 [s1-r, s1] → [t1-r, t1]      刚性（角区）
    bbox 之外的像素按最近段斜率刚性外推

要改的两处（必须一致，Photopea/PS 谁读哪个都行）：

1. `vmsk` 路径：8 个结点 × 3 点 × (y,x)，坐标是**按画布尺寸归一化**的 8.24 定点
   （实测：×176 / ×86 后与 vogk 的 bbox 分毫不差）；
2. `vogk` 的 `keyOriginShapeBBox` 4 个 double（Top/Left/Btom/Rght，文档坐标）。

用法：

    python _psd_reshape.py <psd> --group <组名> --bbox x0,y0,x1,y1 [--radius R] --out <out>
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _psd_raster as R
import _psd_struct as S
from _psd_group import clipping, find_group, find_group_by_lyid

FIXED = 0x01000000
KNOT_SEL = (1, 2, 4, 5)


# ------------------------------------------------------------------ 路径/vogk


def records(blk):
    """vmsk 记录偏移：每条 = u16 selector + 24 字节载荷（末尾可能有 <26 字节填充）。"""
    q, out = 8, []
    while q + 26 <= len(blk):
        out.append((struct.unpack_from('>H', blk, q)[0], q))
        q += 26
    return out


def knot_points(blk, W, H):
    """所有结点控制点 → [(记录偏移, 第几个点, 文档坐标 x, 文档坐标 y)]。"""
    pts = []
    for sel, off in records(blk):
        if sel not in KNOT_SEL:
            continue
        for k in range(3):
            yi, xi = struct.unpack_from('>ii', blk, off + 2 + k * 8)
            pts.append((off, k, xi / FIXED * W, yi / FIXED * H))
    return pts


def shape_bbox(pts):
    xs = [p[2] for p in pts]
    ys = [p[3] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def axis_map(s0, s1, t0, t1, r):
    """分段线性映射，返回 (正算, 反算)。"""
    if s1 - s0 <= 2 * r or t1 - t0 <= 2 * r:
        raise SystemExit(f'!! 形状比圆角还小：源 {s1-s0:.3f} 目标 {t1-t0:.3f} 半径 {r}')
    xs = (s0, s0 + r, s1 - r, s1)
    ys = (t0, t0 + r, t1 - r, t1)

    def seg(v, a, b):
        for k in range(3):
            if v <= a[k + 1] or k == 2:
                d = a[k + 1] - a[k]
                slope = (b[k + 1] - b[k]) / d if d else 1.0
                return b[k] + (v - a[k]) * slope
        raise AssertionError

    return (lambda x: seg(x, xs, ys)), (lambda X: seg(X, ys, xs))


def rewrite_knots(blk, fx, fy, W, H):
    out = bytearray(blk)
    n = 0
    for sel, off in records(out):
        if sel not in KNOT_SEL:
            continue
        for k in range(3):
            p = off + 2 + k * 8
            yi, xi = struct.unpack_from('>ii', out, p)
            xn, yn = fx(xi / FIXED * W), fy(yi / FIXED * H)
            struct.pack_into('>ii', out, p,
                             int(round(yn / H * FIXED)), int(round(xn / W * FIXED)))
            n += 1
    return bytes(out), n


def vogk_slots(vg):
    """vogk 里 bbox / 半径的 double 偏移（只在对应对象内部找，避免 Left 撞 topLeft）。"""
    slots = {}

    anchor = vg.find(b'keyOriginShapeBBox')
    if anchor < 0:
        raise SystemExit('!! vogk 里没有 keyOriginShapeBBox')
    for key, name in ((b'Top ', 'top'), (b'Left', 'left'),
                      (b'Btom', 'bottom'), (b'Rght', 'right')):
        pat = key + b'UntF#Pxl'
        i = vg.find(pat, anchor)
        if i < 0 or vg.find(pat, i + 1) >= 0:
            raise SystemExit(f'!! keyOriginShapeBBox 里找不到唯一的 {key!r}')
        slots[name] = i + len(pat)

    anchor = vg.find(b'keyOriginRRectRadii')
    if anchor < 0:
        raise SystemExit('!! vogk 里没有 keyOriginRRectRadii')
    radii, j = [], anchor
    while len(radii) < 4:
        j = vg.find(b'UntF#Pxl', j + 1)
        if j < 0:
            raise SystemExit('!! vogk 半径不足 4 个')
        radii.append(j + len(b'UntF#Pxl'))
    slots['radii'] = radii
    return slots


# ------------------------------------------------------------------ 栅格重采样


def _sample(rgba, w, h, sx, sy):
    x0, y0 = math.floor(sx), math.floor(sy)
    tx, ty = sx - x0, sy - y0
    acc = [0.0, 0.0, 0.0, 0.0]
    for dy in (0, 1):
        yy = y0 + dy
        if yy < 0 or yy >= h:
            continue
        wy = (1 - ty) if dy == 0 else ty
        base = yy * w
        for dx in (0, 1):
            xx = x0 + dx
            if xx < 0 or xx >= w:
                continue
            wx = (1 - tx) if dx == 0 else tx
            k = (base + xx) * 4
            g = wx * wy
            acc[0] += rgba[k] * g
            acc[1] += rgba[k + 1] * g
            acc[2] += rgba[k + 2] * g
            acc[3] += rgba[k + 3] * g
    return acc


def resample_layer(L, fx, fy, ix, iy, W, H):
    """按同一映射重采样一个图层的栅格；矩形重算并钳在画布内。"""
    t, l, b, r = L.rect()
    w, h = r - l, b - t
    if w * h == 0:
        return None
    _, _, rgba = R.read_image(L)
    nt = max(0, math.floor(fy(t)))
    nb = min(H, math.ceil(fy(b)))
    nl = max(0, math.floor(fx(l)))
    nr = min(W, math.ceil(fx(r)))
    nw, nh = nr - nl, nb - nt
    if nw <= 0 or nh <= 0:
        return None
    out = bytearray(nw * nh * 4)
    for oy in range(nh):
        v = iy(nt + oy + 0.5) - t - 0.5
        row = oy * nw * 4
        for ox in range(nw):
            u = ix(nl + ox + 0.5) - l - 0.5
            px = _sample(rgba, w, h, u, v)
            k = row + ox * 4
            for c in range(4):
                val = px[c]
                out[k + c] = 0 if val <= 0 else (255 if val >= 255 else int(round(val)))
    if not R.write_image(L, (nt, nl, nb, nr), out):
        return None
    return (t, l, b, r), (nt, nl, nb, nr)


# ------------------------------------------------------------------ CLI


def reshape(psd, group, bbox, out, radius=None, group_lyid=None):
    data = Path(psd).read_bytes()
    st = S.parse(data)
    W, H = struct.unpack_from('>II', data, 18)[0], struct.unpack_from('>II', data, 14)[0]
    info = find_group_by_lyid(st, group_lyid) if group_lyid is not None else find_group(st, group)
    layers = st['layers']
    gname = layers[info['header']].name

    base_idx = [i for i in info['members'] if clipping(layers[i]) == 0]
    if not base_idx:
        raise SystemExit(f'!! 组 {gname!r} 里没有 clip=0 的剪切基底')

    # 组里**所有** clip=0 的矢量形状层都要重排：实测 `源文件\扣牌-按钮.psd` 的
    # `组 5` 里"亮面"和"深色底"两层都是 clip=0 的形状层，只认第一层会让另一层
    # 留在原尺寸。源 bbox 取它们的**并集**（= 用户看到的整个按钮外形），
    # 映射对全组统一，每层再拿自己的 vogk bbox 过一遍同一个映射写回。
    bases = [layers[i] for i in base_idx
             if S.get_block(layers[i].extra, b'vmsk') is not None]
    if not bases:
        raise SystemExit(f'!! 剪切基底里没有矢量形状层（缺 vmsk）')

    geoms = []
    for L in bases:
        vm = S.get_block(L.extra, b'vmsk')
        pts = knot_points(vm, W, H)
        vg = S.get_block(L.extra, b'vogk')
        slots = None
        box = None
        if vg is not None:
            try:
                slots = vogk_slots(vg)
                box = tuple(struct.unpack_from('>d', vg, slots[k])[0]
                            for k in ('top', 'left', 'bottom', 'right'))
            except SystemExit:
                slots = box = None
        geoms.append({'vmsk': vm, 'pts': pts, 'bbox': shape_bbox(pts),
                      'vogk': vg, 'slots': slots, 'box': box})

    s = (min(g['bbox'][0] for g in geoms), min(g['bbox'][1] for g in geoms),
         max(g['bbox'][2] for g in geoms), max(g['bbox'][3] for g in geoms))

    vg_r = None
    for g in geoms:
        if g['slots']:
            r0 = struct.unpack_from('>d', g['vogk'], g['slots']['radii'][0])[0]
            vg_r = r0 if vg_r is None else max(vg_r, r0)

    # 半径默认取 vogk 现值，但不能超过源/目标尺寸的一半（胶囊形状 r 正好 = 高/2）
    rad = float(radius) if radius else (vg_r if vg_r else 5.0)
    rad = min(rad, (s[2] - s[0]) / 2 - 1e-6, (s[3] - s[1]) / 2 - 1e-6,
              (bbox[2] - bbox[0]) / 2 - 1e-6, (bbox[3] - bbox[1]) / 2 - 1e-6)

    print(f'剪切基底 {len(bases)} 层：')
    for L, g in zip(bases, geoms):
        b = g['bbox']
        line = (f"  {L.name!r:18} vmsk ({b[0]:.4f}, {b[1]:.4f})-({b[2]:.4f}, {b[3]:.4f})"
                f"  {b[2]-b[0]:.4f}×{b[3]-b[1]:.4f}")
        if g['box']:
            gb = g['box']
            line += (f"   vogk ({gb[1]:.4f}, {gb[0]:.4f})-({gb[3]:.4f}, {gb[2]:.4f})"
                     f" 半径 {struct.unpack_from('>d', g['vogk'], g['slots']['radii'][0])[0]:.4f}")
        print(line)
    print(f'源 bbox（全组并集）：({s[0]:.4f}, {s[1]:.4f})-({s[2]:.4f}, {s[3]:.4f})  '
          f'{s[2]-s[0]:.4f}×{s[3]-s[1]:.4f}')
    print(f'目标 bbox        ：({bbox[0]}, {bbox[1]})-({bbox[2]}, {bbox[3]})  '
          f'{bbox[2]-bbox[0]}×{bbox[3]-bbox[1]}   半径 {rad:.4f}')

    fx, ix = axis_map(s[0], s[2], bbox[0], bbox[2], rad)
    fy, iy = axis_map(s[1], s[3], bbox[1], bbox[3], rad)
    for tag, a0, a1, b0, b1 in (('X', s[0], s[2], bbox[0], bbox[2]),
                                ('Y', s[1], s[3], bbox[1], bbox[3])):
        mid_s, mid_t = a1 - a0 - 2 * rad, b1 - b0 - 2 * rad
        k = (mid_t / mid_s) if mid_s > 1e-9 else float('nan')
        print(f'中间段拉伸      ：{tag} [{a0+rad:.3f},{a1-rad:.3f}] → '
              f'[{b0+rad:.1f},{b1-rad:.1f}]  ×{k:.4f}'
              + ('（源中段≈0，两端按平移）' if mid_s <= 1e-9 else ''))

    print('\nvmsk / vogk 重排：')
    for L, g in zip(bases, geoms):
        new_vmsk, n = rewrite_knots(g['vmsk'], fx, fy, W, H)
        L.extra = S.set_block(L.extra, b'vmsk', new_vmsk)
        ns = shape_bbox(knot_points(new_vmsk, W, H))
        print(f"  {L.name!r:18} {n} 个控制点 → bbox ({ns[0]:.4f}, {ns[1]:.4f})-"
              f"({ns[2]:.4f}, {ns[3]:.4f})  {ns[2]-ns[0]:.4f}×{ns[3]-ns[1]:.4f}")
        if g['slots'] and g['box'] is not None:
            t, l, b, r = g['box']
            nb = (fy(t), fx(l), fy(b), fx(r))
            vg = bytearray(g['vogk'])
            for key, val in zip(('top', 'left', 'bottom', 'right'), nb):
                struct.pack_into('>d', vg, g['slots'][key], float(val))
            L.extra = S.set_block(L.extra, b'vogk', bytes(vg))
            print(f"      vogk keyOriginShapeBBox → ({nb[1]:.4f}, {nb[0]:.4f})-"
                  f"({nb[3]:.4f}, {nb[2]:.4f})   半径保持")

    print('\n栅格同映射重采样：')
    for i in info['members']:
        L = layers[i]
        got = resample_layer(L, fx, fy, ix, iy, W, H)
        if got is None:
            print(f'  [{i}] {L.name!r:18} 跳过（零尺寸）')
            continue
        (t, l, b, r), (nt, nl, nb, nr) = got
        print(f'  [{i}] {L.name!r:18} ({l},{t})-({r},{b}) {r-l}×{b-t}'
              f'  →  ({nl},{nt})-({nr},{nb}) {nr-nl}×{nb-nt}')

    st['li_pad'] = b''
    Path(out).write_bytes(S.serialize(st))
    print(f'\n写出 {out}  （{len(data)} → {Path(out).stat().st_size} 字节）')
    return out


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='九宫格式重排矢量形状 + 重采样组内栅格')
    ap.add_argument('psd')
    ap.add_argument('--group', help='组名（与 --组lyid 二选一）')
    ap.add_argument('--组lyid', type=int, dest='group_lyid',
                    help='按 lyid 定位组（组名可重复时用；与 --group 二选一）')
    ap.add_argument('--bbox', required=True, help='新 bbox：x0,y0,x1,y1（文档坐标）')
    ap.add_argument('--radius', type=float, help='圆角半径（默认取 vogk 里的现值）')
    ap.add_argument('--out', help='输出 PSD（默认原地改）')
    a = ap.parse_args(argv)
    if a.group is None and a.group_lyid is None:
        ap.error('要给 --group 或 --组lyid')
    bbox = tuple(float(v) for v in a.bbox.replace('×', ',').split(','))
    if len(bbox) != 4:
        raise SystemExit('!! --bbox 应为 x0,y0,x1,y1')
    return 0 if reshape(a.psd, a.group, bbox, a.out or a.psd, a.radius, a.group_lyid) else 1


if __name__ == '__main__':
    sys.exit(main())
