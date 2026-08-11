"""Playwright driver for Amazon.com Alexa for Shopping chat."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

try:
    import pyotp
except ImportError:  # optional
    pyotp = None  # type: ignore


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class AlexaReply:
    ok: bool
    text: str
    error: str = ""
    url: str = ""
    screenshot: str = ""


class AlexaShoppingClient:
    """Drive Alexa for Shopping on https://www.amazon.com (US)."""

    def __init__(
        self,
        *,
        headless: bool = True,
        storage_state: str | Path | None = None,
        screenshot_dir: str | Path = "artifacts/screenshots",
        timeout_ms: int = 60000,
    ) -> None:
        self.headless = headless
        self.storage_state = str(storage_state) if storage_state else None
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_ms = timeout_ms
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> "AlexaShoppingClient":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def start(self) -> None:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        kwargs: dict[str, Any] = {
            "user_agent": UA,
            "viewport": {"width": 1440, "height": 900},
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "geolocation": {"longitude": -74.006, "latitude": 40.7128},
            "permissions": ["geolocation"],
        }
        if self.storage_state and Path(self.storage_state).exists():
            kwargs["storage_state"] = self.storage_state
        self._context = self._browser.new_context(**kwargs)
        self._page = self._context.new_page()
        self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        self._page.set_default_timeout(self.timeout_ms)

    def close(self) -> None:
        try:
            if self._context and self.storage_state:
                self._context.storage_state(path=self.storage_state)
        except Exception:
            pass
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    @property
    def page(self) -> Page:
        assert self._page is not None
        return self._page

    def _shot(self, name: str) -> str:
        path = self.screenshot_dir / f"{name}.png"
        try:
            self.page.screenshot(path=str(path), full_page=False)
            return str(path)
        except Exception:
            return ""

    def dismiss_gates(self) -> None:
        for text in ("Continue shopping", "Dismiss", "Not now", "No thanks", "Accept", "Got it"):
            try:
                loc = self.page.get_by_role("button", name=re.compile(text, re.I))
                if loc.count() and loc.first.is_visible():
                    loc.first.click(timeout=1500)
                    self.page.wait_for_timeout(800)
            except Exception:
                pass

    def login_if_needed(
        self,
        email: str | None = None,
        password: str | None = None,
        otp_secret: str | None = None,
    ) -> bool:
        email = email or os.environ.get("AMAZON_EMAIL")
        password = password or os.environ.get("AMAZON_PASSWORD")
        otp_secret = otp_secret or os.environ.get("AMAZON_OTP_SECRET")
        self.page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
        self.dismiss_gates()
        # Already signed in?
        try:
            acct = self.page.locator("#nav-link-accountList-nav-line-1")
            if acct.count():
                txt = (acct.inner_text(timeout=2000) or "").lower()
                if "hello" in txt and "sign in" not in txt:
                    return True
        except Exception:
            pass
        if not email or not password:
            return False
        self.page.goto(
            "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0"
            "&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F"
            "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
            "&openid.assoc_handle=usflex"
            "&openid.mode=checkid_setup&openid.claimed_id="
            "http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
            "&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0",
            wait_until="domcontentloaded",
        )
        self.dismiss_gates()
        self._shot("login_start")
        # email
        try:
            self.page.fill("#ap_email", email)
        except Exception:
            try:
                self.page.fill('input[name="email"]', email)
            except Exception as e:
                raise RuntimeError(f"Could not fill email: {e}") from e
        try:
            self.page.click("#continue", timeout=3000)
        except Exception:
            try:
                self.page.keyboard.press("Enter")
            except Exception:
                pass
        self.page.wait_for_timeout(1500)
        # password
        try:
            self.page.fill("#ap_password", password)
        except Exception:
            self.page.fill('input[name="password"]', password)
        try:
            self.page.click("#signInSubmit")
        except Exception:
            self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(3000)
        self._shot("login_after_password")
        # OTP
        otp_box = self.page.locator("#auth-mfa-otpcode, input[name='otpCode'], #input-box-otp")
        if otp_box.count() and otp_box.first.is_visible():
            if not otp_secret or pyotp is None:
                raise RuntimeError("Amazon MFA required but AMAZON_OTP_SECRET / pyotp missing")
            code = pyotp.TOTP(otp_secret).now()
            otp_box.first.fill(code)
            try:
                self.page.click("#auth-signin-button, #cvf-submit-otp-button, button[type=submit]")
            except Exception:
                self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(3000)
            self._shot("login_after_otp")
        self.page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
        self.dismiss_gates()
        return True

    def open_alexa_chat(self) -> bool:
        """Open Alexa for Shopping chat panel on amazon.com."""
        self.page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
        self.dismiss_gates()
        self._shot("before_open_alexa")
        selectors = [
            '[aria-label*="Alexa" i]',
            '[aria-label*="Rufus" i]',
            'a[href*="rufus" i]',
            'button:has-text("Alexa")',
            '[data-testid*="rufus" i]',
            '[data-testid*="alexa" i]',
            "#nav-rufus",
            "#nav-link-alexa",
            'span:has-text("Alexa")',
            ".ucc-v2-widget__rufus-pills-trigger",
            '[class*="rufus-pills" i]',
            'a:has-text("Ask Alexa")',
            'button:has-text("Ask Alexa")',
            'a:has-text("Chat with Alexa")',
        ]
        for sel in selectors:
            try:
                loc = self.page.locator(sel)
                n = loc.count()
                for i in range(min(n, 5)):
                    el = loc.nth(i)
                    if el.is_visible():
                        el.click(timeout=2000)
                        self.page.wait_for_timeout(2500)
                        if self._chat_input() is not None:
                            self._shot("alexa_open")
                            return True
            except Exception:
                continue
        # Fallback: natural-language search may route into Alexa chat when signed in
        try:
            box = self.page.locator("#twotabsearchtextbox")
            if box.count():
                box.fill("What are good running headphones under $50?")
                self.page.locator("#nav-search-submit-button").click()
                self.page.wait_for_timeout(5000)
                self._shot("nlq_fallback")
                if self._chat_input() is not None:
                    return True
                # try clicking any Alexa/Rufus ingress on results
                for text in ("Alexa", "Ask Alexa", "Chat with Alexa", "Rufus"):
                    try:
                        t = self.page.get_by_text(text, exact=False)
                        if t.count():
                            t.first.click(timeout=2000)
                            self.page.wait_for_timeout(2500)
                            if self._chat_input() is not None:
                                return True
                    except Exception:
                        pass
        except Exception:
            pass
        self._shot("alexa_open_failed")
        return False

    def _chat_input(self):
        candidates = [
            'textarea[placeholder*="Ask" i]',
            'textarea[aria-label*="Ask" i]',
            'textarea[aria-label*="Alexa" i]',
            'textarea[aria-label*="Rufus" i]',
            '[role="textbox"]',
            "textarea",
            'input[placeholder*="Ask" i]',
        ]
        for sel in candidates:
            try:
                loc = self.page.locator(sel)
                for i in range(min(loc.count(), 6)):
                    el = loc.nth(i)
                    if el.is_visible():
                        # Prefer assistants over the main Amazon search box
                        el_id = el.get_attribute("id") or ""
                        if el_id == "twotabsearchtextbox":
                            continue
                        return el
            except Exception:
                continue
        return None

    def ask(self, prompt: str, *, wait_s: float = 45.0, tag: str = "ask") -> AlexaReply:
        if self._chat_input() is None:
            opened = self.open_alexa_chat()
            if not opened:
                return AlexaReply(
                    ok=False,
                    text="",
                    error="Alexa for Shopping chat UI not available (login/region/weblab gated)",
                    url=self.page.url,
                    screenshot=self._shot(f"{tag}_no_ui"),
                )
        inp = self._chat_input()
        if inp is None:
            return AlexaReply(
                ok=False,
                text="",
                error="Chat input not found after opening Alexa",
                url=self.page.url,
                screenshot=self._shot(f"{tag}_no_input"),
            )
        before = self._assistant_text_snapshot()
        try:
            inp.click()
            inp.fill("")
            # Fill large prompts in chunks to avoid UI truncation
            chunk = 1500
            for i in range(0, len(prompt), chunk):
                inp.type(prompt[i : i + chunk], delay=0)
            inp.press("Enter")
        except Exception as e:
            return AlexaReply(
                ok=False,
                text="",
                error=f"Failed to send prompt: {e}",
                url=self.page.url,
                screenshot=self._shot(f"{tag}_send_fail"),
            )

        deadline = time.time() + wait_s
        latest = ""
        while time.time() < deadline:
            self.page.wait_for_timeout(1500)
            latest = self._assistant_text_snapshot()
            if latest and latest != before and len(latest) > len(before) + 20:
                # wait a bit more for streaming to settle
                self.page.wait_for_timeout(2500)
                latest2 = self._assistant_text_snapshot()
                if latest2 == latest:
                    break
                latest = latest2
        # Prefer delta
        reply = latest
        if before and latest.startswith(before):
            reply = latest[len(before) :].strip()
        elif before and before in latest:
            reply = latest.replace(before, "", 1).strip()
        self._shot(f"{tag}_done")
        if not reply:
            return AlexaReply(
                ok=False,
                text=latest,
                error="No assistant reply captured",
                url=self.page.url,
                screenshot=self._shot(f"{tag}_empty"),
            )
        return AlexaReply(ok=True, text=reply, url=self.page.url, screenshot=self._shot(f"{tag}_ok"))

    def _assistant_text_snapshot(self) -> str:
        try:
            return self.page.evaluate(
                """() => {
                  const sels = [
                    '[data-testid*="message" i]',
                    '[class*="assistant" i]',
                    '[class*="rufus" i]',
                    '[class*="alexa" i]',
                    '[role="log"]',
                    '[aria-live]'
                  ];
                  let best = '';
                  for (const s of sels) {
                    for (const el of document.querySelectorAll(s)) {
                      const t = (el.innerText || '').trim();
                      if (t.length > best.length) best = t;
                    }
                  }
                  if (!best) best = (document.body.innerText || '').slice(0, 20000);
                  return best;
                }"""
            )
        except Exception:
            return ""
