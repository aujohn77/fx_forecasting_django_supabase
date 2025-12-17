# 🌍 ML Deployment Platform

A production-ready **ML deployment system** for automated **daily FX forecasting**.  
This platform ingests currency data, runs forecasting models, stores predictions, and exposes everything through a Django interface — fully automated via GitHub Actions.

Unlike experimentation platforms, this system focuses purely on **operational forecasting**, not model comparison or evaluation dashboards.

---

## ⚠️ Portfolio Website Notice

This repository also contains code for a personal portfolio site, merged into the same Django project for hosting convenience.

- ✔ Portfolio pages are fully isolated  
- ✔ They do **not** interact with forecasting logic  
- ✔ They do **not** affect ingestion, automation, or database operations  

Portfolio-related files:


```
apps/portfolio/
apps/analytics/
static/images/projects/
templates/portfolio/
```

These can be safely ignored if your focus is the ML Deployment System.

---

## 🚀 Features

### 1️⃣ Automated FX Data Ingestion
- Runs daily via **GitHub Actions**  
- Pulls FX rates from the **Frankfurter API**  
- Writes data into **Supabase PostgreSQL**  
- Supports historical backfilling  

---

### 2️⃣ Pluggable Forecasting Models
Add models with *zero changes* to the core system:

- Supports **Python** and **R**  
- Each model uses a clean template  
- Register once and it becomes available  
- Pipeline is fully model-agnostic  

---

### 3️⃣ Automated Daily Forecasting

Every day, GitHub Actions:

1. Fetches FX data  
2. Runs **all registered models**  
3. Stores predictions in Supabase  
4. Logs execution details  

---

### 4️⃣ Production-Ready Architecture

Stable stack used in real deployments:

- Django  
- Supabase PostgreSQL  
- Render  
- GitHub Actions  
- Python (and optional R)  

---

### 5️⃣ Forecast Display Pages

Minimal UI that provides:

- **Market page** — latest FX values  
- **Forecast page** — today’s predictions  

No scoring dashboards or comparison tools (by design).

---

## 📁 Repository Structure

### ML Deployment Platform (Main System)

```
fx_forecasting_django_supabase/
│
├── apps/
│ ├── core/ # Currency + timeframe utilities
│ ├── rates/ # FX ingestion + Supabase writes
│ ├── forecasting/ # Forecast logic & models
│ │ ├── models_lib/ # Python & R forecasting models
│ │ │ ├── python_model_template.py
│ │ │ ├── registry.py
│ │ │ └── <your_model>.py
│ │ ├── services/ # Forecast execution engine
│ │ ├── management/commands/ # ingest_rates, run_forecasts
│ │ └── views.py
│ │
│ ├── portfolio/ # Portfolio pages (isolated)
│ └── ...
│
├── .github/workflows/
│ ├── daily_ops.yml # Daily ingest + forecast
│ ├── deploy.yml # Deploy to Render
│ └── backtest_runner.yml # Legacy workflow
│
├── fx/ # Django settings & routing
├── templates/ # HTML templates
├── static/ # Static assets
│
├── requirements.txt
├── manage.py
└── README.md

```



---

### Portfolio Website (Isolated)


```

apps/portfolio/
templates/portfolio/
static/images/projects/

```


These do **not** affect forecasting.

---

## 🧠 Adding Your Own Forecasting Model

### 1. Choose Your Template

**Python:**

apps/forecasting/models_lib/python_model_template.py


**R:**


apps/forecasting/r_models/r_model_template.R


Edit only:



PART 2 — MODEL LOGIC (THIS IS YOUR AREA)


Set your model name in PART 3:

python
model_name = "my_model"

2. Python Model Registration

Save your model in:

apps/forecasting/models_lib/


Rename to match the model:

my_model.py


Register in registry.py:

from . import my_model


Add:

"my_model": my_model.predict,

3. R Model Registration

Save your file in:

apps/forecasting/r_models/


Add to registry:

"my_model": make_r_predictor("my_model.R")

⚙️ Running Locally
1. Install dependencies
pip install -r requirements.txt

2. Create .env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
DJANGO_SECRET_KEY=
DJANGO_DEBUG=True

3. Start the server
python manage.py runserver

4. Ingest rates manually
python manage.py ingest_rates

5. Run forecasts manually
python manage.py run_forecasts

🖥 Deployment

Supports deployment to:

Render (Django hosting)

Supabase PostgreSQL (database)

GitHub Actions (automation)

Workflows live in:

.github/workflows/

🌐 GitHub Actions Included
daily_ops.yml

Fetch FX data

Run all models

Store predictions

deploy.yml

Deploy to Render (optional)

🧰 Tech Stack

Python

Django

Supabase PostgreSQL

GitHub Actions

Render

Frankfurter API

Optional: R models via Rscript
