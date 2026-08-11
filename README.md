# SWE-Alexa

Evaluate **Alexa for Shopping** (Amazon.com web UI only) on **SWE-bench Verified** by driving the chat interface with Playwright, collecting patches in parallel, then grading.

## System name: **Alexa-Rufus-1**

## Summary of live run (`results/run40_live`)

| Metric | Value |
| --- | --- |
| Dataset | `princeton-nlp/SWE-bench_Verified` (first 40 test instances) |
| Interface | amazon.com Alexa for Shopping (`#nav-rufus-disco` / `#rufus-text-area`) |
| Auth | Signed-in US session (cookie jar reused; minimal logins) |
| Parallel workers | **2** |
| Instances completed | **40 / 40** |
| Chat replies captured | **40 / 40** |
| Non-empty patches | **0** |
| Offline resolved estimate | **0%** |

**Headline:** With a live signed-in amazon.com session, Alexa for Shopping consistently answered SWE-bench coding prompts by **refusing software-engineering / GitHub-patch help** and steering back to shopping. No unified diffs were produced → **0%** on this 40-instance slice.

See [RESULTS_DETAILED.md](RESULTS_DETAILED.md) for methodology, probe notes, and per-instance IDs.

## Setup

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
export AMAZON_EMAIL='...'
export AMAZON_PASSWORD='...'
# Email OTP once if challenged:
export AMAZON_OTP_CODE='......'
```

## Commands

```bash
# Finish OTP on an open challenge (no extra password login)
PYTHONPATH=. python3 scripts/submit_otp_only.py

# Or full bootstrap
PYTHONPATH=. python3 -m swe_alexa bootstrap --storage artifacts/amazon_storage.json

# Run ≥40 Verified instances in parallel (reuses cookie jar; avoids re-login)
PYTHONPATH=. python3 -m swe_alexa run --limit 40 --workers 2 --wait 55 \
  --out results/run40_live --storage artifacts/amazon_storage.json
```

## Repo layout

| Path | Purpose |
| --- | --- |
| `swe_alexa/` | Playwright Alexa/Rufus client, prompts, patch extractor, parallel runner, grader |
| `scripts/` | Probes + OTP helpers |
| `results/run40_live/` | Live signed-in 40-instance preds/trajectories/grades |
| `RESULTS_DETAILED.md` | Full write-up |
| `PROBE_REPORT.md` | amazon.com discovery notes |

## Limitations

1. Rufus composer `maxlength=500` → prompts are compacted.
2. Alexa for Shopping is a **shopping** assistant; coding refusal is expected and was observed live.
3. Official Docker SWE-bench harness may be unavailable in some VMs; empty-patch sets grade as 0% offline.
