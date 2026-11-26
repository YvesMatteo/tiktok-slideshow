#!/usr/bin/env python3
"""Self-checks for the format engine: python3 scripts/test_make_deck.py"""
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_deck as M  # noqa: E402
import pull_stats as P  # noqa: E402

NOW = datetime.now(timezone.utc)


def row(acc, fmt, days_ago, variant=None):
    dt = NOW - timedelta(days=days_ago)
    return {'ts': dt.isoformat(), 'dt': dt, 'account': acc, 'format': fmt,
            'variant': variant or f'{fmt}:0', 'hook': '', 'photos': '', 'run': 't'}


# never repeats the account's previous format
for seed in range(200):
    assert M.choose_format('a', [row('a', 'versus', 1)], random.Random(seed), {}) != 'versus'

# a format rests after 3 uses in 14 days
led = [row('a', 'maxxing', d) for d in (2, 4, 6)] + [row('a', 'versus', 1)]
for seed in range(200):
    assert M.choose_format('a', led, random.Random(seed), {}) != 'maxxing'

# learned multiplier of ~0 still never resurrects a resting/last format, and 3x boosts
picks = [M.choose_format('a', [], random.Random(s), {'killing_app': 3.0}) for s in range(2000)]
assert picks.count('killing_app') > picks.count('objection_loop')

# least-used variant is chosen
ctx = M.Ctx([row('a', 'versus', 1, 'versus:0'), row('b', 'versus', 2, 'versus:0')], random.Random(0))
assert ctx.pick_variant('versus', ['x', 'y'])[0] == 1

# learn(): matches posts after the deck, needs MIN_POSTS, clamps
t = lambda d: int((NOW - timedelta(days=d)).timestamp())  # noqa: E731
led = [row('a', 'versus', d) for d in (10, 8, 6)] + [row('a', 'maxxing', d) for d in (9, 7, 5)]
stats = {}
for i, (d, views) in enumerate([(10, 10000), (8, 9000), (6, 12000), (9, 1000), (7, 1000), (5, 1000)]):
    stats[str(i)] = {'account': 'a', 'video_id': str(i), 'create_time': t(d) + 3600, 'views': views}
learned = P.learn(led, stats, NOW)
assert learned['versus'] > 1 > learned['maxxing'], learned
assert P.learn(led[:2], stats, NOW).get('versus') is None  # under MIN_POSTS

# QA catches a banned phrase and missing glyphs
import deck_formats as F  # noqa: E402
d = F.Deck([], 'hook', '#a', 'x:0', drawn=[('Good afternoon, Yves', F.BOLD), ('ok → \U0001F600', F.BOLD)])
errs = ' '.join(M.qa(d))
assert 'banned' in errs and 'missing glyphs' in errs, errs

print('ok')
