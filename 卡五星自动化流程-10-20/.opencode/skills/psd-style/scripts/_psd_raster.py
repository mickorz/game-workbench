# -*- coding: utf-8 -*-
"""PSD 图层像素通道的编解码与读写（RLE / 原始），供重排、换色脚本共用。

通道数据格式（PSD 规范）：

    u16 压缩标志   0 = 原始数据，1 = PackBits RLE（后面跟 高×u16 行字节数 + 各行数据）

图层记录 `head` 里的**通道表 (cid i16, clen u32)** 必须随数据长度一起重写 —— `write_image()`
负责重建 `head`，所以调用方只要给新的矩形和 RGBA 就行。

像素一律按 RGBA 逐像素存：`bytearray`，长度 `w*h*4`，顺序 R,G,B,A（与 PIL 一致）。
零尺寸图层（组头/分隔符，w×h = 0）原样保留，不重写 —— 它们那 2 字节的空通道数据
是 comp=0，改成 comp=1 没有意义。
"""
from __future__ import annotations

import colorsys
import struct

# ------------------------------------------------------------------ RLE 编解码


def unpackbits(data, off: int, nbytes: int):
    """解 nbytes 字节的 PackBits 数据；返回 (解出字节, 下一个偏移)。"""
    out = bytearray()
    i, end = off, off + nbytes
    while i < end:
        n = struct.unpack_from('>b', data, i)[0]
        i += 1
        if n >= 0:
            out += data[i:i + n + 1]
            i += n + 1
        elif n != -128:
            out += data[i:i + 1] * (1 - n)
            i += 1
    return bytes(out), i


def packbits(row: bytes) -> bytes:
    """行数据 → PackBits。与 unpackbits 严格互为逆运算。"""
    out = bytearray()
    i, n = 0, len(row)
    while i < n:
        run = 1
        while i + run < n and run < 128 and row[i + run] == row[i]:
            run += 1
        if run >= 2:
            out.append(256 - (run - 1))        # 有符号 -(run-1)
            out.append(row[i])
            i += run
            continue
        # 字面量：一直收到"下一个 >=3 的重复段"之前
        j = i + 1
        while j < n:
            r = 1
            while j + r < n and r < 128 and row[j + r] == row[j]:
                r += 1
            if r >= 3:
                break
            j += 1
        lit = row[i:j]
        while lit:
            chunk, lit = lit[:128], lit[128:]
            out.append(len(chunk) - 1)
            out += chunk
        i = j
    return bytes(out)


def decode_channel(data, off: int, w: int, h: int):
    """解一条通道（含 2 字节压缩标志）；返回 (平面字节, 下一个偏移)。"""
    comp = struct.unpack_from('>H', data, off)[0]
    off += 2
    if comp == 0:
        return bytes(data[off:off + w * h]), off + w * h
    if comp != 1:
        raise ValueError(f'不支持的压缩标志 {comp}')
    counts = struct.unpack_from('>%dH' % h, data, off) if h else ()
    off += 2 * h
    out = bytearray()
    for c in counts:
        if c > 65535:
            raise ValueError('行字节数越界')
        row, _ = unpackbits(data, off, c)
        off += c
        out += row[:w].ljust(w, b'\x00')
    return bytes(out[:w * h]).ljust(w * h, b'\x00'), off


def encode_channel(plane: bytes, w: int, h: int) -> bytes:
    """平面字节 → comp=1 的 RLE 通道数据。"""
    if w * h == 0:
        return struct.pack('>H', 0)
    rows = [packbits(plane[j * w:(j + 1) * w]) for j in range(h)]
    for r in rows:
        if len(r) > 65535:
            raise ValueError('RLE 行超过 65535 字节，应改用 comp=0')
    return (struct.pack('>H', 1)
            + b''.join(struct.pack('>H', len(r)) for r in rows)
            + b''.join(rows))


# ------------------------------------------------------------------ 图层像素


def layer_size(layer):
    t, l, b, r = layer.rect()
    return r - l, b - t


def read_image(layer):
    """图层像素 → (w, h, RGBA bytearray)。缺的通道按 0/255 补。"""
    w, h = layer_size(layer)
    if w <= 0 or h <= 0:
        return w, h, bytearray()
    planes = {}
    for (cid, clen), blob in zip(layer.chans, layer.chan_data):
        if len(blob) != clen:
            raise ValueError(f'图层 {layer.name!r} 通道 {cid} 数据长度不符')
        plane, used = decode_channel(blob, 0, w, h)
        if used != clen:
            raise ValueError(f'图层 {layer.name!r} 通道 {cid} 解码 {used} != 表 {clen}')
        planes[cid] = plane.ljust(w * h, b'\x00')[:w * h]
    rgba = bytearray(w * h * 4)
    for cid, shift in ((0, 0), (1, 1), (2, 2)):
        if cid in planes:
            rgba[shift::4] = planes[cid]
    rgba[3::4] = planes.get(-1, b'\xff' * (w * h))
    return w, h, rgba


