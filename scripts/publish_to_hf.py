#!/usr/bin/env python3
"""Publish Alexa-Rufus-1 results to Hugging Face Hub (model + Space).

Requires HF_TOKEN with write access.
Optional: HF_USERNAME (defaults to token identity).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_MODEL = ROOT / "publish" / "hf_model"
SRC_SPACE = ROOT / "publish" / "hf_space"
SCORES = ROOT / "publish" / "alexa_rufus_1_scores.json"


def main() -> int:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print("HF_TOKEN missing; cannot publish to Hugging Face.", file=sys.stderr)
        return 2

    from huggingface_hub import HfApi, login, whoami

    login(token=token, add_to_git_credential=False)
    api = HfApi(token=token)
    user = os.environ.get("HF_USERNAME") or whoami(token=token)["name"]
    model_id = f"{user}/Alexa-Rufus-1"
    space_id = f"{user}/Alexa-Rufus-1-benchmarks"

    # sync scores into space package
    shutil.copy2(SCORES, SRC_SPACE / "alexa_rufus_1_scores.json")

    print(f"Creating/updating model repo {model_id}")
    api.create_repo(model_id, repo_type="model", exist_ok=True, private=False)
    api.upload_folder(
        folder_path=str(SRC_MODEL),
        repo_id=model_id,
        repo_type="model",
        commit_message="Publish Alexa-Rufus-1 unofficial eval results",
    )

    print(f"Creating/updating Space {space_id}")
    api.create_repo(space_id, repo_type="space", exist_ok=True, private=False, space_sdk="gradio")
    api.upload_folder(
        folder_path=str(SRC_SPACE),
        repo_id=space_id,
        repo_type="space",
        commit_message="Publish Alexa-Rufus-1 Gradio leaderboard Space",
    )

    print("Model:", f"https://huggingface.co/{model_id}")
    print("Space:", f"https://huggingface.co/spaces/{space_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
