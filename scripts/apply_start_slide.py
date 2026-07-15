#!/usr/bin/env python3
"""Swap a Higgsfield-varied starting image in as slide_00 of an MCP slideshow run.

Additive wrapper for the MCP-servers slideshow (make_mcp_slideshow.py). The
generator writes a run folder under runs_mcp/ containing slide_00.jpg ..
slide_05.jpg, caption.txt, post.zip and post.html. The scheduled task's Step 1.5
generates a fresh lifestyle starting image via Higgsfield and calls this script
to replace the synthetic title slide with it, then rebuild the share bundle.

Usage:
    python3 apply_start_slide.py --run <RUN_DIR> --start-image <downloaded.png>

- <RUN_DIR> is the folder printed by make_mcp_slideshow.py (under runs_mcp/).
- <downloaded.png> is the Higgsfield result PNG already downloaded to the sandbox.

Overwrites slide_00.jpg (cover-cropped to 1080x1440, quality 92) and rebuilds
post.zip + post.html so the embedded thumbnails and ZIP reflect the new slide.
Does NOT modify the generator, copy bank, plates, or fonts.
"""
import argparse
import base64
import html
import os
import re
import sys
import zipfile
from datetime import datetime

from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from mcp_slideshow import cover_crop, W, H  # reuse generator's exact crop + dims


def _b64(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def _slide_files(run_dir):
    files = sorted(
        f for f in os.listdir(run_dir)
        if re.fullmatch(r'slide_\d{2}\.jpg', f)
    )
    if not files:
        raise SystemExit(f"[apply_start_slide] no slide_NN.jpg files in {run_dir}")
    return files


def _rebuild_zip(run_dir, slide_files):
    zip_path = os.path.join(run_dir, 'post.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in slide_files:
            z.write(os.path.join(run_dir, f), f)


def _rebuild_html(run_dir, slide_files):
    """Re-embed the (now updated) slide thumbnails into the existing post.html.

    We edit the existing page in place rather than regenerate the whole
    template, so the title / caption / order text stay exactly as the generator
    wrote them. Only the base64 thumbnails in the .grid are refreshed.
    """
    html_path = os.path.join(run_dir, 'post.html')
    if not os.path.exists(html_path):
        return  # nothing to rebuild; generator may have skipped it
    with open(html_path, 'r') as fp:
        page = fp.read()

    thumbs = ''.join(
        f'<img class="slide" data-name="{f}" '
        f'src="data:image/jpeg;base64,{_b64(os.path.join(run_dir, f))}">'
        for f in slide_files)

    # Replace the contents of <div class="grid"> ... </div> with fresh thumbs.
    new_page, n = re.subn(
        r'(<div class="grid">)(.*?)(</div>)',
        lambda m: m.group(1) + thumbs + m.group(3),
        page,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        # Fallback: no grid found (unexpected template) — leave page untouched.
        return
    with open(html_path, 'w') as fp:
        fp.write(new_page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True, help='run folder under runs_mcp/')
    ap.add_argument('--start-image', required=True,
                    help='Higgsfield-varied starting image (PNG) to use as slide_00')
    args = ap.parse_args()

    run_dir = os.path.abspath(args.run)
    if not os.path.isdir(run_dir):
        raise SystemExit(f"[apply_start_slide] run folder not found: {run_dir}")
    if not os.path.isfile(args.start_image):
        raise SystemExit(f"[apply_start_slide] start image not found: {args.start_image}")

    slide0 = os.path.join(run_dir, 'slide_00.jpg')

    # Cover-crop the starting image to 1080x1440 and overwrite slide_00.jpg.
    im = Image.open(args.start_image).convert('RGB')
    im = cover_crop(im, W, H)
    im.save(slide0, quality=92)

    slide_files = _slide_files(run_dir)
    _rebuild_zip(run_dir, slide_files)
    _rebuild_html(run_dir, slide_files)

    print(f"[apply_start_slide] OK -> slide_00.jpg replaced from "
          f"{os.path.basename(args.start_image)}; post.zip + post.html rebuilt "
          f"({len(slide_files)} slides) at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == '__main__':
    main()
