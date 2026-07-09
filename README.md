# TikTok slideshow generator (checkvibe.dev)

Self-contained generator for the "5 apps my whole business runs on" TikTok /
Instagram slideshow. Produces six 3:4 (1080×1440) slides plus a caption, a
self-contained `post.html`, and importer helpers.

The folder is **portable**: the background photos are bundled under `photos/`,
and every path resolves relative to the script, so it runs anywhere (your Mac,
CI, a cloud runner) with no separately-connected folder required.

## Layout

```
tiktok-slideshow/
├── scripts/
│   ├── make_slideshow.py   # entry point
│   └── slideshow.py        # rendering
├── assets/
│   ├── logos/              # app logo tiles
│   ├── fonts/
│   ├── copy_bank.json      # captions / titles / tactics
│   ├── title_slide.png     # current title image (fallback if not regenerated)
│   ├── approved_photos.txt # vetted background filenames
│   └── photo_brightness.json
├── photos/                 # bundled background photos (was checkvibe-Marketing/pinterest_final)
├── runs/                   # generated output (git-ignored)
├── docs/scheduled-task.md  # the recurring-run spec (Cowork task)
└── .github/workflows/slideshow.yml
```

## Run locally

Only needs Pillow (`pip install Pillow`):

```
python3 scripts/make_slideshow.py
```

Output lands in a new timestamped folder under `runs/`. Open `post.html`.

You can override the photos directory with a positional arg:
`python3 scripts/make_slideshow.py /path/to/photos`.

## Run on a schedule

There are two ways to run this on a schedule. They differ in one important way:
**only the Cowork task can regenerate the title slide via Higgsfield.**

### Option A — Cowork scheduled task (runs on your Mac, includes Higgsfield)

This is the original setup. Cowork has the Higgsfield connector, so each run
generates a fresh title slide before building the deck. See
[`docs/scheduled-task.md`](docs/scheduled-task.md) for the exact per-run spec,
and use the Cowork prompt provided with this repo to (re)create the task.

### Option B — GitHub Actions (runs in the cloud)

`.github/workflows/slideshow.yml` runs `make_slideshow.py` on a cron schedule
and uploads the run as a build artifact. To enable it:

1. Push this repo to GitHub (already done: `YvesMatteo/tiktok-slideshow`).
2. In the repo, open **Actions** and enable workflows if prompted.
3. Adjust the `cron:` line in the workflow (times are **UTC**).
4. Trigger a test run from the Actions tab (**Run workflow**), then download the
   artifact to get `post.html` and the slides.

**Higgsfield caveat:** GitHub Actions has no MCP access, so the workflow **reuses
the committed `assets/title_slide.png`** — it does not generate a fresh title
slide each run. To refresh it in CI you'd add a step that calls the Higgsfield
API with a repo secret (`HIGGSFIELD_API_KEY`); a commented placeholder marks
where. Until then, refresh `title_slide.png` periodically via Cowork (Option A)
or commit a new one by hand.

## Notes

- Because bundled `photos/` is preferred, local runs use the bundled set. If you
  add new photos to your source folder, re-sync them into `photos/` and commit.
- Slide 1 rotates among Claude / Notion / Framer / Higgsfield; checkvibe.dev is
  always slide 2; slides 3–5 are drawn from a rotating app pool.
