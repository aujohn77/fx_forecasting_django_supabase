from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Dict, Optional

import pandas as pd
from django.db import transaction
from django.utils import timezone

from apps.core.models import Currency, Timeframe
from apps.forecasting.pipelines.prepare_series import load_series
from apps.forecasting.services.weekly_cutoffs import (
    daily_cutoff, next_business_day,
    last_complete_friday, next_friday,
)
from apps.forecasting.models_lib.registry import get_model
from apps.forecasting.models_lib.types import ForecastResult


from apps.forecasting.models import ForecastRun, Forecast, ModelSpec, ModelLibrary



DEFAULT_QUOTES = ["EUR", "GBP", "AUD"]
# Default USD quote set used when --quotes is omitted
DEFAULT_USD_QUOTES = [
    "EUR","GBP","AUD","NZD","JPY","CNY","CHF","CAD","MXN","INR","BRL","KRW"
]




# ========================
# Persistence helpers
# ========================
def _field_names(Model) -> set[str]:
    return {f.name for f in Model._meta.get_fields()}

def _set_if_has(obj, field: str, value):
    if field in _field_names(obj.__class__):
        setattr(obj, field, value)

def _fk_name(Model, candidates: list[str]) -> Optional[str]:
    """Pick the first field name that exists on Model from candidates."""
    names = _field_names(Model)
    for c in candidates:
        if c in names:
            return c
    return None

@transaction.atomic
def _create_or_get_run(
    timeframe: Timeframe,
    cutoff_date: date,
    model_name: str,
    trigger: str = "cli",
) -> ForecastRun:
    """
    Create or get a ForecastRun using a natural uniqueness:
    (timeframe, data_cutoff_date, model_name) when available.
    Falls back to (timeframe, model) if you don't have data_cutoff_date/model_name.
    """
    run_fields = _field_names(ForecastRun)

    # Build a uniqueness filter from fields you actually have
    flt: Dict[str, object] = {}

    # timeframe (assumed to exist)
    if "timeframe" in run_fields:
        flt["timeframe"] = timeframe
    else:
        # If your run model doesn't store timeframe, it'll still work but be less precise
        pass

    # data_cutoff_date (optional)
    if "data_cutoff_date" in run_fields:
        flt["data_cutoff_date"] = cutoff_date

    # model identifier (string)
    if "model_name" in run_fields:
        flt["model_name"] = model_name
    elif "model" in run_fields:
        flt["model"] = model_name

    # defaults
    defaults: Dict[str, object] = {}
    if "trigger" in run_fields:
        defaults["trigger"] = trigger
    # If as_of isn't auto_now_add and exists, set it
    if "as_of" in run_fields:
        # We won't inspect auto_now_add; setting now() is harmless if ignored
        defaults["as_of"] = timezone.now()

    run, created = ForecastRun.objects.get_or_create(**flt, defaults=defaults)

    # optional status/notes reset
    _set_if_has(run, "status", "ok")
    run.save(update_fields=list(defaults.keys()) + (["status"] if "status" in run_fields else []))

    return run




@transaction.atomic
def _save_forecast_rows(
    run: ForecastRun,
    base_code: str,
    quote_code: str,
    result: ForecastResult,
    timeframe: Timeframe,
) -> int:
    fc_fields = _field_names(Forecast)
    rows = []

    # Resolve FK field names (schema-tolerant)
    run_fk   = _fk_name(Forecast, ["run", "forecast_run"])
    base_fk  = _fk_name(Forecast, ["base", "base_currency", "base_ccy"])
    quote_fk = _fk_name(Forecast, ["quote", "quote_currency", "quote_ccy"])
    tdate_field  = _fk_name(Forecast, ["target_date", "date", "for_date"])
    point_field  = _fk_name(Forecast, ["point", "yhat", "value", "forecast"])
    tf_field     = "timeframe" if "timeframe" in fc_fields else None
    lo_field     = _fk_name(Forecast, ["lo", "lower", "yhat_lo"])
    hi_field     = _fk_name(Forecast, ["hi", "upper", "yhat_hi"])
    model_fk     = _fk_name(Forecast, ["model", "model_spec"])  # attach ModelSpec if present

    if not (run_fk and base_fk and quote_fk and tdate_field and point_field):
        missing = [n for n in ["run/run_fk", "base", "quote", "target_date", "point"]
                   if n not in ["run/run_fk" if run_fk else None, base_fk, quote_fk, tdate_field, point_field]]
        raise ValueError(f"Forecast model is missing required fields: {missing}. Please add/rename accordingly.")

    base  = Currency.objects.get(code=base_code.upper())
    quote = Currency.objects.get(code=quote_code.upper())

    # Build/lookup a ModelSpec unique per timeframe
    tf_code = {"D": "daily", "W": "weekly", "M": "monthly"}.get(timeframe.value, str(timeframe.value).lower())
    model_key = (result.model_name or "").lower()
    spec_code = f"{model_key}-{tf_code}"

    horizon = max(1, len(result.yhat))  # typically 1-step

    # --- NEW: choose the proper library for the spec ---
    lib_map = {
        "naive":   ModelLibrary.BASELINE,
        "drift":   ModelLibrary.BASELINE,
        "arima":   ModelLibrary.ARIMA,
        "prophet": ModelLibrary.PROPHET,
    }
    library = lib_map.get(model_key, ModelLibrary.BASELINE)

    spec, _ = ModelSpec.objects.get_or_create(
        code=spec_code,
        defaults=dict(
            name=f"{(result.model_name or 'Model').title()} ({tf_code.title()})",
            library=library,                 # <- was hard-coded to BASELINE
            timeframe=timeframe,
            horizon_days=horizon,
            params=result.params or {},
            active=True,
        ),
    )

    # Build row objects
    for ts, yhat_val in result.yhat.items():
        ts = pd.Timestamp(ts)  # ensure Timestamp (handles int index edge-cases)
        inst_kwargs = {
            run_fk: run,
            base_fk: base,
            quote_fk: quote,
            tdate_field: ts.date(),
            point_field: Decimal(str(float(yhat_val))),
        }
        if model_fk:
            inst_kwargs[model_fk] = spec
        if tf_field:
            inst_kwargs[tf_field] = timeframe
        if lo_field and hasattr(result, "lo") and result.lo is not None and ts in getattr(result, "lo", pd.Series()).index:
            inst_kwargs[lo_field] = Decimal(str(float(result.lo.loc[ts])))
        if hi_field and hasattr(result, "hi") and result.hi is not None and ts in getattr(result, "hi", pd.Series()).index:
            inst_kwargs[hi_field] = Decimal(str(float(result.hi.loc[ts])))

        rows.append(Forecast(**inst_kwargs))

    Forecast.objects.bulk_create(rows, ignore_conflicts=True, batch_size=1000)
    return len(rows)










