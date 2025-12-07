from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import shutil  # for shutil.which

import pandas as pd

from .types import ForecastResult

# Base folder for all R scripts
R_MODELS_DIR = Path(__file__).resolve().parent.parent / "r_models"

# Resolve Rscript path:
# Priority:
#   1. RSCRIPT_EXE env var (local or CI)
#   2. Whatever "Rscript" on PATH points to
#   3. Fallback to your Windows installation path (local dev)
_env_rscript = os.environ.get("RSCRIPT_EXE")
if _env_rscript:
    RSCRIPT_EXE = _env_rscript
else:
    _which_rscript = shutil.which("Rscript")
    if _which_rscript:
        RSCRIPT_EXE = _which_rscript
    else:
        RSCRIPT_EXE = r"C:\Program Files\R\R-4.5.1\bin\x64\Rscript.exe"

# Optional: this will show in logs (useful on GitHub Actions)
print(f"[r_model_adapter] Using Rscript at: {RSCRIPT_EXE}")


def make_r_predictor(script_name: str):
    """
    Factory that returns a Python wrapper for a given R script.
    """
    r_script_path = R_MODELS_DIR / script_name

    def _predict_r_model(
        y_train: pd.Series,
        steps: int = 1,
        target_index: pd.DatetimeIndex | None = None,
    ) -> ForecastResult:
        if y_train.empty:
            raise ValueError("y_train is empty")

        idx = (
            target_index
            if target_index is not None
            else pd.date_range(periods=steps, freq="D")
        )

        payload = {
            "y": y_train.astype(float).tolist(),
            "steps": int(steps),
            "cutoff": y_train.index.max().isoformat(),
        }

        json_arg = json.dumps(payload)

        # ---------- DEBUG: show exactly what we're sending to R ----------
        print("\n====== RSCRIPT DEBUG START ======")
        print(f"Script name: {script_name}")
        print(f"R script path: {r_script_path}")
        print(f"Using Rscript: {RSCRIPT_EXE}")
        print("JSON payload (truncated):")
        print(json_arg[:400] + ("..." if len(json_arg) > 400 else ""))

        # Call Rscript
        proc = subprocess.run(
            [RSCRIPT_EXE, str(r_script_path), json_arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        print("\n------ R STDOUT ------")
        print(proc.stdout)
        print("------ R STDERR ------")
        print(proc.stderr)
        print("Exit code:", proc.returncode)
        print("====== RSCRIPT DEBUG END ======\n")
        # -----------------------------------------------------------------

        if proc.returncode != 0:
            # Surface R’s error clearly to Django / GitHub Actions logs
            raise RuntimeError(
                f"Rscript failed with exit code {proc.returncode} "
                f"for script '{script_name}'.\n"
                f"R STDERR:\n{proc.stderr}"
            )

        # Parse JSON response from R
        try:
            out = json.loads(proc.stdout)
        except Exception as e:
            raise RuntimeError(
                "Invalid JSON returned from Rscript.\n"
                f"STDOUT was:\n{proc.stdout}\n\nSTDERR was:\n{proc.stderr}"
            ) from e

        yhat = pd.Series(out["yhat"], index=idx, dtype=float)

        return ForecastResult(
            target_index=idx,
            yhat=yhat,
            model_name=out.get("model_name", script_name.replace(".R", "")),
            cutoff=pd.to_datetime(out["cutoff"]),
        )

    return _predict_r_model
