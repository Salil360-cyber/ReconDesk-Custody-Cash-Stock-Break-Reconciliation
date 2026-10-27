"""
Synthetic custody dataset generator.

Creates two pairs of files that a custody operations team reconciles every day:

  Cash reconciliation
    data/cash_ledger.csv                 internal books (what we think moved)
    data/custodian_cash_statement.csv    custodian / bank statement (what actually moved)

  Stock (position) reconciliation
    data/internal_positions.csv          internal holdings per account and ISIN
    data/custodian_positions.csv         custodian / depository holdings

  Reference data
    data/security_master.csv             ISIN, name, currency, price

  Ground truth
    data/injected_breaks.json            every break that was deliberately injected,
                                         so the engine's results can be checked
                                         (see tests/test_engine.py)

All data is synthetic. Account names and ISINs are invented.
"""

import csv
import json
import os
import random
import sys
from datetime import timedelta

from config import AS_OF_DATE

SEED = 42
DATA_DIR = "data"

ACCOUNTS = [
    ("ACC-1001", "Northfield Pension Trust"),
    ("ACC-1002", "Blue Ridge Equity Fund"),
    ("ACC-1003", "Sahyadri Growth Fund"),
    ("ACC-1004", "Coastal Insurance Co."),
    ("ACC-1005", "Meridian Global Fund"),
]

SECURITIES = [
    # isin, name, currency, price
    ("INE101S01019", "Aravali Power Ltd", "INR", 412.50),
    ("INE102S01017", "Deccan Steel Ltd", "INR", 158.20),
    ("INE103S01015", "Konkan Ports Ltd", "INR", 1275.00),
    ("INE104S01013", "Narmada Pharma Ltd", "INR", 2310.40),
    ("INE105S01011", "Vindhya Cement Ltd", "INR", 865.75),
    ("INE106S01019", "Godavari Foods Ltd", "INR", 342.10),
    ("INE107S01017", "Satpura Telecom Ltd", "INR", 96.30),
    ("INE108S01015", "Kaveri Finance Ltd", "INR", 1540.00),
    ("US9Z01S10017", "Harbor Tech Inc", "USD", 182.40),
    ("US9Z02S10015", "Summit Health Corp", "USD", 74.90),
    ("US9Z03S10013", "Pioneer Energy Inc", "USD", 51.25),
]

TXN_TYPES = ["TRADE_SETTLEMENT", "TRADE_SETTLEMENT", "TRADE_SETTLEMENT",
             "DIVIDEND", "COUPON", "FEE", "FX_CONVERSION"]

N_CLEAN_CASH = 170


def rng_amount(rnd, txn_type):
    if txn_type == "TRADE_SETTLEMENT":
        return round(rnd.choice([-1, 1]) * rnd.uniform(50_000, 5_000_000), 2)
    if txn_type in ("DIVIDEND", "COUPON"):
        return round(rnd.uniform(5_000, 500_000), 2)
    if txn_type == "FEE":
        return round(-rnd.uniform(500, 20_000), 2)
    if txn_type == "FX_CONVERSION":
        return round(rnd.choice([-1, 1]) * rnd.uniform(100_000, 3_000_000), 2)
    if txn_type == "CORPORATE_ACTION_CASH":
        return round(rnd.uniform(10_000, 300_000), 2)
    raise ValueError(txn_type)


