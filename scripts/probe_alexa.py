#!/usr/bin/env python3
"""Probe Amazon.com for Alexa for Shopping chat UI and dump selectors."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/workspace/artifacts/probe")
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = Path("/opt/cursor/artifacts/screenshots")
SHOTS.mkdir(parents=True, exist_ok=True)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def save(page, name: str) -> None:
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)
    (OUT / f"{name}.html").write_text(page.content(), encoding="utf-8")
    print(f"saved {name} url={page.url}")


def dismiss_gates(page) -> None:
    for text in (
        "Continue shopping",
        "Dismiss",
        "Not now",
        "No thanks",
        "Accept",
        "Got it",
        "Continue",
    ):
        try:
            loc = page.get_by_role("button", name=re.compile(text, re.I))
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2000)
                page.wait_for_timeout(1000)
        except Exception:
            pass
    # Zip / country change
    try:
        change = page.get_by_text(re.compile("Change address|Deliver to", re.I))
        if change.count():
            print("delivery UI present")
    except Exception:
        pass


def find_alexa_entrypoints(page) -> list[dict]:
    candidates = []
    patterns = [
        r"alexa",
        r"rufus",
        r"ask\s*alexa",
        r"shopping\s*assistant",
    ]
    # links/buttons/aria
    for sel in ["a", "button", "[role=button]", "[aria-label]", "[data-testid]"]:
        for el in page.query_selector_all(sel):
            try:
                blob = " ".join(
                    filter(
                        None,
                        [
                            el.get_attribute("aria-label") or "",
                            el.get_attribute("title") or "",
                            el.get_attribute("data-testid") or "",
                            el.get_attribute("href") or "",
                            el.get_attribute("id") or "",
                            el.inner_text(timeout=500)[:120] if True else "",
                        ],
                    )
                ).lower()
            except Exception:
                continue
            if any(re.search(p, blob) for p in patterns):
                candidates.append(
                    {
                        "tag": el.evaluate("e => e.tagName"),
                        "aria": el.get_attribute("aria-label"),
                        "id": el.get_attribute("id"),
                        "testid": el.get_attribute("data-testid"),
                        "href": el.get_attribute("href"),
                        "text": (el.inner_text(timeout=500) or "")[:160],
                        "class": (el.get_attribute("class") or "")[:200],
                    }
                )
    # de-dupe
    seen = set()
    uniq = []
    for c in candidates:
        key = json.dumps(c, sort_keys=True)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq


def try_open_alexa(page, candidates: list[dict]) -> bool:
    for c in candidates:
        for key in ("aria", "text", "testid", "id"):
            val = c.get(key)
            if not val:
                continue
            try:
                if key == "aria":
                    page.get_by_label(re.compile(re.escape(val[:40]), re.I)).first.click(
                        timeout=3000
                    )
                elif key == "text" and len(val.strip()) > 2:
                    page.get_by_text(val.strip()[:40], exact=False).first.click(timeout=3000)
                elif key == "id":
                    page.locator(f"#{val}").first.click(timeout=3000)
                elif key == "testid":
                    page.locator(f'[data-testid="{val}"]').first.click(timeout=3000)
                page.wait_for_timeout(2500)
                save(page, "alexa_opened")
                return True
            except Exception:
                continue
        href = c.get("href")
        if href and "alexa" in href.lower():
            try:
                page.goto(href if href.startswith("http") else f"https://www.amazon.com{href}")
                page.wait_for_timeout(3000)
                save(page, "alexa_href")
                return True
            except Exception:
                pass
    return False


def main() -> None:
    report: dict = {"steps": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"longitude": -74.006, "latitude": 40.7128},
            permissions=["geolocation"],
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        urls = [
            "https://www.amazon.com/",
            "https://www.amazon.com/?language=en_US",
            "https://www.amazon.com/alexa-shopping",
            "https://www.amazon.com/gp/help/customer/display.html?nodeId=G202211260",
        ]
        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(3000)
                dismiss_gates(page)
                name = re.sub(r"[^a-z0-9]+", "_", url.lower())[:60]
                save(page, f"nav_{name}")
                cands = find_alexa_entrypoints(page)
                report["steps"].append({"url": page.url, "candidates": cands[:30]})
                print(f"{url} -> {page.url} candidates={len(cands)}")
                if cands:
                    opened = try_open_alexa(page, cands)
                    report["steps"][-1]["opened"] = opened
                    if opened:
                        # look for chat input
                        inputs = []
                        for sel in [
                            "textarea",
                            'input[type="text"]',
                            '[contenteditable="true"]',
                            "[role=textbox]",
                        ]:
                            for el in page.query_selector_all(sel):
                                try:
                                    inputs.append(
                                        {
                                            "sel_hint": sel,
                                            "aria": el.get_attribute("aria-label"),
                                            "placeholder": el.get_attribute("placeholder"),
                                            "id": el.get_attribute("id"),
                                            "name": el.get_attribute("name"),
                                            "class": (el.get_attribute("class") or "")[:200],
                                        }
                                    )
                                except Exception:
                                    pass
                        report["chat_inputs"] = inputs
                        # try a message via search bar fallback
                        break
            except Exception as e:
                report["steps"].append({"url": url, "error": str(e)})

        # Also try search-bar conversational query (Alexa for Shopping entry)
        try:
            page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=60000)
            dismiss_gates(page)
            box = page.locator("#twotabsearchtextbox")
            if box.count():
                box.fill("What is a good wireless mouse under $30?")
                page.locator("#nav-search-submit-button").click()
                page.wait_for_timeout(5000)
                save(page, "search_conversational")
                report["search_url"] = page.url
                report["search_candidates"] = find_alexa_entrypoints(page)[:20]
        except Exception as e:
            report["search_error"] = str(e)

        (OUT / "probe_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2)[:4000])
        browser.close()


if __name__ == "__main__":
    main()
