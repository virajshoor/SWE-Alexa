#!/usr/bin/env python3
"""Complete Amazon login using an already-open OTP challenge + AMAZON_OTP_CODE.

Minimizes logins: password step may be skipped if CVF approval page is still valid
in storage_state; otherwise performs at most one fresh password+OTP login.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STORAGE = ROOT / "artifacts" / "amazon_storage.json"
SHOTS = Path("/opt/cursor/artifacts/screenshots")
SHOTS.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def main() -> int:
    email = os.environ.get("AMAZON_EMAIL")
    password = os.environ.get("AMAZON_PASSWORD")
    otp = os.environ.get("AMAZON_OTP_CODE")
    if not email or not password:
        print(json.dumps({"ok": False, "error": "AMAZON_EMAIL/PASSWORD missing"}))
        return 2
    if not otp:
        print(json.dumps({"ok": False, "error": "AMAZON_OTP_CODE missing — paste email code"}))
        return 3

    code = re.sub(r"\D", "", otp.strip())
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        kwargs = {
            "user_agent": UA,
            "viewport": {"width": 1440, "height": 900},
            "locale": "en-US",
        }
        if STORAGE.exists():
            kwargs["storage_state"] = str(STORAGE)
        ctx = browser.new_context(**kwargs)
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        # If prior flow left us on CVF OTP page, reuse it; else fresh login once.
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        acct = page.locator("#nav-link-accountList-nav-line-1")
        if acct.count():
            txt = (acct.inner_text(timeout=2000) or "").lower()
            if "hello" in txt and "sign in" not in txt:
                ctx.storage_state(path=str(STORAGE))
                print(json.dumps({"ok": True, "already_logged_in": True, "account": txt}))
                browser.close()
                return 0

        # Prefer existing CVF URL from last attempt if still in history — go sign-in
        page.goto(
            "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0"
            "&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F"
            "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
            "&openid.assoc_handle=usflex&openid.mode=checkid_setup"
            "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
            "&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(1500)

        # Email
        for sel in ["#ap_email", "#ap_email_login", "input[name=email]"]:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.fill(email)
                break
        try:
            page.click("#continue", timeout=2500)
        except Exception:
            page.keyboard.press("Enter")
        page.wait_for_timeout(1500)

        # Password if shown
        for sel in ["#ap_password", "input[name=password]"]:
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.fill(password)
                try:
                    page.click("#signInSubmit", timeout=2500)
                except Exception:
                    page.keyboard.press("Enter")
                page.wait_for_timeout(3500)
                break

        page.screenshot(path=str(SHOTS / "login_otp_ready.png"))
        otp_box = page.locator("#input-box-otp, #auth-mfa-otpcode, input[name=otpCode]")
        if not (otp_box.count() and otp_box.first.is_visible()):
            # Maybe already in
            page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.screenshot(path=str(SHOTS / "login_after_attempt.png"))
            body = page.inner_text("body")[:500]
            ctx.storage_state(path=str(STORAGE))
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "OTP box not shown",
                        "url": page.url,
                        "body": body,
                    }
                )
            )
            browser.close()
            return 4

        otp_box.first.fill(code)
        try:
            page.locator("input[type=submit], button[type=submit]").first.click(timeout=5000)
        except Exception:
            page.keyboard.press("Enter")
        page.wait_for_timeout(5000)
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(SHOTS / "login_success_check.png"))
        acct_txt = ""
        try:
            acct_txt = page.locator("#nav-link-accountList-nav-line-1").inner_text(timeout=3000)
        except Exception:
            pass
        ctx.storage_state(path=str(STORAGE))
        logged_in = bool(acct_txt) and "sign in" not in acct_txt.lower()
        # Try open Alexa landing
        page.goto(
            "https://www.amazon.com/b?ie=UTF8&node=216450446011",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(4000)
        page.screenshot(path=str(SHOTS / "alexa_after_login.png"))
        has_ask = "ask a shopping question" in page.inner_text("body").lower()
        ctx.storage_state(path=str(STORAGE))
        print(
            json.dumps(
                {
                    "ok": logged_in,
                    "account": acct_txt,
                    "alexa_landing_ask_box": has_ask,
                    "url": page.url,
                    "storage": str(STORAGE),
                },
                indent=2,
            )
        )
        browser.close()
        # consume OTP
        os.environ.pop("AMAZON_OTP_CODE", None)
        return 0 if logged_in else 5


if __name__ == "__main__":
    raise SystemExit(main())
