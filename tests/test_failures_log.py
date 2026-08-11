"""Mini-spec V24 (docs/PLAN.md, Phase F) — log lỗi tập trung `failures.jsonl`."""
from __future__ import annotations

import json
import os

from autodub.failures_log import append_failure, failures_path


def test_failures_path_sits_next_to_state_path(tmp_path):
    state_path = str(tmp_path / "batch_state.json")
    assert failures_path(state_path) == str(tmp_path / "failures.jsonl")


def test_append_creates_file_and_directory(tmp_path):
    path = str(tmp_path / "nested" / "failures.jsonl")
    append_failure({"video": "a"}, path)
    assert os.path.isfile(path)


def test_append_is_additive_not_overwriting(tmp_path):
    path = str(tmp_path / "failures.jsonl")
    append_failure({"video": "a", "error": "e1"}, path)
    append_failure({"video": "b", "error": "e2"}, path)
    lines = open(path, encoding="utf-8").read().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["video"] == "a"
    assert json.loads(lines[1])["video"] == "b"


def test_unicode_preserved_not_escaped(tmp_path):
    path = str(tmp_path / "failures.jsonl")
    append_failure({"video": "tiếng Việt có dấu"}, path)
    content = open(path, encoding="utf-8").read()
    assert "tiếng Việt có dấu" in content
