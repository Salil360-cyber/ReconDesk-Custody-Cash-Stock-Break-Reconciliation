"""
Generates two synthetic datasets that simulate a real reconciliation problem:
  - ledger.csv          : internal system of record (what the business thinks happened)
  - bank_statement.csv  : external bank feed (what actually settled)

Intentional mismatches are injected so the reconciliation engine has real
work to do, and so the "exception list" in the final report is honest,
not cherry-picked.
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

N_CLEAN = 40          # transactions that match perfectly
N_TIMING = 6           # same transaction, date off by 1-2 days
N_AMOUNT_MISMATCH = 4  # small amount discrepancy (fees, rounding)
N_MISSING_IN_BANK = 5  # exists in ledger, never settled (failed payment)
N_MISSING_IN_LEDGER = 3  # exists in bank feed, not recorded internally
N_DUPLICATE = 2         # duplicate entry in ledger (double booking)

start_date = datetime(2026, 8, 1)
merchants = ["Merchant_A", "Merchant_B", "Merchant_C", "Merchant_D", "Merchant_E"]

ledger_rows = []
bank_rows = []
ref_counter = 1000


def new_ref():
    global ref_counter
    ref_counter += 1
    return f"TXN{ref_counter}"


def rand_date():
    return start_date + timedelta(days=random.randint(0, 27))


def rand_amount():
    return round(random.uniform(500, 50000), 2)


# 1. Clean matches
for _ in range(N_CLEAN):
    ref = new_ref()
    date = rand_date()
    amount = rand_amount()
    merchant = random.choice(merchants)
    ledger_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant, "settled"])
    bank_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant])

# 2. Timing mismatches (bank settles 1-2 days after ledger date)
for _ in range(N_TIMING):
    ref = new_ref()
    date = rand_date()
    amount = rand_amount()
    merchant = random.choice(merchants)
    bank_date = date + timedelta(days=random.choice([1, 2]))
    ledger_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant, "settled"])
    bank_rows.append([ref, bank_date.strftime("%Y-%m-%d"), amount, merchant])

# 3. Amount mismatches (bank fee deducted, small rounding diff)
for _ in range(N_AMOUNT_MISMATCH):
    ref = new_ref()
    date = rand_date()
    amount = rand_amount()
    merchant = random.choice(merchants)
    fee = round(amount * random.uniform(0.005, 0.02), 2)
    ledger_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant, "settled"])
    bank_rows.append([ref, date.strftime("%Y-%m-%d"), round(amount - fee, 2), merchant])

# 4. Missing in bank (payment initiated but never actually settled)
for _ in range(N_MISSING_IN_BANK):
    ref = new_ref()
    date = rand_date()
    amount = rand_amount()
    merchant = random.choice(merchants)
    ledger_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant, "pending"])
    # intentionally NOT added to bank_rows

# 5. Missing in ledger (bank shows money, internal system never recorded it)
for _ in range(N_MISSING_IN_LEDGER):
    ref = new_ref()
    date = rand_date()
    amount = rand_amount()
    merchant = random.choice(merchants)
    bank_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant])
    # intentionally NOT added to ledger_rows

# 6. Duplicate ledger entry (double booking bug)
for _ in range(N_DUPLICATE):
    ref = new_ref()
    date = rand_date()
    amount = rand_amount()
    merchant = random.choice(merchants)
    ledger_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant, "settled"])
    ledger_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant, "settled"])  # dup
    bank_rows.append([ref, date.strftime("%Y-%m-%d"), amount, merchant])

random.shuffle(ledger_rows)
random.shuffle(bank_rows)

with open("ledger.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ref_id", "date", "amount", "merchant", "status"])
    w.writerows(ledger_rows)

with open("bank_statement.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ref_id", "date", "amount", "merchant"])
    w.writerows(bank_rows)

print(f"ledger.csv: {len(ledger_rows)} rows")
print(f"bank_statement.csv: {len(bank_rows)} rows")
print("Injected: timing mismatches, amount mismatches, missing-in-bank, "
      "missing-in-ledger, duplicate bookings.")
