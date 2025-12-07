from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.management import call_command
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache


from apps.forecasting.services.forecast_service import (
    run_daily_batch,
    run_weekly_batch,
)
from apps.forecasting.services.backtest_service import (
    run_backtests_daily,
    run_backtests_weekly,
)
from apps.forecasting.models_lib.registry import list_models  # dynamic model list

# ──────────────────────────────────────────────────────────────────────────────
# Default configuration
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_USD_QUOTES = [
    "EUR", "GBP", "AUD", "NZD", "JPY", "CNY", "CHF",
    "CAD", "MXN", "INR", "BRL", "KRW",
]
DEFAULT_QUOTES_CSV = ",".join(DEFAULT_USD_QUOTES)


def _admin_link(model: str, pk) -> str:
    """Quick admin change link (works for UUIDs & ints)."""
    return f"/admin/forecasting/{model}/{pk}/change/"


def _available_models() -> list[str]:
    """Pull models from the registry; fall back if nothing loads."""
    try:
        models = list_models()
    except Exception:
        models = []
    if not models:
        models = ["naive", "drift"]
    return models


def _normalize_model(selected: str | None, models_list: list[str]) -> str:
    """Ensure the selected model is valid; otherwise default to first."""
    chosen = (selected or models_list[0]).lower()
    if chosen not in {m.lower() for m in models_list}:
        return models_list[0]
    return chosen


# ──────────────────────────────────────────────────────────────────────────────
# Console pages
# ──────────────────────────────────────────────────────────────────────────────
@staff_member_required
@csrf_protect
def console(request):
    """Show the Ops Console page with simple forms."""
    model_choices = _available_models()
    ctx = {
        "model_choices": model_choices,
        "default_quotes": DEFAULT_QUOTES_CSV,
        "today": date.today().isoformat(),
    }
    return render(request, "ops/console.html", ctx)


@staff_member_required
@csrf_protect
def run_action(request):
    """Single POST endpoint that branches by action."""
    if request.method != "POST":
        return redirect(reverse("ops:console"))

    action = request.POST.get("action")

    # Common inputs
    base = (request.POST.get("base") or "USD").upper()
    quotes = [
        q.strip().upper()
        for q in (request.POST.get("quotes") or DEFAULT_QUOTES_CSV).split(",")
        if q.strip()
    ]

    # Dynamic model selection
    model_choices = _available_models()
    model = _normalize_model(request.POST.get("model"), model_choices)

    try:
        if action == "ingest_daily":
            call_command("ingest_rates", daily=True, base=base, quotes=",".join(quotes))
            messages.success(request, f"Daily ingest started for {base}->{quotes}. See console logs.")

        elif action == "ingest_monthly":
            years = int(request.POST.get("years") or 10)
            call_command("ingest_rates", monthly=True, years=years, base=base, quotes=",".join(quotes))
            messages.success(request, f"Monthly backfill (last {years}y) queued for {base}->{quotes}.")

        elif action == "ingest_range":
            start = parse_date(request.POST.get("start") or "")
            end = parse_date(request.POST.get("end") or "")
            if not (start and end):
                messages.error(request, "Please provide Start and End for range ingest (YYYY-MM-DD).")
            else:
                call_command("ingest_rates", start=start.isoformat(), end=end.isoformat(), base=base, quotes=",".join(quotes))
                messages.success(request, f"Custom ingest {start} → {end} for {base}->{quotes} queued.")

        elif action == "check_missing":
            call_command("check_missing", base=base, quotes=",".join(quotes))
            messages.success(request, "Checked for missing business days. See console output for details.")

        elif action == "forecast_daily":
            run_daily_batch(base_code=base, quotes=quotes, model=model)
            messages.success(request, f"Daily forecasts run ({model}) for {base}->{quotes}. See Admin → Forecasts/ForecastRuns.")

        elif action == "forecast_weekly":
            run_weekly_batch(base_code=base, quotes=quotes, model=model)
            messages.success(request, f"Weekly forecasts run ({model}) for {base}->{quotes}.")

        elif action == "backtest_daily":
            window = int(request.POST.get("window") or 60)
            newrun = bool(request.POST.get("newrun"))
            run = run_backtests_daily(base_code=base, quotes=quotes, model=model, window=window, new_run=newrun)
            messages.success(request, f"Daily backtests run ({model}, last {window} biz days) → <a href='{_admin_link('backtestrun', run.id)}'>open in Admin</a>.", extra_tags="safe")

        elif action == "backtest_weekly":
            window = int(request.POST.get("window") or 60)
            newrun = bool(request.POST.get("newrun"))
            run = run_backtests_weekly(base_code=base, quotes=quotes, model=model, window=window, new_run=newrun)
            messages.success(request, f"Weekly backtests run ({model}, last {window} Fridays) → <a href='{_admin_link('backtestrun', run.id)}'>open in Admin</a>.", extra_tags="safe")
        elif action == "clear_cache":        
            cache.clear()
        else:
            messages.error(request, "Unknown action.")

    except Exception as e:
        messages.error(request, f"Error: {e}")

    return redirect(reverse("ops:console"))
