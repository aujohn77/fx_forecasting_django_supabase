# apps/rates/admin.py
from django.contrib import admin, messages
from django.http import HttpResponse
import csv
from .models import ExchangeRate

@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display  = ("date","source","base","quote","timeframe","rate")
    list_filter   = ("source","base","quote","timeframe","date")
    search_fields = ("base__code","quote__code")
    date_hierarchy = "date"
    actions = ["delete_filtered", "export_as_csv"]

    @admin.action(description="Delete ALL rows that match current filters")
    def delete_filtered(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        messages.success(request, f"Deleted {count} ExchangeRate rows.")

    @admin.action(description="Export selected (or filtered) rows to CSV")
    def export_as_csv(self, request, queryset):
        # Use the filtered queryset, not just the checked boxes
        qs = queryset.order_by("date")

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=exchange_rates.csv"
        writer = csv.writer(response)

        # header
        writer.writerow(["date", "source", "base", "quote", "timeframe", "rate"])

        # rows
        for obj in qs:
            writer.writerow([
                obj.date,
                obj.source.code,
                obj.base.code,
                obj.quote.code,
                obj.get_timeframe_display(),
                obj.rate,
            ])
        return response
