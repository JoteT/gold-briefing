#!/usr/bin/env python3
"""
beehiiv_browser.py — Africa Gold Intelligence
===============================================
Publishes posts to Beehiiv by automating the web interface with Playwright.
Bypasses the Enterprise-only Send API — works on any Beehiiv plan.

FIRST-TIME SETUP:
  pip install playwright --break-system-packages
  playwright install chromium

REQUIRED ENV VARS (add to .env):
  BEEHIIV_EMAIL     — your Beehiiv login email
  BEEHIIV_PASSWORD  — your Beehiiv login password

OPTIONAL:
  BEEHIIV_PUB_ID    — publication ID (auto-detected from login if omitted)

USAGE (standalone test):
  python3 beehiiv_browser.py --test
"""

import os, sys, json, time, datetime
from pathlib import Path

SCRIPT_DIR    = Path(__file__).parent
COOKIES_FILE  = SCRIPT_DIR.parent / "data" / ".beehiiv_session.json"
PROFILE_DIR   = Path.home() / ".beehiiv_profile"   # persistent login profile
BEEHIIV_APP   = "https://app.beehiiv.com"

# ── Load .env ────────────────────────────────────────────────────────────────
_env_file = SCRIPT_DIR.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k, _v = _k.strip(), _v.strip()
            if _v and "REPLACE_WITH" not in _v and "your_" not in _v.lower():
                os.environ[_k] = _v

BEEHIIV_EMAIL    = os.environ.get("BEEHIIV_EMAIL",    "")
BEEHIIV_PASSWORD = os.environ.get("BEEHIIV_PASSWORD", "")
BEEHIIV_PUB_ID   = os.environ.get("BEEHIIV_PUB_ID",   "pub_5927fa56-6b7c-4310-8f35-2ff9d18f523b")


# ── Core publisher ────────────────────────────────────────────────────────────

