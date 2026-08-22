# CloudShell — one-shot end-to-end run

Runs the entire project on real AWS: deploys both stacks, creates the
gateway and harness, drives a live multi-turn bug report, verifies the
ticket in DynamoDB, generates the evaluation dataset, and runs a Bedrock
Evaluations job.

## Run it

Open **AWS CloudShell** in **us-east-1**, then paste the single line from
[`PASTE-THIS.txt`](PASTE-THIS.txt) and press Enter.

That line reconstructs `run-all.sh` from an embedded gzip payload and runs
it — nothing else to download, clone or configure.

Prefer the readable version? Upload `run-all.sh` with **Actions → Upload
file**, then:

```bash
bash run-all.sh
```

## Options

```bash
bash run-all.sh                 # full run; resumes where it left off
RESET=1 bash run-all.sh         # rebuild the project files from scratch
SKIP_EVAL=1 bash run-all.sh     # stop before the Bedrock Evaluations job
REGION=us-east-1 bash run-all.sh
```

Re-running is safe. Finished steps are detected and skipped, so if a
CloudShell session drops mid-run, just paste it again.

## What it will not do

It never deletes working resources — your evidence survives the run. The
only deletion is recovering a stack stuck in `ROLLBACK_COMPLETE` or
`CREATE_FAILED`, which CloudFormation cannot update in place.

Teardown commands are **printed at the end** for you to run when you are
done collecting evidence.

## Prerequisite it checks for you

**Amazon Nova Pro model access**, enabled in the Bedrock console for
`us-east-1`. The script makes one tiny inference call up front and stops
with instructions if access is missing — rather than failing five minutes
later inside CloudFormation.

## Editing it

`PASTE-THIS.txt` is generated. After any change to `run-all.sh`:

```bash
bash cloudshell/regenerate-paste.sh
python -m pytest          # asserts the paste and the script agree
```

The test suite also asserts that the `system_prompt.txt` and
`harness-tests.json` inlined in the script are byte-identical to the ones
in `project/starter/`, so the CloudShell run can never deploy a stale
prompt.


---

# create-evidence-user.sh — IAM user for the screenshots

The screenshot automation signs in to the console with
`sts:GetFederationToken`. **Root credentials cannot call it** — that is an AWS
restriction, not a preference — so a small IAM user is needed.

Paste [`PASTE-CREATE-USER.txt`](PASTE-CREATE-USER.txt) into CloudShell, or
upload `create-evidence-user.sh` and run `bash create-evidence-user.sh`.

It creates a **read-only** user (`evidence-capture`) with `ReadOnlyAccess`
plus an explicit `sts:GetFederationToken` grant, makes an access key, mints a
one-click console sign-in URL, and prints the exact PowerShell command to run
on your own machine:

```powershell
$env:AWS_ACCESS_KEY_ID     = "AKIA..."
$env:AWS_SECRET_ACCESS_KEY = "..."
.\scripts\capture-evidence.ps1 -Federated
```

CloudShell has no browser, so it cannot take the screenshots itself. It
prepares the credentials; the capture runs locally.

Options:

```bash
bash create-evidence-user.sh --console   # also set a console password, so you
                                         # can stop signing in as root
bash create-evidence-user.sh --delete    # remove the user, keys and password
```

The user can read the console and change nothing. Delete it when you are
done, and wipe the printed secret with `clear && history -c`.
