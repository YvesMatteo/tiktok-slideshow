#!/usr/bin/env python3
"""TikTok slideshow compositor — SCREENSHOT / browser-mockup variant.

Renders 3:4 (1080x1440) slides. Each app slide shows the app's wide
screenshot framed as a clean browser window (macOS traffic-light dots +
a URL pill) floating as the hero visual over a darkened background photo,
with a bold heading above and caption below. The title slide is the static
Higgsfield-rendered image. Kept fully separate from slideshow.py so the
logo-based generator is untouched.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

W, H = 1080, 1440

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


def font_bold(size):
    return _font(['Inter-Bold.ttf', 'Inter-SemiBold.ttf'], size)


def font_med(size):
    return _font(['Inter-Medium.ttf', 'Inter-SemiBold.ttf', 'Inter-Bold.ttf'], size)


# real domains so the browser URL pill reads true
DOMAINS = {
    'claude': 'claude.ai', 'notion': 'notion.com', 'framer': 'framer.com',
    'higgsfield': 'higgsfield.ai', 'checkvibe': 'checkvibe.dev',
    'antigravity': 'antigravity.google', 'github': 'github.com',
    'lovable': 'lovable.dev', 'obsidian': 'obsidian.md',
    'pinterest': 'pinterest.com', 'posthog': 'posthog.com',
    'railway': 'railway.com', 'supabase': 'supabase.com', 'vercel': 'vercel.com',
}


def cover_crop(im, w, h):
    tr, ir = w / h, im.width / im.height
    if ir > tr:
        nw = int(im.height * tr)
        im = im.crop(((im.width - nw)//2, 0, (im.width - nw)//2 + nw, im.height))
    else:
        nh = int(im.width / tr)
        im = im.crop((0, (im.height - nh)//2, im.width, (im.height - nh)//2 + nh))
    return im.resize((w, h), Image.LANCZOS)


def wrap(draw, text, font, maxw):
    """Word-wrap; preserve \\n in source as a blank line between paragraphs."""
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


def draw_lines_centered(base, lines, font, y, leading, fill=(255, 255, 255),
                        shadow_alpha=0.85, shadow_blur=11, shadow_offset=(0, 6)):
    """Draw horizontally-centered lines with a soft drop shadow for legibility."""
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


def _load_logo(key, target_h):
    """Return the app's logo as an RGBA image scaled to target_h, or None."""
    for ext in ('.png', '.jpg', '.jpeg'):
        p = os.path.join(_LOGOS_DIR, key + ext)
        if os.path.exists(p):
            lg = Image.open(p).convert('RGBA')
            w = max(1, int(round(lg.width * target_h / lg.height)))
            return lg.resize((w, target_h), Image.LANCZOS)
    return None


def draw_heading_with_logo(base, num, name, logo, font, y,
                           fill=(255, 255, 255), gap=18,
                           shadow_alpha=0.85, shadow_blur=11, shadow_offset=(0, 6)):
    """Draw '<num>. <name>' centered, with the app logo inline before the name.

    Text and logo share one soft drop shadow so the group stays legible over
    any background (dark app icons separate cleanly from dark photos).
    """
    measure = ImageDraw.Draw(base)
    prefix = f"{num}. "
    prefix_w = measure.textlength(prefix, font=font)
    name_w = measure.textlength(name, font=font)
    logo_w = logo.width if logo else 0
    total = prefix_w + (logo_w + gap if logo else 0) + name_w
    x = (base.width - total) / 2

    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    dl.text((x, y), prefix, font=font, fill=fill + (255,))
    cursor = x + prefix_w
    if logo:
        nb = font.getbbox(name)                       # visual glyph extent
        name_cy = y + (nb[1] + nb[3]) / 2
        ly = int(round(name_cy - logo.height / 2))
        layer.alpha_composite(logo, (int(round(cursor)), ly))
        cursor += logo_w + gap
    dl.text((cursor, y), name, font=font, fill=fill + (255,))

    alpha = layer.split()[3]
    shadow = Image.new('RGBA', base.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda a: int(a * shadow_alpha)))
    shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_blur))
    off = Image.new('RGBA', base.size, (0, 0, 0, 0))
    off.paste(shadow, shadow_offset)
    base.alpha_composite(off)
    base.alpha_composite(layer)


