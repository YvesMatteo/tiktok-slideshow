#!/usr/bin/env python3
"""Close the loop: fetch each account's recent post stats, learn format weights.

    TIKTOK_CLIENT_KEY=.. TIKTOK_CLIENT_SECRET=.. TIKTOK_REFRESH_TOKEN=.. \
        python3 scripts/pull_stats.py --account aitools_guy
    python3 scripts/pull_stats.py --learn-only     # recompute learned.json from STATS.tsv

Needs the `video.list` scope on the account's token (re-run tiktok_auth.py once).

Posts are matched to LEDGER.tsv rows by account + time: the first video created
within MATCH_HOURS after a deck was built is that deck. Drafts posted by hand
later than that are skipped rather than guessed.

Learning: a format's multiplier is the median of (views / account median views)
over its matched posts in the last 30 days, clamped to [0.3, 3], and only once it
has MIN_POSTS. The API has no save count, so views carry the signal; the
teardown showed saves and views move together on these accounts.
"""
from __future__ import annotations
import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_deck import FMT_DIR, LEARNED, read_ledger  # noqa: E402
from tiktok_draft import API, post_json, refresh_access_token  # noqa: E402

STATS = os.path.join(FMT_DIR, 'STATS.tsv')
SCOLS = ['account', 'video_id', 'create_time', 'views', 'likes', 'comments', 'shares']
MATCH_HOURS, MIN_POSTS, WINDOW_DAYS = 48, 3, 30


def fetch(account):
    tok = refresh_access_token(os.environ['TIKTOK_CLIENT_KEY'], os.environ['TIKTOK_CLIENT_SECRET'],
                               os.environ['TIKTOK_REFRESH_TOKEN'])
    fields = 'id,create_time,view_count,like_count,comment_count,share_count'
    res = post_json(f'{API}/v2/video/list/?fields={fields}', tok, {'max_count': 20})
    if res.get('error', {}).get('code') not in (None, 'ok'):
        raise SystemExit(f"video.list failed (does the token have the video.list scope?): {res['error']}")
    return [{'account': account, 'video_id': v['id'], 'create_time': v['create_time'],
             'views': v.get('view_count', 0), 'likes': v.get('like_count', 0),
             'comments': v.get('comment_count', 0), 'shares': v.get('share_count', 0)}
            for v in res.get('data', {}).get('videos', [])]


def read_stats():
    if not os.path.exists(STATS):
        return {}
    rows = {}
    for ln in open(STATS, encoding='utf-8'):
        if ln.startswith('account\t') or not ln.strip():
            continue
        r = dict(zip(SCOLS, ln.rstrip('\n').split('\t')))
        rows[r['video_id']] = r
    return rows


def write_stats(rows):
    with open(STATS, 'w', encoding='utf-8') as f:
        f.write('\t'.join(SCOLS) + '\n')
        for r in sorted(rows.values(), key=lambda r: (r['account'], int(r['create_time']))):
            f.write('\t'.join(str(r[c]) for c in SCOLS) + '\n')


def learn(ledger, stats, today=None):
    """-> {format: multiplier}. Pure function so it can be tested."""
    today = today or datetime.now(timezone.utc)
    by_acc = {}
    for r in stats.values():
        by_acc.setdefault(r['account'], []).append(r)
    ratios = {}
    for acc, vids in by_acc.items():
        vids.sort(key=lambda r: int(r['create_time']))
        med = statistics.median(int(v['views']) for v in vids) or 1
        taken = set()
        for row in sorted((r for r in ledger if r['account'] == acc), key=lambda r: r['dt']):
            if row['dt'] < today - timedelta(days=WINDOW_DAYS):
                continue
            t0 = row['dt'].timestamp()
            match = next((v for v in vids if v['video_id'] not in taken
                          and t0 <= int(v['create_time']) <= t0 + MATCH_HOURS * 3600), None)
            if match:
                taken.add(match['video_id'])
                ratios.setdefault(row['format'], []).append(int(match['views']) / med)
    return {f: round(min(3.0, max(0.3, statistics.median(r))), 3)
            for f, r in ratios.items() if len(r) >= MIN_POSTS}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--account')
    ap.add_argument('--learn-only', action='store_true')
    a = ap.parse_args()
    stats = read_stats()
    if not a.learn_only:
        if not a.account:
            raise SystemExit('--account is required unless --learn-only')
        for r in fetch(a.account):
            stats[r['video_id']] = r
        write_stats(stats)
    learned = learn(read_ledger(), stats)
    with open(LEARNED, 'w') as f:
        json.dump(learned, f, indent=1, sort_keys=True)
    print(json.dumps(learned))


if __name__ == '__main__':
    main()
