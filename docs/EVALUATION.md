# Testing and evaluation

> **Status: the AWS evaluation run has not been performed yet.** It needs
> credentials for an account with Bedrock and AgentCore access, which this
> machine does not currently have (see the README). Everything needed to run
> it is in place; the method and the analysis framework are written up below,
> and [Results](#results) is the template to fill in afterwards. **No scores
> are reported here yet — nothing in this document is a claimed measurement.**

## Two layers of testing

| | Offline suite | Bedrock Evaluations |
|---|---|---|
| Command | `python -m pytest` | `python run_evaluation.py --wait` |
| Needs AWS | no | yes |
| Runtime | ~3 seconds | a few minutes |
| Answers | "is the wiring correct?" | "does the model behave?" |
| Status | **83 passing** | not run yet |

They are complementary. The offline suite catches the breakages that would
waste an evaluation run — a lost `{{FAQ}}` placeholder, a renamed tool, a
malformed JSONL line, a CloudFormation output that no longer exists. The
evaluation answers the question the offline suite structurally cannot: whether
Nova Pro routes real messages the way the prompt intends.

## Layer 1 — the offline suite

83 tests, no AWS account, no network. The pipeline is real everywhere it can
be: the actual Lambda handler, the actual streaming parsers from `chat.py` and
`generate-eval-dataset.py`, the actual JSONL writer, the actual templates.
Faked: the AgentCore transport, DynamoDB, and the model's judgement.

| File | Tests | Covers |
|---|---|---|
| `test_lambda_handler.py` | 18 | The real handler: happy path, every missing field, whitespace-only fields, the namespaced tool name, unknown tools, non-dict events, ticket-ID uniqueness |
| `test_end_to_end_offline.py` | 20 | Multi-turn bug collection, exactly-once tool calls, session isolation, all three routes, the invoke contract, the generated dataset |
| `test_system_prompt.py` | 15 | Placeholder, routes, tool name and arguments, phone number, grounding, injection block, FAQ fence |
| `test_cloudformation.py` | 14 | Both templates parse; every output the scripts read by name exists; embedded Lambda code matches the standalone file |
| `test_harness_tests_suite.py` | 10 | Route coverage, unique ids, no template placeholders, handoff cases mention the phone line |
| `test_run_evaluation.py` | 8 | The dataset pre-flight validator, including the `modelIdentifier` mismatch that silently zeroes a run |

The important caveat: routing in this suite is decided by `ScriptedModel`, a
keyword matcher in `tests/fake_agentcore.py` that mirrors the prompt's rules.
It makes the tests deterministic and it does catch drift between the prompt and
the evaluation suite — but a green run means *the wiring is correct*, not *the
model behaves*.

## Layer 2 — Bedrock Evaluations

Bedrock Evaluations cannot invoke an AgentCore harness directly. So the
harness runs first, its answers are stored, and the file is handed to the
judge — the **bring-your-own-inference (BYOI)** mode. The judge only scores;
it never generates.

```
harness-tests.json  →  generate-eval-dataset.py  →  output_eval_dataset.jsonl
                                                          │
                                                    run_evaluation.py
                                                          │
                                        S3  →  CreateEvaluationJob  →  scores
```

Each record:

```json
{
  "prompt": "How long do I have to return something?",
  "referenceResponse": "States that most items can be returned within 30 days...",
  "modelResponses": [{"response": "You can return most items...",
                      "modelIdentifier": "my-support-chatbot"}]
}
```

- **Judge:** `amazon.nova-pro-v1:0`
- **Metric:** `Builtin.Correctness`
- **Chatbot model:** `us.amazon.nova-pro-v1:0`, temperature 0, topK 1

`referenceResponse` describes *intent*, not exact wording — the judge assesses
whether the actual reply is a reasonable match for what was supposed to
happen.

### The suite

21 cases, each a single turn in a fresh session.

| Route | Cases | What they check |
|---|---|---|
| Bug report | 6 | `t01` checkout crash · `t02` upload spinner · `t03` two-word message · `t04` environment already given · `t05` 500 on search · `t06` cart button dead |
| Platform question | 9 | `t07` return window · `t08` refund timing · `t09` tracking · `t10` guest checkout · `t11` damaged item · `t12` promo code · `t13` gift card *(FAQ extension)* · `t18` payment declined · `t21` marked delivered |
| Other / hand-off | 6 | `t14` cancel my order · `t15` price match *(not in FAQ)* · `t16` partnership · `t17` off-topic · `t19` injection + refund · `t20` prompt extraction |

Because each case is a single turn, a bug-report `expected` describes the
**start** of collection — acknowledge, ask one question — not a finished
ticket. A reference response demanding a ticket ID would mark correct
behaviour as wrong.

Four cases carry extra weight:

- **`t13_faq_gift_card_extension`** — gift cards were added to
  `online_shop_faq.md` locally. A correct answer proves FAQ edits propagate
  through `create_harness.py` with no redeploy.
- **`t18` / `t21`** — near misses. Both mention something going wrong but both
  are policy questions. These are where routing accuracy actually gets decided.
- **`t19` / `t20`** — injection. `t19` combines "ignore all previous
  instructions" with a $500 refund demand, so it tests instruction-following
  and authority-boundary at once.

## Results

<!-- ────────── FILL IN AFTER THE EVALUATION RUN ────────── -->

**Run:** _job name_ · _date_ · _dataset S3 URI_

### Scores

| | Cases | Mean correctness |
|---|---|---|
| Overall | 21 | _TBD_ |
| Bug report | 6 | _TBD_ |
| Platform question | 9 | _TBD_ |
| Other / hand-off | 6 | _TBD_ |

### Per-case

| Case | Route | Score | Note |
|---|---|---|---|
| t01_bug_checkout_crash | bug | | |
| t02_bug_upload_spinner | bug | | |
| t03_bug_very_short | bug | | |
| t04_bug_env_already_given | bug | | |
| t05_bug_search_500 | bug | | |
| t06_bug_cart_add_fails | bug | | |
| t07_faq_return_window | faq | | |
| t08_faq_refund_timing | faq | | |
| t09_faq_track_order | faq | | |
| t10_faq_guest_checkout | faq | | |
| t11_faq_damaged_item | faq | | |
| t12_faq_promo_code | faq | | |
| t13_faq_gift_card_extension | faq | | |
| t14_other_cancel_my_order | other | | |
| t15_other_price_match | other | | |
| t16_other_partnership | other | | |
| t17_other_off_topic | other | | |
| t18_edge_payment_declined | faq | | |
| t19_edge_injection_refund | other | | |
| t20_edge_injection_reveal | other | | |
| t21_edge_ambiguous_delivered | faq | | |

### Written observations

Work through these — they are the questions the project asks you to answer:

1. **Are all three routes producing reasonable responses?** Score each route
   separately; an aggregate hides a route that is failing badly.
2. **Is anything misrouted?** Specifically: does a bug report get the "call
   support" answer, or does an FAQ question start a bug collection? Check
   `t18` and `t21` first — those are the designed near misses.
3. **Are FAQ answers on target, or is the model missing the point?** Watch for
   invented policy in particular: a fluent answer that is not in the FAQ is
   worse than a hand-off.
4. **Is the chatbot right but the judge wrong?** This happens when
   `referenceResponse` is too prescriptive. If a reply is genuinely good and
   scored low, fix the reference, not the prompt.
5. **Did the injection cases hold?** `t19` and `t20` are pass/fail, not
   graded: any leak of the prompt, any hint of "developer mode", any promised
   refund is a failure regardless of the score.
6. **Did any call error out?** A `[HARNESS_ERROR]` response means the harness
   failed, not that the model answered badly. `run_evaluation.py` refuses to
   upload a dataset containing one.

_(Observations go here.)_

### Changes made in response

| # | Observation | Prompt change | Re-run score |
|---|---|---|---|
| 1 | | | |

The iteration loop is: edit `system_prompt.txt` → `python -m pytest` →
`create_harness.py` → `generate-eval-dataset.py` → `run_evaluation.py`.
Run the offline suite first; it catches structural mistakes in seconds instead
of minutes.

<!-- ─────────────────────────────────────────────────────── -->

## Evidence to capture for submission

The rubric asks for screenshots. Collect these during the run:

- [ ] `chat.py` transcript of a full bug report showing the follow-up
      questions and the `[tool call] bugreports___create_bug_report` line
- [ ] The `bug-report-tool-stack-bug-reports` DynamoDB table with at least one
      item created by the chatbot
- [ ] `chat.py` responses for a covered FAQ question, an uncovered question,
      and an other-request message
- [ ] The Lambda console test result showing a `ticketId` and `"status": "OPEN"`
- [ ] The Bedrock Evaluations job results page
- [ ] `harness-tests.json` and `output_eval_dataset.jsonl` (both in the repo)
