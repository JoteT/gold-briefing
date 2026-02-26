#!/usr/bin/env python3
"""
test_email.py — Quick test for AGI email notifications
Run this first to confirm your Gmail App Password is correct.

Usage:
    NOTIFY_PASSWORD='your_app_password' python3 test_email.py

Or just run it and paste your password when prompted.
"""

import smtplib
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

NOTIFY_EMAIL = "jote.taddese@gmail.com"
SMTP_HOST    = "smtp.gmail.com"
SMTP_PORT    = 587

def main():
    password = os.environ.get("NOTIFY_PASSWORD", "")

    if not password:
        print("\n  AGI Email Notification Test")
        print("  ─────────────────────────────")
        print("  You need a Gmail App Password (NOT your regular Gmail password).")
        print("  Get one at: https://myaccount.google.com/apppasswords")
        print("  (Google account must have 2-Step Verification enabled)")
        print()
        password = input("  Enter Gmail App Password: ").strip()

    if not password:
        print("\n  ❌ No password provided. Exiting.")
        sys.exit(1)

    print(f"\n  Sending test email to {NOTIFY_EMAIL}...")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "✅ AGI Email Test — Notifications are working"
    msg["From"]    = NOTIFY_EMAIL
    msg["To"]      = NOTIFY_EMAIL

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
      <h2 style="color: #B8860B;">Africa Gold Intelligence</h2>
      <h3>✅ Email notifications are working!</h3>
      <p>This confirms your Gmail App Password is correctly configured for the AGI orchestrator.</p>
      <table style="width:100%; border-collapse:collapse; margin: 20px 0;">
        <tr>
          <td style="padding:8px; color:#666;">Sent at</td>
          <td style="padding:8px; font-weight:bold;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
        </tr>
        <tr style="background:#f9f9f9;">
          <td style="padding:8px; color:#666;">Notify email</td>
          <td style="padding:8px; font-weight:bold;">{NOTIFY_EMAIL}</td>
        </tr>
        <tr>
          <td style="padding:8px; color:#666;">Next step</td>
          <td style="padding:8px; font-weight:bold;">Run install_scheduler.sh to activate daily 6AM automation</td>
        </tr>
      </table>
      <hr style="border: 1px solid #eee; margin: 20px 0;">
      <p style="color:#999; font-size:12px;">
        Each morning at 6AM, you'll receive a similar email with a link to review your Beehiiv draft
        before anything is sent to subscribers.
      </p>
    </div>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(NOTIFY_EMAIL, password)
            server.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())

        print(f"\n  ✅ Test email sent successfully to {NOTIFY_EMAIL}")
        print("  Check your inbox (and spam folder just in case).")
        print()
        print("  Now run the full installer:")
        print(f"    cd ~/Documents/GoldBriefing")
        print(f"    NOTIFY_PASSWORD='{password}' bash install_scheduler.sh")
        print()

    except smtplib.SMTPAuthenticationError:
        print("\n  ❌ Authentication failed.")
        print("  Your Gmail App Password is incorrect, or you used your regular Gmail password.")
        print()
        print("  To get a Gmail App Password:")
        print("  1. Go to: https://myaccount.google.com/apppasswords")
        print("  2. Sign in to your Google account")
        print("  3. Click 'Select app' → 'Mail'")
        print("  4. Click 'Select device' → 'Mac' (or Other)")
        print("  5. Click 'Generate' — copy the 16-character password shown")
        print()
        sys.exit(1)

    except Exception as e:
        print(f"\n  ❌ Failed to send email: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
