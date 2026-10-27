"""
ReconDesk - run the daily custody reconciliation.

    python generate_data.py          # create the synthetic data (once)
    python reconcile.py              # run cash + stock recon, write reports
    python reconcile.py --no-ai      # same, rules-only explanations

Outputs (in reports/):
    recon_report_<date>.xlsx   daily control workbook with sign-off sheet
    breaks_<date>.csv          flat break list (for Power BI / Tableau / SQL)
"""

import argparse
import csv
import os
from datetime import date

import config
from ai_explainer import enrich_breaks
from excel_report import build_report
from recon_engine import (breaks_only, load_csv, load_security_master,
                          reconcile_cash, reconcile_stock, summarise)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CSV_FIELDS = ["break_id", "recon_type", "account_id", "key", "item", "currency", "status",
              "books_value", "custodian_value", "difference", "difference_inr",
              "books_value_date", "custodian_value_date", "age_days", "age_bucket", "priority",
              "probable_cause", "explanation", "next_action"]


def run(data_dir="data", out_dir="reports", as_of=config.AS_OF_DATE, use_ai=True, quiet=False):
    p = lambda name: os.path.join(data_dir, name)  # noqa: E731
    cash = reconcile_cash(load_csv(p("cash_ledger.csv")), load_csv(p("custodian_cash_statement.csv")), as_of)
    stock = reconcile_stock(load_csv(p("internal_positions.csv")), load_csv(p("custodian_positions.csv")),
                            load_security_master(p("security_master.csv")), as_of)

    prio_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    breaks = sorted(breaks_only(cash) + breaks_only(stock),
                    key=lambda b: (prio_rank[b["priority"]], -abs(b["difference_inr"])))
    ai_mode = enrich_breaks(breaks, use_ai=use_ai)

    os.makedirs(out_dir, exist_ok=True)
    xlsx_path = os.path.join(out_dir, f"recon_report_{as_of.isoformat()}.xlsx")
    build_report(xlsx_path, cash, stock, breaks, as_of, ai_mode)   # also assigns break_id
    csv_path = os.path.join(out_dir, f"breaks_{as_of.isoformat()}.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(breaks)

    summary = summarise(cash, stock)
    if not quiet:
        print_summary(summary, breaks, as_of, ai_mode, xlsx_path, csv_path)
    return cash, stock, breaks, summary


def print_summary(summary, breaks, as_of, ai_mode, xlsx_path, csv_path):
    line = "=" * 72
    print(line)
    print(f"RECONDESK  |  Daily custody reconciliation  |  as of {as_of.isoformat()}")
    print(line)
    for name in ("cash", "stock"):
        s = summary[name]
        print(f"{name.upper():6} items {s['total']:4}  matched {s['matched']:4}  breaks {s['breaks']:3}  "
              f"match rate {s['match_rate']*100:5.1f}%  HIGH {s['high_priority']:2}  "
              f"break value INR {s['break_value_inr']:,.2f}")
    print(f"Explanations: {ai_mode}")
    print("-" * 72)
    counts = {}
    for b in breaks:
        k = (b["recon_type"], b["status"])
        counts[k] = counts.get(k, 0) + 1
    for (rt, st), n in sorted(counts.items()):
        print(f"  {rt:5} {st:24} {n:3}")
    print("-" * 72)
    print("Top 5 breaks by priority and value:")
    for b in breaks[:5]:
        print(f"  {b['break_id']} [{b['priority']:6}] {b['recon_type']:5} {b['status']:22} "
              f"{b['key']:24} INR {b['difference_inr']:>15,.2f}  -> {b['probable_cause']}")
    print(line)
    print(f"Excel control report : {xlsx_path}")
    print(f"Break list (CSV)     : {csv_path}")


def main():
    ap = argparse.ArgumentParser(description="ReconDesk daily custody reconciliation")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--out-dir", default="reports")
    ap.add_argument("--as-of", default=config.AS_OF_DATE.isoformat(), help="business date YYYY-MM-DD")
    ap.add_argument("--no-ai", action="store_true", help="use rule-based explanations only")
    a = ap.parse_args()
    if not os.path.exists(os.path.join(a.data_dir, "cash_ledger.csv")):
        raise SystemExit("No data found. Run `python generate_data.py` first.")
    run(a.data_dir, a.out_dir, date.fromisoformat(a.as_of), use_ai=not a.no_ai)


if __name__ == "__main__":
    main()
