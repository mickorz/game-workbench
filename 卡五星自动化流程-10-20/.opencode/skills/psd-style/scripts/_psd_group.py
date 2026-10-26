# -*- coding: utf-8 -*-
"""PSD 组（图层文件夹）结构的定位与整组复制。

组的存储形态（PSD 规范，图层按"自下而上"排列）：

    索引 d      : 分隔符图层（lsct = 3，隐藏、名字通常是 `</Layer group>`）
    索引 d+1..h-1: 组内子图层（含嵌套组）
    索引 h      : 组头（lsct = 1 打开 / 2 关闭，就是图层面板里那一行）

所以"一个组"在文件里是**连续的一段** `layers[d .. h]`，复制整组就是把这一段克隆一份插到
`h` 之后（新组叠在原组上方）。

剪切蒙版关系在同组内是**按层次**（子层里 clip=1 的跟着它下面第一个 clip=0 的基底），
克隆整段会原样带走，不需要额外处理。
"""
from __future__ import annotations

import struct

from _psd_struct import get_block, set_block

LSCT_FOLDER_OPEN, LSCT_FOLDER_CLOSED, LSCT_DIVIDER = 1, 2, 3


def lsct_type(layer):
    """组的类型标记：1/2 = 组头，3 = 分隔符，None = 普通图层。"""
    d = get_block(layer.extra, b'lsct')
    return struct.unpack_from('>I', d, 0)[0] if d is not None and len(d) >= 4 else None


def clipping(layer) -> int:
    """图层记录里的 clipping 字节：0 = 剪切基底，1 = 被剪切。"""
    nchan = struct.unpack_from('>h', layer.head, 16)[0]
    return layer.head[18 + 6 * nchan + 9]


def visible(layer) -> bool:
    """图层是否可见。

    ⚠️ 图层记录 flags 字节的 bit1（0x02）是**隐藏位**：置位 = 隐藏，不置位 = 可见
    （规范写成 "bit 1 = visible" 很容易读反）。实测校对：`源文件\\选字.psd` 里
    `图层 0`（用户确认的隐藏白底）是 0x0a（置位=隐藏），而按钮组各层是 0x08（可见）。
    """
    nchan = struct.unpack_from('>h', layer.head, 16)[0]
    return not bool(layer.head[18 + 6 * nchan + 10] & 0x02)


def layer_lyid(L):
    """图层的 lyid（唯一 ID）；没有返回 None。"""
    d = get_block(L.extra, b'lyid')
    return struct.unpack_from('>I', d, 0)[0] if d is not None and len(d) >= 4 else None


def _group_info_from_header(layers, header: int) -> dict:
    """由组头索引算出 {header, divider, members}（分隔符按嵌套深度配对）。"""
    divider, depth = None, 0
    for j in range(header - 1, -1, -1):
        t = lsct_type(layers[j])
        if t in (LSCT_FOLDER_OPEN, LSCT_FOLDER_CLOSED):
            depth += 1
        elif t == LSCT_DIVIDER:
            if depth == 0:
                divider = j
                break
            depth -= 1
    if divider is None:
        raise SystemExit('!! 组找不到分隔符（lsct=3）')
    return {'header': header, 'divider': divider,
            'members': list(range(divider + 1, header))}


def find_group(st, name: str) -> dict:
    """按组头名字找组；返回 {'header','divider','members'}（都是索引）。

    ⚠️ 分隔符要按**嵌套深度**配对：从组头往下走，遇到组头（lsct=1/2）深度 +1、
    遇到分隔符（lsct=3）深度 -1，**深度归零的那个分隔符**才是这一组的。
    早期版本写的是"往下找第一个 lsct=3"，在**嵌套组**上会认错层：实测
    `源文件\扣牌-按钮.psd` 的外层组 `离开房间`[9] 真正的分隔符是 [0]，
    却被认成内层 `组 5`[7] 的分隔符 [1] → `clone_group` 会把内层分隔符当成
    新组块的底部隔符，复制出来的嵌套关系错乱（新组没有被自己的分隔符闭合）。
    非嵌套组上两种算法结果一致，所以之前没暴露。

    ⚠️ 组名**可能重复**（PSD 允许同名组，同色按钮一堆）。要精确到某一组时用
    `find_group_by_lyid`。
    """
    layers = st['layers']
    header = None
    for i, L in enumerate(layers):
        if L.name == name and lsct_type(L) in (LSCT_FOLDER_OPEN, LSCT_FOLDER_CLOSED):
            header = i
    if header is None:
        raise SystemExit(f'!! 找不到组 {name!r}；现有图层：'
                         f'{[L.name for L in layers]}')
    return _group_info_from_header(layers, header)


def find_group_by_lyid(st, lyid: int) -> dict:
    """按 lyid 找组（组名可重复时用这个精确命中）；返回同 find_group 的 dict。"""
    layers = st['layers']
    for i, L in enumerate(layers):
        if lsct_type(L) in (LSCT_FOLDER_OPEN, LSCT_FOLDER_CLOSED) and layer_lyid(L) == lyid:
            return _group_info_from_header(layers, i)
    groups = [(layer_lyid(L), L.name) for L in layers
              if lsct_type(L) in (LSCT_FOLDER_OPEN, LSCT_FOLDER_CLOSED)]
    raise SystemExit(f'!! 找不到 lyid={lyid} 的组；现有组 (lyid, 名)：{groups}')


def describe(st, info) -> str:
    layers = st['layers']
    out = [f"组 [{info['header']}] {layers[info['header']].name!r}"
           f"  分隔符 [{info['divider']}] {layers[info['divider']].name!r}"]
    for i in info['members']:
        L = layers[i]
        t, l, b, r = L.rect()
        out.append(f"     [{i}] {L.name!r:18} {r-l}×{b-t}  clip={clipping(L)} "
                   f"可见={visible(L)} 通道={[c for c, _ in L.chans]}")
    return '\n'.join(out)


def _max_lyid(st) -> int:
    top = 0
    for L in st['layers']:
        d = get_block(L.extra, b'lyid')
        if d is not None and len(d) >= 4:
            top = max(top, struct.unpack_from('>I', d, 0)[0])
    return top


def clone_group(st, name: str, new_name: str):
    """整组克隆并给新组头改名（按组名找组）；返回 (info, 新组头索引, 克隆层数)。"""
    return clone_group_info(st, find_group(st, name), new_name)


def clone_group_info(st, info, new_name: str):
    """整组克隆并给新组头改名（info 由 find_group / find_group_by_lyid 得到）。"""
    d, h = info['divider'], info['header']
    block = st['layers'][d:h + 1]
    max_lyid = _max_lyid(st)

    clones = []
    for L in block:
        c = L.copy()
        ly = get_block(c.extra, b'lyid')
        if ly is not None and len(ly) >= 4:
            max_lyid += 1
            c.extra = set_block(c.extra, b'lyid',
                                struct.pack('>I', max_lyid) + ly[4:])
        clones.append(c)

    header_clone = clones[-1]                      # 块内最后一个是组头
    header_clone.extra = set_block(
        header_clone.extra, b'luni',
        struct.pack('>I', len(new_name)) + new_name.encode('utf-16-be'))

    st['layers'][h + 1:h + 1] = clones
    st['count'] = (abs(st['count']) + len(clones)) * (1 if st['count'] > 0 else -1)
    st['li_pad'] = b''                             # serialize 会按 4 字节重算
    return info, h + 1 + len(clones) - 1, len(clones)
