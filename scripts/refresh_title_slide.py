#!/usr/bin/env python3
"""Claim one never-before-used title slide from the bank and stamp it.

Every posted slideshow must open on an image no post has ever used. That is a
property of the *ledger*, not of a random draw: the bank holds a finite set of
pre-generated images and `assets/title_bank/USED.tsv` records every one that has
ever been claimed. A claimed image is never offered again, and the ledger is
committed to the repo, so the guarantee survives across runs, accounts,
machines and re-clones.

Consequences that are deliberate, not oversights:

  * The bank is exhaustible. When it runs dry this script FAILS (exit 1) rather
    than reusing an image. A red build is the correct outcome -- the alternative
    is silently posting a duplicate opener, which is the thing we are
    preventing. Refill with scripts/build_title_bank.py.
  * Claiming is not idempotent. Each invocation consumes exactly one image.

The weighted draw over the nine source looks is preserved from the Cowork task,
but it now only chooses *which look* to spend; within that look the specific
variant is whatever is still unclaimed. A look whose variants are exhausted is
dropped from the draw and its weight redistributes over the rest.

Usage:
    refresh_title_slide.py [--out assets/title_slide.png] [--dry-run]
"""
from __future__ import annotations
import argparse
import os
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"
BANK = ASSETS / "title_bank"
LEDGER = BANK / "USED.tsv"
FONT_DIR = ASSETS / "fonts"

# --------------------------------------------------------------------------
# From the Claude Cowork scheduled task. The weights choose which of the nine
# source looks a post opens on; the variant within that look is then whichever
# generated image is still unclaimed.
# --------------------------------------------------------------------------
WEIGHTS = {
    "start_18yo": 12, "start_always_2": 3, "start_always_3": 12,
    "start_always_4": 17, "start_always_5": 17, "start_porsche": 9.75,
    "start_jet": 9.75, "start_stairs": 9.75, "start_wolf": 9.75,
}

# These looks carry their own hook text baked into the photograph. They are
# posted exactly as generated: never stamp a second line of text over them.
TEXT_BAKED = {"start_porsche", "start_jet", "start_stairs", "start_wolf"}

# Plain, non-technical hooks: every line says "business" or "startup" so a
# scroller gets it instantly. The count must stay 5 -- every deck has 5 apps.
HOOKS = ["5 apps I use to run my entire business.",
         "5 apps I use to build my startup.",
         "the 5 apps behind my entire business.",
         "5 apps every startup founder should use.",
         "5 apps I use every day in my business.",
         "how I run my whole business with just 5 apps.",
         "5 apps that run my business for me.",
         "5 apps I wish I knew before starting my business.",
         "the only 5 apps my startup needs.",
         "5 apps that save me hours in my business.",
         "5 apps I'd use if I started a business today.",
         "5 apps that help me run my startup alone."]
# A hook used on any of the last RECENT_HOOKS openers is not drawn again, so
# accounts in the same batch and back-to-back days open on different lines.
RECENT_HOOKS = 8

# --------------------------------------------------------------------------


def log(msg):
    print(f"[title-slide] {msg}", flush=True)


def read_ledger() -> set[str]:
    """Every image ever claimed, as '<look>/<id>'."""
    if not LEDGER.exists():
        return set()
    used = set()
    for line in LEDGER.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        used.add(line.split("\t")[0])
    return used


def available(used: set[str]) -> dict[str, list[str]]:
    """Unclaimed images per look, in sorted order for determinism."""
    stock: dict[str, list[str]] = {}
    if not BANK.exists():
        return stock
    for look_dir in sorted(BANK.iterdir()):
        if not look_dir.is_dir():
            continue
        free = sorted(p.name for p in look_dir.glob("*.jpg")
                      if f"{look_dir.name}/{p.name}" not in used)
        if free:
            stock[look_dir.name] = free
    return stock


def total_images() -> int:
    """Every image in the bank. Not rglob: look dirs may be symlinks."""
    if not BANK.exists():
        return 0
    return sum(len(list(d.glob("*.jpg"))) for d in BANK.iterdir() if d.is_dir())


