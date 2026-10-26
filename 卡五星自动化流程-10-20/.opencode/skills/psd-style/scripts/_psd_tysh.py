# -*- coding: utf-8 -*-
"""临时探针 v4：打印 TySh 的 EngineData 全文（可读化）与 bounds / boundingBox 数值。"""
import re
import struct
import sys

from _psd_lfx import TYSH_DESC_OFFSET, Reader, layer_block, locate

sys.stdout.reconfigure(encoding='utf-8')


def pretty(b):
    """把 UTF-16BE 串换成可读引号形式，其余按 latin1 显示。"""
    out = []
    i = 0
    while i < len(b):
        if b[i] == 0 and i + 1 < len(b) and 0x20 <= b[i + 1] < 0x7f:
            j = i
            s = []
            while j + 1 < len(b) and b[j] == 0 and 0x20 <= b[j + 1] < 0x7f:
                s.append(chr(b[j + 1]))
                j += 2
            out.append('«' + ''.join(s) + '»')
            i = j
            continue
        ch = b[i]
        if 0x20 <= ch < 0x7f or ch in (9, 10, 13):
            out.append(chr(ch))
        else:
            out.append('\\x%02x' % ch)
        i += 1
    return ''.join(out)


def main(psd, layer='自摸'):
    d = open(psd, 'rb').read()
    doc = locate(d)
    L = doc['layers'][[x['name'] for x in doc['layers']].index(layer)]
    b = layer_block(d, L, b'TySh')
    raw = d[b['data_off']:b['data_off'] + b['size']]
    r = Reader(raw, TYSH_DESC_OFFSET)
    kids, _ = r.descriptor()

    for key in ('bounds', 'boundingBox'):
        n = kids.get(key)
        print(f'--- {key} ---')
        for k, ch in n.children.items():
            print(f'   {k!r} type={ch.typ} 值={ch._v}')

    ed = kids['EngineData']
    m = struct.unpack_from('>I', raw, ed.val_start)[0]
    payload = raw[ed.val_start + 4:ed.val_start + 4 + m]
    print(f'\n--- EngineData 内容 {len(payload)} 字节 ---')
    txt = pretty(payload)
    print(txt)
    print('\n--- 上述内容里的 /Text /FontSize 行 ---')
    for line in txt.split('\n'):
        if re.search(r'Text|FontSize|FontSet|RunLength|Kerning|Trailing|Leading|AutoLeading|Font \d|Size \d', line):
            print('   ', line.strip()[:160])


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '结算界面-标签.psd')
