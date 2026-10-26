# -*- coding: utf-8 -*-
"""图层体检：一眼看出每个图层是什么，以及「能不能直接改」。

回答三个问题：
  1. 这个图层是 普通 / 形状 / 文字 / 填充 / 调整 / 图层组 / **智能对象** —— 哪种？
  2. 带不带图层效果（`lfx2` / `lmfx`），哪些效果是开着的？
  3. 是智能对象的话：源在哪（嵌入在文件里 / 只是外链）、源叫什么、什么格式、多大、
     对应哪个 `lnk2` 条目 —— 决定了「改它里面的东西」这条路走不走得通。

用法：
    python _psd_layerinfo.py <psd>                # 体检全部图层
    python _psd_layerinfo.py <psd> <图层名>        # 只看一个（支持子串匹配）
    python _psd_layerinfo.py <psd> --json         # 给程序看的

判定依据（都是 PSD 图层记录里的 tagged block）：
    智能对象   SoLd（本体：Idnt/placed/Type/Trnf/Sz/Rslt）、PlLd（老版 placed layer）、SoLE（外链）
    源数据     lnk2 / lnkD（嵌入的源文件字节）、lnk3（外链）、liFD/liFE 条目标记
    文字       TySh
    形状       vmsk/vogk + SoCo/GdFl/PtFl（矢量蒙版 + 填充/渐变/图案填充）
    填充       SoCo/GdFl/PtFl（没有矢量蒙版就是纯填充层）
    调整       AdjL 类块（brit/levl/curv/hue2/selc/mixr/…）
    图层组     lsct
    效果       lfx2（标准）/ lmfx（本项目文件的写法，结构一样）
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _psd_struct as S
from _psd_lfx import TYSH_DESC_OFFSET, Reader, parse_block

FX_KEYS = (b'lfx2', b'lmfx')
LINK_KEYS = (b'lnk2', b'lnk3', b'lnkD')
SO_KEYS = (b'SoLd', b'PlLd', b'SoLE')
FILL_KEYS = (b'SoCo', b'GdFl', b'PtFl')
ADJ_KEYS = {b'brit': '亮度/对比度', b'levl': '色阶', b'curv': '曲线', b'hue2': '色相/饱和度',
            b'selc': '可选颜色', b'mixr': '通道混合器', b'post': '色调分离', b'thrs': '阈值',
            b'nvrt': '反相', b'grdm': '渐变映射', b'phfl': '照片滤镜', b'expA': '曝光度',
            b'vibA': '自然饱和度', b'blnc': '色彩平衡', b'clrL': '颜色查找', b'CgEd': '内容感知'}


# ------------------------------------------------------------------ 小工具

def norm(node) -> dict:
    """子节点索引：键名去空格转小写（'Rd  ' → 'rd'）；VlLs 的整数下标保留。"""
    out = {}
    for k, v in node.children.items():
        out[int(k) if isinstance(k, int) else str(k).strip().lower()] = v
    return out


def blocks_of(layer):
    return S.scan_blocks(layer.extra, S.blocks_offset(layer.extra)) or []


def block_keys(layer):
    return [b['key'] for b in blocks_of(layer)]


def global_blocks(tail: bytes):
    """layer-and-mask 段尾部的附加信息块（全局 lnk2 就在这里）。"""
    out, q = [], 4 + struct.unpack_from('>I', tail, 0)[0]
    while q + 12 <= len(tail):
        if tail[q:q + 4] != b'8BIM':
            break
        key = tail[q + 4:q + 8]
        size = struct.unpack_from('>I', tail, q + 8)[0]
        out.append((key, tail[q + 12:q + 12 + size]))
        q += 12 + size + (size & 1)
    return out


def link_entries(payload: bytes):
    """从一个 lnk2/lnk3/lnkD 载荷里抠出所有 liFD/liFE/liFA 条目。

    条目标记后面的布局（实测 Photoshop CC / Photopea 都这样）：
        4B 类型标记 | u32 版本 | u8 ID长度 + ID | u32 名长度 + UTF-16BE 名
        | 4B 文件类型('8BPS'/'8BPB'/…) | 4B creator | u32 标志 | u32 数据长度 | 数据
    """
    out = []
    for m in re.finditer(rb'liFD|liFE|liFA', payload):
        p = m.start()
        try:
            ver = struct.unpack_from('>I', payload, p + 4)[0]
            nid = payload[p + 8]
            uid = payload[p + 9:p + 9 + nid].decode('latin1', 'replace')
            q = p + 9 + nid
            nlen = struct.unpack_from('>I', payload, q)[0]
            name = payload[q + 4:q + 4 + nlen * 2].decode('utf-16-be', 'replace').rstrip('\x00')
            q2 = q + 4 + nlen * 2
            ftype = payload[q2:q2 + 4]
            creator = payload[q2 + 4:q2 + 8]
            dlen = struct.unpack_from('>I', payload, q2 + 12)[0]
            data = payload[q2 + 16:q2 + 16 + dlen]
        except Exception:
            continue
        ent = {'类型': payload[p:p + 4].decode('latin1'), '版本': ver, 'ID': uid,
               '文件名': name, '文件类型': ftype.decode('latin1', 'replace'),
               'creator': creator.decode('latin1', 'replace'),
               '数据字节': dlen, '嵌入': payload[p:p + 4] == b'liFD' and dlen > 0,
               '源格式': None, '源尺寸': None, '段首偏移': None}
        # 数据里找内嵌 PSD/PSB 头（'8BPS'，版本字段 1=PSD / 2=PSB）
        k = data.find(b'8BPS', 0, 4096)
        if k >= 0:
            ver2 = struct.unpack_from('>H', data, k + 4)[0]
            ch = struct.unpack_from('>H', data, k + 12)[0]
            h, w = struct.unpack_from('>II', data, k + 14)
            ent['源格式'] = ('PSB 大文档' if ver2 == 2 else 'PSD') + f'（{k} 字节包装头之后）'
            ent['源尺寸'] = [w, h]
            ent['段首偏移'] = k
            ent['通道'] = ch
        out.append(ent)
    return out


def all_links(st) -> list:
    """全文所有嵌入/链接源：全局 lnk* + 各图层自己带的 lnk*。"""
    out = []
    for key, payload in global_blocks(st['tail']):
        if key in LINK_KEYS:
            for e in link_entries(payload):
                e['所在'] = f'全局 {key.decode("latin1")}'
                out.append(e)
    for L in st['layers']:
        for b in blocks_of(L):
            if b['key'] in LINK_KEYS:
                payload = bytes(L.extra[b['data_off']:b['data_off'] + b['size']])
                for e in link_entries(payload):
                    e['所在'] = f'图层 {L.name!r} 的 {b["key"].decode("latin1")}'
                    out.append(e)
    return out


def so_detail(layer, links):
    """智能对象的源信息：SoLd 描述符 + 按 Idnt 匹配 lnk 条目。"""
    body = S.get_block(layer.extra, b'SoLd')
    info = {}
    if body:
        try:
            kids, _ = Reader(body, 12).descriptor()
            k = {str(a).strip().lower(): v for a, v in kids.items()}
            info['Idnt'] = k['idnt']._v.strip('\x00') if 'idnt' in k else None
            info['placed'] = k['placed']._v.strip('\x00') if 'placed' in k else None
            info['Type'] = k['type']._v if 'type' in k else None
            if 'sz' in k:
                sz = {str(a).strip().lower(): v._v for a, v in k['sz'].children.items()}
                info['源文档尺寸'] = [int(sz.get('wdth', 0)), int(sz.get('hght', 0))]
            if 'trnf' in k:
                info['变换四角'] = [round(v._v, 2) for v in k['trnf'].children.values()]
            if 'rslt' in k:
                info['源分辨率'] = k['rslt']._v[1]
        except Exception as e:
            info['解析错误'] = f'{type(e).__name__}: {e}'

    hit = [e for e in links if info.get('Idnt') and e['ID'] == info['Idnt']]
    info['源'] = hit
    info['源在文件里'] = any(e['嵌入'] for e in hit)
    info['外链'] = bool(hit) and not info['源在文件里']
    return info


def fx_summary(layer):
    for key in FX_KEYS:
        b = S.get_block(layer.extra, key)
        if b is None:
            continue
        try:
            top, _ = parse_block(bytes(b))
        except Exception as e:
            return {'块': key.decode('latin1'), '解析错误': str(e)}, []
        slots = []

        def rec(path, node):
            kids = norm(node)
            flags = {k: kids[k]._v for k in ('enab', 'present')
                     if k in kids and kids[k].typ == 'bool'}
            if flags:
                slots.append({'槽': path, '开': bool(flags.get('enab')),
                              'present': bool(flags.get('present'))})
            for kk, child in node.children.items():
                if isinstance(kk, int):
                    rec(f'{path}[{kk}]', child)
                elif child.typ in ('obj ', 'Objc', 'GlbO', 'VlLs'):
                    rec(f'{path}.{str(kk).strip()}', child)

        for kk, vv in top.items():
            rec(str(kk).strip(), vv)
        return {'块': key.decode('latin1'), '字节': len(b)}, slots
    return None, []


def layer_kind(layer, keys):
    has = set(keys)
    if b'lsct' in has:
        return '图层组', ''
    if has & set(SO_KEYS):
        return '智能对象', ''
    if b'TySh' in has:
        return '文字图层', ''
    fill = sorted(k.decode('latin1') for k in has & set(FILL_KEYS))
    if b'vmsk' in has or b'vogk' in has:
        return '形状图层', '填充=' + ','.join(fill) if fill else ''
    if fill:
        return '填充层', '填充=' + ','.join(fill)
    adj = sorted(ADJ_KEYS[k] for k in has if k in ADJ_KEYS)
    if adj:
        return '调整层', '类型=' + ','.join(adj)
    return '普通图层', ''


def layer_head_fields(layer):
    """记录头里的 不透明度 / 剪贴蒙版。"""
    head = layer.head
    nchan = struct.unpack_from('>h', head, 16)[0]
    base = 16 + 2 + 6 * nchan + 8          # 混合签名+键 之后
    op = head[base]
    clip = head[base + 1]
    return op, bool(clip)


def own_text(layer):
    """取**这一层自己** TySh 里的文字。

    ★ **不能按层名取**（原来是 `read_text(raw, L.name)`）：产物里经常有同名层
    —— 本仓实测 `XxxMahPiaoView` 的还原稿里有 5 个 `title`、4 个 `漂1`，
    按名字查会全部命中第一层，于是 5 个按钮的标题都被报成同一个内容，
    看着像「脚本把内容写错了」，其实是体检工具自己读错了层。
    """
    raw = S.get_block(layer.extra, b'TySh')
    if not raw:
        return None
    try:
        kids, _ = Reader(raw, TYSH_DESC_OFFSET).descriptor()
        node = kids.get('Txt ')
        if node is None or node.typ != 'TEXT':
            return '<TySh 里没有 Txt>'
        n = struct.unpack_from('>I', raw, node.val_start)[0]
        return raw[node.val_start + 4:node.val_start + 4 + n * 2] \
            .decode('utf-16-be', 'replace').rstrip('\x00')
    except Exception as e:
        return f'<读不出：{e}>'


def inspect(psd):
    raw = Path(psd).read_bytes()
    st = S.parse(raw)
    links = all_links(st)
    rows = []
    for L in st['layers']:
        keys = block_keys(L)
        kind, note = layer_kind(L, keys)
        fx, slots = fx_summary(L)
        op, clip = layer_head_fields(L)
        top, left, btom, rght = L.rect()
        mask_len = struct.unpack_from('>I', L.extra, 0)[0] if len(L.extra) >= 4 else 0
        row = {'序号': len(rows), '名字': L.name, '类型': kind, '备注': note,
               '矩形': [left, top, rght, btom], '尺寸': [rght - left, btom - top],
               '不透明度': op, '剪贴蒙版': clip, '图层蒙版': mask_len > 0,
               '效果块': fx['块'] if fx else None,
               '效果': slots,
               '开着的效果': [s['槽'] for s in slots if s['开'] and s['present']],
               '块': [k.decode('latin1') for k in keys]}
        if kind == '文字图层':
            row['文字'] = own_text(L)
        if kind == '智能对象':
            row['智能对象'] = so_detail(L, links)
        rows.append(row)
    return {'文件': str(psd), '图层数': len(rows), '图层': rows,
            '嵌入源总数': len(links), '源清单': links}


def render(res):
    print(f'{res["文件"]}   {res["图层数"]} 个图层')
    for r in res['图层']:
        w, h = r['尺寸']
        print(f'\n[{r["序号"]}] {r["名字"]!r}   {r["类型"]}   {w}×{h} @ 左上({r["矩形"][0]},{r["矩形"][1]})')
        extra = []
        if r['不透明度'] != 255:
            extra.append(f'不透明度 {r["不透明度"]}')
        if r['剪贴蒙版']:
            extra.append('剪贴蒙版')
        if r['图层蒙版']:
            extra.append('图层蒙版')
        if r['备注']:
            extra.append(r['备注'])
        if extra:
            print(f'      ' + '，'.join(extra))
        if r.get('文字') is not None:
            print(f'      文字 = {r["文字"]!r}')
        if r['效果块']:
            on = r['开着的效果']
            print(f'      图层效果：{r["效果块"]} —— 开 {len(on)} 个'
                  + (f'：{"、".join(on)}' if on else '（全关）')
                  + f'（共 {len(r["效果"])} 个槽；颜色路径用 _psd_fx_color.py --list 看）')
        else:
            print('      图层效果：无')
        so = r.get('智能对象')
        if so:
            if so.get('解析错误'):
                print(f'      智能对象：SoLd 解析异常 —— {so["解析错误"]}')
            print(f'      智能对象：ID={so.get("Idnt")}  Type={so.get("Type")}'
                  f'  源文档 {so.get("源文档尺寸")}  @{so.get("源分辨率")}ppi')
            if so.get('变换四角'):
                print(f'                变换四角 = {so["变换四角"]}')
            if so['源在文件里']:
                for e in so['源']:
                    print(f'                源：**嵌入的**（源就在这个 PSD 里）{e["文件名"]!r}'
                          f'  类型 {e["文件类型"]}/{e["creator"]}  {e["数据字节"]} 字节'
                          f'  内含 {e["源格式"]} {e["源尺寸"]}  [{e["所在"]}]')
            elif so.get('外链'):
                for e in so['源']:
                    print(f'                源：**链接的**（源是外部文件，PSD 里只有引用 + 缓存）'
                          f'{e["文件名"]!r} [{e["所在"]}]')
            else:
                print('                源：**找不到源数据**（只剩壳 + 光栅缓存；双击进去 PS 会报找不到源）')
    print(f'\n全文嵌入/链接源 {res["嵌入源总数"]} 条：')
    for e in res['源清单']:
        fmt = e['源格式'] or '（不是 PSD/PSB，或加了包装头）'
        print(f'  · {e["文件名"]!r}  {e["类型"]}  {e["数据字节"]} 字节  '
              f'{"嵌入" if e["嵌入"] else "外链"}  ID={e["ID"]}  [{e["所在"]}]')
        print(f'      源文档：{fmt}  {e["源尺寸"]}')


def main():
    import argparse
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='图层体检：类型 / 效果 / 智能对象源在哪')
    ap.add_argument('psd')
    ap.add_argument('图层名', nargs='?')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    res = inspect(a.psd)
    if a.图层名:
        want = a.图层名.lower()
        hit = [r for r in res['图层'] if want in r['名字'].lower()]
        if not hit:
            raise SystemExit(f'!! 没有匹配 {a.图层名!r} 的图层；现有：'
                             f'{[r["名字"] for r in res["图层"]]}')
        res['图层'] = hit
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        render(res)
    return 0


if __name__ == '__main__':
    sys.exit(main())
