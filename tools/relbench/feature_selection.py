"""Bounded selection over already computed features, using validation labels only.

The caller supplies the benchmark's unchanged learner and scoring function.
No SQL, model-service calls, task names, test features or test labels enter this
module. The incumbent is always retained as the fallback candidate.
"""
import math
import re
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


def complementary_pool(primary_train, primary_valid, secondary_train, secondary_valid,
                       secondary_importance, max_extra=40):
    """Keep genuinely different columns of a second attempt, with stable names.

    Hashes only shortlist possible duplicates; equality on both complete matrices
    confirms them. Same-valued training columns that differ on validation stay
    distinct. No labels are read by this operation.
    """
    import pandas as pd

    if not primary_train.index.equals(secondary_train.index) or not primary_valid.index.equals(secondary_valid.index):
        raise ValueError("both attempts must use identically ordered seed rows")
    if list(primary_train) != list(primary_valid) or list(secondary_train) != list(secondary_valid):
        raise ValueError("training and validation feature columns must match")
    if not primary_train.columns.is_unique or not secondary_train.columns.is_unique:
        raise ValueError("feature names must be unique within each attempt")

    def signature(train, valid):
        return (int(pd.util.hash_pandas_object(train, index=False).sum()),
                int(pd.util.hash_pandas_object(valid, index=False).sum()))

    seen = {}
    for c in primary_train:
        seen.setdefault(signature(primary_train[c], primary_valid[c]), []).append((primary_train[c], primary_valid[c]))
    extra, mapping, duplicates = [], {}, []
    for c, gain in secondary_importance if max_extra > 0 else []:
        if gain <= 0 or c not in secondary_train or c in mapping or c in duplicates:
            continue
        xt, xv = secondary_train[c], secondary_valid[c]
        key = signature(xt, xv)
        if any(xt.equals(t) and xv.equals(v) for t, v in seen.get(key, [])):
            duplicates.append(c)
            continue
        safe = re.sub(r"[^A-Za-z0-9_]", "_", str(c))
        name = f"p2_{len(extra)}_{safe}"[:63]
        nonce = 0
        while name in primary_train.columns or name in mapping.values():
            nonce += 1
            name = f"p2_{len(extra)}_{nonce}_{safe}"[:63]
        mapping[c] = name
        extra.append(c)
        seen.setdefault(key, []).append((xt, xv))
        if len(extra) >= max_extra:
            break
    train = pd.concat([primary_train, secondary_train[extra].rename(columns=mapping)], axis=1)
    valid = pd.concat([primary_valid, secondary_valid[extra].rename(columns=mapping)], axis=1)
    return train, valid, mapping, duplicates


def select_union(xtrain, ytrain, xvalid, yvalid, primary_columns, incumbent_score,
                 higher, fit, score, max_features=100, budget_seconds=30.0, clock=time.monotonic):
    """Choose a bounded union, retaining the best individual attempt as fallback.

    One joint fit ranks the combined pool; at most three further fits evaluate
    global and complementary feature subsets. The fixed learner is unchanged.
    """
    if (list(xtrain) != list(xvalid) or not xtrain.columns.is_unique
            or len(xtrain) != len(ytrain) or len(xvalid) != len(yvalid)):
        raise ValueError("feature matrices and labels must align")
    if not set(primary_columns).issubset(xtrain.columns) or len(primary_columns) > max_features:
        raise ValueError("the primary candidate must fit the feature limit")
    if not math.isfinite(incumbent_score):
        raise ValueError("incumbent score must be finite")
    base = list(primary_columns)
    incumbent = {"name": "single_attempt", "columns": base, "val": incumbent_score}
    rec = {"chosen": incumbent, "trials": [], "fits": 0, "train_seconds": 0.0}
    started = clock()
    if len(xtrain.columns) <= len(base) or budget_seconds <= 0:
        return {**rec, "seconds": clock() - started}
    _, importance, duration = fit(xtrain, ytrain, xvalid.iloc[:1])
    rec["fits"] += 1
    rec["train_seconds"] += duration
    ranked = list(dict.fromkeys(c for c, gain in importance if gain > 0 and c in xtrain))
    extra = [c for c in ranked if c not in base]
    own = [c for c in ranked if c in base]
    added = min(16, len(extra), max(0, max_features - 1))
    complementary = own[:max_features - added] + extra[:added]
    specifications = [("joint_top100", ranked[:max_features]),
                      ("joint_top64", ranked[:min(64, max_features)]),
                      ("complementary", complementary)]
    margin = 0.0005 if higher else max(abs(incumbent_score) * 0.002, 1e-8)
    seen = {tuple(base)}
    for name, proposed in specifications:
        if clock() - started >= budget_seconds:
            break
        wanted = set(proposed)
        columns = [c for c in xtrain if c in wanted]
        if len(columns) < 2 or tuple(columns) in seen:
            continue
        seen.add(tuple(columns))
        ts = clock()
        prediction, imp, duration = fit(xtrain[columns], ytrain, xvalid[columns])
        val = float(score(yvalid, prediction))
        rec["fits"] += 1
        rec["train_seconds"] += duration
        trial = {"name": name, "columns": columns, "val": val, "importance": imp,
                 "train_seconds": duration, "seconds": clock() - ts}
        rec["trials"].append(trial)
        if math.isfinite(val) and (val > rec["chosen"]["val"] + margin if higher else val < rec["chosen"]["val"] - margin):
            rec["chosen"] = trial
    return {**rec, "seconds": clock() - started, "margin": margin, "selection_split": "validation"}
