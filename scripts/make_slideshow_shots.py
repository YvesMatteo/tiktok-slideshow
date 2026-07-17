#!/usr/bin/env python3
"""Autonomous TikTok slideshow generator — SCREENSHOT / browser-mockup edition.

Same concept and copy as make_slideshow.py, but every app slide shows the
app's real screenshot framed as a browser window (the hero visual) instead
of a logo tile. Only apps that have a screenshot in assets/screenshots/ are
eligible. Title slide stays the static Higgsfield image. Writes a fresh
timestamped run under runs_screenshots/ with six 3:4 slides, caption.txt,
post.html, post.zip and the Mac Photos importer.

Reuses make_slideshow.py's post-page / caption / photo-matching helpers so
the two generators stay in sync; renders via slideshow_shots.py so the
logo-based compositor is untouched.

Usage:  python3 make_slideshow_shots.py [photos_dir]
Only requires Pillow.
"""
import json
import os
import random
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_slideshow as base          # reuse caption / post.html / photo helpers
import slideshow_shots                 # browser-mockup compositor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(SKILL_DIR, 'assets')
SHOTS = os.path.join(ASSETS, 'screenshots')
RUNS = os.path.join(SKILL_DIR, 'runs_screenshots')

_args = [a for a in sys.argv[1:] if not a.startswith('--')]
PHOTOS = _args[0] if _args else base._detect_photos_dir()


def available_roster():
    """App keys that have a screenshot on disk."""
    if not os.path.isdir(SHOTS):
        return set()
    return {os.path.splitext(f)[0] for f in os.listdir(SHOTS)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))}


def main():
    bank = json.load(open(os.path.join(ASSETS, 'copy_bank.json')))
    approved = base._lines(os.path.join(ASSETS, 'approved_photos.txt'))
    _pdir = os.path.abspath(PHOTOS)
    approved = [a for a in approved if os.path.exists(os.path.join(_pdir, a))]
    roster = available_roster()
    if not roster:
        raise SystemExit(f"No screenshots found in {SHOTS}")

    # ---- pick apps (only ones with screenshots) ----
    # slide 1: a first-slide-pool app; slide 2: CheckVibe (if available);
    # slides 3-5: distinct apps from the rest of the screenshot roster.
    first_pool = [k for k in bank['first_slide_pool'] if k in roster]
    first = random.choice(first_pool) if first_pool else random.choice(list(roster))
    picked = [first]
    second = bank.get('second_slide')
    if second in roster and second != first:
        picked.append(second)
    if os.environ.get('WITH_SLIDEYS') == '1' and 'slideys' in roster \
            and 'slideys' not in picked:
        picked.append('slideys')
    remaining = [k for k in roster if k not in picked]
    need = max(0, 5 - len(picked))
    rest = random.sample(remaining, min(need, len(remaining)))
    apps = picked + rest
    variant = f"slide1={bank['apps'][first]['name']}"

    # ---- background photos matched to the title slide's mood ----
    title_image = os.path.join(ASSETS, 'title_slide.png')
    app_photos, tone_note = base.pick_matching_photos(
        approved, os.path.abspath(PHOTOS), title_image, len(apps))

    # ---- slide config: static title + hero-screenshot app slides ----
    config = [{'type': 'static', 'image': title_image}]
    for i, key in enumerate(apps):
        a = bank['apps'][key]
        config.append({'type': 'app', 'photo': app_photos[i], 'shot': key,
                       'num': i + 1, 'name': a['name'],
                       'body': random.choice(a['copy'])})

    # ---- render ----
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    out_dir = os.path.join(RUNS, stamp)
    slideshow_shots.render_slideshow(config, os.path.abspath(PHOTOS), SHOTS, out_dir)

    # ---- caption (same copy bank as the logo generator) ----
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

    # ---- one-click post sheet + zip + Mac Photos importer ----
    slide_files = [f"slide_{i:02d}.jpg" for i in range(len(config))]
    base.write_post_page(out_dir, title, full_caption, order, slide_files)
    mirror = base._mirror_post_html(os.path.join(out_dir, 'post.html'), stamp)

    now = datetime.now()
    print(f"GENERATED AT: {now.strftime('%H:%M  %a %b %d')}")
    print(f"FIRST SLIDE: {variant}")
    print(f"STYLE: browser-mockup screenshots")
    print(f"PHOTO TONE: {tone_note}")
    print(f"Slideshow ready: {out_dir}")
    if mirror:
        print(f"  Mirrored to: {mirror}")
    else:
        print(f"  No cloud-synced folder found (set SLIDESHOW_SHARE_DIR for phone sync).")
    print(f"  Apps: {order}")
    print(f"  Title: {title}")
    print(f"  Caption length: {len(full_caption)} chars")
    print(f"  Hashtags: {tags}")
    return out_dir


if __name__ == '__main__':
    main()
