"""Shared fixtures.

The starter scripts live in ``project/starter`` and two of them are awkward
to import:

* ``create_bug_report.py`` builds its DynamoDB table handle at *import* time
  (``boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])``), so boto3
  has to be patched before the import, not after.
* ``generate-eval-dataset.py`` has dashes in its name, so it cannot be
  imported with a plain ``import`` statement.

Both are handled here.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STARTER = REPO_ROOT / "project" / "starter"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_agentcore import (  # noqa: E402
    FakeAgentCoreRuntime,
    FakeDynamoResource,
    FakeTable,
)

TABLE_NAME = "bug-report-tool-stack-bug-reports"


def _load_module(path: Path, name: str):
    """Import a file by path, including files whose names aren't identifiers."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- paths -----------------------------------------------------------------


@pytest.fixture(scope="session")
def starter_dir() -> Path:
    return STARTER


@pytest.fixture(scope="session")
def system_prompt_text() -> str:
    return (STARTER / "system_prompt.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def faq_text() -> str:
    return (STARTER / "online_shop_faq.md").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def rendered_prompt(system_prompt_text, faq_text) -> str:
    """The prompt exactly as ``create_harness.py`` would upload it."""
    return system_prompt_text.replace("{{FAQ}}", faq_text)


@pytest.fixture(scope="session")
def harness_tests() -> dict:
    return json.loads(
        (STARTER / "harness-tests.json").read_text(encoding="utf-8")
    )


# --- the Lambda under test -------------------------------------------------


@pytest.fixture
def fake_table() -> FakeTable:
    return FakeTable(TABLE_NAME)


@pytest.fixture
def lambda_module(fake_table, monkeypatch):
    """``create_bug_report`` bound to a fake DynamoDB table.

    Reloaded per test so each one gets a clean table.
    """
    monkeypatch.setenv("TABLE_NAME", TABLE_NAME)
    monkeypatch.setattr(
        "boto3.resource", lambda *a, **k: FakeDynamoResource(fake_table)
    )
    sys.modules.pop("create_bug_report", None)
    return _load_module(STARTER / "create_bug_report.py", "create_bug_report")


@pytest.fixture
def fake_runtime(lambda_module, fake_table) -> FakeAgentCoreRuntime:
    """An offline stand-in for the AgentCore runtime, wired to the real Lambda."""
    return FakeAgentCoreRuntime(lambda_module.lambda_handler, fake_table)


# --- the eval dataset generator --------------------------------------------


@pytest.fixture
def eval_module(monkeypatch, fake_runtime):
    """``generate-eval-dataset.py`` with boto3 pointed at the fake runtime."""
    monkeypatch.setattr("boto3.client", lambda *a, **k: fake_runtime)
    sys.modules.pop("generate_eval_dataset", None)
    return _load_module(
        STARTER / "generate-eval-dataset.py", "generate_eval_dataset"
    )


@pytest.fixture
def chat_module(monkeypatch, fake_runtime):
    """``chat.py`` with boto3 pointed at the fake runtime."""
    monkeypatch.setattr("boto3.client", lambda *a, **k: fake_runtime)
    sys.modules.pop("chat", None)
    return _load_module(STARTER / "chat.py", "chat")


@pytest.fixture
def agentcore_config(tmp_path) -> Path:
    """The config file the setup scripts would have written."""
    cfg = {
        "region": "us-east-1",
        "stack_name": "bug-report-tool-stack",
        "table_name": TABLE_NAME,
        "lambda_arn": "arn:aws:lambda:us-east-1:123456789012:function:"
                      "bug-report-tool-stack-create-bug-report",
        "gateway_name": "bug-report-tool-stack-gateway",
        "gateway_id": "gw-offlinetest",
        "gateway_arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:"
                       "gateway/gw-offlinetest",
        "gateway_target_id": "tgt-offlinetest",
        "gateway_target_name": "bugreports",
        "harness_execution_role_arn": "arn:aws:iam::123456789012:role/"
                                      "bug-report-tool-stack-harness-role",
        "harness_name": "support_chatbot",
        "harness_id": "hrn-offlinetest",
        "harness_arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:"
                       "harness/hrn-offlinetest",
        "model_id": "us.amazon.nova-pro-v1:0",
    }
    path = tmp_path / "agentcore_config.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return path
