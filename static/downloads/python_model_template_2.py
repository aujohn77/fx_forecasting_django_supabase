from __future__ import annotations
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from .types import ForecastResult   # <- MUST keep this import (or equivalent)


# ─────────────────────────────────────────────
# DO NOT CHANGE: function name or parameters
# ─────────────────────────────────────────────
def predict(
    y_train: pd.Series,
    steps: int = 1,
    target_index: pd.DatetimeIndex | None = None
) -> ForecastResult:
    """
    Example: ARIMA-based custom model built from the template.
    """

    # ─────────────────────────────────────────
    # PART 1 — SAFETY & BASIC SETUP (KEEP IT)
    # You should NOT remove these checks.
    # You may *extend* them if needed, but not break them.
    # ─────────────────────────────────────────
    if y_train is None or y_train.empty:
        raise ValueError("y_train is empty")

    # Ensure series is sorted and indexed by date.
    # You should generally keep this; if you change it,
    # you must guarantee the index is still a proper DatetimeIndex.
    y_train = y_train.sort_index()


    # Build target_index if none is provided.
    if target_index is None:
        target_index = pd.date_range(
            start=y_train.index.max() + pd.Timedelta(days=1),
            periods=int(steps),
            freq="B"    # business-day frequency (Mon–Fri only)

        )





    # ──────────────────────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────────────────


    # ─────────────────────────────────────────
    # PART 2 — MODEL LOGIC (THIS IS YOUR AREA)
    # You CAN change anything inside this block.
    #
    # IMPORTANT:
    #   • You RECEIVE:  y_train → pd.Series of historical FX values
    #   • You MUST RETURN: yhat → pd.Series indexed by target_index
    #
    #   yhat and y_train MUST be pandas Series.
    #   yhat.index MUST equal target_index.
    #   
    #   You must import whatever libraries your own model needs.

    # Everything inside this section is UP TO YOU.
    # ─────────────────────────────────────────


    # Example ARIMA fit
    model = ARIMA(y_train, order=(1,1,0))
    fit = model.fit()

    # Forecast values (must match the number of target timestamps)
    fc = fit.forecast(steps=len(target_index))

    # yhat MUST be a pandas Series indexed by target_index
    yhat = pd.Series(fc.values, index=target_index, dtype=float)








    # ──────────────────────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────────────────────



    # ─────────────────────────────────────────
    # PART 3 — BUILD AND RETURN ForecastResult
    # Structure MUST be kept.
    # ─────────────────────────────────────────
    result = ForecastResult(
        target_index=target_index,   # <- KEEP THE WAY IT IS
        yhat=yhat,                   # <- KEEP THE WAY IT IS
        model_name="my_arima",       # <---------------------------- CHOOSE A NAME FOR YOUR MODEL
        cutoff=y_train.index.max()   # <- KEEP THE WAY IT IS
    )


    return result     # <- MUST return a ForecastResult instance
