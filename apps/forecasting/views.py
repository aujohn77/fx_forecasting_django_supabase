# apps/forecasting/views.py
from __future__ import annotations
import json
import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
from django.db.models import F
from django.shortcuts import render

from apps.core.models import Currency, Timeframe
from apps.forecasting.models import (
    Forecast, BacktestSlice, BacktestMetric, ModelSpec
)
from apps.rates.models import ExchangeRate  # <- actual market data (USD base)
from apps.forecasting.services.metrics import compute_overview_metrics
from django.views.decorators.cache import cache_page










# apps/forecasting/views.py


# FILE: apps/forecasting/views.py

from .services.metrics import compute_overview_metrics  # if this is where it lives

# ──────────────────────────────────────────────────────────────────────────────
# Resampling helpers (ported from your Streamlit logic)
# ──────────────────────────────────────────────────────────────────────────────
def _last_complete_cutoff(last_obs: pd.Timestamp, freq_code: str) -> pd.Timestamp:
    if freq_code == "D":
        return last_obs.normalize()
    if freq_code == "W":
        this_fri = (last_obs + pd.offsets.Week(weekday=4)).normalize()  # W-FRI
        return this_fri if last_obs.normalize() >= this_fri else (this_fri - pd.offsets.Week(1))
    if freq_code == "M":
        this_me = (last_obs + pd.offsets.MonthEnd(0))
        return this_me if last_obs.normalize() >= this_me else (last_obs + pd.offsets.MonthEnd(-1))
    raise ValueError("freq_code must be one of {'D','W','M'}")

def _resample_actual_df(daily_df: pd.DataFrame, freq_code: str) -> pd.DataFrame:
    if daily_df.empty:
        return daily_df

    df = daily_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df.sort_values("date")
    # collapse duplicates per day (pick last; use .mean() if you prefer)
    df = df.groupby("date", as_index=False)["rate"].last()

    s = df.set_index("date")["rate"].asfreq("B").interpolate()
    last_obs = s.dropna().index.max()

    if freq_code == "D":
        out = s.asfreq("D")
    elif freq_code == "W":
        out = s.resample("W-FRI").last()
    elif freq_code == "M":
        out = s.resample("M").last()
    else:
        raise ValueError("freq_code must be 'D','W','M'")

    # clip to the last complete period (same rule you used in Streamlit)
    cutoff = _last_complete_cutoff(last_obs, freq_code)
    out = out.loc[:cutoff]

    return (
        out.dropna()
           .to_frame("rate")
           .reset_index()
           .rename(columns={"index": "date"})
    )

# ──────────────────────────────────────────────────────────────────────────────
# Overview metrics (for tiles)
# ──────────────────────────────────────────────────────────────────────────────
def _series_daily(base_code: str, quote_code: str) -> pd.Series:
    """
    Return a clean business-day series up to the last observed day (no forward beyond).
    """
    rows = (
        ExchangeRate.objects
        .filter(base__code=base_code.upper(), quote__code=quote_code.upper(), timeframe=Timeframe.DAILY)
        .order_by("date")
        .values("date", "rate")
    )
    df = pd.DataFrame(list(rows))
    if df.empty:
        return pd.Series(dtype=float)

    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    s = (df.set_index("date")["rate"]).astype(float)

    last_obs = s.index.max()
    # Build business-day index only within observed range; ffill within range
    full_idx = pd.bdate_range(s.index.min(), last_obs, freq="C")
    return s.reindex(full_idx).ffill()

def _streak_positive(returns: pd.Series) -> int:
    """Consecutive >0 daily returns ending at the last day."""
    if returns.empty:
        return 0
    rev = (returns > 0).iloc[::-1]
    cnt = 0
    for v in rev:
        if v:
            cnt += 1
        else:
            break
    return cnt

