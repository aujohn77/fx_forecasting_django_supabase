from __future__ import annotations
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from .types import ForecastResult

def predict(y_train: pd.Series, steps: int = 1, target_index: pd.DatetimeIndex | None = None, **params) -> ForecastResult:
    if y_train.empty:
        raise ValueError("y_train is empty")

    idx = target_index if target_index is not None else pd.date_range(start=y_train.index[-1] + pd.Timedelta(days=1), periods=steps, freq="D")

    # Default params if not passed
    order = params.get("order", (1, 1, 0))

    model = ARIMA(y_train, order=order)
    fit = model.fit()
    fc = fit.forecast(steps=steps)

    return ForecastResult(
        target_index=idx,
        yhat=pd.Series(fc.values, index=idx, dtype=float),
        model_name="arima",
        params={"order": order},
        cutoff=y_train.index.max(),
        fit_info={"aic": fit.aic, "bic": fit.bic}
    )
