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
        all_quotes = sorted(set(qs_avail)) or ["EUR","GBP","AUD","NZD","JPY","CNY","CHF","CAD","MXN","INR","BRL","RUB","KRW"]

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
        "RUB": "Russia",
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
                  "CAD","MXN","INR","BRL","RUB","KRW"]

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
        latest_actual[q] = {"date": r["date"], "rate": float(r["rate"])}

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
        "RUB": "Russia",
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
                "date": str(info["date"]),
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
    }
    return render(request, "market.html", ctx)












def forecast_page(request):
    """Actuals to last complete period + forward forecasts, with timeframe/model/currency/start selectors."""
    all_quotes = ["EUR","GBP","AUD","NZD","JPY","CNY","CHF","CAD","MXN","INR","BRL","RUB","KRW"]

    selected_quote = request.GET.get("currency", "ALL")
    freq_code = request.GET.get("freq", "D")
    selected_model = (request.GET.get("model") or "").strip()
    start_str = request.GET.get("start", "2020-01-01")
    start_date = pd.Timestamp(start_str)

    # Which currencies to show
    quotes = all_quotes if selected_quote == "ALL" else [selected_quote]

    df_actuals: dict[str, pd.DataFrame] = {}
    for q in quotes:
        rows = (
            ExchangeRate.objects
            .filter(base__code="USD", quote__code=q, timeframe=Timeframe.DAILY)
            .order_by("date")
            .values("date", "rate")
        )
        a = pd.DataFrame(list(rows))
        if a.empty:
            df_actuals[q] = pd.DataFrame(columns=["date", "rate"])
            continue
        a["date"] = pd.to_datetime(a["date"])
        a = a[a["date"] >= start_date].sort_values("date")
        df_actuals[q] = _resample_actual_df(a, freq_code)

    # Forecast payload (filtered)
    chart_payload = {}
    for q in quotes:
        a = df_actuals[q]
        chart_payload[q] = {
            "actual": [{"date": str(d.date()), "rate": float(r)} for d, r in zip(a["date"], a["rate"])],
            "forecast": {},
        }
        if not a.empty:
            last_dt = a["date"].max()
            fqs = Forecast.objects.filter(
                base__code="USD",
                quote__code=q,
                run__timeframe=freq_code,
                target_date__gt=last_dt,
            )
            if selected_model:
                fqs = fqs.filter(model__code=selected_model)

            for r in fqs.order_by("model__code", "target_date").values("model__code", "target_date", "yhat"):
                m = r["model__code"]
                chart_payload[q]["forecast"].setdefault(m, [])
                chart_payload[q]["forecast"][m].append(
                    {"date": str(r["target_date"]), "rate": float(r["yhat"])}
                )

    model_codes = list(
        ModelSpec.objects.filter(timeframe=freq_code, active=True).order_by("code").values_list("code", flat=True)
    )

    ctx = {
        "chart_json": json.dumps(chart_payload),
        "selected_freq": freq_code,
        "selected_model": selected_model,
        "selected_quote": selected_quote,
        "model_codes": model_codes,
        "all_quotes": all_quotes,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "freq_code": freq_code,
    }
    return render(request, "forecast.html", ctx)

def compare_page(request):
    """Compare: metrics table + per-series backtest slices (with timeframe)."""
    # Metrics table (unchanged)
    metrics_qs = (
        BacktestMetric.objects
        .select_related("run", "base", "quote")
        .annotate(
            run_model=F("run__model__code"),
            run_tf=F("run__timeframe"),
            base_code=F("base__code"),
            quote_code=F("quote__code"),
        )
        .values("run_model", "run_tf", "base_code", "quote_code", "mape", "rmse", "mae", "n")
    )
    metrics = list(metrics_qs)

    # Backtest slices — now include timeframe
    slices = (
        BacktestSlice.objects
        .select_related("run", "quote")
        .annotate(
            run_model=F("run__model__code"),
            run_tf=F("run__timeframe"),
            quote_code=F("quote__code"),
        )
        .values("run_model", "run_tf", "quote_code", "date", "actual", "forecast")
        .order_by("date")
    )

    plot: dict[str, dict] = {}
    for r in slices:
        key = f'{r["run_model"]}:{r["run_tf"]}:{r["quote_code"]}'
        plot.setdefault(
            key,
            {"model": r["run_model"], "tf": r["run_tf"], "quote": r["quote_code"], "points": []},
        )
        plot[key]["points"].append(
            {"date": str(r["date"]), "actual": float(r["actual"]), "forecast": float(r["forecast"])}
        )

    ctx = {
        "metrics_json": json.dumps(metrics),
        "plot_json": json.dumps(list(plot.values())),
    }
    return render(request, "compare.html", ctx)
