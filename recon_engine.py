"""
ReconDesk reconciliation engine.

Two reconciliations, both deterministic and rule-based (fully auditable):

  reconcile_cash()    internal cash ledger  vs  custodian cash statement
  reconcile_stock()   internal positions    vs  custodian positions

Every result row is classified, aged, prioritised and given a probable cause
and a next action. AI is NOT used for matching; see ai_explainer.py for the
one place where it is (optional) used.
"""

import csv
from collections import defaultdict
from datetime import date

import config

MATCH_STATUSES = {"MATCHED", "MATCHED_WITHIN_TOLERANCE"}

# Probable cause -> (plain-language explanation, next action for the ops analyst)
CAUSE_PLAYBOOK = {
    "SETTLEMENT_LAG": (
        "Same transaction, custodian value date is later than books. Usually a settlement delay.",
        "Confirm the actual settlement date with the custodian; expected to auto-clear. Escalate if it stays open past T+3."),
    "WITHHOLDING_TAX": (
        "Income received net of tax; books carry the gross amount.",
        "Book the withholding tax entry and check the applied tax rate against the client's tax status / treaty rate."),
    "CHARGES_DIFF": (
        "Small shortfall on a trade settlement, consistent with brokerage, stamp duty or exchange charges not booked.",
        "Get the contract note / charges breakdown and book the charges, or raise a claim if they look wrong."),
    "FX_RATE_DIFF": (
        "FX conversion settled at a different rate than the one booked.",
        "Compare the booked rate with the custodian's FX confirmation and book the rate difference."),
    "INCOME_NOT_RECEIVED": (
        "Expected income (dividend / coupon) is booked but not yet received at the custodian.",
        "Check the event (record date, pay date, entitlement) and chase the custodian / paying agent for the payment."),
    "POSSIBLE_FAILED_SETTLEMENT": (
        "Trade settlement is in the books but no cash moved at the custodian. The trade may have failed or is pending.",
        "Check settlement status with the custodian / counterparty; if failed, update books and inform the client."),
    "UNBOOKED_CUSTODY_FEE": (
        "Custodian debited a fee that is not in the books.",
        "Validate the fee against the fee schedule, then book it or dispute it."),
    "UNBOOKED_CORPORATE_ACTION": (
        "Custodian processed a corporate action that the books have not captured.",
        "Check the corporate action announcement and entitlement, then book the event."),
    "UNBOOKED_TRANSACTION": (
        "Cash moved at the custodian with no matching entry in the books.",
        "Identify the instruction behind the movement; book it if valid, otherwise query the custodian."),
    "DOUBLE_BOOKING": (
        "The same reference is booked more than once internally.",
        "Reverse the duplicate entry and check why the booking ran twice."),
    "CUSTODIAN_DUPLICATE": (
        "The custodian statement shows the same movement twice.",
        "Raise a query with the custodian to reverse the duplicate movement."),
    "QUANTITY_MISMATCH": (
        "Share quantity in the books differs from the custodian.",
        "Check recent trades and pending deliveries for this ISIN; correct the side that is wrong."),
    "POSITION_NOT_AT_CUSTODIAN": (
        "Books show a holding the custodian does not hold.",
        "Check whether the purchase settled and whether the securities were delivered to the right account."),
    "UNBOOKED_POSITION": (
        "Custodian holds a position that is not in the books.",
        "Find the trade or transfer behind it and book it, or ask the custodian to correct the account."),
    "AMOUNT_UNEXPLAINED": (
        "Amount differs and does not fit a known pattern.",
        "Investigate manually: pull both source records and the original instruction."),
}


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_security_master(path):
    return {r["isin"]: {"security_name": r["security_name"], "currency": r["currency"],
                        "price": float(r["price"])} for r in load_csv(path)}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def to_inr(amount, currency):
    return amount * config.FX_TO_INR.get(currency, 1.0)


def age_bucket(days):
    label = config.AGE_BUCKETS[0][1]
    for lower, name in config.AGE_BUCKETS:
        if days >= lower:
            label = name
    return label


