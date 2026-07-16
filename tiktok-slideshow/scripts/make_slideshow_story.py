#!/usr/bin/env python3
"""Autonomous TikTok slideshow generator — STORY / narrative edition.

The checkvibe "I almost lost my business overnight" story: 7 slides.

  slide 0 : the shared Higgsfield title slide (assets/title_slide.png) — the
            same title image the other slideshows use, regenerated per run by
            the scheduled task before this script runs.
  slides 1-5 : caption-over-photo beats (launch -> got users -> hacked ->
            leaked -> prevented -> built checkvibe -> free scan CTA). Copy
            varies a bit each run by drawing from story_bank.json. Backgrounds
            come from pinterest_final (the same photo pool the other
            slideshows use), tone-matched to the title slide.
  slide 6 : the checkvibe.dev logo slide.

Reuses make_slideshow.py's caption / post.html / photo-matching helpers so
all generators stay in sync. Renders via slideshow_story.py.

Usage:  python3 make_slideshow_story.py [photos_dir]
Only requires Pillow.
"""
import json
import os
import random
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_slideshow as base          # caption / post.html / photo helpers
import slideshow_story                 # story compositor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(SKILL_DIR, 'assets')
LOGOS = os.path.join(ASSETS, 'logos')
RUNS = os.path.join(SKILL_DIR, 'runs_story')

_args = [a for a in sys.argv[1:] if not a.startswith('--')]
PHOTOS = _args[0] if _args else base._detect_photos_dir()


def main():
    bank = json.load(open(os.path.join(ASSETS, 'story_bank.json')))
    approved = base._lines(os.path.join(ASSETS, 'approved_photos.txt'))
    _pdir = os.path.abspath(PHOTOS)
    approved = [a for a in approved if os.path.exists(os.path.join(_pdir, a))]

    # ---- 5 background photos matched to the title slide's mood ----
    # (beats 1-5 need a photo each; the title slide and logo slide don't)
    title_image = os.path.join(ASSETS, 'title_slide.png')
    photo_beats = [b for b in bank['beats'] if b['id'] != 'cta']  # cta is logo
    # every beat except the final CTA (logo) rides on a photo
    n_photos = len(photo_beats)
    photos, tone_note = base.pick_matching_photos(
        approved, _pdir, title_image, n_photos)

    # ---- assemble slide config, varying copy per beat ----
    config = [{'type': 'static', 'image': title_image}]
    pi = 0
    for b in bank['beats']:
        if b['id'] == 'cta':
            # final logo slide
            config.append({
                'type': 'logo',
                'logo_path': os.path.join(LOGOS, 'checkvibe.png'),
                'top': random.choice(b['top']),
            })
        else:
            slide = {'type': 'story', 'photo': photos[pi],
                     'pos': b.get('pos', 'top'),
                     'top': random.choice(b['top'])}
            if b.get('pos') == 'split':
                slide['bottom'] = random.choice(b['bottom'])
            config.append(slide)
            pi += 1

    # ---- render ----
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    out_dir = os.path.join(RUNS, stamp)
    slideshow_story.render_slideshow(config, _pdir, LOGOS, out_dir)

    # ---- caption ----
    title = random.choice(bank['title_top'])
    tags = ' '.join(random.sample(bank['hashtags'], 5))
    beat_names = ['title', 'launch', 'hacked', 'prevented', 'built',
                  'free-scan', 'checkvibe.dev']
    order = ' -> '.join(beat_names)
    template = random.choice(bank['caption_templates'])
    full_caption = template.replace('{hashtags}', tags)
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
    print(f"STYLE: story / narrative")
    print(f"PHOTO TONE: {tone_note}")
    print(f"Slideshow ready: {out_dir}")
    if mirror:
        print(f"  Mirrored to: {mirror}")
    else:
        print(f"  No cloud-synced folder found (set SLIDESHOW_SHARE_DIR for phone sync).")
    print(f"  Slides: {order}")
    print(f"  Title: {title}")
    print(f"  Caption length: {len(full_caption)} chars")
    print(f"  Hashtags: {tags}")
    return out_dir


if __name__ == '__main__':
    main()
