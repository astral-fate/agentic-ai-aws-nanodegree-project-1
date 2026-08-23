#!/usr/bin/env python3
"""The AWS calls the screenshot capture needs, via boto3.

    python scripts/aws_helpers.py signin-url [--region us-east-1]
    python scripts/aws_helpers.py bucket [--stack bug-report-testing-stack]
    python scripts/aws_helpers.py upload <dir> --bucket B [--prefix P]
    python scripts/aws_helpers.py whoami

These were originally shelled out to the AWS CLI, which meant
``capture-evidence.ps1`` could not run on a machine without it — including
the one this project was developed on. boto3 is already a dependency, so
using it here drops the extra install.

Credentials come from the usual boto3 chain, so exporting ``AWS_ACCESS_KEY_ID``
and ``AWS_SECRET_ACCESS_KEY`` (which the PowerShell wrapper does, from .env)
is enough.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# The federated session is capped by the *intersection* of this policy and the
# user's own policy. The evidence-capture user is ReadOnlyAccess, so asking
# for "*" here still yields a read-only console session.
FEDERATION_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}],
})


def cmd_whoami(args) -> int:
    ident = boto3.client("sts", region_name=args.region).get_caller_identity()
    print(json.dumps({"account": ident["Account"], "arn": ident["Arn"]}))
    return 0


def cmd_signin_url(args) -> int:
    """Turn the current credentials into a console sign-in URL."""
    sts = boto3.client("sts", region_name=args.region)
    try:
        creds = sts.get_federation_token(
            Name="evidence-capture",
            Policy=FEDERATION_POLICY,
            DurationSeconds=args.duration,
        )["Credentials"]
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if "AccessDenied" in code or "not authorized" in str(exc):
            print(
                "GetFederationToken was denied.\n"
                "  Root credentials cannot call it at all, and an IAM user "
                "needs an explicit sts:GetFederationToken grant.\n"
                "  Run cloudshell/create-evidence-user.sh to set one up.",
                file=sys.stderr,
            )
        else:
            print(f"GetFederationToken failed: {exc}", file=sys.stderr)
        return 1

    session = urllib.parse.quote(json.dumps({
        "sessionId": creds["AccessKeyId"],
        "sessionKey": creds["SecretAccessKey"],
        "sessionToken": creds["SessionToken"],
    }))
    with urllib.request.urlopen(
        "https://signin.aws.amazon.com/federation"
        f"?Action=getSigninToken&Session={session}", timeout=30
    ) as resp:
        token = json.load(resp)["SigninToken"]

    dest = urllib.parse.quote(
        f"https://{args.region}.console.aws.amazon.com/console/home"
        f"?region={args.region}"
    )
    print("https://signin.aws.amazon.com/federation?Action=login"
          f"&Issuer=evidence-capture&Destination={dest}&SigninToken={token}")
    return 0


def cmd_bucket(args) -> int:
    cfn = boto3.client("cloudformation", region_name=args.region)
    try:
        outputs = cfn.describe_stacks(StackName=args.stack)["Stacks"][0].get("Outputs", [])
    except ClientError as exc:
        print(f"Could not read {args.stack}: {exc}", file=sys.stderr)
        return 1
    for o in outputs:
        if o["OutputKey"] == "EvalDatasetBucketName":
            print(o["OutputValue"])
            return 0
    print("EvalDatasetBucketName not found in the stack outputs", file=sys.stderr)
    return 1


def cmd_upload(args) -> int:
    src = Path(args.directory)
    if not src.is_dir():
        print(f"Not a directory: {src}", file=sys.stderr)
        return 1

    files = [f for f in sorted(src.rglob("*")) if f.is_file()]
    if not files:
        print(f"Nothing to upload in {src}", file=sys.stderr)
        return 1

    s3 = boto3.client("s3", region_name=args.region)
    prefix = args.prefix.strip("/")
    uploaded = 0
    for f in files:
        key = f"{prefix}/{f.relative_to(src).as_posix()}" if prefix else f.relative_to(src).as_posix()
        extra = {}
        if f.suffix.lower() == ".png":
            extra["ContentType"] = "image/png"
        elif f.suffix.lower() == ".md":
            extra["ContentType"] = "text/markdown"
        try:
            s3.upload_file(str(f), args.bucket, key, ExtraArgs=extra or None)
        except Exception as exc:  # noqa: BLE001 - boto3 wraps ClientError here
            if "AccessDenied" in str(exc):
                print(
                    "  s3:PutObject denied. The evidence-capture user is "
                    "read-only by design.\n"
                    "  Grant the narrow upload path from CloudShell:\n"
                    "    bash cloudshell/create-evidence-user.sh\n"
                    "  (it adds PutObject on the evidence/ prefix only, and "
                    "is safe to re-run)",
                    file=sys.stderr,
                )
                return 1
            print(f"  failed {key}: {exc}", file=sys.stderr)
            continue
        print(f"  s3://{args.bucket}/{key}  ({f.stat().st_size:,} bytes)")
        uploaded += 1

    print(f"{uploaded}/{len(files)} uploaded")
    return 0 if uploaded == len(files) else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--region", default="us-east-1")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(fn=cmd_whoami)

    su = sub.add_parser("signin-url")
    su.add_argument("--duration", type=int, default=3600)
    su.set_defaults(fn=cmd_signin_url)

    bk = sub.add_parser("bucket")
    bk.add_argument("--stack", default="bug-report-testing-stack")
    bk.set_defaults(fn=cmd_bucket)

    up = sub.add_parser("upload")
    up.add_argument("directory")
    up.add_argument("--bucket", required=True)
    up.add_argument("--prefix", default="evidence/screenshots")
    up.set_defaults(fn=cmd_upload)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