@transaction.atomic
def _persist_result(
    base_code: str,
    quote_code: str,
    timeframe: Timeframe,
    cutoff_date: date,
    model_name: str,
    result: ForecastResult,
    trigger: str = "cli",
) -> ForecastRun:
    """
    Create/get the run, insert forecast rows, and update rows_written.
    """
    run = _create_or_get_run(timeframe=timeframe, cutoff_date=cutoff_date, model_name=model_name, trigger=trigger)
    written = _save_forecast_rows(run, base_code, quote_code, result, timeframe)

    # Update rows_written if present
    if "rows_written" in _field_names(ForecastRun):
        run.rows_written = (getattr(run, "rows_written", 0) or 0) + written
        run.save(update_fields=["rows_written"])

    return run

# ========================
# Orchestration (public)
# ========================
def run_daily(base_code: str = "USD", quote_code: str = "EUR", model: str = "naive") -> ForecastResult:
    """1-step ahead daily forecast (next business day)."""
    bundle = load_series(base_code, quote_code, freq="D", fill="none")
    y = bundle.y
    c = daily_cutoff(y)
    tgt = next_business_day(c.date())
    idx = pd.DatetimeIndex([pd.Timestamp(tgt)])

    y_train = y.loc[:c]
    predictor = get_model(model)
    result = predictor(y_train, steps=1, target_index=idx)

    # Console summary
    print(f"{base_code}->{quote_code} | tf={Timeframe.DAILY.label} | cutoff={c.date()} | target={tgt} | model={result.model_name} | ŷ={result.yhat.iloc[0]:.6f}")

    # Persist
    _persist_result(
        base_code=base_code,
        quote_code=quote_code,
        timeframe=Timeframe.DAILY,
        cutoff_date=c.date(),
        model_name=result.model_name,
        result=result,
        trigger="cli",
    )
    return result

def run_weekly(base_code: str = "USD", quote_code: str = "EUR", model: str = "naive") -> ForecastResult:
    """1-step ahead weekly forecast (next real Friday), strict—no synthetic weeks."""
    bundle = load_series(base_code, quote_code, freq="W")  # strict Fridays only
    y = bundle.y
    last_fri = last_complete_friday(y)
    tgt = next_friday(last_fri.date())
    idx = pd.DatetimeIndex([pd.Timestamp(tgt)])

    y_train = y.loc[:last_fri]
    predictor = get_model(model)
    result = predictor(y_train, steps=1, target_index=idx)

    print(f"{base_code}->{quote_code} | tf={Timeframe.WEEKLY.label} | cutoff={last_fri.date()} | target={tgt} | model={result.model_name} | ŷ={result.yhat.iloc[0]:.6f}")

    _persist_result(
        base_code=base_code,
        quote_code=quote_code,
        timeframe=Timeframe.WEEKLY,
        cutoff_date=last_fri.date(),
        model_name=result.model_name,
        result=result,
        trigger="cli",
    )
    return result

def run_daily_batch(base_code: str = "USD", quotes = None, model: str = "naive"):
    quotes = quotes or DEFAULT_USD_QUOTES

    results = {}
    for q in quotes:
        results[q] = run_daily(base_code, q, model=model)
    return results

def run_weekly_batch(base_code: str = "USD", quotes = None, model: str = "naive"):
    quotes = quotes or DEFAULT_USD_QUOTES

    results = {}
    for q in quotes:
        results[q] = run_weekly(base_code, q, model=model)
    return results
