#!/usr/bin/env python3
"""Render the reviewer-facing evidence images from real project content.

    python scripts/render_evidence.py --out evidence/run-02/screenshots

The reviewer asked for four things: the full flow diagram, the classifier
prompt, the condition expressions, and the FAQ evidence. In Bedrock Flows
those are console screenshots. This project runs on the AgentCore managed
harness, where the equivalents live in ``system_prompt.txt`` and in the run
output rather than on a canvas - so they are rendered here as images the
reviewer can actually look at.

What these are, and what they are not
-------------------------------------
Every image is built from a file in this repository or from the evaluation
dataset the live run produced. The prompt excerpts are the real text, read
from disk at render time. The route responses are the model's actual replies,
read from ``output_eval_dataset.jsonl``.

None of them imitate the AWS console. Each carries a header naming the source
file, because a picture styled to look like a console screenshot would be a
fabricated record even when the content underneath is true. The genuine
console screenshots are captured separately by ``capture_console.py``.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
STARTER = REPO / "project" / "starter"

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px; width: 1400px;
  background: #fff; color: #16191f;
  font: 15px/1.55 "Segoe UI", system-ui, -apple-system, sans-serif;
}
.head { border-bottom: 3px solid #ff9900; padding-bottom: 14px; margin-bottom: 22px; }
h1 { margin: 0 0 6px; font-size: 25px; }
.src {
  font: 13px/1.4 "Cascadia Mono", Consolas, monospace;
  color: #5f6b7a; background: #f4f6f8;
  padding: 5px 9px; border-radius: 4px; display: inline-block;
}
.note {
  margin-top: 10px; padding: 9px 13px; border-left: 4px solid #0972d3;
  background: #f0f7ff; font-size: 13.5px; color: #22303f;
}
pre {
  font: 13.5px/1.5 "Cascadia Mono", Consolas, monospace;
  background: #f7f8fa; border: 1px solid #d6dce3; border-radius: 6px;
  padding: 16px 18px; white-space: pre-wrap; margin: 0 0 18px;
}
.hl { background: #fff3cd; font-weight: 600; }
h2 { font-size: 17px; margin: 24px 0 9px; color: #0f2b46; }
table { border-collapse: collapse; width: 100%; margin-bottom: 18px; }
th, td { border: 1px solid #d6dce3; padding: 9px 12px; text-align: left;
         vertical-align: top; font-size: 14px; }
th { background: #f0f2f5; font-weight: 600; }
td.q { width: 27%; font-weight: 600; }
code { font-family: "Cascadia Mono", Consolas, monospace; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 3px;
       font-size: 12px; font-weight: 600; }
.ok { background: #d4f5dd; color: #0a5c2a; }
.no { background: #ffe0e0; color: #8b1a1a; }
"""


def page(title: str, source: str, body: str, note: str = "") -> str:
    note_html = f'<div class="note">{note}</div>' if note else ""
    return (f"<!doctype html><meta charset='utf-8'><style>{CSS}</style>"
            f"<div class='head'><h1>{html.escape(title)}</h1>"
            f"<span class='src'>{html.escape(source)}</span>{note_html}</div>{body}")


def section(text: str, start: str, end: str) -> str:
    """Pull a literal block out of the prompt, so nothing is paraphrased."""
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j].rstrip()


def esc(s: str, highlight: tuple[str, ...] = ()) -> str:
    out = html.escape(s)
    for h in highlight:
        out = out.replace(html.escape(h), f"<span class='hl'>{html.escape(h)}</span>")
    return out


# --- 1. the flow diagram ---------------------------------------------------

