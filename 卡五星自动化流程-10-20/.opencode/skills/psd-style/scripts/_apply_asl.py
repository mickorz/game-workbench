# -*- coding: utf-8 -*-
"""Correctly apply an ASL layer style onto a PSD layer.

Three things the earlier attempts got wrong:

1. The lfx2 block carries 2 trailing bytes after its descriptor. They must be
   preserved: Photoshop writes them, so they are part of the block contract.
2. ASL and lfx2 name some effects differently. In an ASL, Color Overlay is the
   key `SoFi`; in lfx2 it is the slot `solidFillMulti` whose value is a `VlLs`
   list holding one `SoFi` object. Inner Shadow is `IrSh` vs `innerShadowMulti`.
3. Applying a style must also switch OFF effects the style does not define,
   otherwise stale effects from the layer leak into the result.

Everything else (the 11-slot skeleton, Scl, masterFXSwitch) is kept from the
layer's own block, because that is the shape Photoshop itself produced.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _psd_lfx import Reader, encode_key, locate, match_layer

# ASL effect key -> lfx2 slot key. Effects not listed map to themselves.
LIST_WRAPPED = {
    'SoFi': 'solidFillMulti',
    'IrSh': 'innerShadowMulti',
    'PtFl': 'patternFillMulti',
}
# lfx2 slots that hold effects (everything except the two global settings)
GLOBAL_KEYS = {'Scl ', 'masterFXSwitch'}


def item_spans(block, skip=8):
    """Return (head_end, classID, [(key, start, end)]) for a descriptor."""
    r = Reader(block, skip)
    r.ustring()
    cls = r.key()
    n = r.u32()
    head_end = r.o
    items = []
    for _ in range(n):
        start = r.o
        k = r.key()
        _, node = r.value()
        items.append((k, start, r.o))
    return head_end, cls, items, r.o


def set_bool(block, start, end, key, value):
    """Flip an `enab`/`present` bool in place. Length never changes."""
    pat = encode_key(key) + b'bool'
    i = block.find(pat, start, end)
    if i < 0:
        return block
    out = bytearray(block)
    out[i + len(pat)] = 1 if value else 0
    return bytes(out)


def slot_bytes(src_key, asl_desc, ss, se):
    """Encode one ASL effect as the lfx2 slot Photoshop expects.

    A plain effect becomes  <key> <value>. A list-wrapped effect such as
    Color Overlay becomes  <slot key> VlLs <count 1> <value>.
    """
    slot = LIST_WRAPPED.get(src_key, src_key)
    value = asl_desc[ss + len(encode_key(src_key)):se]
    if src_key in LIST_WRAPPED:
        return encode_key(slot) + b'VlLs' + struct.pack('>I', 1) + value
    return encode_key(slot) + value


def build_lfx2(orig_block, asl_desc, verbose=True):
    """Return the replacement lfx2 payload."""
    head_end, cls, orig_items, consumed = item_spans(orig_block)
    tail = orig_block[consumed:]                 # the 2 bytes Photoshop writes
    a_head, a_cls, asl_items, a_consumed = item_spans(asl_desc)

    # slot key (str) -> (source ASL key, start, end)
    supplied = {}
    for k, s, e in asl_items:
        if k in GLOBAL_KEYS:
            continue
        supplied[LIST_WRAPPED.get(k, k)] = (k, s, e)

    head = orig_block[:head_end]
    out = bytearray()
    replaced, disabled, added = [], [], []

    for k, s, e in orig_items:
        if k in supplied:
            src_k, ss, se = supplied.pop(k)
            out += slot_bytes(src_k, asl_desc, ss, se)
            replaced.append(k)
        elif k in GLOBAL_KEYS:
            out += orig_block[s:e]
        else:
            # an effect slot the style does not define -> switch it off
            piece = set_bool(orig_block, s, e, 'enab', False)
            piece = set_bool(piece, s, e, 'present', False)
            out += piece[s:e]
            disabled.append(k)

    for slot, (src_k, ss, se) in supplied.items():
        out += slot_bytes(src_k, asl_desc, ss, se)
        added.append(slot)

    new_block = head + bytes(out) + tail
    if verbose:
        print(f'    替换: {replaced}')
        print(f'    关闭: {disabled}')
        if added:
            print(f'    新增: {added}')
        print(f'    尾部保留: {tail.hex(" ") if tail else "(无)"}')
    return new_block


def apply_asl(psd_path, asl_path, style_index, layer_index, out_path,
              drop_lrfx=False):
    from _asl_extract import asl_styles
    import tempfile, os

    src = psd_path
    if drop_lrfx:
        from _drop_block import drop_block      # 可选依赖，只有删 lrFX 时才需要
        tmp = os.path.join(tempfile.gettempdir(), '_asl_stage.psd')
        drop_block(psd_path, tmp, layer_index, b'lrFX', report=False)
        src = tmp

    body = open(src, 'rb').read()
    info = locate(body)
    layer = info['layers'][layer_index]
    blk = next(b for b in layer['blocks'] if b['key'] == b'lfx2')
    orig_block = body[blk['data_off']:blk['data_off'] + blk['size']]

    style = asl_styles(asl_path)[style_index]
    asl_desc = struct.pack('>II', 0, 16) + style['raw']

    print(f'  图层 {layer["name"]!r}: lfx2 {blk["size"]} 字节')
    print(f'  ASL 样式 #{style_index}: {len(style["raw"])} 字节')
    new_block = build_lfx2(orig_block, asl_desc)

    old_span = 12 + blk['size'] + (blk['size'] % 2)
    new_span = 12 + len(new_block) + (len(new_block) % 2)
    delta = new_span - old_span
    out = bytearray()
    out += body[:blk['data_off']]
    out += new_block
    if len(new_block) % 2:
        out += b'\x00'
    out += body[blk['data_off'] + blk['size'] + (blk['size'] % 2):]
    struct.pack_into('>I', out, blk['size_off'], len(new_block))
    struct.pack_into('>I', out, layer['extra_len_off'], layer['extra'] + delta)
    struct.pack_into('>I', out, info['li_len_off'], info['li'] + delta)
    struct.pack_into('>I', out, info['lm_off'], info['lm'] + delta)

    print(f'  新 lfx2 {len(new_block)} 字节 (delta {delta:+d})')
    Path(out_path).write_bytes(bytes(out))
    print(f'  写出 {out_path}  ({len(body)} -> {len(out)} 字节)')
    if drop_lrfx:
        os.unlink(src)
    return out_path


def _cli():
    import argparse
    ap = argparse.ArgumentParser(description='把 ASL 里的一整套图层样式套到 PSD 的某个图层上')
    ap.add_argument('--psd', required=True, help='目标 PSD（副本）')
    ap.add_argument('--asl', required=True, help='ASL 样式库')
    ap.add_argument('--style', required=True, help='样式名（或 0 起的序号）')
    ap.add_argument('--layer', required=True, help='目标图层名')
    ap.add_argument('--out', required=True, help='输出 PSD')
    ap.add_argument('--drop-lrfx', action='store_true',
                    help='先删掉 lrFX 块再套（需要 _drop_block.py，默认不用）')
    a = ap.parse_args()

    from _asl_extract import asl_styles
    styles = asl_styles(a.asl)
    idx = int(a.style) if a.style.isdigit() else None
    if idx is None:
        idx = next((i for i, s in enumerate(styles) if s['name'] == a.style), None)
    if idx is None:
        idx = next((i for i, s in enumerate(styles) if a.style in (s['name'] or '')), None)
    if idx is None or not 0 <= idx < len(styles):
        raise SystemExit(f'!! 样式库里找不到 {a.style!r}；'
                         f'现有样式：{[s["name"] for s in styles]}')
    print(f'样式库 {a.asl}：{[s["name"] for s in styles]}')
    layer_index = match_layer(locate(open(a.psd, 'rb').read()), a.layer)
    apply_asl(a.psd, a.asl, idx, layer_index, a.out, drop_lrfx=a.drop_lrfx)
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(_cli())