def main(data_dir=DATA_DIR, seed=SEED):
    rnd = random.Random(seed)
    os.makedirs(data_dir, exist_ok=True)

    # random (not sequential) reference numbers, so breaks can't be spotted by ref order
    ref_pool = rnd.sample(range(100_000, 1_000_000), 500)

    def new_ref():
        return f"CSH{ref_pool.pop()}"

    def rand_date(max_back=22, min_back=0):
        return AS_OF_DATE - timedelta(days=rnd.randint(min_back, max_back))

    def currency_for(txn_type):
        if txn_type == "FX_CONVERSION":
            return "INR"
        return "USD" if rnd.random() < 0.2 else "INR"

    def make_txn(txn_type=None, min_back=0, max_back=None):
        # Breaks are mostly recent (worked daily); clean history goes back ~3 weeks.
        if max_back is None:
            max_back = 22 if clean else rnd.choice([1, 2, 3, 4, 6, 9])
        txn_type = txn_type or rnd.choice(TXN_TYPES)
        acc = rnd.choice(ACCOUNTS)[0]
        return {
            "ref_id": new_ref(),
            "account_id": acc,
            "value_date": rand_date(max_back=max(max_back, min_back), min_back=min_back).isoformat(),
            "txn_type": txn_type,
            "currency": currency_for(txn_type),
            "amount": rng_amount(rnd, txn_type),
        }

    books, custodian, truth = [], [], []

    def expect(ref, status, cause):
        truth.append({"recon": "CASH", "key": ref, "status": status, "cause": cause})

    clean = True
    # 1. Clean matches
    for _ in range(N_CLEAN_CASH):
        t = make_txn()
        books.append(dict(t))
        custodian.append(dict(t))

    clean = False
    # 2. Rounding differences inside tolerance (should NOT be breaks)
    for _ in range(3):
        t = make_txn("TRADE_SETTLEMENT")
        books.append(dict(t))
        c = dict(t)
        c["amount"] = round(t["amount"] + 0.01, 2)
        custodian.append(c)
        expect(t["ref_id"], "MATCHED_WITHIN_TOLERANCE", None)

    # 3. Timing differences: custodian value date 1-3 days later
    for _ in range(8):
        t = make_txn("TRADE_SETTLEMENT", min_back=4, max_back=7)
        books.append(dict(t))
        c = dict(t)
        d = AS_OF_DATE.fromisoformat(t["value_date"]) + timedelta(days=rnd.randint(1, 3))
        c["value_date"] = d.isoformat()
        custodian.append(c)
        expect(t["ref_id"], "TIMING_DIFF", "SETTLEMENT_LAG")

    # 4a. Amount differences: withholding tax deducted on income
    for _ in range(2):
        t = make_txn("DIVIDEND")
        books.append(dict(t))
        c = dict(t)
        c["amount"] = round(t["amount"] * rnd.choice([0.80, 0.85, 0.90]), 2)
        custodian.append(c)
        expect(t["ref_id"], "AMOUNT_DIFF", "WITHHOLDING_TAX")

    # 4b. Amount differences: broker charges / stamp duty not booked
    for _ in range(2):
        t = make_txn("TRADE_SETTLEMENT")
        books.append(dict(t))
        c = dict(t)
        charges = round(abs(t["amount"]) * rnd.uniform(0.001, 0.006), 2)
        c["amount"] = round(t["amount"] - charges, 2)
        custodian.append(c)
        expect(t["ref_id"], "AMOUNT_DIFF", "CHARGES_DIFF")

    # 4c. Amount differences: FX rate booked vs applied
    for _ in range(2):
        t = make_txn("FX_CONVERSION")
        books.append(dict(t))
        c = dict(t)
        c["amount"] = round(t["amount"] * rnd.uniform(0.992, 0.998), 2)
        custodian.append(c)
        expect(t["ref_id"], "AMOUNT_DIFF", "FX_RATE_DIFF")

    # 5. Missing at custodian (in books only)
    for txn_type, cause in [("DIVIDEND", "INCOME_NOT_RECEIVED"),
                            ("COUPON", "INCOME_NOT_RECEIVED"),
                            ("TRADE_SETTLEMENT", "POSSIBLE_FAILED_SETTLEMENT"),
                            ("TRADE_SETTLEMENT", "POSSIBLE_FAILED_SETTLEMENT"),
                            ("TRADE_SETTLEMENT", "POSSIBLE_FAILED_SETTLEMENT")]:
        t = make_txn(txn_type)
        books.append(t)
        expect(t["ref_id"], "MISSING_AT_CUSTODIAN", cause)

    # 6. Missing in books (on custodian statement only)
    for txn_type, cause in [("FEE", "UNBOOKED_CUSTODY_FEE"),
                            ("FEE", "UNBOOKED_CUSTODY_FEE"),
                            ("CORPORATE_ACTION_CASH", "UNBOOKED_CORPORATE_ACTION"),
                            ("TRADE_SETTLEMENT", "UNBOOKED_TRANSACTION")]:
        t = make_txn(txn_type)
        custodian.append(t)
        expect(t["ref_id"], "MISSING_IN_BOOKS", cause)

    # 7. Duplicates
    for _ in range(2):
        t = make_txn()
        books.extend([dict(t), dict(t)])
        custodian.append(dict(t))
        expect(t["ref_id"], "DUPLICATE_IN_BOOKS", "DOUBLE_BOOKING")
    t = make_txn()
    books.append(dict(t))
    custodian.extend([dict(t), dict(t)])
    expect(t["ref_id"], "DUPLICATE_AT_CUSTODIAN", "CUSTODIAN_DUPLICATE")

    rnd.shuffle(books)
    rnd.shuffle(custodian)

    cash_cols = ["ref_id", "account_id", "value_date", "txn_type", "currency", "amount"]
    write_csv(os.path.join(data_dir, "cash_ledger.csv"), cash_cols, books)
    write_csv(os.path.join(data_dir, "custodian_cash_statement.csv"), cash_cols, custodian)

    # ------------------------------------------------------------------
    # Stock positions
    # ------------------------------------------------------------------
    sec_by_isin = {s[0]: s for s in SECURITIES}
    internal_pos, custodian_pos = [], []
    for acc, _ in ACCOUNTS:
        for isin in rnd.sample(list(sec_by_isin), 9):
            qty = rnd.randrange(1_000, 50_000, 50)
            internal_pos.append({"account_id": acc, "isin": isin, "quantity": qty})
            custodian_pos.append({"account_id": acc, "isin": isin, "quantity": qty})

    def spos(acc, isin, status, cause):
        truth.append({"recon": "STOCK", "key": f"{acc}|{isin}", "status": status, "cause": cause})

    idx = rnd.sample(range(len(internal_pos)), 9)
    # Plain quantity breaks (pending delivery, wrong booking)
    for i in idx[:3]:
        # odd, small deltas (< 10%) so they can never look like a split/bonus ratio
        delta = rnd.choice([-1, 1]) * rnd.randrange(7, 99)
        custodian_pos[i]["quantity"] = max(0, internal_pos[i]["quantity"] + delta)
        spos(internal_pos[i]["account_id"], internal_pos[i]["isin"], "QTY_BREAK", "QUANTITY_MISMATCH")
    # Corporate action not booked: custodian already applied a split / bonus
    for i, ratio in zip(idx[3:5], [2.0, 1.5]):
        internal_pos[i]["quantity"] = internal_pos[i]["quantity"] // 2 * 2
        custodian_pos[i]["quantity"] = int(internal_pos[i]["quantity"] * ratio)
        spos(internal_pos[i]["account_id"], internal_pos[i]["isin"], "QTY_BREAK", "UNBOOKED_CORPORATE_ACTION")
    # Missing at custodian: books show a holding the custodian does not
    to_remove_c = idx[5:7]
    for i in to_remove_c:
        spos(internal_pos[i]["account_id"], internal_pos[i]["isin"],
             "MISSING_AT_CUSTODIAN", "POSITION_NOT_AT_CUSTODIAN")
    # Missing in books: custodian holds a position the books do not
    to_remove_i = idx[7:9]
    for i in to_remove_i:
        spos(internal_pos[i]["account_id"], internal_pos[i]["isin"],
             "MISSING_IN_BOOKS", "UNBOOKED_POSITION")

    internal_final = [p for j, p in enumerate(internal_pos) if j not in to_remove_i]
    custodian_final = [p for j, p in enumerate(custodian_pos) if j not in to_remove_c]

    pos_cols = ["account_id", "isin", "quantity"]
    write_csv(os.path.join(data_dir, "internal_positions.csv"), pos_cols, internal_final)
    write_csv(os.path.join(data_dir, "custodian_positions.csv"), pos_cols, custodian_final)

    write_csv(os.path.join(data_dir, "security_master.csv"),
              ["isin", "security_name", "currency", "price"],
              [dict(zip(["isin", "security_name", "currency", "price"], s)) for s in SECURITIES])

    with open(os.path.join(data_dir, "injected_breaks.json"), "w") as f:
        json.dump({"seed": seed, "as_of": AS_OF_DATE.isoformat(), "expected": truth}, f, indent=2)

    n_breaks = sum(1 for t in truth if t["status"] != "MATCHED_WITHIN_TOLERANCE")
    print(f"cash_ledger.csv               : {len(books)} rows")
    print(f"custodian_cash_statement.csv  : {len(custodian)} rows")
    print(f"internal_positions.csv        : {len(internal_final)} rows")
    print(f"custodian_positions.csv       : {len(custodian_final)} rows")
    print(f"Injected breaks (ground truth): {n_breaks}  -> data/injected_breaks.json")


def write_csv(path, cols, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DATA_DIR)
