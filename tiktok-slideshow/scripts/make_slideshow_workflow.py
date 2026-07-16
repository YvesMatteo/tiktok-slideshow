#!/usr/bin/env python3
"""Autonomous TikTok slideshow generator — WORKFLOW / step-by-step edition.

Same collage / sticker look as make_slideshow_collage.py (lifestyle background,
big centered app-name heading, dark caption stickers, screenshot as a bottom
rounded card), but instead of a random "apps I use" list this tells the
step-by-step story of how a web developer actually builds a website, in a fixed
narrative order with a couple of slots randomized each run:

  1. design inspiration   -> Mobbin OR Pinterest      (random)
  2. build it             -> Lovable OR Cursor OR Antigravity  (random)
  3. check it             -> checkvibe.dev  (SEO, AEO & security)   [fixed]
  4. database / backend   -> Supabase OR Convex        (random)
  5. deploy it            -> Vercel OR Railway          (random)

Title slide is a lifestyle photo with an English headline + subtitle overlaid
on top. The title photo is picked at random from a small pool: the Higgsfield
lifestyle photo (title_inspo_bg.png) plus mog1/mog2/mog3 marketing photos if
they exist under assets/title_photos/.

Writes a fresh timestamped run under runs_workflow/ with six 3:4 slides
(title + 5 steps), caption.txt, post.html, post.zip and the Mac Photos importer.

Usage:  python3 make_slideshow_workflow.py [photos_dir]
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
RUNS = os.path.join(SKILL_DIR, 'runs_workflow')

# ---- title photo pool -------------------------------------------------------
# The Higgsfield lifestyle photo (regenerated each run by the scheduled task)
# plus optional mog1/mog2/mog3 marketing photos dropped in title_photos/.
TITLE_BG = os.path.join(ASSETS, 'title_inspo_bg.png')
TITLE_FALLBACK = os.path.join(ASSETS, 'title_slide.png')
TITLE_PHOTOS_DIR = os.path.join(ASSETS, 'title_photos')
MOG_NAMES = ['mog1', 'mog2', 'mog3']

# English title text in the reference style — edit these two lines to retune
TITLE_HEADLINE = "How I build a website step by step"
TITLE_SUB = "the exact tools I use, in order"

# ---- the workflow: one step per slide, each a fixed role with random picks ---
# Only candidates that actually have a screenshot in assets/screenshots/ are
# eligible; the first available one is kept if random picks miss.
WORKFLOW = [
    {"step": "design",   "options": ["mobbin", "pinterest"]},
    {"step": "build",    "options": ["lovable", "cursor", "antigravity"]},
    {"step": "check",    "options": ["checkvibe"]},
    {"step": "database", "options": ["supabase", "convex"]},
    {"step": "deploy",   "options": ["vercel", "railway"]},
]

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
    s = parts[0] if parts else ''
    if '. ' in s:
        a, b = s.split('. ', 1)
        return [a.strip() + '.', b.strip()]
    return [s]


def pick_title_photo():
    """Choose the title photo at random from the Higgsfield photo + mog1/2/3.

    Returns (path, label). Falls back to the baked title slide if nothing else
    is available."""
    pool = []
    if os.path.exists(TITLE_BG):
        pool.append((TITLE_BG, 'higgsfield'))
    if os.path.isdir(TITLE_PHOTOS_DIR):
        for name in MOG_NAMES:
            for ext in ('.png', '.jpg', '.jpeg', '.PNG', '.JPG'):
                p = os.path.join(TITLE_PHOTOS_DIR, name + ext)
                if os.path.exists(p):
                    pool.append((p, name))
                    break
    if not pool:
        return TITLE_FALLBACK, 'fallback (baked title_slide)'
    return random.choice(pool)


def pick_workflow_apps(roster):
    """Return an ordered list of app keys, one per workflow step.

    Randomizes each step's choice among its options, keeping only options that
    have a screenshot. Steps with no available screenshot are dropped."""
    apps = []
    for stepdef in WORKFLOW:
        avail = [k for k in stepdef['options'] if k in roster]
        if not avail:
            continue
        apps.append(random.choice(avail))
    return apps


def main():
    bank = json.load(open(os.path.join(ASSETS, 'copy_bank.json')))
    approved = base._lines(os.path.join(ASSETS, 'approved_photos.txt'))
    _pdir = os.path.abspath(PHOTOS)
    approved = [a for a in approved if os.path.exists(os.path.join(_pdir, a))]
    roster = available_roster()
    if not roster:
        raise SystemExit(f"No screenshots found in {SHOTS}")

    # ---- pick apps in the fixed workflow order ----
    apps = pick_workflow_apps(roster)
    if not apps:
        raise SystemExit("No workflow apps have screenshots available")
    variant = f"step1={bank['apps'][apps[0]]['name']}"

    # ---- title photo (random: higgsfield or mog1/2/3) ----
    title_bg, title_label = pick_title_photo()

    # ---- background photos matched to the title photo's mood ----
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

    # ---- caption (workflow framing) ----
    title = random.choice(bank.get('workflow_title', bank['slideshow_title']))
    tags = ' '.join(random.sample(bank['hashtags'], 5))
    order = ' -> '.join(['title'] + [bank['apps'][k]['name'] for k in apps])
    app_lines = [f"{i+1}. {bank['apps'][k]['name']}: {bank['apps'][k]['tagline']}"
                 for i, k in enumerate(apps)]
    templates = bank.get('workflow_caption_templates') or bank['caption_templates']
    template = random.choice(templates)
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
    print(f"STYLE: workflow / step-by-step collage")
    print(f"TITLE PHOTO: {title_label}")
    print(f"PHOTO TONE: {tone_note}")
    print(f"Slideshow ready: {out_dir}")
    if mirror:
        print(f"  Mirrored to: {mirror}")
    print(f"  Steps: {order}")
    print(f"  Title headline: {TITLE_HEADLINE}")
    print(f"  Caption title: {title}")
    print(f"  Hashtags: {tags}")
    return out_dir


if __name__ == '__main__':
    main()
