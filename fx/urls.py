from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path

from apps.forecasting import views as fviews


# URLs that should not receive a language prefix
urlpatterns = [
    path("admin/", admin.site.urls),

    # Internal operations
    path("ops/", include("apps.forecasting.ops.urls")),

    # Analytics endpoint
    path(
        "analytics/",
        include("apps.analytics.urls", namespace="analytics"),
    ),

    # Data Observability Platform
    path(
        "observability/",
        include("dop_apps.observability.urls"),
    ),

    # Django language-switching endpoint
    path("i18n/", include("django.conf.urls.i18n")),
]


# Public pages available in English and Brazilian Portuguese
urlpatterns += i18n_patterns(
    path("home/", fviews.overview, name="overview"),
    path("forecast/", fviews.forecast_page, name="forecast"),
    path("market/", fviews.market_page, name="market"),

    path(
        "",
        include(
            "apps.site_portfolio.urls",
            namespace="portfolio",
        ),
    ),

    # English remains unprefixed; Portuguese uses /pt-br/
    prefix_default_language=False,
)


# Django Debug Toolbar — development only
if settings.DEBUG:
    try:
        import debug_toolbar
    except ModuleNotFoundError:
        pass
    else:
        urlpatterns += [
            path("__debug__/", include(debug_toolbar.urls)),
        ]