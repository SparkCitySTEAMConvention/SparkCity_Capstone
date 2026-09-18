"""Auditable fiscal forecasts: baselines, NumPy ridge and a Spark ML challenger.

No dependencies on Spark, database access, generator formulas, or event assumptions.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

TARGETS = ("revenue", "expense")
CANDIDATES = ("training_mean", "yesterday", "last_week", "trailing_7d", "ridge_1", "ridge_10", "ridge_100")
SPARK_CANDIDATE = "spark_random_forest"


def aggregate_fiscal_spark(spark, path, expected_rows):
    """Project/cache once for validation and aggregation; collect only daily results."""
    from pyspark.sql import functions as F
    from pyspark.sql.types import NumericType, StringType, TimestampType, TimestampNTZType
    from sparkcityx.data_quality import get_validation_config, validate_dataframe
    frame = spark.read.parquet(str(path)).select(*get_validation_config("fiscal")["required_columns"]).cache()
    try:
        report = validate_dataframe(frame, "fiscal")
        if not report["valid"] or report["record_count"] != expected_rows:
            raise ValueError("Fiscal input validation/count failed")
        if not isinstance(frame.schema["sensor_id"].dataType, StringType):
            raise ValueError("Text fiscal sensor IDs required")
        if not isinstance(frame.schema["timestamp"].dataType, (TimestampType, TimestampNTZType)):
            raise ValueError("Typed Day 3 timestamps required")
        numeric = [f.name for f in frame.schema.fields if isinstance(f.dataType, NumericType)]
        bad = F.col("sensor_id").rlike(r"^\s*$")
        for col in numeric:
            bad = bad | F.isnan(col) | (F.abs(F.col(col)) == float("inf"))
        if frame.filter(bad).limit(1).count():
            raise ValueError("Nonfinite measurements or blank identifiers")
        daily = (frame.groupBy(F.to_date("timestamp").alias("day"))
                 .agg(F.avg("revenue").alias("revenue"), F.avg("expense").alias("expense"),
                      F.count("*").alias("observations"), F.countDistinct("sensor_id").alias("sensors"))
                 .orderBy("day").toPandas())
        daily["day"] = pd.to_datetime(daily.day)
        if daily.observations.sum() != expected_rows:
            raise ValueError("Aggregation row accounting failed")
        return daily.set_index("day"), report
    finally:
        frame.unpersist()


def _spark_features(spark, x, y=None):
    rows = [(int(i), *(float(value) for value in row)) for i, row in enumerate(x.to_numpy())]
    names = ["_row_id", *list(x.columns)]
    if y is not None:
        rows = [(*row, float(label)) for row, label in zip(rows, y)]
        names += ["label"]
    return spark.createDataFrame(rows, names)


def calendar_data(daily):
    if daily.empty or not set(TARGETS).issubset(daily):
        raise ValueError("Daily revenue and expense are required")
    if not isinstance(daily.index, pd.DatetimeIndex) or daily.index.tz is not None:
        raise ValueError("Use naive source-calendar dates")
    if daily.index.has_duplicates or not daily.index.equals(daily.index.normalize()):
        raise ValueError("One row per calendar day is required")
    frame = daily.loc[:, list(TARGETS)].sort_index().copy()
    for col in TARGETS:
        if not pd.api.types.is_numeric_dtype(frame[col]) or pd.api.types.is_bool_dtype(frame[col]):
            raise ValueError("Numeric daily means are required")
        if np.isinf(frame[col]).any() or (frame[col].dropna() < 0).any():
            raise ValueError("Finite nonnegative daily means are required; missing days may be NaN")
    return frame.reindex(pd.date_range(frame.index.min(), frame.index.max(), freq="D", name="day"))


def make_features(daily):
    """Target day d uses observations through d-1 only; no target-day covariates."""
    data = calendar_data(daily)
    features = pd.DataFrame(index=data.index)
    for target in TARGETS:
        past = data[target].shift(1)
        features[target + "_lag1"] = past
        features[target + "_lag7"] = data[target].shift(7)
        features[target + "_past7_mean"] = past.rolling(7, min_periods=7).mean()
        features[target + "_past28_mean"] = past.rolling(28, min_periods=28).mean()
    for weekday in range(1, 7):  # Monday is the reference category.
        features[f"weekday_{weekday}"] = (features.index.weekday == weekday).astype(float)
    return features


def chronological_parts(daily):
    data = calendar_data(daily)
    if len(data) < 200:
        raise ValueError("At least 200 calendar days required for this fixed experiment")
    features = make_features(data)
    complete = features.notna().all(axis=1) & data.notna().all(axis=1)
    n = len(data)
    a, b, c = int(n * .60), int(n * .75), int(n * .85)
    # Boundaries are set from calendar coverage before removing unavailable features.
    position = np.arange(n)
    masks = {"train": position < a, "validation": (position >= a) & (position < b),
             "calibration": (position >= b) & (position < c), "test": position >= c}
    parts, audit = {}, []
    for name, mask in masks.items():
        dates = data.index[mask & complete.to_numpy()]
        if len(dates) < 20:
            raise ValueError(f"Insufficient usable {name} dates: {len(dates)}")
        parts[name] = dates
        audit.append({"partition": name, "calendar_days": int(mask.sum()), "usable_days": len(dates),
                      "excluded_days": int(mask.sum()) - len(dates),
                      "calendar_start": data.index[mask][0].date().isoformat(),
                      "calendar_end": data.index[mask][-1].date().isoformat(),
                      "first_target": dates.min().date().isoformat(), "last_target": dates.max().date().isoformat()})
    return data, features, parts, pd.DataFrame(audit)


def fit_candidate(name, x, y, target, *, spark=None, model_directory=None):
    if name not in (*CANDIDATES, SPARK_CANDIDATE) or target not in TARGETS:
        raise ValueError("Unsupported model/target")
    if len(x) == 0 or np.asarray(y).shape != (len(x),):
        raise ValueError("Aligned nonempty training rows required")
    if not np.isfinite(x.to_numpy()).all() or not np.isfinite(np.asarray(y)).all():
        raise ValueError("Training values must be finite")
    result = {"name": name, "target": target, "training_mean": float(np.mean(y)),
              "feature_columns": list(x.columns)}
    if name == SPARK_CANDIDATE:
        from pathlib import Path
        from pyspark.ml import Pipeline
        from pyspark.ml.feature import VectorAssembler
        from pyspark.ml.regression import RandomForestRegressor
        if spark is None or model_directory is None:
            raise ValueError("Spark and a model directory are required")
        relative = target + "_random_forest"
        model = Pipeline(stages=[VectorAssembler(inputCols=list(x.columns), outputCol="features"),
                                 RandomForestRegressor(labelCol="label", featuresCol="features",
                                                       numTrees=30, maxDepth=3, minInstancesPerNode=10, seed=42)])
        fitted = model.fit(_spark_features(spark, x, y))
        fitted.write().save(str(Path(model_directory) / relative))
        result.update({"spark_model_relative_path": relative, "seed": 42, "num_trees": 30,
                       "max_depth": 3, "min_instances_per_node": 10})
    if name.startswith("ridge_"):
        penalty = float(name.split("_")[1])
        array = x.to_numpy(dtype=float)
        center = array.mean(axis=0)
        scale = array.std(axis=0)
        scale[scale == 0] = 1.
        standardized = (array - center) / scale
        coefficients = np.linalg.solve(standardized.T @ standardized + penalty * np.eye(x.shape[1]),
                                       standardized.T @ (np.asarray(y) - result["training_mean"]))
        result.update({"alpha": penalty, "center": center.tolist(), "scale": scale.tolist(),
                       "coefficients": coefficients.tolist()})
    return result


def predict_candidate(model, x, *, spark=None, model_directory=None):
    columns = model["feature_columns"]
    if not set(columns).issubset(x.columns):
        raise ValueError("Missing forecast features")
    array = x[columns].to_numpy(dtype=float)
    if not np.isfinite(array).all():
        raise ValueError("Forecast requires complete prior-calendar history")
    name, target = model["name"], model["target"]
    if name == "training_mean":
        result = np.repeat(model["training_mean"], len(x))
    elif name == "yesterday":
        result = x[target + "_lag1"].to_numpy()
    elif name == "last_week":
        result = x[target + "_lag7"].to_numpy()
    elif name == "trailing_7d":
        result = x[target + "_past7_mean"].to_numpy()
    elif name == SPARK_CANDIDATE:
        from pathlib import Path
        from pyspark.ml import PipelineModel
        if spark is None or model_directory is None:
            raise ValueError("Saved Spark model requires Spark and its model directory")
        relative = model["spark_model_relative_path"]
        if Path(relative).name != relative:
            raise ValueError("Invalid saved model path")
        fitted = PipelineModel.load(str(Path(model_directory) / relative))
        rows = fitted.transform(_spark_features(spark, x[columns])).orderBy("_row_id").select("prediction").collect()
        result = np.array([r[0] for r in rows])
    elif name.startswith("ridge_"):
        result = ((array - np.asarray(model["center"])) / np.asarray(model["scale"])) @ np.asarray(model["coefficients"]) + model["training_mean"]
    else:
        raise ValueError("Unknown saved model")
    # All candidates use the same nonnegative output policy, including during scoring.
    return np.maximum(np.asarray(result, dtype=float), 0.)


def metrics(actual, prediction):
    actual, prediction = np.asarray(actual, dtype=float), np.asarray(prediction, dtype=float)
    if actual.ndim != 1 or actual.shape != prediction.shape or not len(actual):
        raise ValueError("Aligned nonempty vectors are required")
    if not np.isfinite(actual).all() or not np.isfinite(prediction).all():
        raise ValueError("Nonfinite evaluation values")
    error = prediction - actual
    variation = float(np.sum((actual - actual.mean()) ** 2))
    return {"rows": len(actual), "rmse": float(np.sqrt(np.mean(error ** 2))),
            "mae": float(np.mean(np.abs(error))), "bias": float(np.mean(error)),
            "r2": float(1 - np.sum(error ** 2) / variation) if variation > 0 else None}


def residual_radius(actual, prediction, level=.90):
    actual, prediction = np.asarray(actual), np.asarray(prediction)
    if actual.ndim != 1 or actual.shape != prediction.shape:
        raise ValueError("Aligned calibration vectors required")
    errors = np.sort(np.abs(actual - prediction))
    if not 0 < level < 1 or len(errors) < 20 or not np.isfinite(errors).all():
        raise ValueError("At least 20 finite calibration residuals and a valid level are required")
    rank = min(int(np.ceil((len(errors) + 1) * level)), len(errors))
    return float(errors[rank - 1])


def evaluate_forecasts(daily, *, spark=None, model_directory=None):
    data, features, parts, audit = chronological_parts(daily)
    selection, testing, predictions, saved = [], [], [], {}
    candidates = (*CANDIDATES, SPARK_CANDIDATE) if spark is not None else CANDIDATES
    runtime = {"spark": spark, "model_directory": model_directory}
    for target in TARGETS:
        print(f"Fitting {target}: {len(parts['train'])} training days, {len(candidates)} candidates", flush=True)
        models = {name: fit_candidate(name, features.loc[parts["train"]], data.loc[parts["train"], target], target, **runtime)
                  for name in candidates}
        scores = {}
        for name, model in models.items():
            score = metrics(data.loc[parts["validation"], target], predict_candidate(model, features.loc[parts["validation"]], **runtime))
            scores[name] = score["rmse"]
            selection.append({"target": target, "model": name, **score})
        chosen = min(candidates, key=lambda name: scores[name])  # Stable order breaks exact ties.
        print(f"{target}: validation selected {chosen}; RMSE={scores[chosen]:.4f}", flush=True)
        model = models[chosen]
        calibration_prediction = predict_candidate(model, features.loc[parts["calibration"]], **runtime)
        radius = residual_radius(data.loc[parts["calibration"], target], calibration_prediction)
        saved[target] = {"model": model, "residual_radius": radius, "nominal_level": .90}
        # Frozen selected model plus every baseline on exactly the same held-out dates.
        for name in dict.fromkeys(["training_mean", "yesterday", "last_week", "trailing_7d", chosen]):
            prediction = predict_candidate(models[name], features.loc[parts["test"]], **runtime)
            score = metrics(data.loc[parts["test"], target], prediction)
            testing.append({"target": target, "model": name, "selected": name == chosen, **score})
        predicted = predict_candidate(model, features.loc[parts["test"]], **runtime)
        for day, actual, prediction in zip(parts["test"], data.loc[parts["test"], target], predicted):
            lower, upper = max(0., prediction - radius), prediction + radius
            predictions.append({"target": target, "day": day.date().isoformat(),
                                "origin_day": (day.to_pydatetime() - timedelta(days=1)).date().isoformat(),
                                "actual": float(actual), "prediction": float(prediction),
                                "lower": lower, "upper": upper, "covered": lower <= actual <= upper})
    artifact = {"format_version": 1, "horizon_days": 1,
                "deployment_status": "experimental; requires external validation before operational use",
                "target_definition": "Next-calendar-day fiscal observation means, not totals",
                "models": saved, "split_audit": audit.to_dict("records"),
                "candidates": list(candidates),
                "selection": "Lowest validation RMSE; no refitting after selection",
                "interval_scope": "Calibration residual bands; serial dependence prevents a guaranteed 90% coverage claim",
                "negative_predictions": "clipped to zero consistently during selection, evaluation and inference"}
    return artifact, pd.DataFrame(selection), pd.DataFrame(testing), pd.DataFrame(predictions), audit


def predict_next_day(artifact, daily, *, spark=None, model_directory=None):
    if artifact.get("format_version") != 1 or artifact.get("horizon_days") != 1:
        raise ValueError("Unsupported saved forecast format")
    history = calendar_data(daily)
    target_day = pd.Timestamp(history.index[-1].to_pydatetime() + timedelta(days=1))
    extended = history.reindex(pd.date_range(history.index.min(), target_day, freq="D", name="day"))
    features = make_features(extended).loc[[target_day]]
    result = []
    for target in TARGETS:
        config = artifact["models"][target]
        prediction = float(predict_candidate(config["model"], features, spark=spark, model_directory=model_directory)[0])
        radius = config["residual_radius"]
        result.append({"target": target, "origin_day": history.index[-1].date().isoformat(),
                       "target_day": target_day.date().isoformat(), "horizon_days": 1,
                       "model": config["model"]["name"], "prediction": prediction,
                       "lower": max(0., prediction-radius), "upper": prediction+radius})
    return pd.DataFrame(result)
