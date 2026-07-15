#!/usr/bin/env python3
"""Regenerate the collage title photo (assets/title_inspo_bg.png) via Higgsfield.

Runs in CI (GitHub Actions) so every cloud run gets a fresh lifestyle title
photo, mirroring what the Cowork scheduled task does with the Higgsfield MCP.

Auth: set HF_KEY = "your-api-key:your-api-secret" (a single GitHub secret), or
      HF_API_KEY + HF_API_SECRET. Get them at https://cloud.higgsfield.ai/.

Model: configurable via HF_MODEL (defaults to a photoreal text-to-image model).
       Aspect 3:4, 2K. One image, no reference media.

The script NEVER hard-fails the build: if the key is missing, credits are out,
the API errors, times out, or flags NSFW, it prints a warning and exits 0 so the
generator falls back to the committed title photo. This matches the Cowork spec
("never error out on the title regen").
"""
import os
import random
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
TITLE_BG = os.path.join(REPO_ROOT, "assets", "title_inspo_bg.png")

# Photoreal text-to-image model slug on Higgsfield Cloud. Override with HF_MODEL.
MODEL = os.environ.get("HF_MODEL", "bytedance/seedream/v4/text-to-image")

SETTINGS = [
    "sitting on the edge of a luxury infinity pool overlooking the ocean at golden hour",
    "on a modern villa rooftop terrace at sunset",
    "leaning on the glass balcony of a penthouse with a city skyline",
    "by a pool at an expensive minimalist villa with palm trees and marble",
]

TAIL = ("realistic natural skin and muscle texture, looks like a real photo taken "
        "by a friend, not a professional shoot, vertical 3:4, clean empty sky/space "
        "in the upper third of the frame.")


def build_prompt():
    setting = random.choice(SETTINGS)
    return (
        "An authentic amateur iPhone snapshot, candid, mild sensor grain, natural "
        "light, slightly imperfect phone-camera framing, no gloss, no retouching, "
        "no CGI, no 3D render, absolutely no text, of an attractive athletic young "
        "man about 22 with a muscular toned physique (broad shoulders, defined "
        f"muscular back), shirtless or in a fitted tank top, seen from behind or "
        f"slightly to the side (face not required), {setting}. {TAIL}"
    )


def warn_skip(msg):
    print(f"[refresh_title] SKIP: {msg} -- falling back to committed title photo.")
    sys.exit(0)


def main():
    if not (os.environ.get("HF_KEY") or
            (os.environ.get("HF_API_KEY") and os.environ.get("HF_API_SECRET"))):
        warn_skip("no Higgsfield credentials (set HF_KEY secret)")

    try:
        import higgsfield_client as hf
    except Exception as e:  # noqa: BLE001
        warn_skip(f"higgsfield-client not installed ({e})")

    prompt = build_prompt()
    print(f"[refresh_title] model={MODEL}")
    print(f"[refresh_title] prompt={prompt}")

    try:
        result = hf.subscribe(
            MODEL,
            arguments={
                "prompt": prompt,
                "resolution": "2K",
                "aspect_ratio": "3:4",
                "camera_fixed": False,
            },
        )
    except Exception as e:  # noqa: BLE001  (covers Failed/NSFW/timeout/network)
        warn_skip(f"generation failed ({type(e).__name__}: {e})")

    try:
        url = result["images"][0]["url"]
    except Exception as e:  # noqa: BLE001
        warn_skip(f"unexpected response shape ({e}); got {str(result)[:200]}")

    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
        if len(data) < 10_000:
            warn_skip(f"downloaded image suspiciously small ({len(data)} bytes)")
        with open(TITLE_BG, "wb") as f:
            f.write(data)
    except Exception as e:  # noqa: BLE001
        warn_skip(f"download failed ({e})")

    print(f"[refresh_title] OK -> wrote {TITLE_BG} ({len(data)} bytes) from {url}")


if __name__ == "__main__":
    main()
