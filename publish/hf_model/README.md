---
license: mit
tags:
  - evaluation
  - leaderboard
  - amazon
  - alexa
  - rufus
  - unofficial
library_name: n/a
---

# Alexa-Rufus-1 (unofficial web-UI eval)

**Alexa-Rufus-1** is the system name used for evaluating Amazon.com **Alexa for Shopping (Rufus)**
through the public web UI with Playwright.

This is **not** an open-weight model and **not** an Amazon-published checkpoint.
Official Open LLM Leaderboard / Artificial Analysis boards cannot ingest it (no Safetensors / no vendor API harness).

## Scores (see `.eval_results/`)

| Benchmark | n | Accuracy |
| --- | ---: | ---: |
| SWE-bench Verified | 40 | 0.0% |
| GPQA Diamond | 198 | 38.4% |
| MMLU-Pro (slice) | 80 | 81.2% |
| ARC-Challenge (slice) | 80 | 95.0% |
| OpenBookQA (slice) | 80 | 87.5% |
| GSM8K (slice) | 80 | 62.5% |
| TruthfulQA-MC (slice) | 80 | 88.8% |
| SimpleQA (slice) | 60 | 38.3% |
| Shopping-MC | 40 | 95.0% |

## Methodology

- Interface: `https://www.amazon.com` Rufus panel (`#rufus-text-area`, maxlength 500)
- Harness: https://github.com/virajshoor/SWE-Alexa
- Prompts compacted; MC framed as practice quizzes
- Except GPQA Diamond, academic suites are **sample slices** for runtime balance

## Links

- GitHub: https://github.com/virajshoor/SWE-Alexa
- PR: https://github.com/virajshoor/SWE-Alexa/pull/1
- Public board: https://virajshoor.github.io/SWE-Alexa/ (after Pages enable)
