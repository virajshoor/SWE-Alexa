# SWE-Alexa detailed results

## Goal

Run **at least 40** SWE-bench Verified instances against **Alexa for Shopping** through the **amazon.com web interface**, in parallel, and record code + results in this repository.

## Probe findings (amazon.com)

- Signed-out browsers do not expose a usable Alexa chat composer.
- Signed-in US desktop session surfaces:
  - `#nav-rufus-disco` (“Open Alexa panel” / “alexa for shopping”)
  - Docked panel `#nav-flyout-rufus`
  - Composer `#rufus-text-area` (`placeholder="Ask a shopping question"`, **`maxlength=500`**)
- Landing node used in harness: `https://www.amazon.com/b?ie=UTF8&node=216450446011`
- Profile gate (“Select your profile”) may appear; harness dismisses/clicks through when possible.

## Method

1. Authenticate once (email/password + email OTP), persist `artifacts/amazon_storage.json`.
2. Parallel Playwright workers reuse the cookie jar (**no per-instance logins**).
3. For each Verified instance, send a ≤500-char compact SWE-bench prompt asking for a unified diff or `NO_PATCH`.
4. Capture `#nav-flyout-rufus` text; extract `diff --git` patches when present.
5. Write `preds.jsonl` and offline-grade patch presence (empty ⇒ unresolved).

## Live run configuration (`results/run40_live`)

```text
PYTHONPATH=. python3 -m swe_alexa run --limit 40 --workers 2 --wait 55 \
  --out results/run40_live --storage artifacts/amazon_storage.json
model_name_or_path: Alexa-Rufus-1
```

Bootstrap probe replied `PONG` to a ping, confirming the chat path before the batch.

## Aggregate results

| Field | Value |
| --- | --- |
| Instances | 40 |
| OK chat replies | 40 |
| Non-empty patches | 0 |
| Offline resolved | 0 / 40 (0%) |
| Explicit “can't help with coding” refusals | vast majority (~32+) |
| Other non-diff replies (CS redirects, shopping misreads, incomplete generation) | remainder |
| Unified diffs produced | **0** |

Typical refusal from live transcripts:

> I'm Alexa, Amazon's shopping assistant — I'm not able to help with software engineering tasks, coding issues, or GitHub patches.

## Instance IDs

Same first-40 Verified slice as before (astropy + django IDs listed in `results/run40_live/run_summary.json`).

## Interpretation

1. **Access:** Live signed-in amazon.com Alexa for Shopping chat is reachable via Playwright.
2. **Capability on SWE-bench:** Alexa for Shopping declines coding/patch tasks; this 40-instance sample produced **zero** patches.
3. **Grading:** Empty `model_patch` ⇒ 0% resolved under SWE-bench semantics (Docker FAIL_TO_PASS would not change that).

## Artifacts

- `results/run40_live/preds.jsonl`
- `results/run40_live/raw_results.json`
- `results/run40_live/trajectories/*.json`
- `results/run40_live/grade/offline_grade.json`
- `results/run40_live/bootstrap.json`
