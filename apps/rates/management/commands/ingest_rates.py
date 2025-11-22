from django.core.management.base import BaseCommand
from datetime import datetime
from apps.rates.services.ingest_rates import (
    fast_ingest_monthly,
    ingest_missing_daily,
    ingest_range_months,
)

class Command(BaseCommand):
    help = "Ingest FX rates from Frankfurter. Use --monthly (backfill), --daily (incremental), or --start/--end for a manual range."

    def add_arguments(self, parser):
        parser.add_argument("--monthly", action="store_true", help="Backfill month-by-month for the last N years")
        parser.add_argument("--daily", action="store_true", help="Fetch only missing daily rows up to today")
        parser.add_argument("--years", type=int, default=10, help="Years to backfill when using --monthly (default: 10)")
        parser.add_argument("--base", default="USD", help="Base currency code (default: USD)")
        parser.add_argument("--quotes", default="EUR,GBP,AUD", help="Comma-separated quote codes")
        parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD) for manual range ingest")
        parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD) for manual range ingest")

    def handle(self, *args, **opts):
        base = opts["base"].upper()
        quotes = [q.strip().upper() for q in opts["quotes"].split(",") if q.strip()]

        self.stdout.write(self.style.NOTICE(f"Starting ingestion: base={base}, quotes={quotes}"))

        if opts["monthly"]:
            self.stdout.write(self.style.NOTICE(f"Running monthly backfill for last {opts['years']} years..."))
            n = fast_ingest_monthly(years=opts["years"], base_code=base, quotes=quotes)
            self.stdout.write(self.style.SUCCESS(f"✅ Monthly backfill attempted {n} rows (duplicates ignored)."))
            return

        if opts["daily"]:
            self.stdout.write(self.style.NOTICE("Running daily catch-up..."))
            n = ingest_missing_daily(base_code=base, quotes=quotes)
            self.stdout.write(self.style.SUCCESS(f"✅ Daily ingest inserted {n} rows (duplicates ignored)."))
            return


        if opts["start"] or opts["end"]:
            if not (opts["start"] and opts["end"]):
                self.stderr.write("--start and --end must be provided together (YYYY-MM-DD).")
                return
            try:
                start = datetime.strptime(opts["start"], "%Y-%m-%d").date()
                end   = datetime.strptime(opts["end"], "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write("Invalid date format. Use YYYY-MM-DD.")
                return
            if start > end:
                self.stderr.write("Start date must be <= end date.")
                return

            self.stdout.write(self.style.NOTICE(f"Running custom ingest {start} → {end}..."))

            if start == end:
                # NEW: fetch exactly one day
                from apps.rates.services.ingest_rates import ingest_day
                n = ingest_day(start, base_code=base, quotes=quotes)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Single-day ingest {start} attempted {n} rows (duplicates ignored).")
                )
            else:
                # Existing: month-chunked range ingest
                from apps.rates.services.ingest_rates import ingest_range_months
                n = ingest_range_months(start, end, base_code=base, quotes=quotes)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Range ingest {start}..{end} attempted {n} rows (duplicates ignored).")
                )
            return






        self.stdout.write(self.style.WARNING("⚠️ Nothing to do. Use --monthly, --daily, or --start/--end."))
