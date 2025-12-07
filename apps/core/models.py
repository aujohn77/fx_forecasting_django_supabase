from django.db import models
from django.core.validators import RegexValidator

class Timeframe(models.TextChoices):
    DAILY = "D", "Daily"
    WEEKLY = "W", "Weekly"
    MONTHLY = "M", "Monthly"

ccy_code_validator = RegexValidator(
    regex=r"^[A-Z]{3}$",
    message="Currency code must be a 3-letter ISO uppercase code (e.g., USD).",
)

class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True, validators=[ccy_code_validator])
    name = models.CharField(max_length=64)
    symbol = models.CharField(max_length=8, blank=True, default="")
    decimals = models.PositiveSmallIntegerField(default=6)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"   # <-- FIXED PLURAL HERE


class ExchangeSource(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    base_url = models.URLField(blank=True, default="")

    def __str__(self):
        return self.name
