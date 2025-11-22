from __future__ import annotations
from datetime import date, timedelta
import pandas as pd

# --------- DAILY ---------
def daily_cutoff(y: pd.Series) -> pd.Timestamp:
    """
    Latest observed date in the series (no forward fill, no guessing).
    Works for a daily series with real calendar days only.
    """
    if y.empty:
        raise ValueError("Series is empty.")
    return y.index.max()

def next_business_day(d: date) -> date:
    """Next Mon–Fri after d."""
    n = d + timedelta(days=1)
    while n.weekday() >= 5:  # 5=Sat, 6=Sun
        n += timedelta(days=1)
    return n

# --------- WEEKLY (STRICT FRIDAY) ---------
def last_complete_friday(y: pd.Series) -> pd.Timestamp:
    """
    Return the last *real* Friday present in y.
    - If y is weekly (strict Fridays), this is just y.index.max().
    - If y is daily, we scan back to the latest index that is a Friday.
    - If the most recent week had a holiday Friday, we step back to the previous Friday.
    """
    if y.empty:
        raise ValueError("Series is empty.")

    # If it's already a Friday-only series, the last index is the last Friday.
    if (y.index.weekday == 4).all():
        return y.index.max()

    # Otherwise, find the last Friday present in the index.
    idx = y.index.sort_values()
    fridays = idx[idx.weekday == 4]
    if len(fridays) == 0:
        raise ValueError("No Fridays found in series.")
    return fridays.max()

def next_friday(friday: date) -> date:
    """The next calendar Friday after the given Friday."""
    # Given a Friday, the next Friday is +7 days (don’t synthesize values—just the target date).
    return friday + timedelta(days=7)
