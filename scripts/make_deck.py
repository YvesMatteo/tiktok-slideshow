#!/usr/bin/env python3
"""Build one slideshow for one account, choosing the format on autopilot.

    python3 scripts/make_deck.py --account aitools_guy            # pick + build
    python3 scripts/make_deck.py --account x --format versus      # force a format
    python3 scripts/make_deck.py --account x --dry-run            # no ledger write

Output matches make_slideshow.py (runs/<stamp>/slide_XX.jpg + caption.txt) so
tiktok_draft.py and the workflow are unchanged.

Rotation rules come from the 2026-11 teardown: every account that reused a
template more than ~3 times, or posted the same thing twice in a row, decayed.
  * never the account's previous format
  * a format rests after 3 uses on one account inside 14 days
  * formats already used by another account today are down-weighted
  * learned multipliers from pull_stats.py (assets/formats/learned.json)
  * photos are never reused within PHOTO_REST_DAYS (any account)
"""
from __future__ import annotations
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deck_formats as F  # noqa: E402
import remix as R  # noqa: E402

ROOT = F.ROOT
FMT_DIR = os.path.join(ROOT, 'assets', 'formats')
LEDGER = os.path.join(FMT_DIR, 'LEDGER.tsv')
LEARNED = os.path.join(FMT_DIR, 'learned.json')
RUNS = os.path.join(ROOT, 'runs')

BASE_WEIGHTS = {'apps_classic': 3, 'two_types': 2, 'versus': 2, 'price_parity': 2,
                'maxxing': 2, 'killing_app': 1.5, 'objection_loop': 1.5}
REST_USES, REST_DAYS = 3, 14
CLASSIC_SHARE = 0.35                          # share of posts that are the classic 'N apps I use' deck
APP_COUNTS = {5: 0.4, 4: 0.35, 3: 0.25}       # how many tools a classic deck shows
PHOTO_REST_DAYS = 60
BANNED = re.compile(r'\byves\b|good (morning|afternoon|evening),|winter arc|every startup founder should'
                    r'|feel illegal|link in bio|comment below|follow for', re.I)
COLS = ['ts', 'account', 'format', 'variant', 'hook', 'photos', 'run']


def now():
    return datetime.now(timezone.utc)


def read_ledger():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, encoding='utf-8') as f:
        rows = [dict(zip(COLS, ln.rstrip('\n').split('\t'))) for ln in f if ln.strip() and not ln.startswith('ts\t')]
    for r in rows:
        r['dt'] = datetime.fromisoformat(r['ts'])
    return rows


def append_ledger(row):
    new = not os.path.exists(LEDGER)
    with open(LEDGER, 'a', encoding='utf-8') as f:
        if new:
            f.write('\t'.join(COLS) + '\n')
        f.write('\t'.join(str(row[c]).replace('\t', ' ').replace('\n', ' ') for c in COLS) + '\n')


def choose_format(account, ledger, rng, learned):
    mine = sorted((r for r in ledger if r['account'] == account), key=lambda r: r['dt'])
    last = mine[-1]['format'] if mine else None
    recent = [r['format'] for r in mine if r['dt'] > now() - timedelta(days=REST_DAYS)]
    today = {r['format'] for r in ledger if r['dt'].date() == now().date() and r['account'] != account}
    weights = {}
    for fmt, w in BASE_WEIGHTS.items():
        if fmt == last or recent.count(fmt) >= REST_USES:
            continue
        w *= learned.get(fmt, 1.0)
        if fmt in today:
            w *= 0.3
        weights[fmt] = w
    if not weights:  # everything resting: fall back to anything but the last one
        weights = {f: w for f, w in BASE_WEIGHTS.items() if f != last}
    fmts = list(weights)
    return rng.choices(fmts, [weights[f] for f in fmts])[0]


class Ctx:
    """What a format needs from history: least-used variants, fresh photos."""

    def __init__(self, ledger, rng):
        self.ledger, self.rng = ledger, rng

    def pick_variant(self, fmt, variants):
        used = [r['variant'] for r in self.ledger if r['format'] == fmt]
        counts = [sum(u.split(':')[1] == str(i) for u in used if ':' in u) for i in range(len(variants))]
        low = min(counts)
        i = self.rng.choice([i for i, n in enumerate(counts) if n == low])
        return i, variants[i]

    def pick_photos(self, n):
        cutoff = now() - timedelta(days=PHOTO_REST_DAYS)
        burned = {p for r in self.ledger if r['dt'] > cutoff for p in r['photos'].split(',') if p}
        pool = [p.strip() for p in open(os.path.join(ROOT, 'assets', 'approved_photos.txt')) if p.strip()]
        pool = [p for p in pool if os.path.exists(os.path.join(F.PHOTOS, p))]
        fresh = [p for p in pool if p not in burned]
        if len(fresh) < n:
            raise SystemExit(f'QA: only {len(fresh)} unburned photos left (need {n}); add photos '
                             f'to assets/approved_photos.txt')
        return self.rng.sample(fresh, n)


# --------------------------------------------------------------------- QA ---

def glyphs(path, _cache={}):
    if path not in _cache:
        from fontTools.ttLib import TTFont
        _cache[path] = set(TTFont(path).getBestCmap())
    return _cache[path]


