#!/usr/bin/env python3
"""Weighted draw from the 9 starting images + random hook line."""
from __future__ import annotations
import random, shutil, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"
TITLE_SLIDE = ASSETS / "title_slide.png"
FONT_DIR = ASSETS / "fonts"

POOL = [("start_18yo.png",12),("start_always_2.png",3),("start_always_3.png",12),
        ("start_always_4.png",17),("start_always_5.png",17),("start_porsche.png",9.75),
        ("start_jet.png",9.75),("start_stairs.png",9.75),("start_wolf.png",9.75)]
TEXT_BAKED = {"start_porsche.png","start_jet.png","start_stairs.png","start_wolf.png"}
HOOKS = ["5 apps I use to build my startup",
         "5 apps every startup founder should use",
         "5 apps I use daily in my business",
         "5 apps I use to run my entire business"]

def warn_skip(msg):
    print(f"[refresh_title_slide] SKIP: {msg}"); sys.exit(0)

def stamp(path, text):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(path).convert("RGB")
    if im.width > im.height:
        im = im.rotate(90, expand=True)
    W, H = im.size
    size = max(16, int(W * 0.082))
    font = None
    for name in ("Poppins-Bold.ttf", "Inter-Bold.ttf"):
        if (FONT_DIR / name).exists():
            font = ImageFont.truetype(str(FONT_DIR / name), size); break
    if font is None:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(im)
    max_w, lines, cur = W * 0.80, [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur: lines.append(cur)
            cur = word
    if cur: lines.append(cur)
    line_h, top = int(size * 1.18), int(H * 0.09)
    max_lw = max(d.textlength(l, font=font) for l in lines)
    overlay = Image.new("RGBA", im.size, (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    pad_x, pad_y = int(W * 0.045), int(size * 0.45)
    od.rounded_rectangle(
        [int((W-max_lw)/2-pad_x), top-pad_y, int((W+max_lw)/2+pad_x), top+line_h*len(lines)+pad_y],
        radius=int(size*0.35), fill=(0,0,0,110))
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(im)
    y = top
    for line in lines:
        x = (W - d.textlength(line, font=font)) / 2
        for dx, dy in ((-3,3),(3,3),(0,4),(3,-3),(-3,-3)):
            d.text((x+dx, y+dy), line, font=font, fill=(0,0,0))
        d.text((x, y), line, font=font, fill=(255,255,255))
        y += line_h
    im.save(path)
    print(f"[refresh_title_slide] stamped: {lines}")

def main():
    rng = random.SystemRandom()
    available = [(n,w) for n,w in POOL if (ASSETS/n).exists()]
    if not available:
        warn_skip("no starting images found in assets/")
    drawn = rng.choices([n for n,_ in available], weights=[w for _,w in available], k=1)[0]
    print(f"[refresh_title_slide] drew: {drawn}")
    try:
        shutil.copyfile(ASSETS/drawn, TITLE_SLIDE)
    except Exception as e:
        warn_skip(f"copy failed ({e})")
    if drawn in TEXT_BAKED:
        print("[refresh_title_slide] text-baked image, no stamping."); return
    hook = rng.choice(HOOKS)
    print(f"[refresh_title_slide] hook: {hook}")
    try:
        stamp(TITLE_SLIDE, hook)
    except Exception as e:
        print(f"[refresh_title_slide] WARN: stamping failed ({e})")

if __name__ == "__main__":
    main()
