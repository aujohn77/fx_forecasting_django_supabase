from django.urls import path
from . import views

app_name = "portfolio"  # URL namespace

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),

    path("projects/model-deployment/", views.project_model_deploy, name="project_model_deploy"),
    path("projects/amazon-recommender/", views.project_amazon_recommender, name="project_amazon_recommender"),
    path("projects/lead-conversion/", views.project_lead_conversion, name="project_lead_conversion"),
    path("projects/customer-segmentation/", views.project_customer_segmentation, name="project_customer_segmentation"),
]
