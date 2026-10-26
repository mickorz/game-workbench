# -*- coding: utf-8 -*-
"""Extract layer styles (and specifically Color/Gradient Overlay) from .ASL files.

ASL entry layout (verified against Photoshop CC 2018's shipped libraries):
  '8BSL' header, then per style a descriptor containing a `Lefx` object.
  The `Lefx` object's descriptor holds the same effect items as a PSD `lfx2` block,
  encoded with the identical Key/UString scheme.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _psd_lfx import Reader

EFFECT_NAMES = {
    'DrSh': '投影', 'IrSh': '内阴影', 'OrGl': '外发光', 'IrGl': '内发光',
    'ebbl': '斜面和浮雕', 'SoFl': '颜色叠加', 'GrFl': '渐变叠加',
    'PtFl': '图案叠加', 'ChFX': '光泽', 'FrFX': '描边', 'SoLd': '描边',
}
MULTI_TO_KEY = {
    'dropShadowMulti': 'DrSh', 'innerShadowMulti': 'IrSh',
    'outerGlowMulti': 'OrGl', 'innerGlowMulti': 'IrGl',
    'bevelEmbossMulti': 'ebbl', 'solidFillMulti': 'SoFl',
    'gradientFillMulti': 'GrFl', 'patternFillMulti': 'PtFl',
    'chromeFXMulti': 'ChFX', 'frameFXMulti': 'FrFX', 'strokeMulti': 'SoLd',
}


def rgb_of(node):
    ks = ('Rd  ', 'Grn ', 'Bl  ')
    if node is not None and all(k in node.children for k in ks):
        return tuple(int(round(node.children[k]._v)) for k in ks)
    return None


def hexs(c):
    return '#%02X%02X%02X' % c if c else '?'


def entries_of(node):
    """Effects are sometimes stored directly, sometimes wrapped in a VlLs."""
    if node.typ == 'VlLs':
        return [ch for _, ch in node.children.items()]
    return [node]


def describe(effect_key, obj):
    """Human summary of one effect object."""
    enab = obj.children.get('enab')
    on = bool(enab._v) if enab else False
    bits = [f'[{"开" if on else "关"}] {EFFECT_NAMES.get(effect_key, effect_key)}']
    if effect_key == 'SoFl':
        c = rgb_of(obj.children.get('Clr '))
        op = obj.children.get('Opct')
        bits.append(f'颜色 {hexs(c)}')
        if op:
            bits.append(f'不透明度 {op._v[1]:g}%')
        m = obj.children.get('Md  ')
        if m:
            bits.append(f'模式 {m._v[1]}')
    elif effect_key == 'GrFl':
        g = obj.children.get('Grad')
        if g:
            clrs = g.children.get('Clrs')
            stops = []
            if clrs:
                for _, st in clrs.children.items():
                    c = rgb_of(st.children.get('Clr '))
                    loc = st.children.get('Lctn')
                    op = st.children.get('Opct')
                    s = f'{hexs(c)}@{loc._v if loc else 0}'
                    if op:
                        s += f'({op._v[1]:g}%)'
                    stops.append(s)
            bits.append('渐变 ' + ' -> '.join(stops))
            nm = g.children.get('Nm  ')
            if nm:
                bits.append(f'预设 {nm._v.strip(chr(0))!r}')
        a = obj.children.get('Angl')
        if a:
            bits.append(f'角度 {a._v[1]:g}°')
        r = obj.children.get('Rvrs')
        if r:
            bits.append(f'反向 {r._v}')
        op = obj.children.get('Opct')
        if op:
            bits.append(f'不透明度 {op._v[1]:g}%')
    elif effect_key in ('FrFX', 'SoLd'):
        c = rgb_of(obj.children.get('Clr '))
        sz = obj.children.get('Sz  ')
        st = obj.children.get('Styl') or obj.children.get('strokeStyle')
        if sz:
            bits.append(f'{sz._v[1]:g}px')
        if st:
            bits.append(f'位置 {st._v[1]}')
        bits.append(f'颜色 {hexs(c)}')
    else:
        for pk in ('Opct', 'Sz  ', 'Dstn', 'blur', 'lagl', 'Angl'):
            p = obj.children.get(pk)
            if p and isinstance(p._v, tuple):
                bits.append(f'{pk.strip()}={p._v[1]:g}')
        c = rgb_of(obj.children.get('Clr '))
        if c:
            bits.append(f'颜色 {hexs(c)}')
    return '  '.join(bits)


def read_styles(path):
    data = open(path, 'rb').read()
    out = []
    start = 0
    while True:
        i = data.find(b'LefxObjc', start)
        if i < 0:
            break
        start = i + 8
        try:
            r = Reader(data, i + 8)
            kids, _ = r.descriptor()
        except Exception as exc:
            out.append((None, None, f'parse error: {exc}'))
            continue
        # the Lefx object's own items are the effects
        out.append((i, kids, None))
    return data, out


def style_name_before(data, off, window=400):
    """The style display name sits just before the descriptor; find a UTF-16 run."""
    lo = max(0, off - window)
    chunk = data[lo:off]
    # look for u32 length followed by that many UTF-16BE chars ending at a plausible point
    best = None
    for p in range(len(chunk) - 4, -1, -1):
        n = struct.unpack_from('>I', chunk, p)[0]
        if not (2 <= n <= 60):
            continue
        if p + 4 + n * 2 > len(chunk) + 8:
            continue
        raw = chunk[p + 4:p + 4 + n * 2]
        if len(raw) < n * 2:
            continue
        try:
            s = raw.decode('utf-16-be')
        except Exception:
            continue
        if all(32 <= ord(c) < 0x3000 for c in s.rstrip('\x00')):
            cand = s.rstrip('\x00')
            if cand and (best is None or len(cand) < len(best[1])):
                best = (p, cand)
    return best[1] if best else None


def asl_styles(path):
    """[{name, raw, off}] — raw is the style's Lefx descriptor (name+classID+items).

    `raw` is exactly what `_apply_asl.build_lfx2` consumes after it prepends the
    two version words, so applying a style is `struct.pack('>II', 0, 16) + raw`.
    """
    data = open(path, 'rb').read()
    out = []
    start = 0
    while True:
        i = data.find(b'LefxObjc', start)
        if i < 0:
            break
        start = i + 8
        r = Reader(data, i + 8)
        try:
            r.descriptor()
        except Exception as exc:
            print(f'  !! 第 {len(out)} 个样式解析失败：{exc}')
            continue
        out.append({'name': style_name_before(data, i - 8) or f'样式{len(out) + 1}',
                    'raw': data[i + 8:r.o], 'off': i})
    return out


def print_styles(path):
    data, styles = read_styles(path)
    print(f'{Path(path).name}: {len(data)} bytes, {len(styles)} style(s) found\n')
    for idx, (off, kids, err) in enumerate(styles):
        if err:
            print(f'[{idx}] {err}')
            continue
        name = style_name_before(data, off - 8)
        print(f'[{idx:2d}] 样式 {name!r}  (Lefx @ {off})')
        for k, node in kids.items():
            key = MULTI_TO_KEY.get(k, k)
            for obj in entries_of(node):
                print(f'      {describe(key, obj)}')
        print()
    print(f'总共 {len(styles)} 个样式')


if __name__ == '__main__':
    import argparse
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='ASL 样式库：列出样式名与参数')
    ap.add_argument('asl', help='ASL 文件')
    ap.add_argument('--list', action='store_true', help='列出全部样式名 + 参数摘要')
    a = ap.parse_args()
    print_styles(a.asl)
