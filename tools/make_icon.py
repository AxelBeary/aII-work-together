#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_icon.py — 用代码画看板图标（零依赖：只用标准库）

设计：圆角蓝底 + 三列错落的卡片 ＝ 一眼看出是「看板」。
为什么不用文字（比如「板」字）：纯标准库没有字体渲染，
硬画汉字只能靠位图字模，等于把字体嵌进代码里，不值当。
三列卡片这个形状在 16px 下也认得出。

产出（都写到 assets/）：
  board.png      256×256，网页 favicon / 文档配图用
  board-64.png   64×64，小尺寸备用
  board.ico      多尺寸（16/32/48/64/128/256），Windows 快捷方式用

跑法：python tools/make_icon.py
"""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

SS = 4                    # 超采样倍数（先画大图再缩，得到抗锯齿边缘）
BASE = 256                # 最终尺寸

BLUE = (0x5A, 0xA9, 0xFF)
INK = (0x06, 0x12, 0x1F)
CLEAR = (0, 0, 0, 0)


# ---------- 画布 ----------

class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 4)      # RGBA

    def put(self, x, y, rgb, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 4
            self.px[i:i + 4] = bytes((rgb[0], rgb[1], rgb[2], a))

    def fill_round_rect(self, x0, y0, x1, y1, r, rgb):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                if _inside_round(x, y, x0, y0, x1, y1, r):
                    self.put(x, y, rgb)

    def downsample(self, factor):
        w, h = self.w // factor, self.h // factor
        out = Canvas(w, h)
        n = factor * factor
        for y in range(h):
            for x in range(w):
                r = g = b = a = 0
                for dy in range(factor):
                    for dx in range(factor):
                        i = ((y * factor + dy) * self.w + (x * factor + dx)) * 4
                        r += self.px[i]
                        g += self.px[i + 1]
                        b += self.px[i + 2]
                        a += self.px[i + 3]
                out.px[(y * w + x) * 4: (y * w + x) * 4 + 4] = bytes(
                    (r // n, g // n, b // n, a // n))
        return out


def _inside_round(x, y, x0, y0, x1, y1, r):
    if x0 + r <= x < x1 - r or y0 + r <= y < y1 - r:
        return True
    cx = x0 + r if x < x0 + r else x1 - r - 1
    cy = y0 + r if y < y0 + r else y1 - r - 1
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def draw(size=None):
    """画一张 size×size 的图（内部按 SS 倍超采样）。"""
    target = size or BASE
    s = target * SS
    k = s / 256.0                   # 以 256 为设计基准缩放

    cv = Canvas(s, s)
    cv.fill_round_rect(0, 0, s, s, int(56 * k), BLUE)

    # 三列，宽度和间距按比例；y 起点各不相同 ⇒ 卡片错落，像在看板里
    col_w = int(46 * k)
    gap = int(24 * k)
    total = col_w * 3 + gap * 2
    left = (s - total) // 2
    card_h = int(30 * k)
    card_gap = int(16 * k)
    tops = [int(66 * k), int(96 * k), int(78 * k)]      # 每列起点不同

    for ci in range(3):
        x0 = left + ci * (col_w + gap)
        y = tops[ci]
        for _ in range(3):
            if y + card_h > s - int(52 * k):
                break
            cv.fill_round_rect(x0, y, x0 + col_w, y + card_h,
                               int(9 * k), INK)
            y += card_h + card_gap
    return cv.downsample(SS)


# ---------- 编码 ----------

def png_bytes(cv):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)                                # filter: none
        raw += cv.px[y * cv.w * 4:(y + 1) * cv.w * 4]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def ico_bytes(pngs):
    """把多个 PNG 打包成 .ico（Vista+ 支持 PNG 压缩的图标）。"""
    n = len(pngs)
    header = struct.pack("<HHH", 0, 1, n)
    dirs, body = b"", b""
    offset = 6 + 16 * n
    for w, png in pngs:
        dim = 0 if w >= 256 else w
        dirs += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset)
        body += png
        offset += len(png)
    return header + dirs + body


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    big = draw(256)
    (OUT / "board.png").write_bytes(png_bytes(big))

    small = draw(64)
    (OUT / "board-64.png").write_bytes(png_bytes(small))

    sizes = [16, 32, 48, 64, 128, 256]
    pngs = [(s, png_bytes(draw(s))) for s in sizes]
    ico = ico_bytes(pngs)
    (OUT / "board.ico").write_bytes(ico)

    print(f"board.png     {(OUT / 'board.png').stat().st_size:>7} 字节")
    print(f"board-64.png  {(OUT / 'board-64.png').stat().st_size:>7} 字节")
    print(f"board.ico     {(OUT / 'board.ico').stat().st_size:>7} 字节（{len(sizes)} 种尺寸）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
