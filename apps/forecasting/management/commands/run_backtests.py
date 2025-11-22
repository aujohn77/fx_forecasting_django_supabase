# FILE: apps/forecasting/management/commands/run_backtests.py
from __future__ import annotations
from typing import List
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Timeframe
from apps.forecasting.services.backtest_service import BacktestOptions, run_backtests
from apps.forecasting.models_lib.registry import list_models  # helper you likely have; see note below

class Command(BaseCommand):
    help = "Run walk-forward backtests for a given model/timeframe over a rolling window."

    def add_arguments(self, parser):
        parser.add_argument("--base", default="USD", help="Base currency code (default USD)")
        parser.add_argument("--quotes", default="EUR,GBP,AUD", help="Comma-separated quote codes")
        parser.add_argument("--model", required=True, help="Model key (e.g., naive, drift, arima, prophet)")
        parser.add_argument("--window", type=int, default=60, help="Rolling train window length")
        parser.add_argument("--horizon", type=int, default=1, help="Forecast horizon steps")
        tf = parser.add_argument_group("Timeframe").add_mutually_exclusive_group()
        tf.add_argument("--daily", action="store_true")
        tf.add_argument("--weekly", action="store_true")
        tf.add_argument("--monthly", action="store_true")

        # Optional model params, e.g. --param order=1,1,0 --param seasonality_mode=additive
        parser.add_argument("--param", action="append", default=[], help="Model param key=val (repeatable)")

    def handle(self, *args, **options):
        base = options["base"].upper()
        quotes: List[str] = [q.strip().upper() for q in options["quotes"].split(",") if q.strip()]
        model = options["model"].lower()
        window = options["window"]
        horizon = options["horizon"]

        if options["daily"]:
            timeframe = Timeframe.DAILY
        elif options["weekly"]:
            timeframe = Timeframe.WEEKLY
        elif options["monthly"]:
            timeframe = Timeframe.MONTHLY
        else:
            timeframe = Timeframe.DAILY  # default

        # Validate model exists in registry
        try:
            available = set(list_models())  # e.g., returns ["naive","drift","arima","prophet"]
        except Exception:
            available = set()
        if available and model not in available:
            raise CommandError(f"Unknown model '{model}'. Available: {sorted(available)}")

        # Parse --param key=value
        params = {}
        for kv in options["param"]:
            if "=" not in kv:
                raise CommandError(f"--param must be key=value, got: {kv}")
            k, v = kv.split("=", 1)
            # lightweight literal parsing (ints, floats, tuples)
            v = v.strip()
            if v.isdigit():
                v = int(v)
            else:
                try:
                    v = float(v)
                except ValueError:
                    # tuple like 1,1,0
                    if "," in v and all(p.strip("- ").replace(".","",1).replace("e","").replace("E","").replace("+","").lstrip().replace("+","").replace("_","").replace(" ", "") for p in v.split(",")):
                        v = tuple(int(p) if p.strip().lstrip("-").isdigit() else float(p) for p in v.split(","))
                    # else leave as string
            params[k.strip()] = v

        opts = BacktestOptions(
            base_code=base,
            quotes=quotes,
            model=model,
            window=window,
            horizon=horizon,
            timeframe=timeframe,
            params=params,
        )

        run = run_backtests(opts)
        self.stdout.write(self.style.SUCCESS(
            f"Backtest run {run.id} complete | model={model} | tf={timeframe} | window={window} | horizon={horizon} | quotes={quotes}"
        ))
