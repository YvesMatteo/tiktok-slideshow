#!/usr/bin/env python3
"""MCP slideshow compositor.

Renders 3:4 (1080x1440) slides in the "laptop on a desk" style: a pre-made
Higgsfield plate (a MacBook showing an MCP server's site) with a rounded
number pill at the top and a caption at the bottom. Also renders a title
slide. Used by make_mcp_slideshow.py.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

W, H = 1080, 1440
ACCENT = (124, 240, 90)          # green highlight

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_FONTS_DIR = os.path.join(_SKILL_DIR, 'assets', 'fonts')
_BOLD = [os.path.join(_FONTS_DIR, 'Inter-Bold.ttf'),
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
_SEMI = [os.path.join(_FONTS_DIR, 'Inter-SemiBold.ttf')] + _BOLD
FONT_BOLD = next((p for p in _BOLD if os.path.exists(p)), _BOLD[-1])
FONT_SEMI = next((p for p in _SEMI if os.path.exists(p)), FONT_BOLD)


def plate_path(plates_dir, name):
    """Resolve a plate by name, preferring .jpg then .png."""
    for ext in ('.jpg', '.jpeg', '.png'):
        p = os.path.join(plates_dir, name + ext)
        if os.path.exists(p):
            return p
    return os.path.join(plates_dir, name + '.png')


def cover_crop(im, w, h):
    tr, ir = w / h, im.width / im.height
    if ir > tr:
        nw = int(im.height * tr)
        im = im.crop(((im.width - nw)//2, 0, (im.width - nw)//2 + nw, im.height))
    else:
        nh = int(im.width / tr)
        im = im.crop((0, (im.height - nh)//2, im.width, (im.height - nh)//2 + nh))
    return im.resize((w, h), Image.LANCZOS)


def _v_gradient(size, top_alpha, bottom_alpha):
    """Vertical black gradient layer, alpha interpolated top->bottom."""
    w, h = size
    grad = Image.new('L', (1, h))
    for y in range(h):
        a = top_alpha + (bottom_alpha - top_alpha) * (y / max(1, h - 1))
        grad.putpixel((0, y), int(a))
    grad = grad.resize((w, h))
    layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    layer.putalpha(grad)
    return layer


def _wrap(draw, text, font, maxw):
    out, line = [], ''
    for wd in text.split(' '):
        test = (line + ' ' + wd).strip()
        if draw.textlength(test, font=font) <= maxw or not line:
            line = test
        else:
            out.append(line)
            line = wd
    if line:
        out.append(line)
    return out


def _text_shadow(base, pos, lines, font, leading, fill=(255, 255, 255),
                 blur=9, alpha=0.85, offset=(0, 4), align_center=False):
    x, y = pos
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cy = y
    for ln in lines:
        lx = x
        if align_center:
            lw = d.textlength(ln, font=font)
            lx = (base.size[0] - lw) / 2
        d.text((lx, cy), ln, font=font, fill=fill + (255,))
        cy += leading
    a = layer.split()[3]
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * alpha)))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    off = Image.new('RGBA', base.size, (0, 0, 0, 0))
    off.paste(sh, offset)
    base.alpha_composite(off)
    base.alpha_composite(layer)
    return cy


def _pill(canvas, cx, top, text, font, pad_x=34, pad_y=18,
          bg=(0, 0, 0, 150), fg=(255, 255, 255)):
    d = ImageDraw.Draw(canvas)
    tw = d.textlength(text, font=font)
    asc, desc = font.getmetrics()
    th = asc + desc
    w = tw + 2 * pad_x
    h = th + 2 * pad_y
    x0 = cx - w / 2
    layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.rounded_rectangle([x0, top, x0 + w, top + h], radius=int(h / 2), fill=bg)
    canvas.alpha_composite(layer)
    _text_shadow(canvas, (x0 + pad_x, top + pad_y - 2), [text], font, th,
                 fill=fg, blur=6, alpha=0.5)
    return top + h


def render_content_slide(plate_path, num, name, caption, out_path):
    base = cover_crop(Image.open(plate_path).convert('RGB'), W, H).convert('RGBA')
    # legibility scrims: top for the pill, bottom for the caption
    base.alpha_composite(_v_gradient((W, 300), 150, 0), (0, 0))
    base.alpha_composite(_v_gradient((W, 560), 0, 210), (0, H - 560))

    f_pill = ImageFont.truetype(FONT_BOLD, 52)
    _pill(base, W // 2, 60, f"{num})  {name}", f_pill)

    f_cap = ImageFont.truetype(FONT_SEMI, 46)
    lead = 60
    lines = _wrap(ImageDraw.Draw(base), caption, f_cap, W - 150)
    block_h = lead * len(lines)
    y = H - 90 - block_h
    _text_shadow(base, (75, y), lines, f_cap, lead, align_center=True,
                 blur=8, alpha=0.9)
    base.convert('RGB').save(out_path, quality=92)


def _title_layout(draw, text, maxw, hi_word):
    """Largest bold font (<=118) that wraps text to <=3 lines within maxw."""
    words = text.split()
    for size in range(118, 60, -4):
        f = ImageFont.truetype(FONT_BOLD, size)
        lines, line = [], ''
        for wd in words:
            test = (line + ' ' + wd).strip()
            if draw.textlength(test, font=f) <= maxw or not line:
                line = test
            else:
                lines.append(line)
                line = wd
        if line:
            lines.append(line)
        if len(lines) <= 3 and all(draw.textlength(l, font=f) <= maxw for l in lines):
            return f, lines, size
    f = ImageFont.truetype(FONT_BOLD, 64)
    return f, _wrap(draw, text, f, maxw), 64


def render_title_slide(bg_plate, hook, sub, highlight, thumb_plates, out_path):
    bg = cover_crop(Image.open(bg_plate).convert('RGB'), W, H)
    bg = ImageEnhance.Brightness(bg).enhance(0.34)
    bg = bg.filter(ImageFilter.GaussianBlur(14)).convert('RGBA')
    bg.alpha_composite(_v_gradient((W, H), 90, 150), (0, 0))

    draw = ImageDraw.Draw(bg)
    f_title, lines, size = _title_layout(draw, hook, W - 150, highlight)
    lead = int(size * 1.12)
    hi = (highlight or '').lower()

    total = lead * len(lines)
    y = 250
    for ln in lines:
        lw = draw.textlength(ln, font=f_title)
        x = (W - lw) / 2
        # highlight matching words in green, rest white
        cx = x
        for i, wd in enumerate(ln.split(' ')):
            word = wd + ('' if i == len(ln.split(' ')) - 1 else ' ')
            color = ACCENT if hi and wd.strip('.,!').lower() in hi.split() else (255, 255, 255)
            _text_shadow(bg, (cx, y), [word], f_title, lead, fill=color,
                         blur=10, alpha=0.85)
            cx += draw.textlength(word, font=f_title)
        y += lead

    # sub pill (green)
    if sub:
        f_sub = ImageFont.truetype(FONT_BOLD, 44)
        _pill(bg, W // 2, y + 24, sub, f_sub, bg=ACCENT + (235,), fg=(6, 20, 4))

    # teaser row of small plate thumbnails near the bottom
    if thumb_plates:
        n = len(thumb_plates)
        SZ, GAP = 150, 20
        tot = n * SZ + (n - 1) * GAP
        x0 = (W - tot) // 2
        ty = H - SZ - 150
        row = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        for i, p in enumerate(thumb_plates):
            th = cover_crop(Image.open(p).convert('RGB'), SZ, SZ)
            mask = Image.new('L', (SZ, SZ), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, SZ, SZ], radius=26, fill=255)
            row.paste(th, (x0 + i * (SZ + GAP), ty), mask)
        bg.alpha_composite(row)

    bg.convert('RGB').save(out_path, quality=92)


def render_slideshow(config, plates_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, s in enumerate(config):
        p = os.path.join(out_dir, f"slide_{i:02d}.jpg")
        if s['type'] == 'title':
            render_title_slide(s['bg'], s['hook'], s['sub'], s['highlight'],
                               s['thumbs'], p)
        else:
            render_content_slide(plate_path(plates_dir, s['plate']),
                                 s['num'], s['name'], s['caption'], p)
        paths.append(p)
    return paths