def recent_hooks(n: int = RECENT_HOOKS) -> set[str]:
    """Hooks stamped on the last n openers (4th ledger column, when present)."""
    if not LEDGER.exists():
        return set()
    rows = [ln.split("\t") for ln in LEDGER.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")]
    return {r[3] for r in rows[-n:] if len(r) > 3 and r[3] in HOOKS}


def pick_hook(rng: random.Random) -> str:
    fresh = [h for h in HOOKS if h not in recent_hooks()]
    return rng.choice(fresh or HOOKS)


def claim(rng: random.Random) -> tuple[str, str, Path, str | None]:
    """Pick and record one unclaimed image, plus the hook to stamp on it (None
    for text-baked looks). Returns (look, ident, path, hook)."""
    used = read_ledger()
    stock = available(used)
    if not stock:
        total = total_images()
        raise SystemExit(
            f"[title-slide] ERROR: the title bank is exhausted "
            f"({len(used)} of {total} images already used).\n"
            f"  Every image may be posted exactly once, so this run cannot "
            f"proceed without repeating an opener.\n"
            f"  Refill with: python3 scripts/build_title_bank.py --count N")

    looks = list(stock)
    weights = [WEIGHTS.get(k, 1) for k in looks]
    look = rng.choices(looks, weights=weights, k=1)[0]
    ident = rng.choice(stock[look])
    key = f"{look}/{ident}"
    hook = None if look in TEXT_BAKED else pick_hook(rng)

    # Append before the image is used anywhere. If a later step fails, the
    # image stays burned -- losing one image is cheap, reusing one is not.
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    new = not LEDGER.exists()
    with open(LEDGER, "a") as f:
        if new:
            f.write("# Title-bank images already posted. Append-only; never "
                    "edit or remove a line -- an entry here is a promise that "
                    "the image will never be posted again.\n"
                    "# <look>/<id>\\t<claimed at UTC>\\t<claimed by>"
                    "\\t<hook stamped, or - for text-baked looks>\n")
        f.write(f"{key}\t{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
                f"\t{os.environ.get('TITLE_CLAIMED_BY', 'local')}\t{hook or '-'}\n")

    remaining = sum(len(v) for v in stock.values()) - 1
    log(f"claimed {key} ({remaining} unused images left in the bank)")
    return look, ident, BANK / look / ident, hook


# ---- Opener typography -----------------------------------------------------
# Matched to the reference opener (white bold sans, left-aligned, no box, soft
# dark glow). Measured off the reference at 1494x2000: the first line spans
# ~50% of the frame, starts 13.4% from the left and 29% from the top, and the
# line pitch is ~1.22x the font size. Everything is a fraction of the frame so
# any bank resolution renders the same.
TEXT_X = 0.134          # left edge of every line, fraction of width
TEXT_MAX_W = 0.60       # wrap width -> "5 apps I use to run my / entire business."
FONT_SIZE = 0.0493      # fraction of width (53 px at 1080)
LEADING = 1.22          # line pitch, multiple of font size
TRACKING = -0.02        # letter-spacing, em (Inter runs wider than SF Display)
PREFERRED_Y = 0.29      # reference cap-top position, fraction of height
Y_RANGE = (0.07, 0.46)  # where the block is allowed to move to find calm space


def _opener_font(size):
    from PIL import ImageFont
    for name in ("Inter-Bold.ttf", "Inter-SemiBold.ttf", "Poppins-SemiBold.ttf"):
        if (FONT_DIR / name).exists():
            return ImageFont.truetype(str(FONT_DIR / name), size)
    return ImageFont.load_default()


def _tracked_width(font, line, track_px):
    return font.getlength(line) + track_px * max(0, len(line) - 1)


def _wrap(font, text, max_w, track_px):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if not cur or _tracked_width(font, trial, track_px) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _draw_tracked(draw, xy, line, font, track_px, fill):
    """Draw a line with letter-spacing while keeping the font's kerning:
    each glyph goes where the un-tracked prefix ends, plus the tracking."""
    x0, y = xy
    for i, ch in enumerate(line):
        if ch != " ":
            draw.text((x0 + font.getlength(line[:i]) + track_px * i, y), ch,
                      font=font, fill=fill)


def _pick_top(gray, box_w, box_h, x):
    """Top edge for the text block: the calmest band (least edge detail, so
    the words sit on wall/ceiling/sky rather than a head or furniture), nudged
    toward the reference position so openers still feel consistent.

    The band is scored by its busiest cells, not its mean, so a single head in
    one corner of the block still disqualifies it."""
    from PIL import ImageFilter, ImageStat
    W, H = gray.size
    edges = gray.filter(ImageFilter.GaussianBlur(1)).filter(ImageFilter.FIND_EDGES)
    lo, hi = int(H * Y_RANGE[0]), int(H * Y_RANGE[1]) - box_h
    pad = int(box_h * 0.2)
    x0, x1 = max(0, x - pad), min(W, x + box_w + pad)
    cols = 6
    best = None
    for top in range(lo, max(lo, hi) + 1, max(4, H // 120)):
        y0, y1 = max(0, top - pad), min(H, top + box_h + pad)
        cells = []
        for c in range(cols):
            cx0 = x0 + (x1 - x0) * c // cols
            cx1 = x0 + (x1 - x0) * (c + 1) // cols
            for cy0, cy1 in ((y0, (y0 + y1) // 2), ((y0 + y1) // 2, y1)):
                cells.append(ImageStat.Stat(edges.crop((cx0, cy0, cx1, cy1))).mean[0])
        cells.sort()
        busy = cells[-1] + cells[-2] + sum(cells) / len(cells)
        drift = abs(top - H * PREFERRED_Y) / H
        score = busy + 40 * drift
        if best is None or score < best[0]:
            best = (score, top)
    return best[1]


def stamp(path, text):
    from PIL import Image, ImageDraw, ImageFilter, ImageStat
    im = Image.open(path).convert("RGB")
    if im.width > im.height:
        im = im.rotate(90, expand=True)
    W, H = im.size

    size = max(16, round(W * FONT_SIZE))
    font = _opener_font(size)
    track = size * TRACKING
    lines = _wrap(font, text, W * TEXT_MAX_W, track)
    pitch = round(size * LEADING)
    asc = font.getbbox("Hb")[1]            # blank space above the cap line
    x = round(W * TEXT_X)
    block_w = max(_tracked_width(font, ln, track) for ln in lines)
    block_h = pitch * (len(lines) - 1) + size
    cap_top = _pick_top(im.convert("L"), int(block_w), block_h, x)

    # Glyphs on their own layer so the glow is built from the exact shapes.
    layer = Image.new("L", im.size, 0)
    d = ImageDraw.Draw(layer)
    for i, ln in enumerate(lines):
        _draw_tracked(d, (x, cap_top - asc + i * pitch), ln, font, track, 255)

    # Soft dark glow, as in the reference: no box, no hard outline. Stronger on
    # bright backgrounds so white type never washes out.
    region = im.convert("L").crop((x, cap_top, x + int(block_w) + 1,
                                   cap_top + block_h + 1))
    luma = ImageStat.Stat(region).mean[0]
    strength = 0.42 if luma < 150 else (0.55 if luma < 200 else 0.68)
    glow = layer.filter(ImageFilter.GaussianBlur(size * 0.28))
    glow = glow.point(lambda a: int(min(255, a * strength * 1.6)))
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    shadow.putalpha(glow)
    offset = Image.new("RGBA", im.size, (0, 0, 0, 0))
    offset.paste(shadow, (0, round(size * 0.05)))

    out = im.convert("RGBA")
    out.alpha_composite(offset)
    white = Image.new("RGBA", im.size, (255, 255, 255, 0))
    white.putalpha(layer)
    out.alpha_composite(white)
    out.convert("RGB").save(path)
    print(f"[title-slide] stamped at y={cap_top / H:.2f} (bg luma {luma:.0f}): {lines}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ASSETS / "title_slide.png"))
    ap.add_argument("--dry-run", action="store_true",
                    help="report bank stock without claiming anything")
    args = ap.parse_args()

    if args.dry_run:
        used = read_ledger()
        stock = available(used)
        total = total_images()
        log(f"bank: {total} images, {len(used)} used, "
            f"{sum(len(v) for v in stock.values())} free")
        for k in sorted(stock):
            log(f"  {k:20s} {len(stock[k])} free")
        return

    rng = random.SystemRandom()
    look, ident, src, hook = claim(rng)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out)

    if hook is None:
        # The photo already carries its own hook; a second line would clash.
        log("text-baked look, posted as generated -- nothing stamped.")
        return
    log(f"hook: {hook}")
    stamp(out, hook)


if __name__ == "__main__":
    main()
