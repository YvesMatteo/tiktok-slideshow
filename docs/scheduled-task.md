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
- medias: **randomly pick ONE** of the five starting images using these weights
  — `start_18yo.png` 25%, `start_always.png` 12.5%, `start_always_3.png` 12.5%,
  `start_always_4.png` 25%, `start_always_5.png` 25%. Decide with a real random
  draw, e.g.
  `python3 -c "import random;print(random.choices(['18yo','a1','a3','a4','a5'],weights=[25,12.5,12.5,25,25])[0])"`.
  Pass the chosen image as `[{"role":"image","value":"<media_id>"}]`.
  **The prompt depends on which image was picked.**
    - `start_always.png`   (12.5%) → media_id `945e5643-26e1-4a6e-a3d4-d6f469f44e04` → **prompt A**
    - `start_always_3.png` (12.5%) → media_id `c93aeed2-beec-4109-9dc7-5138ffac4b6d` → **prompt A**
    - `start_always_4.png` (25%)   → media_id `102026d6-3870-4145-84cc-566b786769d5` → **prompt C**
    - `start_always_5.png` (25%)   → media_id `bb17588f-526a-4aa8-84f5-5a355a30808f` → **prompt D**
    - `start_18yo.png`     (25%)   → no cached id: upload `assets/start_18yo.png`
      via `media_upload` → curl PUT → `media_confirm`, then use the fresh
      media_id → **prompt B**
- **Rotating hook text** — prompts A, C, and D all need one line of hook text
  substituted in at `<CHOSEN LINE>`. Pick it with an independent real random
  draw each run, e.g.
  `python3 -c "import random;print(random.choice(['5 apps I use to run my entire business.','the 5 apps behind my entire business.','how I run a business with just 5 apps.']))"`.
  Use the *same* chosen line for whichever of A/C/D ends up firing this run
  (only one of them ever fires per run, since only one starting image is
  drawn).
- **prompt A** (start_always / start_always_3): `Either same person or different attractive about 25 year old person, similar outfit, same overall color palette, clean and same aesthetic, different background, different camera angle. Add clean bold white sans-serif text reading '<CHOSEN LINE>' in a similar clean position/style as before. Photographic.`
- **prompt B** (start_18yo.png): `Keep the same young man seen from behind and the same dark, moody aesthetic and color palette. Keep the text exactly the same, always written across his bare back and only where his back is, in the same clean white type so it stands out clearly. Subtly change the rest of the scene: different room details, slightly different lighting and camera angle. Photographic, realistic.`
- **prompt C** (start_always_4.png): `Same or a different attractive person in their mid-20s, seated at a minimalist designer desk in a bright, sun-lit apartment with tall windows and herringbone floors, similar relaxed pose at the computer, same airy natural-light color palette. Add clean bold white sans-serif text in the upper-left reading '<CHOSEN LINE>', same simple typography style as the rest. Vary the room details, time of day, and camera angle slightly. Photographic, realistic.`
- **prompt D** (start_always_5.png): `Same or a different person seen from behind in silhouette, walking away through a modern architectural space with clean concrete lines, reflecting pool, and cars in the driveway, same dusk lighting and moody color palette. Add clean bold white sans-serif text centered in the upper portion reading '<CHOSEN LINE>', same simple typography style as the rest. Vary the architecture details, framing, and camera angle slightly. Photographic, realistic.`
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
