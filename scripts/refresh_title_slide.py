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

# These looks carry their own hook text baked into the photograph, so nothing
# is stamped over them.
TEXT_BAKED = {"start_porsche", "start_jet", "start_stairs", "start_wolf"}

HOOKS = ["5 apps I use to build my startup",
         "5 apps every startup founder should use",
         "5 apps I use daily in my business",
         "5 apps I use to run my entire business"]
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


def claim(rng: random.Random) -> tuple[str, str, Path]:
    """Pick and record one unclaimed image. Returns (look, ident, path)."""
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

    # Append before the image is used anywhere. If a later step fails, the
    # image stays burned -- losing one image is cheap, reusing one is not.
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    new = not LEDGER.exists()
    with open(LEDGER, "a") as f:
        if new:
            f.write("# Title-bank images already posted. Append-only; never "
                    "edit or remove a line -- an entry here is a promise that "
                    "the image will never be posted again.\n"
                    "# <look>/<id>\\t<claimed at UTC>\\t<claimed by>\n")
        f.write(f"{key}\t{datetime.now(timezone.utc).isoformat(timespec='seconds')}"
                f"\t{os.environ.get('TITLE_CLAIMED_BY', 'local')}\n")

    remaining = sum(len(v) for v in stock.values()) - 1
    log(f"claimed {key} ({remaining} unused images left in the bank)")
    return look, ident, BANK / look / ident


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
    print(f"[title-slide] stamped: {lines}")


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
    look, ident, src = claim(rng)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out)

    if look in TEXT_BAKED:
        log("text-baked look, nothing stamped.")
        return
    hook = rng.choice(HOOKS)
    log(f"hook: {hook}")
    stamp(out, hook)


if __name__ == "__main__":
    main()
