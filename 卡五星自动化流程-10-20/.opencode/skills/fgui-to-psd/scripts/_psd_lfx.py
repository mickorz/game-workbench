# -*- coding: utf-8 -*-
"""Read AND patch Photoshop layer styles (lfx2) directly in the PSD binary.

Verified descriptor encoding (Photoshop CC 2018, confirmed against both the
lfx2 layer-style block and image-resource 1050 slice data):

    Descriptor := name:UString, classID:Key, count:u32, count*(Key, Value)
    UString    := u32 charCount, charCount*2 bytes UTF-16BE      (no padding)
    Key        := u32 n; n == 0 -> next 4 bytes are the code; n > 0 -> n ASCII bytes
    Value      := 4-byte type tag + payload

Editing strategy: locate the exact byte range of the value to change and replace
it with a same-length encoding. Total block size is preserved, so no size fields
anywhere in the PSD need fixups.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

# --------------------------------------------------------------------- model


class Node:
    """A parsed descriptor node with its exact byte span in the block."""

    __slots__ = ('typ', 'start', 'end', 'val_start', 'val_end', 'children', 'key', 'raw', '_v')

    def __init__(self, typ, start, end, val_start=None, val_end=None):
        self.typ = typ
        self.start = start
        self.end = end
        self.val_start = val_start
        self.val_end = val_end
        self.children = {}          # key -> Node
        self.key = None
        self.raw = None


class Reader:
    def __init__(self, b, o=0):
        self.b = b
        self.o = o

    def u32(self):
        v = struct.unpack_from('>I', self.b, self.o)[0]
        self.o += 4
        return v

    def ustring(self):
        n = self.u32()
        s = self.b[self.o:self.o + n * 2].decode('utf-16-be', 'replace')
        self.o += n * 2
        return s

    def key(self):
        n = self.u32()
        if n == 0:
            s = self.b[self.o:self.o + 4].decode('latin1')
            self.o += 4
            return s
        s = self.b[self.o:self.o + n].decode('latin1')
        self.o += n
        return s

    def value(self, depth=0):
        start = self.o
        typ = self.b[self.o:self.o + 4].decode('latin1')
        self.o += 4
        val_start = self.o
        kids = {}
        if typ == 'TEXT':
            val = self.ustring()
        elif typ in ('obj ', 'Objc', 'GlbO'):
            kids, val = self.descriptor(depth + 1)
        elif typ == 'VlLs':
            n = self.u32()
            val = []
            for i in range(n):
                v, k = self.value(depth + 1)
                val.append(v)
                kids[i] = k
        elif typ == 'doub':
            val = struct.unpack_from('>d', self.b, self.o)[0]
            self.o += 8
        elif typ == 'UntF':
            unit = self.b[self.o:self.o + 4].decode('latin1')
            self.o += 4
            v = struct.unpack_from('>d', self.b, self.o)[0]
            self.o += 8
            val = (unit, v)
        elif typ in ('long', 'comp'):
            val = struct.unpack_from('>i', self.b, self.o)[0]
            self.o += 4
        elif typ == 'bool':
            val = bool(self.b[self.o])
            self.o += 1
        elif typ == 'enum':
            a = self.key(); b2 = self.key()
            val = (a, b2)
        elif typ == 'alis':
            val = self.ustring()
        elif typ == 'tdta':
            n = self.u32()
            self.o += n
            val = ('tdta', n)
        elif typ in ('type', 'GlbC'):
            val = self.key()
        else:
            raise ValueError(f'bad descriptor type {typ!r} at {start}')
        node = Node(typ, start, self.o, val_start, self.o)
        node.raw = self.b[start:self.o]
        # recompute val_start relative to the payload only for containers
        node.children = kids
        node._v = val
        return val, node

    def descriptor(self, depth=0):
        self.ustring()                 # name
        self.key()                     # classID
        cnt = self.u32()
        node = Node('descriptor', 0, 0)
        kids = {}
        for _ in range(cnt):
            k = self.key()
            v, kn = self.value(depth)
            kn.key = k
            kids[k] = kn
        node.children = kids
        return kids, node


# ------------------------------------------------------------------ helpers

def _sane_key(k):
    """True for a plausible 4-byte tagged-block key ('luni', 'lfx2', ...)."""
    return len(k) == 4 and all(33 <= ch < 127 for ch in k)


def _read_pascal(data, q, extra_end):
    """Legacy pascal layer name (GBK on a Chinese Photoshop); returns (name, next)."""
    if q >= extra_end:
        return '', q
    n = data[q]
    if n == 0:
        return '', q + 1
    raw = data[q + 1:q + 1 + n]
    try:
        name = raw.decode('gbk')
    except Exception:
        name = raw.decode('latin1', 'replace')
    return name, q + 1 + n


def _scan_blocks(data, start, end):
    """Parse the tagged blocks of one layer's extra data; None if implausible."""
    blocks = []
    q = start
    while q + 12 <= end:
        key = data[q + 4:q + 8]
        size = struct.unpack_from('>I', data, q + 8)[0]
        if not _sane_key(key) or q + 12 + size > end:
            return None
        blocks.append({'sig': data[q:q + 4], 'key': key, 'size_off': q + 8,
                       'data_off': q + 12, 'size': size})
        q += 12 + size + (size & 1)
    return blocks


