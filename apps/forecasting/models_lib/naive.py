from __future__ import annotations
import numpy as np
import pandas as pd
from .types import ForecastResult

def predict(y_train: pd.Series, steps: int = 1, target_index: pd.DatetimeIndex | None = None) -> ForecastResult:
    if y_train.empty:
        raise ValueError("y_train is empty")
    idx = target_index if target_index is not None else pd.date_range(periods=steps, freq="D")
    last = float(y_train.iloc[-1])
    yhat = pd.Series(np.repeat(last, steps), index=idx, dtype=float)
    return ForecastResult(target_index=idx, yhat=yhat, model_name="naive", cutoff=y_train.index.max())
