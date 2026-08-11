#!/usr/bin/env python3
"""Unit tests for patch extraction (no network)."""

from swe_alexa.patch_extract import extract_patch


def test_fenced_diff():
    text = """Sure.\n```diff\ndiff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n```\n"""
    p = extract_patch(text)
    assert p.startswith("diff --git")
    assert "+b" in p


def test_bare_diff():
    text = "diff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -1 +1 @@\n-x\n+y\n"
    assert extract_patch(text).startswith("diff --git")


def test_no_patch():
    assert extract_patch("NO_PATCH") == ""
    assert extract_patch("I can help you find headphones") == ""


if __name__ == "__main__":
    test_fenced_diff()
    test_bare_diff()
    test_no_patch()
    print("ok")