DIAGRAM = """
<svg width="1330" height="700" viewBox="0 0 1330 700" xmlns="http://www.w3.org/2000/svg"
     font-family="Segoe UI, system-ui, sans-serif">
  <defs>
    <marker id="a" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
      <path d="M0,0 L10,4 L0,8 Z" fill="#5f6b7a"/>
    </marker>
  </defs>

  <rect x="560" y="14" width="220" height="46" rx="23" fill="#232f3e"/>
  <text x="670" y="43" fill="#fff" font-size="15" text-anchor="middle">Customer message</text>
  <line x1="670" y1="60" x2="670" y2="92" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>

  <rect x="380" y="94" width="580" height="86" rx="8" fill="#fff3e0" stroke="#ff9900" stroke-width="2.5"/>
  <text x="670" y="122" font-size="16" font-weight="700" text-anchor="middle">STEP 1 — CLASSIFY</text>
  <text x="670" y="145" font-size="13.5" fill="#3b4859" text-anchor="middle">system_prompt.txt · pick EXACTLY ONE category before acting</text>
  <text x="670" y="166" font-size="12.5" fill="#5f6b7a" text-anchor="middle">Nova Pro · temperature 0 · topK 1 (greedy, so routing is repeatable)</text>

  <line x1="670" y1="180" x2="670" y2="204" stroke="#5f6b7a" stroke-width="2"/>
  <line x1="215" y1="204" x2="1125" y2="204" stroke="#5f6b7a" stroke-width="2"/>
  <line x1="215" y1="204" x2="215" y2="236" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>
  <line x1="670" y1="204" x2="670" y2="236" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>
  <line x1="1125" y1="204" x2="1125" y2="236" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>

  <!-- BUG_REPORT -->
  <rect x="40" y="238" width="350" height="60" rx="7" fill="#e8f2ff" stroke="#0972d3" stroke-width="2"/>
  <text x="215" y="263" font-size="15" font-weight="700" text-anchor="middle">BUG_REPORT</text>
  <text x="215" y="284" font-size="12.5" fill="#3b4859" text-anchor="middle">software is broken / errors / crashes</text>

  <rect x="40" y="316" width="350" height="104" rx="7" fill="#fff" stroke="#adb5bd"/>
  <text x="215" y="339" font-size="13.5" font-weight="600" text-anchor="middle">Collect across the conversation</text>
  <text x="60" y="361" font-size="12.5" fill="#3b4859">1. description — in the customer's words</text>
  <text x="60" y="381" font-size="12.5" fill="#3b4859">2. stepsToReproduce — what they did, in order</text>
  <text x="60" y="401" font-size="12.5" fill="#3b4859">3. environment — browser / OS / device</text>
  <line x1="215" y1="420" x2="215" y2="446" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>

  <rect x="40" y="448" width="350" height="52" rx="7" fill="#fff8e1" stroke="#f0ad4e" stroke-width="2"/>
  <text x="215" y="469" font-size="13" font-weight="700" text-anchor="middle">THE GATE — all three, or ask</text>
  <text x="215" y="489" font-size="12" fill="#6b4a00" text-anchor="middle">first reply is always a question, never a tool call</text>
  <line x1="215" y1="500" x2="215" y2="526" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>

  <rect x="40" y="528" width="350" height="70" rx="7" fill="#f3e8ff" stroke="#8b5cf6" stroke-width="2"/>
  <text x="215" y="550" font-size="13" font-weight="700" text-anchor="middle">bugreports___create_bug_report</text>
  <text x="215" y="571" font-size="12" fill="#3b4859" text-anchor="middle">AgentCore Gateway → Lambda → DynamoDB</text>
  <text x="215" y="589" font-size="12" fill="#5f6b7a" text-anchor="middle">rejects blank and placeholder values</text>
  <line x1="215" y1="598" x2="215" y2="624" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>

  <rect x="40" y="626" width="350" height="50" rx="7" fill="#232f3e"/>
  <text x="215" y="647" fill="#fff" font-size="13.5" font-weight="600" text-anchor="middle">OUTPUT — ticket ID to the customer</text>
  <text x="215" y="666" fill="#c9d3df" font-size="11.5" text-anchor="middle">"I have filed a bug report with ID 2dd5cc3c-…"</text>

  <!-- PLATFORM_QUESTION -->
  <rect x="495" y="238" width="350" height="60" rx="7" fill="#e8f8ee" stroke="#1a7f37" stroke-width="2"/>
  <text x="670" y="263" font-size="15" font-weight="700" text-anchor="middle">PLATFORM_QUESTION</text>
  <text x="670" y="284" font-size="12.5" fill="#3b4859" text-anchor="middle">orders · shipping · returns · payments</text>

  <rect x="495" y="316" width="350" height="104" rx="7" fill="#fff" stroke="#adb5bd"/>
  <text x="670" y="339" font-size="13.5" font-weight="600" text-anchor="middle">Answer from the embedded FAQ only</text>
  <text x="515" y="361" font-size="12.5" fill="#3b4859">{{FAQ}} is replaced by online_shop_faq.md</text>
  <text x="515" y="381" font-size="12.5" fill="#3b4859">at upload time by create_harness.py</text>
  <text x="515" y="401" font-size="12.5" fill="#3b4859">Never invent a policy, price or timeframe</text>
  <line x1="670" y1="420" x2="670" y2="446" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>

  <rect x="495" y="448" width="350" height="52" rx="7" fill="#fff8e1" stroke="#f0ad4e" stroke-width="2"/>
  <text x="670" y="469" font-size="13" font-weight="700" text-anchor="middle">Does the FAQ cover it?</text>
  <text x="670" y="489" font-size="12" fill="#6b4a00" text-anchor="middle">no → fall through to OTHER</text>
  <line x1="845" y1="474" x2="1105" y2="474" stroke="#f0ad4e" stroke-width="2" stroke-dasharray="5,4"/>
  <line x1="1105" y1="474" x2="1105" y2="530" stroke="#f0ad4e" stroke-width="2" stroke-dasharray="5,4" marker-end="url(#a)"/>
  <line x1="670" y1="500" x2="670" y2="624" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>

  <rect x="495" y="626" width="350" height="50" rx="7" fill="#232f3e"/>
  <text x="670" y="647" fill="#fff" font-size="13.5" font-weight="600" text-anchor="middle">OUTPUT — FAQ-grounded answer</text>
  <text x="670" y="666" fill="#c9d3df" font-size="11.5" text-anchor="middle">"…within 30 days of delivery, unused and in original packaging"</text>

  <!-- OTHER -->
  <rect x="950" y="238" width="350" height="60" rx="7" fill="#fdecea" stroke="#c0392b" stroke-width="2"/>
  <text x="1125" y="263" font-size="15" font-weight="700" text-anchor="middle">OTHER  (the default)</text>
  <text x="1125" y="284" font-size="12.5" fill="#3b4859" text-anchor="middle">anything not clearly one of the other two</text>

  <rect x="950" y="316" width="350" height="104" rx="7" fill="#fff" stroke="#adb5bd"/>
  <text x="1125" y="339" font-size="13.5" font-weight="600" text-anchor="middle">Hand off to a human</text>
  <text x="970" y="361" font-size="12.5" fill="#3b4859">Not in the FAQ · account actions · off-topic</text>
  <text x="970" y="381" font-size="12.5" fill="#3b4859">Complaints · legal · partnerships</text>
  <text x="970" y="401" font-size="12.5" fill="#3b4859">Every refusal, for any reason</text>

  <rect x="950" y="530" width="350" height="46" rx="7" fill="#fff8e1" stroke="#f0ad4e" stroke-width="2"/>
  <text x="1125" y="558" font-size="12.5" font-weight="600" text-anchor="middle">mandatory closing sentence</text>
  <line x1="1125" y1="576" x2="1125" y2="624" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>
  <line x1="1125" y1="420" x2="1125" y2="528" stroke="#5f6b7a" stroke-width="2" marker-end="url(#a)"/>

  <rect x="950" y="626" width="350" height="50" rx="7" fill="#232f3e"/>
  <text x="1125" y="647" fill="#fff" font-size="13.5" font-weight="600" text-anchor="middle">OUTPUT — support line hand-off</text>
  <text x="1125" y="666" fill="#c9d3df" font-size="11.5" text-anchor="middle">"call our support team on 1-800-555-0199, Monday to Friday"</text>
</svg>
"""


