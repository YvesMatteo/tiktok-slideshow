#!/usr/bin/env python3
"""Story-format TikTok slideshow compositor.

Renders the checkvibe "I almost lost my business" narrative as 3:4
(1080x1440) slides. Three slide types:

  - 'static' : a pre-rendered image (the Higgsfield title slide). Reuses
               slideshow.render_slide's static path so the title stays
               identical to the other slideshows.
  - 'story'  : a darkened background photo with a bold white caption. Copy
               sits either at the top ('top') or is split into a top line and
               a bottom line ('split'), matching the reference screenshots.
  - 'logo'   : pure-black slide with the checkvibe mark centred, "checkvibe.dev"
               underneath, and a short caption at the top.

White text stays legible over any photo via a continuous top+bottom dark
gradient plus the same soft drop-shadow used by the app slides.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

import slideshow as base   # reuse W/H, fonts, cover_crop, wrap, draw_text_soft

W, H = base.W, base.H
FONT = base.FONT
MARGIN = 80


def _gradient_scrim(canvas, top=True, bottom=True):
    """Darken the top and/or bottom bands so white captions read on any
    photo, mimicking the reference look (text lives in the dark bands)."""
    grad = Image.new('L', (1, H), 0)
    px = grad.load()
    for y in range(H):
        a = 0
        if top:
            # strong at the very top, fading out by ~46% height
            t = max(0.0, 1.0 - y / (H * 0.46))
            a = max(a, int(150 * t))
        if bottom:
            b = max(0.0, (y - H * 0.54) / (H * 0.46))
            a = max(a, int(150 * b))
        px[0, y] = a
    grad = grad.resize((W, H))
    scrim = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    scrim.putalpha(grad)
    black = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    black.putalpha(grad)
    canvas.alpha_composite(black)
    return canvas


def _fit_font(draw, text, maxw, start=68, floor=40, step=3):
    """Largest font size (<= start) whose longest wrapped line fits maxw."""
    for size in range(start, floor - 1, -step):
        f = ImageFont.truetype(FONT, size)
        lines = base.wrap(draw, text, f, maxw)
        if all(draw.textlength(ln, font=f) <= maxw for ln in lines):
            return f, lines, size
    f = ImageFont.truetype(FONT, floor)
    return f, base.wrap(draw, text, f, maxw), floor


def _render_story(slide, photo_path, out_path):
    im = base.cover_crop(Image.open(photo_path).convert('RGB'), W, H)
    im = ImageEnhance.Brightness(im).enhance(0.86)
    im = ImageEnhance.Color(im).enhance(0.97)
    canvas = im.convert('RGBA')

    pos = slide.get('pos', 'top')          # 'top' | 'split'
    maxw = W - 2 * MARGIN
    d = ImageDraw.Draw(canvas)

    if pos == 'split':
        _gradient_scrim(canvas, top=True, bottom=True)
        d = ImageDraw.Draw(canvas)
        top_txt = slide.get('top', '')
        bot_txt = slide.get('bottom', '')
        f_top, top_lines, s_top = _fit_font(d, top_txt, maxw, start=66, floor=44)
        base.draw_text_soft(canvas, (MARGIN, 150), top_lines, f_top,
                            int(s_top * 1.16))
        f_bot, bot_lines, s_bot = _fit_font(d, bot_txt, maxw, start=64, floor=42)
        bh = int(s_bot * 1.16) * len(bot_lines)
        by = H - 250 - bh
        base.draw_text_soft(canvas, (MARGIN, by), bot_lines, f_bot,
                            int(s_bot * 1.16))
    else:                                   # 'top'
        _gradient_scrim(canvas, top=True, bottom=False)
        d = ImageDraw.Draw(canvas)
        txt = slide.get('top', '')
        f, lines, s = _fit_font(d, txt, maxw, start=70, floor=44)
        base.draw_text_soft(canvas, (MARGIN, 150), lines, f, int(s * 1.16))

    canvas.convert('RGB').save(out_path, quality=92)
    return 0


def _render_logo(slide, logo_path, out_path):
    """Pure-black slide: checkvibe mark centred, 'checkvibe.dev' below, short
    caption at the top. The bundled logo is a white mark on a black rounded
    tile; we drop it straight onto black so only the mark reads."""
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 255))

    # caption at the top
    d = ImageDraw.Draw(canvas)
    maxw = W - 2 * MARGIN
    cap = slide.get('top', '')
    if cap:
        f, lines, s = _fit_font(d, cap, maxw, start=64, floor=42)
        base.draw_text_soft(canvas, (MARGIN, 130), lines, f, int(s * 1.16),
                            shadow_alpha=0.0)

    # centred mark. The bundled logo is a white mark on a near-black rounded
    # tile; to match the reference (mark floating on pure black) we key out
    # the dark tile: keep only the bright mark pixels, drop the tile to fully
    # transparent so nothing but the mark shows on the black canvas.
    MARK = 560
    logo = Image.open(logo_path).convert('RGB').resize((MARK, MARK), Image.LANCZOS)
    lum = logo.convert('L')                       # brightness = the white mark
    alpha = lum.point(lambda v: 0 if v < 60 else min(255, int((v - 60) * 3)))
    white = Image.new('RGBA', (MARK, MARK), (255, 255, 255, 0))
    white.putalpha(alpha)
    lx = (W - MARK) // 2
    ly = (H - MARK) // 2 - 40
    canvas.alpha_composite(white, (lx, ly))

    # wordmark under the logo
    f_word = ImageFont.truetype(FONT, 88)
    word = "checkvibe.dev"
    ww = d.textlength(word, font=f_word)
    wy = ly + MARK + 20
    base.draw_text_soft(canvas, ((W - ww) // 2, wy), [word], f_word, 96,
                        shadow_alpha=0.0)

    canvas.convert('RGB').save(out_path, quality=94)
    return 0


def render_slide(slide, photo_path, logos_dir, out_path):
    t = slide.get('type')
    if t == 'static':
        return base.render_slide(slide, slide['image'], logos_dir, out_path)
    if t == 'logo':
        return _render_logo(slide, slide['logo_path'], out_path)
    return _render_story(slide, photo_path, out_path)


def render_slideshow(config, photos_dir, logos_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, slide in enumerate(config):
        p = os.path.join(out_dir, f"slide_{i:02d}.jpg")
        if slide.get('type') in ('static', 'logo'):
            photo_path = slide.get('image')
        else:
            photo_path = os.path.join(photos_dir, slide['photo'])
        render_slide(slide, photo_path, logos_dir, p)
        paths.append(p)
    return paths