def publish_post(
    title: str,
    subtitle: str,
    free_html: str,
    premium_html: str = "",
    publish_type: str = "draft",   # "draft" | "instant"
    slug: str = None,
    tags: list = None,
) -> dict:
    """
    Create a Beehiiv post using browser automation.

    Returns:
        {"success": True, "post_url": "...", "post_id": "...", "method": "browser"}
    Raises:
        RuntimeError with a human-readable message on failure.
    """
    _check_credentials()
    _check_playwright()

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    print("  🌐 Launching browser...")

    # Use persistent profile if setup_beehiiv_login.py has been run —
    # this carries the trusted-device flag so no confirmation code is needed.
    use_persistent = PROFILE_DIR.exists() and any(PROFILE_DIR.iterdir())

    with sync_playwright() as pw:
        if use_persistent:
            print("  🔑 Using persistent login profile (no device code needed)...")
            ctx = pw.chromium.launch_persistent_context(
                str(PROFILE_DIR),
                headless=True,
                viewport={"width": 1440, "height": 900},
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        else:
            print("  ⚠️  No persistent profile found.")
            print("       Run setup_beehiiv_login.py once to avoid device confirmation codes.")
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            _load_session(ctx)

        page = ctx.pages[0] if (use_persistent and ctx.pages) else ctx.new_page()

        try:
            # 1. Log in if needed (skipped when using persistent profile — already trusted)
            if not use_persistent:
                _ensure_logged_in(page, ctx)

            # 2. Navigate to new post form
            print("  📝 Opening new post editor...")
            page.goto(f"{BEEHIIV_APP}/posts/new", timeout=60_000,
                      wait_until="domcontentloaded")
            time.sleep(2)

            # 3. Check if Beehiiv redirected us to a login/error page
            current_url = page.url
            on_auth_page = any(x in current_url for x in
                               ["sign-in", "login", "sign_in", "/auth"])

            if on_auth_page:
                if use_persistent:
                    raise RuntimeError(
                        "Persistent session has expired.\n"
                        "Run setup_beehiiv_login.py again to refresh it:\n"
                        "  python3 setup_beehiiv_login.py"
                    )
                else:
                    print("  🔑 Redirected to login — logging in now...")
                    _do_login(page)
                    _save_session(ctx)
                    page.goto(f"{BEEHIIV_APP}/posts/new", timeout=60_000,
                              wait_until="domcontentloaded")
                    time.sleep(2)

            _wait_for_editor(page)

            # 3. Fill in title
            print("  ✍️  Setting title...")
            _set_title(page, title)

            # 4. Inject the free content HTML into the editor
            print("  📄 Injecting post content...")
            _inject_content(page, free_html)

            # 5. Fill subtitle / preview text if the field is present
            _set_subtitle(page, subtitle)

            # 6. Set SEO slug if provided
            if slug:
                _set_slug(page, slug)

            # 7. Publish or save as draft
            if publish_type == "instant":
                print("  🚀 Publishing post live...")
                post_url = _publish_now(page)
            else:
                print("  📋 Saving as draft...")
                post_url = _save_draft(page)

            # 8. Save session for next run
            _save_session(ctx)

            result = {
                "success":  True,
                "post_url": post_url or "",
                "post_id":  "browser-post",
                "method":   "browser",
            }
            print(f"  ✅ Post {'published' if publish_type == 'instant' else 'saved as draft'} via browser")
            if post_url:
                print(f"     URL: {post_url}")
            return result

        except PWTimeout as e:
            screenshot = SCRIPT_DIR.parent / "logs" / "browser_error.png"
            try:
                page.screenshot(path=str(screenshot))
                print(f"  📸 Screenshot saved: {screenshot}")
            except Exception:
                pass
            raise RuntimeError(f"Browser timed out: {e}") from e

        except Exception as e:
            screenshot = SCRIPT_DIR.parent / "logs" / "browser_error.png"
            try:
                page.screenshot(path=str(screenshot))
                print(f"  📸 Screenshot saved: {screenshot}")
            except Exception:
                pass
            raise

        finally:
            ctx.close()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _check_credentials():
    missing = []
    if not BEEHIIV_EMAIL:
        missing.append("BEEHIIV_EMAIL")
    if not BEEHIIV_PASSWORD:
        missing.append("BEEHIIV_PASSWORD")
    if missing:
        raise RuntimeError(
            f"Missing credentials: {', '.join(missing)}\n"
            f"Add them to your .env file:\n"
            f"  BEEHIIV_EMAIL=your@email.com\n"
            f"  BEEHIIV_PASSWORD=your_beehiiv_password"
        )


def _check_playwright():
    try:
        import playwright  # noqa
    except ImportError:
        raise RuntimeError(
            "Playwright is not installed.\n"
            "Run these two commands to install it:\n"
            "  pip install playwright --break-system-packages\n"
            "  playwright install chromium"
        )


def _load_session(ctx):
    if COOKIES_FILE.exists():
        try:
            cookies = json.loads(COOKIES_FILE.read_text())
            if cookies:
                ctx.add_cookies(cookies)
        except Exception as e:
            print(f"  ⚠️  Could not load saved session: {e}")


def _save_session(ctx):
    try:
        COOKIES_FILE.write_text(json.dumps(ctx.cookies()))
    except Exception as e:
        print(f"  ⚠️  Could not save session: {e}")


def _ensure_logged_in(page, ctx):
    """Navigate to Beehiiv and log in if necessary."""
    # Use domcontentloaded — Beehiiv's SPA keeps loading background scripts
    # after the page is visually ready, so "load" can time out even on success
    page.goto(f"{BEEHIIV_APP}/", timeout=60_000,
              wait_until="domcontentloaded")
    time.sleep(2)

    # Check URL AND whether we're actually in the app (not a sign-in redirect)
    on_signin = "sign-in" in page.url or "login" in page.url
    if on_signin:
        print("  🔑 Logging in to Beehiiv...")
        _do_login(page)
        _save_session(ctx)
    else:
        # Verify the session is actually valid by checking for an app element
        app_element = page.query_selector('nav, [data-testid="sidebar"], .sidebar, [href*="/posts"]')
        if app_element:
            print("  🔑 Session valid — already logged in")
        else:
            # Looks logged out even though URL doesn't say sign-in — force login
            print("  🔑 Session may be stale — logging in fresh...")
            _do_login(page)
            _save_session(ctx)


def _do_login(page):
    """
    Handle Beehiiv login. Supports two layouts:
      A) Single-page: email + password shown together → fill both, click Sign in
      B) Two-step:    email only → click Continue → password appears → fill + Sign in
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    page.goto(f"{BEEHIIV_APP}/sign-in", timeout=60_000,
              wait_until="domcontentloaded")
    time.sleep(1.5)

    email_sel  = 'input[type="email"], input[name="email"]'
    pwd_sel    = 'input[type="password"], input[name="password"]'
    submit_sel = 'button[type="submit"], button:has-text("Sign in"), button:has-text("Continue")'

    # Wait for email field
    page.wait_for_selector(email_sel, timeout=15_000)

    # Fill email
    page.fill(email_sel, BEEHIIV_EMAIL)
    time.sleep(0.5)

    # Check if password field is ALREADY visible (single-page form)
    pwd_visible = page.query_selector(pwd_sel) is not None

    if pwd_visible:
        # ── Layout A: fill password immediately, then submit ─────────────────
        page.fill(pwd_sel, BEEHIIV_PASSWORD)
        time.sleep(0.3)
        page.click(submit_sel)
    else:
        # ── Layout B: click Continue, wait for password field ─────────────────
        page.click(submit_sel)
        time.sleep(1.5)
        try:
            page.wait_for_selector(pwd_sel, timeout=8_000)
            page.fill(pwd_sel, BEEHIIV_PASSWORD)
            time.sleep(0.3)
            page.click(submit_sel)
        except PWTimeout:
            raise RuntimeError(
                "Password field did not appear after entering email.\n"
                "If you signed up via Google ('Sign in with Google'), you may not\n"
                "have a password set. Visit app.beehiiv.com/settings/account to\n"
                "set a password, then update BEEHIIV_PASSWORD in .env."
            )

    # ── Wait for successful redirect away from sign-in page ───────────────────
    try:
        page.wait_for_url(
            lambda url: "sign-in" not in url and "login" not in url,
            timeout=25_000
        )
    except PWTimeout:
        raise RuntimeError(
            "Login failed — still on sign-in page after submitting.\n"
            "Most likely cause: wrong password in .env.\n"
            "Double-check BEEHIIV_PASSWORD matches your Beehiiv account password.\n"
            "Screenshot saved to browser_error.png for inspection."
        )

    print("  ✅ Logged in successfully")


def _wait_for_editor(page):
    """Wait until the Beehiiv post editor is ready."""
    from playwright.sync_api import TimeoutError as PWTimeout
    selectors = [
        '[data-testid="post-title"]',
        'textarea[placeholder*="Title"]',
        'input[placeholder*="Title"]',
        '.ProseMirror',
        '[contenteditable="true"]',
    ]
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=15_000)
            return
        except PWTimeout:
            continue
    # Give it extra time for JS to render
    time.sleep(4)


def _set_title(page, title: str):
    """Fill the post title field."""
    selectors = [
        '[data-testid="post-title"]',
        'textarea[placeholder*="Title"]',
        'input[placeholder*="Title"]',
        'h1[contenteditable="true"]',
    ]
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            el.click()
            # Clear any existing content
            el.evaluate("el => el.value !== undefined ? (el.value = '') : (el.textContent = '')")
            el.type(title, delay=20)
            return
    # Fallback: try pressing Tab from the first editable element
    page.keyboard.press("Tab")
    page.keyboard.type(title, delay=20)


def _inject_content(page, html: str):
    """
    Inject HTML content into the Beehiiv post editor.
    Strategy: use the execCommand / clipboard paste API.
    Beehiiv's ProseMirror editor respects HTML paste events.
    """
    # Find the contenteditable editor area
    editor_sel = '.ProseMirror, [contenteditable="true"][role="textbox"], [data-testid="editor-content"]'

    editor = page.query_selector(editor_sel)
    if not editor:
        # Try clicking below the title to get focus in the body
        page.keyboard.press("Tab")
        time.sleep(0.5)
        editor = page.query_selector(editor_sel)

    # Use browser clipboard injection
    # This writes the HTML to the clipboard then triggers a paste event
    # Works reliably with ProseMirror-based editors
    success = page.evaluate(
        """(html) => {
            try {
                // Find the editor
                const editor = document.querySelector('.ProseMirror')
                    || document.querySelector('[contenteditable="true"][role="textbox"]')
                    || document.querySelector('[contenteditable="true"]');
                if (!editor) return false;
                editor.focus();

                // Create a DataTransfer with HTML content
                const dt = new DataTransfer();
                dt.setData('text/html', html);
                dt.setData('text/plain', html.replace(/<[^>]+>/g, ''));

                // Dispatch paste event
                const pasteEvent = new ClipboardEvent('paste', {
                    bubbles: true,
                    cancelable: true,
                    clipboardData: dt,
                });
                editor.dispatchEvent(pasteEvent);
                return true;
            } catch(e) {
                return false;
            }
        }""",
        html
    )

    if not success:
        # Fallback: try keyboard.insertText (inserts plain text)
        print("  ⚠️  Rich HTML paste unavailable — inserting as plain text")
        if editor:
            editor.click()
        # Strip HTML tags for plain text fallback
        import re
        plain = re.sub(r'<[^>]+>', ' ', html)
        plain = re.sub(r'\s+', ' ', plain).strip()
        page.keyboard.type(plain[:3000], delay=5)

    time.sleep(1)


def _set_subtitle(page, subtitle: str):
    """Fill the post subtitle/description field if present."""
    selectors = [
        '[data-testid="post-subtitle"]',
        'input[placeholder*="subtitle" i]',
        'textarea[placeholder*="subtitle" i]',
        'input[placeholder*="description" i]',
    ]
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            el.click()
            el.fill(subtitle[:250])
            return


def _set_slug(page, slug: str):
    """Set the SEO slug if the field is accessible."""
    selectors = [
        'input[name="slug"]',
        'input[placeholder*="slug" i]',
        'input[placeholder*="url" i]',
    ]
    for sel in selectors:
        el = page.query_selector(sel)
        if el:
            try:
                el.fill(slug)
                return
            except Exception:
                pass


def _save_draft(page) -> str:
    """Click Save as Draft and return the post URL."""
    from playwright.sync_api import TimeoutError as PWTimeout

    # Let the editor settle after content injection
    time.sleep(3)

    selectors = [
        'button:has-text("Save draft")',
        'button:has-text("Save as draft")',
        '[data-testid="save-draft-button"]',
        'button:has-text("Save")',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=8_000)
            loc.scroll_into_view_if_needed()
            loc.click(timeout=15_000)
            time.sleep(2)
            return _extract_post_url(page)
        except Exception:
            continue

    # Keyboard shortcut fallback: Cmd+S / Ctrl+S
    page.keyboard.press("Meta+s")
    time.sleep(2)
    return _extract_post_url(page)


def _publish_now(page) -> str:
    """
    Click Publish (or Send) and confirm to go live.

    Beehiiv's publish flow:
      1. Click the primary "Publish" / "Send" button in the top bar
         → opens a confirmation panel / drawer
      2. Click "Send now" / "Publish now" inside that panel

    Uses locator() which has built-in actionability waits, preventing the
    'ElementHandle.click timeout' that occurs when using raw query_selector().
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    # Let the editor settle fully after content injection
    time.sleep(3)

    # ── Step 1: Click the primary publish/send button ─────────────────────────
    pub_selectors = [
        'button:has-text("Publish")',
        'button:has-text("Send")',
        '[data-testid="publish-button"]',
        'button:has-text("Send & Publish")',
    ]
    clicked_primary = False
    for sel in pub_selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=10_000)
            loc.scroll_into_view_if_needed()
            loc.click(timeout=20_000)
            clicked_primary = True
            time.sleep(2)
            break
        except Exception:
            continue

    if not clicked_primary:
        raise RuntimeError(
            "Could not find or click the Publish button.\n"
            "The Beehiiv editor UI may have changed. Screenshot saved to browser_error.png."
        )

    # ── Step 2: Confirmation panel / dialog ───────────────────────────────────
    confirm_selectors = [
        'button:has-text("Send now")',
        'button:has-text("Publish now")',
        'button:has-text("Confirm")',
        'button:has-text("Yes, publish")',
        'button:has-text("Send & Publish")',
        '[data-testid="confirm-publish-button"]',
    ]
    for sel in confirm_selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=10_000)
            loc.scroll_into_view_if_needed()
            loc.click(timeout=15_000)
            time.sleep(3)
            break
        except PWTimeout:
            continue

    return _extract_post_url(page)


