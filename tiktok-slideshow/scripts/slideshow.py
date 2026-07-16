#!/usr/bin/env python3
"""TikTok slideshow compositor.

Renders 3:4 (1080x1440) slides: a darkened background photo with a logo
tile and bold white text. A continuous dark gradient + adaptive boost keep
white text legible over any photo. Used by make_slideshow.py.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

W, H = 1080, 1440
MARGIN = 86

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
_FONTS_DIR = os.path.join(_SKILL_DIR, 'assets', 'fonts')
_FONT_CANDIDATES = [
    # bundled with the skill so all slides match the Higgsfield title slide
    os.path.join(_FONTS_DIR, 'Inter-Bold.ttf'),
    os.path.join(_FONTS_DIR, 'Inter-SemiBold.ttf'),
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), _FONT_CANDIDATES[-1])


def cover_crop(im, w, h):
    tr, ir = w / h, im.width / im.height
    if ir > tr:
        nw = int(im.height * tr)
        im = im.crop(((im.width - nw)//2, 0, (im.width - nw)//2 + nw, im.height))
    else:
        nh = int(im.width / tr)
        im = im.crop((0, (im.height - nh)//2, im.width, (im.height - nh)//2 + nh))
    return im.resize((w, h), Image.LANCZOS)


def title_layout(draw, text, maxw):
    """Largest font (<=104) giving a balanced 2-line split within maxw."""
    words = text.split()
    for size in range(104, 60, -4):
        f = ImageFont.truetype(FONT, size)
        best = None
        for k in range(1, len(words)):
            l1, l2 = ' '.join(words[:k]), ' '.join(words[k:])
            w1, w2 = draw.textlength(l1, font=f), draw.textlength(l2, font=f)
            if w1 <= maxw and w2 <= maxw:
                diff = abs(w1 - w2)
                if best is None or diff < best[0]:
                    best = (diff, [l1, l2])
        if best:
            return f, best[1], size
    return ImageFont.truetype(FONT, 64), [text], 64


def wrap(draw, text, font, maxw):
    """Word-wrap; preserve \\n in source as a blank line between paragraphs."""
    out = []
    paragraphs = text.split('\n')
    for i, para in enumerate(paragraphs):
        if i > 0:
            out.append('')  # blank line between paragraphs
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


def draw_text_soft(base, pos, lines, font, leading, fill=(255, 255, 255),
                   shadow_alpha=0.82, shadow_blur=10, shadow_offset=(0, 6)):
    x, y = pos
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cy = y
    for ln in lines:
        if ln:
            d.text((x, cy), ln, font=font, fill=fill + (255,))
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


def _mean_luma(im, box):
    crop = im.convert('RGB').crop(box).resize((40, 40))
    px = list(crop.getdata())
    return sum(0.299*r + 0.587*g + 0.114*b for r, g, b in px) / len(px)


def render_slide(slide, photo_path, logos_dir, out_path):
    """slide: dict with type 'title', 'app', or 'static'."""
    # 'static' slides are pre-rendered images (e.g. the Higgsfield title
    # slide that already has text baked in) — just cover-crop to 3:4 and save
    if slide.get('type') == 'static':
        src = Image.open(slide['image']).convert('RGB')
        src = cover_crop(src, W, H)
        # composite image at 95% opacity over black — subtle dim so the
        # baked-in title text reads a touch better
        src = ImageEnhance.Brightness(src).enhance(0.95)
        # optional teaser: small row of the 5 app icons near the bottom
        if slide.get('preview_logos'):
            canvas = src.convert('RGBA')
            names = slide['preview_logos']
            SZ, GAP = 108, 26
            total = len(names)*SZ + (len(names)-1)*GAP
            x0 = (W - total)//2
            y0 = H - SZ - 150
            row = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            x = x0
            for lg in names:
                icon = Image.open(os.path.join(logos_dir, lg + '.png'))
                icon = icon.convert('RGBA').resize((SZ, SZ), Image.LANCZOS)
                row.alpha_composite(icon, (x, y0))
                x += SZ + GAP
            sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            sh.putalpha(row.split()[3].point(lambda a: int(a*0.5)))
            sh = sh.filter(ImageFilter.GaussianBlur(12))
            off = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            off.paste(sh, (0, 6))
            canvas.alpha_composite(off)
            canvas.alpha_composite(row)
            src = canvas.convert('RGB')
        src.save(out_path, quality=92)
        return 0
    im = cover_crop(Image.open(photo_path).convert('RGB'), W, H)
    im = ImageEnhance.Brightness(im).enhance(0.82)   # subtle global darken
    im = ImageEnhance.Color(im).enhance(0.97)
    canvas = im.convert('RGBA')
    tmp = ImageDraw.Draw(canvas)

    # ---- 'title' slide (legacy compositing path; static title is the
    # current default but keep this for fallback) ----
    if slide['type'] == 'title':
        f_title, lines, tsize = title_layout(tmp, slide['text'], W - 2*MARGIN)
        lead = int(tsize * 1.14)
        draw_text_soft(canvas, (MARGIN, 168), lines, f_title, lead)
        canvas.convert('RGB').save(out_path, quality=92)
        return 0

    # ---- 'app' slide — reference-style layout ----
    LEFT = 70
    LOGO_SZ = 210
    BODY_W = 620

    f_head = ImageFont.truetype(FONT, 74)
    f_body = ImageFont.truetype(FONT, 40)
    head_text = f"{slide['num']}. {slide['name']}"
    body_lines = wrap(tmp, slide['body'], f_body, BODY_W)
    body_lead = 52
    head_h = 74
    body_h = body_lead * len(body_lines)

    pos = slide.get('pos', 'middle')   # 'top' | 'middle' | 'bottom'
    sub = slide.get('sub', 'inline')   # 'inline' (heading right of logo) | 'stacked'

    # vertical anchor for the logo top
    if pos == 'top':
        logo_top = 100
        body_gap = 36
    elif pos == 'middle':
        logo_top = 470
        body_gap = 60
    else:                              # bottom
        body_gap = 32
        if sub == 'inline':
            block_h = LOGO_SZ + body_gap + body_h
        else:
            block_h = LOGO_SZ + 26 + head_h + body_gap + body_h
        logo_top = max(80, H - block_h - 90)

    # paint logo with a soft drop shadow for separation from busy photos
    logo = Image.open(os.path.join(logos_dir, slide['logo'] + '.png')).convert('RGBA')
    logo = logo.resize((LOGO_SZ, LOGO_SZ), Image.LANCZOS)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh.paste(Image.new('RGBA', (LOGO_SZ, LOGO_SZ), (0, 0, 0, 255)),
             (LEFT, logo_top), logo.split()[3])
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    sh.putalpha(sh.split()[3].point(lambda a: int(a * 0.45)))
    canvas.alpha_composite(sh, (0, 8))
    canvas.alpha_composite(logo, (LEFT, logo_top))

    if sub == 'inline':
        # heading vertically centred with the logo's middle, to its right
        head_y = logo_top + (LOGO_SZ - head_h)//2 - 4
        head_x = LEFT + LOGO_SZ + 26
        draw_text_soft(canvas, (head_x, head_y), [head_text], f_head, head_h)
        body_y = logo_top + LOGO_SZ + body_gap
    else:                              # stacked: heading below logo
        head_y = logo_top + LOGO_SZ + 26
        draw_text_soft(canvas, (LEFT, head_y), [head_text], f_head, head_h)
        body_y = head_y + head_h + body_gap

    draw_text_soft(canvas, (LEFT, body_y), body_lines, f_body, body_lead,
                   fill=(255, 255, 255))

    canvas.convert('RGB').save(out_path, quality=92)
    return 0


def render_slideshow(config, photos_dir, logos_dir, out_dir):
    """config: list of slide dicts, each with a 'photo' filename."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, slide in enumerate(config):
        p = os.path.join(out_dir, f"slide_{i:02d}.jpg")
        if slide.get('type') == 'static':
            photo_path = slide['image']
        else:
            photo_path = os.path.join(photos_dir, slide['photo'])
        render_slide(slide, photo_path, logos_dir, p)
        paths.append(p)
    return paths
