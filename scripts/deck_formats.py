#!/usr/bin/env python3
"""Slideshow formats beyond the classic "5 apps" deck.

Each format is a function (rng, bank, ctx) -> Deck. Layouts copy the posts that
won in the 2026-11 teardown (slideshow-research/REPORT.md): white contrast memes
with CheckVibe as the punchline (nicodunlap style), an editorial "mistakes"
carousel with the brand held to the last slide, a radial "maxxing" cheat-sheet,
price parity, and the "but I don't know how to X" -> "bro..." objection loop.

Every string drawn goes through `text()` so make_deck.py can QA glyph coverage
and banned words on exactly what ships.
"""
from __future__ import annotations
import math
import os
from dataclasses import dataclass, field

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')
FONTS = os.path.join(ASSETS, 'fonts')
LOGOS = os.path.join(ASSETS, 'logos')
ITEMS = os.path.join(ASSETS, 'items')
PHOTOS = os.path.join(ROOT, 'photos')
W, H = 1080, 1440

BOLD = os.path.join(FONTS, 'Inter-Bold.ttf')
SEMI = os.path.join(FONTS, 'Inter-SemiBold.ttf')
MED = os.path.join(FONTS, 'Inter-Medium.ttf')
DISPLAY = os.path.join(FONTS, 'Poppins-Bold.ttf')

INK = (17, 17, 17)
GREY = (120, 120, 120)
CLAUDE_ORANGE = (217, 119, 87)
RUST = (194, 83, 47)
CREAM = (245, 240, 232)


@dataclass
class Deck:
    slides: list
    hook: str
    caption: str
    variant: str
    photos: list = field(default_factory=list)
    drawn: list = field(default_factory=list)   # (text, font_path) for QA
    photo_slides: list = field(default_factory=list)  # indices of slides on photos


