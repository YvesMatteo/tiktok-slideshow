#!/usr/bin/env python3
"""TikTok slideshow compositor — COLLAGE / sticker variant.

Recreates the "tools I use" collage look: a lifestyle background photo, a
big centered app-name heading at the top, two or three dark translucent
rounded caption "stickers" scattered in the middle, and the app's real
screenshot as a rounded card anchored at the bottom. The title slide is a
lifestyle photo (Higgsfield) with a bold headline + subtitle overlaid at
the top. Fully separate from slideshow.py / slideshow_shots.py.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageChops

W, H = 1080, 1440
MARGIN = 64

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_FONTS_DIR = os.path.join(_SKILL_DIR, 'assets', 'fonts')
_LOGOS_DIR = os.path.join(_SKILL_DIR, 'assets', 'logos')


def _font(names, size):
    for n in names:
        p = os.path.join(_FONTS_DIR, n)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def f_bold(s):
    # headings — Poppins SemiBold reads as a native TikTok caption font
    return _font(['Poppins-SemiBold.ttf', 'Poppins-Bold.ttf', 'Inter-Bold.ttf'], s)


def f_semi(s):
    # caption stickers
    return _font(['Poppins-Medium.ttf', 'Poppins-SemiBold.ttf', 'Inter-SemiBold.ttf'], s)


def f_med(s):
    # subtitle
    return _font(['Poppins-Regular.ttf', 'Poppins-Medium.ttf', 'Inter-Medium.ttf'], s)


def cover_crop(im, w, h):
    tr, ir = w / h, im.width / im.height
    if ir > tr:
        nw = int(im.height * tr)
        im = im.crop(((im.width - nw)//2, 0, (im.width - nw)//2 + nw, im.height))
    else:
        nh = int(im.width / tr)
        im = im.crop((0, (im.height - nh)//2, im.width, (im.height - nh)//2 + nh))
    return im.resize((w, h), Image.LANCZOS)


def cover_top(im, w, h):
    """Cover-fill w x h but keep the TOP of the image (for website shots)."""
    ar_t, ar_i = w / h, im.width / im.height
    if ar_i > ar_t:                     # wider: match height, crop width centre
        nh = h
        nw = max(w, int(round(im.width * h / im.height)))
        im = im.resize((nw, nh), Image.LANCZOS)
        x = (nw - w) // 2
        return im.crop((x, 0, x + w, h))
    else:                               # taller/narrower: match width, crop top
        nw = w
        nh = max(h, int(round(im.height * w / im.width)))
        im = im.resize((nw, nh), Image.LANCZOS)
        return im.crop((0, 0, w, h))


def wrap(draw, text, font, maxw):
    out = []
    for i, para in enumerate(text.split('\n')):
        if i > 0:
            out.append('')
        line = ''
        for wd in para.split(' '):
            test = (line + ' ' + wd).strip()
            if draw.textlength(test, font=font) <= maxw or not line:
                line = test
            else:
                out.append(line)
                line = wd
        out.append(line)
    return out


def draw_centered(base, lines, font, y, leading, fill=(255, 255, 255),
                  shadow_alpha=0.5, shadow_blur=4, shadow_offset=(0, 3)):
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cy = y
    for ln in lines:
        if ln:
            w = d.textlength(ln, font=font)
            d.text(((base.width - w) / 2, cy), ln, font=font, fill=fill + (255,))
        cy += leading
    alpha = layer.split()[3]
    shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda a: int(a * shadow_alpha)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
    off = Image.new('RGBA', base.size, (0, 0, 0, 0))
    off.paste(shadow, shadow_offset)
    base.alpha_composite(off)
    base.alpha_composite(layer)
    return cy


def draw_chip(base, text, side, y, max_text_w=470):
    """Draw a dark rounded caption sticker. Returns (top, height)."""
    font = f_semi(38)
    tmp = ImageDraw.Draw(base)
    lines = wrap(tmp, text, font, max_text_w)
    line_h = 48
    pad_x, pad_y = 30, 22
    text_w = max(tmp.textlength(ln, font=font) for ln in lines if ln) if lines else 0
    box_w = int(min(max_text_w, text_w) + 2 * pad_x)
    box_h = int(line_h * len(lines) + 2 * pad_y)
    if side == 'left':
        x = MARGIN
    else:
        x = W - MARGIN - box_w
    # shadow
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.rounded_rectangle([x, y, x + box_w, y + box_h], radius=22,
                         fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(11))
    base.alpha_composite(sh)
    # chip body
    chip = Image.new('RGBA', base.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(chip)
    dc.rounded_rectangle([x, y, x + box_w, y + box_h], radius=22,
                         fill=(12, 12, 14, 176))
    cy = y + pad_y
    for ln in lines:
        if ln:
            dc.text((x + pad_x, cy), ln, font=font, fill=(255, 255, 255, 255))
        cy += line_h
    base.alpha_composite(chip)
    return y, box_h


def make_shot_card(shot_path, card_w, card_h, radius=26):
    card = cover_top(Image.open(shot_path).convert('RGB'), card_w, card_h).convert('RGBA')
    mask = Image.new('L', (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card_w - 1, card_h - 1],
                                           radius=radius, fill=255)
    card.putalpha(mask)
    return card


def _top_gradient(canvas, height=400, strength=110):
    grad = Image.new('L', (1, height), 0)
    for i in range(height):
        grad.putpixel((0, i), int(strength * (1 - i / height)))
    grad = grad.resize((W, height))
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    layer.paste((0, 0, 0), (0, 0), grad)
    canvas.alpha_composite(layer)


def _logo_tile(key, size, radius_frac=0.23):
    """Return the app's logo as a rounded app-icon tile (RGBA), or None."""
    if not key:
        return None
    path = os.path.join(_LOGOS_DIR, key + '.png')
    if not os.path.exists(path):
        return None
    logo = Image.open(path).convert('RGBA').resize((size, size), Image.LANCZOS)
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                           radius=int(size * radius_frac), fill=255)
    # round the corners while keeping any existing edge transparency
    logo.putalpha(ImageChops.multiply(logo.split()[3], mask))
    return logo