def priority(value_inr, age_days):
    v = abs(value_inr)
    if v >= config.HIGH_VALUE_INR or age_days >= config.HIGH_AGE_DAYS:
        return "HIGH"
    if v >= config.MEDIUM_VALUE_INR or age_days >= config.MEDIUM_AGE_DAYS:
        return "MEDIUM"
    return "LOW"


def _finish(row, cause, as_of):
    """Add aging, priority, cause, explanation and next action to a result row."""
    if row["status"] in MATCH_STATUSES:
        row.update(probable_cause="", explanation="", next_action="",
                   age_days="", age_bucket="", priority="")
        return row
    age = (as_of - date.fromisoformat(row["break_date"])).days if row.get("break_date") else 0
    row["age_days"] = age
    row["age_bucket"] = age_bucket(age)
    row["priority"] = priority(row["difference_inr"], age)
    row["probable_cause"] = cause
    row["explanation"], row["next_action"] = CAUSE_PLAYBOOK[cause]
    return row


# ---------------------------------------------------------------------------
# Cash reconciliation
# ---------------------------------------------------------------------------
def _amount_cause(txn_type, books_amt, cust_amt):
    if txn_type in ("DIVIDEND", "COUPON") and books_amt > 0:
        ratio = cust_amt / books_amt
        if 0.6 <= ratio < 1:
            return "WITHHOLDING_TAX"
    if txn_type == "FX_CONVERSION":
        return "FX_RATE_DIFF"
    if txn_type == "TRADE_SETTLEMENT" and books_amt and abs(cust_amt - books_amt) / abs(books_amt) <= 0.01:
        return "CHARGES_DIFF"
    return "AMOUNT_UNEXPLAINED"


def reconcile_cash(books_rows, custodian_rows, as_of=config.AS_OF_DATE):
    books = defaultdict(list)
    for r in books_rows:
        books[r["ref_id"]].append(r)
    cust = defaultdict(list)
    for r in custodian_rows:
        cust[r["ref_id"]].append(r)

    results = []
    for ref in sorted(set(books) | set(cust)):
        b_list, c_list = books.get(ref, []), cust.get(ref, [])
        ref_row = (b_list or c_list)[0]
        currency = ref_row["currency"]
        base = {
            "recon_type": "CASH",
            "key": ref,
            "account_id": ref_row["account_id"],
            "item": ref_row["txn_type"],
            "currency": currency,
            "books_value_date": b_list[0]["value_date"] if b_list else "",
            "custodian_value_date": c_list[0]["value_date"] if c_list else "",
            "books_value": round(sum(float(r["amount"]) for r in b_list), 2) if b_list else "",
            "custodian_value": round(sum(float(r["amount"]) for r in c_list), 2) if c_list else "",
        }

        def emit(status, diff, break_date, cause):
            row = dict(base, status=status, difference=round(diff, 2),
                       difference_inr=round(to_inr(diff, currency), 2), break_date=break_date)
            results.append(_finish(row, cause, as_of))

        # Duplicates first: the counts themselves are the break.
        if len(b_list) > 1 and len(b_list) > len(c_list):
            extra = float(b_list[0]["amount"]) * (len(b_list) - max(len(c_list), 1))
            emit("DUPLICATE_IN_BOOKS", extra, b_list[0]["value_date"], "DOUBLE_BOOKING")
            continue
        if len(c_list) > 1 and len(c_list) > len(b_list):
            extra = float(c_list[0]["amount"]) * (len(c_list) - max(len(b_list), 1))
            emit("DUPLICATE_AT_CUSTODIAN", extra, c_list[0]["value_date"], "CUSTODIAN_DUPLICATE")
            continue

        if b_list and not c_list:
            t = b_list[0]["txn_type"]
            cause = "INCOME_NOT_RECEIVED" if t in ("DIVIDEND", "COUPON") else "POSSIBLE_FAILED_SETTLEMENT"
            emit("MISSING_AT_CUSTODIAN", float(b_list[0]["amount"]), b_list[0]["value_date"], cause)
            continue
        if c_list and not b_list:
            t = c_list[0]["txn_type"]
            cause = {"FEE": "UNBOOKED_CUSTODY_FEE",
                     "CORPORATE_ACTION_CASH": "UNBOOKED_CORPORATE_ACTION"}.get(t, "UNBOOKED_TRANSACTION")
            emit("MISSING_IN_BOOKS", float(c_list[0]["amount"]), c_list[0]["value_date"], cause)
            continue

        b, c = b_list[0], c_list[0]
        b_amt, c_amt = float(b["amount"]), float(c["amount"])
        diff = c_amt - b_amt
        if abs(diff) > config.AMOUNT_TOLERANCE + 1e-9:
            emit("AMOUNT_DIFF", diff, b["value_date"], _amount_cause(b["txn_type"], b_amt, c_amt))
        elif b["value_date"] != c["value_date"]:
            emit("TIMING_DIFF", b_amt, b["value_date"], "SETTLEMENT_LAG")
        elif abs(diff) > 0:
            emit("MATCHED_WITHIN_TOLERANCE", diff, "", None)
        else:
            emit("MATCHED", 0.0, "", None)
    return results