class Canvas:
    def __init__(self, deck: Deck, bg=(255, 255, 255)):
        self.deck = deck
        self.im = Image.new('RGBA', (W, H), bg + (255,))
        self.d = ImageDraw.Draw(self.im)

    def font(self, path, size):
        return ImageFont.truetype(path, size)

    def text(self, xy, s, path, size, fill=INK, anchor='la', maxw=None, leading=1.18, align='left'):
        """Draw (optionally wrapped) text; returns bottom y."""
        self.deck.drawn.append((s, path))
        f = self.font(path, size)
        lines = wrap(self.d, s, f, maxw) if maxw else s.split('\n')
        x, y = xy
        step = int(size * leading)
        for ln in lines:
            self.d.text((x, y), ln, font=f, fill=fill, anchor=anchor, align=align)
            y += step
        return y

    def fit_text(self, xy, s, path, maxsize, minsize, maxw, maxlines, **kw):
        """Largest size <= maxsize whose wrap fits in maxlines."""
        for size in range(maxsize, minsize - 1, -2):
            if len(wrap(self.d, s, self.font(path, size), maxw)) <= maxlines:
                break
        return self.text(xy, s, path, size, maxw=maxw, **kw)

    def logo(self, key, center, size, shadow=True):
        im = Image.open(os.path.join(LOGOS, f'{key}.png')).convert('RGBA').resize((size, size), Image.LANCZOS)
        x, y = int(center[0] - size / 2), int(center[1] - size / 2)
        if shadow:
            sh = Image.new('RGBA', self.im.size, (0, 0, 0, 0))
            sh.paste((0, 0, 0, 70), (x, y + 8), im.split()[3])
            self.im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
        self.im.alpha_composite(im, (x, y))

    def item(self, key, center, size):
        """White-background product photo, multiplied onto a light canvas."""
        im = Image.open(os.path.join(ITEMS, f'{key}.jpg')).convert('RGB')
        im.thumbnail((size, size), Image.LANCZOS)
        corners = [im.getpixel(p) for p in ((2, 2), (im.width - 3, 2), (2, im.height - 3), (im.width - 3, im.height - 3))]
        bgv = max(200, min(min(c) for c in corners) - 4)  # studio white is ~235-250, lift it to 255
        im = im.point(lambda v: min(255, int(v * 255 / bgv)))
        x, y = int(center[0] - im.width / 2), int(center[1] - im.height / 2)
        region = self.im.crop((x, y, x + im.width, y + im.height)).convert('RGB')
        self.im.paste(ImageChops.multiply(region, im), (x, y))

    def pill(self, xy, s, size, fg, bg, pad=(22, 12)):
        f = self.font(SEMI, size)
        self.deck.drawn.append((s, SEMI))
        tw = self.d.textlength(s, font=f)
        x, y = xy
        box = (x, y, x + tw + 2 * pad[0], y + size + 2 * pad[1])
        self.d.rounded_rectangle(box, radius=(size + 2 * pad[1]) // 2, fill=bg)
        self.d.text((x + pad[0], y + pad[1] + size * 0.02), s, font=f, fill=fg)
        return box

    def vcenter(self, top=0, bottom=H - 60):
        """Move everything drawn below `top` so it sits centered in [top, bottom]."""
        bg = Image.new('RGBA', self.im.size, self.im.getpixel((5, H - 5)))
        box = ImageChops.difference(self.im, bg).convert('L').point(lambda v: 255 if v > 1 else 0) \
            .crop((0, top, W, H)).getbbox()
        if not box:
            return
        y0, y1 = box[1] + top, box[3] + top
        dy = int((top + bottom) / 2 - (y0 + y1) / 2)
        if dy:
            band = self.im.crop((0, y0, W, y1))
            self.im.paste(bg.crop((0, y0, W, y1)), (0, y0))
            self.im.paste(band, (0, y0 + dy))

    def done(self):
        return self.im.convert('RGB')


def wrap(d, text, font, maxw):
    out = []
    for para in text.split('\n'):
        words, line = para.split(), ''
        for w in words:
            t = (line + ' ' + w).strip()
            if d.textlength(t, font=font) <= maxw or not line:
                line = t
            else:
                out.append(line); line = w
        out.append(line)
    return out


def photo_canvas(deck, photo, darken=0.55):
    """Cover-crop a photo to 3:4 and darken it so white text reads."""
    im = Image.open(os.path.join(PHOTOS, photo)).convert('RGB')
    s = max(W / im.width, H / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((l, t, l + W, t + H))
    im = Image.blend(im, Image.new('RGB', im.size, (0, 0, 0)), darken)
    c = Canvas(deck)
    c.im = im.convert('RGBA'); c.d = ImageDraw.Draw(c.im)
    deck.photos.append(photo)
    return c


def soft_text(c, xy, s, size, fill=(255, 255, 255), path=SEMI, maxw=760, anchor='ma'):
    """TikTok-native look: centered white text with a soft shadow, no box."""
    layer = Canvas(c.deck, bg=(0, 0, 0))
    layer.im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); layer.d = ImageDraw.Draw(layer.im)
    bottom = layer.text(xy, s, path, size, fill=fill + (255,), anchor=anchor, maxw=maxw)
    a = layer.im.split()[3]
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sh.putalpha(a.point(lambda v: int(v * .8)))
    off = Image.new('RGBA', (W, H), (0, 0, 0, 0)); off.paste(sh.filter(ImageFilter.GaussianBlur(9)), (0, 5))
    c.im.alpha_composite(off); c.im.alpha_composite(layer.im)
    return bottom


def hashtags(bank, rng, n=5):
    core = bank['hashtags']['core']
    return ' '.join(core + rng.sample(bank['hashtags']['pool'], n - len(core)))


def caption_for(fmt, bank, rng):
    line = rng.choice(bank['captions'][fmt])
    return (line + ' ' if line else '') + hashtags(bank, rng)


# ---------------------------------------------------------------- formats ---

def two_types(rng, bank, ctx):
    i, v = ctx.pick_variant('two_types', bank['two_types'])
    deck = Deck([], v['title'], caption_for('two_types', bank, rng), f'two_types:{i}')
    c = Canvas(deck)
    c.fit_text((60, 70), v['title'], BOLD, 78, 56, W - 120, 1)
    for col, side in enumerate(('left', 'right')):
        s, x0 = v[side], 40 + col * 540
        y = c.text((x0 + 10, 230), s['quote'], SEMI, 42, maxw=460)
        y += 30
        for k, key in enumerate(s['items']):            # products, 2 per row
            c.item(key, (x0 + 125 + (k % 2) * 235, y + 125 + (k // 2) * 255), 245)
        y += 255 * math.ceil(len(s['items']) / 2) + 30
        for k, key in enumerate(s['logos']):
            c.logo(key, (x0 + 90 + k * 165, y + 75), 140)
        y += 190 if s['logos'] else 0
        fg, bg = ((198, 40, 40), (253, 236, 236)) if side == 'left' else ((46, 125, 50), (232, 245, 233))
        for chip in s['chips']:
            y = c.pill((x0 + 10, y), chip, 34, fg, bg)[3] + 20
    c.vcenter(215)
    c.d.line((540, 210, 540, H - 70), fill=(225, 225, 225), width=3)  # after centering: it spans the slide
    deck.slides.append(c.done())
    return deck


def versus(rng, bank, ctx):
    i, v = ctx.pick_variant('versus', bank['versus'])
    deck = Deck([], v['hook'], caption_for('versus', bank, rng), f'versus:{i}')
    for pi, (left, right) in enumerate(v['pairs']):
        c = Canvas(deck)
        # headers: plain word vs logo + brand (the punchline)
        c.text((270, 150), v['left'], BOLD, 84, anchor='ma')
        c.logo(bank['brand']['logo'], (810, 120), 110)
        c.text((810, 195), v['right'], BOLD, 70, anchor='ma')
        y = 360
        for msg in left:                                  # iMessage-ish bubbles
            f = c.font(MED, 42); tw = min(max(c.d.textlength(l, font=f) for l in wrap(c.d, msg, f, 400)), 400)
            lines = wrap(c.d, msg, f, 400); h = 54 * len(lines) + 36
            c.d.rounded_rectangle((60, y, 60 + tw + 44, y + h), 30, fill=(233, 233, 235))
            c.text((84, y + 18), msg, MED, 42, maxw=400, leading=1.28)
            y += h + 22
        card_top, yy = 360, 400
        lay = Canvas(deck); lay.im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); lay.d = ImageDraw.Draw(lay.im)
        for k, ln in enumerate(right):                    # measure card height first
            yy = lay.text((600, yy), ln, SEMI, 38, maxw=400) + 20
        deck.drawn[-len(right):] = []
        c.d.rounded_rectangle((560, card_top, 1040, yy + 25), 28, fill=(18, 18, 18))
        yy = 400
        for k, ln in enumerate(right):                    # scan-report card
            if k == 0:
                c.d.ellipse((600, yy + 10, 620, yy + 30), fill=CLAUDE_ORANGE)
            yy = c.text((635 if k == 0 else 600, yy), ln, SEMI if k == 0 else MED, 38,
                        fill=(255, 255, 255) if k == 0 else (200, 200, 200), maxw=400 if k else 370) + 20
        if pi == 0:
            by = max(y, yy + 25) + 70
            c.text((270, by), v['left_sub'], MED, 40, fill=GREY, anchor='ma')
            c.text((800, by), v['right_sub'], MED, 40, fill=GREY, anchor='ma', maxw=440)
        c.vcenter(0, H)
        deck.slides.append(c.done())
    return deck


def price_parity(rng, bank, ctx):
    i, v = ctx.pick_variant('price_parity', bank['price_parity'])
    pairs = rng.sample(v['pairs'], min(3, len(v['pairs'])))
    b = bank['brand']
    first = pairs[0]
    deck = Deck([], f"{first[1]} {first[2]} vs {b['name']} {b['price']}",
                caption_for('price_parity', bank, rng), f"price_parity:{i}:{'|'.join(p[0] for p in pairs)}")
    for key, label, price in pairs:
        c = Canvas(deck)
        c.item(key, (300, 360), 400)
        c.text((560, 280), label, BOLD, 64, maxw=470)
        c.text((560, 450), price, MED, 64, fill=GREY)
        c.d.line((60, 720, W - 60, 720), fill=(230, 230, 230), width=3)
        c.logo(b['logo'], (300, 1080), 300)
        c.text((560, 1000), b['name'], BOLD, 72)
        c.text((560, 1100), b['price'], MED, 64, fill=GREY)
        deck.slides.append(c.done())
    c = Canvas(deck)
    c.text((W // 2, 600), v['closer'], BOLD, 84, anchor='ma', align='center', leading=1.2)
    c.vcenter(0, H)
    deck.slides.append(c.done())
    return deck


def maxxing(rng, bank, ctx):
    i, v = ctx.pick_variant('maxxing', bank['maxxing'])
    topics = v['topics']
    deck = Deck([], v['title'].replace('\n', ' '), caption_for('maxxing', bank, rng), f'maxxing:{i}')
    c = Canvas(deck)
    c.text((W // 2, 110), v['title'], BOLD, 88, anchor='ma', align='center')
    cx, cy, r = W // 2, 860, 380
    c.logo(v['center'], (cx, cy), 250)
    for k, t in enumerate(topics):                        # radial bubbles
        a = -math.pi / 2 + 2 * math.pi * k / len(topics)
        f = c.font(SEMI, 40); tw = c.d.textlength(t['name'], font=f)
        bx, by = cx + r * math.cos(a), cy + r * math.sin(a)
        bx = min(max(bx, tw / 2 + 50), W - tw / 2 - 50)
        c.d.line((cx, cy, bx, by), fill=(230, 230, 230), width=3)
        c.pill((int(bx - tw / 2 - 24), int(by - 34)), t['name'], 40, INK, (243, 238, 234))
    deck.slides.append(c.done())
    for t in topics:
        c = Canvas(deck)
        c.text((80, 150), t['name'], BOLD, 92)
        y = 360
        for n, tip in enumerate(t['tips'], 1):
            c.d.ellipse((80, y, 160, y + 80), fill=CLAUDE_ORANGE)
            c.text((120, y + 14), str(n), BOLD, 46, fill=(255, 255, 255), anchor='ma')
            y = max(c.text((200, y + 8), tip, MED, 54, maxw=800), y + 100) + 70
        c.vcenter(0, H)
        deck.slides.append(c.done())
    return deck


def killing_app(rng, bank, ctx):
    i, v = ctx.pick_variant('killing_app', bank['killing_app'])
    deck = Deck([], v['hook'].replace('\n', ' '), caption_for('killing_app', bank, rng), f'killing_app:{i}')
    c = Canvas(deck, CREAM)
    c.text((80, 120), "THE VIBE CODER'S DILEMMA", SEMI, 26, fill=GREY)
    c.d.line((80, 170, W - 80, 170), fill=(210, 200, 190), width=2)
    y = 420                                               # hook, accent word in rust
    f = c.font(DISPLAY, 104)
    for ln in wrap(c.d, v['hook'], f, W - 160):
        x = 80
        for w in ln.split(' '):
            col = RUST if w.strip(',.').lower() == v['accent'] else INK
            deck.drawn.append((w, DISPLAY))
            c.d.text((x, y), w, font=f, fill=col)
            x += c.d.textlength(w + ' ', font=f)
        y += 125
    c.text((80, H - 150), '-> keep reading', MED, 30, fill=GREY)
    deck.slides.append(c.done())
    for n, (head, body) in enumerate(v['items'], 1):
        c = Canvas(deck, CREAM)
        c.text((80, 200), f'{n:02d}', DISPLAY, 170, fill=RUST)
        y = c.text((80, 440), head, DISPLAY, 84, maxw=W - 160, leading=1.12)
        c.text((80, y + 50), body, MED, 52, fill=(70, 70, 70), maxw=W - 160, leading=1.35)
        c.vcenter(0, H)
        deck.slides.append(c.done())
    c = Canvas(deck, CREAM)
    c.logo(bank['brand']['logo'], (W // 2, 560), 220)
    c.text((W // 2, 760), v['outro'], SEMI, 58, anchor='ma', align='center', maxw=880)
    c.vcenter(0, H)
    deck.slides.append(c.done())
    return deck


def objection_loop(rng, bank, ctx):
    i, v = ctx.pick_variant('objection_loop', bank['objection_loop'])
    photos = ctx.pick_photos(len(v['steps']) * 2 + 1)
    deck = Deck([], v['steps'][0][0], caption_for('objection_loop', bank, rng), f'objection_loop:{i}')
    p = iter(photos)
    for objection, logo, name, line in v['steps']:
        c = photo_canvas(deck, next(p), 0.45)
        soft_text(c, (W // 2, 640), objection, 62)
        deck.photo_slides.append(len(deck.slides)); deck.slides.append(c.done())
        c = photo_canvas(deck, next(p), 0.55)
        soft_text(c, (W // 2, 330), 'bro...', 64, fill=(255, 70, 70), path=BOLD)
        c.logo(logo, (W // 2, 640), 230)
        y = soft_text(c, (W // 2, 820), name, 60, path=BOLD)
        soft_text(c, (W // 2, y + 10), line, 46, path=MED)
        deck.photo_slides.append(len(deck.slides)); deck.slides.append(c.done())
    c = photo_canvas(deck, next(p), 0.5)
    soft_text(c, (W // 2, 640), v['closer'], 60, path=BOLD)
    deck.photo_slides.append(len(deck.slides)); deck.slides.append(c.done())
    return deck


FORMATS = {
    'two_types': two_types,
    'versus': versus,
    'price_parity': price_parity,
    'maxxing': maxxing,
    'killing_app': killing_app,
    'objection_loop': objection_loop,
}