def draw_heading_with_icon(base, name, key, y, top_font_size=80,
                           icon_size=88, gap=22, fill=(255, 255, 255)):
    """Draw an app-icon tile + the app name as one horizontally centered group.

    Mirrors draw_centered's soft drop shadow on the text and gives the icon a
    matching soft shadow so it reads as a sticker on the photo. Falls back to a
    plain centered name when the app has no logo.
    """
    max_w = base.width - 2 * 72
    d = ImageDraw.Draw(base)
    fs = top_font_size
    font = f_bold(fs)
    tile = _logo_tile(key, icon_size)
    icon_w = icon_size if tile else 0
    icon_gap = gap if tile else 0
    while d.textlength(name, font=font) + icon_w + icon_gap > max_w and fs > 54:
        fs -= 4
        font = f_bold(fs)
    tw = d.textlength(name, font=font)
    group_w = icon_w + icon_gap + tw
    x0 = (base.width - group_w) / 2
    text_x = x0 + icon_w + icon_gap

    # ---- name with drop shadow (mirrors draw_centered) ----
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((text_x, y), name, font=font, fill=fill + (255,))
    alpha = layer.split()[3]
    shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda a: int(a * 0.5)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    off = Image.new('RGBA', base.size, (0, 0, 0, 0))
    off.paste(shadow, (0, 3))
    base.alpha_composite(off)
    base.alpha_composite(layer)

    # ---- icon tile, vertically centered on the glyphs, with a soft shadow ----
    if tile:
        bbox = d.textbbox((text_x, y), name, font=font)
        text_cy = (bbox[1] + bbox[3]) / 2
        icon_y = int(text_cy - icon_size / 2)
        icon_x = int(x0)
        sh = Image.new('RGBA', base.size, (0, 0, 0, 0))
        sh.paste(Image.new('RGBA', tile.size, (0, 0, 0, 255)), (icon_x, icon_y),
                 tile.split()[3])
        sh = sh.filter(ImageFilter.GaussianBlur(12))
        sh.putalpha(sh.split()[3].point(lambda a: int(a * 0.45)))
        off2 = Image.new('RGBA', base.size, (0, 0, 0, 0))
        off2.paste(sh, (0, 4))
        base.alpha_composite(off2)
        base.alpha_composite(tile, (icon_x, icon_y))
    return y


