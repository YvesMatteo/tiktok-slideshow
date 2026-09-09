#!/usr/bin/env python3
"""Refill assets/title_bank with fresh, never-before-seen title images.

The bank is consumed one image per post and never reused (see
refresh_title_slide.py), so it has to be topped up. This regenerates from the
nine committed source looks using Google's Gemini image model -- "Nano Banana
Pro" is Gemini 3 Pro Image, which is the same model the old Claude Cowork task
reached through Higgsfield, one hop closer to the source.

Auth: GEMINI_API_KEY. Image models are NOT on Gemini's free tier; at 3:4 / 2K
this bills roughly $0.134 an image, so `--count 100` costs about $13.

New images land beside the existing ones under assets/title_bank/<look>/ and
are picked up automatically. Filenames are content-hashed, so re-running can
never overwrite or duplicate an existing image, and anything already recorded
in USED.tsv stays used.

    python3 scripts/build_title_bank.py --count 100
    python3 scripts/build_title_bank.py --count 20 --look start_always_5
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import os
import random
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"
BANK = ASSETS / "title_bank"

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-pro-image")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

# Same weights the posting draw uses, so a refill keeps the mix roughly right.
WEIGHTS = {
    "start_18yo": 12, "start_always_2": 3, "start_always_3": 12,
    "start_always_4": 17, "start_always_5": 17, "start_porsche": 9.75,
    "start_jet": 9.75, "start_stairs": 9.75, "start_wolf": 9.75,
}

# Prompts as tuned on 2026-09-09: enough change to read as a different photo,
# not so much that it stops looking like the same person and palette. The
# text-baked looks must keep their wording, font, size and position untouched.
PROMPT_BLANK = (
    "Either the same person or a different attractive person about 25 years old, "
    "similar outfit and the same overall colour palette, same clean aesthetic and "
    "same mood. Change the scene moderately: a different room or background, a "
    "different camera angle and a different pose. Keep it photographic and "
    "realistic. No text anywhere in the image — completely blank, no writing on "
    "the body, the wall, or the background."
)
PROMPT_KEEP_TEXT = (
    "Keep the text exactly as it is — identical wording, font, size, weight, "
    "colour and position on the frame. Do not restyle, move or re-render the text "
    "in any way. Change only the photograph behind it, moderately: same subject "
    "and same mood and colour palette, but a different camera angle and different "
    "background details. Photographic and realistic."
)
PROMPT_KEEP_TEXT_WOLF = (
    "Keep the text exactly as it is — identical wording, font, size, weight, "
    "colour and position on the frame. Do not restyle, move or re-render the text "
    "in any way. Keep the same subject and composition, and change the background "
    "moderately: different setting details and slightly different lighting, same "
    "mood. Photographic and realistic."
)
TEXT_BAKED = {"start_porsche", "start_jet", "start_stairs", "start_wolf"}


def prompt_for(look: str) -> str:
    if look == "start_wolf":
        return PROMPT_KEEP_TEXT_WOLF
    return PROMPT_KEEP_TEXT if look in TEXT_BAKED else PROMPT_BLANK


def generate(api_key: str, source: Path, prompt: str) -> bytes | None:
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/png",
                             "data": base64.b64encode(source.read_bytes()).decode()}},
            {"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"],
                             "imageConfig": {"aspectRatio": "3:4", "imageSize": "2K"}},
    }
    req = urllib.request.Request(
        ENDPOINT.format(MODEL) + "?key=" + api_key,
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"  {type(e).__name__}: {e}")
        return None
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            blob = part.get("inlineData") or part.get("inline_data")
            if blob:
                return base64.b64decode(blob["data"])
        print(f"  no image returned (finishReason={cand.get('finishReason')})")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=50, help="images to add")
    ap.add_argument("--look", help="only refill this look (default: weighted mix)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    if not key and not args.dry_run:
        raise SystemExit("Set GEMINI_API_KEY (image models are not on the free tier).")

    looks = [args.look] if args.look else list(WEIGHTS)
    for look in looks:
        if not (ASSETS / f"{look}.png").exists():
            raise SystemExit(f"No source image assets/{look}.png")

    rng = random.SystemRandom()
    weights = [WEIGHTS.get(l, 1) for l in looks]
    plan = rng.choices(looks, weights=weights, k=args.count)
    print(f"model={MODEL}  adding {args.count} images "
          f"(~${args.count * 0.134:.2f} at 2K)")
    for look in sorted(set(plan)):
        print(f"  {look:20s} {plan.count(look)}")
    if args.dry_run:
        return

    from PIL import Image
    added = failed = 0
    for i, look in enumerate(plan, 1):
        src = ASSETS / f"{look}.png"
        raw = generate(key, src, prompt_for(look))
        if raw is None:
            failed += 1
            print(f"[{i}/{len(plan)}] {look}: failed")
            continue
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if im.width > im.height:
            failed += 1
            print(f"[{i}/{len(plan)}] {look}: landscape {im.size}, dropped")
            continue
        ident = hashlib.sha1(raw).hexdigest()[:8]
        out = BANK / look / f"{ident}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            print(f"[{i}/{len(plan)}] {look}: identical image already banked, skipped")
            continue
        im.resize((1080, 1440), Image.LANCZOS).save(out, quality=92, optimize=True)
        added += 1
        print(f"[{i}/{len(plan)}] {look}: + {out.relative_to(REPO_ROOT)}")
    print(f"\nadded {added}, failed {failed}")
    print("Commit assets/title_bank/ so the new images are available to CI.")


if __name__ == "__main__":
    main()
