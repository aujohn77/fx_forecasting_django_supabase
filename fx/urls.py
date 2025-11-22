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

urlpatterns = [
    path("admin/", admin.site.urls),

    # dashboards
    path("home/", fviews.overview, name="overview"),
    path("forecast/", fviews.forecast_page, name="forecast"),
    path("compare/", fviews.compare_page, name="compare"),

    # NEW: ops console
    path("ops/", include("apps.forecasting.ops.urls")),
]
