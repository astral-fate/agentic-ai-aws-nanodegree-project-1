# Evidence — rubric checklist

Every item the rubric's **Evidence** lines ask for, and the exact file that
satisfies it. Reviewer note: this project uses the **AgentCore managed
harness**, not Bedrock Flows — see [why that changes some artefacts](#a-note-on-the-flows-wording).

## 1. Implement Classification and Routing

| Rubric asks for | File |
|---|---|
| Screenshot of the full flow diagram | *No flow exists — see the note below.* Architecture: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) |
| Screenshot of the classifier prompt configuration | [`run-01/system_prompt.txt`](run-01/system_prompt.txt) — the `STEP 1 - CLASSIFY` block |
| Screenshot of the Condition node expressions | *No condition nodes.* The equivalent is the category definitions and near-miss table in the same file |

## 2. Implement the Bug Report Path

| Rubric asks for | File |
|---|---|
| The submitted `system_prompt.txt` showing the bug-report route and its collection rules | [`run-01/system_prompt.txt`](run-01/system_prompt.txt) — `--- BUG_REPORT ---`, including `THE GATE` |
| A transcript of a bug report showing the follow-up questions and the `[tool call] bugreports___create_bug_report` line | [`run-01/bug_report_transcript.txt`](run-01/bug_report_transcript.txt) |
| Screenshot of the `bug-report-tool-stack-bug-reports` DynamoDB table showing at least one item created by the chatbot | [`run-01/screenshots/02-dynamodb-bug-reports.png`](run-01/screenshots/02-dynamodb-bug-reports.png) — 24 items |

## 3. Implement Platform Question and Other Request Paths

| Rubric asks for | File |
|---|---|
| Screenshot of the FAQ Prompt node template showing embedded FAQ content | [`run-01/rendered_system_prompt.txt`](run-01/rendered_system_prompt.txt) — the exact 16,708-character prompt the harness received, with `{{FAQ}}` substituted. The template itself is [`run-01/system_prompt.txt`](run-01/system_prompt.txt) and the source FAQ is [`run-01/online_shop_faq.md`](run-01/online_shop_faq.md) |
| Response for a **covered** question | [`run-01/route_responses.txt`](run-01/route_responses.txt) — "How long do I have to return something?" |
| Response for an **uncovered** question | Same file — "Do you price match competitors?" → `1-800-555-0199` |
| Response for an **other-request** message | Same file — "What's a good recipe for brownies?" → `1-800-555-0199` |

## 4. Implement the Testing and Evaluation

| Rubric asks for | File |
|---|---|
| `flow-tests.json` with ≥1 entry per path | [`run-01/flow-tests.json`](run-01/flow-tests.json) — 21 cases: 6 bug, 9 platform, 6 hand-off |
| JSONL output file | [`run-01/output_eval_dataset.jsonl`](run-01/output_eval_dataset.jsonl) — 21 records |
| Screenshot of the Bedrock Evaluation job results page | [`run-01/screenshots/01b-evaluation-job-results.png`](run-01/screenshots/01b-evaluation-job-results.png) — **Correctness 0.95**, avg 0.952 over 21 prompts |
| The result's correctness score is close to 1 | **0.952** — 20 of 21 prompts scored 1.0 |
| Written observation in a README or separate text file | [`../docs/EVALUATION.md`](../docs/EVALUATION.md) |

## Everything in this folder

| File | What it is |
|---|---|
| `run-01/system_prompt.txt` | The deliverable — routing, collection rules, FAQ placeholder |
| `run-01/rendered_system_prompt.txt` | The same prompt with the FAQ substituted, as uploaded |
| `run-01/online_shop_faq.md` | The FAQ, extended with a gift-card section |
| `run-01/harness-tests.json` / `run-01/flow-tests.json` | The test suite, under both names |
| `run-01/output_eval_dataset.jsonl` | 21 records, no harness errors |
| `run-01/bug_report_transcript.txt` | The multi-turn bug report |
| `run-01/route_responses.txt` | The three route responses |
| `run-01/dynamodb_bug_reports.json` | Full scan of the ticket table |
| `run-01/eval-results/` | Per-record scores from Bedrock Evaluations |
| `run-01/eval_job.json` | Job ARN, name and results URI |
| `run-01/run_summary.txt` | Every ARN from the run |
| `run-01/screenshots/` | Console screenshots — see its own README |

## A note on the Flows wording

The rubric asks for a flow diagram, Condition node expressions and a FAQ
Prompt node template. Those are Bedrock **Flows** artefacts, and this project
is built on the **AgentCore managed harness**, which the course moved to. The
Project Overview is explicit:

> *"The centerpiece of this project is prompt engineering: all of the routing,
> information gathering, and grounding behavior lives in a single system
> prompt that you design. … There are no condition nodes or separate
> classifiers."*

So there is no canvas to screenshot. Every requirement is still met — the
classification, the three distinct paths and the embedded FAQ all exist and
are demonstrated — they live in `system_prompt.txt` and in the run output
rather than in a diagram. [`../SUBMISSION.md`](../SUBMISSION.md) maps each
rubric line to the AgentCore artefact that plays the same role.