def locate(data):
    """Locate every layer record and its tagged blocks.

    Returns {'layers': [{'index', 'name', 'pascal_name', 'extra_len_off', 'extra',
    'blocks': [{'sig', 'key', 'size_off', 'data_off', 'size'}]}],
    'li_len_off', 'li', 'lm_off', 'lm'} — the offsets a size-changing edit needs.
    """
    p = 26                                                   # file header
    p += 4 + struct.unpack_from('>I', data, p)[0]             # color mode data
    p += 4 + struct.unpack_from('>I', data, p)[0]             # image resources
    lm_off = p
    lm = struct.unpack_from('>I', data, p)[0]
    p += 4
    li_len_off = p
    li = struct.unpack_from('>I', data, p)[0]
    p += 4
    count = struct.unpack_from('>h', data, p)[0]
    p += 2

    layers = []
    for i in range(abs(count)):
        p += 16                                              # rectangle
        nchan = struct.unpack_from('>h', data, p)[0]
        p += 2 + 6 * nchan                                   # channel id + length
        p += 4 + 4 + 1 + 1 + 1 + 1                           # blend sig/key, opacity, clipping, flags, filler
        extra_len_off = p
        extra = struct.unpack_from('>I', data, p)[0]
        p += 4
        extra_end = min(p + extra, len(data))

        q = p
        if q + 4 <= extra_end:
            q += 4 + struct.unpack_from('>I', data, q)[0]     # layer mask data
        if q + 4 <= extra_end:
            q += 4 + struct.unpack_from('>I', data, q)[0]     # blending ranges
        pascal, q_name = _read_pascal(data, q, extra_end)

        # Photoshop pads the pascal name to a multiple of 4; some writers align
        # the following byte absolutely instead. Try both, keep the sane parse.
        best = None
        for nxt in {q_name + (-(q_name - q) % 4), (q_name + 3) & ~3}:
            blocks = _scan_blocks(data, nxt, extra_end)
            if blocks is None:
                continue
            score = len(blocks) + (2 if any(b['key'] == b'luni' for b in blocks) else 0)
            if best is None or score > best[0]:
                best = (score, blocks)
        blocks = best[1] if best else []

        name = None
        for b in blocks:
            if b['key'] == b'luni' and b['data_off'] + 4 <= len(data):
                n = struct.unpack_from('>I', data, b['data_off'])[0]
                name = data[b['data_off'] + 4:b['data_off'] + 4 + n * 2].decode('utf-16-be', 'replace')
                break
        layers.append({'index': i, 'name': name or pascal or f'layer{i}',
                       'pascal_name': pascal, 'extra_len_off': extra_len_off,
                       'extra': extra, 'blocks': blocks})
        p = extra_end

    return {'layers': layers, 'li_len_off': li_len_off, 'li': li,
            'lm_off': lm_off, 'lm': lm}


def match_layer(doc, name):
    """Index of the layer called `name`: exact, then case-insensitive, then substring."""
    layers = doc['layers']
    for i, L in enumerate(layers):
        if L['name'] == name:
            return i
    for i, L in enumerate(layers):
        if L['name'].lower() == name.lower():
            return i
    for i, L in enumerate(layers):
        if name in L['name']:
            return i
    raise SystemExit(f'!! 找不到图层 {name!r}；现有图层：{[L["name"] for L in layers]}')


def layer_block(data, layer, key):
    """The tagged block with `key` inside one layer record, or None."""
    for b in layer['blocks']:
        if b['key'] == key:
            return b
    return None


def find_lfx2_blocks(data):
    """Return {layer_name: (block_start, block_size)} for every lfx2 block."""
    out = {}
    for L in locate(data)['layers']:
        b = layer_block(data, L, b'lfx2')
        if b:
            out[L['name']] = (b['data_off'], b['size'])
    return out