def _extract_post_url(page) -> str:
    """Try to extract the live post URL from the current page state."""
    try:
        # Beehiiv often shows the public URL after save/publish
        url_el = page.query_selector('[data-testid="post-url"], a[href*="/p/"]')
        if url_el:
            href = url_el.get_attribute("href")
            if href and href.startswith("http"):
                return href
            if href and href.startswith("/p/"):
                return f"https://www.africagoldintelligence.com{href}"

        # Check current URL for post ID
        current = page.url
        if "/posts/" in current:
            # Extract internal Beehiiv post URL
            return current

    except Exception:
        pass
    return ""


# ── Standalone test ───────────────────────────────────────────────────────────

def _run_test():
    print("\n" + "─"*60)
    print("  Beehiiv Browser Automation — Test Run")
    print("─"*60 + "\n")

    if not BEEHIIV_EMAIL or not BEEHIIV_PASSWORD:
        print("  ❌  BEEHIIV_EMAIL or BEEHIIV_PASSWORD not set in .env\n")
        print("  Add these lines to your .env file:")
        print("    BEEHIIV_EMAIL=your@email.com")
        print("    BEEHIIV_PASSWORD=your_beehiiv_password\n")
        return

    print(f"  Email:  {BEEHIIV_EMAIL}")
    print(f"  Pub ID: {BEEHIIV_PUB_ID}\n")

    test_html = """
    <h2>AGI Browser Automation Test Post</h2>
    <p>This is an automated test post created by the Africa Gold Intelligence
    browser automation system. If you see this in your Beehiiv drafts, the
    integration is working correctly. You can safely delete this post.</p>
    <p style="color:#6b7280;font-size:0.85rem;">
      Generated: {ts}
    </p>
    """.format(ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    try:
        result = publish_post(
            title    = "AGI Browser Test — DELETE ME",
            subtitle = "Automated browser integration test",
            free_html = test_html,
            publish_type = "draft",
        )
        print("\n  ✅  SUCCESS — test draft created in Beehiiv!")
        print(f"     Check your Beehiiv drafts panel and delete it.")
        if result.get("post_url"):
            print(f"     URL: {result['post_url']}")
    except Exception as e:
        print(f"\n  ❌  FAILED: {e}")
        print("\n  Troubleshooting:")
        print("  • Check browser_error.png for a screenshot of what went wrong")
        print("  • Ensure BEEHIIV_EMAIL and BEEHIIV_PASSWORD are correct in .env")
        print("  • Run: playwright install chromium  (if Chromium isn't installed)")

    print()


if __name__ == "__main__":
    if "--test" in sys.argv:
        _run_test()
    else:
        print("Usage: python3 beehiiv_browser.py --test")
        print("       (Tests that the browser can log in and create a draft)")
