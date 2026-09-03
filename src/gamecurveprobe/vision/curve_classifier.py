from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

import numpy as np

from gamecurveprobe.models import CurveAnalysis, MeasurementPoint


@dataclass(slots=True)
class FitCandidate:
    kind: str
    nrmse: float
    metrics: dict[str, float]


def classify_curve(points: Sequence[MeasurementPoint]) -> CurveAnalysis:
    valid_points = [p for p in points if p.valid and p.velocity_px_s is not None]
    if len(valid_points) < 5:
        return CurveAnalysis(curve_type="undetermined", confidence=0.0, metrics={})

    xs = np.array([p.input for p in valid_points], dtype=np.float64)
    ys = np.array([p.velocity_px_s for p in valid_points], dtype=np.float64)

    # Normalize ys to [0, 1]
    y_min, y_max = float(np.min(ys)), float(np.max(ys))
    y_range = y_max - y_min
    if y_range <= 1e-6:
        return CurveAnalysis(curve_type="undetermined", confidence=0.0, metrics={})
    ys_norm = (ys - y_min) / y_range

    try:
        linear_fit = _fit_linear(xs, ys_norm)
        power_fit = _fit_power_grid(xs, ys_norm)
        logistic_fit = _fit_logistic_grid(xs, ys_norm)
    except Exception:
        return CurveAnalysis(curve_type="undetermined", confidence=0.0, metrics={})

    ranked = sorted([linear_fit, power_fit, logistic_fit], key=lambda f: f.nrmse)
    best, second = ranked[0], ranked[1]

    if best.nrmse > 0.12 or (second.nrmse - best.nrmse) < 0.02:
        return CurveAnalysis(curve_type="undetermined", confidence=0.0, metrics={"best_nrmse": round(best.nrmse, 4)})

    confidence = round(max(0.0, min(1.0, 1.0 - best.nrmse)), 4)
    return CurveAnalysis(curve_type=best.kind, confidence=confidence, metrics=best.metrics)


def _compute_nrmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    y_range = float(np.max(y_true) - np.min(y_true))
    return rmse / y_range if y_range > 1e-6 else rmse


def _fit_linear(x: np.ndarray, y: np.ndarray) -> FitCandidate:
    A = np.vstack([x, np.ones(len(x))]).T
    m, c = np.linalg.lstsq(A, y, rcond=None)[0]
    y_pred = m * x + c
    nrmse = _compute_nrmse(y, y_pred)
    return FitCandidate(kind="linear", nrmse=nrmse, metrics={"slope": round(float(m), 4), "intercept": round(float(c), 4)})


def _fit_power_grid(x: np.ndarray, y: np.ndarray) -> FitCandidate:
    best_nrmse = float("inf")
    best_p = 1.0
    best_a = 1.0

    # Grid search exponents distinct from linear (p <= 0.75 or p >= 1.25)
    powers = np.concatenate([np.linspace(0.4, 0.75, 8), np.linspace(1.25, 3.5, 19)])
    for p in powers:
        x_pow = x**p
        A = np.vstack([x_pow, np.ones(len(x))]).T
        res = np.linalg.lstsq(A, y, rcond=None)[0]
        a, b = res[0], res[1]
        y_pred = a * x_pow + b
        nrmse = _compute_nrmse(y, y_pred)
        if nrmse < best_nrmse:
            best_nrmse = nrmse
            best_p = float(p)
            best_a = float(a)

    return FitCandidate(
        kind="exponential",
        nrmse=best_nrmse,
        metrics={"exponent": round(best_p, 4), "scale": round(best_a, 4)},
    )


def _fit_logistic_grid(x: np.ndarray, y: np.ndarray) -> FitCandidate:
    best_nrmse = float("inf")
    best_k = 10.0
    best_x0 = 0.5

    # Grid search logistic: L / (1 + exp(-k*(x-x0)))
    for k in np.linspace(4.0, 16.0, 13):
        for x0 in np.linspace(0.2, 0.8, 7):
            pred = 1.0 / (1.0 + np.exp(-k * (x - x0)))
            nrmse = _compute_nrmse(y, pred)
            if nrmse < best_nrmse:
                best_nrmse = nrmse
                best_k = float(k)
                best_x0 = float(x0)

    return FitCandidate(
        kind="s_curve",
        nrmse=best_nrmse,
        metrics={"steepness": round(best_k, 4), "midpoint": round(best_x0, 4)},
    )
