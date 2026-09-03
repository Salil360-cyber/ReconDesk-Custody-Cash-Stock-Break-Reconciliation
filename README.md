# Multi-Source Reconciliation Engine

Built for the Razorpay AI Buildathon 2026 — **Track 04: AI Finance Controller**

## Problem

Businesses running payments have two records of the same money: what their
internal system (ledger) *thinks* happened, and what the bank/PSP statement
*actually* shows settled. These two rarely match perfectly — timing delays,
fees, failed payments, and booking bugs create drift. Today this reconciliation
is mostly done by hand, which doesn't scale past a few hundred transactions
and hides real financial risk (unsettled money, duplicate bookings, silent
failures).

## What this does

Given two CSVs — `ledger.csv` (internal) and `bank_statement.csv` (external) —
the engine:

1. Matches every transaction by reference ID
2. Classifies each into one of: `MATCHED`, `MATCHED_WITH_MINOR_DIFF`,
   `TIMING_DIFF`, `AMOUNT_DIFF`, `MISSING_IN_BANK`, `MISSING_IN_LEDGER`,
   `DUPLICATE`
3. Reports an honest match rate across the **full batch**
4. Lists **every** exception (not a cherry-picked sample), each with a
   plain-language likely cause

## Where AI is actually used — and where it isn't

Matching itself is deterministic (amount/date/ref comparison with tolerance
bands) — that's a rules problem, not an AI problem, and forcing an LLM into
it would just make it slower and less auditable.

AI is used in exactly one place that earns it: **`explain_exception()`** in
`reconcile.py`. Turning a raw mismatch into a categorized, plain-language
likely cause is a judgment call that benefits from an LLM. The current code
ships with a heuristic fallback (zero API dependency, so it runs anywhere)
with a clearly marked integration point to plug in a real LLM call.

## Known limitations (honest, on purpose)

- Matching is reference-ID based; it does not yet do fuzzy matching when
  reference IDs themselves are missing or malformed on both sides
- `explain_exception()` ships with heuristics, not a live LLM call, by
  default — see the docstring for the exact integration point
- Tolerance bands (3% amount, 2 days) are illustrative defaults, not tuned
  against real bank data

## How to run

```bash
python generate_data.py   # creates ledger.csv + bank_statement.csv (60 synthetic txns)
python reconcile.py       # runs reconciliation, prints the full report
```

No dependencies beyond the Python standard library — runs anywhere.

## Files

- `generate_data.py` — synthetic dataset generator with intentionally
  injected mismatches (so the numbers reported are real, not cherry-picked)
- `reconcile.py` — the reconciliation engine + report generator
- `ledger.csv`, `bank_statement.csv` — generated sample data
