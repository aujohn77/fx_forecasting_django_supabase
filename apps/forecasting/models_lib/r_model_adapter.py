from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from .types import ForecastResult


# Full path to Rscript.exe (confirmed working)
RSCRIPT_EXE = Path(r"C:\Program Files\R\R-4.5.1\bin\x64\Rscript.exe")


def make_r_predictor(script_name: str):
    """
    Factory that returns a Python predictor function bound to a specific R script.

    Example:
        average_r_predict = make_r_predictor("average_r.R")
        ets_r_predict     = make_r_predictor("ets_r.R")
    """
    r_script_path = Path(__file__).resolve().parent.parent / "r_models" / script_name

    def _predict_r_model(
        y_train: pd.Series,
        steps: int = 1,
        target_index: pd.DatetimeIndex | None = None,
    ) -> ForecastResult:
        if y_train.empty:
            raise ValueError("y_train is empty")

        # If Django passes a target_index (for backtests), use it; otherwise build one
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
            [str(RSCRIPT_EXE), str(r_script_path), json.dumps(payload)],
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




