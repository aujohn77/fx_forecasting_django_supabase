from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("event/", views.analytics_event, name="analytics_event"),
    path("console/", views.behaviour_console, name="behaviour_console"),
    path("optout/", views.analytics_optout, name="analytics_optout"),  # NEW
    path("optin/", views.analytics_optin, name="analytics_optin"),      # NEW
]
