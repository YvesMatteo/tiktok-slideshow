---
name: tiktok-slideshow
description: >-
  Generate TikTok/Instagram-style slideshows that promote apps and tools — the
  "5 apps that run my entire business" format. Use when the user wants to create
  a TikTok slideshow, an app/tool recommendation slideshow, a "X apps I use"
  slideshow, or social slideshow images built from background photos with logo
  tiles and captions. Produces six 3:4 (1080x1440) slides plus a post caption
  with a title and 5 hashtags.
---

# TikTok Slideshow Generator

Creates a 6-slide vertical slideshow: a title slide plus five app slides, each a
darkened background photo with a rounded-square logo tile, a numbered heading,
and a short first-person caption. Slide 1 is always **Claude**, slide 2 is always
**CheckVibe**; slides 3-5 are picked at random from the other apps. Every run
also produces a `caption.txt` with a post title, caption, and 5 hashtags.

## Fastest path — generate one now

```
python3 scripts/make_slideshow.py
```

This needs only Pillow (pre-installed). It writes a timestamped folder under
`runs/`, e.g. `runs/2026-05-24_0800/` containing `slide_00.jpg` … `slide_05.jpg`
(3:4, 1080x1440) and `caption.txt`. It prints the output path, app order, title,
caption, and hashtags. Pass a photos directory as the first argument to override
the default (`../startup-grind`).

When run interactively, after the script finishes you should **open the slides,
check every caption is legible over its background**, and report the output
folder, title, caption, and hashtags to the user. The compositor darkens photos
with a continuous gradient and an adaptive boost, so text stays readable, but a
quick visual check is still worthwhile.

## How it works

- **Backgrounds** — `assets/approved_photos.txt` is a hand-vetted pool of clean
  workspace photos (no text/watermarks, not weird, dark or darkenable).
  `assets/title_photos.txt` is a smaller pool of strong hero shots used only for
  the title slide. Photos themselves live in the sibling `startup-grind/` folder.
- **Logos** — `assets/logos/*.png` are pre-built rounded-square app-icon tiles
  (Claude, CheckVibe, Cursor, PostHog, Supabase, Notion, Vercel, Figma, GitHub).
- **Copy** — `assets/copy_bank.json` holds 3 caption variants per app, title-slide
  variants, post-caption variants, and a hashtag pool. Each run rotates a fresh
  combination.
- **Compositor** — `scripts/slideshow.py` renders each slide: cover-crop to 3:4,
  darken, apply a top-down dark scrim sized to the text block, adaptively boost
  if the text region is still bright, then draw the logo (with soft shadow) and
  text (with soft shadow).

## Customizing

- **Add an app**: drop a logo tile in `assets/logos/<key>.png` and add an entry
  under `apps` in `copy_bank.json`, then add `<key>` to `rotating_pool`.
- **Change captions / hashtags / titles**: edit `copy_bank.json`.
- **Add background photos**: append filenames to `assets/approved_photos.txt`
  (vet them first — no text or watermarks on the image).
- **Rebuild logos**: tiles are app-icon style — brand color background, white or
  brand-color glyph, ~22.5% corner radius. Brand glyphs came from the
  `simple-icons` package; the CheckVibe tile is cropped from the user's logo
  asset onto a `#0B0B0B` tile.

## Output

Each `runs/<timestamp>/` folder contains:
- `slide_00.jpg` … `slide_05.jpg` — the six 3:4 slides
- `caption.txt` — title + the full long caption (with hashtags appended)
- `post.zip` — all 6 slides zipped, one-click desktop download
- `post.html` — **the "post sheet"** and the primary deliverable:
  - all 6 slides are **base64-embedded** inside the file, so it is
    fully self-contained — AirDropping just this one HTML to a phone
    is enough; no sibling files needed.
  - Mobile: a **"Save all 6 to Photos"** button uses the Web Share
    API to drop every slide into the camera roll in one tap; long-pressing
    any thumbnail also offers "Save to Photos".
  - Desktop: same Copy and ZIP buttons.
  - The textarea pre-loads the **long caption** (hook + numbered app
    list with taglines + CTA + 5 hashtags), tuned for the TikTok
    algorithm — copy-and-paste ready.
  - Native posting beats auto-posting on the TikTok algo, so this
    "post sheet" workflow is intentional. Present `post.html` first.

## Sending to your phone

Two ways the files get from this generator to your iPhone:

**Mac → iCloud Photos → iPhone (recommended).** Each run produces an
`import-to-photos.command` script that, when double-clicked, imports the 6
slides into the macOS Photos app via AppleScript. If iCloud Photos is on,
they sync to your iPhone within seconds. The "Save to Mac Photos" button
in `post.html` downloads `import-to-photos.zip` (the script is wrapped in a
zip so the +x bit survives the browser download — macOS Archive Utility
unzips automatically). First-time GateKeeper prompt: right-click the
unzipped `.command` → Open. The script bakes absolute host paths via
`_host_path()`, so it works regardless of where it's executed from
(including when the runner itself ran inside the Cowork sandbox).

**iCloud Drive (post.html only).**



Each run also copies `post.html` to the first cloud-synced folder it can find,
so the file shows up on your phone seconds later:

1. **iCloud Drive** — `~/Library/Mobile Documents/com~apple~CloudDocs/TikTokSlideshows/`
   (default on macOS — open the Files app on iPhone → iCloud Drive → TikTokSlideshows)
2. **Dropbox** — `~/Dropbox/TikTokSlideshows/`
3. **Google Drive** — `~/Library/CloudStorage/GoogleDrive-MyDrive/TikTokSlideshows/`
4. **Custom** — set the `SLIDESHOW_SHARE_DIR` environment variable to any
   absolute path and post.html files land there with timestamped names.

Open the mirrored file in mobile Safari and the "Save all 6 to Photos" +
"Copy caption" buttons work natively against the embedded data.

## Title slide

`assets/title_slide.png` is the first slide of every run, used as a
`type:'static'` slide — no compositing, just cover-cropped to 3:4 with
text baked in. The scheduled task **regenerates this file via Higgsfield
(`nano_banana_pro`)** before each run, so the title varies each time
while preserving the vibe, person, colours, and the headline text. The
original reference image is the cached upload `media_id
21d153bf-5856-4f47-a9e6-4cd680106a38` (Higgsfield CDN), produced from
`/Users/yvesromano/checkvibe-Marketing/start_always.png`. Manual runs of
`make_slideshow.py` skip the regen and use whatever `title_slide.png`
exists.

## App lineup

- **Slide 1** is always Claude.
- **Slide 2** alternates: odd-numbered runs use SiteJourney (and push
  CheckVibe to slide 3); even-numbered runs skip SiteJourney and put
  CheckVibe in slide 2.
- Remaining slots (5 apps total) are random samples from `rotating_pool`
  in `copy_bank.json`.
- Parity is decided by counting existing folders in `runs/` — so the first
  run after install includes SiteJourney, the next skips it, and so on.

## Caption strategy

Captions rotate from `caption_templates` in `copy_bank.json`. Each template
has hook → intro → `{app_list}` placeholder → CTA → `{hashtags}` placeholder.
The runner builds `{app_list}` by joining each picked app's short `tagline`
field. Edit taglines or templates in `copy_bank.json` to tune voice.