def parse_block(blk):
    ver, dver = struct.unpack_from('>II', blk, 0)
    r = Reader(blk, 8)
    kids, _ = r.descriptor()
    return kids, r.o


# ------------------------------------------------------------------ patching

def node_span(node):
    """Byte span of a value's *scriptable payload* inside the block."""
    return node.start, node.end


def encode_bool(v):
    return b'\x01' if v else b'\x00'


def encode_double(v):
    return struct.pack('>d', float(v))


def encode_untf(unit, v):
    return unit.encode('latin1') + struct.pack('>d', float(v))


def encode_rgb(r, g, b):
    out = []
    for name, val in (('Rd  ', r), ('Grn ', g), ('Bl  ', b)):
        out.append(encode_key(name))
        out.append(b'doub' + struct.pack('>d', float(val)))
    return b''.join(out)


def encode_key(k):
    if len(k) == 4:
        return struct.pack('>I', 0) + k.encode('latin1')
    raw = k.encode('latin1')
    return struct.pack('>I', len(raw)) + raw


def encode_enum(typ, val):
    return encode_key(typ) + encode_key(val)


def patch_bytes(data, start, end, new):
    """Replace data[start:end] with new; require identical length."""
    if len(new) != end - start:
        raise ValueError(f'length mismatch: slice={end - start} new={len(new)}')
    return data[:start] + new + data[end:]


# ------------------------------------------------------------------- mutate

SLOT_ALIASES = {
    'color': 'solidFillMulti', '颜色叠加': 'solidFillMulti', 'solidfill': 'solidFillMulti',
    'gradient': 'GrFl', '渐变叠加': 'GrFl', 'gradientfill': 'GrFl',
    'stroke': 'FrFX', '描边': 'FrFX', 'frame': 'FrFX',
    'glow': 'OrGl', '外发光': 'OrGl',
    'innershadow': 'innerShadowMulti', '内阴影': 'innerShadowMulti',
    'shadow': 'DrSh', '投影': 'DrSh', 'dropshadow': 'DrSh',
    'innerglow': 'IrGl', '内发光': 'IrGl',
    'bevel': 'ebbl', '斜面和浮雕': 'ebbl', 'satin': 'ChFX', '光泽': 'ChFX',
}


def resolve_slot(name):
    """Accept a friendly effect name or the raw lfx2 slot key."""
    return SLOT_ALIASES.get(name.lower(), name)


def slot_object(top, slot):
    """The effect object node of a slot; unwraps the VlLs that `...Multi` slots use."""
    node = top.get(slot)
    if node is None:
        return None
    if node.typ == 'VlLs':
        return node.children.get(0)
    return node


def _clr_nodes(obj):
    clr = obj.children.get('Clr ') if obj is not None else None
    if clr is None or not all(k in clr.children for k in ('Rd  ', 'Grn ', 'Bl  ')):
        return None
    return [clr.children[k] for k in ('Rd  ', 'Grn ', 'Bl  ')]


def _patch_color(raw, obj, rgb):
    """Rewrite one object's Clr RGB in place — same length, no size fixups."""
    nodes = _clr_nodes(obj)
    if nodes is None:
        return False
    for node, val in zip(nodes, rgb):
        raw[node.start:node.end] = b'doub' + encode_double(val)
    return True


def _enable(raw, obj):
    """Force enab/present = true.

    `enab` alone is not enough: an effect whose `present` flag is false is one the
    layer does not "use", and Photoshop ignores it no matter what `enab` says.
    """
    for key in ('enab', 'present'):
        n = obj.children.get(key)
        if n is not None and n.typ == 'bool':
            raw[n.start:n.end] = b'bool' + encode_bool(True)


def _load_styles(data, layer_name):
    """(doc, layer, lfx2_block, bytearray of the block's bytes)."""
    doc = locate(data)
    layer = doc['layers'][match_layer(doc, layer_name)]
    blk = layer_block(data, layer, b'lfx2')
    if blk is None:
        raise SystemExit(f'!! 图层 {layer_name!r} 没有图层样式（无 lfx2 块）')
    raw = bytearray(data[blk['data_off']:blk['data_off'] + blk['size']])
    return doc, layer, blk, raw


def _save_styles(data, blk, raw, dst):
    out = bytearray(data)
    out[blk['data_off']:blk['data_off'] + blk['size']] = raw
    Path(dst).write_bytes(bytes(out))
    return dst


