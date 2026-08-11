"""Extract unified diffs / code patches from free-form Alexa replies."""

from __future__ import annotations

import re

DIFF_FENCE = re.compile(
    r"```(?:diff|patch)?\s*\n(diff --git[\s\S]*?)```",
    re.IGNORECASE,
)
BARE_DIFF = re.compile(r"(diff --git [\s\S]+?)(?:\n```|\Z)", re.IGNORECASE)
NO_PATCH = re.compile(r"^\s*NO_PATCH\s*$", re.IGNORECASE | re.MULTILINE)


def extract_patch(text: str | None) -> str:
    if not text:
        return ""
    if NO_PATCH.search(text) and "diff --git" not in text:
        return ""
    m = DIFF_FENCE.search(text)
    if m:
        return m.group(1).strip() + "\n"
    m = BARE_DIFF.search(text)
    if m:
        return m.group(1).strip() + "\n"
    # Some models return ---/+++ without diff --git header
    if re.search(r"^---\s+\S+", text, re.M) and re.search(r"^\+\+\+\s+\S+", text, re.M):
        return text.strip() + "\n"
    return ""
