#!/usr/bin/env Rscript

suppressWarnings(suppressMessages({
  library(jsonlite)
}))

# ---- Step 1: Read JSON arguments from Python ----
args <- commandArgs(trailingOnly = TRUE)
input <- fromJSON(args[1])

# Extract fields
y <- input$y
h <- input$steps

# ---- Step 2: Simple average model ----
avg_value <- mean(y)
forecast_values <- rep(avg_value, h)

# ---- Step 3: Output JSON ----
output <- list(
  yhat = forecast_values,
  model_name = "average_r",
  cutoff = input$cutoff
)

cat(toJSON(output, auto_unbox=TRUE))
