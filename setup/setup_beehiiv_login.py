#!/usr/bin/env python3
"""
setup_beehiiv_login.py — Africa Gold Intelligence
===================================================
Run this ONCE to establish a trusted Beehiiv session.

It opens a real visible browser window. You log in normally — including
entering the device confirmation code from your email. Once you're in,
press Enter here and the session is saved permanently.

All future runs of orchestrator.py will reuse this saved session and
will never ask for a device confirmation code again.

USAGE:
  python3 setup_beehiiv_login.py
"""

import sys, time
from pathlib import Path

PROFILE_DIR = Path.home() / ".beehiiv_profile"
BEEHIIV_APP = "https://app.beehiiv.com"

def main():
    print("\n" + "━"*58)
    print("  Beehiiv One-Time Login Setup")
    print("━"*58)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n  ❌  Playwright not installed.")
        print("  Run:  pip install playwright --break-system-packages")
        print("        playwright install chromium\n")
        sys.exit(1)

    print(f"""
  This will open a real browser window.

  Steps:
    1. Log into Beehiiv normally (email + password)
    2. Check your email for the device confirmation code
    3. Enter the code in the browser
    4. Once you see your Beehiiv dashboard, come back here
    5. Press Enter to save the session

  Profile will be saved to:
    {PROFILE_DIR}
""")
    input("  Press Enter to open the browser... ")

    with sync_playwright() as pw:
        print("\n  🌐 Opening browser...")
        ctx = pw.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox"],
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # If not already on beehiiv, navigate there
        if "beehiiv" not in page.url:
            page.goto(f"{BEEHIIV_APP}/sign-in", wait_until="domcontentloaded")

        print("  Browser is open. Log in and complete the device confirmation.")
        print("  Come back to this Terminal window once you're on your dashboard.\n")

        input("  Press Enter once you're logged in and can see your Beehiiv dashboard... ")

        # Verify we're actually logged in (not still on sign-in page)
        current_url = page.url
        if "sign-in" in current_url or "login" in current_url:
            print("\n  ⚠️  Looks like you're still on the login page.")
            print("  Please complete the full login in the browser, then press Enter again.")
            input("  Press Enter when done... ")

        ctx.close()

    print(f"\n  ✅  Session saved to {PROFILE_DIR}")
    print("  You only need to do this once.")
    print("\n  Now run the test to confirm everything works:")
    print("    python3 beehiiv_browser.py --test\n")


if __name__ == "__main__":
    main()
