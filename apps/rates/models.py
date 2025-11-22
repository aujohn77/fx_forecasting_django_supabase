from django.db import models
from apps.core.models import Currency, ExchangeSource, Timeframe

class ExchangeRate(models.Model):
    source = models.ForeignKey(ExchangeSource, on_delete=models.CASCADE)
    base   = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="rates_as_base")
    quote  = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="rates_as_quote")
    timeframe = models.CharField(max_length=1, choices=Timeframe.choices, default=Timeframe.DAILY)
    date   = models.DateField()
    rate   = models.DecimalField(max_digits=20, decimal_places=10)

    class Meta:
        ordering = ["-date"]
        unique_together = ("source", "base", "quote", "timeframe", "date")
        indexes = [models.Index(fields=["base", "quote", "date", "timeframe"])]

    def __str__(self):
        return f"{self.base.code}/{self.quote.code} {self.date}: {self.rate}"
