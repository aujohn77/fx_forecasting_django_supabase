from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional
import pandas as pd

from apps.core.models import Currency, ExchangeSource, Timeframe
from apps.rates.models import ExchangeRate

Freq = Literal["D", "W"]
Fill = Literal["none", "ffill_within"]          # never extends past last observed date
WeeklyPolicy = Literal["strict_friday"]         # only real Fridays

@dataclass
class SeriesBundle:
    base: str
    quote: str
    freq: Freq
    y: pd.Series  # DatetimeIndex, float

def load_series(
    base_code: str,
    quote_code: str,
    freq: Freq = "D",
    start: Optional[date] = None,
    end: Optional[date] = None,
    fill: Fill = "none",
    weekly_policy: WeeklyPolicy = "strict_friday",
) -> SeriesBundle:
    base = Currency.objects.get(code=base_code.upper())
    quote = Currency.objects.get(code=quote_code.upper())
    src = ExchangeSource.objects.get(code="frankfurter")

    qs = ExchangeRate.objects.filter(
        source=src, base=base, quote=quote, timeframe=Timeframe.DAILY
    )
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)

    df = pd.DataFrame.from_records(
        qs.values("date", "rate").order_by("date"),
        index="date"
    ).rename(columns={"rate": "y"})

    if df.empty:
        return SeriesBundle(base.code, quote.code, freq, pd.Series(dtype=float))

    s = df["y"].astype(float)
    s.index = pd.to_datetime(s.index)
    last_obs = s.index.max()

    if freq == "D":
        if fill == "ffill_within":
            # Build a business-day index up to the last observed date ONLY
            full_idx = pd.bdate_range(s.index.min(), last_obs, freq="C")
            s = s.reindex(full_idx).ffill()
        # else: "none" → return sparse daily observations (no fill)
        return SeriesBundle(base.code, quote.code, "D", s)

    # Weekly
    if weekly_policy == "strict_friday":
        # Keep ONLY actual Fridays; drop weeks without a real Friday quote.
        s = s[s.index.weekday == 4]  # 4 = Friday
        # Optional: also clip to <= last observed Friday (already true)
    else:
        raise ValueError("Unsupported weekly policy")

    return SeriesBundle(base.code, quote.code, "W", s)
