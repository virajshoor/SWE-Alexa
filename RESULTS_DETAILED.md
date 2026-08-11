# SWE-Alexa detailed results

## Goal

Run **at least 40** SWE-bench Verified instances against **Alexa for Shopping** through the **amazon.com web interface**, in parallel, and record code + results in this repository.

## Probe findings (amazon.com)

Date: 2026-08-11 (UTC). Region observed: US storefront, deliver-to Ashburn 20149.

### What loaded without login

- Homepage and search work in Chromium/Playwright (US `amazon.com`).
- Natural-language search queries (e.g. “What is a good wireless mouse under $30?”) fall back to **ordinary product search**, not Alexa chat.
- Product detail pages sometimes include `ucc-v2-widget__rufus-pills-trigger` inside compare widgets (legacy Rufus branding). These are **not** a free-text coding chat; no assistant textbox appeared while signed out.
- HTML/JS references docked `rufus` panel state on search pages, but the panel assets/chat input do not activate without an authenticated session.

### What is required for Alexa chat

Public Amazon documentation states Alexa for Shopping is available to **signed-in US customers** on the Amazon Shopping app and **amazon.com**, via the Alexa icon (desktop top nav / mobile bottom nav) or conversational search when signed in.

In this Cloud Agent environment, `AMAZON_EMAIL` / `AMAZON_PASSWORD` were **not** configured, so the harness could not open the Alexa chat panel.

### Screenshots / artifacts

- `/opt/cursor/artifacts/screenshots/nav_https_www_amazon_com_.png` — homepage
- `/opt/cursor/artifacts/screenshots/search_conversational.png` — NL query → keyword search
- `artifacts/probe/probe_report.json`, `deep_probe.json`, `asin_scan.json` — selector/network scans

## Method

1. Load SWE-bench Verified (`princeton-nlp/SWE-bench_Verified`, test split).
2. Take the first **40** instances (also cached in `data/verified_50.json`).
3. For each instance, build a prompt asking for a unified diff only (`swe_alexa/prompts.py`).
4. Drive amazon.com with Playwright (`swe_alexa/alexa_client.py`): login → open Alexa → send prompt → capture reply.
5. Extract `diff --git` patches (`swe_alexa/patch_extract.py`).
6. Write `preds.jsonl` and grade (`swe_alexa/evaluate.py`).
7. Parallelism via `ThreadPoolExecutor` (`--workers 4`), sharing a bootstrap cookie jar (`artifacts/amazon_storage.json`).

## Run configuration

```text
command: PYTHONPATH=. python3 -m swe_alexa run --limit 40 --workers 4 --out results/run40
model_name_or_path: amazon-alexa-for-shopping-web
workers: 4
wait_seconds: 45 (per reply when chat is open)
```

## Aggregate results (run40)

| Field | Value |
| --- | --- |
| Instances | 40 |
| Bootstrap logged_in | false |
| Bootstrap alexa_opened | false |
| OK chat replies | 0 |
| Non-empty patches | 0 |
| Empty patches | 40 |
| Offline resolved estimate | 0 / 40 (0%) |
| Error class | Alexa chat UI unavailable without amazon.com sign-in |

Source files:

- `results/run40/run_summary.json`
- `results/run40/preds.jsonl`
- `results/run40/raw_results.json`
- `results/run40/grade/offline_grade.json`
- `results/run40/trajectories/<instance_id>.json` (prompt + error per instance)

## Instance IDs evaluated

```text
astropy__astropy-12907
astropy__astropy-13033
astropy__astropy-13236
astropy__astropy-13398
astropy__astropy-13453
astropy__astropy-13579
astropy__astropy-13977
astropy__astropy-14096
astropy__astropy-14182
astropy__astropy-14309
astropy__astropy-14365
astropy__astropy-14369
astropy__astropy-14508
astropy__astropy-14539
astropy__astropy-14598
astropy__astropy-14995
astropy__astropy-7166
astropy__astropy-7336
astropy__astropy-7606
astropy__astropy-7671
astropy__astropy-8707
astropy__astropy-8872
django__django-10097
django__django-10554
django__django-10880
django__django-10914
django__django-10973
django__django-10999
django__django-11066
django__django-11087
django__django-11095
django__django-11099
django__django-11119
django__django-11133
django__django-11138
django__django-11141
django__django-11149
django__django-11163
django__django-11179
django__django-11206
```

## Interpretation

1. **Access result:** Under signed-out automation, Alexa for Shopping cannot be tested as a conversational coding agent on amazon.com.
2. **Capability prior:** Even after login, Alexa for Shopping is product/shopping-oriented. Asking it for GitHub issue patches is out-of-distribution; a near-zero SWE-bench score would still be an informative negative result.
3. **Grading:** With zero nonempty patches, official FAIL_TO_PASS / PASS_TO_PASS Docker execution would also yield **0% resolved**. Local Docker in this VM could not run containers (overlayfs mount error); offline patch-presence grading is sufficient for this empty-prediction set.

## How to reproduce a live-chat run

1. Add secrets: `AMAZON_EMAIL`, `AMAZON_PASSWORD`, optional `AMAZON_OTP_SECRET`.
2. `PYTHONPATH=. python3 -m swe_alexa bootstrap` — confirm `alexa_opened: true`.
3. `PYTHONPATH=. python3 -m swe_alexa run --limit 40 --workers 4 --out results/run40_live`
4. If Docker/sb-cli is available, grade with the official harness; otherwise use the offline grader and treat nonempty-patch rate as an intermediate metric.

## Code map

| Module | Role |
| --- | --- |
| `swe_alexa/alexa_client.py` | Login, open Alexa, send prompt, capture reply |
| `swe_alexa/runner.py` | Dataset load + parallel workers + preds writing |
| `swe_alexa/prompts.py` | SWE-bench → Alexa prompt framing |
| `swe_alexa/patch_extract.py` | Pull unified diffs out of chat text |
| `swe_alexa/evaluate.py` | Offline / sb-cli / local harness grading |
| `swe_alexa/__main__.py` | CLI (`bootstrap`, `run`, `grade`) |
| `scripts/probe_alexa.py` | Initial homepage/search probe |
| `scripts/probe_alexa_deep.py` | Network + product-page probe |
