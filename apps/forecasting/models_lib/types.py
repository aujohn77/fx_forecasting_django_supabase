from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict
import pandas as pd

@dataclass
class ForecastResult:
    target_index: pd.DatetimeIndex   # future timestamps (prediction times)
    yhat: pd.Series                  # point forecasts, indexed by target_index
    model_name: str                  # e.g., "naive", "drift"
    params: Optional[Dict] = None
    cutoff: Optional[pd.Timestamp] = None
    fit_info: Optional[Dict] = None

# (Optional) If future models return intervals, you can add:
# lo: Optional[pd.Series] = None
# hi: Optional[pd.Series] = None
