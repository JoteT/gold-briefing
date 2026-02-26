#!/usr/bin/env python3
"""
beehiiv_api_check.py — Africa Gold Intelligence
=================================================
Diagnose Beehiiv API key permissions and identify the SEND_API_DISABLED fix.

Usage:
    python3 beehiiv_api_check.py

Checks:
  1. API key is present and has the right format
  2. GET /publications/{pub_id} — read access works
  3. GET /publications/{pub_id}/posts — list access works
  4. POST /publications/{pub_id}/posts (draft test post) — write access works
  5. DELETE the test post if creation succeeded
"""

import os, json, sys
from pathlib import Path

# ── Load .env ────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
_env_file  = SCRIPT_DIR.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k, _v = _k.strip(), _v.strip()
            if _v and "REPLACE_WITH" not in _v and "your_" not in _v.lower():
                os.environ[_k] = _v

API_KEY = os.environ.get("BEEHIIV_API_KEY", "")
PUB_ID  = os.environ.get("BEEHIIV_PUB_ID",  "pub_5927fa56-6b7c-4310-8f35-2ff9d18f523b")
BASE    = "https://api.beehiiv.com/v2"

# ── Helpers ──────────────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    print("❌  'requests' not installed. Run: pip install requests --break-system-packages")
    sys.exit(1)

def hdr():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type":  "application/json",
    }

def check(label, fn):
    try:
        result = fn()
        print(f"  ✅  {label}")
        return result
    except Exception as e:
        print(f"  ❌  {label}\n      Error: {e}")
        return None

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "─"*60)
    print("  Beehiiv API Diagnostic — Africa Gold Intelligence")
    print("─"*60 + "\n")

    # 1. Key presence
    if not API_KEY:
        print("  ❌  BEEHIIV_API_KEY is not set in .env or environment.\n")
        print("  Fix: add  BEEHIIV_API_KEY=your_key  to .env and retry.\n")
        sys.exit(1)

    key_prefix = API_KEY[:8] + "..." + API_KEY[-4:] if len(API_KEY) > 12 else "too short"
    key_len    = len(API_KEY)
    print(f"  Key loaded:  {key_prefix}  ({key_len} chars)")
    print(f"  Pub ID:      {PUB_ID}\n")

    if key_len < 20:
        print("  ⚠️  Key looks too short — double-check you copied the full API key.\n")

    # 2. Read publication info (GET — any key can do this)
    print("  Test 1: Read publication info (GET)...")
    pub_data = check(
        "GET /publications/{pub_id}",
        lambda: _check_read_pub()
    )

    # 3. List posts (GET)
    print("\n  Test 2: List posts (GET)...")
    check(
        "GET /publications/{pub_id}/posts",
        lambda: _check_list_posts()
    )

    # 4. Create draft test post (POST — this is what SEND_API_DISABLED blocks)
    print("\n  Test 3: Create a draft test post (POST — requires Send API enabled)...")
    created_id = check(
        "POST /publications/{pub_id}/posts",
        lambda: _check_create_post()
    )

    # 5. Delete if created
    if created_id:
        print(f"\n  Test 4: Delete the test draft (DELETE)...")
        check(
            f"DELETE /publications/{PUB_ID}/posts/{created_id}",
            lambda: _check_delete_post(created_id)
        )

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "─"*60)
    if created_id:
        print("\n  ✅  ALL TESTS PASSED — your API key has full write access!")
        print("      Your orchestrator should now be able to create draft posts.")
        print("      Run: python3 orchestrator.py\n")
    else:
        print("\n  ❌  POST test failed — API write access is not enabled.\n")
        print("  HOW TO FIX THE SEND_API_DISABLED ERROR:")
        print("  ─"*30)
        print("  Step 1: Go to  https://app.beehiiv.com/settings/api")
        print("  Step 2: Find the 'API Keys' section")
        print("  Step 3: DELETE your existing API key")
        print("  Step 4: Click 'Create New API Key'")
        print("  Step 5: On the permissions screen, make sure")
        print("          'Posts' write access is CHECKED")
        print("          (Some keys are created read-only by default)")
        print("  Step 6: Copy the new key and update .env:")
        print("          BEEHIIV_API_KEY=your_new_key_here")
        print("  Step 7: Re-run this diagnostic to confirm it works\n")
        print("  Note: If you don't see a permissions screen when creating")
        print("  the key, contact Beehiiv support — some Scale accounts need")
        print("  their Send API manually enabled by their team.\n")


def _check_read_pub():
    url  = f"{BASE}/publications/{PUB_ID}"
    resp = requests.get(url, headers=hdr(), timeout=15)
    if resp.status_code == 200:
        name = resp.json().get("data", {}).get("name", "unknown")
        print(f"       Publication: '{name}'")
        return resp.json()
    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")


def _check_list_posts():
    url  = f"{BASE}/publications/{PUB_ID}/posts?limit=1"
    resp = requests.get(url, headers=hdr(), timeout=15)
    if resp.status_code == 200:
        total = resp.json().get("total_results", "?")
        print(f"       Posts found: {total}")
        return resp.json()
    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")


def _check_create_post():
    url     = f"{BASE}/publications/{PUB_ID}/posts"
    payload = {
        "title":              "AGI API Diagnostic Test Post — DELETE ME",
        "subtitle":           "Auto-generated diagnostic test. Safe to delete.",
        "email_subject_line": "AGI Test",
        "preview_text":       "Diagnostic test",
        "free_web_content":   "<p>This is an automated API diagnostic test post. Please delete it.</p>",
        "free_email_content": "<p>This is an automated API diagnostic test post. Please delete it.</p>",
        "audience":           "all",
        "publish_type":       "draft",
        "content_tags":       ["test"],
    }
    resp = requests.post(url, headers=hdr(), data=json.dumps(payload), timeout=30)
    if resp.status_code in (200, 201):
        post_id = resp.json().get("data", {}).get("id", "unknown")
        print(f"       Test draft created — ID: {post_id}")
        return post_id
    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")


def _check_delete_post(post_id: str):
    url  = f"{BASE}/publications/{PUB_ID}/posts/{post_id}"
    resp = requests.delete(url, headers=hdr(), timeout=15)
    if resp.status_code in (200, 204):
        print(f"       Test draft deleted ✓")
        return True
    # Non-fatal — draft might need manual deletion
    print(f"       Could not auto-delete (HTTP {resp.status_code}) — delete it manually in Beehiiv drafts.")
    return False


if __name__ == "__main__":
    main()