def compute_overview_metrics(base_code: str = "USD", quote_code: str = "EUR") -> dict:
    yD = _series_daily(base_code, quote_code)
    if len(yD) < 10:
        return {}

    rD = yD.pct_change()

    # Daily % (last vs previous business day)
    daily_pct = float((yD.iloc[-1] / yD.iloc[-2] - 1.0) * 100.0) if len(yD) >= 2 else None

    # Weekly % (last complete Friday vs previous Friday)
    yW = yD.resample("W-FRI").last().dropna()
    weekly_pct = float((yW.iloc[-1] / yW.iloc[-2] - 1.0) * 100.0) if len(yW) >= 2 else None

    # Monthly % (last complete month-end vs previous)
    yM = yD.resample("M").last().dropna()
    monthly_pct = float((yM.iloc[-1] / yM.iloc[-2] - 1.0) * 100.0) if len(yM) >= 2 else None

    # ROC (5d)
    roc5 = float((yD.iloc[-1] / yD.iloc[-5] - 1.0) * 100.0) if len(yD) >= 6 else None

    # Volatilities (std of daily returns, population)
    vol7  = float(rD.tail(7).std(ddof=0))  if len(rD) >= 7  else None
    vol30 = float(rD.tail(30).std(ddof=0)) if len(rD) >= 30 else None

    streak = _streak_positive(rD.tail(90))

    return {
        "daily_pct": daily_pct,
        "weekly_pct": weekly_pct,
        "monthly_pct": monthly_pct,
        "roc5_pct": roc5,
        "vol7": vol7,
        "vol30": vol30,
        "streak_days": streak,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Pages
# ──────────────────────────────────────────────────────────────────────────────


def next_business_day(d: date) -> date:
    """
    Return the next business day (Mon–Fri) after date d.
    Very simple version: skips Saturday and Sunday.
    """
    n = d + timedelta(days=1)
    # 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun
    while n.weekday() >= 5:  # if Sat or Sun, keep moving forward
        n += timedelta(days=1)
    return n




def overview(request):
    base_code = "USD"

    # ---- Latest forecast per model/quote (keep only the newest per pair)
    latest_by_model: dict[str, dict] = {}

    latest_f = (
        Forecast.objects
        .filter(base__code=base_code,
                model__timeframe__in=[Timeframe.DAILY, Timeframe.WEEKLY])
        .order_by("quote__code", "model__code", "-created_at", "-target_date")
        .values("quote__code", "model__code", "target_date", "yhat")
    )
    for r in latest_f:
        q = r["quote__code"]; m = r["model__code"]
        latest_by_model.setdefault(m, {})
        if q not in latest_by_model[m]:  # first is newest due to ordering
            latest_by_model[m][q] = {"date": str(r["target_date"]), "rate": float(r["yhat"])}

    # ---- Quotes that actually have at least one forecast (any model/timeframe)
    forecast_quotes = sorted({q for m in latest_by_model.values() for q in m.keys()})

    # Fallback to actuals only if there are literally no forecasts at all
    if forecast_quotes:
        all_quotes = forecast_quotes
    else:
        qs_avail = (
            ExchangeRate.objects
            .filter(base__code=base_code, timeframe=Timeframe.DAILY)
            .values_list("quote__code", flat=True)
            .distinct()
        )
        all_quotes = sorted(set(qs_avail)) or ["EUR","GBP","AUD","NZD","JPY","CNY","CHF","CAD","MXN","INR","BRL","KRW"]

    # ---- Selected quote (force into allowed list)
    requested = (request.GET.get("quote") or "EUR").upper()
    quote_code = requested if requested in all_quotes else (all_quotes[0] if all_quotes else "EUR")

    # ---- Latest ACTUAL per quote (limit to quotes we expose)
    latest_actual: dict[str, dict] = {}
    rows = (
        ExchangeRate.objects
        .filter(base__code=base_code, timeframe=Timeframe.DAILY, quote__code__in=all_quotes)
        .order_by("quote__code", "-date")
        .values("quote__code", "date", "rate")
    )
    for r in rows:
        q = r["quote__code"]
        if q in latest_actual:
            continue
        latest_actual[q] = {"date": str(r["date"]), "rate": float(r["rate"])}

    # ---- Headline tiles: only show if this quote has a forecast
    has_forecast_for_selected = quote_code in forecast_quotes
    if has_forecast_for_selected:
        metrics = compute_overview_metrics(base_code, quote_code)
    else:
        metrics = {
            "daily_pct": None, "weekly_pct": None, "monthly_pct": None,
            "roc5_pct": None, "vol7": None, "vol30": None, "streak_days": 0,
        }

    # ---- NEW: Country/Zone labels to display next to currency code
    # Prefer a short country/zone name (for recognition). Fallback to Currency.name.
    # You can extend this map anytime; it doesn't change your DB schema.
    short_zone = {
        "EUR": "Eurozone",
        "GBP": "United Kingdom",
        "AUD": "Australia",
        "NZD": "New Zealand",
        "JPY": "Japan",
        "CNY": "China",
        "CHF": "Switzerland",
        "CAD": "Canada",
        "MXN": "Mexico",
        "INR": "India",
        "BRL": "Brazil",
        "KRW": "South Korea",
        "USD": "United States",
    }

    # Pull names from DB (e.g., "Australian Dollar") for any not in the short map
    db_names = {c.code: c.name for c in Currency.objects.filter(code__in=all_quotes)}
    currency_names = {}
    for code in all_quotes:
        currency_names[code] = short_zone.get(code, db_names.get(code, code))

    ctx = {
        "all_quotes": all_quotes,
        "selected_quote": quote_code,
        "latest_actual_json": json.dumps(latest_actual),
        "latest_forecast_json": json.dumps(latest_by_model),
        "currency_names_json": json.dumps(currency_names),   # NEW -> used by JS to render e.g. "AUD (Australia)"
        "metrics": metrics,
    }

    return render(request, "overview.html", ctx)





@cache_page(60 * 45)  # 45 minutes
def market_page(request):
    """
    Market view:
      - table of latest daily USD→quote rates for all quotes
      - daily / weekly / monthly % changes
      - 1-year history line chart with carousel
    """
    base_code = "USD"
    all_quotes = ["EUR", "GBP", "AUD", "NZD", "JPY", "CNY", "CHF",
                  "CAD", "MXN", "INR", "BRL", "KRW"]

    today = date.today()
    one_year_ago = today - timedelta(days=365)

    # ---- Latest ACTUAL per quote (for the table)  [QUERY 1]
    latest_actual: dict[str, dict] = {}
    rows = (
        ExchangeRate.objects
        .filter(
            base__code=base_code,
            timeframe=Timeframe.DAILY,
            quote__code__in=all_quotes,
        )
        .order_by("quote__code", "-date")
        .values("quote__code", "date", "rate")
    )
    for r in rows:
        q = r["quote__code"]
        if q in latest_actual:
            continue
        latest_actual[q] = {"date": r["date"], "rate": float(r["rate"])}

    # ---- Overall latest date (for page title / header)
    latest_date = max((info["date"] for info in latest_actual.values()), default=None)

    # ---- Country / zone labels  [QUERY 2]
    short_zone = {
        "EUR": "Eurozone",
        "GBP": "United Kingdom",
        "AUD": "Australia",
        "NZD": "New Zealand",
        "JPY": "Japan",
        "CNY": "China",
        "CHF": "Switzerland",
        "CAD": "Canada",
        "MXN": "Mexico",
        "INR": "India",
        "BRL": "Brazil",
        "KRW": "South Korea",
        "USD": "United States",
    }
    db_names = {c.code: c.name for c in Currency.objects.filter(code__in=all_quotes)}
    currency_names = {
        code: short_zone.get(code, db_names.get(code, code))
        for code in all_quotes
    }

    # ---- 1-year history for ALL currencies in ONE query  [QUERY 3]
    history_qs = (
        ExchangeRate.objects
        .filter(
            base__code=base_code,
            quote__code__in=all_quotes,
            timeframe=Timeframe.DAILY,
            date__gte=one_year_ago,
            date__lte=today,
        )
        .order_by("quote__code", "date")
        .values("quote__code", "date", "rate")
    )

    # Group by currency code
    rates_by_code: dict[str, list[tuple[date, float]]] = {code: [] for code in all_quotes}
    for r in history_qs:
        q = r["quote__code"]
        rates_by_code.setdefault(q, []).append((r["date"], float(r["rate"])))

    # ---- Helper: pct change
    def pct_change(curr: float, prev: float | None):
        if prev is None or prev == 0:
            return None
        return (curr / prev - 1.0) * 100.0

    # ---- Helper: previous rate from the in-memory series (no more DB hits)
    def get_prev_from_series(code: str, days_back: int) -> float | None:
        info = latest_actual.get(code)
        if not info:
            return None
        target_date = info["date"] - timedelta(days=days_back)
        series = rates_by_code.get(code, [])
        # series is sorted by date → scan backwards until we find <= target_date
        for d, r in reversed(series):
            if d <= target_date:
                return r
        return None

    # ---- Build table rows with % changes
    table_rows = []
    for code in all_quotes:
        info = latest_actual.get(code)
        if not info:
            continue

        rate = info["rate"]
        d_prev = get_prev_from_series(code, 1)
        w_prev = get_prev_from_series(code, 7)
        m_prev = get_prev_from_series(code, 30)

        table_rows.append(
            {
                "code": code,
                "label": f"{code} ({currency_names.get(code, code)})",
                "date": str(info["date"]),
                "rate": rate,
                "daily_change": pct_change(rate, d_prev),
                "weekly_change": pct_change(rate, w_prev),
                "monthly_change": pct_change(rate, m_prev),
            }
        )

    # ---- Build chart payload from the same in-memory series
    series_payload: dict[str, list[dict]] = {}
    for code, series in rates_by_code.items():
        series_payload[code] = [
            {"date": d.strftime("%Y-%m-%d"), "rate": r}
            for d, r in series
        ]

    ctx = {
        "table_rows": table_rows,
        "all_quotes": all_quotes,
        "currency_names_json": json.dumps(currency_names),
        "series_json": json.dumps(series_payload),
        "all_quotes_json": json.dumps(all_quotes),
        "latest_date": latest_date,
    }

    return render(request, "forecasting/market.html", ctx)












@cache_page(60 * 45)   # 45 minutes
def forecast_page(request):
    """
    Forecasts page:
      - Top table: current rate vs next-business-day forecast (+% change) per currency
      - Model dropdown: only models that actually have DAILY forecasts
      - Bottom chart: last 60 business days (actual vs backtest forecast) for one currency,
        with client-side carousel (auto-rotate + Prev/Next buttons).
    """
    base_code = "USD"

    # --- Which quotes we care about (same list you use elsewhere) ---
    all_quotes = ["EUR","GBP","AUD","NZD","JPY","CNY","CHF",
                  "CAD","MXN","INR","BRL","KRW"]

    # ──────────────────────────────────────────────────────────────
    # 1) Models that actually have DAILY forecasts  (1 query)
    # ──────────────────────────────────────────────────────────────

    # 1) Allowed models: ACTIVE daily ModelSpecs
    allowed_codes = list(
        ModelSpec.objects.filter(
            timeframe=Timeframe.DAILY,
            active=True,
        ).values_list("code", flat=True)
    )

    # 2) Models that actually have DAILY forecasts, restricted to allowed_codes
    model_codes = list(
        Forecast.objects.filter(
            base__code=base_code,
            run__timeframe=Timeframe.DAILY,
            model__code__in=allowed_codes,
        )
        .values_list("model__code", flat=True)
        .distinct()
        .order_by("model__code")
    )



    if not model_codes:
        ctx = {
            "model_codes": [],
            "selected_model": None,
            "table_rows": [],
            "available_quotes": [],
            "chart_quote": None,
            "chart_series_json": "{}",
            "available_quotes_json": "[]",
            "currency_names_json": "{}",
            "forecast_date": None,
        }
        return render(request, "forecasting/forecast.html", ctx)

    selected_model = (request.GET.get("model") or model_codes[0]).strip()
    if selected_model not in model_codes:
        selected_model = model_codes[0]

    # ──────────────────────────────────────────────────────────────
    # 2) Latest ACTUAL per quote (1 query)
    # ──────────────────────────────────────────────────────────────
    latest_actual: dict[str, dict] = {}
    rows = (
        ExchangeRate.objects
        .filter(
            base__code=base_code,
            quote__code__in=all_quotes,
            timeframe=Timeframe.DAILY,
        )
        .order_by("-date")
        .values("quote__code", "date", "rate")
    )
    for r in rows:
        code = r["quote__code"]
        if code in latest_actual:  # already have newest for this code
            continue
        latest_actual[code] = {"date": r["date"], "rate": float(r["rate"])}

    # Only keep quotes that actually have data
    available_quotes = [q for q in all_quotes if q in latest_actual]

    # Canonical forecast date for title: next biz day after latest market date
    if latest_actual:
        latest_market_date = max(info["date"] for info in latest_actual.values())
        forecast_date = next_business_day(latest_market_date)
    else:
        forecast_date = None

    if not available_quotes:
        ctx = {
            "model_codes": model_codes,
            "selected_model": selected_model,
            "table_rows": [],
            "available_quotes": [],
            "chart_quote": None,
            "chart_series_json": "{}",
            "available_quotes_json": "[]",
            "currency_names_json": "{}",
            "forecast_date": forecast_date,
        }
        return render(request, "forecasting/forecast.html", ctx)

    # ──────────────────────────────────────────────────────────────
    # 3) Country/zone labels  (1 query)
    # ──────────────────────────────────────────────────────────────
    short_zone = {
        "EUR": "Eurozone",
        "GBP": "United Kingdom",
        "AUD": "Australia",
        "NZD": "New Zealand",
        "JPY": "Japan",
        "CNY": "China",
        "CHF": "Switzerland",
        "CAD": "Canada",
        "MXN": "Mexico",
        "INR": "India",
        "BRL": "Brazil",
        "KRW": "South Korea",
        "USD": "United States",
    }
    db_names = {c.code: c.name for c in Currency.objects.filter(code__in=available_quotes)}
    currency_names = {
        code: short_zone.get(code, db_names.get(code, code))
        for code in available_quotes
    }

    # ──────────────────────────────────────────────────────────────
    # 4) Top table forecasts – batch in ONE query
    #    (instead of one Forecast query per currency)
    # ──────────────────────────────────────────────────────────────
    # target date may differ slightly per quote → map by code
    target_dates = {
        code: next_business_day(info["date"])
        for code, info in latest_actual.items()
        if code in available_quotes
    }
    target_dates_set = set(target_dates.values())

    forecast_rows = (
        Forecast.objects
        .filter(
            base__code=base_code,
            quote__code__in=available_quotes,
            run__timeframe=Timeframe.DAILY,
            model__code=selected_model,
            target_date__in=target_dates_set,
        )
        .order_by("quote__code", "-created_at")
        .values("quote__code", "target_date", "yhat")
    )

    # keep newest (by created_at order) per (code, target_date)
    best_forecast: dict[tuple[str, date], float] = {}
    for r in forecast_rows:
        key = (r["quote__code"], r["target_date"])
        if key in best_forecast:
            continue
        best_forecast[key] = float(r["yhat"])

    table_rows: list[dict] = []
    for code in available_quotes:
        info = latest_actual.get(code)
        if not info:
            continue

        curr_date = info["date"]
        curr_rate = info["rate"]
        target_date = target_dates.get(code)

        forecast_rate = best_forecast.get((code, target_date)) if target_date else None
        if forecast_rate is not None and curr_rate:
            delta_pct = (forecast_rate / curr_rate - 1.0) * 100.0
        else:
            delta_pct = None

        table_rows.append(
            {
                "code": code,
                "label": f"{code} ({currency_names.get(code, code)})",
                "latest_date": str(curr_date),
                "current_rate": curr_rate,
                "forecast_rate": forecast_rate,
                "delta_pct": delta_pct,
            }
        )

    # ──────────────────────────────────────────────────────────────
    # 5) Chart data – batch actuals and backtests
    #    (2 queries instead of 2 * len(available_quotes))
    # ──────────────────────────────────────────────────────────────
    # 5a) Actuals – one big query, then keep last 60 per code
    qs_actual_all = (
        ExchangeRate.objects
        .filter(
            base__code=base_code,
            quote__code__in=available_quotes,
            timeframe=Timeframe.DAILY,
        )
        .order_by("-date")
        .values("quote__code", "date", "rate")
    )

    actual_by_code: dict[str, list[dict]] = {code: [] for code in available_quotes}
    for r in qs_actual_all:
        code = r["quote__code"]
        buf = actual_by_code.get(code)
        if buf is None or len(buf) >= 60:
            continue
        buf.append({"date": r["date"], "rate": float(r["rate"])})

    # 5b) Backtests – one big query, keep last 60 per code
    qs_bt_all = (
        BacktestSlice.objects
        .filter(
            base__code=base_code,
            quote__code__in=available_quotes,
            run__model__code=selected_model,
            run__timeframe=Timeframe.DAILY,
            run__horizon_days=1,
        )
        .order_by("-date")
        .values("quote__code", "date", "forecast")
    )

    bt_by_code: dict[str, list[dict]] = {code: [] for code in available_quotes}
    for r in qs_bt_all:
        code = r["quote__code"]
        buf = bt_by_code.get(code)
        if buf is None or len(buf) >= 60:
            continue
        buf.append({"date": r["date"], "forecast": float(r["forecast"])})

    # Build final payload per quote
    chart_payload: dict[str, dict] = {}
    for code in available_quotes:
        actual_rows = actual_by_code.get(code, [])
        bt_rows = bt_by_code.get(code, [])

        # reverse to chronological
        actual_rows = list(reversed(actual_rows))
        bt_rows = list(reversed(bt_rows))

        labels = [str(r["date"]) for r in actual_rows]
        actual = [r["rate"] for r in actual_rows]

        bt_by_date = {str(r["date"]): r["forecast"] for r in bt_rows}
        backtest = [bt_by_date.get(d) for d in labels]

        chart_payload[code] = {
            "labels": labels,
            "actual": actual,
            "backtest": backtest,
        }

    # Default chart quote (first available); JS will handle rotation
    chart_quote = available_quotes[0] if available_quotes else None

    ctx = {
        "model_codes": model_codes,
        "selected_model": selected_model,
        "table_rows": table_rows,
        "available_quotes": available_quotes,
        "chart_quote": chart_quote,
        "chart_series_json": json.dumps(chart_payload),
        "available_quotes_json": json.dumps(available_quotes),
        "currency_names_json": json.dumps(currency_names),
        "forecast_date": forecast_date,
    }

    return render(request, "forecasting/forecast.html", ctx)
