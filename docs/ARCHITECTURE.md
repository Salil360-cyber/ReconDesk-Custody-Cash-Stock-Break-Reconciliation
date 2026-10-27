# Architecture

## Data flow

```
 data/cash_ledger.csv ─────────┐
 data/custodian_cash_statement ┼─► reconcile_cash() ──┐
                               │                      │
 data/internal_positions.csv ──┤                      ├─► breaks ─► enrich_breaks() ─► excel_report.build_report()
 data/custodian_positions.csv ─┼─► reconcile_stock() ─┘   (rules)    (optional AI)     reports/*.xlsx
 data/security_master.csv ─────┘                                                       reports/*.csv
```

## Cash matching logic (per reference ID)

Checked in this order; the first rule that applies decides the status.

1. **Duplicate** – more entries on one side than the other (and more than one):
   `DUPLICATE_IN_BOOKS` or `DUPLICATE_AT_CUSTODIAN`. Break value = the extra entries.
2. **One-sided** – only in books: `MISSING_AT_CUSTODIAN`; only at custodian: `MISSING_IN_BOOKS`.
3. **Amount** – |custodian − books| > 0.01: `AMOUNT_DIFF`.
4. **Date** – same amount, different value date: `TIMING_DIFF`.
5. **Rounding** – difference > 0 but ≤ 0.01: `MATCHED_WITHIN_TOLERANCE`.
6. Otherwise `MATCHED`.

Amount is checked before date on purpose: a payment that is both late and short
is an amount problem first.

### Probable cause for amount breaks

| Condition | Cause |
|---|---|
| Dividend/coupon, custodian 60–99% of books | `WITHHOLDING_TAX` |
| FX conversion | `FX_RATE_DIFF` |
| Trade settlement, difference ≤ 1% | `CHARGES_DIFF` |
| Anything else | `AMOUNT_UNEXPLAINED` |

## Stock matching logic (per account + ISIN)

1. Only at custodian → `MISSING_IN_BOOKS`
2. Only in books → `MISSING_AT_CUSTODIAN`
3. Quantities differ → `QTY_BREAK`
   - if custodian qty ÷ books qty equals a known split/bonus ratio
     (1.1, 1.2, 1.25, 1.5, 2, 3, 4, 5, 10) → cause `UNBOOKED_CORPORATE_ACTION`
   - otherwise `QUANTITY_MISMATCH`
4. Equal → `MATCHED`

Break value for stock = quantity difference × price from the security master,
converted to INR.

## Aging and priority

- **Age** = business date − books value date (custodian date if missing in books).
- **Buckets**: 0-1, 2-3, 4-7, 8+ days.
- **Priority**: HIGH if value ≥ ₹10 lakh or age ≥ 6 days; MEDIUM if value ≥ ₹1 lakh
  or age ≥ 3 days; else LOW.

All of these live in `config.py`.

## Why rules for matching, AI only for text

| Concern | Rules | LLM |
|---|---|---|
| Same input → same output every day | Yes | Not guaranteed |
| Explainable to an auditor | Yes | Hard |
| Speed on thousands of rows | Milliseconds | Seconds per call |
| Writing a sensible, context-aware next step | Fixed template | Good at this |

So the engine decides **what** the break is; the LLM (optional) only improves
**how it is described**. If the AI call fails, nothing about the break
classification changes.

## Testing approach

`generate_data.py` writes `injected_breaks.json`, the list of every break it
deliberately created. `tests/test_engine.py` regenerates the data and asserts:

- every injected break is found, with the right type and cause
- no extra (false) breaks are raised
- rounding inside tolerance is not a break
- the v1 tolerance bugs stay fixed
