#!/usr/bin/env python3
"""Refresh the 5-apps title slide: weighted draw from the 9 starting images,
regenerated through Higgsfield image-to-image, then stamped with a hook line.

This reproduces what the (now disabled) Claude Cowork scheduled task did with
the Higgsfield MCP. GitHub Actions has no MCP access, so the generation goes
through the Higgsfield Cloud HTTP API via the `higgsfield-client` package.

Auth: HF_KEY = "key-id:key-secret" (one GitHub secret), or HF_API_KEY +
      HF_API_SECRET. Credentials are created at https://cloud.higgsfield.ai/.

Model: the Cowork task used `nano_banana_pro`, which exists only in the
       Higgsfield MCP catalog -- the Cloud API is a separate registry. The
       closest Cloud equivalents are tried in order (HF_MODELS, or HF_MODEL to
       pin exactly one): `nano-banana`, then `higgsfield-ai/popcorn/auto`.
       A model the account cannot reach answers 404/423 on submit in well under
       a second, so the chain costs nothing when the first choice is enabled.

The script NEVER hard-fails the build. Missing key, no credits, API error,
timeout, NSFW flag, bad response -- it warns, falls back to the drawn local
image (stamped or not per the case below), and exits 0.
"""
from __future__ import annotations
import os
import random
import shutil
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"
TITLE_SLIDE = ASSETS / "title_slide.png"
FONT_DIR = ASSETS / "fonts"

# --------------------------------------------------------------------------
# Everything below to the next divider came from the Claude Cowork scheduled
# task that used to run this every morning. It lived only in that task's text,
# so it is pinned here as the single source of truth. Do not retune casually.
# --------------------------------------------------------------------------

# Weighted draw over the 9 starting images (percentages, sum 100).
POOL = [("start_18yo.png", 12), ("start_always_2.png", 3), ("start_always_3.png", 12),
        ("start_always_4.png", 17), ("start_always_5.png", 17), ("start_porsche.png", 9.75),
        ("start_jet.png", 9.75), ("start_stairs.png", 9.75), ("start_wolf.png", 9.75)]

# CASE B images already carry their own hook text, baked into the photo.
TEXT_BAKED = {"start_porsche.png", "start_jet.png", "start_stairs.png", "start_wolf.png"}

# CASE A only: one of these is stamped onto the generated image.
HOOKS = ["5 apps I use to build my startup",
         "5 apps every startup founder should use",
         "5 apps I use daily in my business",
         "5 apps I use to run my entire business"]

# CASE A generation prompt (blank images -- keep them free of any text so the
# stamped hook is the only writing in the frame).
PROMPT_BLANK = (
    "Either Same person or Different attractive about 25 year old person, "
    "similar outfit, same overall color palette, clean and same aesthetic. "
    "No text anywhere in the image — completely blank, no writing on the body, "
    "the wall, or the background."
)

# CASE B generation prompts, per image. Nothing is stamped afterwards.
PROMPTS_TEXT_BAKED = {
    "start_wolf.png": "Keep the photo exactly the same, just change the background a bit.",
    "start_porsche.png": "Keep the text exactly the same, change the image a bit overall.",
    "start_jet.png": "Keep the text exactly the same, change the image a bit overall.",
    "start_stairs.png": "Keep the text exactly the same, change the image a bit overall.",
}

# Generation settings (Cowork used model nano_banana_pro, 3:4, 2k, count 1,
# one reference image; the Cloud model has no resolution knob).
ASPECT_RATIO = "3:4"
NUM_IMAGES = 1

# --------------------------------------------------------------------------

# Tried in order; the first that accepts the request wins. HF_MODEL pins one.
DEFAULT_MODELS = ["nano-banana", "higgsfield-ai/popcorn/auto"]
MODELS = ([os.environ["HF_MODEL"]] if os.environ.get("HF_MODEL")
          else [m.strip() for m in os.environ.get("HF_MODELS", "").split(",") if m.strip()]
          or DEFAULT_MODELS)
GEN_TIMEOUT = float(os.environ.get("HF_TIMEOUT", "420"))   # seconds, whole job
POLL_DELAY = 3.0


