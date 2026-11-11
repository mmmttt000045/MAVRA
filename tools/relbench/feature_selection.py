"""Bounded selection over already computed features, using validation labels only.

The caller supplies the benchmark's unchanged learner and scoring function.
No SQL, model-service calls, task names, test features or test labels enter this
module. The incumbent is always retained as the fallback candidate.
"""
import math
import time


PREFIX_SIZES = (16, 32, 64)


def select_subset(xtrain, ytrain, xvalid, yvalid, importance, incumbent_score,
                  higher, fit, score, budget_seconds=15.0, clock=time.monotonic):
    if list(xtrain.columns) != list(xvalid.columns):
        raise ValueError("training and validation columns must match in order")
    if len(xtrain) != len(ytrain) or len(xvalid) != len(yvalid):
        raise ValueError("feature rows and labels must have matching lengths")
    if not xtrain.columns.is_unique:
        raise ValueError("feature column names must be unique")
    if not math.isfinite(incumbent_score):
        raise ValueError("incumbent score must be finite")
    columns = list(xtrain.columns)
    ranked = [c for c, gain in importance if gain > 0 and c in columns]
    ranked = list(dict.fromkeys(ranked))
    started = clock()
    chosen = {"columns": columns, "val": incumbent_score, "name": "unchanged"}
    trials = []
    # A tiny improvement on one validation split is not enough to replace an
    # incumbent. MAE uses a scale-relative margin; AUC uses an absolute one.
    margin = 0.0005 if higher else max(abs(incumbent_score) * 0.002, 1e-8)
    seen = {tuple(columns)}
    for size in PREFIX_SIZES:
        if clock() - started >= budget_seconds:
            break
        wanted = set(ranked[:size])
        subset = [c for c in columns if c in wanted]
        if len(subset) < 2 or tuple(subset) in seen:
            continue
        seen.add(tuple(subset))
        t0 = clock()
        prediction, imp, train_seconds = fit(xtrain[subset], ytrain, xvalid[subset])
        val = float(score(yvalid, prediction))
        trial = {"name": f"gain_{size}", "columns": subset, "val": val,
                 "seconds": clock() - t0, "train_seconds": train_seconds,
                 "importance": imp}
        if not math.isfinite(val):
            trial["rejected"] = "non-finite validation score"
        elif (val > chosen["val"] + margin if higher else val < chosen["val"] - margin):
            chosen = trial
        trials.append(trial)
    return {"chosen": chosen, "trials": trials, "seconds": clock() - started,
            "train_seconds": sum(t["train_seconds"] for t in trials),
            "fits": len(trials), "selection_split": "validation", "margin": margin}
