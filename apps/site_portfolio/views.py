from django.shortcuts import render

def home(request):
    return render(request, "portfolio/home.html")

def projects(request):
    return render(request, "portfolio/projects.html")

def about(request):
    return render(request, "portfolio/about.html")

def project_model_deploy(request):
    return render(request, "portfolio/project_model_deploy.html")

def project_amazon_recommender(request):
    return render(request, "portfolio/project_amazon_recommender.html")

def project_lead_conversion(request):
    return render(request, "portfolio/project_lead_conversion.html")

def project_customer_segmentation(request):
    return render(request, "portfolio/project_customer_segmentation.html")

def kaggle_certs(request):
    return render(request, "portfolio/kaggle_certs.html")

