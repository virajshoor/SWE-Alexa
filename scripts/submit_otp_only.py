#!/usr/bin/env python3
"""Submit AMAZON_OTP_CODE against the saved mid-challenge session (no new password login)."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PRE = ROOT / "artifacts" / "amazon_storage_pre_otp.json"
STORAGE = ROOT / "artifacts" / "amazon_storage.json"
PENDING = ROOT / "artifacts" / "otp_pending.json"
SHOTS = Path("/opt/cursor/artifacts/screenshots")


def main() -> int:
    otp = os.environ.get("AMAZON_OTP_CODE", "")
    code = re.sub(r"\D", "", otp.strip())
    if len(code) < 4:
        print(json.dumps({"ok": False, "error": "AMAZON_OTP_CODE missing/short"}))
        return 2
    if not PRE.exists() and not PENDING.exists():
        print(json.dumps({"ok": False, "error": "No pending OTP challenge state"}))
        return 3

    url = None
    if PENDING.exists():
        try:
            url = json.loads(PENDING.read_text()).get("url")
        except Exception:
            url = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        kwargs = {
            "viewport": {"width": 1440, "height": 900},
            "locale": "en-US",
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        }
        if PRE.exists():
            kwargs["storage_state"] = str(PRE)
        ctx = browser.new_context(**kwargs)
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        if url:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        else:
            page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        page.screenshot(path=str(SHOTS / "otp_only_1.png"))
        box = page.locator("#input-box-otp, #auth-mfa-otpcode, input[name=otpCode]")
        if not (box.count() and box.first.is_visible()):
            body = page.inner_text("body")[:600]
            print(json.dumps({"ok": False, "error": "OTP box missing", "url": page.url, "body": body}))
            browser.close()
            return 4
        box.first.fill("")
        box.first.fill(code)
        try:
            page.get_by_role("button", name=re.compile("Submit code", re.I)).click(timeout=4000)
        except Exception:
            page.locator("input[type=submit]").first.click()
        page.wait_for_timeout(6000)
        page.screenshot(path=str(SHOTS / "otp_only_2.png"))
        body = page.inner_text("body")
        still = page.locator("#input-box-otp").count() and page.locator("#input-box-otp").first.is_visible()
        rejected = any(
            k in body.lower()
            for k in ["not valid", "incorrect", "invalid", "expired", "try again"]
        )
        if still or rejected:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "OTP rejected or still on challenge",
                        "url": page.url,
                        "body": body[:500],
                    }
                )
            )
            # keep pre-otp state
            browser.close()
            return 5
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(SHOTS / "otp_only_home.png"))
        try:
            acct = page.locator("#nav-link-accountList-nav-line-1").inner_text(timeout=3000)
        except Exception:
            acct = ""
        logged = bool(acct) and "sign in" not in acct.lower()
        ctx.storage_state(path=str(STORAGE))
        # also refresh pre file to logged-in jar
        if logged:
            PRE.write_text(STORAGE.read_text(encoding="utf-8"), encoding="utf-8")
        print(json.dumps({"ok": logged, "account": acct, "url": page.url}, indent=2))
        browser.close()
        os.environ.pop("AMAZON_OTP_CODE", None)
        return 0 if logged else 6


if __name__ == "__main__":
    raise SystemExit(main())
