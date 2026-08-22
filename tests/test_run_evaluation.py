"""The pre-flight validator in run_evaluation.py.

Its whole job is to catch dataset problems *before* an evaluation job is
created, because a bad dataset otherwise fails slowly and costs a run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from conftest import STARTER, _load_module

MODEL_ID = "my-support-chatbot"


@pytest.fixture(scope="module")
def run_eval():
    sys.modules.pop("run_evaluation", None)
    return _load_module(STARTER / "run_evaluation.py", "run_evaluation")


def _write(tmp_path: Path, records) -> Path:
    path = tmp_path / "output_eval_dataset.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8"
    )
    return path


def _record(**overrides):
    record = {
        "prompt": "How long do I have to return something?",
        "referenceResponse": "Explains the 30 day return window.",
        "modelResponses": [
            {"response": "You have 30 days.", "modelIdentifier": MODEL_ID}
        ],
    }
    record.update(overrides)
    return record


def test_a_good_dataset_passes(run_eval, tmp_path):
    path = _write(tmp_path, [_record(), _record()])

    assert run_eval.check_dataset(path, MODEL_ID) == 2


def test_a_missing_file_is_reported(run_eval, tmp_path):
    with pytest.raises(SystemExit, match="generate-eval-dataset"):
        run_eval.check_dataset(tmp_path / "nope.jsonl", MODEL_ID)


def test_an_empty_file_is_reported(run_eval, tmp_path):
    path = tmp_path / "output_eval_dataset.jsonl"
    path.write_text("", encoding="utf-8")

    with pytest.raises(SystemExit, match="empty"):
        run_eval.check_dataset(path, MODEL_ID)


def test_a_mismatched_model_identifier_is_caught(run_eval, tmp_path, capsys):
    """The failure mode this exists for: the job's inferenceSourceIdentifier
    and the file's modelIdentifier must be the same string, or Bedrock scores
    nothing."""
    bad = _record(
        modelResponses=[{"response": "hi", "modelIdentifier": "some-other-name"}]
    )
    path = _write(tmp_path, [bad])

    with pytest.raises(SystemExit):
        run_eval.check_dataset(path, MODEL_ID)

    assert "modelIdentifier" in capsys.readouterr().err


def test_a_harness_error_response_is_caught(run_eval, tmp_path, capsys):
    bad = _record(
        modelResponses=[
            {
                "response": "[HARNESS_ERROR] ValidationException: boom",
                "modelIdentifier": MODEL_ID,
            }
        ]
    )
    path = _write(tmp_path, [bad])

    with pytest.raises(SystemExit):
        run_eval.check_dataset(path, MODEL_ID)

    assert "harness error" in capsys.readouterr().err


def test_malformed_json_is_caught(run_eval, tmp_path, capsys):
    path = tmp_path / "output_eval_dataset.jsonl"
    path.write_text('{"prompt": "x"\n', encoding="utf-8")

    with pytest.raises(SystemExit):
        run_eval.check_dataset(path, MODEL_ID)

    assert "not valid JSON" in capsys.readouterr().err


def test_a_missing_required_key_is_caught(run_eval, tmp_path, capsys):
    bad = _record()
    del bad["referenceResponse"]
    path = _write(tmp_path, [bad])

    with pytest.raises(SystemExit):
        run_eval.check_dataset(path, MODEL_ID)

    assert "referenceResponse" in capsys.readouterr().err


def test_the_real_generated_dataset_passes_validation(
    run_eval, eval_module, harness_tests, tmp_path, monkeypatch
):
    """Closes the loop: what generate-eval-dataset.py writes is exactly what
    run_evaluation.py is willing to upload."""
    tests_json = tmp_path / "harness-tests.json"
    tests_json.write_text(json.dumps(harness_tests), encoding="utf-8")
    out = tmp_path / "output_eval_dataset.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "generate-eval-dataset.py",
            "--tests-json", str(tests_json),
            "--harness-arn", "arn:h",
            "--out-jsonl", str(out),
        ],
    )
    eval_module.main()

    assert run_eval.check_dataset(out, MODEL_ID) == len(harness_tests["tests"])
