FX Forecasting – Django + Supabase + Automated Daily Predictions

A fully working ML deployment system for daily FX forecasting.
This project lets you:

Fetch daily exchange rate data

Store data in Supabase

Register any Python or R forecasting model

Automatically run forecasts once per day

View results through Django pages

Deploy everything to Render

Run everything via GitHub Actions

No model comparison, no scoring metrics, and no evaluation dashboards — this system focuses purely on operational forecasting, not experimentation.

⚠️ Note About Portfolio Pages

This repository also contains my personal portfolio website, merged into the same Django project for hosting convenience.

However:

✔ The portfolio pages are completely isolated
✔ They do NOT interact with any forecasting logic
✔ They do NOT affect ingestion, forecasting, or database operations

Portfolio-related code lives in:

apps/portfolio/
static/images/projects/
templates/portfolio/


You can safely ignore these directories if your only interest is the ML Deployment Platform.

🚀 Features
1. Automated FX Data Ingestion

Runs once per day via GitHub Actions

Uses the Frankfurter API

Writes data to Supabase

Supports backfilling historical data

2. Pluggable Forecasting Models

You can easily add your own models:

Python or R

Write your logic using a clean template

Register the model and it becomes available to the forecast pipeline

3. Automated Daily Forecasting

Each day GitHub Actions:

Fetches FX data

Runs all registered models

Stores predictions in Supabase

Logs execution

4. Simple, Production-Ready Architecture

Used in real deployments:

Django

Supabase

Render

GitHub Actions

Python (and optional R)

5. Forecast Display Pages

The project includes:

Market page: Latest FX values

Forecast page: Today's predictions

No comparison pages, no overview dashboards.

## 📁 Repository Structure

### ML Deployment Platform (Main System)

```
fx_forecasting_django_supabase/
│
├── apps/
│   ├── core/                     # Core utilities (currencies, timeframes)
│   ├── rates/                    # FX ingestion + storage (Supabase)
│   ├── forecasting/              # Forecast logic
│   │   ├── models_lib/           # Python & R forecasting models
│   │   │   ├── python_model_template.py
│   │   │   ├── registry.py
│   │   │   └── <your model>.py
│   │   ├── services/             # Forecast execution engine
│   │   ├── management/commands/  # CLI tasks (ingest, forecast)
│   │   └── views.py              # Market & Forecast pages
│   │
│   ├── portfolio/                # Portfolio pages (isolated)
│   └── ...
│
├── .github/workflows/
│   ├── daily_ops.yml             # Daily ingest + forecast
│   ├── deploy.yml                # Render deploy (optional)
│   └── backtest_runner.yml       # (legacy, safe to ignore)
│
├── fx/                           # Django project settings & routing
├── templates/                    # Base and project templates
├── static/                       # Static assets
│
├── requirements.txt
├── manage.py
└── README.md
```

### Portfolio Website (Isolated, Optional)

```
apps/portfolio/
templates/portfolio/
static/images/projects/
```



These folders do NOT affect forecasting.

🧠 How to Add Your Own Forecasting Model


Download the template for your language:

• Python: python_model_template.py
• R:      r_model_template.R

Open the template and edit only the section marked:
"PART 2 — MODEL LOGIC (THIS IS YOUR AREA)"

In "PART 3", you will see where to set your model name (e.g., 'my_model').

Then:

Python models
-------------
Save the file to:
apps/forecasting/models_lib/

Rename it to match your model name (e.g., my_model.py).

Open:
apps/forecasting/models_lib/registry.py

Add at the top:
from . import my_model

Add this to _REGISTRY:
"my_model": my_model.predict,


R models
--------
Save the file to:
apps/forecasting/r_models/

Rename it to match your model name (e.g., my_model.R).

Open:
apps/forecasting/models_lib/registry.py

(You do NOT add an import at the top for R models.)

Add this to _REGISTRY:
"my_model": make_r_predictor("my_model.R")



⚙️ Running Locally
1. Install dependencies
pip install -r requirements.txt

2. Set environment variables

Create .env with:

SUPABASE_URL

SUPABASE_ANON_KEY

SUPABASE_SERVICE_KEY

DJANGO_SECRET_KEY

DJANGO_DEBUG=True (optional)

3. Run the server
python manage.py runserver

4. Run ingestion manually
python manage.py ingest_rates

5. Run daily forecasts manually
python manage.py run_forecasts

🖥 Deployment

This project supports full production deployment:

Django → Render

Database → Supabase PostgreSQL

Automation → GitHub Actions

Workflows included in:

.github/workflows/

🌐 Included GitHub Actions
daily_ops.yml

Fetch rates

Run forecasts

Write to Supabase

deploy.yml

Deploy to Render (optional)

🧰 Tech Stack

Python

Django

Supabase (PostgreSQL)

GitHub Actions

Render

Frankfurter API

Optional: R models via Rscript