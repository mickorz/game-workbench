# -*- coding: utf-8 -*-
"""PSD 图层结构解析 / 重写。

把 PSD 拆成可编辑的片段（图层记录 + 通道数据 + 尾部），再原样拼回去。
**先保证"解析 → 重写"与原文逐字节一致**（`--check` 自检），在此之上的任何改动才可信。

实测口径（`结算界面-标签.psd`，Photopea 写出的 PSD）：

    文件     = 文件头(26) + 颜色模式段 + 图像资源段
             + [u32 段长][layer-and-mask 内容] + 合并图数据
    layer-and-mask 内容 = [u32 段长][layer-info 内容 + 填充] + global mask + 附加信息
    layer-info 内容     = i16 图层数 + 各图层记录 + 通道数据
    图层记录           = 矩形(16) + 通道表(2+6n) + 混合签名/键(4+4)
                        + 不透明度/裁剪/标志/填充(4) + u32 额外数据长度 + 额外数据
    额外数据           = 图层蒙版(4+len) + 混合区间(4+len) + pascal 名 + 对齐 + tagged blocks
    tagged block       = 签名(4) + 键(4) + u32 长度 + 数据 + 奇数补 1 字节
    layer-info 段长字段 = 内容长度向上取整到 4 的倍数（字段本身 4 字节不计在内）
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


# --------------------------------------------------------------------- 通用

def _sane_key(k: bytes) -> bool:
    """像不像一个 4 字节 tagged-block 键（'luni' / 'lfx2' …）。"""
    return len(k) == 4 and all(33 <= ch < 127 for ch in k)


def _read_pascal(extra: bytes, q: int, end: int):
    """旧的 pascal 图层名（中文 PS 上是 GBK）；返回 (名字, 下一个位置)。"""
    if q >= end:
        return '', q
    n = extra[q]
    if n == 0:
        return '', q + 1
    raw = extra[q + 1:q + 1 + n]
    try:
        name = raw.decode('gbk')
    except Exception:
        name = raw.decode('latin1', 'replace')
    return name, q + 1 + n


def scan_blocks(extra: bytes, off: int):
    """从 off 起扫描 tagged blocks；不像就返回 None。"""
    blocks, q, end = [], off, len(extra)
    while q + 12 <= end:
        sig = extra[q:q + 4]
        key = extra[q + 4:q + 8]
        size = struct.unpack_from('>I', extra, q + 8)[0]
        if not _sane_key(key) or q + 12 + size > end:
            return None
        blocks.append({'sig': sig, 'key': key, 'size_off': q + 8,
                       'data_off': q + 12, 'size': size,
                       'pad_off': q + 12 + size, 'pad': extra[q + 12 + size:q + 12 + size + (size & 1)]})
        q += 12 + size + (size & 1)
    return blocks


def blocks_offset(extra: bytes) -> int:
    """第一条 tagged block 在额外数据里的偏移（跳过蒙版/混合区间/pascal 名）。"""
    q = 0
    if q + 4 <= len(extra):
        q += 4 + struct.unpack_from('>I', extra, q)[0]
    if q + 4 <= len(extra):
        q += 4 + struct.unpack_from('>I', extra, q)[0]
    _, q_name = _read_pascal(extra, q, len(extra))
    best = None
    for nxt in {q_name + (-(q_name - q) % 4), (q_name + 3) & ~3}:
        blocks = scan_blocks(extra, nxt)
        if blocks is None:
            continue
        score = len(blocks) + (2 if any(b['key'] == b'luni' for b in blocks) else 0)
        if best is None or score > best[0]:
            best = (score, nxt)
    if best is None:
        raise ValueError('额外数据里找不到 tagged blocks')
    return best[1]


def get_block(extra: bytes, key: bytes):
    """取一条 tagged block 的数据字节；没有就 None。"""
    off = blocks_offset(extra)
    for b in scan_blocks(extra, off) or []:
        if b['key'] == key:
            return bytes(extra[b['data_off']:b['data_off'] + b['size']])
    return None


def set_block(extra: bytes, key: bytes, data: bytes) -> bytes:
    """换掉一条 tagged block 的数据（长度可变），重建整段额外数据。"""
    base = bytes(extra)
    off = blocks_offset(base)
    blocks = scan_blocks(base, off)
    if blocks is None:
        raise ValueError('额外数据里找不到 tagged blocks')
    out = bytearray(base[:off])
    hit = False
    for b in blocks:
        payload = bytes(base[b['data_off']:b['data_off'] + b['size']])
        if b['key'] == key:
            payload = data
            hit = True
        out += b['sig'] + b['key'] + struct.pack('>I', len(payload)) + payload
        if len(payload) & 1:
            out += b'\x00'
    if not hit:
        raise KeyError(f'图层里没有 {key!r} 块')
    return bytes(out)


# ------------------------------------------------------------------ 结构体

class Layer:
    """一个图层记录：头部（含通道表）+ 额外数据 + 通道像素数据。"""

    __slots__ = ('head', 'chans', 'extra', 'chan_data')

    def __init__(self, head, chans, extra, chan_data):
        self.head = head            # 到 u32 额外数据长度字段为止
        self.chans = chans          # [(通道号, 字节数)]
        self.extra = extra          # 额外数据（tagged blocks）
        self.chan_data = chan_data  # 与 chans 一一对应的原始字节

    @property
    def name(self) -> str:
        d = get_block(self.extra, b'luni')
        if d is None:
            return ''
        n = struct.unpack_from('>I', d, 0)[0]
        return d[4:4 + n * 2].decode('utf-16-be', 'replace')

    def rect(self):
        return struct.unpack_from('>4i', self.head, 0)

    def copy(self):
        return Layer(self.head, list(self.chans), self.extra, list(self.chan_data))


def parse(data: bytes) -> dict:
    """拆开 PSD；返回可直接交给 serialize() 的片段字典。"""
    if data[:4] != b'8BPS':
        raise ValueError('不是 PSD 文件')
    st = {'header': data[:26]}
    p = 26
    cm = struct.unpack_from('>I', data, p)[0]
    st['color_mode'] = data[p:p + 4 + cm]
    p += 4 + cm
    ir = struct.unpack_from('>I', data, p)[0]
    st['resources'] = data[p:p + 4 + ir]
    p += 4 + ir

    st['lm_off'] = p
    lm = struct.unpack_from('>I', data, p)[0]
    lm_end = p + 4 + lm
    li_off = p + 4
    L = struct.unpack_from('>I', data, li_off)[0]
    content_start = li_off + 4
    content_end = content_start + L

    q = content_start
    count = struct.unpack_from('>h', data, q)[0]
    st['count'] = count
    q += 2
    layers = []
    for _ in range(abs(count)):
        rec_start = q
        nchan = struct.unpack_from('>h', data, q + 16)[0]
        table_end = q + 18 + 6 * nchan
        chans = []
        for i in range(nchan):
            cid = struct.unpack_from('>h', data, table_end - 6 * (nchan - i))[0]
            clen = struct.unpack_from('>I', data, table_end - 6 * (nchan - i) + 2)[0]
            chans.append((cid, clen))
        extra_len = struct.unpack_from('>I', data, table_end + 12)[0]
        extra = data[table_end + 16:table_end + 16 + extra_len]
        if len(extra) != extra_len:
            raise ValueError(f'图层 {len(layers)} 额外数据越界')
        layers.append(Layer(data[rec_start:table_end + 12], chans, extra, []))
        q = table_end + 16 + extra_len

    st['records_end'] = q
    for L_ in layers:
        for cid, clen in L_.chans:
            L_.chan_data.append(data[q:q + clen])
            if len(L_.chan_data[-1]) != clen:
                raise ValueError(f'图层 {L_.name!r} 通道数据越界')
            q += clen

    st['li_pad'] = data[q:content_end]           # layer-info 的填充字节（凑 4 的倍数）
    st['layers'] = layers
    st['tail'] = data[content_end:lm_end]        # global mask + 附加信息，原样保留
    st['image_data'] = data[lm_end:]
    st['_lm'] = lm
    st['_li_L'] = L
    return st


def serialize(st: dict) -> bytes:
    """按片段拼回 PSD，所有长度字段重算。"""
    body = bytearray(struct.pack('>h', st['count']))
    for L_ in st['layers']:
        body += L_.head
        body += struct.pack('>I', len(L_.extra))
        body += L_.extra
    for L_ in st['layers']:
        for blob in L_.chan_data:
            body += blob
    body += bytes(st['li_pad'])

    L = (len(body) + 3) & ~3                      # 段长向上取整到 4 的倍数
    li_section = struct.pack('>I', L) + bytes(body) + b'\x00' * (L - len(body))
    lm_content = li_section + bytes(st['tail'])
    return (bytes(st['header']) + bytes(st['color_mode']) + bytes(st['resources'])
            + struct.pack('>I', len(lm_content)) + lm_content + bytes(st['image_data']))


# --------------------------------------------------------------------- CLI

def _check(psd: str, verbose: bool = True) -> int:
    data = Path(psd).read_bytes()
    st = parse(data)
    again = serialize(st)
    ok = again == data
    print(f'{psd}')
    print(f'  原文件 {len(data)} 字节 → 重写 {len(again)} 字节   '
          f'逐字节一致：{"是 ✓" if ok else "否 ✗"}')
    if not ok:
        n = min(len(data), len(again))
        diff = [i for i in range(n) if data[i] != again[i]]
        print(f'  首个差异 @{diff[0] if diff else n}  共 {len(diff)} 处')
        if diff:
            i = diff[0]
            print(f'    原 {data[i - 8:i + 8].hex(" ")}')
            print(f'    新 {again[i - 8:i + 8].hex(" ")}')
        # 唯一已知的"合法差异"：Photopea 存盘把 layer-info 段长**只按 2 字节对齐**
        # （PSD 规范原文 "rounded up to a multiple of 2"），本模块统一按 4 对齐写。
        # 实测 `扣牌-按钮.psd` 回存后段长 197190（2 对齐、非 4 对齐）：差异只有两个
        # 长度字段各 +2，其余 23 万字节逐字节相同 —— 口径差异，不是解析错。
        if st['_li_L'] % 4:
            print(f'  说明：layer-info 段长 {st["_li_L"]} 不是 4 的倍数（Photopea 按 2 字节'
                  f'对齐写，规范允许）；本模块按 4 对齐重写，故长度字段差 '
                  f'{len(again) - len(data):+d} 字节 —— 文件本身合法，不是解析错。')
    if verbose:
        print(f'  图层数 {st["count"]}  layer-info 段长 {st["_li_L"]}  '
              f'layer-and-mask 段长 {st["_lm"]}  '
              f'填充 {len(st["li_pad"])} 字节  尾部 {len(st["tail"])} 字节')
        for i, L_ in enumerate(st['layers']):
            print(f'  [{i}] {L_.name!r:12} 矩形 {L_.rect()} '
                  f'通道 {[(c, l) for c, l in L_.chans]} '
                  f'额外数据 {len(L_.extra)} 字节 '
                  f'块 {[b["key"].decode("latin1") for b in scan_blocks(L_.extra, blocks_offset(L_.extra)) or []]}')
    return 0 if ok else 1


if __name__ == '__main__':
    import argparse
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='PSD 图层结构解析 / 重写（自检用）')
    ap.add_argument('psd')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    sys.exit(_check(a.psd, not a.quiet))