# ---------------------------------------------------------------------------
# Stock (position) reconciliation
# ---------------------------------------------------------------------------
def _is_ca_ratio(books_qty, cust_qty):
    if books_qty <= 0 or cust_qty <= books_qty:
        return False
    ratio = cust_qty / books_qty
    return any(abs(ratio - r) < 1e-9 for r in config.CORPORATE_ACTION_RATIOS)


def reconcile_stock(books_rows, custodian_rows, security_master, as_of=config.AS_OF_DATE):
    books = {(r["account_id"], r["isin"]): int(float(r["quantity"])) for r in books_rows}
    cust = {(r["account_id"], r["isin"]): int(float(r["quantity"])) for r in custodian_rows}

    results = []
    for acc, isin in sorted(set(books) | set(cust)):
        sec = security_master.get(isin, {"security_name": "UNKNOWN", "currency": "INR", "price": 0.0})
        b_qty, c_qty = books.get((acc, isin)), cust.get((acc, isin))
        base = {
            "recon_type": "STOCK",
            "key": f"{acc}|{isin}",
            "account_id": acc,
            "item": f"{isin} {sec['security_name']}",
            "currency": sec["currency"],
            "books_value_date": as_of.isoformat(),
            "custodian_value_date": as_of.isoformat(),
            "books_value": b_qty if b_qty is not None else "",
            "custodian_value": c_qty if c_qty is not None else "",
        }
        qty_diff = (c_qty or 0) - (b_qty or 0)
        mv_diff = qty_diff * sec["price"]
        row = dict(base, difference=qty_diff,
                   difference_inr=round(to_inr(mv_diff, sec["currency"]), 2),
                   break_date=as_of.isoformat())

        if b_qty is None:
            row["status"], cause = "MISSING_IN_BOOKS", "UNBOOKED_POSITION"
        elif c_qty is None:
            row["status"], cause = "MISSING_AT_CUSTODIAN", "POSITION_NOT_AT_CUSTODIAN"
        elif abs(qty_diff) > config.QUANTITY_TOLERANCE:
            row["status"] = "QTY_BREAK"
            cause = "UNBOOKED_CORPORATE_ACTION" if _is_ca_ratio(b_qty, c_qty) else "QUANTITY_MISMATCH"
        else:
            row["status"], cause = "MATCHED", None
        results.append(_finish(row, cause, as_of))
    return results


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def summarise(cash_results, stock_results):
    def block(rows):
        total = len(rows)
        matched = sum(1 for r in rows if r["status"] in MATCH_STATUSES)
        breaks = [r for r in rows if r["status"] not in MATCH_STATUSES]
        return {
            "total": total,
            "matched": matched,
            "breaks": len(breaks),
            "match_rate": matched / total if total else 0.0,
            "break_value_inr": round(sum(abs(r["difference_inr"]) for r in breaks), 2),
            "high_priority": sum(1 for r in breaks if r["priority"] == "HIGH"),
        }
    return {"cash": block(cash_results), "stock": block(stock_results)}


def breaks_only(results):
    return [r for r in results if r["status"] not in MATCH_STATUSES]
