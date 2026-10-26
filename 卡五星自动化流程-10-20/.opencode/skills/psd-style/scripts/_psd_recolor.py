# -*- coding: utf-8 -*-
"""把某个组里"黄橙色系"的颜色换成另一种色系（栅格像素 + 形状填充 + 已启用图层效果色）。

为什么不能只改图层样式：本按钮的颜色**绝大部分来自栅格像素**（剪切蒙版的光泽/高光位图），
只改 SoCo/效果色在画面上根本看不出来。

换算口径（技能第六节，只换色相、不动饱和度）：

    源区间 H15~80 的像素/颜色 → 按两个锚点线性映射到目标色相，结果钳在目标区间
    饱和度按目标乘一个系数（默认 1.0 = 不变）；L ≥ 0.55 的亮部明度 +0.05
    S < 0.10（近白/近灰）或色相不在 H15~80（如近黑投影 #0D262B）→ 原样不动
    图层样式里**未启用**（enab=false）的槽不动 —— 它们本来就看不见

`--target` 预设（锚点见 `TARGETS`）：

    blue   黄橙 → 天蓝（默认；本项目 `选字.psd` 黄按钮 → 蓝按钮的既有对照）
    yellow 黄橙 → 亮黄（H24→46 / H42→54，钳 45~57；对应 `漂-按钮.psd` 橙按钮 → 亮黄）
    green  黄橙 → 绿  （H24→125 / H42→145，钳 118~150，饱和度×0.85）
    red    橙 → 红    （H24→358 / H42→350，钳 344~359；对应 `扣牌-按钮.psd` 橙按钮 → 红按钮）

用法：

    python _psd_recolor.py <psd> --group <组名> [--target yellow|green|red] [--out <out>]
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _psd_raster as R
import _psd_struct as S
from _psd_fx_color import norm
from _psd_group import find_group, find_group_by_lyid
from _psd_lfx import Reader, parse_block

FX_KEYS = (b'lfx2', b'lmfx')
COLOR_KEYS = ('rd', 'grn', 'bl')

# 目标色系预设：名字 → (src_a, dst_a, src_b, dst_b, clamp, lift, sat_scale, 说明)
TARGETS = {
    'blue': (42.0, 210.0, 53.0, 193.0, (185.0, 222.0), 0.05, 1.00,
             '黄橙 → 天蓝（H42→210 / H53→193，项目既有对照）'),
    'yellow': (24.0, 46.0, 42.0, 54.0, (45.0, 57.0), 0.05, 1.00,
               '黄橙 → 亮黄（H24→46 / H42→54，钳 45~57）'),
    'green': (24.0, 125.0, 42.0, 145.0, (118.0, 150.0), 0.05, 0.85,
              '黄橙 → 绿（H24→125 / H42→145，钳 118~150，饱和度×0.85）'),
    # 红：目标色相不跨 360（钳 344~359），所以锚点写成"越黄越低色相"
    # （H24→358、H42→350），和 blue 的 210/193 同一个走向，色相内部差异保留。
    'red': (24.0, 358.0, 42.0, 350.0, (344.0, 359.0), 0.05, 1.00,
            '橙 → 红（H24→358 / H42→350，钳 344~359）'),
}


def target_mapper(name: str):
    """按预设名造换算函数。"""
    if name not in TARGETS:
        raise SystemExit(f'!! 不认识的目标 {name!r}；可选：{sorted(TARGETS)}')
    sa, da, sb, db, clamp, lift, sat, _ = TARGETS[name]
    return R.make_mapper(sa, da, sb, db, clamp, lift=lift, sat_scale=sat)



# ------------------------------------------------------------------ 描述符


def payload_of(layer, key):
    for b in S.scan_blocks(layer.extra, S.blocks_offset(layer.extra)) or []:
        if b['key'] == key:
            return bytes(layer.extra[b['data_off']:b['data_off'] + b['size']])
    return None


def is_color(kids) -> bool:
    return (all(k in kids for k in COLOR_KEYS)
            and all(kids[k].typ == 'doub' for k in COLOR_KEYS))


def collect_colors(node, enabled, out):
    """收集"已启用"的容器下的颜色节点（enab 就近继承）。"""
    kids = norm(node)
    en = enabled
    if 'enab' in kids and kids['enab'].typ == 'bool':
        en = bool(kids['enab']._v)
    if en and is_color(kids):
        out.append(kids)
    for k, ch in node.children.items():
        if isinstance(k, int) or ch.typ in ('obj ', 'Objc', 'GlbO', 'VlLs'):
            collect_colors(ch, en, out)


def remap_color_nodes(payload, top, slot_name, report, mapper):
    """就地改 payload 里已启用槽的颜色，返回 (新 payload, 改动数)。"""
    nodes = []
    for _, slot in top.items():
        collect_colors(slot, False, nodes)
    if not nodes:
        return payload, 0
    buf = bytearray(payload)
    n = 0
    for kids in nodes:
        old = tuple(int(round(float(kids[k]._v))) for k in COLOR_KEYS)
        new = mapper(*old)
        if new == old:
            report.append(f'    {slot_name}: {R.hexs(old)} 不变（不在源色相区间）')
            continue
        for k, val in zip(COLOR_KEYS, new):
            buf[kids[k].start:kids[k].end] = b'doub' + struct.pack('>d', float(val))
        report.append(f'    {slot_name}: {R.hexs(old)} → {R.hexs(new)}')
        n += 1
    return bytes(buf), n


def recolor_styles(layer, report, mapper):
    """改 SoCo 填充色 + lfx2/lmfx 里已启用槽的颜色；返回改动数。"""
    n = 0
    for key in FX_KEYS:
        raw = payload_of(layer, key)
        if raw is None:
            continue
        top, _ = parse_block(raw)
        new, k = remap_color_nodes(raw, top, key.decode(), report, mapper)
        if k:
            layer.extra = S.set_block(layer.extra, key, new)
        n += k
        break                                  # lfx2 优先，和 _psd_fx_color 一致
    soco = payload_of(layer, b'SoCo')
    if soco is not None:
        top, _ = Reader(soco, 4).descriptor()
        kids = norm(norm(_Fake(top)).get('clr'))
        if is_color(kids):
            old = tuple(int(round(float(kids[k]._v))) for k in COLOR_KEYS)
            new = mapper(*old)
            if new != old:
                buf = bytearray(soco)
                for k, val in zip(COLOR_KEYS, new):
                    buf[kids[k].start:kids[k].end] = b'doub' + struct.pack('>d', float(val))
                layer.extra = S.set_block(layer.extra, b'SoCo', bytes(buf))
                report.append(f'    SoCo 填充: {R.hexs(old)} → {R.hexs(new)}')
                n += 1
    return n


class _Fake:
    """把描述符根套一层，好让 norm() 统一处理。"""

    def __init__(self, kids):
        self.children = kids or {}


# ------------------------------------------------------------------ CLI


def recolor(psd, group, out, target='blue', group_lyid=None):
    data = Path(psd).read_bytes()
    st = S.parse(data)
    info = find_group_by_lyid(st, group_lyid) if group_lyid is not None else find_group(st, group)
    layers = st['layers']
    mapper = target_mapper(target)
    gname = layers[info['header']].name
    how = f'lyid={group_lyid}' if group_lyid is not None else '按名'
    print(f'组 {gname!r}（{how}）：分隔符 [{info["divider"]}]，组头 [{info["header"]}]，'
          f'{len(info["members"])} 个子层')
    print(f'目标色系：{target} —— {TARGETS[target][7]}')

    total_px = total_col = 0
    for i in info['members']:
        L = layers[i]
        report = []
        w, h = R.layer_size(L)
        px = 0
        if w * h:
            _, _, rgba = R.read_image(L)
            px = R.remap_rgba_inplace(rgba, mapper)
            if px:
                R.write_image(L, L.rect(), rgba)
        col = recolor_styles(L, report, mapper)
        total_px += px
        total_col += col
        print(f'  [{i}] {L.name!r:18} {w}×{h}  像素 {px} 个换色   样式色 {col} 处')
        for line in report:
            print(line)

    st['li_pad'] = b''
    Path(out).write_bytes(S.serialize(st))
    print(f'\n合计：像素 {total_px} 个、样式色 {total_col} 处 → {target}')
    print(f'写出 {out}  （{len(data)} → {len(Path(out).read_bytes())} 字节）')
    return total_px + total_col


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='把组里的黄橙色系颜色换成目标色系')
    ap.add_argument('psd')
    ap.add_argument('--group', help='组名（与 --组lyid 二选一）')
    ap.add_argument('--组lyid', type=int, dest='group_lyid',
                    help='按 lyid 定位组（组名可重复时用；与 --group 二选一）')
    ap.add_argument('--target', default='blue',
                    help=f'目标色系预设，可选 {sorted(TARGETS)}（默认 blue = 天蓝）')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    if a.group is None and a.group_lyid is None:
        ap.error('要给 --group 或 --组lyid')
    return 0 if recolor(a.psd, a.group, a.out or a.psd, a.target, a.group_lyid) else 1


if __name__ == '__main__':
    sys.exit(main())
