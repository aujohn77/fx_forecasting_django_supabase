from django.shortcuts import render
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET
from django.conf import settings

from django_ratelimit.decorators import ratelimit

from pathlib import Path


# ---------------------------------------------
# REGULAR PAGE VIEWS (your existing ones)
# ---------------------------------------------

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


# ----------------------------------------------------
#  🔥 GENERIC DOWNLOAD SYSTEM (CV + templates + more)
# ----------------------------------------------------

# Map simple keys to real files in protected_files/
FILE_MAP = {
    "cv": {
        "path": Path(settings.BASE_DIR, "protected_files", "joao_reis_cv.pdf"),
        "download_name": "Joao_Eduardo_Reis_CV.pdf",
    },
    "python_template": {
        "path": Path(settings.BASE_DIR, "protected_files", "python_model_template.py"),
        "download_name": "python_model_template.py",
    },
    "r_template": {
        "path": Path(settings.BASE_DIR, "protected_files", "r_model_template.R"),
        "download_name": "r_model_template.R",
    },
    "thesis": {
        "path": Path(settings.BASE_DIR, "protected_files", "student_final_year_undergraduate_thesis.pdf"),
        "download_name": "student_final_year_undergraduate_thesis.pdf",
    },
}


@require_GET
@ratelimit(key="ip", rate="10/m", block=True)  # limit: 10 downloads per minute
def download_file(request, file_key: str):

    config = FILE_MAP.get(file_key)
    if not config:
        raise Http404("Unknown file")

    file_path = config["path"]
    if not file_path.exists():
        raise Http404("File not found")

    return FileResponse(
        open(file_path, "rb"),
        as_attachment=True,
        filename=config["download_name"],
    )