def set_style_color(src, dst, layer_name, slot, rgb):
    """Replace one effect slot's color. Same length, so no size fields change."""
    data = open(src, 'rb').read()
    _, _, blk, raw = _load_styles(data, layer_name)
    top, _ = parse_block(bytes(raw))
    slot = resolve_slot(slot)
    obj = slot_object(top, slot)
    if obj is None:
        raise SystemExit(f'!! 图层 {layer_name!r} 没有 {slot} 效果槽')
    if not _patch_color(raw, obj, rgb):
        raise SystemExit(f'!! {slot} 里找不到 Clr / Rd / Grn / Bl')
    _enable(raw, obj)
    return _save_styles(data, blk, raw, dst)


def set_style_gradient(src, dst, layer_name, colors):
    """Set the first and last gradient stop colors (one color sets both ends)."""
    data = open(src, 'rb').read()
    _, _, blk, raw = _load_styles(data, layer_name)
    top, _ = parse_block(bytes(raw))
    obj = slot_object(top, 'GrFl')
    grad = obj.children.get('Grad') if obj is not None else None
    clrs = grad.children.get('Clrs') if grad is not None else None
    stops = [clrs.children[k] for k in sorted(clrs.children)] if clrs is not None else []
    if not stops:
        raise SystemExit(f'!! 图层 {layer_name!r} 没有渐变叠加（GrFl）')
    targets = [(stops[0], colors[0]), (stops[-1], colors[-1])]
    for stop, rgb in targets:
        if not _patch_color(raw, stop, rgb):
            raise SystemExit('!! 渐变色标里找不到 Clr / Rd / Grn / Bl')
    _enable(raw, obj)
    return _save_styles(data, blk, raw, dst)


def set_effect_enabled(src, dst, layer_name, slot, on):
    """Turn one effect slot on/off (same length). Needed when two overlaps fight.

    叠加类效果互相遮盖：渐变叠加开着时，只改颜色叠加的颜色看不出来 —— 要么关掉
    渐变叠加，要么连它一起改。
    """
    data = open(src, 'rb').read()
    _, _, blk, raw = _load_styles(data, layer_name)
    top, _ = parse_block(bytes(raw))
    slot = resolve_slot(slot)
    obj = slot_object(top, slot)
    if obj is None:
        raise SystemExit(f'!! 图层 {layer_name!r} 没有 {slot} 效果槽')
    hit = 0
    for key in ('enab', 'present'):
        node = obj.children.get(key)
        if node is not None and node.typ == 'bool':
            raw[node.start:node.end] = b'bool' + encode_bool(on)
            hit += 1
    if not hit:
        raise SystemExit(f'!! {slot} 里没有 enab / present')
    return _save_styles(data, blk, raw, dst)


NUM_PARAMS = {
    '不透明度': 'Opct', 'opacity': 'Opct', 'opct': 'Opct',
    '角度': 'Angl', 'angle': 'Angl', 'angl': 'Angl',
    '大小': 'Sz  ', 'size': 'Sz  ', 'sz': 'Sz  ',
    '距离': 'Dstn', 'distance': 'Dstn', 'dstn': 'Dstn',
    '模糊': 'blur', 'blur': 'blur',
    '阻塞': 'Ckmt', '扩展': 'Ckmt', 'ckmt': 'Ckmt',
    '杂色': 'Nose', 'nose': 'Nose',
    '缩放': 'Scl ', 'scale': 'Scl ',
}


def set_style_param(src, dst, layer_name, slot, param, value):
    """Set one numeric effect parameter (不透明度/角度/大小/…). Same length."""
    data = open(src, 'rb').read()
    _, _, blk, raw = _load_styles(data, layer_name)
    top, _ = parse_block(bytes(raw))
    slot = resolve_slot(slot)
    obj = slot_object(top, slot)
    if obj is None:
        raise SystemExit(f'!! 图层 {layer_name!r} 没有 {slot} 效果槽')
    key = NUM_PARAMS.get(param.lower(), param)
    node = obj.children.get(key)
    if node is None:
        raise SystemExit(f'!! {slot} 里没有 {key}；现有参数：'
                         f'{[k for k in obj.children]}')
    if node.typ == 'UntF':
        unit = node._v[0]
        raw[node.start:node.end] = b'UntF' + unit.encode('latin1') + encode_double(value)
    elif node.typ == 'doub':
        raw[node.start:node.end] = b'doub' + encode_double(value)
    else:
        raise SystemExit(f'!! {key} 不是数值（类型 {node.typ}）')
    _enable(raw, obj)
    return _save_styles(data, blk, raw, dst)


TYSH_DESC_OFFSET = 2 + 48 + 2 + 4      # version + transform + text version + descriptor version

