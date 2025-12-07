# apps/forecasting/management/commands/fx_daily_ops.py
from __future__ import annotations

from typing import List

from django.core.management.base import BaseCommand

from apps.forecasting.models import ModelSpec, Timeframe
from apps.forecasting.services.forecast_service import run_daily_batch
from apps.forecasting.services.backtest_service import run_backtests_daily


class Command(BaseCommand):
    help = "Run daily forecasts + backtests for all active daily ModelSpecs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--base",
            type=str,
            default="USD",
            help="Base currency (e.g. USD)",
        )
        parser.add_argument(
            "--quotes",
            type=str,
            default="AUD",
            help='Comma-separated list of quote currencies, e.g. "AUD,EUR,GBP"',
        )
        parser.add_argument(
            "--window",
            type=int,
            default=60,
            help="Backtest window in business days",
        )

    def handle(self, *args, **options):
        base_code: str = options["base"].upper()
        quotes: List[str] = [
            q.strip().upper()
            for q in options["quotes"].split(",")
            if q.strip()
        ]
        window: int = options["window"]

        # 1) find all active daily ModelSpecs with forecasts (horizon=1)
        specs = (
            ModelSpec.objects
            .filter(
                timeframe=Timeframe.DAILY,
                active=True,
                horizon_days=1,
            )
            .order_by("code")
        )

        if not specs.exists():
            self.stdout.write(self.style.WARNING("No active daily ModelSpecs found."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Running daily ops for models: {', '.join(s.code for s in specs)}"
            )
        )

        for spec in specs:
            # spec.code looks like "ets_r-daily" → we need the registry key "ets_r"
            model_name = spec.code.split("-")[0]

            self.stdout.write(self.style.SUCCESS(f"→ Forecasts: {model_name}"))
            run_daily_batch(base_code=base_code, quotes=quotes, model=model_name)

            self.stdout.write(self.style.SUCCESS(f"→ Backtests: {model_name}"))
            run_backtests_daily(
                base_code=base_code,
                quotes=quotes,
                model=model_name,
                window=window,
                new_run=False,   # or True if you prefer
            )

        self.stdout.write(self.style.SUCCESS("Daily FX ops (DB-driven) finished."))
