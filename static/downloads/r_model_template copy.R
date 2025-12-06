suppressWarnings(suppressMessages({
  library(jsonlite)
  # You may add other libraries your model needs here, e.g.:
  # library(forecast)
  # library(fable)
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

# Example model: simple mean forecast
avg_value <- mean(y, na.rm = TRUE)
yhat <- rep(avg_value, h)


# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────
# PART 3 — BUILD AND OUTPUT JSON (KEEP IT)
# Structure MUST be kept.
# You ONLY change the model_name string.
# ─────────────────────────────────────────

output <- list(
  yhat = yhat,                # <- KEEP THE WAY IT IS
  model_name = "my_r_model",  # <---------------------------------------- SET YOUR MODEL NAME HERE
  cutoff = input$cutoff       # <- KEEP THE WAY IT IS
)

cat(toJSON(output, auto_unbox = TRUE))
