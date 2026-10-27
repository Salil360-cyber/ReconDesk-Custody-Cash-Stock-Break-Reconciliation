# Break Handling SOP — Daily Custody Reconciliation

*Sample standard operating procedure written for this project. Steps reflect
common custody operations practice; a real team would follow its own
policies and custodian agreements.*

## 1. Daily routine

| When | Step |
|---|---|
| Start of day | Load books and custodian files for the business date. Check both files are complete (row counts, file date). |
| Run | `python reconcile.py`. Open `recon_report_<date>.xlsx`. |
| Triage | Work the **Breaks** sheet top-down (it is sorted HIGH first, then by value). Assign an **Owner** to every HIGH break. |
| Investigate | Follow the playbook in section 3 for each break type. |
| Update | Set **Resolution Status** (OPEN / IN PROGRESS / ESCALATED / RESOLVED) and add **Comments**. |
| Sign-off | On the **Sign-off** sheet, every checklist item should be YES. Fill in Prepared by / Reviewed by / time. |

## 2. Escalation rules

- Any break **6+ days old** or **≥ ₹10 lakh** is HIGH and needs an owner the same day.
- A break reaching the **8+ days** bucket is escalated to the team lead.
- Any break where client money or securities may be at risk (failed settlement,
  missing income, missing position at custodian) is communicated to the client
  service lead the same day.

## 3. Playbook by break type

### Cash

| Break | Check | Close by |
|---|---|---|
| `TIMING_DIFF` — settlement lag | Custodian settlement confirmation; market holiday calendar | Auto-clears when dates align; escalate if open past T+3 |
| `AMOUNT_DIFF` — withholding tax | Tax rate applied vs client's tax status / treaty rate | Book the tax entry, or raise a tax reclaim if the rate is wrong |
| `AMOUNT_DIFF` — charges | Contract note / charges breakdown | Book charges, or dispute with broker |
| `AMOUNT_DIFF` — FX rate | Booked rate vs custodian FX confirmation | Book the rate difference |
| `MISSING_AT_CUSTODIAN` — income | Corporate action event: record date, pay date, entitlement | Chase custodian / paying agent; client informed if late |
| `MISSING_AT_CUSTODIAN` — trade | Settlement status with custodian / counterparty | If failed: reverse in books, notify client, track re-settlement |
| `MISSING_IN_BOOKS` — fee | Fee schedule for the account | Book it, or dispute if not per schedule |
| `MISSING_IN_BOOKS` — corporate action | Event announcement and entitlement | Book the event |
| `DUPLICATE_IN_BOOKS` | Booking logs | Reverse the duplicate; log root cause |
| `DUPLICATE_AT_CUSTODIAN` | Custodian statement history | Query custodian to reverse |

### Stock

| Break | Check | Close by |
|---|---|---|
| `QTY_BREAK` — corporate action ratio | Split / bonus announcement for the ISIN, ex-date | Book the corporate action |
| `QTY_BREAK` — quantity mismatch | Recent trades, pending deliveries, transfers | Correct the side that is wrong |
| `MISSING_AT_CUSTODIAN` | Purchase settlement and delivery account | Chase delivery or fix account mapping |
| `MISSING_IN_BOOKS` | Trade/transfer instruction behind it | Book it, or ask custodian to correct |

## 4. Controls

- Zero tolerance on cash beyond ₹0.01 rounding; zero tolerance on share quantity.
- Every break carries a cause and a next action before sign-off.
- The full matched and unmatched population is kept in the report (Cash Recon /
  Stock Recon sheets) as an audit trail.
- Thresholds are documented on the Assumptions sheet; any change to `config.py`
  should be reviewed and dated.

## 5. Review of this SOP

Review when a new market, product or custodian is added, when a new break
pattern repeats, or at least quarterly.
