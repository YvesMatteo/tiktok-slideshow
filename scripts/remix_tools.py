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


SHOTS = os.path.join(ROOT, 'assets', 'screenshots')
APPS = {  # key: (name, domain, tagline) for browser-preview slides
    'claude': ('Claude', 'claude.ai', '*the best AI assistant'),
    'checkvibe': ('CheckVibe', 'checkvibe.dev', '*finds the security holes in your app'),
    'lovable': ('Lovable', 'lovable.dev', '*builds the whole app for you'),
    'framer': ('Framer', 'framer.com', '*websites in an afternoon'),
    'supabase': ('Supabase', 'supabase.com', '*your backend in 5 minutes'),
    'higgsfield': ('Higgsfield', 'higgsfield.ai', '*every photo and video you need'),
    'vercel': ('Vercel', 'vercel.com', '*one click and it’s live'),
    'notion': ('Notion', 'notion.com', '*my second brain'),
    'github': ('GitHub', 'github.com', '*never lose your code again'),
    'railway': ('Railway', 'railway.com', '*servers without the headache'),
    'obsidian': ('Obsidian', 'obsidian.md', '*notes that think with you'),
    'posthog': ('PostHog', 'posthog.com', '*see what users actually do'),
}


def browser(key, w):
    """Mac-style browser window showing the app's real website screenshot. Returns RGBA with shadow."""
    name, domain, _ = APPS[key]
    shot = Image.open(os.path.join(SHOTS, f'{key}.png')).convert('RGB')
    bar = int(w * 0.055)
    body_h = int(w * 0.62)
    s = w / shot.width
    shot = shot.resize((w, max(body_h, int(shot.height * s))), Image.LANCZOS).crop((0, 0, w, body_h))  # top of page = hero
    win = Image.new('RGB', (w, bar + body_h), (236, 236, 239))
    win.paste(shot, (0, bar))
    d = ImageDraw.Draw(win)
    r = bar * 0.17
    for i, col in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        cx = bar * 0.55 + i * bar * 0.48
        d.ellipse((cx - r, bar / 2 - r, cx + r, bar / 2 + r), fill=col)
    pw, ph = w * 0.42, bar * 0.6
    d.rounded_rectangle((w / 2 - pw / 2, bar / 2 - ph / 2, w / 2 + pw / 2, bar / 2 + ph / 2), radius=ph / 2, fill=(255, 255, 255))
    d.text((w / 2, bar / 2), domain, font=font('Inter-Medium.ttf', int(bar * 0.36)), fill=(90, 90, 95), anchor='mm')
    mask = Image.new('L', win.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, win.width - 1, win.height - 1), radius=int(w * 0.025), fill=255)
    pad = 40
    out = Image.new('RGBA', (win.width + 2 * pad, win.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new('RGBA', out.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 70), (pad, pad + 14), mask)
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    win = win.convert('RGBA'); win.putalpha(mask)
    out.alpha_composite(win, (pad, pad))
    return out


def niche_app(key, bg=(205, 209, 223)):
    """theworkflowguy 168k layout: logo + name + '*tagline' on lavender, browser preview instead of phones."""
    name, domain, tag = APPS[key]
    im = Image.new('RGBA', (W, H), bg + (255,))
    logo = Image.open(os.path.join(LOGOS, f'{key}.png')).convert('RGBA').resize((250, 250), Image.LANCZOS)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh.paste((0, 0, 0, 60), (190, 160), logo.split()[3])
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    im.alpha_composite(logo, (190, 140))
    d = ImageDraw.Draw(im)
    fn = 96
    while font('Inter-SemiBold.ttf', fn).getlength(name) > W - 520 and fn > 60:
        fn -= 4
    d.text((480, 175), name, font=font('Inter-SemiBold.ttf', fn), fill=(15, 15, 15), anchor='la')
    ft = 40
    while font('Inter-SemiBold.ttf', ft).getlength(tag) > W - 500 and ft > 26:
        ft -= 2
    d.text((475, 300), tag, font=font('Inter-SemiBold.ttf', ft), fill=(15, 15, 15), anchor='la')
    win = browser(key, 940)
    im.alpha_composite(win, ((W - win.width) // 2, 500))
    return im.convert('RGB')
