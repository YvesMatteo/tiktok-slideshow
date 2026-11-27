#!/usr/bin/env python3
"""Build-time helpers for assets/remix_bank decks (not used at posting time).

Workflow per deck: Pinterest photo or original viral slide -> light Nano Banana 2
edit on Higgsfield -> these helpers stamp the *real* CheckVibe logo and *real*
text on top (image models garble small logos and text) -> slide_XX.jpg in a
bank folder with deck.json.
"""
from __future__ import annotations
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, 'assets', 'fonts')
LOGOS = os.path.join(ROOT, 'assets', 'logos')
W, H = 1080, 1440


def font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def cover(im, w=W, h=H):
    im = im.convert('RGB')
    s = max(w / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def find_dark_tile(im, region, thresh=45):
    """Bounding box (x0,y0,x1,y1) of the first near-black square tile inside region (fractions)."""
    w, h = im.size
    x0, y0, x1, y1 = int(region[0] * w), int(region[1] * h), int(region[2] * w), int(region[3] * h)
    px = im.convert('RGB').load()
    dark = lambda x, y: sum(px[x, y]) / 3 < thresh  # noqa: E731
    top = next((y for y in range(y0, y1) if sum(dark(x, y) for x in range(x0, x1, 3)) > 8), None)
    if top is None:
        return None
    def run(y):
        xs = [x for x in range(x0, x1) if dark(x, y)]
        return (min(xs), max(xs)) if xs else (None, None)
    a, b = run(min(top + 25, y1 - 1))
    if a is None:
        return None
    a, b = run(min(top + (b - a) // 2, y1 - 1))
    return a, top, b, top + (b - a)


def stamp_logo(im, box, key='checkvibe', pad=0.04):
    """Cover an AI-drawn tile with the real logo file."""
    im = im.convert('RGB')
    x0, y0, x1, y1 = box
    w = x1 - x0
    p = int(w * pad)
    bg = im.getpixel((max(0, x0 - p - 10), (y0 + y1) // 2))
    ImageDraw.Draw(im).rectangle((x0 - p, y0 - p, x1 + p, y1 + p), fill=bg)
    logo = Image.open(os.path.join(LOGOS, f'{key}.png')).convert('RGBA').resize((w + 2 * p, w + 2 * p), Image.LANCZOS)
    im.paste(logo, (x0 - p, y0 - p), logo)
    return im


def soft_text(im, xy, text, f, fill=(255, 255, 255), anchor='la', shadow=0.55):
    """White text with a soft drop shadow, TikTok-native look."""
    im = im.convert('RGBA')
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=f, fill=fill + (255,), anchor=anchor)
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
    sh.putalpha(layer.split()[3].point(lambda v: int(v * shadow)))
    off = Image.new('RGBA', im.size, (0, 0, 0, 0))
    off.paste(sh.filter(ImageFilter.GaussianBlur(8)), (0, 4))
    im.alpha_composite(off)
    im.alpha_composite(layer)
    return im.convert('RGB')


def quiet_top(im):
    """True when the band where hook text goes (y 130-300) is low-detail, i.e. text won't sit on the subject."""
    band = im.convert('L').crop((200, 130, 800, 300)).filter(ImageFilter.FIND_EDGES)
    return sum(band.getdata()) / (600 * 170) < 12


def hook_two_line(photo, small, big, arrow=True):
    """theworkflowguy hook: small line + bigger line, left-aligned in the upper third, swipe arrow."""
    im = cover(photo)
    y = 150 if quiet_top(im) else 330  # keep the text off the subject when the top band is empty
    im = soft_text(im, (230, y), small, font('Inter-Medium.ttf', 50))
    im = soft_text(im, (230, y + 65), big, font('Inter-SemiBold.ttf', 78))
    if arrow:
        im = soft_text(im, (W - 130, H - 170), '—>', font('Inter-Medium.ttf', 64), anchor='ra')
    return im


def glass_apps(bg_photo, small, big, apps, tile=None):
    """theworkflowguy body slide: blurred photo, '. the best / <big>' header, frosted card with app icons."""
    bg = cover(bg_photo).filter(ImageFilter.GaussianBlur(28))
    im = bg.convert('RGBA')
    im = Image.alpha_composite(im, Image.new('RGBA', im.size, (0, 0, 0, 60)))
    # frosted card: lighter blurred region + thin light border
    card = (130, 470, W - 50, H + 60)
    mask = Image.new('L', im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(card, radius=90, fill=255)
    frost = Image.alpha_composite(im, Image.new('RGBA', im.size, (255, 255, 255, 38)))
    im.paste(frost, (0, 0), mask)
    ImageDraw.Draw(im).rounded_rectangle(card, radius=90, outline=(255, 255, 255, 110), width=3)
    im = im.convert('RGB')
    im = soft_text(im, (200, 300), '•', font('Inter-SemiBold.ttf', 44), shadow=0.3)
    im = soft_text(im, (295, 280), small, font('Inter-SemiBold.ttf', 66), shadow=0.3)
    size = 84
    while font('Inter-Medium.ttf', size).getlength(big) > W - 330 and size > 50:
        size -= 2
    im = soft_text(im, (295, 370), big, font('Inter-Medium.ttf', size), shadow=0.3)
    im = im.convert('RGBA')
    size, gap, x, y = 190, 85, 215, 580
    for key, label in apps:
        logo = Image.open(os.path.join(LOGOS, f'{key}.png')).convert('RGBA').resize((size, size), Image.LANCZOS)
        im.alpha_composite(logo, (x, y))
        im = soft_text(im, (x + size // 2, y + size + 22), label, font('Inter-Medium.ttf', 36), anchor='ma', shadow=0.3).convert('RGBA')
        x += size + gap
    if tile is not None:
        t = cover(tile, 540, 380)
        im.paste(t, (200, 920))
    return im.convert('RGB')
