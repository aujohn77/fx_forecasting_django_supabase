from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.analytics"   # ← important: full Python path to the app
    verbose_name = "Analytics"
