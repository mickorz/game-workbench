# -*- coding: utf-8 -*-
"""改 PSD 图层名（重写 `luni` 块）。

用法:
    python _rename_layer.py <psd> <现有图层名> <新名> [--group <组名>] [--out <输出>]

只动 `luni`（PS / Photopea 显示的就是它），旧式 pascal 名保持原样。

`--group <组名>` 把查找范围限制在该组的块内（分隔符 .. 组头）—— 整组复制出来的
副本里子层名字和原组**完全一样**（实测 `扣牌-按钮.psd` 复制出两个按钮组后就有两个
`离开房间` 文字层），这时全局按名字查会命中原组那一个。加 `--group <副本组名>`
才能精准改副本里的那一层。

**为什么要走 _psd_struct**：layer-info 段长必须按 4 字节对齐（PS 自己就是 4 对齐写
的）。早期版本直接做「旧段长 + delta」的原地替换，当 delta 不是 4 的倍数时
（例如「自摸」→「漂10」是 +2 字节）会把段长写成非对齐值，`_psd_struct.py` 的
逐字节自检就会报错。加 `out_` 前缀恰好是 +8 字节，所以这个 bug 一直没暴露。

现在和 `_psd_lfx.py` 走同一条路：`_psd_struct.parse` → `set_block` → `serialize`
（serialize 会重算所有长度字段并按 4 字节补填充）。
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _psd_struct as S
from _psd_group import find_group, layer_lyid


def rename(src, layer_name, new_name, dst=None, group=None, lyid=None):
    """把某个图层的 luni 改成 new_name；返回 (输出路径, 旧名, 字节增量)。

    定位方式（精确到粗）：`lyid` > `group`+`layer_name` > 全局 `layer_name`。
    用 `lyid` 时 `layer_name` 会被忽略（CLI 里填 `-` 即可）。
    """
    dst = dst or src
    data = Path(src).read_bytes()
    st = S.parse(data)

    if lyid is not None:
        idx = next((i for i, L in enumerate(st['layers']) if layer_lyid(L) == lyid), None)
        if idx is None:
            raise SystemExit(f'!! 找不到 lyid={lyid} 的图层')
        print(f'  按 lyid={lyid} 定位到 [{idx}] {st["layers"][idx].name!r}')
    else:
        lo, hi = 0, len(st['layers']) - 1
        if group:
            info = find_group(st, group)
            lo, hi = info['divider'], info['header']
            print(f'  只在组 {group!r}（[{lo}]..[{hi}]）里找 {layer_name!r}')
        idx = None
        for i in range(lo, hi + 1):
            if st['layers'][i].name == layer_name:
                idx = i
                break
        if idx is None:
            raise SystemExit(f'!! 在 [{lo}]..[{hi}] 里找不到图层 {layer_name!r}；'
                             f'范围内的图层：{[L.name for L in st["layers"][lo:hi + 1]]}')

    old_name = st['layers'][idx].name
    if old_name == new_name:
        raise SystemExit(f'!! 新旧名相同：{new_name!r}')

    payload = struct.pack('>I', len(new_name)) + new_name.encode('utf-16-be')
    st['layers'][idx].extra = S.set_block(st['layers'][idx].extra, b'luni', payload)
    st['li_pad'] = b''                    # 交给 serialize 按 4 字节重算填充
    out = S.serialize(st)
    Path(dst).write_bytes(out)
    return dst, old_name, len(out) - len(data)


if __name__ == '__main__':
    import argparse
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='改 PSD 图层名（luni），用于加 out_ 导出前缀')
    ap.add_argument('psd')
    ap.add_argument('layer', help='现有图层名（用 --lyid 时填 - 即可）')
    ap.add_argument('new_name', help='新图层名（如 out_自摸）')
    ap.add_argument('--group', help='只在某个组的块内找该图层（同名子层时必加）')
    ap.add_argument('--lyid', type=int, help='按 lyid 定位图层（组名/层名可重复时用；此时 layer 填 -）')
    ap.add_argument('--out', help='输出 PSD（默认原地改）')
    a = ap.parse_args()
    dst, old, delta = rename(a.psd, a.layer, a.new_name, a.out, a.group, a.lyid)
    print(f'{old!r} → {a.new_name!r}   ({delta:+d} 字节)  ->  {dst}')