def write_image(layer, rect, rgba):
    """用新的矩形 + RGBA 重建图层记录 head 与通道数据（原地改 layer）。"""
    t, l, b, r = rect
    w, h = r - l, b - t
    if w * h == 0:
        return False
    if len(rgba) != w * h * 4:
        raise ValueError(f'RGBA 长度 {len(rgba)} != {w}×{h}×4')
    planes = {0: bytes(rgba[0::4]), 1: bytes(rgba[1::4]),
              2: bytes(rgba[2::4]), -1: bytes(rgba[3::4])}
    blobs = []
    for cid, _old in layer.chans:
        if cid not in planes:
            raise ValueError(f'图层 {layer.name!r} 有非 RGBA 通道 {cid}，本模块不处理')
        blobs.append(encode_channel(planes[cid], w, h))

    head = bytearray(layer.head)
    struct.pack_into('>4i', head, 0, t, l, b, r)
    for i in range(len(layer.chans)):
        struct.pack_into('>I', head, 18 + 6 * i + 2, len(blobs[i]))
    layer.head = bytes(head)
    layer.chans = [(cid, len(blob)) for (cid, _), blob in zip(layer.chans, blobs)]
    layer.chan_data = blobs
    return True


# ------------------------------------------------------------------ 颜色换算

# 换算口径（技能第六节）：只换色相、饱和度不变，亮部明度可微调；
# 近白/近灰（S < SAT_MIN）和色相不在源区间（如近黑投影）原样不动。
HUE_LO, HUE_HI = 15.0, 80.0          # 只换算黄橙区间的像素/颜色
HUE_SRC_A, HUE_DST_A = 42.0, 210.0   # 默认目标 = 天蓝，锚点取自本项目既有对照
HUE_SRC_B, HUE_DST_B = 53.0, 193.0   # （H42→H210 = #FFC73F→#56AAFF，
HUE_CLAMP = (185.0, 222.0)           #   H53→H193 = #FFF5A4→#B8EFFF）
LIFT_MIN_L, LIFT = 0.55, 0.05        # 冷色同明度偏暗 → 亮部明度 +0.05
SAT_MIN = 0.10                       # 近白/近灰不动


def make_mapper(src_a=HUE_SRC_A, dst_a=HUE_DST_A, src_b=HUE_SRC_B, dst_b=HUE_DST_B,
                clamp=HUE_CLAMP, lift_min_l=LIFT_MIN_L, lift=LIFT,
                hue_lo=HUE_LO, hue_hi=HUE_HI, sat_min=SAT_MIN, sat_scale=1.0):
    """造一个颜色换算函数 `(r,g,b) -> (r,g,b)`。

    色相按两点线性映射：源锚点 `src_a`→`dst_a`、`src_b`→`dst_b`，结果钳在 `clamp`；
    饱和度乘 `sat_scale`；明度 `L >= lift_min_l` 的亮部加 `lift`。
    `src_a == src_b` 时退化为整体平移 `dst_a - src_a`。

    默认参数就是"黄 → 天蓝"（`remap_rgb` 用的那套），换个目标只是换锚点。
    """
    span = src_b - src_a

    def mapper(r: int, g: int, b: int):
        h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
        H = h * 360.0
        if s < sat_min or not (hue_lo <= H <= hue_hi):
            return r, g, b
        hn = dst_a if span == 0 else dst_a + (H - src_a) * (dst_b - dst_a) / span
        hn = min(clamp[1], max(clamp[0], hn))
        L = min(1.0, l + lift) if l >= lift_min_l else l
        r2, g2, b2 = colorsys.hls_to_rgb(hn / 360.0, L, min(1.0, s * sat_scale))
        return (int(round(r2 * 255)), int(round(g2 * 255)), int(round(b2 * 255)))

    return mapper


def map_hue(h: float) -> float:
    hn = HUE_DST_A + (h - HUE_SRC_A) * (HUE_DST_B - HUE_DST_A) / (HUE_SRC_B - HUE_SRC_A)
    return min(HUE_CLAMP[1], max(HUE_CLAMP[0], hn))


def in_yellow_family(h: float, s: float) -> bool:
    return s >= SAT_MIN and HUE_LO <= h <= HUE_HI


# 默认换算函数 = 黄 → 天蓝（保持既有行为不变）
remap_rgb = make_mapper()


def remap_rgba_inplace(rgba: bytearray, mapper=None):
    """整张 RGBA 换色：只动不透明像素的 RGB，alpha 不变。返回改动像素数。"""
    fn = mapper or remap_rgb
    cache, n = {}, 0
    for k in range(0, len(rgba), 4):
        if rgba[k + 3] == 0:
            continue
        key = (rgba[k], rgba[k + 1], rgba[k + 2])
        got = cache.get(key)
        if got is None:
            got = fn(*key)
            cache[key] = got
        if got != key:
            rgba[k], rgba[k + 1], rgba[k + 2] = got
            n += 1
    return n


def hexs(rgb) -> str:
    return '#%02X%02X%02X' % tuple(int(round(max(0.0, min(255.0, v)))) for v in rgb)