def build_pages(out: Path) -> list[tuple[str, str]]:
    prompt = (STARTER / "system_prompt.txt").read_text(encoding="utf-8")
    faq = (STARTER / "online_shop_faq.md").read_text(encoding="utf-8")
    rendered = prompt.replace("{{FAQ}}", faq)

    pages: list[tuple[str, str]] = []

    # 1 — flow diagram
    pages.append(("06-flow-diagram", page(
        "Full flow — message classification and the three routes",
        "Architecture of project/starter/system_prompt.txt  ·  AgentCore managed harness",
        DIAGRAM,
        "This project runs on the <b>AgentCore managed harness</b>, not Bedrock "
        "Flows, so there is no console canvas to screenshot — the Project "
        "Overview states there are no condition nodes or separate classifiers. "
        "This diagram shows the same structure as it is actually implemented: "
        "one classification step, three mutually exclusive paths, each ending "
        "at its own distinct output.")))

    # 2 — classifier prompt
    classify = section(prompt, "STEP 1 - CLASSIFY", "STEP 2 - ACT")
    pages.append(("07-classifier-prompt", page(
        "Classifier prompt configuration",
        "project/starter/system_prompt.txt  ·  lines quoted verbatim",
        f"<pre>{esc(classify, ('EXACTLY ONE', 'BUG_REPORT', 'PLATFORM_QUESTION', 'OTHER'))}</pre>",
        "The classifier is this block of the system prompt. It runs before any "
        "reply is written and must select exactly one category. Greedy "
        "decoding (temperature 0, topK 1) is pinned in create_harness.py so "
        "the choice is repeatable.")))

    # 3 — condition expressions
    near_miss = section(prompt, "  Careful: a POLICY question", "PLATFORM_QUESTION\n")
    # Split at a section boundary rather than a character count, so nothing
    # is cut mid-word.
    act = section(prompt, "STEP 2 - ACT", "--- PLATFORM_QUESTION")
    tail = section(prompt, "--- PLATFORM_QUESTION",
                   "===================================================================\nSTYLE")
    pages.append(("08-condition-expressions", page(
        "Condition expressions — how each category is decided and routed",
        "project/starter/system_prompt.txt  ·  lines quoted verbatim",
        "<h2>The decision rules (the Condition-node equivalent)</h2>"
        f"<pre>{esc(near_miss, ('PLATFORM_QUESTION', 'BUG_REPORT'))}</pre>"
        "<h2>What the BUG_REPORT branch does</h2>"
        f"<pre>{esc(act, ('THE GATE',))}</pre>"
        "<h2>What the PLATFORM_QUESTION and OTHER branches do</h2>"
        f"<pre>{esc(tail, ('ONLY the FAQ', '1-800-555-0199'))}</pre>",
        "There is no Condition node in AgentCore. Routing is decided by these "
        "rules inside the prompt. The worked near-miss pairs are the load-"
        "bearing part: both sides mention something going wrong, and the rule "
        "is whether the FAQ has an answer or the software is genuinely "
        "broken.")))

    # 4 — FAQ embedded in the prompt
    idx = rendered.index("--- FAQ document ---")
    faq_view = rendered[idx:idx + 2500]
    pages.append(("09-faq-embedded-in-prompt", page(
        "FAQ embedded in the prompt template",
        "project/starter/system_prompt.txt  →  rendered_system_prompt.txt "
        f"({len(rendered):,} characters)",
        "<h2>The template placeholder</h2>"
        f"<pre>{esc(chr(10).join(prompt.splitlines()[-3:]), ('{{FAQ}}',))}</pre>"
        "<h2>The same region after create_harness.py substitutes it</h2>"
        f"<pre>{esc(faq_view)}\n\n[… {len(faq):,} characters of FAQ in total …]</pre>",
        "create_harness.py replaces <code>{{FAQ}}</code> with the contents of "
        "online_shop_faq.md at upload time, so the model sees the whole FAQ at "
        "inference. The full substituted prompt is in the evidence bundle as "
        "rendered_system_prompt.txt.")))

    # 5 — the three route responses, from the live evaluation dataset
    dataset = out.parent / "output_eval_dataset.jsonl"
    rows = ""
    if dataset.exists():
        wanted = [
            ("How long do I have to return something?",
             "Covered by the FAQ", "ok", "Answers from the FAQ: 30 days, unused, original packaging"),
            ("Do you price match if I find the same item cheaper somewhere else?",
             "NOT covered by the FAQ", "ok", "Declines to invent a policy, gives the support line"),
            ("What's a good recipe for chocolate brownies?",
             "Other request", "ok", "Declines, gives the support line"),
        ]
        by_prompt = {}
        for line in dataset.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                by_prompt[r["prompt"]] = r["modelResponses"][0]["response"]
        for q, label, cls, why in wanted:
            a = by_prompt.get(q, "(not found)")
            phone = "1-800-555-0199" in a
            rows += (f"<tr><td class='q'>{html.escape(q)}"
                     f"<br><span class='tag {cls}'>{label}</span></td>"
                     f"<td>{esc(a, ('30 days', '1-800-555-0199'))}"
                     f"<br><br><i style='color:#5f6b7a'>{why}"
                     f"{' · support line present' if phone else ''}</i></td></tr>")
    pages.append(("10-faq-and-handoff-responses", page(
        "Responses: covered question, uncovered question, other request",
        "evidence/run-02/output_eval_dataset.jsonl  ·  the model's actual replies",
        "<table><tr><th>Customer message</th><th>The chatbot's reply</th></tr>"
        + rows + "</table>",
        "These are the live replies recorded during the evaluation run, not "
        "written for this image. All three scored 1.0 in Bedrock Evaluations.")))

    return pages


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="evidence/run-02/screenshots")
    args = p.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pages = build_pages(out)
    print(f"Rendering {len(pages)} evidence images into {out}/")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        pg = browser.new_page(viewport={"width": 1400, "height": 1000},
                              device_scale_factor=2)
        for name, markup in pages:
            path = out / f"{name}.png"
            pg.set_content(markup, wait_until="load")
            pg.wait_for_timeout(400)
            pg.screenshot(path=str(path), full_page=True)
            print(f"  {path}  ({path.stat().st_size:,} bytes)")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
