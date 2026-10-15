"""Improvement loop: walk-forward ridge regression + parameter sweep, with promotion guards.

Nothing is changed unless the candidate beats thresholds out-of-sample, and parameter moves
are bounded so a noisy run cannot swing the strategy. Every run is appended to
state/improvement_log.jsonl for auditing.
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from . import compute
from .config import STATE_DIR, Settings
from .data import build_provider
from .features import FEATURES, feature_frame, forward_return
from .strategies.day_trader import MODEL_FILE, PARAMS_FILE, load_params

HORIZON = 10
MIN_IC, MIN_HIT = 0.02, 0.51
FAST_GRID, SLOW_GRID = [5, 7, 9, 12, 15], [15, 21, 30, 40, 55]


def build_dataset(frames: dict[str, pd.DataFrame]):
    parts_tr, parts_te = [], []
    for bars in frames.values():
        X = feature_frame(bars)[FEATURES]
        y = forward_return(bars, HORIZON)
        d = pd.concat([X, y.rename("y")], axis=1).dropna()
        cut = int(len(d) * 0.7)
        parts_tr.append(d.iloc[:cut])
        parts_te.append(d.iloc[cut:])
    return pd.concat(parts_tr), pd.concat(parts_te)


def fit_and_validate(frames: dict[str, pd.DataFrame], alpha: float = 10.0) -> dict:
    train, test = build_dataset(frames)
    mean, std = train[FEATURES].mean(), train[FEATURES].std().replace(0, 1)
    coef = compute.ridge_fit(((train[FEATURES] - mean) / std).values, train["y"].values, alpha)
    pred = compute.ridge_predict(coef, ((test[FEATURES] - mean) / std).values)
    y = test["y"].values
    ic = float(np.corrcoef(pred, y)[0, 1]) if pred.std() > 0 and y.std() > 0 else 0.0
    ss_res, ss_tot = float(((y - pred) ** 2).sum()), float(((y - y.mean()) ** 2).sum())
    metrics = {"ic": ic, "hit_rate": float((np.sign(pred) == np.sign(y)).mean()),
               "r2": 1 - ss_res / ss_tot if ss_tot else 0.0, "n_train": len(train), "n_test": len(test)}
    return {"coef": coef.tolist(), "mean": mean.tolist(), "std": std.tolist(), "features": FEATURES,
            "horizon": HORIZON, "alpha": alpha, "metrics": metrics,
            "trained_at": datetime.now().isoformat(timespec="seconds")}


def run(s: Settings, provider=None, dry_run: bool = False) -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    provider = provider or build_provider(s, s.day_symbols)
    frames = {sym: provider.get_bars(sym, "1m", 5000) for sym in s.day_symbols}
    model = fit_and_validate(frames)
    m = model["metrics"]
    promoted = m["ic"] >= MIN_IC and m["hit_rate"] >= MIN_HIT

    params = load_params()
    spy = provider.get_bars("SPY", "1m", 5000)["close"].values
    sweep = compute.sweep_ma_crossover(spy, FAST_GRID, SLOW_GRID)
    best = sweep[0] if sweep else None
    new = dict(params)
    if best and best["score"] > 0:
        # bounded move: at most 3 periods per run toward the sweep winner
        new["fast"] = int(params["fast"] + np.clip(best["fast"] - params["fast"], -3, 3))
        new["slow"] = int(max(new["fast"] + 3, params["slow"] + np.clip(best["slow"] - params["slow"], -3, 3)))
    result = {"ts": datetime.now().isoformat(timespec="seconds"), "backend": compute.BACKEND,
              "metrics": m, "model_promoted": promoted, "sweep_best": best, "params_before": params,
              "params_after": new, "dry_run": dry_run}
    if not dry_run:
        if promoted:
            MODEL_FILE.write_text(json.dumps(model))
        PARAMS_FILE.write_text(json.dumps(new, indent=1))
        with open(STATE_DIR / "improvement_log.jsonl", "a") as f:
            f.write(json.dumps(result) + "\n")
    return result
