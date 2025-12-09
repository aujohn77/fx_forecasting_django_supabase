from __future__ import annotations
from typing import Callable, Dict

from . import my_arima
from .r_model_adapter import make_r_predictor


_REGISTRY: Dict[str, Callable[..., object]] = {
    # Python models
    "my_arima": my_arima.predict,

    # R models (explicit, strict)
    "ets_r": make_r_predictor("ets_r.R"),
}


def get_model(name: str) -> Callable[..., object]:
    key = (name or "naive").lower()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown model '{name}'. Available: {sorted(_REGISTRY.keys())}")
    return _REGISTRY[key]


def list_models() -> list[str]:
    return sorted(_REGISTRY.keys())
