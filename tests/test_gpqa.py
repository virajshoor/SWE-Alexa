#!/usr/bin/env python3
from swe_alexa.gpqa import build_gpqa_prompt, extract_mc_letter


def test_extract_answer_line():
    text = "Customer question\nPractice quiz...\nANSWER:\nC\nScheduled actions"
    assert extract_mc_letter(text) == "C"


def test_extract_standalone():
    text = "....\nCustomer question\nQ stuff\nB\nScheduled actions"
    assert extract_mc_letter(text) == "B"


def test_prompt_fits():
    q = "Short question about photons?"
    choices = ["yes", "no", "maybe", "never"]
    p = build_gpqa_prompt(q, choices, max_chars=500)
    assert len(p) <= 500
    assert "ANSWER:" in p
    assert "A)" in p


def test_prompt_long_truncated():
    q = "Q" * 800
    choices = ["A" * 200, "B" * 200, "C" * 200, "D" * 200]
    p = build_gpqa_prompt(q, choices, max_chars=500)
    assert len(p) <= 500


if __name__ == "__main__":
    test_extract_answer_line()
    test_extract_standalone()
    test_prompt_fits()
    test_prompt_long_truncated()
    print("ok")
