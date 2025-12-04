from __future__ import annotations
from typing import Callable, Dict

from . import naive, drift, arima, prophet, my_arima
from .r_model_adapter import make_r_predictor


_REGISTRY: Dict[str, Callable[..., object]] = {
    # Python models
    "naive": naive.predict,
    "drift": drift.predict,
    "arima": arima.predict,
    "prophet": prophet.predict,
    "my_arima": my_arima.predict,

    # R models (explicit, strict)
    "average_r": make_r_predictor("average_r.R"),
    "drift_r": make_r_predictor("drift_r.R")
    #"average_r": lambda y_train, steps, target_index=None: (predict_r_model("average_r.R", y_train, steps, target_index)),
    #"average_r": lambda y, s, idx=None: predict_r_model("average_r.R", y, s, target_index=idx),

    #"arima_r": lambda y, s, idx=None: predict_r_model("arima_r.R", y, s, idx),

    # Add your next models here:
    # "ets_r": lambda y, s, idx=None: predict_r_model("ets_r.R", y, s, idx),
    # "tbats_r": lambda y, s, idx=None: predict_r_model("tbats_r.R", y, s, idx),
}


def get_model(name: str) -> Callable[..., object]:
    key = (name or "naive").lower()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown model '{name}'. Available: {sorted(_REGISTRY.keys())}")
    return _REGISTRY[key]


def list_models() -> list[str]:
    return sorted(_REGISTRY.keys())
