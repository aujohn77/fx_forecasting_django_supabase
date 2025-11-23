#!/usr/bin/env Rscript

suppressWarnings(suppressMessages({
  library(jsonlite)
}))

# ---- Step 1: Read JSON arguments from Python ----
args <- commandArgs(trailingOnly = TRUE)
input <- fromJSON(args[1])

# Extract fields
y <- as.numeric(input$y)
h <- as.integer(input$steps)

n <- length(y)

# ---- Step 2: Drift model ----
if (n <= 1) {
  drift <- 0
} else {
  drift <- (y[n] - y[1]) / (n - 1)
}

forecast_values <- y[n] + drift * (1:h)

# ---- Step 3: Output JSON ----
output <- list(
  yhat = forecast_values,
  model_name = "drift_r",
  cutoff = input$cutoff
)

cat(toJSON(output, auto_unbox = TRUE))
