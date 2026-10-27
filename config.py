"""
Central configuration for ReconDesk.

Every threshold the engine uses lives here, so a reviewer can see (and change)
the control rules in one place instead of hunting through code.
"""

from datetime import date

# Business date the reconciliation is run "as of" (the daily control date).
AS_OF_DATE = date(2026, 10, 23)

# ---------------------------------------------------------------------------
# Matching tolerances
# ---------------------------------------------------------------------------
# Absolute tolerance per currency unit. Custody cash breaks are normally
# reconciled to zero; 0.01 only absorbs paise/cent rounding between systems.
# (v1 of this project used a 3% tolerance, which silently hid real fee and
# withholding-tax breaks. That was the main bug fixed in v2.)
AMOUNT_TOLERANCE = 0.01

# Stock positions are reconciled to the exact share. No tolerance.
QUANTITY_TOLERANCE = 0

# ---------------------------------------------------------------------------
# Reporting currency conversion (illustrative fixed rates, not market data)
# ---------------------------------------------------------------------------
FX_TO_INR = {
    "INR": 1.0,
    "USD": 84.0,
}

# ---------------------------------------------------------------------------
# Break priority rules
# ---------------------------------------------------------------------------
HIGH_VALUE_INR = 1_000_000     # >= 10 lakh INR equivalent  -> HIGH
MEDIUM_VALUE_INR = 100_000     # >= 1 lakh INR equivalent   -> at least MEDIUM
HIGH_AGE_DAYS = 6              # open for 6+ days           -> HIGH
MEDIUM_AGE_DAYS = 3            # open for 3-5 days          -> at least MEDIUM

# Age buckets used in the aging report (inclusive lower bound, label).
AGE_BUCKETS = [(0, "0-1 days"), (2, "2-3 days"), (4, "4-7 days"), (8, "8+ days")]

# ---------------------------------------------------------------------------
# Corporate action detection
# ---------------------------------------------------------------------------
# If custodian quantity / books quantity equals one of these ratios, the break
# is most likely an unbooked split or bonus issue (e.g. 1:1 bonus -> 2.0x,
# 1:2 bonus -> 1.5x, 1:5 split -> 5.0x).
CORPORATE_ACTION_RATIOS = [1.1, 1.2, 1.25, 1.5, 2.0, 3.0, 4.0, 5.0, 10.0]

# ---------------------------------------------------------------------------
# AI (optional)
# ---------------------------------------------------------------------------
# Model name can be overridden with the GEMINI_MODEL environment variable.
DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
MAX_BREAKS_FOR_AI = 60   # one batched call; larger batches fall back to rules
