#!/usr/bin/env python3
"""Generate a MapLibre SDF glyph range (0-255.pbf) for contour labels.

Only the handful of characters labels need (digits, minus, degree sign, F) are
rendered, from DejaVu Sans Bold, so the page needs no external glyph server.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
STACK = "DejaVu Sans Bold"
CHARS = " 0123456789-°F"
SIZE, BORDER, RADIUS, CUTOFF, SS = 24, 3, 8, 0.25, 16


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def fld(num, wt, v):
    if wt == 0:
        return varint(num << 3) + varint(v)
    return varint(num << 3 | 2) + varint(len(v)) + v


def zz(n):
    return (n << 1) ^ (n >> 31)


def glyph(font, ch):
    adv = round(font.getlength(ch) / SS)
    l, t, r, b = font.getbbox(ch, anchor="ls")
    if r <= l:
        return fld(1, 0, ord(ch)) + fld(3, 0, 0) + fld(4, 0, 0) + fld(5, 0, 0) + fld(6, 0, zz(-SIZE)) + fld(7, 0, adv)
    left, top = int(np.floor(l / SS)), int(np.ceil(-t / SS))
    w, h = int(np.ceil(r / SS)) - left, top + int(np.ceil(b / SS))
    W, H = w + 2 * BORDER, h + 2 * BORDER
    img = Image.new("L", (W * SS, H * SS), 0)
    ImageDraw.Draw(img).text(((BORDER - left) * SS, (BORDER + top) * SS), ch, font=font, fill=255, anchor="ls")
    a = np.asarray(img) > 127
    d = (distance_transform_edt(~a) - distance_transform_edt(a)) / SS  # +outside
    # sample at pixel centres
    d = d[SS // 2::SS, SS // 2::SS][:H, :W]
    v = np.clip(255 - 255 * (d / RADIUS + CUTOFF), 0, 255).astype(np.uint8)
    return (fld(1, 0, ord(ch)) + fld(2, 2, v.tobytes()) + fld(3, 0, w) + fld(4, 0, h)
            + fld(5, 0, zz(left)) + fld(6, 0, zz(top - 21)) + fld(7, 0, adv))


def main(out="web/glyphs"):
    font = ImageFont.truetype(FONT, SIZE * SS)
    stack = fld(1, 2, STACK.encode()) + fld(2, 2, b"0-255")
    for ch in CHARS:
        stack += fld(3, 2, glyph(font, ch))
    os.makedirs(f"{out}/{STACK}", exist_ok=True)
    with open(f"{out}/{STACK}/0-255.pbf", "wb") as f:
        f.write(fld(1, 2, stack))


if __name__ == "__main__":
    main(*sys.argv[1:])
