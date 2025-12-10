from django.urls import path
from . import views

urlpatterns = [
    path("event/", views.analytics_event, name="analytics_event"),
    path("console/", views.behaviour_console, name="behaviour_console"),
]