def read_text(data, layer_name):
    """(text, TySh block, raw bytes) for a text layer."""
    doc = locate(data)
    layer = doc['layers'][match_layer(doc, layer_name)]
    blk = layer_block(data, layer, b'TySh')
    if blk is None:
        raise SystemExit(f'!! 图层 {layer_name!r} 不是文字图层（没有 TySh 块）')
    raw = bytes(data[blk['data_off']:blk['data_off'] + blk['size']])
    r = Reader(raw, TYSH_DESC_OFFSET)
    kids, _ = r.descriptor()
    node = kids.get('Txt ')
    if node is None or node.typ != 'TEXT':
        raise SystemExit(f'!! 图层 {layer_name!r} 的 TySh 里没有 Txt')
    n = struct.unpack_from('>I', raw, node.val_start)[0]
    return raw[node.val_start + 4:node.val_start + 4 + n * 2].decode('utf-16-be', 'replace'), blk, bytearray(raw), node


ENGINE_TEXT_MARK = b'/Text (' + b'\xfe\xff'     # EngineData 里的 /Text (FEFF<UTF-16BE>)
RUN_LEN_MARK = b'/RunLengthArray'


def _rewrite_tysh_text(raw: bytes, new_text: str) -> bytes:
    """在 TySh 块里换文字，**允许字数变化**。

    要改三处，缺一处 Photopea/PS 就会文字与排版不一致：
      1. 描述符 `Txt `（u32 字符数 + UTF-16BE，沿用原有的结尾 NUL 习惯）
      2. EngineData `/Text (FEFF<UTF-16BE>...)`（沿用原有的结尾 \\r / \\n）
      3. 两处 `/RunLengthArray [ n ]`（字符数 = 字数 + 1 个结尾符）
    EngineData 的 tdta 长度、TySh 块长度由调用方重算。
    """
    node = _tx_txt_node(raw)
    old_val = raw[node.val_start + 4:node.val_end]
    old_str = old_val.decode('utf-16-be', 'replace')
    old_units = struct.unpack_from('>I', raw, node.val_start)[0]   # 含结尾 NUL

    tail = '\x00' if old_str.endswith('\x00') else ''
    new_units = len(new_text) + len(tail)
    new_val = (struct.pack('>I', new_units)          # 字符数（TEXT 值自带 u32 计数）
               + (new_text + tail).encode('utf-16-be'))

    ed = _tx_engine_node(raw)
    pay_start = ed.val_start + 4
    pay_len = struct.unpack_from('>I', raw, ed.val_start)[0]
    payload = raw[pay_start:pay_start + pay_len]
    if len(payload) != pay_len:
        raise SystemExit('!! EngineData 越界')

    k = payload.find(ENGINE_TEXT_MARK)
    if k < 0:
        raise SystemExit('!! EngineData 里找不到 /Text (FEFF…')
    ts = k + len(ENGINE_TEXT_MARK)
    te = ts + 2 * old_units
    term = payload[te - 2:te]
    if term not in (b'\x00\r', b'\x00\n', b'\x00\x00'):
        raise SystemExit(f'!! EngineData 文字结尾符异常 {term!r}，不敢动')
    payload = payload[:ts] + new_text.encode('utf-16-be') + term + payload[te:]

    # 两处 /RunLengthArray [ n ] 一起跟着改（字符数 = 字数 + 1 个结尾符）
    i, hits = 0, 0
    while True:
        r = payload.find(RUN_LEN_MARK, i)
        if r < 0:
            break
        lb = payload.find(b'[', r)
        rb = payload.find(b']', lb)
        if lb < 0 or rb < 0:
            break
        payload = (payload[:lb + 1] + b' ' + str(new_units).encode('latin1') + b' ]'
                   + payload[rb + 1:])
        i = lb + len(str(new_units)) + 4
        hits += 1
    if hits == 0:
        raise SystemExit('!! EngineData 里没有 /RunLengthArray，不敢动')

    out = bytearray(raw)
    # 从后往前替换，前面的偏移才不会失效
    out[ed.start:ed.end] = b'tdta' + struct.pack('>I', len(payload)) + payload
    out[node.val_start:node.val_end] = new_val
    return bytes(out)


def _tx_txt_node(raw):
    r = Reader(raw, TYSH_DESC_OFFSET)
    kids, _ = r.descriptor()
    node = kids.get('Txt ')
    if node is None or node.typ != 'TEXT':
        raise SystemExit('!! TySh 描述符里没有 Txt')
    return node