def make_browser(shot_path, bw, domain=''):
    """Return an RGBA browser-window card of width bw wrapping the screenshot."""
    shot = Image.open(shot_path).convert('RGB')
    ar = shot.width / shot.height
    disp_h = int(round(bw / ar))
    bar_h = 46
    radius = 26
    bh = bar_h + disp_h
    card = Image.new('RGBA', (bw, bh), (255, 255, 255, 255))
    d = ImageDraw.Draw(card)
    # title bar
    d.rectangle([0, 0, bw, bar_h], fill=(238, 238, 241, 255))
    # screenshot body
    card.paste(shot.resize((bw, disp_h), Image.LANCZOS), (0, bar_h))
    d.line([(0, bar_h), (bw, bar_h)], fill=(206, 206, 212, 255))
    # traffic-light dots
    cyb = bar_h // 2
    for i, col in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx = 26 + i * 26
        d.ellipse([cx - 8, cyb - 8, cx + 8, cyb + 8], fill=col + (255,))
    # URL pill
    if domain:
        pill_w = min(400, bw - 280)
        pill_h = 30
        px = (bw - pill_w) // 2
        py = cyb - pill_h // 2
        d.rounded_rectangle([px, py, px + pill_w, py + pill_h], radius=15,
                            fill=(255, 255, 255, 255), outline=(208, 208, 214, 255),
                            width=1)
        f = font_med(20)
        tw = d.textlength(domain, font=f)
        d.text((px + (pill_w - tw) / 2, py + (pill_h - 20) / 2 - 2), domain,
               font=f, fill=(120, 120, 130, 255))
    # round the outer corners
    mask = Image.new('L', (bw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, bw - 1, bh - 1],
                                           radius=radius, fill=255)
    card.putalpha(mask)
    return card


def render_slide(slide, photo_path, shots_dir, out_path):
    """slide: dict with type 'static' or 'app'."""
    if slide.get('type') == 'static':
        src = cover_crop(Image.open(slide['image']).convert('RGB'), W, H)
        src = ImageEnhance.Brightness(src).enhance(0.95)
        src.save(out_path, quality=92)
        return 0

    # darkened background photo so the bright screenshot pops
    im = cover_crop(Image.open(photo_path).convert('RGB'), W, H)
    im = ImageEnhance.Brightness(im).enhance(0.70)
    im = ImageEnhance.Color(im).enhance(0.95)
    canvas = im.convert('RGBA')
    tmp = ImageDraw.Draw(canvas)

    key = slide['shot']
    shot_path = os.path.join(shots_dir, key + '.png')
    domain = DOMAINS.get(key, '')

    # browser width so every screenshot lands at ~ the same body height
    shot = Image.open(shot_path)
    ar = shot.width / shot.height
    target_disp_h = 588
    bw = int(round(target_disp_h * ar))
    bw = max(770, min(946, bw))
    card = make_browser(shot_path, bw, domain)

    # ---- text metrics ----
    f_head = font_bold(72)
    f_body = font_med(40)
    logo = _load_logo(key, 78)
    body_lines = wrap(tmp, slide['body'], f_body, 900)
    head_h = 74
    body_lead = 52
    body_h = body_lead * len(body_lines)
    gap1, gap2 = 30, 44
    block_h = head_h + gap1 + card.height + gap2 + body_h
    top = max(58, (H - block_h) // 2)

    # ---- heading (number + app logo + name) ----
    draw_heading_with_logo(canvas, slide['num'], slide['name'], logo, f_head, top)

    # ---- browser card with soft shadow ----
    cx0 = (W - card.width) // 2
    cy0 = top + head_h + gap1
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    shadow.paste(Image.new('RGBA', card.size, (0, 0, 0, 255)), (cx0, cy0),
                 card.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(34))
    shadow.putalpha(shadow.split()[3].point(lambda a: int(a * 0.50)))
    off = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    off.paste(shadow, (0, 20))
    canvas.alpha_composite(off)
    canvas.alpha_composite(card, (cx0, cy0))

    # ---- caption below ----
    body_y = cy0 + card.height + gap2
    draw_lines_centered(canvas, body_lines, f_body, body_y, body_lead,
                        fill=(245, 245, 245))

    canvas.convert('RGB').save(out_path, quality=92)
    return 0


def render_slideshow(config, photos_dir, shots_dir, out_dir):
    """config: list of slide dicts. App slides carry 'photo' + 'shot'."""
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for i, slide in enumerate(config):
        p = os.path.join(out_dir, f"slide_{i:02d}.jpg")
        if slide.get('type') == 'static':
            photo_path = slide['image']
        else:
            photo_path = os.path.join(photos_dir, slide['photo'])
        render_slide(slide, photo_path, shots_dir, p)
        paths.append(p)
    return paths
