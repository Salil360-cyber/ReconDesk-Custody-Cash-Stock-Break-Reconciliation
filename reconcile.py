"""
Multi-source reconciliation engine.

Matches an internal ledger against a bank statement, classifies every
row into MATCHED / TIMING_DIFF / AMOUNT_DIFF / MISSING_IN_BANK /
MISSING_IN_LEDGER / DUPLICATE, and reports an honest match rate across
the FULL batch (not a cherry-picked example).

AI is used deliberately in ONE place: explaining/categorizing exceptions
that pure rule-matching leaves ambiguous.
"""

import csv
import os
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import time 
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-3.6-flash")
else:
    model = None

AMOUNT_TOLERANCE_PCT = 0.03
DATE_TOLERANCE_DAYS = 2


def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def reconcile(ledger_rows, bank_rows):
    bank_by_ref = defaultdict(list)
    for row in bank_rows:
        bank_by_ref[row["ref_id"]].append(row)

    ledger_by_ref = defaultdict(list)
    for row in ledger_rows:
        ledger_by_ref[row["ref_id"]].append(row)

    results = []
    all_refs = set(ledger_by_ref.keys()) | set(bank_by_ref.keys())

    for ref in all_refs:
        l_entries = ledger_by_ref.get(ref, [])
        b_entries = bank_by_ref.get(ref, [])

        if len(l_entries) > 1:
            results.append({
                "ref_id": ref, "status": "DUPLICATE",
                "detail": f"{len(l_entries)} ledger entries for same ref_id",
            })
            continue

        if not l_entries and b_entries:
            results.append({
                "ref_id": ref, "status": "MISSING_IN_LEDGER",
                "detail": "Present in bank feed, not recorded internally",
            })
            continue

        if l_entries and not b_entries:
            results.append({
                "ref_id": ref, "status": "MISSING_IN_BANK",
                "detail": "Recorded internally, never settled at bank",
            })
            continue

        l, b = l_entries[0], b_entries[0]
        l_amount, b_amount = float(l["amount"]), float(b["amount"])
        l_date, b_date = parse_date(l["date"]), parse_date(b["date"])

        amount_diff_pct = abs(l_amount - b_amount) / l_amount if l_amount else 0
        date_diff_days = abs((l_date - b_date).days)

        if amount_diff_pct > AMOUNT_TOLERANCE_PCT:
            results.append({
                "ref_id": ref, "status": "AMOUNT_DIFF",
                "detail": f"Ledger {l_amount} vs Bank {b_amount} "
                          f"({amount_diff_pct*100:.1f}% diff)",
            })
        elif date_diff_days > DATE_TOLERANCE_DAYS:
            results.append({
                "ref_id": ref, "status": "TIMING_DIFF",
                "detail": f"Ledger date {l['date']} vs Bank date {b['date']}",
            })
        elif amount_diff_pct > 0 or date_diff_days > 0:
            results.append({
                "ref_id": ref, "status": "MATCHED_WITH_MINOR_DIFF",
                "detail": f"amount_diff={amount_diff_pct*100:.2f}%, "
                          f"date_diff={date_diff_days}d (within tolerance)",
            })
        else:
            results.append({"ref_id": ref, "status": "MATCHED", "detail": ""})

    return results


def explain_exception(exception_row):
    """Real AI call to Gemini. Falls back to a heuristic if no API key/model."""
    heuristics = {
        "MISSING_IN_BANK": "Likely a failed/pending payment that never settled.",
        "MISSING_IN_LEDGER": "Likely an unrecorded internal transaction — check ingestion pipeline.",
        "AMOUNT_DIFF": "Likely a bank fee, currency conversion, or rounding difference.",
        "TIMING_DIFF": "Likely a settlement delay — same transaction, different processing date.",
        "DUPLICATE": "Likely a double-booking bug in the internal ledger.",
    }

    if model is None:
        return heuristics.get(exception_row["status"], "Needs manual review.") + " (heuristic fallback — no API key found)"

    prompt = (
        "You are a finance-ops assistant. In ONE short sentence, explain the "
        "most likely root cause of this bank reconciliation exception:\n"
        f"Status: {exception_row['status']}\n"
        f"Detail: {exception_row['detail']}\n"
        "Answer in one sentence, no preamble."
    )
    try:
        time.sleep(13)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return heuristics.get(exception_row["status"], "Needs manual review.") + f" (AI call failed: {e})"


def generate_report(results):
    total = len(results)
    matched = sum(1 for r in results if r["status"] in ("MATCHED", "MATCHED_WITH_MINOR_DIFF"))
    exceptions = [r for r in results if r["status"] not in ("MATCHED", "MATCHED_WITH_MINOR_DIFF")]

    print("=" * 60)
    print("RECONCILIATION REPORT")
    print("=" * 60)
    print(f"Total transactions considered : {total}")
    print(f"Matched (clean + within tol.)  : {matched}")
    print(f"Exceptions                     : {len(exceptions)}")
    print(f"Match rate                     : {matched/total*100:.1f}%")
    print(f"AI mode                        : {'Gemini (live)' if model else 'heuristic fallback'}")
    print("-" * 60)
    print("EXCEPTION LIST (every one, no cherry-picking):")
    print("-" * 60)
    for e in exceptions:
        explanation = explain_exception(e)
        print(f"[{e['status']}] ref={e['ref_id']}")
        print(f"    detail : {e['detail']}")
        print(f"    likely cause: {explanation}")
    print("=" * 60)


if __name__ == "__main__":
    if not (os.path.exists("ledger.csv") and os.path.exists("bank_statement.csv")):
        print("Run `python generate_data.py` first to create the sample datasets.")
        raise SystemExit(1)

    ledger = load_csv("ledger.csv")
    bank = load_csv("bank_statement.csv")
    results = reconcile(ledger, bank)
    generate_report(results)