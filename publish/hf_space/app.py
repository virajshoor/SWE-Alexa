"""Gradio Space: Alexa-Rufus-1 unofficial benchmark board."""

from __future__ import annotations

import json
from pathlib import Path

import gradio as gr
import pandas as pd

SCORES = json.loads(Path(__file__).with_name("alexa_rufus_1_scores.json").read_text())

ORDER = [
    "swe_bench_verified",
    "gpqa_diamond",
    "mmlu_pro",
    "arc_challenge",
    "openbookqa",
    "gsm8k",
    "truthfulqa_mc",
    "simpleqa",
    "shopping_mc",
]


def table() -> pd.DataFrame:
    rows = []
    for key in ORDER:
        s = SCORES["scores"][key]
        rows.append(
            {
                "Benchmark": s["name"],
                "n": s["n"],
                "Correct": s["correct"],
                "Accuracy %": round(100 * s["accuracy"], 1),
            }
        )
    return pd.DataFrame(rows)


INTRO = """
# Alexa-Rufus-1 — unofficial LLM benchmark board

System name: **Alexa-Rufus-1** (Amazon.com Alexa for Shopping / Rufus web UI, Playwright).

This Space publishes third-party results from [virajshoor/SWE-Alexa](https://github.com/virajshoor/SWE-Alexa).
It is **not** an official Open LLM Leaderboard or Artificial Analysis entry (those require open weights / their harnesses).
"""

with gr.Blocks(title="Alexa-Rufus-1 Benchmarks") as demo:
    gr.Markdown(INTRO)
    gr.Dataframe(value=table(), interactive=False, wrap=True)
    gr.Markdown(
        "Methodology notes: Rufus `maxlength=500`; academic suites (except full GPQA Diamond) are balanced sample slices."
    )

if __name__ == "__main__":
    demo.launch()
