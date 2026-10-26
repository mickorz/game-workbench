# -*- coding: utf-8 -*-
"""临时探针 v3：解码 PSD 通道数据（含合并图）导出预览，并打印渐变叠加的全部色标。"""
import struct
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image

from _psd_lfx import locate, layer_block, parse_block, slot_object


def unpackbits(data, expected, start=0):
    out = bytearray()
    i = start
    while len(out) < expected and i < len(data):
        n = struct.unpack_from('>b', data, i)[0]
        i += 1
        if n >= 0:
            out += data[i:i + n + 1]
            i += n + 1
        elif n != -128:
            out += data[i:i + 1] * (1 - n)
            i += 1
    return bytes(out[:expected]), i


def read_channel(d, off, w, h):
    comp = struct.unpack_from('>H', d, off)[0]
    off += 2
    if comp == 0:
        return d[off:off + w * h], off + w * h
    counts = struct.unpack_from('>%dH' % h, d, off)
    off += 2 * h
    rows, p = [], off
    for c in counts:
        row, p = unpackbits(d, w, p)
        rows.append(row)
    return b''.join(rows), p


def main(psd, outdir='_preview'):
    d = open(psd, 'rb').read()
    doc = locate(d)
    Path(outdir).mkdir(exist_ok=True)
    H = struct.unpack_from('>I', d, 14)[0]
    W = struct.unpack_from('>I', d, 18)[0]

    p = doc['li_len_off'] + 4
    cnt = struct.unpack_from('>h', d, p)[0]
    p += 2
    records = []
    for i in range(abs(cnt)):
        t, l, b, r = struct.unpack_from('>4i', d, p)
        nchan = struct.unpack_from('>h', d, p + 16)[0]
        q = p + 18
        chans = []
        for _ in range(nchan):
            cid = struct.unpack_from('>h', d, q)[0]
            clen = struct.unpack_from('>I', d, q + 2)[0]
            chans.append((cid, clen))
            q += 6
        extra = struct.unpack_from('>I', d, q + 12)[0]
        records.append({'rect': (t, l, b, r), 'chans': chans, 'flags': d[q + 10]})
        p = q + 16 + extra

    # 通道数据段
    q = p
    for i, rec in enumerate(records):
        t, l, b, r = rec['rect']
        w, h = r - l, b - t
        planes = {}
        for cid, clen in rec['chans']:
            comp = struct.unpack_from('>H', d, q)[0]
            data, q2 = read_channel(d, q, w, h)
            if q2 - q != clen:
                print(f'   !! 通道 {cid} 长度不符 解析 {q2 - q} != 表 {clen} '
                      f'(comp={comp}, 解出 {len(data)} / 期望 {w * h})')
            planes[cid] = data.ljust(w * h, b'\x00')[:w * h]
            q = q + clen
        alpha = planes.get(-1, b'\xff' * (w * h))
        rgb = b''.join(planes.get(c, b'\x00' * (w * h)) for c in (0, 1, 2))
        px = bytearray()
        for k in range(w * h):
            px += bytes((rgb[k], rgb[w * h + k], rgb[2 * w * h + k], alpha[k]))
        im = Image.frombytes('RGBA', (w, h), bytes(px))
        can = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        can.paste(im, (l, t))
        can.save(f'{outdir}/layer{i}.png')
        print(f'[{i}] rect={rec["rect"]} flags={rec["flags"]:#04x} '
              f'{w}x{h} -> {outdir}/layer{i}.png  不透明像素 '
              f'{sum(1 for k in range(w * h) if alpha[k] > 200)}')

    # 合并图（文件末尾图像数据段）
    print(f'通道数据段 结束于 {q}；global-mask 长度字段 = {struct.unpack_from(">I", d, q)[0]}')
    q = doc['lm_off'] + 4 + doc['lm']                    # layer-and-mask 段之后就是合并图
    print('图像数据段起点', q, ' 剩余', len(d) - q)
    planes = []
    for c in range(3):
        comp = struct.unpack_from('>H', d, q)[0]
        data, q2 = read_channel(d, q, W, H)
        print(f'  合并通道 {c}: comp={comp} 解析 {q2 - q} 字节 解出 {len(data)} / 期望 {W * H}')
        planes.append(data.ljust(W * H, b'\x00')[:W * H])
        q = q2
    px = bytearray()
    for k in range(W * H):
        px += bytes((planes[0][k], planes[1][k], planes[2][k], 255))
    Image.frombytes('RGBA', (W, H), bytes(px)).save(f'{outdir}/merged.png')
    print(f'合并图 -> {outdir}/merged.png  ({W}x{H})  剩余未解析字节 {len(d) - q}')

    # 渐变叠加色标
    for L in doc['layers']:
        blk = layer_block(d, L, b'lfx2')
        if not blk:
            continue
        top, _ = parse_block(d[blk['data_off']:blk['data_off'] + blk['size']])
        for slot in ('GrFl', 'gradientFillMulti'):
            obj = slot_object(top, slot)
            if obj is None:
                continue
            grad = obj.children.get('Grad')
            stops = grad.children.get('Clrs') if grad else None
            print(f'\n--- {L["name"]} {slot} 渐变 ---')
            print('  类型', grad.children.get('GrdT')._v if grad and grad.children.get('GrdT') else None,
                  ' 仿色', grad.children.get('Dthr')._v if grad and grad.children.get('Dthr') else None)
            if stops is not None and stops.typ == 'VlLs':
                for k in sorted(stops.children):
                    st = stops.children[k]
                    clr = st.children.get('Clr ')
                    typ = st.children.get('Type')
                    loc = st.children.get('Lctn')
                    mdp = st.children.get('Mdpn')
                    rgb = '#%02X%02X%02X' % tuple(
                        int(round(clr.children[x]._v)) for x in ('Rd  ', 'Grn ', 'Bl  ')) if clr else '?'
                    print(f'  色标 {k}: {rgb}  位置={loc._v if loc else "?"} '
                          f'类型={typ._v if typ else "?"} 中点={mdp._v if mdp else "?"}')
            for key in ('Angl', 'Rvrs', 'Algn', 'Scl '):
                n = obj.children.get(key)
                if n is not None:
                    print(f'  {key} = {n._v}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '结算界面-标签.psd')