def draw_step_label(base, text, y, fill=(255, 255, 255)):
    """Draw a small centered narration line above the app heading, e.g.
    'First I go to' / 'Then I go to'. Mirrors the heading's soft drop shadow so
    it reads as part of the same sticker group. Returns the baseline y used."""
    font = f_med(46)
    d = ImageDraw.Draw(base)
    tw = d.textlength(text, font=font)
    x = (base.width - tw) / 2
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((x, y), text, font=font, fill=fill + (255,))
    alpha = layer.split()[3]
    shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda a: int(a * 0.55)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))
    off = Image.new('RGBA', base.size, (0, 0, 0, 0))
    off.paste(shadow, (0, 3))
    base.alpha_composite(off)
    base.alpha_composite(layer)
    return y


def render_slide(slide, photo_path, shots_dir, out_path):
    # ---- title slide: lifestyle photo + headline + subtitle overlay ----
    if slide.get('type') == 'title_overlay':
        im = cover_crop(Image.open(slide['image']).convert('RGB'), W, H)
        im = ImageEnhance.Brightness(im).enhance(0.94)
        canvas = im.convert('RGBA')
        # Optional vertical placement jitter so the title text isn't in the
        # exact same spot every run. The generator passes a small random
        # title_y; default keeps the original 104 position.
        title_y = int(slide.get('title_y', 104))
        grad_h = max(420, min(620, title_y + 456))
        _top_gradient(canvas, height=grad_h, strength=122)
        tmp = ImageDraw.Draw(canvas)
        f_head = f_bold(80)
        head_lines = wrap(tmp, slide['headline'], f_head, W - 2 * 84)
        y = draw_centered(canvas, head_lines, f_head, title_y, 92)
        if slide.get('sub'):
            f_sub = f_med(44)
            sub_lines = wrap(tmp, slide['sub'], f_sub, W - 2 * 130)
            draw_centered(canvas, sub_lines, f_sub, y + 16, 54,
                          fill=(240, 240, 240),
                          shadow_alpha=0.72, shadow_blur=6)
        canvas.convert('RGB').save(out_path, quality=92)
        return 0

    # ---- app slide: heading + chips + bottom screenshot card ----
    im = cover_crop(Image.open(photo_path).convert('RGB'), W, H)
    im = ImageEnhance.Brightness(im).enhance(0.86)
    im = ImageEnhance.Color(im).enhance(0.98)
    canvas = im.convert('RGBA')
    step_label = slide.get('step_label')
    _top_gradient(canvas, height=490 if step_label else 430, strength=120)

    # bottom screenshot card
    card_w, card_h = 862, 516
    card = make_shot_card(os.path.join(shots_dir, slide['shot'] + '.png'),
                          card_w, card_h)
    cx0 = (W - card_w) // 2
    cy0 = H - card_h - 66
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh.paste(Image.new('RGBA', card.size, (0, 0, 0, 255)), (cx0, cy0),
             card.split()[3])
    sh = sh.filter(ImageFilter.GaussianBlur(30))
    sh.putalpha(sh.split()[3].point(lambda a: int(a * 0.5)))
    off = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    off.paste(sh, (0, 18))
    canvas.alpha_composite(off)
    canvas.alpha_composite(card, (cx0, cy0))

    # optional narration line ("First I go to" / "Then I go to") + heading below
    if step_label:
        draw_step_label(canvas, step_label, 52)
        head_y = 116
        chips_y = 268
    else:
        head_y = 96
        chips_y = 250

    # heading (app name) with its app-icon tile
    draw_heading_with_icon(canvas, slide['name'], slide.get('shot'), head_y)

    # caption chips scattered between heading and card
    chips = slide.get('chips', [])[:3]
    sides = ['left', 'right', 'left']
    y = chips_y
    limit = cy0 - 34
    for i, txt in enumerate(chips):
        if not txt:
            continue
        top, hgt = draw_chip(canvas, txt, sides[i], y)
        y = top + hgt + 40
        if y > limit:
            break

    canvas.convert('RGB').save(out_path, quality=92)
    return 0


def render_slideshow(config, photos_dir, shots_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, slide in enumerate(config):
        p = os.path.join(out_dir, f"slide_{i:02d}.jpg")
        if slide.get('type') == 'title_overlay':
            photo_path = slide['image']
        else:
            photo_path = os.path.join(photos_dir, slide['photo'])
        render_slide(slide, photo_path, shots_dir, p)
        paths.append(p)
    return paths
