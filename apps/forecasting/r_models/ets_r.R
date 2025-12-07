suppressWarnings(suppressMessages({
  library(jsonlite)
  library(forecast)   # <- ETS comes from this package
}))

# ─────────────────────────────────────────
# PART 1 — INPUT & SAFETY (KEEP IT)
# You should NOT remove these checks.
# You may extend them if needed, but not break them.
# ─────────────────────────────────────────

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("No JSON argument received from Python.")
}

input <- fromJSON(args[1])

# Expected fields coming from Python:
#   • y      → numeric vector of historical FX values
#   • steps  → forecast horizon (integer)
#   • cutoff → last observed date (string or numeric, passed through)
y <- input$y
h <- input$steps
# We just pass cutoff through; no need to extract it here

if (is.null(y) || length(y) == 0) {
  stop("Input 'y' is empty.")
}
if (is.null(h) || h <= 0) {
  stop("Input 'steps' must be a positive integer.")
}

# Ensure numeric
y <- as.numeric(y)


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────
# PART 2 — MODEL LOGIC (THIS IS YOUR AREA)
# You CAN change anything inside this block.
#
# IMPORTANT:
#   • You RECEIVE:  y  → numeric vector of historical FX values
#   • You MUST RETURN: yhat → numeric vector of length h
#
#   The forecast horizon h is already set (default = 1). Simply use h wherever your model needs to create yhat.
#   You may import any R packages you need at the top of the file.
#
# Everything inside this section is UP TO YOU.
# ─────────────────────────────────────────

# ETS model using the `forecast` package
fit_ets <- forecast::ets(y)            # automatic ETS model selection
fc_ets  <- forecast::forecast(fit_ets, h = h)

# Forecast vector to return (length must be h)
yhat <- as.numeric(fc_ets$mean)


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────
# PART 3 — BUILD AND OUTPUT JSON (KEEP IT)
# Structure MUST be kept.
# You ONLY change the model_name string.
# ─────────────────────────────────────────

output <- list(
  yhat = yhat,                # <- KEEP THE WAY IT IS
  model_name = "ets_r",       # <---------------------------------------- SET YOUR MODEL NAME HERE
  cutoff = input$cutoff       # <- KEEP THE WAY IT IS
)

cat(toJSON(output, auto_unbox = TRUE))
