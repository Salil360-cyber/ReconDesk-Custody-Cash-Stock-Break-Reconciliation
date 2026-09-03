# Submission Checklist — Razorpay AI Buildathon

Deadline: **September 5, 2026** (today: Sept 3 — ~2 days left)

## Required deliverables

- [ ] **Public GitHub repo** — push this folder, make sure README renders cleanly
- [ ] **5-minute pitch video** — screen recording, structure below
- [ ] **Architecture documentation** — short doc/section explaining design decisions
- [ ] **Application form submitted** at https://razorpay.com/buildathon/

## What to add before submitting (priority order)

1. **Wire the real LLM call** into `explain_exception()` in `reconcile.py`
   (replace the heuristic dict with an actual API call). This is the single
   highest-leverage change for the "AI Judgment" score — right now it's a
   stub, and a judge will notice.
2. **Push to GitHub** with clean commit history (a few honest commits >
   one giant commit — shows process, not just output)
3. **Record the pitch video** (5 min, don't overrun):
   - 30s — the problem (why reconciliation is painful, in plain words)
   - 1 min — live demo: run `generate_data.py` + `reconcile.py`, show the
     real match rate and exception list on screen
   - 1.5 min — walk through the code: why matching is rule-based, why AI
     is used only for exception explanation (this directly answers
     "AI Judgment")
   - 1 min — one failure case, explained: e.g. what happens with a
     malformed reference ID, and what you'd build next to handle it
     (this directly answers "Failure Recovery")
   - 1 min — what you'd build next if you had more time (shows scope
     awareness, not just what's finished)
4. **Architecture doc** — a few paragraphs is enough: data flow, why
   these tolerance bands, why this exception taxonomy, what's stubbed
   vs. what's real

## Judging criteria — map your video to these explicitly

| Criterion | Where to show it |
|---|---|
| Problem Taste | 30s problem framing — make it concrete, not generic |
| Build Quality | Clean repo, working code, the demo actually running live |
| AI Judgment | Explain *why* matching isn't AI but exception-explanation is |
| Failure Recovery | The one failure case walkthrough |

## Do NOT do

- Don't wire in a chatbot UI just to "look AI-powered" — it doesn't fit
  this problem and dilutes AI Judgment score
- Don't cherry-pick a clean match rate — show the full batch number,
  exceptions included, exactly as this report does
- Don't leave `explain_exception()` as the heuristic stub if you have
  time to wire a real API call — that's the one gap a judge will spot
  immediately
