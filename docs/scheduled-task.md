# Scheduled task spec — TikTok slideshow (checkvibe.dev)

This is the per-run specification for the recurring "generate a fresh TikTok
slideshow" task. It is written for **Cowork**, which has the Higgsfield
connector. It mirrors the original task, adapted for the now-portable folder
(photos are bundled under `photos/`, so no separately-connected folder is
needed and no fallback photos path is required).

Paths below assume the repo lives at `pinterest-scraper/tiktok-slideshow/`.
Translate host paths to the bash sandbox mount as needed.

---

## Step 1 — regenerate the title slide via Higgsfield (every run)

Use the Higgsfield MCP `generate_image`:

- model: `nano_banana_pro`
- aspect_ratio: `3:4`
- resolution: `2k`
- count: `1`
- medias: **randomly pick ONE** of the three starting images using these weights
  — `start_18yo.png` 50%, each `start_always` image 25%. Decide with a real
  random draw, e.g.
  `python3 -c "import random;print(random.choices(['18yo','a1','a3'],weights=[50,25,25])[0])"`.
  Pass the chosen image as `[{"role":"image","value":"<media_id>"}]`.
  **The prompt depends on which image was picked.**
    - `start_always.png`   (25%) → media_id `945e5643-26e1-4a6e-a3d4-d6f469f44e04` → **prompt A**
    - `start_always_3.png` (25%) → media_id `c93aeed2-beec-4109-9dc7-5138ffac4b6d` → **prompt A**
    - `start_18yo.png`     (50%) → no cached id: upload `assets/start_18yo.png`
      via `media_upload` → curl PUT → `media_confirm`, then use the fresh
      media_id → **prompt B**
- **prompt A** (start_always images): `Either Same person or Different attractive about 25 year old person, similar outfit, same overall color palette, exactly the same text but put it very slightly in a different position, clean and same aesthetic. Different background, different camera angle. Photographic.`
- **prompt B** (start_18yo.png): `Keep the same young man seen from behind and the same dark, moody aesthetic and color palette. Keep the text exactly the same, always written across his bare back and only where his back is, in the same clean white type so it stands out clearly. Subtly change the rest of the scene: different room details, slightly different lighting and camera angle. Photographic, realistic.`
- If a cached media_id is expired/invalid, re-upload the matching file from
  `assets/<that filename>` via `media_upload` → curl PUT → `media_confirm`, then
  use the fresh media_id.

Poll `job_display` until status is `completed`, then download `results.rawUrl`:

```
curl -s -o <repo>/tiktok-slideshow/assets/title_slide.png "<rawUrl>"
```

If any Higgsfield step fails (credits low, media_id expired, etc.) **skip** the
title regeneration and proceed — the slideshow reuses the previous
`title_slide.png`. Do not error out.

## Step 2 — run the slideshow generator

```
python3 pinterest-scraper/tiktok-slideshow/scripts/make_slideshow.py
```

Only needs Pillow (pre-installed in Cowork). Photos are auto-detected from the
bundled `photos/` folder, so **no positional photos argument is needed**. It
writes a new timestamped folder under `runs/` containing six 3:4 slides,
`caption.txt`, `post.html` (six slides base64-embedded, with Copy / Show in
Finder / Save to Mac Photos buttons), `post.zip`, and importer helpers.

App selection: slide 1 rotates among Claude / Notion / Framer / Higgsfield,
checkvibe.dev is always slide 2, and slides 3–5 are three distinct apps from the
rotating pool (Vercel, Obsidian, Antigravity, Higgsfield, PostHog, Railway,
GitHub, Notion, Lovable, Supabase, Pinterest, Cursor, Framer, Claude, Manus,
Wispr Flow, Sentry, VS Code, Mobbin, Resend, ElevenLabs).

## Step 3 — present and report

- Present `post.html` (the primary deliverable).
- Start the reply with the exact line `Generated at HH:MM Mon DD` using the run
  time from the runner's `GENERATED AT:` first line.
- Then briefly state: the FIRST SLIDE line (which app leads), the app order, the
  slideshow title, and the 5 hashtags.

Run autonomously, no questions. Do not modify the generator, the copy bank, the
photos, or the logos.