def qa(deck):
    """Hard gate: anything here fails the build instead of posting a bad deck."""
    errs = []
    if not 1 <= len(deck.slides) <= 35:
        errs.append(f'{len(deck.slides)} slides')
    for i, s in enumerate(deck.slides):
        if s.size != (F.W, F.H):
            errs.append(f'slide {i} is {s.size}')
    for text, font in deck.drawn:
        missing = {ch for ch in text if ch not in '\n' and ord(ch) not in glyphs(font)}
        if missing:
            errs.append(f'missing glyphs {missing!r} in {text!r}')
    blob = ' '.join(t for t, _ in deck.drawn) + ' ' + deck.caption + ' ' + deck.hook
    if BANNED.search(blob):
        errs.append(f'banned phrase: {BANNED.search(blob).group(0)!r}')
    if len(deck.hook.split()) > 12:
        errs.append(f'hook too long ({len(deck.hook.split())} words): {deck.hook!r}')
    if deck.caption.count('#') > 5:
        errs.append('more than 5 hashtags')
    for i in deck.photo_slides:  # white text on photos: center band must be dark enough
        band = deck.slides[i].convert('L').crop((140, 280, F.W - 140, 1000)).resize((40, 40))
        luma = sum(band.getdata()) / 1600
        if luma > 150:
            errs.append(f'slide {i} too bright behind text (luma {luma:.0f})')
    return errs


# ------------------------------------------------------------------ build ---

def wants_classic(account, ledger, rng):
    """Mix the original 'N apps I use to run my business' deck in between remixes, never twice in a row."""
    mine = sorted((r for r in ledger if r['account'] == account), key=lambda r: r['dt'])
    return not (mine and mine[-1]['format'] == 'apps_classic') and rng.random() < CLASSIC_SHARE


def build_apps_classic(account, n_apps=5):
    """The proven 'N apps' deck (3, 4 or 5 tools), built by the existing pipeline."""
    env = dict(os.environ, TITLE_CLAIMED_BY=os.environ.get('TITLE_CLAIMED_BY', f'{account}@local'),
               N_APPS=str(n_apps))
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'refresh_title_slide.py')], check=True, env=env)
    before = set(os.listdir(RUNS)) if os.path.isdir(RUNS) else set()
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'make_slideshow.py')], check=True,
                   env=env, stdout=subprocess.DEVNULL)
    out = sorted(set(os.listdir(RUNS)) - before)[-1]
    cap = open(os.path.join(RUNS, out, 'caption.txt'), encoding='utf-8').read()
    title = re.search(r'^TITLE: (.*)$', cap, re.M)
    return os.path.join(RUNS, out), (title.group(1) if title else '')


def write_run(deck, account, fmt):
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    out = os.path.join(RUNS, f'{stamp}_{account}_{fmt}')
    os.makedirs(out, exist_ok=True)
    for i, s in enumerate(deck.slides):
        s.save(os.path.join(out, f'slide_{i:02d}.jpg'), quality=92)
    with open(os.path.join(out, 'caption.txt'), 'w', encoding='utf-8') as f:
        f.write(f'TITLE: {deck.hook[:90]}\n\nCAPTION:\n{deck.caption}\n\n---\n'
                f'FORMAT: {fmt}\nVARIANT: {deck.variant}\nACCOUNT: {account}\n')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--account', required=True)
    ap.add_argument('--format', choices=sorted(BASE_WEIGHTS) + ['remix'])
    ap.add_argument('--seed', type=int)
    ap.add_argument('--dry-run', action='store_true', help='build but do not write the ledger')
    a = ap.parse_args(argv)

    rng = random.Random(a.seed)
    ledger = read_ledger()
    learned = json.load(open(LEARNED)) if os.path.exists(LEARNED) else {}
    bank = json.load(open(os.path.join(FMT_DIR, 'bank.json'), encoding='utf-8'))
    # Remix decks (near-copies of proven viral posts) are the main format. The
    # generated formats are only a fallback for when this account has used up the bank.
    deck = None
    if a.format is None and wants_classic(a.account, ledger, rng):
        a_fmt = 'apps_classic'
    else:
        a_fmt = a.format
    if a_fmt is None or a.format == 'remix':
        try:
            deck, fmt = R.build(a.account, ledger, rng), 'remix'
        except LookupError:
            if a.format:
                raise
            print('::warning::remix bank exhausted for this account; falling back', file=sys.stderr)
    if deck is None:
        fmt = a_fmt or choose_format(a.account, ledger, rng, learned)

    if fmt == 'apps_classic':
        n_apps = rng.choices(list(APP_COUNTS), list(APP_COUNTS.values()))[0]
        try:
            out, hook = build_apps_classic(a.account, n_apps)
            variant, photos = f'apps_classic:{n_apps}', ''
        except subprocess.CalledProcessError:
            if a.format:
                raise
            # usually: title bank exhausted. Post a remix (or another format) rather than nothing.
            print('::warning::apps_classic failed (title bank empty?); picking another format', file=sys.stderr)
            try:
                deck, fmt = R.build(a.account, ledger, rng), 'remix'
            except LookupError:
                fmt = choose_format(a.account, ledger, rng, dict(learned, apps_classic=0))
    if fmt != 'apps_classic':
        if deck is None:
            deck = F.FORMATS[fmt](rng, bank, Ctx(ledger, rng))
        errs = qa(deck)
        if errs:
            raise SystemExit('QA failed:\n  ' + '\n  '.join(errs))
        out = write_run(deck, a.account, fmt)
        hook, variant, photos = deck.hook, deck.variant, ','.join(deck.photos)

    if not a.dry_run:
        append_ledger({'ts': now().isoformat(timespec='seconds'), 'account': a.account, 'format': fmt,
                       'variant': variant, 'hook': hook, 'photos': photos,
                       'run': os.environ.get('GITHUB_RUN_ID', 'local')})
    print(out)
    print(f'format={fmt} hook={hook!r}', file=sys.stderr)


if __name__ == '__main__':
    main()
