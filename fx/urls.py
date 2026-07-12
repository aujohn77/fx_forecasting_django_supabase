"""
URL configuration for fx project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# fx/urls.py
from django.contrib import admin
from django.urls import path, include
from apps.forecasting import views as fviews
from django.conf import settings   # ← IMPORTANT FOR DEBUG CHECK
from django.conf.urls.i18n import i18n_patterns


urlpatterns = [
    path("admin/", admin.site.urls),

    # 🔹 Existing FX dashboards
    path("home/",    fviews.overview,       name="overview"),
    path("forecast/", fviews.forecast_page, name="forecast"),
    path("market/",   fviews.market_page,   name="market"),

    # 🔹 Ops console
    path("ops/", include("apps.forecasting.ops.urls")),

    # 🔹 Analytics event tracking
    path("analytics/", include("apps.analytics.urls", namespace="analytics")),

    # 🔹 Data Observability Platform
    path("observability/", include("dop_apps.observability.urls")),
    path("i18n/", include("django.conf.urls.i18n")),

]




urlpatterns += i18n_patterns(
    path("", include("apps.site_portfolio.urls", namespace="portfolio")),
    prefix_default_language=False,
)


# =======================================
# Debug Toolbar (development only)
# =======================================

if settings.DEBUG:
    try:
        import debug_toolbar
    except ModuleNotFoundError:
        # debug toolbar not installed (e.g. in production) – just skip
        pass
    else:
        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
