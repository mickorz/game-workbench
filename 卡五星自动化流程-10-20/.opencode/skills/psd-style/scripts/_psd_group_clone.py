# -*- coding: utf-8 -*-
"""整组复制（含子层、分隔符、组头）并给新组改名。

`_psd_clone.py` 只能复制单个图层；组在文件里是连续一段 `layers[分隔符 .. 组头]`，
本脚本按段克隆并插到原组上方，`lyid` 全部另发新号避免 PS 报重复 ID。

用法：

    python _psd_group_clone.py <psd> --group <现有组名> --name <新组名> [--out <out>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _psd_struct as S
from _psd_group import clone_group_info, describe, find_group, find_group_by_lyid

from _psd_struct import parse


def main(argv=None):
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='复制整个 PSD 组并改名')
    ap.add_argument('psd')
    ap.add_argument('--group', help='要复制的组名（与 --组lyid 二选一）')
    ap.add_argument('--组lyid', type=int, dest='group_lyid',
                    help='按 lyid 定位组（组名可重复时用；与 --group 二选一）')
    ap.add_argument('--name', required=True, help='新组名')
    ap.add_argument('--out', help='输出 PSD（默认原地改）')
    a = ap.parse_args(argv)
    if a.group is None and a.group_lyid is None:
        ap.error('要给 --group 或 --组lyid')

    data = Path(a.psd).read_bytes()
    st = parse(data)
    if a.group_lyid is not None:
        before = find_group_by_lyid(st, a.group_lyid)
        print(f'按 lyid={a.group_lyid} 定位组（名 {st["layers"][before["header"]].name!r}）：')
    else:
        before = find_group(st, a.group)
    print('复制前：')
    print(describe(st, before))

    info, new_header, n = clone_group_info(st, before, a.name)
    out = a.out or a.psd
    Path(out).write_bytes(S.serialize(st))

    st2 = parse(Path(out).read_bytes())
    print(f'\n复制了 {n} 层（分隔符 + {n-2} 个子层 + 组头）→ 新组头索引 [{new_header}] {a.name!r}')
    for i, L in enumerate(st2['layers']):
        mark = ' ←新' if new_header - n + 1 <= i <= new_header else ''
        print(f'  [{i}] {L.name!r}{mark}')
    print(f'\n写出 {out}  （{len(data)} → {len(Path(out).read_bytes())} 字节）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
