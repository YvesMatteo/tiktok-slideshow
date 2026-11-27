#!/usr/bin/env python3
"""Find every CheckVibe logo on a slide and put a small 'checkvibe.dev' under it.

    python3 scripts/logo_label.py --style A --preview out_dir    # render previews, change nothing
    python3 scripts/logo_label.py --style A --apply              # stamp the whole remix bank

Detection is multi-scale template matching against assets/logos/checkvibe.png
(edges, so it works on white, frosted-glass and photo backgrounds alike).
"""
from __future__ import annotations
import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, 'assets', 'remix_bank')
FONTS = os.path.join(ROOT, 'assets', 'fonts')
LOGO = os.path.join(ROOT, 'assets', 'logos', 'checkvibe.png')
DOMAIN = 'checkvibe.dev'


def _templates():
    """The logo flattened on white and on black (AI tiles sit on either), plus its edge map."""
    rgba = Image.open(LOGO).convert('RGBA')
    out = []
    for bg in ((255, 255, 255), (0, 0, 0)):
        flat = Image.new('RGB', rgba.size, bg)
        flat.paste(rgba, mask=rgba.split()[3])
        out.append(cv2.cvtColor(np.array(flat), cv2.COLOR_RGB2GRAY))
    return out


def find_logos(img, thresh=0.72, work=540):
    """-> [(x, y, size)] for each CheckVibe logo on the slide, in full-res pixels."""
    rgb = np.array(img.convert('RGB'))
    k = work / rgb.shape[1]
    gray = cv2.cvtColor(cv2.resize(rgb, (work, int(rgb.shape[0] * k)), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
    hits = []
    for tpl in _templates():
        for size in range(24, 270, 4):
            t = cv2.resize(tpl, (size, size), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(res >= thresh)
            hits += [(float(res[y, x]), int(x), int(y), size) for y, x in zip(ys, xs)]
    hits.sort(reverse=True)
    keep = []
    for s, x, y, z in hits:  # non-max suppression
        if all(abs(x - kx) > kz * 0.6 or abs(y - ky) > kz * 0.6 for _, kx, ky, kz in keep):
            keep.append((s, x, y, z))
    return [(round(x / k), round(y / k), round(z / k)) for _, x, y, z in keep]


def _luma(img, box):
    crop = img.convert('L').crop(box).resize((10, 10))
    return sum(crop.getdata()) / 100


def _flat(img, box):
    """True when box is empty background (no text or objects in it)."""
    x0, y0, x1, y1 = [int(v) for v in box]
    if x0 < 0 or y0 < 0 or x1 > img.width or y1 > img.height:
        return False
    crop = np.array(img.convert('L').crop((x0, y0, x1, y1)), dtype=np.float32)
    return crop.std() < 14


def _spot(img, x, y, size, h, tw):
    """Top y for the label: right under the logo if empty, else above it, else the first clear gap below."""
    gap, pad = int(size * 0.08), 14
    cx = x + size / 2
    box = lambda t: (cx - tw / 2 - pad, t - pad // 2, cx + tw / 2 + pad, t + h + pad // 2)  # noqa: E731
    below, above = y + size + gap, y - gap - h
    if _flat(img, box(below)):
        return below
    if _flat(img, box(above)):
        return above
    for t in range(below, int(y + size * 3.5), 6):
        if _flat(img, box(t)):
            return t
    return below


def _arrow(d, x, y, s, col, w):
    """Small north-east arrow drawn as lines (Inter has no arrow glyphs)."""
    d.line((x, y + s, x + s, y), fill=col, width=w)
    d.line((x + s * 0.35, y, x + s, y), fill=col, width=w)
    d.line((x + s, y, x + s, y + s * 0.65), fill=col, width=w)


def label(img, x, y, size, style):
    img = img.convert('RGBA')
    fs = max(16, int(size * 0.17))
    f = ImageFont.truetype(os.path.join(FONTS, 'Inter-SemiBold.ttf' if style != 'A' else 'Inter-Medium.ttf'), fs)
    cx = x + size / 2
    tw = f.getlength(DOMAIN) + (fs * 0.9 if style == 'C' else 0) + (fs * 1.4 if style == 'B' else 0)
    h = int(fs * (2.1 if style == 'B' else 1.5))  # the pill's padding needs clear space too
    top = _spot(img, x, y, size, h, tw)
    dark_bg = _luma(img, (int(cx - tw / 2), int(top), int(cx + tw / 2), int(top + h))) < 110
    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if style == 'A':  # plain app-label text, grey on light / white on dark, like iOS home screen labels
        col = (235, 235, 235, 255) if dark_bg else (110, 110, 110, 255)
        d.text((cx, top), DOMAIN, font=f, fill=col, anchor='ma')
    elif style == 'B':  # black pill badge, same black as the logo tile
        px, py = int(fs * 0.7), int(fs * 0.3)
        tw0 = f.getlength(DOMAIN)
        d.rounded_rectangle((cx - tw0 / 2 - px, top, cx + tw0 / 2 + px, top + fs + py * 2.6), radius=fs, fill=(10, 10, 10, 255),
                            outline=(255, 255, 255, 90) if dark_bg else None, width=2)
        d.text((cx, top + py), DOMAIN, font=f, fill=(255, 255, 255, 255), anchor='ma')
    else:  # 'C': link look, underlined, with a small drawn arrow
        col = (255, 255, 255, 255) if dark_bg else (20, 20, 20, 255)
        tw0 = f.getlength(DOMAIN)
        x0 = cx - tw / 2
        d.text((x0, top), DOMAIN, font=f, fill=col, anchor='la')
        lw = max(2, fs // 12)
        d.line((x0, top + fs * 1.18, x0 + tw0, top + fs * 1.18), fill=col, width=lw)
        _arrow(d, x0 + tw0 + fs * 0.25, top + fs * 0.25, fs * 0.55, col, lw + 1)
        if dark_bg:
            sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
            sh.putalpha(layer.split()[3].point(lambda v: int(v * 0.5)))
            img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    img.alpha_composite(layer)
    return img.convert('RGB')


def process(path, style):
    img = Image.open(path).convert('RGB')
    found = find_logos(img)
    for x, y, z in found:
        img = label(img, x, y, z, style)
    return img, found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--style', choices='ABC', required=True)
    ap.add_argument('--preview')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('slides', nargs='*')
    a = ap.parse_args()
    paths = a.slides or [os.path.join(BANK, d, f) for d in sorted(os.listdir(BANK)) if os.path.isdir(os.path.join(BANK, d))
                         for f in sorted(os.listdir(os.path.join(BANK, d))) if f.startswith('slide_')]
    for p in paths:
        img, found = process(p, a.style)
        if not found:
            continue
        print(f'{os.path.relpath(p, BANK)}: {len(found)} logo(s)', file=sys.stderr)
        if a.apply:
            img.save(p, quality=93)
        elif a.preview:
            os.makedirs(a.preview, exist_ok=True)
            img.save(os.path.join(a.preview, os.path.relpath(p, BANK).replace('/', '__')), quality=90)


if __name__ == '__main__':
    main()
