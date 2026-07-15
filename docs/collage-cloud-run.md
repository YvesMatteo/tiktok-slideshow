# Collage slideshow — cloud run (GitHub Actions)

This runs the **collage / sticker** slideshow (the "Tools I use" look: lifestyle
background, big app-name heading, dark caption stickers, screenshot card) fully
in the cloud. No Mac and no Cowork needed.

Every run:

1. **Regenerates the title photo via Higgsfield** (`scripts/refresh_title.py`).
2. Builds the 7-slide deck (`scripts/make_slideshow_collage.py`).
3. Uploads the run as a downloadable **artifact**.
4. **Commits** the run + the refreshed title photo back into `runs_collage/`.

## One-time setup

1. **Add the Higgsfield secret.** In the repo: **Settings → Secrets and
   variables → Actions → New repository secret**.
   - Name: `HF_KEY`
   - Value: `your-api-key:your-api-secret` (get both from
     https://cloud.higgsfield.ai/ → API keys)

   Without this secret the run still works — it just reuses the committed
   `assets/title_inspo_bg.png` instead of generating a fresh one.

2. **Enable Actions** if prompted (Actions tab → "I understand my workflows").

## Run it

Actions tab → **Generate collage slideshow** → **Run workflow**.

When it finishes:

- Download the **artifact** (`collage-slideshow-<id>`) for `post.html` + slides, or
- Open the newest folder under `runs_collage/` in the repo (committed automatically).

## Notes

- **Title model:** `refresh_title.py` defaults to `bytedance/seedream/v4/text-to-image`
  on Higgsfield Cloud. Change it with the `HF_MODEL` env var in the workflow if
  you prefer another photoreal model. (The Cowork task uses `nano_banana_pro` via
  the MCP, which isn't exposed the same way through the public SDK.)
- **Never fails on the title:** if the key is missing, credits run out, or the API
  errors/timeouts/flags NSFW, the refresh step logs a warning and the build
  continues with the committed title photo.
- **Only apps with a screenshot** in `assets/screenshots/` are eligible.
- **Scheduling:** the workflow is manual-trigger only. To also run on a cron,
  uncomment the `schedule:` block in `.github/workflows/collage_slideshow.yml`
  (times are UTC).
- **Repo growth:** each run commits ~2 MB of slides into `runs_collage/`. If the
  repo gets large over time, prune old run folders, or switch to artifact-only by
  removing the "Commit run back to repo" step.
