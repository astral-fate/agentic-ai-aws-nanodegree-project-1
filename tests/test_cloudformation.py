"""Checks on the two CloudFormation templates.

Deploying a broken template costs a stack rollback and several minutes, so
the cheap structural mistakes are caught here instead: a missing output that
``setup_gateway.py`` reads by name, a renamed table, a Lambda whose
TABLE_NAME no longer matches.
"""

from __future__ import annotations

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML is needed to parse the templates")


class CfnLoader(yaml.SafeLoader):
    """SafeLoader that tolerates CloudFormation's ``!Ref``/``!GetAtt`` tags."""


def _cfn_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {f"Fn::{tag_suffix.lstrip('!')}": value}


CfnLoader.add_multi_constructor("!", _cfn_tag)


@pytest.fixture(scope="module")
def tool_template(request):
    starter = request.config.rootpath / "project" / "starter"
    return yaml.load(
        (starter / "cloudformation-tool.yaml").read_text(encoding="utf-8"),
        Loader=CfnLoader,
    )


@pytest.fixture(scope="module")
def testing_template(request):
    starter = request.config.rootpath / "project" / "starter"
    return yaml.load(
        (starter / "cloudformation-testing.yaml").read_text(encoding="utf-8"),
        Loader=CfnLoader,
    )


# --- the tool stack --------------------------------------------------------


def test_tool_template_parses(tool_template):
    assert "Resources" in tool_template
    assert "Outputs" in tool_template


@pytest.mark.parametrize(
    "output",
    [
        "BugReportsTableName",
        "BugReportsTableArn",
        "LambdaFunctionArn",
        "LambdaExecutionRoleArn",
        "GatewayRoleArn",
        "HarnessExecutionRoleArn",
    ],
)
def test_tool_stack_exports_every_output_the_scripts_read(tool_template, output):
    assert output in tool_template["Outputs"]


def test_setup_gateway_reads_only_outputs_that_exist(tool_template, starter_dir):
    """setup_gateway.py indexes the outputs dict by literal key - a rename in
    the template would only show up as a KeyError at deploy time."""
    source = (starter_dir / "setup_gateway.py").read_text(encoding="utf-8")
    for key in ("LambdaFunctionArn", "GatewayRoleArn",
                "HarnessExecutionRoleArn", "BugReportsTableName"):
        assert f'outputs["{key}"]' in source
        assert key in tool_template["Outputs"]


def test_the_stack_creates_a_table_a_lambda_and_three_roles(tool_template):
    types = [r["Type"] for r in tool_template["Resources"].values()]

    assert types.count("AWS::DynamoDB::Table") == 1
    assert types.count("AWS::Lambda::Function") == 1
    assert types.count("AWS::IAM::Role") == 3


def test_the_ticket_table_is_keyed_by_ticket_id(tool_template):
    table = tool_template["Resources"]["BugReportsTable"]["Properties"]
    keys = [k["AttributeName"] for k in table["KeySchema"]]

    assert keys == ["ticketId"]


def test_the_lambda_is_told_which_table_to_write_to(tool_template):
    fn = tool_template["Resources"]["CreateBugReportFunction"]["Properties"]
    env = fn["Environment"]["Variables"]

    assert "TABLE_NAME" in env


def test_the_lambda_runs_a_supported_python(tool_template):
    fn = tool_template["Resources"]["CreateBugReportFunction"]["Properties"]

    assert fn["Runtime"].startswith("python3.")


def test_embedded_lambda_code_matches_the_standalone_file(
    tool_template, starter_dir
):
    """create_bug_report.py says it mirrors the code inside the template.
    If the two drift, what you test locally is not what AWS runs."""
    embedded = tool_template["Resources"]["CreateBugReportFunction"][
        "Properties"
    ]["Code"]["ZipFile"]
    standalone = (starter_dir / "create_bug_report.py").read_text(encoding="utf-8")

    for marker in (
        'table.put_item(Item=item)',
        '"status": "OPEN"',
        'bedrockAgentCoreToolName',
        'missing required field(s): ',
    ):
        assert marker in embedded, f"template code lost {marker!r}"
        assert marker in standalone, f"standalone code lost {marker!r}"


# --- the testing stack -----------------------------------------------------


def test_testing_stack_exports_the_bucket_and_role(testing_template):
    assert "EvalDatasetBucketName" in testing_template["Outputs"]
    assert "BedrockEvalRoleArn" in testing_template["Outputs"]


def test_testing_stack_creates_a_bucket_and_a_role(testing_template):
    types = [r["Type"] for r in testing_template["Resources"].values()]

    assert "AWS::S3::Bucket" in types
    assert "AWS::IAM::Role" in types


def test_the_eval_bucket_is_account_scoped(testing_template):
    """S3 bucket names are globally unique, so the template has to fold the
    account id in or the stack fails for the second student who deploys it."""
    bucket = testing_template["Resources"]["EvalDatasetBucket"]["Properties"]
    name = bucket["BucketName"]

    assert "AWS::AccountId" in str(name)
