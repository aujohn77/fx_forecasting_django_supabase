from __future__ import annotations
import requests
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterator
from django.db import transaction
from django.db.models import Max
from apps.core.models import Currency, ExchangeSource, Timeframe
from apps.rates.models import ExchangeRate

FRANK_BASE_URL = "https://api.frankfurter.app"

# ---------- helpers ----------
def _get_source() -> ExchangeSource:
    src, _ = ExchangeSource.objects.get_or_create(
        code="frankfurter",
        defaults={"name": "Frankfurter", "base_url": FRANK_BASE_URL},
    )
    return src

def _get_currency(code: str) -> Currency:
    code = code.upper()
    ccy, _ = Currency.objects.get_or_create(
        code=code,
        defaults={"name": code, "symbol": code, "decimals": 6},
    )
    return ccy

def month_iter(start: date, end: date) -> Iterator[tuple[date, date]]:
    """Yield inclusive [month_start, month_end] pairs between start..end."""
    cur = date(start.year, start.month, 1)
    while cur <= end:
        nxt = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
        yield (cur, min(end, nxt - timedelta(days=1)))
        cur = nxt

def fetch_frankfurter_range(start: date, end: date, base_code: str, quote_codes: list[str]) -> dict[str, dict[str, float]]:
    """Return {'YYYY-MM-DD': {'EUR': 0.93, 'GBP': 0.78, ...}, ...}"""
    url = f"{FRANK_BASE_URL}/{start:%Y-%m-%d}..{end:%Y-%m-%d}"
    params = {"from": base_code.upper(), "to": ",".join([q.upper() for q in quote_codes])}
    print(f"  ↳ GET {url}  params={params}")  # <-- show the exact fetch
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json().get("rates", {})

# ---------- public API ----------
@transaction.atomic
def ingest_range_months(start: date, end: date, base_code: str = "USD", quotes: list[str] | None = None) -> int:
    """
    Ingest a specific range month-by-month.
    Idempotent via bulk_create(ignore_conflicts=True).
    """
    if quotes is None:
        quotes = ["EUR", "GBP", "AUD"]

    source = _get_source()
    base = _get_currency(base_code)
    quotes = [q.upper() for q in quotes]
    # ensure quote currencies exist
    code2ccy = {c.code: c for c in Currency.objects.filter(code__in=quotes)}

    print(f"▶️  Ingesting {base.code} → {quotes} from {start} to {end} (monthly chunks)")
    total = 0
    for m_start, m_end in month_iter(start, end):
        print(f"📅 Month {m_start.strftime('%Y-%m')} ({m_start} → {m_end}) …")
        data = fetch_frankfurter_range(m_start, m_end, base.code, quotes)

        rows: list[ExchangeRate] = []
        # iterate days in order so logs look nice
        for ds in sorted(data.keys()):
            per_day = data[ds]
            d = date.fromisoformat(ds)
            for q_code, val in per_day.items():
                quote = code2ccy.get(q_code)
                if not quote:
                    quote = _get_currency(q_code)
                    code2ccy[q_code] = quote
                rows.append(
                    ExchangeRate(
                        source=source,
                        base=base,
                        quote=quote,
                        timeframe=Timeframe.DAILY,
                        date=d,
                        rate=Decimal(str(val)),
                    )
                )

        if rows:
            ExchangeRate.objects.bulk_create(rows, ignore_conflicts=True, batch_size=2000)
            total += len(rows)
            print(f"   ✅ Stored/attempted rows this month: {len(rows)} (duplicates ignored)")
        else:
            print("   ⚠️  No rows returned for this month.")

    print(f"✔️  Monthly ingest complete. Total rows attempted: {total}")
    return total

def fast_ingest_monthly(years: int = 10, base_code: str = "USD", quotes: list[str] | None = None) -> int:
    """Backfill last N years using monthly chunks."""
    end = date.today()
    start = end - timedelta(days=365 * years + 10)  # small buffer
    print(f"▶️  Backfill last {years} years: {start} → {end}")
    return ingest_range_months(start, end, base_code=base_code, quotes=quotes)

def ingest_missing_daily(base_code: str = "USD", quotes: list[str] | None = None) -> int:
    """
    Incremental daily updater: fetches only missing days through today.
    Safe to run every day; no-ops when up to date.
    """
    if quotes is None:
        quotes = ["EUR", "GBP", "AUD"]

    source = _get_source()
    base = _get_currency(base_code)

    last = (
        ExchangeRate.objects
        .filter(source=source, base=base, timeframe=Timeframe.DAILY)
        .aggregate(Max("date"))
        .get("date__max")
    )
    start = (last + timedelta(days=1)) if last else (date.today() - timedelta(days=3))
    end = date.today()
    if start > end:
        print("✔️  Daily ingest: already up to date.")
        return 0

    print(f"▶️  Daily ingest for {base.code} → {quotes}: {start} → {end}")
    data = fetch_frankfurter_range(start, end, base.code, [q.upper() for q in quotes])

    rows: list[ExchangeRate] = []
    for ds in sorted(data.keys()):        # print in day order
        per_day = data[ds]
        d = date.fromisoformat(ds)
        print(f"   • {d.isoformat()} ({len(per_day)} quotes)")
        for q_code, val in per_day.items():
            quote = _get_currency(q_code)
            rows.append(
                ExchangeRate(
                    source=source,
                    base=base,
                    quote=quote,
                    timeframe=Timeframe.DAILY,
                    date=d,
                    rate=Decimal(str(val)),
                )
            )

    if rows:
        ExchangeRate.objects.bulk_create(rows, ignore_conflicts=True, batch_size=500)
        print(f"✔️  Daily ingest complete. Rows attempted: {len(rows)} (duplicates ignored)")
    else:
        print("⚠️  Daily ingest returned no rows.")
    return len(rows)

# Optional: keep a single-day helper for quick tests
def ingest_day(day: date, base_code: str = "USD", quotes: list[str] | None = None) -> int:
    """Insert one day's rates (mostly for manual testing)."""
    if quotes is None:
        quotes = ["EUR", "GBP", "AUD"]
    print(f"▶️  Single-day ingest: {day} {base_code} → {quotes}")
    data = fetch_frankfurter_range(day, day, base_code, quotes)
    per_day = data.get(day.isoformat(), {})
    if not per_day:
        print("⚠️  No data for that day.")
        return 0
    source = _get_source()
    base = _get_currency(base_code)
    rows = [
        ExchangeRate(
            source=source,
            base=base,
            quote=_get_currency(q_code),
            timeframe=Timeframe.DAILY,
            date=day,
            rate=Decimal(str(val)),
        )
        for q_code, val in per_day.items()
    ]
    ExchangeRate.objects.bulk_create(rows, ignore_conflicts=True)
    print(f"✔️  Inserted/attempted {len(rows)} rows for {day}.")
    return len(rows)
