# apps/forecasting/admin.py
from django.contrib import admin
from .models import (
    ModelSpec, ForecastRun, Forecast,
    BacktestRun, BacktestSlice, BacktestMetric,
)

# --- ModelSpec ---
@admin.register(ModelSpec)
class ModelSpecAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "library", "timeframe", "horizon_days", "active")
    list_filter = ("library", "timeframe", "active")
    search_fields = ("code", "name", "library")
    ordering = ("code",)
    list_per_page = 50




@admin.register(ForecastRun)
class ForecastRunAdmin(admin.ModelAdmin):
    list_display = (
        "id", "as_of", "data_cutoff_date",
        "forecast_target_date",  "timeframe", 
        "model_name", "trigger"
    )
    list_filter = ("timeframe", "model_name", "trigger")
    date_hierarchy = "as_of"
    ordering = ("-as_of",)
    readonly_fields = ("as_of",)
    list_per_page = 50
    search_fields = ("id", "timeframe", "model_name", "trigger")

    @admin.display(description="Forecast Target Date")
    def forecast_target_date(self, obj):
        row = obj.forecasts.order_by("target_date").first()
        return row.target_date if row else None


@admin.register(Forecast)
class ForecastAdmin(admin.ModelAdmin):
    list_display = ("run", "model", "base", "quote", "target_date", "yhat")
    list_filter = ("model", "base", "quote", "target_date")
    date_hierarchy = "target_date"
    search_fields = ("model__code", "base__code", "quote__code")
    ordering = ("-target_date", "model__code", "base__code", "quote__code")
    list_select_related = ("run", "model", "base", "quote")
    autocomplete_fields = ("run", "model", "base", "quote")
    list_per_page = 100
    # If you store intervals/ci fields, consider:
    # readonly_fields = ("created_at", "updated_at")


# --- Backtests ---
class BacktestSliceInline(admin.TabularInline):
    model = BacktestSlice
    fields = ("base", "quote", "date", "actual", "forecast")
    extra = 0
    show_change_link = True
    ordering = ("-date",)
    autocomplete_fields = ("base", "quote")


class BacktestMetricInline(admin.TabularInline):
    model = BacktestMetric
    fields = ("base", "quote", "mape", "rmse", "mae", "n")
    extra = 0
    show_change_link = True
    autocomplete_fields = ("base", "quote")


@admin.register(BacktestRun)
class BacktestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "model", "window_start", "window_end", "horizon_days")
    list_filter = ("model", "horizon_days")
    date_hierarchy = "window_start"
    search_fields = ("model__code",)
    ordering = ("-window_end", "-window_start")
    list_select_related = ("model",)
    autocomplete_fields = ("model",)
    inlines = [BacktestSliceInline, BacktestMetricInline]
    list_per_page = 50


from django.contrib import admin
from .models import BacktestSlice

def _short_uuid(u):
    s = str(u)
    return s.split("-")[0]  # e.g., a114593e

@admin.register(BacktestSlice)
class BacktestSliceAdmin(admin.ModelAdmin):
    # Pretty run label + short id
    @admin.display(ordering="run__window_end", description="Run")
    def run_label(self, obj):
        r = obj.run
        tf = getattr(r, "get_timeframe_display", lambda: r.timeframe)()
        return (
            f"{r.model.code} | {tf} | H{r.horizon_days} | "
            f"{r.window_start:%Y-%m-%d}→{r.window_end:%Y-%m-%d} "
            f"[{_short_uuid(r.id)}]"
        )

    # Renamed columns
    @admin.display(ordering="date", description="Targeted Date")
    def targeted_date(self, obj):
        return obj.date

    @admin.display(ordering="actual", description="Observed Rate")
    def observed_value(self, obj):
        return obj.actual

    @admin.display(ordering="forecast", description="Forecasted Rate")
    def forecasted_value(self, obj):
        return obj.forecast

    list_display = (
        "run_label",
        "base",
        "quote",
        "targeted_date",
        "observed_value",
        "forecasted_value",
    )
    list_display_links = ("run_label", "targeted_date")

    list_filter = (
        ("run", admin.RelatedOnlyFieldListFilter),
        "base",
        "quote",
        "date",   # underlying field
    )
    date_hierarchy = "date"

    search_fields = ("run__id", "run__model__code", "base__code", "quote__code")
    ordering = ("-date", "base__code", "quote__code")
    list_select_related = ("run", "base", "quote")
    autocomplete_fields = ("run", "base", "quote")
    list_per_page = 100


@admin.register(BacktestMetric)
class BacktestMetricAdmin(admin.ModelAdmin):
    list_display = ("run", "base", "quote", "mape", "rmse", "mae", "n")
    list_filter = ("base", "quote")
    search_fields = ("run__id", "base__code", "quote__code")
    ordering = ("-run", "base__code", "quote__code")
    list_select_related = ("run", "base", "quote")
    autocomplete_fields = ("run", "base", "quote")
    list_per_page = 100





