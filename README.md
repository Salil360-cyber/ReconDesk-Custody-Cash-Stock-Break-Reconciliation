# ReconDesk — Custody Cash & Stock Break Reconciliation

A daily reconciliation control for a custody operations team. It compares the
firm's **internal books** with the **custodian's records**, finds every break,
classifies it, ages it, prioritises it, suggests the likely cause and the next
action, and produces an **Excel control report with a sign-off sheet**.

> Started as my submission for the Razorpay AI Buildathon 2026 (AI Finance
> Controller track) as a simple ledger-vs-bank matcher. Version 2 rebuilds it
> around how custody operations actually work: zero-tolerance cash breaks,
> stock (position) breaks, corporate action detection, aging and daily sign-off.

All data is **synthetic**. Account names and ISINs are invented.

---

## What it reconciles

| Reconciliation | Books side | Custodian side | Matched on |
|---|---|---|---|
| **Cash** | `cash_ledger.csv` | `custodian_cash_statement.csv` | reference ID, then amount and value date |
| **Stock (positions)** | `internal_positions.csv` | `custodian_positions.csv` | account + ISIN, then quantity |

Cash covers trade settlements, dividends, coupons, fees, FX conversions and
cash corporate actions, in INR and USD.

## Break types it detects

| Recon | Break type | Typical cause it suggests |
|---|---|---|
| Cash | `AMOUNT_DIFF` | withholding tax on income, broker charges not booked, FX rate difference |
| Cash | `TIMING_DIFF` | settlement lag (custodian value date later than books) |
| Cash | `MISSING_AT_CUSTODIAN` | dividend/coupon not received, possible failed settlement |
| Cash | `MISSING_IN_BOOKS` | custody fee not booked, cash corporate action not booked |
| Cash | `DUPLICATE_IN_BOOKS` / `DUPLICATE_AT_CUSTODIAN` | double booking on either side |
| Stock | `QTY_BREAK` | unbooked split/bonus (ratio check), or plain quantity mismatch |
| Stock | `MISSING_AT_CUSTODIAN` / `MISSING_IN_BOOKS` | undelivered purchase, unbooked position |

Every break gets: **age in days, age bucket, priority (HIGH / MEDIUM / LOW),
probable cause, plain-language explanation, and a next action**. See
[`docs/BREAK_HANDLING_SOP.md`](docs/BREAK_HANDLING_SOP.md) for how each one is worked.

## Results on the sample data (as of 2026-10-23)

```
CASH   items  199  matched  173  breaks  26  match rate  86.9%
STOCK  items   45  matched   36  breaks   9  match rate  80.0%
```

The generator records every break it injects (`data/injected_breaks.json`).
The test suite checks the engine against that ground truth: **all 35 injected
breaks are found with the correct type and cause, 0 false breaks, and the 3
paise-level rounding differences are correctly treated as matched.**

## The Excel control report

`reports/recon_report_<date>.xlsx`

| Sheet | What it's for |
|---|---|
| **Sign-off** | Match rates, break counts and values by type, and a sign-off checklist (e.g. "every HIGH break has an owner", "no break aged 8+ days"). All live formulas. |
| **Breaks** | Every open break with priority colouring. Yellow columns (Owner, Resolution Status, Comments) are for the analyst. Updating them updates the Sign-off checklist. |
| **Aging** | Break count and value by age bucket × priority. |
| **Cash Recon / Stock Recon** | Every row, matched or not — the full audit trail. |
| **Assumptions** | Every tolerance, threshold and rate used in the run. |

A flat `reports/breaks_<date>.csv` is also written for Power BI, Tableau or SQL.

## Where AI is used — and where it isn't

- **Matching and classification are rule-based.** They have to be repeatable
  and auditable; an LLM would make them slower and harder to defend to an auditor.
- **AI is optional and only rewrites the explanation and next-action text** for
  each break, in **one batched call** to Google Gemini. With no API key, the
  rule-based playbook text is used and the report says so.

## How to run

```bash
pip install -r requirements.txt
python generate_data.py              # create synthetic data in data/
python reconcile.py --no-ai          # run recon, rules-only explanations
python reconcile.py                  # same, with Gemini if GEMINI_API_KEY is set
python -m unittest discover -s tests -v
```

Optional AI setup: copy `.env.example` to `.env` and add your `GEMINI_API_KEY`.

## Project structure

```
config.py            all tolerances, thresholds, FX rates, CA ratios
generate_data.py     synthetic custody data + ground-truth file
recon_engine.py      cash + stock reconciliation, aging, priority, causes
ai_explainer.py      optional batched Gemini explanations
excel_report.py      Excel control workbook
reconcile.py         command-line entry point
tests/               ground-truth and rule tests
docs/                architecture, SOP, custody primer
data/  reports/      sample inputs and outputs
```

## What changed from v1

| v1 (buildathon) | v2 (ReconDesk) |
|---|---|
| 3% amount and 2-day date tolerance — **10 of 20 injected breaks were reported as matched** (reported 83.3% match rate; real clean rate was 66.7%) | ₹0.01 absolute tolerance; every fee, tax and timing break is caught |
| Cash only | Cash **and** stock (position) reconciliation |
| Duplicates checked on ledger side only | Both sides |
| No aging, no priority | Age buckets, HIGH/MEDIUM/LOW priority |
| Generic causes | Cause per break type and txn type, plus next action |
| Console output only | Excel control report with sign-off sheet + CSV |
| One LLM call per break with a 13 s sleep | One batched call, deprecated SDK replaced |
| No tests | Ground-truth and rule tests |

## Known limitations

- Matching assumes both sides share a reference ID. Real feeds often need
  fuzzy matching (amount + date + account) when references are missing.
- Stock breaks are aged 0 days because positions are a daily snapshot; a
  break history table would be needed to age them properly.
- FX rates for INR-equivalent reporting are fixed illustrative values.
- Data is synthetic; thresholds are sensible defaults, not tuned on real data.

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — design and data flow
- [`docs/BREAK_HANDLING_SOP.md`](docs/BREAK_HANDLING_SOP.md) — how each break is investigated and closed
- [`docs/CUSTODY_PRIMER.md`](docs/CUSTODY_PRIMER.md) — custody terms used in this project

---
Built by **Salil Gokhale** · [LinkedIn](https://www.linkedin.com/in/salil-gokhale-analytics) · [GitHub](https://github.com/Salil360-cyber)
