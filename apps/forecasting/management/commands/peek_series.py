from __future__ import annotations
from datetime import date
from typing import Optional
from django.core.management.base import BaseCommand, CommandError

from apps.forecasting.pipelines.prepare_series import load_series

def parse_date(s: Optional[str]) -> Optional[date]:
    return date.fromisoformat(s) if s else None

class Command(BaseCommand):
    help = "Load a clean pandas Series for a pair and show a quick summary (optional CSV export)."

    def add_arguments(self, p):
        p.add_argument("--base", default="USD", help="Base currency code (default: USD)")
        p.add_argument("--quote", required=True, help="Quote currency code, e.g. EUR")
        p.add_argument("--freq", choices=["D", "W"], default="D", help="D=daily, W=weekly(strict Friday)")
        p.add_argument("--fill", choices=["none", "ffill_within"], default="none",
                       help="Daily only: no fill (default) or forward-fill within observed range")
        p.add_argument("--start", type=str, help="YYYY-MM-DD (optional)")
        p.add_argument("--end", type=str, help="YYYY-MM-DD (optional)")
        p.add_argument("--csv", type=str, help="Optional file path to export as CSV")

    def handle(self, *args, **o):
        base = o["base"].upper()
        quote = o["quote"].upper()
        freq = o["freq"]
        fill = o["fill"]
        start = parse_date(o.get("start"))
        end = parse_date(o.get("end"))

        self.stdout.write(self.style.NOTICE(
            f"Loading series: {base}->{quote} freq={freq} fill={fill} "
            f"range={start or 'min'}..{end or 'max'}"
        ))

        try:
            bundle = load_series(base, quote, freq=freq, start=start, end=end, fill=fill)
            s = bundle.y
        except Exception as e:
            raise CommandError(str(e))

        if s.empty:
            self.stdout.write(self.style.WARNING("No data returned."))
            return

        n = len(s)
        d0, d1 = s.index.min().date(), s.index.max().date()
        self.stdout.write(self.style.SUCCESS(f"OK: {n} points from {d0} to {d1}"))
        self.stdout.write("Tail:")
        self.stdout.write(str(s.tail()))

        if o.get("csv"):
            path = o["csv"]
            s.reset_index().rename(columns={"index": "date", 0: "rate", "y": "rate"}).to_csv(path, index=False)
            self.stdout.write(self.style.SUCCESS(f"Exported CSV → {path}"))
