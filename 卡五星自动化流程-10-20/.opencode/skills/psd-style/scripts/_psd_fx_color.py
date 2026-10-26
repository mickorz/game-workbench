# -*- coding: utf-8 -*-
"""按「描述符路径」改 PSD 里的**图层效果颜色**和**形状填充色**（等长替换）。

为什么不用 `_psd_lfx.py --set-color`：那个脚本认的是 lfx2 的**固定槽位名**
（`GrFl` / `sofi` / `FrFX`…）。本项目 `源文件\\漂-小结算.psd` 的 `Kuang` 层套不上：

  * 效果块键是 **`lmfx`**（不是 `lfx2`），块内结构一样（u32 版本 + u32 描述符版本 + 描述符）；
  * 渐变叠加槽叫 **`gradientFillMulti`**，里面是 VlLs，**可以有好几个渐变**（该层就有 3 个）；
  * 形状图层的填充色在 **`SoCo`** 块里（u32 版本 + 描述符，比效果块少一个描述符版本字段）。

所以这里只做一件事：**按路径定位到 `Clr ` 的三个 `doub` 分量，原地换值**。
每个分量都是固定 8 字节 double，改动**等长** —— 块长度、额外数据长度、各段长度字段全都不用碰。

路径语法（键名大小写不敏感、尾部空格忽略；`fx` = 效果块，`SoCo` = 形状填充块）：

    SoCo.Clr                                     形状填充色
    fx.gradientFillMulti[0].Grad.Clrs[0].Clr     第 1 个渐变叠加的第 1 个色标
    fx.FrFX.Grad.Clrs[1].Clr                     描边渐变的第 2 个色标
    fx.IrGl.Clr                                  内发光的颜色

用法：

    python _psd_fx_color.py --list <psd> <图层名>
    python _psd_fx_color.py --set  <psd> <图层名> <路径>=<RRGGBB> [...] --out <输出psd>
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _psd_struct as S
from _psd_lfx import Reader, locate, match_layer, layer_block, parse_block

FX_KEYS = (b'lfx2', b'lmfx')          # 先 lfx2（标准），再 lmfx（本项目的写法）


# ------------------------------------------------------------------ helpers

def norm(node) -> dict:
    """子节点索引：键名去空格转小写；VlLs 的整数下标保持整数。"""
    if node is None:
        return {}
    out = {}
    for k, v in node.children.items():
        out[int(k) if isinstance(k, int) else str(k).strip().lower()] = v
    return out


def _slot_file(data, layer):
    """(块键, 块字节) —— 优先 lfx2，退回 lmfx。"""
    for key in FX_KEYS:
        blk = layer_block(data, layer, key)
        if blk is not None:
            return key, data[blk['data_off']:blk['data_off'] + blk['size']]
    return None, None


def hexs(rgb) -> str:
    return '#%02X%02X%02X' % tuple(int(round(max(0.0, min(255.0, v)))) for v in rgb)


def load(psd, layer_name):
    """解析出定位信息 + 两棵描述符树。"""
    data = Path(psd).read_bytes()
    doc = locate(data)
    layer = doc['layers'][match_layer(doc, layer_name)]

    fx_key, fx_raw = _slot_file(data, layer)
    fx_top = None
    if fx_raw is not None:
        fx_top, _ = parse_block(bytes(fx_raw))       # u32 版本 + u32 描述符版本 + 描述符

    soco_raw = None
    soco_top = None
    b = layer_block(data, layer, b'SoCo')
    if b is not None:
        soco_raw = data[b['data_off']:b['data_off'] + b['size']]
        r = Reader(bytes(soco_raw), 4)               # SoCo：u32 版本 + 描述符
        soco_top, _ = r.descriptor()

    return {'data': data, 'doc': doc, 'layer': layer,
            'fx_key': fx_key, 'fx_raw': fx_raw, 'fx_top': fx_top,
            'soco_raw': soco_raw, 'soco_top': soco_top}


def resolve(info, path):
    """把路径解析成 (块原始字节, 块在文件里的绝对起点, 该路径的描述符节点)。"""
    parts = [p for p in path.split('.') if p != '']
    if not parts:
        raise SystemExit('!! 路径为空')
    head = parts[0].strip().lower()
    if head == 'soco':
        raw, base = info['soco_raw'], info['doc']
        node = _wrap(info['soco_top'])
        rest = parts[1:]
    elif head == 'fx':
        raw = info['fx_raw']
        node = _wrap(info['fx_top'])
        rest = parts[1:]
    else:
        raise SystemExit(f'!! 路径要以 SoCo 或 fx 开头，收到 {path!r}')
    if raw is None:
        raise SystemExit(f'!! 图层 {info["layer"]["name"]!r} 没有 {head} 块')

    for tok in rest:
        m = re.match(r'^([^\[\]]*)(?:\[(\d+)\])?$', tok)
        if not m:
            raise SystemExit(f'!! 路径片段看不懂：{tok!r}')
        key, idx = m.group(1).strip().lower(), m.group(2)
        kids = norm(node)
        if key and key not in kids:
            raise SystemExit(f'!! 路径 {path!r}：{tok!r} 处没有 {key!r}；'
                             f'现有子键 {sorted(str(k) for k in kids)}')
        if key:
            node = kids[key]
        if idx is not None:
            kids2 = {k: v for k, v in norm(node).items() if isinstance(k, int)}
            if int(idx) not in kids2:
                raise SystemExit(f'!! 路径 {path!r}：下标 [{idx}] 越界（共 {len(kids2)} 项）')
            node = kids2[int(idx)]
    return raw, info['layer'], node


def _wrap(top):
    """给描述符根套一个假节点，好让 norm() 统一处理。"""
    class _Root:
        pass
    r = _Root()
    r.children = top if top is not None else {}
    return r


def color_of(node):
    kids = norm(node)
    if not all(k in kids for k in ('rd', 'grn', 'bl')):
        return None
    return tuple(float(kids[k]._v) for k in ('rd', 'grn', 'bl'))


# ------------------------------------------------------------------ list / set

def cmd_list(psd, layer_name):
    info = load(psd, layer_name)
    L = info['layer']
    print(f'图层 {L["name"]!r}  块：{[b["key"].decode("latin1") for b in L["blocks"]]}')

    if info['soco_top'] is not None:
        node = norm(_wrap(info['soco_top'])).get('clr')
        c = color_of(node) if node is not None else None
        print(f'\n[SoCo 形状填充]   '
              + (f'SoCo.Clr = {hexs(c)}  rgb={tuple(round(v, 2) for v in c)}' if c else '没找到 Clr'))

    if info['fx_top'] is None:
        print(f'\n[效果]  没有 {"/".join(k.decode() for k in FX_KEYS)} 块')
        return
    print(f'\n[{info["fx_key"].decode()} 图层效果]  {len(info["fx_top"])} 个槽')
    print('  %-52s %-24s %s' % ('槽 / 路径', '开关', '颜色路径 = 现值'))
    for name, node in info['fx_top'].items():
        _dump_tree(str(name).strip(), node, 0)


def _dump_tree(path, node, depth):
    ind = '  ' * depth
    kids = norm(node)
    flags = {k: kids[k]._v for k in ('enab', 'present') if k in kids and kids[k].typ == 'bool'}
    c = color_of(node)
    flag_s = (f'enab={flags.get("enab")} present={flags.get("present")}') if flags else ''
    col_s = f'fx.{path} = {hexs(c)}' if c is not None else ''
    if flag_s or col_s:
        print('  %-52s %-24s %s' % (ind + path.split('.')[-1], flag_s, col_s))
    for k, child in node.children.items():
        if isinstance(k, int):
            _dump_tree(f'{path}[{k}]', child, depth)
        elif child.typ in ('obj ', 'Objc', 'GlbO', 'VlLs'):
            _dump_tree(f'{path}.{str(k).strip()}', child, depth + 1)


def cmd_set(psd, layer_name, edits, out):
    info = load(psd, layer_name)
    data = info['data']
    doc = info['doc']
    layer = info['layer']
    out_buf = bytearray(data)
    changed = []

    for path, rgb in edits:
        raw, _, node = resolve(info, path)
        # 该路径所属块的绝对起点
        if path.split('.')[0].strip().lower() == 'soco':
            blk = layer_block(data, layer, b'SoCo')
        else:
            blk = layer_block(data, layer, info['fx_key'])
        base = blk['data_off']

        kids = norm(node)
        if not all(k in kids for k in ('rd', 'grn', 'bl')):
            raise SystemExit(f'!! 路径 {path!r} 不是颜色节点')
        old = color_of(node)
        for k, val in zip(('rd', 'grn', 'bl'), rgb):
            n = kids[k]
            if n.typ != 'doub':
                raise SystemExit(f'!! 路径 {path!r} 的 {k} 不是 doub（类型 {n.typ}）')
            out_buf[base + n.start:base + n.end] = b'doub' + struct.pack('>d', float(val))
        changed.append((path, old, rgb))

    if len(out_buf) != len(data):
        raise SystemExit('!! 长度变了，说明不是等长替换，拒绝写出')
    Path(out).write_bytes(bytes(out_buf))
    print(f'{len(changed)} 处颜色改完 → {out}')
    for path, old, new in changed:
        print(f'  {path:46} {hexs(old)} → {hexs(new)}')
    n_diff = sum(1 for a, b in zip(data, out_buf) if a != b)
    print(f'  字节级差异 {n_diff} 字节（预期 = 处数 × 24）')
    return out


def main(argv=None):
    import argparse
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='按路径改 PSD 图层效果 / 形状填充的颜色（等长替换）')
    ap.add_argument('--list', nargs=2, metavar=('PSD', '图层名'))
    ap.add_argument('--set', nargs=2, metavar=('PSD', '图层名'))
    ap.add_argument('--out')
    ap.add_argument('edits', nargs='*', help='路径=RRGGBB（--set 用）')
    a = ap.parse_args(argv)

    if a.list:
        cmd_list(*a.list)
        return 0
    if not a.set:
        ap.error('要么 --list，要么 --set')
    edits = []
    for e in a.edits:
        if '=' not in e:
            raise SystemExit(f'!! {e!r} 应为 路径=RRGGBB')
        p, h = e.split('=', 1)
        h = h.lstrip('#')
        if len(h) != 6:
            raise SystemExit(f'!! 颜色应为 RRGGBB，收到 {h!r}')
        edits.append((p, tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))))
    if not edits:
        raise SystemExit('!! 没给要改的颜色')
    if not a.out:
        raise SystemExit('!! --set 必须给 --out（不原地改输入文件）')
    cmd_set(a.set[0], a.set[1], edits, a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
