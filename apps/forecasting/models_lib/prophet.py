from __future__ import annotations
import pandas as pd
from prophet import Prophet

from .types import ForecastResult


def _to_datetime_index(x) -> pd.DatetimeIndex:
    """Coerce a sequence/Series/Index of datelike values to a tz-naive DatetimeIndex."""
    idx = pd.to_datetime(x)
    # Drop timezone info if present (Prophet expects tz-naive)
    try:
        idx = idx.tz_localize(None)
    except Exception:
        pass
    return pd.DatetimeIndex(idx)


def predict(
    y_train: pd.Series,
    steps: int = 1,
    target_index: pd.DatetimeIndex | None = None,
    **params,
) -> ForecastResult:
    """
    Prophet-based forecaster.

    Parameters
    ----------
    y_train : pd.Series
        Training series with a DatetimeIndex. Values must be numeric.
    steps : int
        Number of steps ahead if `target_index` is not provided.
    target_index : pd.DatetimeIndex | None
        Exact timestamps to forecast for. If None, generates a daily
        range starting the day after the last observation for `steps`.
    **params
        Parameters forwarded to `Prophet(...)` constructor
        (e.g., seasonality_mode="multiplicative", yearly_seasonality=True, ...).

    Returns
    -------
    ForecastResult
        - target_index: DatetimeIndex of requested forecast timestamps
        - yhat: pd.Series of point forecasts (float) indexed by target_index
        - fit_info: minimal metadata (e.g., train_size)
        Also attaches optional attributes:
        - .lo (pd.Series): lower interval if available
        - .hi (pd.Series): upper interval if available
    """
    if y_train is None or y_train.empty:
        raise ValueError("y_train is empty")

    # Ensure datetime index and clean training frame
    y_train = y_train.sort_index()
    ds = _to_datetime_index(y_train.index)
    df = pd.DataFrame({"ds": ds, "y": pd.to_numeric(y_train.values, errors="coerce")}).dropna()

    if df.empty:
        raise ValueError("y_train has no valid numeric observations after cleaning")

    # Fit Prophet
    model = Prophet(**params)
    model.fit(df)

    # Build target index if not provided
    if target_index is None:
        last = df["ds"].iloc[-1]
        target_index = pd.date_range(start=last + pd.Timedelta(days=1), periods=int(steps), freq="D")
    else:
        # Coerce any incoming sequence to a clean DatetimeIndex
        target_index = _to_datetime_index(target_index)

    # Forecast only for the requested timestamps
    future = pd.DataFrame({"ds": target_index})
    fc = model.predict(future)

    # Ensure shapes & dtypes
    idx = _to_datetime_index(fc["ds"])
    yhat = pd.Series(pd.to_numeric(fc["yhat"], errors="coerce").astype(float).values, index=idx)

    result = ForecastResult(
        target_index=idx,
        yhat=yhat,
        model_name="prophet",
        params=params or {},
        cutoff=df["ds"].iloc[-1],
        fit_info={"train_size": int(len(df))},
    )

    # Attach intervals if Prophet produced them
    if "yhat_lower" in fc.columns and "yhat_upper" in fc.columns:
        lo = pd.Series(pd.to_numeric(fc["yhat_lower"], errors="coerce").astype(float).values, index=idx)
        hi = pd.Series(pd.to_numeric(fc["yhat_upper"], errors="coerce").astype(float).values, index=idx)
        # Add as dynamic attributes (supported by our persistence layer)
        setattr(result, "lo", lo)
        setattr(result, "hi", hi)

    return result
