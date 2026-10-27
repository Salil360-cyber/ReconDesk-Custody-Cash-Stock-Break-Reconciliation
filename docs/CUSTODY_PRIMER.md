# Custody Primer — terms used in this project

**Custodian** — a bank that holds securities and cash safely on behalf of
clients (funds, insurers, pension trusts) and services them: settles trades,
collects income, processes corporate actions, and reports holdings.

**Books vs custodian** — the client (or the bank's internal system) keeps its
own records ("books"). The custodian keeps the official records. Reconciliation
checks the two agree.

**Break** — any difference between books and custodian that must be explained
and closed. **Cash break** = money difference; **stock break** = share quantity
difference.

## Settlement

- **Trade date (T)** — date the trade is agreed.
- **Settlement date** — date cash and securities actually change hands. Indian
  equities settle on **T+1**.
- **DVP (Delivery versus Payment)** — securities move only if cash moves, so
  neither side is left exposed.
- **Failed settlement** — the trade did not settle on the due date (e.g. seller
  short of shares, buyer short of cash, instruction mismatch).
- **Value date** — the date cash is actually credited/debited.

## Asset servicing (income and corporate actions)

- **Income events** — dividends (equity) and coupons (bonds) paid to holders.
- **Withholding tax** — tax deducted at source on income; the custodian credits
  the net amount. Treaty rates can reduce it.
- **Corporate action (CA)** — an event decided by the issuer that changes the
  holding or pays cash: dividend, bonus issue, stock split, rights issue,
  merger, buyback.
  - **Mandatory** (split, bonus, cash dividend) vs **voluntary** (rights,
    tender offer — the client must choose).
- **Record date** — holders on this date are entitled.
- **Ex-date** — from this date the security trades without the entitlement.
- **Pay date** — date the cash or new shares are delivered.
- **Bonus 1:1** — one new share for each held → quantity × 2.
  **Split 1:5** — each share becomes five → quantity × 5.

## Reconciliation terms

- **Cash reconciliation** — books cash movements vs custodian cash statement.
- **Position / stock reconciliation** — books holdings vs custodian holdings
  per account and ISIN.
- **Tolerance** — the difference allowed before something counts as a break.
  In custody this is usually zero or a tiny rounding amount.
- **Aging** — how long a break has been open. Older breaks carry more risk.
- **Sign-off** — the daily confirmation by an analyst and reviewer that the
  recon is complete and every break is owned.

## Identifiers and messages

- **ISIN** — 12-character international security identifier (e.g. `INE…` for
  Indian securities).
- **Depositories (India)** — NSDL and CDSL hold securities in electronic form.
- **SWIFT messages** commonly seen in custody (legacy MT format, moving to
  ISO 20022):
  - MT540–MT543 — settlement instructions (receive/deliver, free or against payment)
  - MT544–MT547 — settlement confirmations
  - MT564 — corporate action notification; MT566 — corporate action confirmation
  - MT535 — statement of holdings; MT950 — cash statement
