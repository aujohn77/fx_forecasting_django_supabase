#!/usr/bin/env Rscript
#
# R MODEL TEMPLATE – FX FORECASTING PLATFORM
# ==========================================
#
# HOW TO USE THIS TEMPLATE
# ------------------------
# 1. Download this file from the website.
# 2. Move it into your project at:
#        apps/forecasting/r_models/
# 3. Rename the file to something meaningful, e.g.:
#        my_custom_r_model.R
# 4. Open the file and:
#    - Change model_name = "my_custom_r_model" in the output list
#    - Replace the MODEL LOGIC section with your own R forecasting code.
# 5. Register the model in:
#        apps/forecasting/models_lib/registry.py
#
#    Example registration (inside registry.py, in Python):
#
#        from .r_model_adapter import make_r_predictor
#
#        _REGISTRY = {
#            # existing models...
#            "my_custom_r_model": make_r_predictor("my_custom_r_model.R"),
#        }
#
# 6. (Optional but recommended)
#    - Add a ModelSpec row (Django admin) with code "my_custom_r_model"
#      so it appears nicely in the UI.
#
# AFTER THESE STEPS:
# ------------------
# - Your R model can be run via the usual management commands:
#
#     python manage.py run_daily_forecasts --model my_custom_r_model
#     python manage.py run_backtests --model my_custom_r_model
#
# INTERFACE CONTRACT (DO NOT CHANGE):
# -----------------------------------
# - Python will call this script via Rscript, passing ONE JSON argument.
#   The JSON contains:
#       y      : numeric vector of training values
#       steps  : integer horizon
#       cutoff : ISO date string (last observed date)
#
# - Your job in this script:
#     1) Parse the JSON from commandArgs(trailingOnly = TRUE).
#     2) Compute a numeric vector yhat of length == steps.
#     3) Print JSON to stdout with at least:
#           yhat       : numeric vector of forecasts
#           model_name : short string for this model
#           cutoff     : cutoff date (usually just echo input$cutoff)
#
# - Python will parse this JSON and convert yhat into a ForecastResult.
#

suppressWarnings(suppressMessages({
  library(jsonlite)
}))

# ─────────────────────────────────────────────────────────────────────
# 1. Read JSON argument from Python
# ─────────────────────────────────────────────────────────────────────
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Expected one JSON argument from Python.")
}

input <- fromJSON(args[1])

# Extract fields
y      <- as.numeric(input$y)
steps  <- as.integer(input$steps)
cutoff <- as.character(input$cutoff)

n <- length(y)
if (n == 0) {
  stop("Training series 'y' is empty.")
}

# ─────────────────────────────────────────────────────────────────────
# 2. MODEL LOGIC – REPLACE THIS WITH YOUR OWN FORECASTING CODE
# ─────────────────────────────────────────────────────────────────────
# Example placeholder: naive forecast (repeat last observed value).
# Replace this with your preferred model, e.g.:
#   - exponential smoothing (ETS)
#   - ARIMA
#   - fable, forecast, etc.
#
# Requirements:
#   - yhat MUST be numeric
#   - length(yhat) MUST equal steps

last_value <- y[n]
yhat <- rep(last_value, steps)

# If you want to compute intervals, you could also build:
#   lo <- ...
#   hi <- ...
# and include them in the output list as additional fields.
# ─────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────
# 3. Output JSON to stdout
# ─────────────────────────────────────────────────────────────────────
output <- list(
  yhat       = yhat,
  model_name = "my_custom_r_model",  # <-- change this slug
  cutoff     = cutoff
  # You may optionally add fields like lo, hi, params, etc.
)

cat(toJSON(output, auto_unbox = TRUE))
