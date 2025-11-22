# apps/forecasting/ops/urls.py
from django.urls import path
from .views import console, run_action

app_name = "ops"

urlpatterns = [
    path("", console, name="console"),          # GET: show console
    path("run/", run_action, name="run_action") # POST: perform an action
]
