# FILE: apps/forecasting/services/backtest_service.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Dict, List, Tuple, Optional
import numpy as np
import pandas as pd

from django.db import transaction
from django.utils import timezone

from apps.core.models import Currency, Timeframe
from apps.forecasting.models import (
    BacktestRun, BacktestSlice, BacktestMetric,
    ModelSpec, ModelLibrary,
)
from apps.forecasting.pipelines.prepare_series import load_series
from apps.forecasting.models_lib.registry import get_model


# -----------------
# Metrics
# -----------------
def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2))) if len(y_true) else float("nan")

def _mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred))) if len(y_true) else float("nan")

def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if not len(y_true):
        return float("nan")
    denom = np.where(y_true == 0, np.nan, y_true)
    return float(np.nanmean(np.abs((y_true - y_pred) / denom)) * 100.0)


# -----------------
# Options
# -----------------
@dataclass
class BacktestOptions:
    base_code: str
    quotes: Iterable[str]
    model: str                  # 'naive' | 'drift' | 'arima' | 'prophet' | ...
    window: int = 60            # EVAL LIMIT: score ONLY the last `window` targets
    horizon: int = 1            # forecast steps ahead (kept)
    timeframe: str = Timeframe.DAILY
    params: Optional[Dict] = None



# -----------------
# Helpers
# -----------------
def _series_for_pair(base: str, quote: str, timeframe: str) -> pd.Series:
    """Load a clean series using your pipeline (daily or strict Friday weekly)."""
    if timeframe == Timeframe.WEEKLY:
        bundle = load_series(base_code=base, quote_code=quote, freq="W")
    else:
        # Default to daily
        bundle = load_series(base_code=base, quote_code=quote, freq="D", fill="none")

    s = bundle.y
    # Ensure datetime index sorted
    if not s.empty:
        s = s.sort_index()
    return s


def _spec_for(model_key: str, timeframe: str, horizon: int) -> ModelSpec:
    """Ensure a ModelSpec exists per (model_name, timeframe)."""
    tf_code = {"D": "daily", "W": "weekly", "M": "monthly"}.get(timeframe, "daily")
    spec_code = f"{model_key.lower()}-{tf_code}"

    # Map library crudely; baselines are 'baseline'
    lib = ModelLibrary.BASELINE
    if model_key.lower() == "arima":
        lib = ModelLibrary.ARIMA
    elif model_key.lower() == "prophet":
        lib = ModelLibrary.PROPHET

    spec, _ = ModelSpec.objects.get_or_create(
        code=spec_code,
        defaults=dict(
            name=f"{model_key.title()} ({tf_code.title()})",
            library=lib,
            timeframe=timeframe,
            horizon_days=max(1, horizon),
            params={},
            active=True,
        ),
    )
    return spec




def _rolling_backtest(y: pd.Series, opts: BacktestOptions) -> Tuple[List[BacktestSlice], Dict[str, float]]:
    """
    Walk-forward backtest (ALL-PAST training):
      - For each target date dt among the *last N* points (N = opts.window):
        * train = y[ y.index < dt ]  (all history strictly before dt)
        * predict horizon steps starting at dt (usually 1 step)
    """
    predictor = get_model(opts.model)
    params = opts.params or {}

    slices: List[BacktestSlice] = []
    y_true_vals: List[float] = []
    y_pred_vals: List[float] = []

    y = y.sort_index()
    if y.isna().all() or len(y) < 2:  # need at least one train point + a target
        return slices, {"rmse": float("nan"), "mae": float("nan"), "mape": float("nan"), "n": 0}

    # Limit evaluation to the LAST N targets available
    n_targets = min(max(1, opts.window), len(y) - 1)
    target_dates = list(y.index[-n_targets:])

    for dt in target_dates:
        # Train on ALL history strictly before the target
        train = y[y.index < dt]
        if train.empty:
            continue

        if opts.horizon == 1:
            target_index = pd.DatetimeIndex([dt])
        else:
            # multi-step: start at dt and move forward by the series’ freq
            start = dt
            target_index = pd.date_range(start=start, periods=opts.horizon, freq=y.index.freq or "D")

        res = predictor(
            y_train=train,
            steps=opts.horizon,
            target_index=target_index,
            **params,
        )
        yhat = pd.Series(res.yhat, index=res.target_index).astype(float)

        # Persist slices (score step=1 headline metrics where actual exists)
        step1_dt = target_index[0]
        if step1_dt in y.index:
            actual = float(y.loc[step1_dt])
            pred = float(yhat.loc[step1_dt])
            y_true_vals.append(actual)
            y_pred_vals.append(pred)
            slices.append(BacktestSlice(
                date=step1_dt.date(),
                actual=actual,
                forecast=pred,
            ))

        # (Optional) If you want to ALSO store horizons >1 as slices, loop here:
        # for h_dt in target_index: ... append more BacktestSlice rows

    metrics = {
        "rmse": float(np.sqrt(np.mean((np.array(y_true_vals) - np.array(y_pred_vals)) ** 2))) if y_true_vals else float("nan"),
        "mae":  float(np.mean(np.abs(np.array(y_true_vals) - np.array(y_pred_vals)))) if y_true_vals else float("nan"),
        "mape": float(np.nanmean(np.abs((np.array(y_true_vals) - np.array(y_pred_vals)) / np.where(np.array(y_true_vals)==0, np.nan, np.array(y_true_vals)))) * 100.0) if y_true_vals else float("nan"),
        "n":    len(y_true_vals),
    }
    return slices, metrics






