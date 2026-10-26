#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 FGUI 占位图（纯 Python 标准库，不装 Pillow）。

刻意做成「一眼就知道不是真图」：
  · 品红底色 + 深品红棋盘格
  · 每 32px 一条网格线、四角黄色角标、整幅对角线
  · 正中写死像素尺寸（如 300x120），下面写 ASCII 标签
  · 给了 --scale9 就把九宫格拉伸区画出来（青色虚线）

安全默认：
  · 已存在的文件**不覆盖**（避免把美术的真图盖掉），要覆盖得显式加 --force
  · 写完自己回读 PNG 头校验像素尺寸，尺寸不符直接报错

用法：
  python .opencode/skills/fgui-flow/scripts/placeholder_png.py --size 300,120 \
      --out assets/xxx_mah_result/atlas/img_new_panel.png --label NewPanel_PH
  python .opencode/skills/fgui-flow/scripts/placeholder_png.py --size 180,60 --scale9 20,16,20,16 \
      --out 某个路径.png --label Tip_PH
  python .opencode/skills/fgui-flow/scripts/placeholder_png.py --self-test      # 自检，不碰工程

注意：中文标签写不进图里（内置只有 5x7 ASCII 点阵字模，标准库画不了中文字）。
      中文用途请写进 .opencode/work/美术清单.备注.txt（脚本会把建议行打印出来给你复制）。