def _tx_engine_node(raw):
    r = Reader(raw, TYSH_DESC_OFFSET)
    kids, _ = r.descriptor()
    node = kids.get('EngineData')
    if node is None or node.typ != 'tdta':
        raise SystemExit('!! TySh 描述符里没有 EngineData')
    return node


def set_text(src, dst, layer_name, new_text):
    """改文字内容，**字数可长可短**。

    改的是 TySh 块（描述符 Txt + EngineData /Text + RunLengthArray），改完重算
    TySh 块长度、图层额外数据长度、layer-info 段长、layer-and-mask 段长。
    图层像素（光栅缓存）与矩形不动 —— Photopea / PS 会按 TySh 重新排版渲染。
    """
    import _psd_struct as S

    data = open(src, 'rb').read()
    st = S.parse(data)
    idx = match_layer({'layers': [{'name': L.name} for L in st['layers']]}, layer_name)
    layer = st['layers'][idx]
    ty = S.get_block(layer.extra, b'TySh')
    if ty is None:
        raise SystemExit(f'!! 图层 {layer.name!r} 不是文字图层（没有 TySh 块）')
    layer.extra = S.set_block(layer.extra, b'TySh', _rewrite_tysh_text(ty, new_text))
    st['li_pad'] = b''
    open(dst, 'wb').write(S.serialize(st))
    return dst


# ---------------------------------------------------------------------- cli

def hex2rgb(s):
    s = s.lstrip('#')
    if len(s) != 6:
        raise SystemExit(f'!! 颜色格式应为 RRGGBB，收到 {s!r}')
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def _inspect(psd, layer_name):
    data = open(psd, 'rb').read()
    doc = locate(data)
    layer = doc['layers'][match_layer(doc, layer_name)]
    print(f'图层 {layer["name"]!r}（第 {layer["index"]} 层）  '
          f'块：{[b["key"].decode("latin1") for b in layer["blocks"]]}')
    blk = layer_block(data, layer, b'lfx2')
    if blk is None:
        print('  （没有图层样式）')
    else:
        raw = data[blk['data_off']:blk['data_off'] + blk['size']]
        top, consumed = parse_block(raw)
        print(f'  lfx2 {blk["size"]} 字节，消耗 {consumed}（尾部 {blk["size"] - consumed} 字节）')
        summarize(top)
    if layer_block(data, layer, b'TySh'):
        text, _, _, _ = read_text(data, layer_name)
        print(f'  文字 = {text!r}')


def _cli():
    import argparse
    ap = argparse.ArgumentParser(description='PSD 图层样式读写（lfx2 / TySh）')
    ap.add_argument('--layers', metavar='PSD', help='列出全部图层名')
    ap.add_argument('--inspect', nargs=2, metavar=('PSD', '图层名'), help='打印该图层的全部图层样式现值')
    ap.add_argument('--set-color', nargs=4, metavar=('PSD', '图层名', '效果', 'RRGGBB'),
                    help='改 颜色叠加/描边/外发光… 的颜色（等长替换）')
    ap.add_argument('--set-gradient', nargs=4, metavar=('PSD', '图层名', 'C1', 'C2'),
                    help='改渐变叠加两端颜色（C1=C2 即单色）')
    ap.add_argument('--set-text', nargs=3, metavar=('PSD', '图层名', '新文字'),
                    help='改文字内容（字数可长可短）')
    ap.add_argument('--set-num', nargs=5, metavar=('PSD', '图层名', '效果', '参数', '值'),
                    help='改数值参数：不透明度/角度/大小/距离/模糊…')
    ap.add_argument('--set-effect', nargs=4, metavar=('PSD', '图层名', '效果', 'on|off'),
                    help='开关某个效果槽（叠加类互相遮盖时用）')
    ap.add_argument('--out', help='输出 PSD 路径（改动类命令必填，默认不动输入文件）')
    a = ap.parse_args()

    if a.layers:
        doc = locate(open(a.layers, 'rb').read())
        for L in doc['layers']:
            keys = ' '.join(b['key'].decode('latin1') for b in L['blocks'])
            print(f'[{L["index"]:2d}] {L["name"]}    ({keys})')
        return 0
    if a.inspect:
        _inspect(*a.inspect)
        return 0
    if a.set_color:
        psd, layer, slot, color = a.set_color
        if not a.out:
            raise SystemExit('!! 改动类命令必须给 --out')
        set_style_color(psd, a.out, layer, slot, hex2rgb(color))
        print(f'已写 {a.out}：{layer} 的 {resolve_slot(slot)} 颜色 = #{color.lstrip("#").upper()}')
        return 0
    if a.set_gradient:
        psd, layer, c1, c2 = a.set_gradient
        if not a.out:
            raise SystemExit('!! 改动类命令必须给 --out')
        set_style_gradient(psd, a.out, layer, [hex2rgb(c1), hex2rgb(c2)])
        print(f'已写 {a.out}：{layer} 的渐变 = #{c1.lstrip("#").upper()} → #{c2.lstrip("#").upper()}')
        return 0
    if a.set_text:
        psd, layer, text = a.set_text
        if not a.out:
            raise SystemExit('!! 改动类命令必须给 --out')
        set_text(psd, a.out, layer, text)
        print(f'已写 {a.out}：{layer} 的文字 = {text!r}')
        return 0
    if a.set_num:
        psd, layer, slot, param, value = a.set_num
        if not a.out:
            raise SystemExit('!! 改动类命令必须给 --out')
        set_style_param(psd, a.out, layer, slot, param, float(value))
        print(f'已写 {a.out}：{layer} 的 {resolve_slot(slot)}.{param} = {value}')
        return 0
    if a.set_effect:
        psd, layer, slot, state = a.set_effect
        if not a.out:
            raise SystemExit('!! 改动类命令必须给 --out')
        on = state.lower() in ('on', '1', 'true', 'yes', '开')
        set_effect_enabled(psd, a.out, layer, slot, on)
        print(f'已写 {a.out}：{layer} 的 {resolve_slot(slot)} = {"开" if on else "关"}')
        return 0
    ap.print_help()
    return 2


