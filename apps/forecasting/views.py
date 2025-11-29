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






def market_page(request):
    """
    Market view:
      - table of latest daily USD→quote rates for all quotes
      - daily / weekly / monthly % changes
      - 5y history line chart with carousel
    """
    base_code = "USD"
    all_quotes = ["EUR","GBP","AUD","NZD","JPY","CNY","CHF",
                  "CAD","MXN","INR","BRL", "KRW"]

    today = date.today()
    five_years_ago = today - timedelta(days=5 * 365)

    # ---- Latest ACTUAL per quote (for the table)
    latest_actual: dict[str, dict] = {}
    rows = (
        ExchangeRate.objects
        .filter(base__code=base_code,
                timeframe=Timeframe.DAILY,
                quote__code__in=all_quotes)
        .order_by("quote__code", "-date")
        .values("quote__code", "date", "rate")
    )
    for r in rows:
        q = r["quote__code"]
        if q in latest_actual:
            continue
        # keep date as a real date object here
        latest_actual[q] = {"date": r["date"], "rate": float(r["rate"])}

    # ---- Overall latest date (for page title / header)
    if latest_actual:
        latest_date = max(info["date"] for info in latest_actual.values())
    else:
        latest_date = None

    # helpers for % changes
    def get_prev_rate(code: str, days_back: int):
        info = latest_actual.get(code)
        if not info:
            return None
        ref_date = info["date"] - timedelta(days=days_back)
        prev = (
            ExchangeRate.objects
            .filter(base__code=base_code,
                    quote__code=code,
                    timeframe=Timeframe.DAILY,
                    date__lte=ref_date)
            .order_by("-date")
            .values("rate")
            .first()
        )
        return float(prev["rate"]) if prev else None

    def pct_change(curr: float, prev: float | None):
        if prev is None or prev == 0:
            return None
        return (curr / prev - 1.0) * 100.0

    # ---- Country / zone labels
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
    currency_names = {code: short_zone.get(code, db_names.get(code, code))
                      for code in all_quotes}

    # ---- Build table rows (including % changes)
    table_rows = []
    for code in all_quotes:
        info = latest_actual.get(code)
        if not info:
            continue

        rate = info["rate"]
        d_prev = get_prev_rate(code, 1)
        w_prev = get_prev_rate(code, 7)
        m_prev = get_prev_rate(code, 30)

        table_rows.append(
            {
                "code": code,
                "label": f"{code} ({currency_names.get(code, code)})",
                "date": str(info["date"]),  # string for display in table (though you removed the column)
                "rate": rate,
                "daily_change": pct_change(rate, d_prev),
                "weekly_change": pct_change(rate, w_prev),
                "monthly_change": pct_change(rate, m_prev),
            }
        )

    # ---- 5y history per currency for the chart
    series_payload: dict[str, list[dict]] = {}
    for code in all_quotes:
        qs = (
            ExchangeRate.objects
            .filter(base__code=base_code,
                    quote__code=code,
                    timeframe=Timeframe.DAILY,
                    date__gte=five_years_ago,
                    date__lte=today)
            .order_by("date")
            .values("date", "rate")
        )
        series_payload[code] = [
            {"date": str(r["date"]), "rate": float(r["rate"])}
            for r in qs
        ]

    ctx = {
        "table_rows": table_rows,
        "all_quotes": all_quotes,
        "currency_names_json": json.dumps(currency_names),
        "series_json": json.dumps(series_payload),
        "all_quotes_json": json.dumps(all_quotes),
        "latest_date": latest_date,  # 👈 new context variable
    }
    

    return render(request, "forecasting/market.html", ctx)













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

    # --- Models that actually have DAILY forecasts ---
    model_codes = list(
        Forecast.objects.filter(
            base__code=base_code,
            run__timeframe=Timeframe.DAILY,
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
        return render(request, "forecast.html", ctx)

    selected_model = (request.GET.get("model") or model_codes[0]).strip()
    if selected_model not in model_codes:
        selected_model = model_codes[0]

    # --- Latest ACTUAL per quote (for table + to know which quotes are usable) ---
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
        if code in latest_actual:
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
        return render(request, "forecast.html", ctx)

    # --- Country/zone labels (same idea as in market_page) ---
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

    # --- Top table: current vs next-biz-day forecast ---
    table_rows: list[dict] = []
    for code in available_quotes:
        info = latest_actual.get(code)
        if not info:
            continue

        curr_date = info["date"]
        curr_rate = info["rate"]
        target_date = next_business_day(curr_date)

        f_row = (
            Forecast.objects
            .filter(
                base__code=base_code,
                quote__code=code,
                run__timeframe=Timeframe.DAILY,
                model__code=selected_model,
                target_date=target_date,
            )
            .order_by("-created_at")
            .values("yhat")
            .first()
        )

        if f_row:
            forecast_rate = float(f_row["yhat"])
            delta_pct = (forecast_rate / curr_rate - 1.0) * 100.0 if curr_rate else None
        else:
            forecast_rate = None
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

    # --- Chart data: build series for ALL available quotes ---
    chart_payload: dict[str, dict] = {}
    for code in available_quotes:
        # Actuals: last 60 business days
        qs_actual = (
            ExchangeRate.objects
            .filter(
                base__code=base_code,
                quote__code=code,
                timeframe=Timeframe.DAILY,
            )
            .order_by("-date")
            .values("date", "rate")[:60]
        )
        actual_rows = list(qs_actual)
        actual_rows.reverse()  # chronological

        labels = [str(r["date"]) for r in actual_rows]
        actual = [float(r["rate"]) for r in actual_rows]

        # Backtests aligned on the same dates
        qs_bt = (
            BacktestSlice.objects
            .filter(
                base__code=base_code,
                quote__code=code,
                run__model__code=selected_model,
                run__timeframe=Timeframe.DAILY,
                run__horizon_days=1,
            )
            .order_by("-date")
            .values("date", "forecast")[:60]
        )
        bt_rows = list(qs_bt)
        bt_rows.reverse()

        bt_by_date = {str(r["date"]): float(r["forecast"]) for r in bt_rows}
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