def log(msg):
    print(f"[refresh_title_slide] {msg}", flush=True)


def warn(msg):
    log(f"WARN: {msg}")


def build_arguments(model: str, prompt: str, image_url: str) -> dict:
    """Per-family argument shape, from docs.higgsfield.ai/docs/openapi.json."""
    if model.rstrip("/").endswith("nano-banana"):
        return {
            "prompt": prompt,
            "num_images": NUM_IMAGES,
            "aspect_ratio": ASPECT_RATIO,
            "input_images": [{"type": "image_url", "image_url": image_url}],
            "output_format": "png",
        }
    # popcorn / reve take a flat list of URLs. (reve/remix needs >= 2 images,
    # so it is not usable here with a single reference.)
    args = {
        "prompt": prompt,
        "num_images": NUM_IMAGES,
        "aspect_ratio": ASPECT_RATIO,
        "image_urls": [image_url],
    }
    if "popcorn" in model:
        args["resolution"] = os.environ.get("HF_RESOLUTION", "1600p")
    return args


def upload_reference(hf, src: Path) -> str:
    """Upload the reference image and return its public URL.

    hf.upload_file() cannot be used: the presign endpoint signs an
    `x-amz-tagging: retention=temporary` header and returns it in
    `upload_headers`, but the SDK sends only Content-Type, so S3 answers
    403 SignatureDoesNotMatch every time. Send the headers the API gave us.
    """
    import mimetypes
    import httpx

    content_type = mimetypes.guess_type(str(src))[0] or "image/png"
    response = hf.sync_client._transport.request(
        "POST", "/files/generate-upload-url", json={"content_type": content_type})
    payload = response.json()
    headers = payload.get("upload_headers") or {"Content-Type": content_type}
    put = httpx.put(payload["upload_url"], content=src.read_bytes(),
                    headers=headers, timeout=180)
    put.raise_for_status()
    return payload["public_url"]


def run_model(hf, model: str, prompt: str, image_url: str):
    """Submit to one model and wait for it. Returns a result dict, or None."""
    from higgsfield_client import Completed, DONE_STATUSES

    try:
        controller = hf.submit(model, arguments=build_arguments(model, prompt, image_url))
    except Exception as e:  # noqa: BLE001  -- 404 model_not_found, 423 blocked, 403 no credits
        warn(f"{model}: submit failed ({type(e).__name__}: {e})")
        return None
    log(f"{model}: request {controller.request_id} submitted")

    deadline = time.monotonic() + GEN_TIMEOUT
    try:
        while True:
            status = controller.status()
            if isinstance(status, DONE_STATUSES):
                break
            if time.monotonic() > deadline:
                warn(f"{model}: timed out after {GEN_TIMEOUT:.0f}s on {controller.request_id}")
                try:
                    controller.cancel()
                except Exception:  # noqa: BLE001
                    pass
                return None
            time.sleep(POLL_DELAY)
        if not isinstance(status, Completed):
            warn(f"{model}: ended as {type(status).__name__}")
            return None
        return controller.get()
    except Exception as e:  # noqa: BLE001
        warn(f"{model}: generation failed ({type(e).__name__}: {e})")
        return None


def generate(src: Path, prompt: str):
    """Return generated image bytes, or None. Never raises."""
    if not (os.environ.get("HF_KEY") or
            (os.environ.get("HF_API_KEY") and os.environ.get("HF_API_SECRET"))):
        warn("no Higgsfield credentials (set the HF_KEY secret)")
        return None
    try:
        import higgsfield_client as hf
    except Exception as e:  # noqa: BLE001
        warn(f"higgsfield-client not installed ({e})")
        return None

    log(f"models={MODELS}")
    log(f"prompt={prompt}")

    try:
        image_url = upload_reference(hf, src)
        log(f"uploaded reference -> {image_url}")
    except Exception as e:  # noqa: BLE001
        warn(f"reference upload failed ({type(e).__name__}: {e})")
        return None

    result = None
    for model in MODELS:
        result = run_model(hf, model, prompt, image_url)
        if result is not None:
            break
    if result is None:
        return None

    try:
        url = result["images"][0]["url"]
    except Exception as e:  # noqa: BLE001
        warn(f"unexpected response shape ({e}); got {str(result)[:200]}")
        return None

    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
    except Exception as e:  # noqa: BLE001
        warn(f"download failed ({e})")
        return None
    if len(data) < 10_000:
        warn(f"downloaded image suspiciously small ({len(data)} bytes)")
        return None
    log(f"generated {len(data)} bytes from {url}")
    return data