# ------------------------------------------------------------------ report

EFFECT_NAMES = {
    'DrSh': '投影 Drop Shadow', 'IrSh': '内阴影 Inner Shadow',
    'OrGl': '外发光 Outer Glow', 'IrGl': '内发光 Inner Glow',
    'ebbl': '斜面和浮雕 Bevel', 'SoFl': '颜色叠加 Color Overlay',
    'GrFl': '渐变叠加 Gradient Overlay', 'PtFl': '图案叠加 Pattern Overlay',
    'ChFX': '光泽 Satin', 'FrFX': '描边 Frame', 'SoLd': '描边 Stroke',
    'innerShadowMulti': '内阴影(多)', 'solidFillMulti': '颜色叠加(多)',
    'gradientFillMulti': '渐变叠加(多)', 'patternFillMulti': '图案叠加(多)',
    'frameFXMulti': '描边(多)', 'chromeFXMulti': '光泽(多)',
    'bevelEmbossMulti': '斜面和浮雕(多)', 'outerGlowMulti': '外发光(多)',
    'innerGlowMulti': '内发光(多)', 'dropShadowMulti': '投影(多)',
    'strokeMulti': '描边(多)',
}

PARAM_NAMES = {
    'enab': '启用', 'present': '生效', 'showInDialog': '显示于对话框',
    'Opct': '不透明度%', 'opct': '不透明度%', 'Sz  ': '大小(px)',
    'blur': '模糊(px)', 'Dstn': '距离(px)', 'Ckmt': '阻塞/收缩(px)',
    'Nose': '杂色%', 'Angl': '角度', 'lagl': '局部角度', 'Lald': '光照角度',
    'Clr ': '颜色', 'Md  ': '混合模式', 'mode': '混合模式',
    'Styl': '位置', 'strokeStyle': '位置', 'PntT': '填充类型',
    'GrdT': '渐变类型', 'Rvrs': '反向', 'algn': '对齐', 'Algn': '对齐',
    'Scl ': '缩放%', 'scl ': '缩放%', 'uglg': '使用全局光',
    'AntA': '消除锯齿', 'antialiasGloss': '光泽消除锯齿',
    'Inpr': '源不透明度%', 'GlwT': '发光类型', 'glwS': '光源',
    'bvlT': '浮雕类型', 'bvlD': '方向', 'style': '样式', 'Sftn': '柔化(px)',
    'srgR': '高光范围%', 'hglC': '高光颜色', 'hglO': '高光不透明度%',
    'sdwC': '阴影颜色', 'sdwO': '阴影不透明度%', 'hglM': '高光模式',
    'sdwM': '阴影模式', 'Invr': '反向', 'layerConceals': '图层遮盖',
    'useGlobalAngle': '使用全局光', 'Dthr': '仿色', 'TrnS': '等高线',
    'TrnF': '等高线', 'transfer': '等高线', 'mapping': '等高线',
    'gradient': '渐变', 'ptrn': '图案', 'ofst': '偏移', 'Ofst': '偏移',
    'fillEnabled': '填充', 'overprint': '叠印', 'Nose ': '杂色%',
    'Mdpn': '映射方式', 'Vrsn': '版本', 'Clrz': '着色',
}