# -----------------
# Main entry
# -----------------
@transaction.atomic
def run_backtests(opts: BacktestOptions) -> BacktestRun:
    """
    Create a BacktestRun + BacktestSlice(s) + BacktestMetric(s)
    aligned with your Django models.
    """
    base = Currency.objects.get(code=opts.base_code.upper())
    spec = _spec_for(opts.model, opts.timeframe, opts.horizon)

    # Provisional dates (will update after slices built)
    provisional = timezone.localdate()
    run = BacktestRun.objects.create(
        model=spec,
        timeframe=opts.timeframe,
        horizon_days=opts.horizon,
        window_start=provisional,
        window_end=provisional,
        notes=f"window={opts.window}; horizon={opts.horizon}; model={opts.model}",
    )

    all_slices: List[BacktestSlice] = []
    metrics_per_quote: List[Dict[str, object]] = []

    for q in opts.quotes:
        q = q.upper()
        y = _series_for_pair(opts.base_code, q, opts.timeframe)
        if y.empty or len(y) < opts.window + opts.horizon:
            continue

        slices, metrics = _rolling_backtest(y, opts)

        # attach FKs
        quote_obj = Currency.objects.get(code=q)
        for s in slices:
            s.run = run
            s.base = base
            s.quote = quote_obj

        BacktestSlice.objects.bulk_create(slices, batch_size=1000, ignore_conflicts=True)
        all_slices.extend(slices)

        metrics_per_quote.append(dict(
            quote=quote_obj,
            mape=metrics["mape"],
            rmse=metrics["rmse"],
            mae=metrics["mae"],
            n=metrics["n"],
        ))

    # Per-quote metrics rows
    bt_metrics = [
        BacktestMetric(run=run, base=base, quote=m["quote"],
                       mape=m["mape"], rmse=m["rmse"], mae=m["mae"], n=m["n"])
        for m in metrics_per_quote
    ]
    BacktestMetric.objects.bulk_create(bt_metrics, batch_size=100)

    # Update run window bounds from actually produced slices
    if all_slices:
        ws = min(s.date for s in all_slices)
        we = max(s.date for s in all_slices)
        BacktestRun.objects.filter(pk=run.pk).update(window_start=ws, window_end=we)

    return run


# -----------------
# Thin wrappers used by Ops Console
# -----------------
def run_backtests_daily(base_code: str, quotes: Iterable[str], model: str, window: int = 60,
                        new_run: bool = False, horizon: int = 1, params: Optional[Dict] = None) -> BacktestRun:
    opts = BacktestOptions(
        base_code=base_code, quotes=list(quotes), model=model,
        window=window, horizon=horizon, timeframe=Timeframe.DAILY, params=params or {}
    )
    return run_backtests(opts)


def run_backtests_weekly(base_code: str, quotes: Iterable[str], model: str, window: int = 60,
                         new_run: bool = False, horizon: int = 1, params: Optional[Dict] = None) -> BacktestRun:
    opts = BacktestOptions(
        base_code=base_code, quotes=list(quotes), model=model,
        window=window, horizon=horizon, timeframe=Timeframe.WEEKLY, params=params or {}
    )
    return run_backtests(opts)
