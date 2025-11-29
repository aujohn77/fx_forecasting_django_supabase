from django.apps import AppConfig

class SitePortfolioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.site_portfolio"   # <- IMPORTANT
    verbose_name = "Portfolio"
