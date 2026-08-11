# SWE-Alexa

Evaluate **Alexa for Shopping** (Amazon.com web UI only) on **SWE-bench Verified** by driving the chat interface with Playwright, collecting patches in parallel, then grading.

## Summary of this run

| Metric | Value |
| --- | --- |
| Dataset | `princeton-nlp/SWE-bench_Verified` (first 40 test instances) |
| Interface | https://www.amazon.com Alexa for Shopping web chat |
| Parallel workers | 4 (configured) |
| Instances completed | **40 / 40** |
| Non-empty patches | **0** |
| Offline resolved estimate | **0%** |
| Alexa chat opened | **No** (signed-out session; chat is login-gated) |

**Headline:** Alexa for Shopping on amazon.com does not expose its chat UI to signed-out browsers in this environment. All 40 instances finished with empty patches and a structured access error. Full Docker SWE-bench test execution was not required to score these empty predictions (0 nonempty → 0 resolved). Re-run with `AMAZON_EMAIL` / `AMAZON_PASSWORD` (optional `AMAZON_OTP_SECRET`) to exercise the live chat.

See [RESULTS_DETAILED.md](RESULTS_DETAILED.md) for the full methodology, probe notes, and per-instance IDs.

## Why a web harness?

SWE-bench Verified only grades `preds.jsonl` patches. Alexa for Shopping has no public coding API on amazon.com, so inference must go through the **web chat** (desktop icon / NL search when signed in).

```text
SWE-bench Verified instance
        │
        ▼
Playwright → amazon.com → Alexa for Shopping chat
        │
        ▼
parse unified diff → preds.jsonl → grade
```

## Setup

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
export AMAZON_EMAIL='...'
export AMAZON_PASSWORD='...'
# optional MFA:
export AMAZON_OTP_SECRET='...'
```

## Commands

```bash
# Login once + open Alexa chat
PYTHONPATH=. python3 -m swe_alexa bootstrap

# Run ≥40 Verified instances in parallel
PYTHONPATH=. python3 -m swe_alexa run --limit 40 --workers 4 --out results/run40

# Grade predictions only
PYTHONPATH=. python3 -m swe_alexa grade --preds results/run40/preds.jsonl --out results/grade
```

## Repo layout

| Path | Purpose |
| --- | --- |
| `swe_alexa/` | Playwright Alexa client, prompts, patch extractor, parallel runner, grader |
| `scripts/probe_alexa*.py` | Amazon.com UI probes |
| `configs/default.yaml` | Default run knobs |
| `data/verified_50.json` | Cached first 50 Verified instances |
| `results/run40/` | Predictions, trajectories, grades for the 40-instance run |
| `artifacts/probe/` | Probe HTML/JSON from amazon.com |
| `RESULTS_DETAILED.md` | Detailed results write-up |
| `PROBE_REPORT.md` | Amazon.com Alexa discovery notes |

## Important limitations

1. **Login required.** Alexa for Shopping is free for signed-in US customers on amazon.com; the chat launcher does not appear when logged out.
2. **Domain mismatch.** Alexa for Shopping is a shopping assistant (product Q&A, cart, deals), not a software-engineering agent. Even with chat access, SWE-bench coding success is expected to stay near zero unless the product is extended.
3. **Official % resolved** needs the SWE-bench Docker harness or `sb-cli`. This environment’s Docker overlay driver failed container runs; empty-patch offline grading is used when the harness cannot execute tests.
