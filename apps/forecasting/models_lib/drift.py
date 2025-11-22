from __future__ import annotations
import pandas as pd
from .types import ForecastResult

def predict(y_train: pd.Series, steps: int = 1, target_index: pd.DatetimeIndex | None = None) -> ForecastResult:
    if y_train.empty:
        raise ValueError("y_train is empty")
    idx = target_index if target_index is not None else pd.date_range(periods=steps, freq="D")

    y0 = float(y_train.iloc[0])
    yT = float(y_train.iloc[-1])
    n = len(y_train)
    slope = (yT - y0) / (n - 1) if n > 1 else 0.0

    vals = [yT + slope * k for k in range(1, steps + 1)]
    yhat = pd.Series(vals, index=idx, dtype=float)
    return ForecastResult(target_index=idx, yhat=yhat, model_name="drift", cutoff=y_train.index.max())
