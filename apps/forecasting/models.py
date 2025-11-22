from __future__ import annotations
import uuid
from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import Currency, ExchangeSource, Timeframe

try:
    JSONField = models.JSONField
except Exception:  # pragma: no cover
    from django.contrib.postgres.fields import JSONField  # type: ignore


class ModelLibrary(models.TextChoices):
    BASELINE = "baseline", "Baseline"
    ARIMA = "arima", "ARIMA/SARIMAX"
    PROPHET = "prophet", "Prophet"
    LSTM = "lstm", "LSTM"
    XGB = "xgb", "XGBoost"

class ModelSpec(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    library = models.CharField(max_length=16, choices=ModelLibrary.choices)
    timeframe = models.CharField(max_length=1, choices=Timeframe.choices, default=Timeframe.DAILY)
    horizon_days = models.PositiveSmallIntegerField(default=1)
    params = JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "fx_model_spec"
        indexes = [models.Index(fields=["library", "timeframe", "active"])]

    def __str__(self):  # I added this for better display in admin (mula)
        lib = self.get_library_display() if hasattr(self, "library") else "?"
        tf  = self.get_timeframe_display() if hasattr(self, "timeframe") else "?"
        return f"{self.code} [{lib} | {tf}]"




class ForecastRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    as_of = models.DateTimeField()
    timeframe = models.CharField(max_length=1, choices=Timeframe.choices, default=Timeframe.DAILY)
    notes = models.TextField(blank=True, default="")
    trigger = models.CharField(max_length=24, blank=True, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    # ✅ NEW FIELDS
    data_cutoff_date = models.DateField(null=True, blank=True, db_index=True)
    model_name = models.CharField(max_length=40, blank=True, default="", db_index=True)

    class Meta:
        db_table = "fx_forecast_run"
        ordering = ["-as_of"]
        # Optional but recommended for uniqueness at the DB level:
        constraints = [
            models.UniqueConstraint(
                fields=["timeframe", "data_cutoff_date", "model_name"],
                name="fx_run_unique_tf_cutoff_model",
                condition=~models.Q(model_name="")  # only enforce when model_name is set
            )
        ]

    def __str__(self):
        tf_disp = self.get_timeframe_display()
        try:
            ts = self.as_of.strftime("%Y-%m-%d %H:%M")
        except Exception:
            ts = str(self.as_of)
        return f"{tf_disp} | as_of={ts}"






class Forecast(models.Model):
    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE, related_name="forecasts")
    model = models.ForeignKey(ModelSpec, on_delete=models.PROTECT)
    base = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="forecasts_as_base")
    quote = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="forecasts_as_quote")
    target_date = models.DateField()
    yhat = models.DecimalField(max_digits=20, decimal_places=8)
    yhat_lower = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    yhat_upper = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    extras = JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fx_forecast"
        unique_together = ("run", "model", "base", "quote", "target_date")
        indexes = [
            models.Index(fields=["quote", "target_date"]),
            models.Index(fields=["model", "target_date"]),
            models.Index(fields=["run"]),
        ]
        constraints = [models.CheckConstraint(check=models.Q(yhat__gt=0), name="fx_forecast_yhat_positive")]
        ordering = ["target_date", "base__code", "quote__code"]

class BacktestRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model = models.ForeignKey(ModelSpec, on_delete=models.PROTECT)
    timeframe = models.CharField(max_length=1, choices=Timeframe.choices, default=Timeframe.DAILY)
    horizon_days = models.PositiveSmallIntegerField(default=1)
    window_start = models.DateField()
    window_end = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "fx_backtest_run"
        indexes = [models.Index(fields=["model", "timeframe"])]
        ordering = ["-created_at"]

class BacktestSlice(models.Model):
    run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="slices")
    base = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="bt_as_base")
    quote = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="bt_as_quote")
    date = models.DateField()
    actual = models.DecimalField(max_digits=20, decimal_places=8, validators=[MinValueValidator(0)])
    forecast = models.DecimalField(max_digits=20, decimal_places=8, validators=[MinValueValidator(0)])

    class Meta:
        db_table = "fx_backtest_slice"
        unique_together = ("run", "base", "quote", "date")
        indexes = [models.Index(fields=["quote", "date"])]
        constraints = [
            models.CheckConstraint(check=models.Q(actual__gt=0), name="fx_bt_actual_positive"),
            models.CheckConstraint(check=models.Q(forecast__gt=0), name="fx_bt_forecast_positive"),
        ]

class BacktestMetric(models.Model):
    run = models.ForeignKey(BacktestRun, on_delete=models.CASCADE, related_name="metrics")
    base = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="bt_metrics_as_base")
    quote = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="bt_metrics_as_quote")
    mape = models.FloatField(null=True, blank=True)
    rmse = models.FloatField(null=True, blank=True)
    mae = models.FloatField(null=True, blank=True)
    n = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "fx_backtest_metric"
        unique_together = ("run", "base", "quote")
        indexes = [models.Index(fields=["quote"])]
