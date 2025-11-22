from django.contrib import admin
from .models import Currency, ExchangeSource

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "decimals")
    search_fields = ("code", "name")
    ordering = ("code",)

@admin.register(ExchangeSource)
class ExchangeSourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "base_url")
    search_fields = ("code", "name")
    ordering = ("code",)
