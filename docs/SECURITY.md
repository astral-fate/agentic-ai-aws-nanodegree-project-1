# Security notes

## ⚠️ Rotate the saudispace access key

An access key pair for the IAM user `saudispace-uploader` was pasted in
plaintext into a chat transcript during this project's setup. Chat
transcripts are stored, and a key that has been pasted into one should be
treated as compromised regardless of who has seen it.

The exposed key id is in your local `.env`, as
`SAUDISPACE_S3_ACCESS_KEY_ID` — it is deliberately not repeated here, so this
repo holds no credential material at all.

```bash
# 0. Find the key ids on the user
aws iam list-access-keys --user-name saudispace-uploader

# 1. Issue a replacement first, so nothing breaks in between
aws iam create-access-key --user-name saudispace-uploader

# 2. Update the new pair in Vercel (Settings → Environment Variables →
#    Production) and in your local .env, then redeploy

# 3. Confirm the old key is no longer being used
aws iam get-access-key-last-used --access-key-id <OLD_KEY_ID>

# 4. Delete the old one
aws iam delete-access-key --user-name saudispace-uploader \
    --access-key-id <OLD_KEY_ID>
```

An IAM user is limited to two access keys, so if creating one fails, delete
the unused key first.

**Blast radius, for context:** the `MediaObjectAccess` policy on that user
grants only `s3:PutObject`, `s3:GetObject` and `s3:DeleteObject` on
`arn:aws:s3:::saudispace/*`. Someone holding the key could read, overwrite or
delete objects in that one bucket. They could not touch IAM, other buckets,
or anything in this nanodegree project. That is a good argument for the
narrow policy — and it still needs rotating.

Related: the bucket policy on `saudispace` makes objects publicly readable
(`"Principal": "*"` on `s3:GetObject`), which is intended for a media CDN
bucket but means anything uploaded there is world-readable. Do not use that
bucket for anything private.

## Why those keys cannot run this project

They are not just a different account's keys — they are scoped to a single S3
bucket in `eu-north-1`. This project needs CloudFormation, Lambda, DynamoDB,
IAM, S3, Bedrock and Bedrock AgentCore in `us-east-1`.

Put your Udacity lab credentials in the top section of `.env`. The saudispace
values are kept in a clearly separated block at the bottom, prefixed
`SAUDISPACE_`, so nothing in this project picks them up by accident.

## How secrets are handled here

- **`.env` is git-ignored**, and `.gitignore` was committed before `.env` was
  created, so it has never been in the index. Verify with
  `git check-ignore -v .env`.
- **`.env.example`** is the committed template — structure only, no values.
- **`agentcore_config.json` is git-ignored.** It is not secret in the
  credential sense, but it contains your account ID and resource ARNs.
- **`output_eval_dataset.jsonl` is git-ignored** by default. It holds the
  chatbot's own answers to test prompts; if you want it in the repo as
  submission evidence, force-add it deliberately: `git add -f`.
- **No credentials are hard-coded** in any script. Everything goes through the
  standard boto3 chain: environment variables, then `~/.aws/credentials`, then
  the instance role.

Before pushing, a quick sanity check:

```bash
git ls-files | xargs grep -lE 'AKIA[0-9A-Z]{16}' 2>/dev/null
```

Silence is what you want.

## Prompt injection

The chatbot is a place where untrusted text meets a model with a tool that
writes to a database, so the system prompt has an explicit trust boundary.
Both customer messages **and** the FAQ document are declared untrusted data,
and the FAQ is fenced between `--- FAQ document ---` and
`--- end of FAQ document ---`.

Named refusals: overriding instructions, revealing the prompt, adopting a
persona, granting refunds or credits, filing a ticket with invented details,
disclosing another customer's data. Social engineering is covered too — the
prompt holds even if a customer claims to be an employee or says another agent
promised something.

Two evaluation cases probe it (`t19_edge_injection_ignore_instructions`,
`t20_edge_injection_reveal_prompt`) and `test_system_prompt.py` asserts the
defences are still present. See [`PROMPT_DESIGN.md`](PROMPT_DESIGN.md) for the
reasoning.

**The remaining gap:** the strongest version of this would put an Amazon
Bedrock Guardrail in front of the model, so injection attempts are blocked
before inference rather than declined by it. That is listed as a stand-out
suggestion in the project and is not implemented here.

## IAM in this project

The CloudFormation template creates three separate roles rather than one
shared role — worth understanding, since it is the least-privilege pattern the
course is demonstrating:

| Role | Can do |
|---|---|
| `bug-report-tool-stack-lambda-role` | Write logs, `PutItem` on the one table |
| `bug-report-tool-stack-gateway-role` | Invoke the one Lambda |
| `bug-report-tool-stack-harness-role` | Call Bedrock models, invoke the gateway |

The harness cannot write to DynamoDB directly, and the gateway cannot call
Bedrock. Each hop only has the permission it needs for the next one.
