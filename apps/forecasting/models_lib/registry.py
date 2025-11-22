from __future__ import annotations
from typing import Callable, Dict

# Always-available baselines
from . import naive, drift

_REGISTRY: Dict[str, Callable[..., object]] = {
    "naive": naive.predict,
    "drift": drift.predict,
}

# Optional models — only register if deps import cleanly
# ARIMA
try:
    from . import arima as _arima
    _REGISTRY["arima"] = _arima.predict
except Exception as _e:
    # Leave unregistered if statsmodels isn't available, etc.
    pass

# Prophet
try:
    from . import prophet as _prophet
    _REGISTRY["prophet"] = _prophet.predict
except Exception as _e:
    # Leave unregistered if prophet/cmdstanpy isn't available, etc.
    pass


def get_model(name: str) -> Callable[..., object]:
    key = (name or "naive").lower()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown model '{name}'. Available: {sorted(_REGISTRY.keys())}")
    return _REGISTRY[key]


def list_models() -> list[str]:
    """Return the models that are actually registered/usable."""
    return sorted(_REGISTRY.keys())
