# FILE: apps/forecasting/management/commands/run_daily_forecasts.py
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from apps.forecasting.services.forecast_service import run_daily_batch
from apps.forecasting.models_lib.registry import list_models  # <- dynamic models

class Command(BaseCommand):
    help = "Run 1-day-ahead daily forecasts."

    def add_arguments(self, p):
        p.add_argument("--base", default="USD", help="Base currency code (e.g., USD)")
        p.add_argument("--quotes", default="EUR,GBP,AUD",
                       help="Comma-separated quote codes (e.g., EUR,GBP,AUD)")
        # no choices here; allow any registered model
        p.add_argument("--model", default="naive",
                       help="Model key from the registry (e.g., naive, drift, arima, prophet)")

    def handle(self, *args, **o):
        base = (o["base"] or "USD").upper()
        quotes = [q.strip().upper() for q in (o["quotes"] or "").split(",") if q.strip()]
        model = (o["model"] or "naive").lower()

        available = list_models()  # e.g., ['naive','drift','arima','prophet'] if installed
        if available and model not in available:
            raise CommandError(
                f"Unknown model '{model}'. Available: {', '.join(available)}"
            )

        self.stdout.write(self.style.NOTICE(
            f"Running DAILY forecasts: base={base}, quotes={quotes}, model={model}"
        ))
        run_daily_batch(base_code=base, quotes=quotes, model=model)
        self.stdout.write(self.style.SUCCESS("Done."))
