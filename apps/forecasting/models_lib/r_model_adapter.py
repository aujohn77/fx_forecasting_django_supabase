from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd

from .types import ForecastResult

# Base folder for all R scripts
R_MODELS_DIR = Path(__file__).resolve().parent.parent / "r_models"

# Path to Rscript:
# - Locally (Windows): use RSCRIPT_EXE in your .env, e.g.
#     RSCRIPT_EXE=C:\Program Files\R\R-4.5.1\bin\x64\Rscript.exe
# - On GitHub Actions (Linux): we’ll set RSCRIPT_EXE=Rscript
RSCRIPT_EXE = os.environ.get(
    "RSCRIPT_EXE",
    r"C:\Program Files\R\R-4.5.1\bin\x64\Rscript.exe",  # fallback for your laptop
)


def make_r_predictor(script_name: str):
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

        proc = subprocess.run(
            [RSCRIPT_EXE, str(r_script_path), json.dumps(payload)],
            capture_output=True,
            text=True,
            check=True,
        )

        out = json.loads(proc.stdout)
        yhat = pd.Series(out["yhat"], index=idx, dtype=float)

        return ForecastResult(
            target_index=idx,
            yhat=yhat,
            model_name=out.get(
                "model_name",
                script_name.replace(".R", ""),
            ),
            cutoff=pd.to_datetime(out["cutoff"]),
        )

    return _predict_r_model


