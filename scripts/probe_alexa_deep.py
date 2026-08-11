#!/usr/bin/env python3
"""Deeper probe: product pages + network sniff for Rufus/Alexa APIs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/workspace/artifacts/probe")
OUT.mkdir(parents=True, exist_ok=True)
SHOTS = Path("/opt/cursor/artifacts/screenshots")
SHOTS.mkdir(parents=True, exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def main() -> None:
    net: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        def on_request(req):
            u = req.url.lower()
            if any(k in u for k in ("rufus", "alexa", "assistant", "chat", "converse", "genai")):
                net.append({"type": "req", "method": req.method, "url": req.url[:500]})

        def on_response(resp):
            u = resp.url.lower()
            if any(k in u for k in ("rufus", "alexa", "assistant", "chat", "converse", "genai")):
                net.append(
                    {
                        "type": "resp",
                        "status": resp.status,
                        "url": resp.url[:500],
                        "ct": resp.headers.get("content-type", ""),
                    }
                )

        page.on("request", on_request)
        page.on("response", on_response)

        # Popular ASIN product page
        urls = [
            "https://www.amazon.com/dp/B0D1XD1ZV3",  # example device
            "https://www.amazon.com/s?k=best+noise+cancelling+headphones",
            "https://www.amazon.com/gp/css/homepage.html",
        ]
        findings = {"pages": []}
        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
                # click continue shopping if present
                try:
                    page.get_by_role("button", name=re.compile("Continue shopping", re.I)).click(
                        timeout=2000
                    )
                    page.wait_for_timeout(2000)
                except Exception:
                    pass
                name = re.sub(r"[^a-z0-9]+", "_", url.lower())[:50]
                page.screenshot(path=str(SHOTS / f"deep_{name}.png"))
                html = page.content()
                (OUT / f"deep_{name}.html").write_text(html, encoding="utf-8")
                # search for ask/rufus buttons
                labels = page.evaluate(
                    """() => {
                      const out=[];
                      for (const el of document.querySelectorAll('a,button,[role=button],[aria-label]')) {
                        const t=((el.getAttribute('aria-label')||'')+' '+(el.innerText||'')+' '+(el.id||'')+' '+(el.className||'')).toLowerCase();
                        if (/rufus|alexa|ask .+about|ask a question|shopping assistant|chat with/.test(t)) {
                          out.push({tag:el.tagName, id:el.id, aria:el.getAttribute('aria-label'), text:(el.innerText||'').slice(0,120), class:(el.className||'').toString().slice(0,120)});
                        }
                      }
                      return out.slice(0,50);
                    }"""
                )
                findings["pages"].append({"url": page.url, "labels": labels})
                print(url, "->", page.url, "labels", len(labels))
                for lab in labels[:10]:
                    print(" ", lab)
                # try clicking first match
                if labels:
                    try:
                        aria = labels[0].get("aria") or labels[0].get("text")
                        if aria:
                            page.get_by_text(aria[:30], exact=False).first.click(timeout=3000)
                            page.wait_for_timeout(4000)
                            page.screenshot(path=str(SHOTS / f"deep_clicked_{name}.png"))
                    except Exception as e:
                        print("click fail", e)
            except Exception as e:
                findings["pages"].append({"url": url, "error": str(e)})

        findings["network"] = net[:200]
        (OUT / "deep_probe.json").write_text(json.dumps(findings, indent=2), encoding="utf-8")
        print("network hits", len(net))
        for n in net[:40]:
            print(n)
        browser.close()


if __name__ == "__main__":
    main()
