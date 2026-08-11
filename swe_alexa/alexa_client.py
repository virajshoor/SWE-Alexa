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
        # OTP / email verification code
        otp_box = self.page.locator("#auth-mfa-otpcode, input[name='otpCode'], #input-box-otp")
        if otp_box.count() and otp_box.first.is_visible():
            otp_code = os.environ.get("AMAZON_OTP_CODE")
            if otp_code:
                code = re.sub(r"\D", "", otp_code.strip())
            elif otp_secret and pyotp is not None:
                code = pyotp.TOTP(otp_secret).now()
            else:
                raise RuntimeError(
                    "Amazon MFA/email OTP required. Set AMAZON_OTP_CODE (one-time email code) "
                    "or AMAZON_OTP_SECRET (TOTP)."
                )
            otp_box.first.fill(code)
            try:
                self.page.locator(
                    "#auth-signin-button, #cvf-submit-otp-button, "
                    "input[type=submit], button[type=submit]"
                ).first.click(timeout=5000)
            except Exception:
                self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(4000)
            self._shot("login_after_otp")
            # Clear one-time code so it is not reused
            if "AMAZON_OTP_CODE" in os.environ:
                os.environ.pop("AMAZON_OTP_CODE", None)
        self.page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
        self.dismiss_gates()
        return True

    # Official Alexa for Shopping promotional landing (US).
    ALEXA_LANDING = "https://www.amazon.com/b?ie=UTF8&node=216450446011"

    def _dismiss_rufus_chrome(self) -> None:
        # Close Amazon popovers/modals that intercept clicks on the composer.
        for _ in range(3):
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass
            try:
                self.page.locator('[data-action="a-popover-floating-close"]').first.click(
                    timeout=500, force=True
                )
            except Exception:
                pass
            try:
                self.page.locator(".a-button-close").first.click(timeout=500, force=True)
            except Exception:
                pass
        for sel in (
            ".rufus-panel-tooltip-close",
            'button[aria-label="close"]',
            "#rufus-panel-tooltip .rufus-panel-tooltip-close",
        ):
            try:
                loc = self.page.locator(sel)
                if loc.count() and loc.first.is_visible():
                    loc.first.click(timeout=1000, force=True)
            except Exception:
                pass
        # Profile picker: choose first visible profile card/button if present
        try:
            panel = self.page.locator("#nav-flyout-rufus")
            if panel.count() and "select your profile" in (panel.inner_text(timeout=1000) or "").lower():
                for sel in (
                    "#nav-flyout-rufus button",
                    "#nav-flyout-rufus [role=button]",
                    "#nav-flyout-rufus a",
                ):
                    loc = self.page.locator(sel)
                    for i in range(min(loc.count(), 8)):
                        el = loc.nth(i)
                        try:
                            t = (el.inner_text(timeout=500) or "").strip().lower()
                            if not el.is_visible():
                                continue
                            if t in {"new chat", "chat history", "get started", "×", "x", ""}:
                                continue
                            if "profile" in t or len(t) > 0:
                                el.click(timeout=1500, force=True)
                                self.page.wait_for_timeout(1500)
                                return
                        except Exception:
                            continue
        except Exception:
            pass

    def _chat_input(self):
        # Prefer the real Alexa/Rufus composer. Docked panel may sit off-screen
        # (negative x) so Playwright is_visible() can be false even when usable.
        preferred = [
            "#rufus-text-area",
            "#nav-flyout-rufus textarea",
            'textarea[placeholder*="Ask a shopping question" i]',
            'textarea[placeholder*="Ask" i]',
        ]
        for sel in preferred:
            try:
                loc = self.page.locator(sel)
                if not loc.count():
                    continue
                el = loc.first
                el_id = el.get_attribute("id") or ""
                if el_id == "twotabsearchtextbox":
                    continue
                # Accept if attached in DOM; JS send path works even when clipped.
                try:
                    if el.count():
                        return el
                except Exception:
                    return el
            except Exception:
                continue
        return None

    def _ensure_panel_ready(self) -> None:
        self._dismiss_rufus_chrome()
        # Profile gate
        try:
            btn = self.page.get_by_role("button", name=re.compile("Select your profile", re.I))
            if btn.count() and btn.first.is_visible():
                btn.first.click(force=True, timeout=3000)
                self.page.wait_for_timeout(2000)
                # click first profile option if a chooser appears
                for sel in (
                    "#nav-flyout-rufus [data-action*='profile' i]",
                    "#nav-flyout-rufus button",
                    "#nav-flyout-rufus li",
                ):
                    loc = self.page.locator(sel)
                    for i in range(min(loc.count(), 6)):
                        t = (loc.nth(i).inner_text(timeout=500) or "").strip().lower()
                        if t and t not in {"select your profile", "new chat", "chat history", "get started"}:
                            try:
                                loc.nth(i).click(force=True, timeout=1500)
                                self.page.wait_for_timeout(1500)
                                break
                            except Exception:
                                pass
        except Exception:
            pass
        # Keep docked-left so composer exists
        try:
            self.page.evaluate(
                """() => {
                  document.body.classList.add('rufus-docked-left','rufus-docked-adjustable');
                  const fly=document.querySelector('#nav-flyout-rufus');
                  if (fly) {
                    fly.classList.add('rufus-panel-closed-to-docked-left');
                    fly.style.display='flex'; fly.style.visibility='visible'; fly.style.opacity='1';
                  }
                }"""
            )
        except Exception:
            pass
        try:
            disco = self.page.locator("#nav-rufus-disco")
            if disco.count():
                # If panel text empty, click disco to open
                fly = self.page.locator("#nav-flyout-rufus")
                txt = ""
                try:
                    txt = fly.inner_text(timeout=1000) if fly.count() else ""
                except Exception:
                    txt = ""
                if len(txt.strip()) < 20:
                    disco.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(2000)
        except Exception:
            pass

    def open_alexa_chat(self) -> bool:
        """Open Alexa for Shopping (Rufus) docked chat on amazon.com."""
        for start in (self.ALEXA_LANDING, "https://www.amazon.com/"):
            try:
                self.page.goto(start, wait_until="domcontentloaded")
                self.dismiss_gates()
                self.page.wait_for_timeout(2000)
            except Exception:
                continue
            self._shot("before_open_alexa")
            try:
                disco = self.page.locator("#nav-rufus-disco, button[aria-label='Open Alexa panel']")
                if disco.count():
                    disco.first.click(force=True, timeout=3000)
                    self.page.wait_for_timeout(2500)
            except Exception:
                pass
            self._ensure_panel_ready()
            if self._chat_input() is not None:
                self._shot("alexa_open")
                return True
        self._shot("alexa_open_failed")
        return False

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
        self._ensure_panel_ready()
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
        max_len = 500
        try:
            ml = inp.get_attribute("maxlength")
            if ml and str(ml).isdigit():
                max_len = max(50, int(ml))
        except Exception:
            pass
        send_prompt = prompt if len(prompt) <= max_len else prompt[: max_len - 15] + "\n[truncated]"
        try:
            # JS path is reliable when the docked composer is clipped off-screen.
            ok = self.page.evaluate(
                """(text) => {
                  const el = document.querySelector('#rufus-text-area');
                  if (!el) return false;
                  el.focus();
                  el.value = text;
                  el.dispatchEvent(new Event('input', {bubbles:true}));
                  el.dispatchEvent(new Event('change', {bubbles:true}));
                  const enter = new KeyboardEvent('keydown', {key:'Enter', code:'Enter', which:13, keyCode:13, bubbles:true});
                  el.dispatchEvent(enter);
                  const form = el.closest('form');
                  if (form) {
                    const btn = form.querySelector('button[type=submit], input[type=submit], [aria-label*=send i]');
                    if (btn) btn.click();
                  }
                  // Also click common send controls inside the panel
                  const panel = document.querySelector('#nav-flyout-rufus');
                  if (panel) {
                    const send = panel.querySelector('button[aria-label*=send i], button[type=submit], .rufus-send-button, [data-action*=send i]');
                    if (send) send.click();
                  }
                  return true;
                }""",
                send_prompt,
            )
            if not ok:
                raise RuntimeError("rufus-text-area missing")
            # Fallback Enter via locator
            try:
                inp.press("Enter")
            except Exception:
                pass
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
            if latest and latest != before and len(latest) > len(before) + 15:
                self.page.wait_for_timeout(2500)
                latest2 = self._assistant_text_snapshot()
                if latest2 == latest:
                    break
                latest = latest2
        reply = latest
        if before and latest.startswith(before):
            reply = latest[len(before) :].strip()
        elif before and before in latest:
            reply = latest.replace(before, "", 1).strip()
        # Strip leading UI chrome lines if present
        if reply:
            lines = [ln for ln in reply.splitlines() if ln.strip()]
            drop_prefixes = (
                "chat history",
                "new chat",
                "get started",
                "welcome back",
                "please select your profile",
                "select your profile",
                "how can i help",
                "questions while you shop",
            )
            while lines and any(lines[0].strip().lower().startswith(p) for p in drop_prefixes):
                lines.pop(0)
            reply = "\n".join(lines).strip()
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
                  const panel = document.querySelector('#nav-flyout-rufus');
                  if (panel) {
                    const t = (panel.innerText || '').trim();
                    if (t) return t;
                  }
                  const sels = [
                    '#rufus-conversation',
                    '[class*="rufus-message" i]',
                    '[data-testid*="rufus" i]',
                    '[class*="assistant" i]',
                    '[role="log"]'
                  ];
                  let best = '';
                  for (const s of sels) {
                    for (const el of document.querySelectorAll(s)) {
                      const t = (el.innerText || '').trim();
                      if (t.length > best.length) best = t;
                    }
                  }
                  return best;
                }"""
            )
        except Exception:
            return ""
