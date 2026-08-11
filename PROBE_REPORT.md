# Amazon.com Alexa for Shopping — probe report

## Target

User requirement: use **Alexa for Amazon / Alexa for Shopping on amazon.com only** (not alexa.com app surfaces) as the AI under test for SWE-bench Verified.

## Entry points tested

| URL / action | Result |
| --- | --- |
| `https://www.amazon.com/` | Homepage OK; no Alexa chat launcher while signed out |
| Search NLQ in `#twotabsearchtextbox` | Standard SERP; no Alexa panel |
| `/alexa-shopping` | Page not found |
| Product detail pages | Occasional `ucc-v2-widget__rufus-pills-trigger` inside compare tables; no free-text assistant input |
| Account / sign-in | Required for Alexa for Shopping per Amazon public docs |

## Selectors worth trying once signed in

The harness tries, in order:

- `[aria-label*="Alexa" i]`, `[aria-label*="Rufus" i]`
- `button:has-text("Alexa")`, `[data-testid*="alexa" i]`, `[data-testid*="rufus" i]`
- `#nav-rufus`, `#nav-link-alexa`
- NL search fallback + click “Ask Alexa” / “Chat with Alexa”
- Chat inputs: `textarea[placeholder*="Ask" i]`, `[role=textbox]` (excluding `#twotabsearchtextbox`)

## Network

While signed out, no Rufus/Alexa conversation SSE/API traffic was observed after homepage/search/PDP loads. Search pages embed JS that *listens* for `rufus-panel-state-change`, indicating the docked chat is a logged-in progressive enhancement.

## Conclusion

Automation can reach amazon.com reliably. **Live Alexa for Shopping chat requires an authenticated US amazon.com session.** The evaluation package is built around that path; the recorded 40-instance run documents the login gate.
