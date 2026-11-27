#!/usr/bin/env python3
"""Remix bank: near-copies of proven viral slideshows with CheckVibe swapped in.

Each deck lives in assets/remix_bank/<deck_id>/ as slide_XX.(jpg|png) plus a
deck.json {"titles": [...], "captions": [...], "hashtags": {"core": [...], "pool": [...]},
"source", "source_views"}. Titles/captions rotate, so accounts that get the same
deck never post the same text. Decks are built offline
(Pinterest photos / original viral slides -> light Nano Banana 2 edit -> real
CheckVibe logo + real text drawn on top, see remix_tools.py) and only *posted*
from here.

Posting rules:
  * a deck is never posted twice on the same account
  * a deck another account used in the last SPREAD_DAYS is skipped, so the same
    deck doesn't hit several accounts at once
  * every post gets a small per-account crop/brightness jitter, so no two uploads
    are pixel-identical (TikTok duplicate-content checks)
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, 'assets', 'remix_bank')
W, H = 1080, 1440
SPREAD_DAYS = 2


def jitter(im, rng):
    """Cover-crop to 1080x1440 with a 1-3% random zoom, a few px of shift and +-1% brightness."""
    im = im.convert('RGB')
    s = max(W / im.width, H / im.height) * (1 + rng.uniform(0.01, 0.03))
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    l = (im.width - W) // 2 + rng.randint(-4, 4)
    t = (im.height - H) // 2 + rng.randint(-4, 4)
    im = im.crop((l, t, l + W, t + H))
    return ImageEnhance.Brightness(im).enhance(rng.uniform(0.99, 1.01))


def decks():
    if not os.path.isdir(BANK):
        return []
    return sorted(d for d in os.listdir(BANK) if os.path.isfile(os.path.join(BANK, d, 'deck.json')))


def pick_deck(account, ledger, rng):
    now = datetime.now(timezone.utc)
    used = [r['variant'].split(':', 1)[1] for r in ledger if r['format'] == 'remix' and ':' in r['variant']]
    mine = {r['variant'].split(':', 1)[1] for r in ledger
            if r['format'] == 'remix' and r['account'] == account and ':' in r['variant']}
    recent = {r['variant'].split(':', 1)[1] for r in ledger if r['format'] == 'remix'
              and r['dt'] > now - timedelta(days=SPREAD_DAYS) and ':' in r['variant']}
    free = [d for d in decks() if d not in mine]
    if not free:
        return None
    fresh = [d for d in free if d not in recent] or free
    low = min(used.count(d) for d in fresh)
    return rng.choice([d for d in fresh if used.count(d) == low])


@dataclass
class RemixDeck:
    slides: list
    hook: str
    caption: str
    variant: str
    photos: list = field(default_factory=list)
    drawn: list = field(default_factory=list)
    photo_slides: list = field(default_factory=list)


def build(account, ledger, rng):
    deck_id = pick_deck(account, ledger, rng)
    if deck_id is None:
        raise LookupError('remix bank exhausted for this account')
    d = os.path.join(BANK, deck_id)
    meta = json.load(open(os.path.join(d, 'deck.json'), encoding='utf-8'))
    files = sorted(f for f in os.listdir(d) if f.startswith('slide_'))
    seed = int(hashlib.sha1(f'{account}:{deck_id}'.encode()).hexdigest()[:8], 16)
    jr = random.Random(seed)
    slides = [jitter(Image.open(os.path.join(d, f)), jr) for f in files]
    title, caption = pick_text(meta, deck_id, ledger, jr)
    return RemixDeck(slides, title, caption, f'remix:{deck_id}')


def pick_text(meta, deck_id, ledger, rng):
    """n-th use of a deck gets the n-th title/caption variant; 5 hashtags = core + random pool picks."""
    n = sum(1 for r in ledger if r['format'] == 'remix' and r['variant'] == f'remix:{deck_id}')
    title = meta['titles'][n % len(meta['titles'])]
    caption = meta['captions'][(n * 2) % len(meta['captions'])]  # different stride from titles -> more combos
    core, pool = meta['hashtags']['core'], meta['hashtags']['pool']
    tags = core + rng.sample([t for t in pool if t not in core], 5 - len(core))
    return title, f'{caption}\n\n{" ".join(tags)}'.strip()
