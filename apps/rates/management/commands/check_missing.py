from __future__ import annotations
from datetime import date, timedelta
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db.models import Min, Max
from apps.core.models import Currency, Timeframe, ExchangeSource
from apps.rates.models import ExchangeRate

def business_days(start: date, end: date):
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # Mon–Fri
            yield cur
        cur += timedelta(days=1)

class Command(BaseCommand):
    help = "Scan USD→{quotes} for missing business days between min..max dates."

    def add_arguments(self, p):
        p.add_argument("--base", default="USD")
        p.add_argument("--quotes", default="EUR,GBP,AUD")
        p.add_argument("--start", type=str, help="YYYY-MM-DD (optional)")
        p.add_argument("--end", type=str, help="YYYY-MM-DD (optional)")

    def handle(self, *args, **o):
        base_code = o["base"].upper()
        quotes = [q.strip().upper() for q in o["quotes"].split(",") if q.strip()]
        base = Currency.objects.get(code=base_code)
        src = ExchangeSource.objects.get(code="frankfurter")

        # global min..max (unless overridden)
        agg = ExchangeRate.objects.filter(
            source=src, base=base, timeframe=Timeframe.DAILY
        ).aggregate(Min("date"), Max("date"))
        gmin, gmax = agg["date__min"], agg["date__max"]

        if not gmin:
            self.stderr.write("No data found.")
            return

        if o.get("start"):
            gmin = date.fromisoformat(o["start"])
        if o.get("end"):
            gmax = date.fromisoformat(o["end"])

        self.stdout.write(self.style.NOTICE(f"Scanning {gmin} → {gmax} (business days)"))

        # For speed, pre-load all existing dates per quote
        existing = defaultdict(set)
        qs = ExchangeRate.objects.filter(
            source=src, base=base, timeframe=Timeframe.DAILY, date__range=(gmin, gmax)
        ).values_list("quote__code", "date")
        for qcode, d in qs:
            existing[qcode].add(d)

        any_gaps = False
        for qcode in quotes:
            miss = [d for d in business_days(gmin, gmax) if d not in existing[qcode]]
            if miss:
                any_gaps = True
                self.stdout.write(self.style.WARNING(f"{base_code}->{qcode}: {len(miss)} missing"))
                # Print a few examples
                self.stdout.write("  e.g. " + ", ".join(d.isoformat() for d in miss[:10]) + (" ..." if len(miss) > 10 else ""))
            else:
                self.stdout.write(self.style.SUCCESS(f"{base_code}->{qcode}: OK (no business-day gaps)"))

        if not any_gaps:
            self.stdout.write(self.style.SUCCESS("All requested pairs are complete for business days."))
