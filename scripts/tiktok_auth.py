#!/usr/bin/env python3
"""One-time TikTok OAuth helper (no local server; TikTok rejects localhost)."""

from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.parse
import urllib.request

DEFAULT_REDIRECT = "https://checkvibe.dev/tiktok/callback"
SCOPES = "user.info.basic,video.upload"


def exchange(key: str, secret: str, code: str, redirect: str) -> dict:
    body = urllib.parse.urlencode({
        "client_key": key,
        "client_secret": secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect,
    }).encode()
    req = urllib.request.Request(
        "https://open.tiktokapis.com/v2/oauth/token/",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}:\n{e.read().decode('utf-8', 'replace')}") from None


def extract_code(pasted: str) -> str:
    pasted = pasted.strip()
    if pasted.startswith("http"):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
        if "error" in qs:
            raise SystemExit(f"TikTok error: {qs.get('error_description', qs['error'])}")
        if "code" not in qs:
            raise SystemExit("That URL has no ?code= parameter.")
        return qs["code"][0]
    return urllib.parse.unquote(pasted)


def main() -> None:
    key = os.environ.get("TIKTOK_CLIENT_KEY")
    secret = os.environ.get("TIKTOK_CLIENT_SECRET")
    redirect = os.environ.get("TIKTOK_REDIRECT_URI", DEFAULT_REDIRECT)

    if not key or not secret:
        raise SystemExit("Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET first.")
    if redirect.startswith("http://"):
        raise SystemExit("TikTok requires an https:// redirect URI.")

    state = secrets.token_urlsafe(16)
    auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": redirect,
        "state": state,
    })

    print("=" * 70)
    print("1. Open this URL and approve access:\n")
    print(auth_url)
    print("\n2. You will land on a 404 page. That is expected.")
    print("3. Copy the FULL URL from the address bar and paste it below.")
    print("=" * 70)

    pasted = input("\nRedirected URL (or just the code): ").strip()
    if not pasted:
        raise SystemExit("Nothing pasted.")

    tokens = exchange(key, secret, extract_code(pasted), redirect)

    if "refresh_token" not in tokens:
        raise SystemExit(f"Token exchange failed:\n{json.dumps(tokens, indent=2)}")

    print("\n" + "=" * 70)
    print("Store this as the GitHub secret TIKTOK_REFRESH_TOKEN:\n")
    print(tokens["refresh_token"])
    print("=" * 70)
    print(f"\nScopes granted: {tokens.get('scope')}")


if __name__ == "__main__":
    main()
