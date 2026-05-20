"""
Синтетический датасет для обучения квантильных моделей (воспроизводимо, seed=42).
Целевая переменная — задержка доставки в днях (логистическая формула + шум).
"""
from __future__ import annotations

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor


def build_synthetic_xy(n_samples: int = 4000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X_list = []
    y_list = []
    for _ in range(n_samples):
        t = int(rng.integers(0, 4))  # truck rail sea air
        p = int(rng.integers(0, 3))
        w = float(rng.uniform(0.05, 8.0))
        route_h = float(rng.uniform(1.5, 96.0))
        wd = float(rng.uniform(0, 10))
        trd = float(rng.uniform(0, 8))
        gd = float(rng.uniform(0, 40))
        tp = float(rng.uniform(0.05, 0.98))
        # Базовая задержка (дней): время в пути + влияние факторов + стадия рейса (телеметрия)
        route_days = route_h / 24.0
        mode = {0: 1.0, 1: 1.12, 2: 1.45, 3: 0.42}[t]
        delay = (
            0.08
            + route_days * 0.22 * mode
            + wd * 0.012
            + trd * 0.015
            + gd * 0.006
            + (1.0 - tp) * 0.15  # чем ближе к концу, тем меньше неопределённость
        )
        delay += rng.normal(0, 0.04)
        delay = float(max(0.05, min(delay, 25.0)))
        X_list.append([t, p, w, route_h, wd, trd, gd, tp])
        y_list.append(delay)
    return np.array(X_list, dtype=np.float64), np.array(y_list, dtype=np.float64)


def train_quantile_models(
    X: np.ndarray, y: np.ndarray, seed: int = 42
) -> tuple[GradientBoostingRegressor | None, GradientBoostingRegressor | None, GradientBoostingRegressor | None]:
    if len(X) < 50:
        return None, None, None
    X_train, _, y_train, _ = train_test_split(X, y, test_size=0.15, random_state=seed)
    models = {}
    for q, name in [(0.1, "low"), (0.5, "median"), (0.9, "high")]:
        m = GradientBoostingRegressor(
            n_estimators=120,
            max_depth=4,
            random_state=seed,
            loss="quantile",
            alpha=q,
            learning_rate=0.06,
        )
        m.fit(X_train, y_train)
        models[name] = m
    return models["low"], models["median"], models["high"]