"""

import argparse
import struct
import sys
import zlib
from pathlib import Path

# ----------------------------------------------------------------------------- 5x7 点阵字模
# 每个字形 7 行，每行 5 bit（最高位在最左）。够画尺寸和英文标签。
FONT = {
    "0": (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110),
    "1": (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "2": (0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111),
    "3": (0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110),
    "4": (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010),
    "5": (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110),
    "6": (0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110),
    "7": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000),
    "8": (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110),
    "9": (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100),
    "A": (0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "B": (0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110),
    "C": (0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110),
    "D": (0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110),
    "E": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111),
    "F": (0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000),
    "G": (0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01111),
    "H": (0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001),
    "I": (0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110),
    "J": (0b00111, 0b00010, 0b00010, 0b00010, 0b00010, 0b10010, 0b01100),
    "K": (0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001),
    "L": (0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111),
    "M": (0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001),
    "N": (0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001),
    "O": (0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "P": (0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000),
    "Q": (0b01110, 0b10001, 0b10001, 0b10001, 0b10101, 0b10010, 0b01101),
    "R": (0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001),
    "S": (0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110),
    "T": (0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100),
    "U": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110),
    "V": (0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100),
    "W": (0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b11011, 0b10001),
    "X": (0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001),
    "Y": (0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100),
    "Z": (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111),
    "x": (0b00000, 0b00000, 0b01010, 0b00100, 0b01010, 0b00000, 0b00000),
    "-": (0b00000, 0b00000, 0b00000, 0b11111, 0b00000, 0b00000, 0b00000),
    "_": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b11111),
    ".": (0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00110, 0b00110),
    ":": (0b00000, 0b00110, 0b00110, 0b00000, 0b00110, 0b00110, 0b00000),
    "/": (0b00001, 0b00010, 0b00010, 0b00100, 0b01000, 0b01000, 0b10000),
    "(": (0b00010, 0b00100, 0b01000, 0b01000, 0b01000, 0b00100, 0b00010),
    ")": (0b01000, 0b00100, 0b00010, 0b00010, 0b00010, 0b00100, 0b01000),
    "+": (0b00000, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0b00000),
    "#": (0b01010, 0b11111, 0b01010, 0b01010, 0b11111, 0b01010, 0b00000),
    " ": (0b00000,) * 7,
}
GLYPH_W, GLYPH_H, GLYPH_GAP = 5, 7, 1

# 配色（品红系 = 「这里缺图」的国际惯例色）
C_BG = (226, 0, 226)
C_BG_ALT = (198, 0, 198)
C_GRID = (160, 0, 160)
C_DIAG = (255, 120, 255)
C_BORDER = (110, 0, 110)
C_CORNER = (255, 232, 0)
C_TEXT = (18, 18, 18)
C_TEXT_HALO = (255, 255, 255)
C_SCALE9 = (0, 230, 230)


def setup_stdout():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ----------------------------------------------------------------------------- 画布


class Canvas:
    """最朴素的 RGB 画布。"""

    def __init__(self, w, h, color):
        self.w, self.h = w, h
        self.px = bytearray(bytes(color) * (w * h))

    def put(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(color)

    def rect(self, x0, y0, x1, y1, color):
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                self.put(x, y, color)

    def frame(self, x0, y0, x1, y1, color, thick=1):
        for t in range(thick):
            for x in range(x0 + t, x1 - t + 1):
                self.put(x, y0 + t, color)
                self.put(x, y1 - t, color)
            for y in range(y0 + t, y1 - t + 1):
                self.put(x0 + t, y, color)
                self.put(x1 - t, y, color)

    def hline(self, x0, x1, y, color):
        for x in range(max(0, x0), min(self.w, x1 + 1)):
            self.put(x, y, color)

    def vline(self, x, y0, y1, color):
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            self.put(x, y, color)

    def dashed_hline(self, y, color, dash=6, gap=5):
        x = 0
        while x < self.w:
            self.hline(x, x + dash - 1, y, color)
            x += dash + gap

    def dashed_vline(self, x, color, dash=6, gap=5):
        y = 0
        while y < self.h:
            self.vline(x, y, y + dash - 1, color)
            y += dash + gap

    def glyph(self, ch, x, y, scale, color):
        rows = FONT.get(ch) or FONT.get(ch.upper())
        if rows is None:
            # 没有字模（例如中文）：画个空框，至少能看出这里本来有字
            self.frame(x, y, x + GLYPH_W * scale - 1, y + GLYPH_H * scale - 1, color)
            return
        for ry, bits in enumerate(rows):
            for rx in range(GLYPH_W):
                if bits & (1 << (GLYPH_W - 1 - rx)):
                    self.rect(x + rx * scale, y + ry * scale,
                              x + rx * scale + scale - 1, y + ry * scale + scale - 1, color)

    def text_width(self, text, scale):
        if not text:
            return 0
        return len(text) * (GLYPH_W + GLYPH_GAP) * scale - GLYPH_GAP * scale

    def text(self, text, cx, y, scale, color, halo=None):
        """以 cx 为中心横向居中画一行字；halo 给白色描边（品红底上更好认）。"""
        w = self.text_width(text, scale)
        x = cx - w // 2
        if halo:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                self._run(text, x + dx, y + dy, scale, halo)
        self._run(text, x, y, scale, color)

    def _run(self, text, x, y, scale, color):
        for ch in text:
            if ch != " ":
                self.glyph(ch, x, y, scale, color)
            x += (GLYPH_W + GLYPH_GAP) * scale


def build_image(w, h, label, grid, scale9, text_scale):
    c = Canvas(w, h, C_BG)
    # 棋盘格底纹
    for y in range(h):
        for x in range(w):
            if ((x // 8) + (y // 8)) % 2 == 1:
                c.put(x, y, C_BG_ALT)
    # 网格
    if grid > 0:
        for x in range(grid, w, grid):
            c.vline(x, 0, h - 1, C_GRID)
        for y in range(grid, h, grid):
            c.hline(0, w - 1, y, C_GRID)
    # 对角线
    steps = max(w, h)
    for i in range(steps):
        x = int(i * w / steps)
        y = int(i * h / steps)
        for d in range(2):
            c.put(x + d, y, C_DIAG)
    # 九宫格拉伸区
    if scale9:
        left, top, right, bottom = scale9
        c.dashed_vline(left, C_SCALE9)
        c.dashed_vline(w - right - 1, C_SCALE9)
        c.dashed_hline(top, C_SCALE9)
        c.dashed_hline(h - bottom - 1, C_SCALE9)
    # 四角角标
    arm = max(8, min(w, h) // 5)
    t = max(2, min(w, h) // 40)
    for (cx, cy, dx, dy) in ((0, 0, 1, 1), (w - 1, 0, -1, 1), (0, h - 1, 1, -1), (w - 1, h - 1, -1, -1)):
        for k in range(t):
            c.hline(cx, cx + dx * (arm - 1), cy + dy * k, C_CORNER)
            c.vline(cx + dx * k, cy, cy + dy * (arm - 1), C_CORNER)
    # 边框
    c.frame(0, 0, w - 1, h - 1, C_BORDER, 2)

    # 文字：第一行尺寸，第二行标签（没有就写 PH）
    scale = text_scale if text_scale > 0 else max(1, min(w, h) // 60)
    line1 = f"{w}x{h}"
    line2 = (label or "PH").strip()
    line2_scale = max(1, scale - 1)
    lh1, lh2 = GLYPH_H * scale, GLYPH_H * line2_scale
    gap = max(2, scale * 2)
    total = lh1 + gap + lh2
    y1 = (h - total) // 2
    y2 = y1 + lh1 + gap
    # 文字底下垫一块半透明不了的实心色块（标准库没有 alpha，用浅色块替代）
    pad = max(3, scale * 2)
    box_x0 = max(1, (w - max(c.text_width(line1, scale), c.text_width(line2, line2_scale))) // 2 - pad)
    box_x1 = min(w - 2, (w + max(c.text_width(line1, scale), c.text_width(line2, line2_scale))) // 2 + pad)
    c.rect(box_x0, y1 - pad, box_x1, y2 + lh2 + pad, (255, 214, 255))
    c.text(line1, w // 2, y1, scale, C_TEXT, halo=C_TEXT_HALO)
    c.text(line2, w // 2, y2, line2_scale, C_TEXT, halo=C_TEXT_HALO)
    return c


# ----------------------------------------------------------------------------- PNG 写出 / 回读


def write_png(canvas, path):
    raw = bytearray()
    stride = canvas.w * 3
    for y in range(canvas.h):
        raw.append(0)  # filter: None
        raw += canvas.px[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)  # 8bit truecolor
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return len(png)


def png_size(path):
    """回读 PNG 头取宽高，用来校验「实际像素尺寸 = 要求尺寸」。"""
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是合法 PNG")
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def parse_pair(text, what):
    parts = [p.strip() for p in str(text).replace("x", ",").replace("X", ",").split(",")]
    try:
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
        if len(parts) == 1:
            return int(parts[0]), int(parts[0])
    except ValueError:
        pass
    raise SystemExit(f"❌ {what} 格式不对：{text}（应为 宽,高 或 宽x高）")


def parse_quad(text):
    parts = [p.strip() for p in str(text).split(",")]
    if len(parts) != 4:
        raise SystemExit(f"❌ --scale9 要 4 个数字 l,t,r,b：{text}")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        raise SystemExit(f"❌ --scale9 必须是数字：{text}")


# ----------------------------------------------------------------------------- 主流程


def note_line(name, w, h, scale9, label, purpose):
    kind = f"九宫格 {scale9[0]},{scale9[1]},{scale9[2]},{scale9[3]}" if scale9 else "普通图（非九宫格）"
    desc = purpose or label or "（用途待补）"
    return f"{name} = 【占位图 · 待美术出图】{desc}，尺寸 {w}×{h}，{kind}"


def generate(size, out, label, grid, scale9, text_scale, force, purpose):
    w, h = size
    if not (1 <= w <= 8192 and 1 <= h <= 8192):
        print(f"❌ 尺寸超范围（1~8192）：{w}x{h}")
        return 1
    out = Path(out)
    if out.exists() and not force:
        print(f"❌ 目标文件已存在，拒绝覆盖（保护真图）：{out}")
        print("   确认要替换就加 --force")
        return 1
    if scale9:
        left, top, right, bottom = scale9
        if left + right >= w or top + bottom >= h:
            print(f"❌ 九宫格 {scale9} 与尺寸 {w}x{h} 不匹配（左右边框之和必须小于宽，上下之和必须小于高）")
            return 1
    canvas = build_image(w, h, label, grid, scale9, text_scale)
    nbytes = write_png(canvas, out)
    real = png_size(out)
    ok = real == (w, h)
    print(f"{'✅' if ok else '❌'} 已生成：{out}")
    print(f"   要求尺寸 {w}x{h} ｜ 实际像素 {real[0]}x{real[1]} ｜ 文件 {nbytes} B ｜ "
          f"{'校验通过' if ok else '校验失败（尺寸不符）'}")
    print(f"   图上文字：{w}x{h} / {label or 'PH'}")
    print(f"   备注建议行（可粘到 .opencode/work/美术清单.备注.txt）：\n     {note_line(out.name, w, h, scale9, label, purpose)}")
    if not ok:
        return 1
    return 0


def self_test():
    import shutil

    print("== placeholder_png.py 自检（写到技能目录下的 _selftest/，不碰工程 assets）==")
    tmp = Path(__file__).resolve().parent / "_selftest"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    cases = [
        ("300,120", None, "NewPanel_PH"),
        ("180,60", (20, 16, 20, 16), "Tip_PH"),
        ("64,64", None, "Icon_PH"),
        ("1024,256", None, "Banner_PH"),
    ]
    bad = 0
    for size_text, s9, label in cases:
        w, h = parse_pair(size_text, "--size")
        out = tmp / f"ph_{w}x{h}_{label}.png"
        rc = generate((w, h), out, label, 16, s9, 0, True, "自检")
        bad += 1 if rc else 0
    print(f"\n自检输出目录：{tmp}")
    print(f"结果：{len(cases) - bad}/{len(cases)} 通过" + ("（全部通过 ✅）" if not bad else ""))
    return 1 if bad else 0


def main(argv=None):
    setup_stdout()
    ap = argparse.ArgumentParser(
        description="生成 FGUI 占位图（纯标准库；含网格 + 角标 + 尺寸文字；默认不覆盖已存在文件）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--size", help="像素尺寸，如 300,120 或 300x120")
    ap.add_argument("--out", help="输出 PNG 路径")
    ap.add_argument("--label", default="", help="图上的 ASCII 标签（如 KW_NewTip_PH）")
    ap.add_argument("--purpose", default="", help="中文用途，只写进备注建议行，不画进图")
    ap.add_argument("--scale9", help="九宫格 l,t,r,b，给了就画出拉伸区")
    ap.add_argument("--grid", type=int, default=32, help="网格间距（默认 32，0=不画）")
    ap.add_argument("--text-scale", type=int, default=0, help="文字放大倍数（默认按尺寸自动）")
    ap.add_argument("--force", action="store_true", help="允许覆盖已存在的文件")
    ap.add_argument("--self-test", dest="self_test", action="store_true", help="自检：生成 4 个尺寸到临时目录并校验")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.size or not args.out:
        ap.print_help()
        print("\n至少要给 --size 和 --out")
        return 1
    size = parse_pair(args.size, "--size")
    scale9 = parse_quad(args.scale9) if args.scale9 else None
    return generate(size, args.out, args.label, args.grid, scale9, args.text_scale, args.force, args.purpose)


if __name__ == "__main__":
    sys.exit(main())
