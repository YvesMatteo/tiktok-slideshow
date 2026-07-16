#!/usr/bin/env python3
"""Autonomous TikTok slideshow generator.

Each run: picks a random vetted background photo for every slide, keeps
Claude (slide 1) and CheckVibe (slide 2) fixed, randomly picks 3 more apps
for slides 3-5, rotates captions from the copy bank, composes six 3:4
slides, and writes a caption.txt (title + post caption + 5 hashtags).

Usage:  python3 make_slideshow.py [photos_dir]
Only requires Pillow. Logos are pre-built; photos come from the vetted list.
"""
import base64
import html
import json
import os
import random
import shutil
import sys
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from slideshow import render_slideshow

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(SKILL_DIR, 'assets')
LOGOS = os.path.join(ASSETS, 'logos')
RUNS = os.path.join(SKILL_DIR, 'runs')

# remaining positional arg overrides the photos dir
_args = sys.argv[1:]
_positional = [a for a in _args if not a.startswith('--')]


def _detect_photos_dir():
    """Photos live in pinterest_final — a separately-connected workspace
    folder under checkvibe-Marketing. Check the repo-bundled photos/ folder
    first (self-contained / headless runs), then the host path (Mac native
    runs), then the Cowork sandbox mount."""
    import glob as _glob
    bundled_path = os.path.join(SKILL_DIR, 'photos')
    if os.path.isdir(bundled_path):
        return bundled_path
    host_path = '/Users/yvesromano/checkvibe-Marketing/pinterest_final'
    if os.path.isdir(host_path):
        return host_path
    for p in _glob.glob('/sessions/*/mnt/pinterest_final'):
        if os.path.isdir(p):
            return p
    return host_path


# override via first positional arg, else auto-detect
PHOTOS = _positional[0] if _positional else _detect_photos_dir()


def _lines(path):
    with open(path) as f:
        return [ln.strip() for ln in f if ln.strip()]


def _mean_brightness(path, size=64):
    """Mean luminance (0-255) of an image, downscaled for speed."""
    from PIL import Image, ImageStat
    im = Image.open(path).convert('L')
    im.thumbnail((size, size))
    return ImageStat.Stat(im).mean[0]


