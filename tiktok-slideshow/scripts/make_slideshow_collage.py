#!/usr/bin/env python3
"""Autonomous TikTok slideshow generator — COLLAGE / sticker edition.

Recreates the "tools I use" collage look (lifestyle background, big centered
app-name heading, dark caption stickers, app screenshot as a bottom card).
Title slide is a Higgsfield lifestyle photo with an English headline +
subtitle overlaid on top. Uses the user's own screenshots (assets/screenshots)
and Pinterest backgrounds (pinterest_final). Reuses the copy bank for text.

Writes a fresh timestamped run under runs_collage/ with seven 3:4 slides
(title + 6 apps), caption.txt, post.html, post.zip and the Mac Photos
importer. Kept fully separate from the logo and browser-mockup generators.

Usage:  python3 make_slideshow_collage.py [photos_dir]
Only requires Pillow.
"""
import json
import os
import random
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_slideshow as base          # reuse caption / post.html / photo helpers
import slideshow_collage               # collage compositor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(SKILL_DIR, 'assets')
SHOTS = os.path.join(ASSETS, 'screenshots')
RUNS = os.path.join(SKILL_DIR, 'runs_collage')

# Higgsfield lifestyle photo for the title (falls back to the baked title slide)
TITLE_BG = os.path.join(ASSETS, 'title_inspo_bg.png')
TITLE_FALLBACK = os.path.join(ASSETS, 'title_slide.png')

# English title text in the reference style — edit these two lines to retune
TITLE_HEADLINE = "Tools I use as a web developer"
TITLE_SUB = "for design, code and inspiration"

N_APPS = 6

# WITH_SLIDEYS=1 pins slideys.app as the 3rd app slide on every run
# (slide 2 stays CheckVibe, rotation fills the remaining slots).
WITH_SLIDEYS = os.environ.get('WITH_SLIDEYS', '').strip().lower() in ('1', 'true', 'yes')

_args = [a for a in sys.argv[1:] if not a.startswith('--')]
PHOTOS = _args[0] if _args else base._detect_photos_dir()


def available_roster():
    if not os.path.isdir(SHOTS):
        return set()
    return {os.path.splitext(f)[0] for f in os.listdir(SHOTS)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))}


def chips_from_copy(block):
    """Split a copy block into up to two short caption stickers."""
    parts = [p.strip() for p in block.split('\n') if p.strip()]
    if len(parts) >= 2:
        return parts[:2]
    # single paragraph -> split on sentence boundary
    s = parts[0] if parts else ''
    if '. ' in s:
        a, b = s.split('. ', 1)
        return [a.strip() + '.', b.strip()]
    return [s]


def main():
    bank = json.load(open(os.path.join(ASSETS, 'copy_bank.json')))
    approved = base._lines(os.path.join(ASSETS, 'approved_photos.txt'))
    _pdir = os.path.abspath(PHOTOS)
    approved = [a for a in approved if os.path.exists(os.path.join(_pdir, a))]
    roster = available_roster()
    if not roster:
        raise SystemExit(f"No screenshots found in {SHOTS}")

    # ---- pick apps (only ones with screenshots) ----
    first_pool = [k for k in bank['first_slide_pool'] if k in roster]
    first = random.choice(first_pool) if first_pool else random.choice(list(roster))
    picked = [first]
    second = bank.get('second_slide')
    if second in roster and second != first:
        picked.append(second)
    slideys_pin = WITH_SLIDEYS and 'slideys' in roster and 'slideys' not in picked
    remaining = [k for k in roster if k not in picked
                 and not (slideys_pin and k == 'slideys')]
    need = max(0, N_APPS - len(picked) - (1 if slideys_pin else 0))
    rest = random.sample(remaining, min(need, len(remaining)))
    apps = picked + rest
    if slideys_pin:
        apps.insert(2, 'slideys')   # always the 3rd app slide
    variant = f"slide1={bank['apps'][first]['name']}"

    # ---- background photos matched to the title photo's mood ----
    title_bg = TITLE_BG if os.path.exists(TITLE_BG) else TITLE_FALLBACK
    app_photos, tone_note = base.pick_matching_photos(
        approved, os.path.abspath(PHOTOS), title_bg, len(apps))

    # ---- slide config ----
    config = [{'type': 'title_overlay', 'image': title_bg,
               'headline': TITLE_HEADLINE, 'sub': TITLE_SUB}]
    for i, key in enumerate(apps):
        a = bank['apps'][key]
        config.append({'type': 'app', 'photo': app_photos[i], 'shot': key,
                       'num': i + 1, 'name': a['name'],
                       'chips': chips_from_copy(random.choice(a['copy']))})

    # ---- render ----
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    out_dir = os.path.join(RUNS, stamp)
    slideshow_collage.render_slideshow(config, os.path.abspath(PHOTOS), SHOTS, out_dir)

    # ---- caption (same copy bank as the other editions) ----
    title = random.choice(bank['slideshow_title'])
    tags = ' '.join(random.sample(bank['hashtags'], 5))
    order = ' -> '.join(['title'] + [bank['apps'][k]['name'] for k in apps])
    app_lines = [f"{i+1}. {bank['apps'][k]['name']}: {bank['apps'][k]['tagline']}"
                 for i, k in enumerate(apps)]
    template = random.choice(bank['caption_templates'])
    full_caption = (template
                    .replace('{app_list}', '\n'.join(app_lines))
                    .replace('{hashtags}', tags))
    with open(os.path.join(out_dir, 'caption.txt'), 'w') as f:
        f.write(f"TITLE: {title}\n\nCAPTION:\n{full_caption}\n\n"
                f"---\nSlides: {order}\n"
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # ---- post sheet + zip + Mac Photos importer ----
    slide_files = [f"slide_{i:02d}.jpg" for i in range(len(config))]
    base.write_post_page(out_dir, title, full_caption, order, slide_files)
    mirror = base._mirror_post_html(os.path.join(out_dir, 'post.html'), stamp)

    now = datetime.now()
    print(f"GENERATED AT: {now.strftime('%H:%M  %a %b %d')}")
    print(f"FIRST SLIDE: {variant}")
    print(f"STYLE: collage / sticker screenshots")
    if slideys_pin:
        print("SLIDEYS PIN: active (slideys.app pinned as 3rd app slide)")
    print(f"TITLE PHOTO: {'higgsfield' if title_bg == TITLE_BG else 'fallback (baked title_slide)'}")
    print(f"PHOTO TONE: {tone_note}")
    print(f"Slideshow ready: {out_dir}")
    if mirror:
        print(f"  Mirrored to: {mirror}")
    print(f"  Apps: {order}")
    print(f"  Title headline: {TITLE_HEADLINE}")
    print(f"  Caption title: {title}")
    print(f"  Hashtags: {tags}")
    return out_dir


if __name__ == '__main__':
    main()
