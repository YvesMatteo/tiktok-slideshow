#!/usr/bin/env python3
"""Push a generated slideshow run to TikTok as a DRAFT (or a direct post)."""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.parse, urllib.request
from pathlib import Path

API = "https://open.tiktokapis.com"
REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_PHOTOS, POLL_TIMEOUT_S, POLL_INTERVAL_S = 35, 300, 5


def _request(url, *, data, headers, method="POST"):
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} from {url}\n{e.read().decode('utf-8','replace')}") from None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise SystemExit(f"Non-JSON response from {url}:\n{body}") from None


def post_json(url, token, payload):
    return _request(url, data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json; charset=UTF-8"})


def post_form(url, payload):
    return _request(url, data=urllib.parse.urlencode(payload).encode("utf-8"),
                    headers={"Content-Type": "application/x-www-form-urlencoded"})


def latest_run():
    runs = REPO_ROOT / "runs"
    c = sorted((p for p in runs.iterdir() if p.is_dir()), reverse=True)
    if not c:
        raise SystemExit(f"No run folders under {runs}")
    return c[0]


def parse_caption(run):
    path = run / "caption.txt"
    if not path.exists():
        raise SystemExit(f"Missing {path}")
    raw = path.read_text(encoding="utf-8")
    title = ""
    for line in raw.splitlines():
        if line.startswith("TITLE:"):
            title = line.split("TITLE:", 1)[1].strip(); break
    body = raw.split("CAPTION:", 1)[1] if "CAPTION:" in raw else raw
    body = body.split("\n---", 1)[0].strip()
    return title[:90], body[:4000]


def slide_urls(run, base_url):
    slides = sorted(run.glob("slide_*.jpg"))
    if not slides:
        raise SystemExit(f"No slide_*.jpg in {run}")
    if len(slides) > MAX_PHOTOS:
        raise SystemExit(f"{len(slides)} slides exceeds TikTok's {MAX_PHOTOS} limit")
    base = base_url.rstrip("/")
    return [f"{base}/{run.name}/{s.name}" for s in slides]


def refresh_access_token(key, secret, refresh_token):
    res = post_form(f"{API}/v2/oauth/token/",
                    {"client_key": key, "client_secret": secret,
                     "grant_type": "refresh_token", "refresh_token": refresh_token})
    if "access_token" not in res:
        raise SystemExit(f"Token refresh failed:\n{json.dumps(res, indent=2)}")
    if res.get("refresh_token") and res["refresh_token"] != refresh_token:
        print("::notice::TikTok rotated the refresh token.")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(f"new_refresh_token={res['refresh_token']}\n")
    return res["access_token"]


def build_payload(title, description, urls, *, direct, privacy, cover_index):
    post_info = {"title": title, "description": description}
    if direct:
        post_info.update({"privacy_level": privacy, "disable_comment": False,
                          "auto_add_music": True, "brand_content_toggle": False,
                          "brand_organic_toggle": False})
    return {"media_type": "PHOTO",
            "post_mode": "DIRECT_POST" if direct else "MEDIA_UPLOAD",
            "post_info": post_info,
            "source_info": {"source": "PULL_FROM_URL",
                            "photo_cover_index": cover_index,
                            "photo_images": urls}}


def poll_status(token, publish_id):
    deadline, last = time.time() + POLL_TIMEOUT_S, {}
    while time.time() < deadline:
        res = post_json(f"{API}/v2/post/publish/status/fetch/", token, {"publish_id": publish_id})
        data = res.get("data", {}); status = data.get("status"); last = data
        print(f"  status: {status}")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return data
        if status == "FAILED":
            raise SystemExit(f"TikTok reported FAILED:\n{json.dumps(res, indent=2)}")
        time.sleep(POLL_INTERVAL_S)
    print("  (still processing at timeout)")
    return last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--base-url", default=os.environ.get("TIKTOK_SLIDES_BASE_URL", ""))
    ap.add_argument("--direct", action="store_true")
    ap.add_argument("--privacy", default="PUBLIC_TO_EVERYONE")
    ap.add_argument("--cover-index", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    run = Path(args.run) if args.run else latest_run()
    if not run.is_absolute():
        run = (REPO_ROOT / run).resolve()
    if not run.is_dir():
        raise SystemExit(f"Not a directory: {run}")
    if not args.base_url:
        raise SystemExit("Set TIKTOK_SLIDES_BASE_URL or pass --base-url")

    title, description = parse_caption(run)
    urls = slide_urls(run, args.base_url)
    payload = build_payload(title, description, urls, direct=args.direct,
                            privacy=args.privacy, cover_index=args.cover_index)

    print(f"Run:    {run.name}")
    print(f"Title:  {title}")
    print(f"Slides: {len(urls)}")
    print(f"Mode:   {'DIRECT_POST (public)' if args.direct else 'MEDIA_UPLOAD (draft)'}")

    if args.dry_run:
        print("\n--- payload (dry run) ---")
        print(json.dumps(payload, indent=2, ensure_ascii=False)); return

    key = os.environ.get("TIKTOK_CLIENT_KEY")
    secret = os.environ.get("TIKTOK_CLIENT_SECRET")
    refresh = os.environ.get("TIKTOK_REFRESH_TOKEN")
    missing = [n for n, v in [("TIKTOK_CLIENT_KEY", key), ("TIKTOK_CLIENT_SECRET", secret),
                              ("TIKTOK_REFRESH_TOKEN", refresh)] if not v]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

    print("\nRefreshing access token...")
    token = refresh_access_token(key, secret, refresh)

    info = post_json(f"{API}/v2/post/publish/creator_info/query/", token, {}).get("data", {})
    if info.get("creator_username"):
        print(f"Authorized as @{info['creator_username']}")

    print("Submitting to TikTok...")
    res = post_json(f"{API}/v2/post/publish/content/init/", token, payload)
    err = res.get("error", {})
    if err.get("code") not in (None, "ok"):
        raise SystemExit(f"TikTok rejected the request:\n{json.dumps(res, indent=2)}")
    publish_id = res.get("data", {}).get("publish_id")
    if not publish_id:
        raise SystemExit(f"No publish_id returned:\n{json.dumps(res, indent=2)}")
    print(f"publish_id: {publish_id}")

    final = poll_status(token, publish_id)
    if final.get("status") == "SEND_TO_USER_INBOX":
        print("\nDraft is waiting in your TikTok inbox. Open it, add a sound, publish.")
    elif final.get("status") == "PUBLISH_COMPLETE":
        print("\nPosted.")


if __name__ == "__main__":
    sys.exit(main())
