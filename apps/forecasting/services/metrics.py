from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import math

import pandas as pd

from apps.core.models import Timeframe
from apps.rates.models import ExchangeRate


# Helper to compute consecutive up/down streak on daily closes
def _streak_days(series: pd.Series) -> int:
    """
    Returns the number of consecutive days the close has moved in the same
    direction (up or down). If the last change is flat or not enough data,
    returns 0.
    """
    if series.size < 2:
        return 0
    # day-over-day change
    delta = series.diff()
    last = delta.iloc[-1]
    if last == 0 or pd.isna(last):
        return 0
    sign = 1 if last > 0 else -1
    cnt = 0
    for x in reversed(delta.dropna().tolist()):
        s = 1 if x > 0 else -1 if x < 0 else 0
        if s == sign:
            cnt += 1
        else:
            break
    return cnt


def compute_overview_metrics(base_code: str, quote_code: str) -> Dict[str, Optional[float]]:
    """
    Pull recent DAILY ExchangeRate rows and compute:
      - daily_pct   : (last / last_1 - 1) * 100
      - weekly_pct  : (last / last_5 - 1) * 100       (≈ 5 trading days)
      - monthly_pct : (last / last_21 - 1) * 100      (≈ 1 trading month)
      - roc5_pct    : (last / last_5 - 1) * 100       (alias for a 5-day ROC)
      - vol7        : stddev of daily returns over last 7 obs
      - vol30       : stddev of daily returns over last 30 obs
      - streak_days : consecutive up/down days ending on last observation
    Returns None for any metric we don't have enough data to compute.
    """
    # Grab enough history to cover 30-day volatility + 21D monthly + a bit of buffer
    qs = (ExchangeRate.objects
          .filter(base__code=base_code, quote__code=quote_code, timeframe=Timeframe.DAILY)
          .order_by("date")
          .values_list("date", "rate"))

    rows: List[tuple] = list(qs)
    if not rows:
        return {
            "daily_pct": None, "weekly_pct": None, "monthly_pct": None,
            "roc5_pct": None, "vol7": None, "vol30": None, "streak_days": 0,
        }

    df = pd.DataFrame(rows, columns=["date", "rate"])
    # Ensure unique dates and proper ordering
    df = df.drop_duplicates(subset=["date"]).sort_values("date")
    s = df["rate"].astype(float)

    def pct(a_idx: int) -> Optional[float]:
        if len(s) <= a_idx:
            return None
        last = s.iloc[-1]
        prev = s.iloc[-1 - a_idx]
        if prev == 0 or pd.isna(prev) or pd.isna(last):
            return None
        return (last / prev - 1.0) * 100.0

    daily_pct   = pct(1)    # 1 day back
    weekly_pct  = pct(5)    # ~5 trading days
    monthly_pct = pct(21)   # ~21 trading days
    roc5_pct    = pct(5)    # same as weekly in this simple definition

    # Daily log returns for stability; fall back to simple returns if needed
    r = s.pct_change().dropna()
    vol7  = float(r.tail(7).std())  if r.size >= 2 else None
    vol30 = float(r.tail(30).std()) if r.size >= 2 else None

    streak = _streak_days(s)

    return {
        "daily_pct": None if daily_pct   is None else float(daily_pct),
        "weekly_pct": None if weekly_pct is None else float(weekly_pct),
        "monthly_pct": None if monthly_pct is None else float(monthly_pct),
        "roc5_pct": None if roc5_pct     is None else float(roc5_pct),
        "vol7": vol7,
        "vol30": vol30,
        "streak_days": int(streak),
    }