def pick_matching_photos(approved, photos_dir, title_image, n):
    """Pick n background photos whose overall brightness matches the title
    slide — a dark title slide gets dark backgrounds, a bright one gets
    bright backgrounds. Falls back to pure random on any failure.
    Returns (photos, note) where note describes what happened."""
    try:
        target = _mean_brightness(title_image)
    except Exception:
        return random.sample(approved, n), 'random (no title slide)'
    cache_path = os.path.join(ASSETS, 'photo_brightness.json')
    try:
        with open(cache_path) as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    changed = False
    scores = []
    for name in approved:
        b = cache.get(name)
        if b is None:
            try:
                b = round(_mean_brightness(os.path.join(photos_dir, name)), 2)
            except Exception:
                continue
            cache[name] = b
            changed = True
        scores.append((abs(b - target), name))
    if changed:
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache, f, indent=1)
        except Exception:
            pass
    if len(scores) < n:
        return random.sample(approved, n), 'random (too few scored photos)'
    scores.sort()
    # keep the closest chunk (at least 3x n) so runs still vary
    k = min(len(scores), max(n * 3, len(scores) // 3))
    pool = [name for _, name in scores[:k]]
    note = (f'matched to title (target {target:.0f}/255, '
            f'pool {k}/{len(scores)})')
    return random.sample(pool, n), note


POST_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__ — Slideshow Post</title>
<style>
  :root { --bg:#0b0b0b; --panel:#161616; --fg:#f2f2f2; --accent:#80ee64; --muted:#888; }
  *{box-sizing:border-box}
  body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:var(--bg);color:var(--fg);padding:24px;
       padding-bottom:max(24px,env(safe-area-inset-bottom))}
  .wrap{max-width:880px;margin:0 auto}
  h1{margin:0 0 4px;font-size:22px;font-weight:700}
  .order{color:var(--muted);font-size:13px;margin-bottom:20px}
  .card{background:var(--panel);border-radius:14px;padding:18px;margin-bottom:14px}
  .label{font-size:11px;letter-spacing:1.2px;text-transform:uppercase;
         color:var(--muted);margin-bottom:8px}
  .hint{color:var(--muted);font-size:12px;margin-top:8px;line-height:1.5}
  textarea{width:100%;min-height:200px;background:transparent;color:var(--fg);
           border:1px solid #2a2a2a;border-radius:8px;padding:12px;
           font:15px/1.5 inherit;resize:vertical}
  .row{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
  button,.btn{background:var(--accent);color:#000;border:none;padding:14px 22px;
              font-weight:700;border-radius:8px;cursor:pointer;font-size:15px;
              text-decoration:none;display:inline-flex;align-items:center;
              justify-content:center;gap:6px;min-height:48px}
  button.ghost,.btn.ghost{background:#2a2a2a;color:var(--fg)}
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}
  .grid img{width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:8px;
            display:block;-webkit-touch-callout:default}
  .ok{background:#fff !important;color:#000 !important}
  .meta{color:var(--muted);font-size:12px;margin-top:14px}
  @media (max-width:600px){
    body{padding:16px}
    h1{font-size:19px}
    .grid{grid-template-columns:repeat(2,1fr)}
    button,.btn{width:100%;padding:16px 18px}
    textarea{min-height:240px;font-size:14px}
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>__TITLE__</h1>
  <div class="order">Generated __GENERATED__ &nbsp;•&nbsp; __ORDER__</div>

  <div class="card">
    <div class="label">Caption + hashtags</div>
    <textarea id="caption" readonly>__FULL_CAPTION__</textarea>
    <div class="row">
      <button onclick="copyCap(this)">Copy caption + hashtags</button>
    </div>
  </div>

  <div class="card">
    <div class="label">6 Slides</div>
    <div class="grid">__THUMBS__</div>
    <div class="row">
      <button onclick="airdrop(this)">AirDrop 6 slides</button>
      <button class="ghost" onclick="saveAll(this)">Save all 6 to Photos</button>
      <a class="btn" href="file://__RUN_FOLDER__/" target="_blank">Show in Finder</a>
      <a class="btn ghost" href="import-to-photos.zip" download>Save to Mac Photos (ZIP)</a>
      <a class="btn ghost" href="post.zip" download>Download ZIP</a>
    </div>
    <div class="hint">
      <b>iPhone / Android:</b> tap "Save all 6 to Photos" → Save Images in the
      share sheet. Or long-press any image.<br>
      <b>Mac → iPhone via iCloud Photos (recommended):</b> tap
      <b>Show in Finder</b> to open this run's folder, then double-click
      <code>import-to-photos.command</code> in the folder that opens.
      Imports to macOS Photos; iCloud Photos syncs to your iPhone in seconds.
      No download, no GateKeeper prompt.<br>
      <b>Alternative (download flow):</b> tap "Save to Mac Photos (ZIP)" —
      macOS unzips automatically — double-click the unzipped
      <code>.command</code> (first time only: right-click → Open).<br>
      <b>Slides quick download:</b> use the ZIP button.
    </div>
  </div>

  <div class="meta">Generated __GENERATED__</div>
</div>
<script>
function flash(btn, msg) {
  const o = btn.textContent;
  btn.textContent = msg; btn.classList.add('ok');
  setTimeout(() => { btn.textContent = o; btn.classList.remove('ok'); }, 1800);
}
function copyCap(btn) {
  const el = document.getElementById('caption');
  el.select(); el.setSelectionRange(0, 99999);
  const done = () => flash(btn, '✓ Copied');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(el.value).then(done,
      () => { try{document.execCommand('copy');done();}catch(e){alert('Copy failed: '+e.message)} });
  } else { try{document.execCommand('copy');done();}catch(e){alert('Copy failed: '+e.message)} }
}
async function collectFiles() {
  const files = [];
  for (const img of [...document.querySelectorAll('.slide')]) {
    const blob = await (await fetch(img.src)).blob();
    files.push(new File([blob], img.dataset.name, {type: 'image/jpeg'}));
  }
  return files;
}
async function airdrop(btn) {
  btn.disabled = true; const o = btn.textContent; btn.textContent = 'Preparing...';
  try {
    const files = await collectFiles();
    btn.textContent = o; btn.disabled = false;
    if (navigator.canShare && navigator.canShare({files})) {
      try {
        await navigator.share({files, title: 'Slideshow'});
        flash(btn, '\u2713 Shared');
      } catch (e) { if (e.name !== 'AbortError') throw e; }
      return;
    }
    await saveAll(btn);
    alert('This browser can\\'t open the share sheet directly.\\n' +
          'The 6 slides were saved/downloaded \u2014 select them in Finder ' +
          'and use Share \u2192 AirDrop, or open this page in Safari to AirDrop straight from here.');
  } catch (e) {
    btn.disabled = false; btn.textContent = o;
    alert('AirDrop failed: ' + e.message);
  }
}
async function saveAll(btn) {
  const imgs = [...document.querySelectorAll('.slide')];
  btn.disabled = true; const o = btn.textContent; btn.textContent = 'Preparing...';
  try {
    const files = [];
    for (const img of imgs) {
      const blob = await (await fetch(img.src)).blob();
      files.push(new File([blob], img.dataset.name, {type: 'image/jpeg'}));
    }
    btn.textContent = o; btn.disabled = false;
    if (navigator.canShare && navigator.canShare({files})) {
      try { await navigator.share({files, title: 'Slideshow'}); flash(btn, '✓ Shared'); return; }
      catch (e) { if (e.name === 'AbortError') return; }
    }
    // fallback: trigger 6 downloads
    for (const f of files) {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(f); a.download = f.name;
      document.body.appendChild(a); a.click(); a.remove();
      await new Promise(r => setTimeout(r, 150));
    }
    flash(btn, '✓ Downloaded 6');
  } catch (e) {
    btn.disabled = false; btn.textContent = o;
    alert('Save failed: ' + e.message);
  }
}
</script>
</body>
</html>
"""


def _b64_jpg(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')


def _host_path(p):
    """If we're running inside the Cowork sandbox, translate
    /sessions/<sess>/mnt/foo/... back to /Users/<host_user>/foo/... so paths
    baked into shell scripts work on the user's actual Mac. No-op on macOS."""
    if '/sessions/' in p and '/mnt/' in p:
        host_home = os.environ.get('HOST_HOME', '/Users/yvesromano')
        parts = p.split('/mnt/', 1)
        if len(parts) == 2:
            return f"{host_home.rstrip('/')}/{parts[1]}"
    return p


def write_photos_importer(out_dir, slide_files):
    """Generate a double-clickable .command file that imports all six slides
    into the macOS Photos app via AppleScript. With iCloud Photos enabled,
    they'll appear on the iPhone automatically a few seconds later."""
    abs_paths = [_host_path(os.path.abspath(os.path.join(out_dir, f)))
                 for f in slide_files]
    file_list = ', '.join(f'POSIX file "{p}"' for p in abs_paths)
    content = f"""#!/bin/zsh
# Import this run's slides into the macOS Photos app.
# iCloud Photos will sync them to your iPhone automatically if enabled.
echo "Importing {len(slide_files)} slides into Photos..."
osascript <<'APPLESCRIPT'
tell application "Photos"
  activate
  import {{{file_list}}}
end tell
APPLESCRIPT
echo ""
echo "Done. Photos has opened. iCloud will sync to your iPhone shortly."
echo "(closing in 3 seconds)"
sleep 3
"""
    cmd_path = os.path.join(out_dir, 'import-to-photos.command')
    with open(cmd_path, 'w') as f:
        f.write(content)
    os.chmod(cmd_path, 0o755)
    # Wrap the .command in a zip so the exec bit survives a browser download.
    # macOS Archive Utility honours the Unix mode stored in the zip entry.
    zip_path = os.path.join(out_dir, 'import-to-photos.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        zi = zipfile.ZipInfo('import-to-photos.command')
        zi.external_attr = (0o755 & 0xFFFF) << 16
        zi.create_system = 3  # 3 = Unix, so the stored mode is honoured
        with open(cmd_path, 'rb') as fp:
            z.writestr(zi, fp.read())
    return cmd_path


def _mirror_post_html(post_html_path, stamp):
    """Copy post.html into the first cloud-synced folder we can find so the
    iPhone Files app (or Dropbox/Drive app) picks it up automatically.
    Returns the destination path, or None if no synced folder is available."""
    if not os.path.exists(post_html_path):
        return None
    home = os.path.expanduser('~')
    override = os.environ.get('SLIDESHOW_SHARE_DIR')
    parents = []
    if override:
        parents.append(override)
    parents += [
        os.path.join(home, 'Library', 'Mobile Documents',
                     'com~apple~CloudDocs'),
        os.path.join(home, 'Dropbox'),
        os.path.join(home, 'Library', 'CloudStorage',
                     'GoogleDrive-MyDrive'),
    ]
    for parent in parents:
        if not os.path.isdir(parent):
            continue
        target_dir = (parent if override
                      else os.path.join(parent, 'TikTokSlideshows'))
        try:
            os.makedirs(target_dir, exist_ok=True)
            dest = os.path.join(target_dir, f'post_{stamp}.html')
            shutil.copy2(post_html_path, dest)
            return dest
        except Exception:
            continue
    return None


def write_post_page(out_dir, title, full_caption, app_order, slide_files):
    # zip the 6 slides for desktop one-click download
    zip_path = os.path.join(out_dir, 'post.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in slide_files:
            z.write(os.path.join(out_dir, f), f)
    # embed each slide as a base64 data URI so post.html is a single
    # self-contained file — AirDrop it to your phone and "Save all to
    # Photos" works without any sibling files
    thumbs = ''.join(
        f'<img class="slide" data-name="{f}" alt="{f}" '
        f'src="data:image/jpeg;base64,{_b64_jpg(os.path.join(out_dir, f))}">'
        for f in slide_files)
    # double-clickable script that imports the 6 slides into Mac Photos
    write_photos_importer(out_dir, slide_files)

    run_folder_host = _host_path(os.path.abspath(out_dir))
    page = (POST_HTML
            .replace('__TITLE__', html.escape(title))
            .replace('__ORDER__', html.escape(app_order))
            .replace('__FULL_CAPTION__', html.escape(full_caption))
            .replace('__THUMBS__', thumbs)
            .replace('__RUN_FOLDER__', run_folder_host)
            .replace('__GENERATED__',
                     datetime.now().strftime('%Y-%m-%d %H:%M')))
    with open(os.path.join(out_dir, 'post.html'), 'w') as fp:
        fp.write(page)


def main():
    bank = json.load(open(os.path.join(ASSETS, 'copy_bank.json')))
    approved = _lines(os.path.join(ASSETS, 'approved_photos.txt'))

    # ---- pick apps ----
    # slide 1 rotates among the first_slide_pool (claude/notion/framer/
    # higgsfield); slide 2 is always CheckVibe; slides 3-5 are 3 distinct
    # apps drawn from the rotating_pool, never repeating slide 1.
    first = random.choice(bank['first_slide_pool'])
    second = bank['second_slide']
    pool = [a for a in bank['rotating_pool'] if a not in (first, second)]
    rest = random.sample(pool, max(0, 5 - 2))
    apps = [first, second] + rest
    variant = f"slide1={bank['apps'][first]['name']}"

    # ---- pick 5 distinct photos for app slides (title is the static
    # Higgsfield-rendered image at assets/title_slide.png), preferring
    # photos whose brightness matches the title slide's mood ----
    title_image = os.path.join(ASSETS, 'title_slide.png')
    app_photos, tone_note = pick_matching_photos(
        approved, os.path.abspath(PHOTOS), title_image, len(apps))

    # ---- build slide config ----
    # 50% of runs: tease the lineup with a small row of the 5 app icons
    # composited near the bottom of the title slide
    show_preview = random.random() < 0.5
    config = [{'type': 'static', 'image': title_image,
               'preview_logos': ([bank['apps'][k]['logo'] for k in apps]
                                 if show_preview else None)}]
    # five distinct layout combinations cycle through the 5 app slides so
    # the logo + text never sits in the same spot twice in a row
    layouts = [('top', 'inline'), ('middle', 'stacked'), ('bottom', 'inline'),
               ('top', 'stacked'), ('middle', 'inline')]
    random.shuffle(layouts)
    for i, key in enumerate(apps):
        a = bank['apps'][key]
        pos, sub = layouts[i]
        config.append({'type': 'app', 'photo': app_photos[i], 'logo': a['logo'],
                       'num': i + 1, 'name': a['name'],
                       'body': random.choice(a['copy']),
                       'pos': pos, 'sub': sub})

    # ---- render ----
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    out_dir = os.path.join(RUNS, stamp)
    render_slideshow(config, os.path.abspath(PHOTOS), LOGOS, out_dir)

    # ---- long algorithm-optimized caption ----
    title = random.choice(bank['slideshow_title'])
    tags = ' '.join(random.sample(bank['hashtags'], 5))
    order = ' -> '.join(['title'] + [bank['apps'][k]['name'] for k in apps])
    app_lines = [
        f"{i+1}. {bank['apps'][k]['name']}: {bank['apps'][k]['tagline']}"
        for i, k in enumerate(apps)
    ]
    app_list = '\n'.join(app_lines)
    template = random.choice(bank['caption_templates'])
    full_caption = (template
                    .replace('{app_list}', app_list)
                    .replace('{hashtags}', tags))
    with open(os.path.join(out_dir, 'caption.txt'), 'w') as f:
        f.write(f"TITLE: {title}\n\nCAPTION:\n{full_caption}\n\n"
                f"---\nSlides: {order}\n"
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # ---- one-click post sheet: thumbnails + copy button + zip download ----
    slide_files = [f"slide_{i:02d}.jpg" for i in range(len(config))]
    write_post_page(out_dir, title, full_caption, order, slide_files)

    # ---- mirror post.html to a cloud-synced folder for phone access ----
    mirror = _mirror_post_html(os.path.join(out_dir, 'post.html'), stamp)

    now = datetime.now()
    print(f"GENERATED AT: {now.strftime('%H:%M  %a %b %d')}")
    print(f"FIRST SLIDE: {variant}")
    print(f"TITLE PREVIEW ICONS: {'yes' if show_preview else 'no'}")
    print(f"PHOTO TONE: {tone_note}")
    print(f"Slideshow ready: {out_dir}")
    print(f"  Open post.html — single self-contained file with thumbs,")
    print(f"  Copy-caption button, and Save-all-to-Photos button.")
    if mirror:
        print(f"  Mirrored to: {mirror}")
        print(f"  (open this on your phone via iCloud Files / Dropbox / Drive)")
    else:
        print(f"  No cloud-synced folder found — to enable phone access, "
              f"set SLIDESHOW_SHARE_DIR or create an iCloud Drive folder.")
    print(f"  Apps: {order}")
    print(f"  Title: {title}")
    print(f"  Caption length: {len(full_caption)} chars")
    print(f"  Hashtags: {tags}")
    return out_dir


if __name__ == '__main__':
    main()
