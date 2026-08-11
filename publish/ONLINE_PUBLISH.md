# Publishing Alexa-Rufus-1 results online

Official boards (**Open LLM Leaderboard**, **Artificial Analysis**, full **MMLU-Pro** Space) require open weights and/or *their* evaluation harness. Alexa-Rufus-1 is a closed shopping assistant evaluated via amazon.com web UI, so those hosts will not auto-list it.

## What this repo publishes

1. **GitHub Pages board** — `docs/index.html` (enable Pages: Settings → Pages → GitHub Actions).
2. **Hugging Face model + Space** — `scripts/publish_to_hf.py` (needs `HF_TOKEN`).
3. **Structured `.eval_results/` YAML** — Hub-native format with explicit `*_slice*` / `webui` task ids so scores are not mistaken for full official runs.

## Publish to Hugging Face

```bash
export HF_TOKEN=hf_...
# optional:
# export HF_USERNAME=your-user
python3 scripts/publish_to_hf.py
```

Creates/updates:

- `https://huggingface.co/<user>/Alexa-Rufus-1`
- `https://huggingface.co/spaces/<user>/Alexa-Rufus-1-benchmarks`

## Enable GitHub Pages

After merging to `main` (or running the workflow):

1. Repo **Settings → Pages → Source: GitHub Actions**
2. Run workflow **Deploy GitHub Pages leaderboard**
3. Board URL: `https://virajshoor.github.io/SWE-Alexa/`

## Do not submit slice scores as full MMLU-Pro

The MMLU-Pro Space expects the **full** official JSON format and verification that the system is a genuine LM. Our 80-item / 4-option Rufus run is **not** that protocol — do not email it as an official Overall score.
