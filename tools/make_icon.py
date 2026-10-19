#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_icon.py — 用代码画看板图标（零依赖：只用标准库）

设计（2026-10-20 第二版，用户说第一版「不好看」）：
  · 蓝底改成**竖向渐变**，再压一圈很淡的内描边 ⇒ 有体积感，不是一块平色
  · 三列卡片**顶对齐**、高度依次递减 ⇒ 读成「活从左边流到右边」，不再是三堆随机药丸
  · 中间列顶上那张用**白卡**当视觉焦点（16px 下就是一个小亮点，认得出）
  · 所有边都在 4 倍超采样下画，缩到 16px 仍然干净

为什么不用汉字「板」：纯标准库没有字体渲染，硬画只能嵌位图字模，不值当。

产出（都写到 assets/）：
  board.png        256×256，网页 favicon / 文档配图
  board-64.png     64×64
  board.ico        多尺寸（16/24/32/48/64/128/256），Windows 快捷方式/托盘/任务栏
  icon-preview.png 自检用：几种变体 × 几种尺寸拼在一张图上（改设计时先看它）

跑法：python tools/make_icon.py
"""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

SS = 4                     # 超采样倍数
BASE = 256

# 底色渐变（上浅下深）
BG_TOP = (0x8C, 0xC4, 0xFF)
BG_BOTTOM = (0x3C, 0x7F, 0xD4)
CARD = (0x0C, 0x1D, 0x30)
CARD_HI = (0xF4, 0xFA, 0xFF)
EDGE = (255, 255, 255, 0x2E)
GLOSS = (255, 255, 255, 0x12)


def _line(cv, x0, y0, x1, y1, width, rgba):
    """画一条粗线（端点圆头）：用距离场判断，避免引第三方库。"""
    hw = width / 2.0
    x_min, x_max = int(min(x0, x1) - hw - 2), int(max(x0, x1) + hw + 3)
    y_min, y_max = int(min(y0, y1) - hw - 2), int(max(y0, y1) + hw + 3)
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    for y in range(max(0, y_min), min(cv.h, y_max)):
        for x in range(max(0, x_min), min(cv.w, x_max)):
            if L2 <= 0:
                t = 0.0
            else:
                t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / L2))
            px, py = x0 + t * dx, y0 + t * dy
            if (x - px) ** 2 + (y - py) ** 2 <= hw * hw:
                cv.blend(x, y, rgba)


def _check(cv, x0, y0, x1, y1, rgba):
    """在矩形里画一个对勾（表示「做完了」）。"""
    w, h = x1 - x0, y1 - y0
    th = max(2.0, 0.14 * min(w, h))
    _line(cv, x0 + 0.26 * w, y0 + 0.52 * h, x0 + 0.44 * w, y0 + 0.71 * h, th, rgba)
    _line(cv, x0 + 0.44 * w, y0 + 0.71 * h, x0 + 0.76 * w, y0 + 0.30 * h, th, rgba)


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 4)

    # ---- 基础 ----
    def set(self, x, y, rgba):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 4
            self.px[i:i + 4] = bytes(rgba)

    def blend(self, x, y, rgba):
        """把 rgba 叠到已有像素上（alpha 混合）。"""
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        i = (y * self.w + x) * 4
        a = rgba[3] / 255.0
        for k in range(3):
            self.px[i + k] = int(self.px[i + k] * (1 - a) + rgba[k] * a)
        self.px[i + 3] = min(255, int(self.px[i + 3] * (1 - a) + 255 * a))

    # ---- 形状 ----
    def round_rect(self, x0, y0, x1, y1, r, rgba_or_fn, blend=False):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                if not _inside_round(x, y, x0, y0, x1, y1, r):
                    continue
                col = rgba_or_fn(x, y) if callable(rgba_or_fn) else rgba_or_fn
                if blend:
                    self.blend(x, y, col)
                else:
                    self.set(x, y, col)

    def ring_round(self, x0, y0, x1, y1, r, width, rgba):
        """画一圈内描边：在外圆角矩形里、内圆角矩形外的那一圈做 alpha 混合。"""
        ix0, iy0, ix1, iy1, ir = x0 + width, y0 + width, x1 - width, y1 - width, max(0, r - width)
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                if not _inside_round(x, y, x0, y0, x1, y1, r):
                    continue
                if _inside_round(x, y, ix0, iy0, ix1, iy1, ir):
                    continue
                self.blend(x, y, rgba)

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
                out.px[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes(
                    (r // n, g // n, b // n, a // n))
        return out


def _inside_round(x, y, x0, y0, x1, y1, r):
    if x0 + r <= x < x1 - r or y0 + r <= y < y1 - r:
        return True
    cx = x0 + r if x < x0 + r else x1 - r - 1
    cy = y0 + r if y < y0 + r else y1 - r - 1
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _lerp(c0, c1, t):
    return tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def draw(size=BASE, counts=(3, 2, 2), hi_col=1, style="plain"):
    """画一张 size×size 的图标。

    counts  —— 每列放几张卡（从左到右）
    hi_col  —— 哪一列的顶上那张用白卡当焦点
    style   —— plain（纯卡片）/ check（白卡上带对勾）/ gloss（每张卡顶部一条高光）

    ⚠️ 小尺寸（≤32px）自动**简化**：9 张小卡缩到 16px 会糊成一团点，
       所以 <=32 改成三根粗柱（左高右低）＝大图里那三列塌成块。
    """
    s = size * SS
    k = s / 256.0
    cv = Canvas(s, s)

    # 1) 圆角底板：竖向渐变
    top, bottom = BG_TOP, BG_BOTTOM
    def bg(x, y):
        t = (y / max(1, s - 1)) ** 0.85     # 上亮下暗，略微非线性，像有光从上面打下来
        return _lerp(top, bottom, t) + (255,)
    cv.round_rect(0, 0, s, s, int(58 * k), bg)

    # 2) 内描边：给边缘一点定义（不然放在浅色桌面上会糊）
    cv.ring_round(0, 0, s, s, int(58 * k), max(1, int(2.0 * k)), EDGE)

    if size <= 32:
        # ---- 小尺寸：三列「实心柱」，左高右低 ----
        bar_w = int(46 * k)
        gap = int(24 * k)
        total = bar_w * 3 + gap * 2
        left = (s - total) // 2
        top_y = int(58 * k)
        bottom_y = s - int(50 * k)
        heights = [1.0, 0.68, 0.42]
        for ci, hf in enumerate(heights):
            x0 = left + ci * (bar_w + gap)
            y1 = top_y + int((bottom_y - top_y) * hf)
            cv.round_rect(x0, top_y, x0 + bar_w, y1, int(12 * k), CARD + (255,))
        return cv.downsample(SS)

    # ---- 正常尺寸：三列卡片，顶对齐、数量递减 ----
    col_w = int(46 * k)
    gap = int(24 * k)
    total = col_w * 3 + gap * 2
    left = (s - total) // 2
    top_y = int(60 * k)
    card_h = int(34 * k)
    vgap = int(15 * k)
    radius = int(10 * k)

    for ci, n in enumerate(counts):
        x0 = left + ci * (col_w + gap)
        for i in range(n):
            y0 = top_y + i * (card_h + vgap)
            if y0 + card_h > s - int(34 * k):
                break
            hi = (ci == hi_col and i == 0)
            cv.round_rect(x0, y0, x0 + col_w, y0 + card_h, radius,
                          CARD_HI + (255,) if hi else CARD + (255,))
            if style == "gloss":
                cv.round_rect(x0 + int(3 * k), y0 + int(3 * k),
                              x0 + col_w - int(3 * k), y0 + int(9 * k),
                              int(4 * k), GLOSS, blend=True)
            if hi and style == "check":
                _check(cv, x0, y0, x0 + col_w, y0 + card_h,
                       CARD + (255,))
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


def preview(cands, sizes, path):
    """把候选 × 尺寸拼成一张对照图：上半深色底（任务栏），下半浅色底（浅色桌面）。"""
    pad, gap, label_w = 20, 24, 26
    rows = []
    for _, counts, hi_col, style in cands:
        rows.append([draw(s, counts, hi_col, style) for s in sizes])
    cell_w = sum(sizes) + gap * (len(sizes) - 1)
    W = pad * 2 + label_w + cell_w
    row_h = max(sizes) + gap
    block = len(rows) * row_h
    H = pad * 2 + block * 2 + gap
    cv = Canvas(W, H)

    # 背景：上半深、下半浅
    for y in range(H):
        for x in range(W):
            if y < H // 2:
                cv.set(x, y, (0x12, 0x15, 0x1A, 255))
            else:
                cv.set(x, y, (0xEC, 0xEF, 0xF4, 255))

    for half in (0, 1):
        base_y = pad + half * (block + gap)
        for ri, row in enumerate(rows):
            y = base_y + ri * row_h
            x = pad + label_w
            for img in row:
                for yy in range(img.h):
                    for xx in range(img.w):
                        i = (yy * img.w + xx) * 4
                        a = img.px[i + 3]
                        if not a:
                            continue
                        tgt = y + yy
                        if not (0 <= tgt < H and 0 <= x + xx < W):
                            continue
                        j = (tgt * W + x + xx) * 4
                        f = a / 255.0
                        for k in range(3):
                            cv.px[j + k] = int(cv.px[j + k] * (1 - f) + img.px[i + k] * f)
                        cv.px[j + 3] = 255
                x += img.w + gap
    path.write_bytes(png_bytes(cv))


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # 三个候选（改设计时先看这张对照图再拍板）
    cands = [("A", (3, 2, 2), 1, "plain"),
             ("B", (3, 2, 2), 1, "check"),
             ("C", (3, 2, 2), 1, "gloss")]

    for label, counts, hi_col, style in cands:
        (OUT / f"icon-cand-{label}.png").write_bytes(png_bytes(draw(256, counts, hi_col, style)))
    preview(cands, [192, 64, 32, 16], OUT / "icon-preview.png")

    # 正式产物用 B 版（白卡上打勾＝「这张卡完事了」；比纯白块更有产品含义）
    big = draw(256, style="check")
    (OUT / "board.png").write_bytes(png_bytes(big))
    (OUT / "board-64.png").write_bytes(png_bytes(draw(64, style="check")))

    sizes = [16, 24, 32, 48, 64, 128, 256]
    pngs = [(s, png_bytes(draw(s, style="check"))) for s in sizes]
    (OUT / "board.ico").write_bytes(ico_bytes(pngs))

    for n in ("board.png", "board-64.png", "board.ico", "icon-preview.png"):
        p = OUT / n
        print(f"{n:<18} {p.stat().st_size:>7} 字节")
    print(f"board.ico 含 {len(sizes)} 种尺寸：{sizes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