def fmt(v):
    if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str) and v[0].startswith('#'):
        return f'{v[1]:g} {v[0]}'
    if isinstance(v, tuple) and len(v) == 2:
        return f'{v[0]} = {v[1]}'
    if isinstance(v, bool):
        return '是' if v else '否'
    if isinstance(v, float):
        return f'{v:g}'
    return str(v)


def is_rgb(node):
    return node.typ in ('obj ', 'Objc', 'GlbO')


def dump(node, indent=1):
    """Pretty print a descriptor node tree."""
    pad = '  ' * indent
    if node.typ in ('obj ', 'Objc', 'GlbO'):
        for k, ch in node.children.items():
            if k in ('Rd  ', 'Grn ', 'Bl  '):
                continue
            label = PARAM_NAMES.get(k, k)
            if is_rgb(ch) and all(x in ch.children for x in ('Rd  ', 'Grn ', 'Bl  ')):
                r = int(round(ch.children['Rd  ']._v))
                g = int(round(ch.children['Grn ']._v))
                b = int(round(ch.children['Bl  ']._v))
                print(f'{pad}{label} = #{r:02X}{g:02X}{b:02X}')
            else:
                print(f'{pad}{label} = {fmt(ch._v)}')
                if is_rgb(ch) and ch.children:
                    dump(ch, indent + 1)
    else:
        print(f'{pad}{fmt(node._v)}')


def grad_stops(node):
    """渐变节点的色标：'#RRGGBB@位置%' 列表（没有就空）。"""
    clrs = node.children.get('Clrs') if node is not None else None
    if clrs is None or clrs.typ != 'VlLs':
        return []
    out = []
    for k in sorted(clrs.children):
        st = clrs.children[k]
        c = st.children.get('Clr ')
        if c is None or 'Rd  ' not in c.children:
            continue
        rgb = tuple(int(round(c.children[x]._v)) for x in ('Rd  ', 'Grn ', 'Bl  '))
        loc = st.children.get('Lctn')
        if loc is None:
            pos = '?'
        elif loc.typ == 'UntF':                       # '#Prc'，0~100
            pos = f'{loc._v[1]:.0f}%'
        elif loc.typ == 'long':                       # Photoshop 里是 0~4096 的定点
            pos = f'{loc._v / 40.96:.0f}%'
        else:
            pos = '?'
        out.append('#%02X%02X%02X@%s' % (*rgb, pos))
    return out


def _print_params(obj, pad):
    """One effect object's parameters, one per line."""
    for pk, pn in obj.children.items():
        label = PARAM_NAMES.get(pk, pk)
        if is_rgb(pn) and all(x in pn.children for x in ('Rd  ', 'Grn ', 'Bl  ')):
            r = int(round(pn.children['Rd  ']._v))
            g = int(round(pn.children['Grn ']._v))
            b = int(round(pn.children['Bl  ']._v))
            print(f'{pad}{label} = #{r:02X}{g:02X}{b:02X}')
        elif pk == 'Grad' and is_rgb(pn):
            nm = pn.children.get('Nm  ')
            stops = grad_stops(pn)
            print(f'{pad}{label} = {nm._v if nm is not None else ""} '
                  f'色标 {len(stops)} 个：{" → ".join(stops) or "（读不出）"}')
        elif pn.typ == 'VlLs':
            print(f'{pad}{label} = [{len(pn.children)} 项]')
        else:
            print(f'{pad}{label} = {fmt(pn._v)}')


def summarize(top, indent=1):
    pad = '  ' * indent
    for k, node in top.items():
        if k in ('Scl ', 'masterFXSwitch', 'Vrsn', 'Lefx'):
            print(f'{pad}[全局] {PARAM_NAMES.get(k, k)} = {fmt(node._v)}')
            continue
        name = EFFECT_NAMES.get(k, k)
        if node.typ == 'VlLs':
            entries = [ch for _, ch in node.children.items()]
        elif is_rgb(node):
            entries = [node]
        else:
            entries = []
        if entries:
            first = entries[0].children
            enab = first.get('enab')
            pres = first.get('present')
            on = bool(enab._v) if enab else False
            state = '开' if on else ('未用' if (pres and not pres._v) else '关')
            print(f'{pad}[{state}] {k}  {name}')
            for ent in entries:
                _print_params(ent, pad + '      ')
        else:
            print(f'{pad}{k} = {fmt(node._v)}')


# --------------------------------------------------------------------- main

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(_cli())