def write_generated(data: bytes, dest: Path) -> bool:
    """Write the generated bytes as an upright PNG. False if it looks wrong."""
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(data))
        im.load()
        if im.width > im.height:
            warn(f"generated image is landscape {im.size}, keeping the local image")
            return False
        im.convert("RGB").save(dest, format="PNG")
        log(f"wrote {dest.name} from Higgsfield ({im.width}x{im.height})")
        return True
    except Exception as e:  # noqa: BLE001
        warn(f"could not use the generated image ({type(e).__name__}: {e})")
        return False


def stamp(path, text):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(path).convert("RGB")
    if im.width > im.height:
        im = im.rotate(90, expand=True)
    W, H = im.size
    size = max(16, int(W * 0.082))
    font = None
    for name in ("Poppins-Bold.ttf", "Inter-Bold.ttf"):
        if (FONT_DIR / name).exists():
            font = ImageFont.truetype(str(FONT_DIR / name), size); break
    if font is None:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(im)
    max_w, lines, cur = W * 0.80, [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur: lines.append(cur)
            cur = word
    if cur: lines.append(cur)
    line_h, top = int(size * 1.18), int(H * 0.09)
    max_lw = max(d.textlength(l, font=font) for l in lines)
    overlay = Image.new("RGBA", im.size, (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    pad_x, pad_y = int(W * 0.045), int(size * 0.45)
    od.rounded_rectangle(
        [int((W-max_lw)/2-pad_x), top-pad_y, int((W+max_lw)/2+pad_x), top+line_h*len(lines)+pad_y],
        radius=int(size*0.35), fill=(0,0,0,110))
    im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(im)
    y = top
    for line in lines:
        x = (W - d.textlength(line, font=font)) / 2
        for dx, dy in ((-3,3),(3,3),(0,4),(3,-3),(-3,-3)):
            d.text((x+dx, y+dy), line, font=font, fill=(0,0,0))
        d.text((x, y), line, font=font, fill=(255,255,255))
        y += line_h
    im.save(path)
    print(f"[refresh_title_slide] stamped: {lines}")


def main():
    rng = random.SystemRandom()
    available = [(n, w) for n, w in POOL if (ASSETS / n).exists()]
    if not available:
        warn("no starting images found in assets/")
        return
    drawn = rng.choices([n for n, _ in available], weights=[w for _, w in available], k=1)[0]
    log(f"drew: {drawn}")

    # Put the local image in place first, so every later step can only improve
    # on a title slide that already exists.
    try:
        shutil.copyfile(ASSETS / drawn, TITLE_SLIDE)
    except Exception as e:  # noqa: BLE001
        warn(f"copy failed ({e})")
        return

    text_baked = drawn in TEXT_BAKED
    prompt = PROMPTS_TEXT_BAKED[drawn] if text_baked else PROMPT_BLANK

    data = generate(ASSETS / drawn, prompt)
    if data is None or not write_generated(data, TITLE_SLIDE):
        log(f"falling back to the local starting image {drawn}")
        # Surface it on the run summary. scripts/refresh_title.py fell back on
        # every run for two months without anyone noticing; a build that is
        # green but quietly un-generated should still be visible.
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning title=Title slide not regenerated::Higgsfield did not "
                  f"produce an image; using the committed {drawn} instead.")

    if text_baked:
        log("text-baked image, no stamping.")
        return
    hook = rng.choice(HOOKS)
    log(f"hook: {hook}")
    try:
        stamp(TITLE_SLIDE, hook)
    except Exception as e:  # noqa: BLE001
        warn(f"stamping failed ({e})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001  -- never fail the build
        print(f"[refresh_title_slide] WARN: unexpected error ({type(e).__name__}: {e})")
    sys.exit(0)
