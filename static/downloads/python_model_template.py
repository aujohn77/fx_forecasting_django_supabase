"""
PYTHON MODEL TEMPLATE – FX FORECASTING PLATFORM
===============================================

HOW TO USE THIS TEMPLATE
------------------------
1. Download this file from the website.
2. Move it into your project at:
       apps/forecasting/models_lib/
3. Rename the file to something meaningful, e.g.:
       my_custom_model.py
4. Open the file and:
   - Change `model_name="my_custom_python_model"` to your model code
   - Replace the "MODEL LOGIC" block with your own logic
5. Register the model in:
       apps/forecasting/models_lib/registry.py

   Example registration (inside registry.py):

       from . import my_custom_model

       _REGISTRY = {
           # existing models...
           "my_custom_model": my_custom_model.predict,
       }

6. (Optional but recommended)
   - Add a row in the ModelSpec table (Django admin) using the same
     code "my_custom_model" so it appears nicely in the UI.

AFTER THESE STEPS:
------------------
- Your model can be run through the existing management commands, e.g.:

    python manage.py run_daily_forecasts --model my_custom_model
    python manage.py run_backtests --model my_custom_model

- The interface below MUST be preserved:
    def predict(y_train, steps=1, target_index=None, **params) -> ForecastResult

Do not change the function name or its parameters, only the internal logic.
"""

from __future__ import annotations

import pandas as pd
from .types import ForecastResult  # This import works once the file is in models_lib/


def predict(
    y_train: pd.Series,
    steps: int = 1,
    target_index: pd.DatetimeIndex | None = None,
    **params,
) -> ForecastResult:
    """
    Custom FX forecasting model template.

    REQUIRED INTERFACE (do not change the function name or arguments):
        - y_train: pandas Series with a DatetimeIndex and float values (FX rates)
        - steps:   integer horizon (how many future points to forecast)
        - target_index: optional DatetimeIndex for the forecast horizon.
                        If None, you must create one inside this function.

    RETURN:
        ForecastResult object with:
          - target_index: DatetimeIndex of future timestamps
          - yhat:         pd.Series of forecasts, indexed by target_index
          - model_name:   short string identifier for this model
          - params:       dict of hyperparameters / options (optional)
          - cutoff:       pd.Timestamp of last observed training date (optional)
    """

    # ──────────────────────────────────────────────────────────────────
    # 1. Basic safety & preparation
    # ──────────────────────────────────────────────────────────────────
    if y_train is None or y_train.empty:
        raise ValueError("y_train is empty")

    # Ensure series is sorted by date and has a datetime index
    y_train = y_train.sort_index()
    cutoff = y_train.index.max()

    # If caller did not provide a target index, create one.
    # You may change the frequency if your data uses business days, etc.
    if target_index is None:
        target_index = pd.date_range(
            start=cutoff + pd.Timedelta(days=1),
            periods=int(steps),
            freq="D",
        )

    # ──────────────────────────────────────────────────────────────────
    # 2. MODEL LOGIC – REPLACE THIS BLOCK WITH YOUR OWN MODEL
    # ──────────────────────────────────────────────────────────────────
    # Example placeholder: constant forecast equal to the last observed value.
    # This is here only as an example; you should implement your own logic.

    last_value = float(y_train.iloc[-1])

    yhat = pd.Series(
        [last_value] * len(target_index),
        index=target_index,
        dtype=float,
    )

    # If your model has hyperparameters, you can read them from `params`, e.g.:
    #   window = params.get("window", 30)
    #   alpha = params.get("alpha", 0.2)
    # and so on.
    # ──────────────────────────────────────────────────────────────────

    # ──────────────────────────────────────────────────────────────────
    # 3. Build and return ForecastResult
    # ──────────────────────────────────────────────────────────────────
    result = ForecastResult(
        target_index=target_index,
        yhat=yhat,
        model_name="my_custom_python_model",  # <-- change this slug
        params=params or {},
        cutoff=cutoff,
    )

    # OPTIONAL: if your model produces intervals, you can attach them, e.g.:
    #   setattr(result, "lo", lo_series)
    #   setattr(result, "hi", hi_series)

    return result
