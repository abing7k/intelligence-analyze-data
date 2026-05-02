from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.services import chart_service
from app.services.preprocess_service import dataframe_records, to_jsonable


MAX_PROFILE_COLUMNS = 80
MAX_TABLE_ROWS = 80
MAX_MODEL_ROWS = 8000
TARGET_NAME_HINTS = (
    "target",
    "label",
    "class",
    "churn",
    "outcome",
    "status",
    "sales",
    "revenue",
    "amount",
    "total",
    "profit",
    "price",
    "score",
    "rating",
    "gdp",
)


@dataclass(frozen=True)
class TargetChoice:
    column: str
    task_type: str
    reason: str


def build_comprehensive_analysis(
    dataset_id: str,
    df: pd.DataFrame,
    question: str,
) -> dict[str, Any]:
    clean_df = _normalize_dataframe(df)
    profile = _dataset_profile(clean_df)
    quality = _quality_profile(clean_df)
    numeric_summary = _numeric_summary(clean_df)
    categorical_summary = _categorical_summary(clean_df)
    correlation = _correlation_analysis(clean_df)
    outliers = _outlier_summary(clean_df)
    charts = _build_default_charts(dataset_id, clean_df, quality, correlation)
    predictive = _predictive_analysis(clean_df, question, dataset_id)
    charts.extend(predictive.get("charts", []))

    return {
        "profile": profile,
        "quality": quality,
        "numeric_summary": numeric_summary,
        "categorical_summary": categorical_summary,
        "correlation": correlation,
        "outliers": outliers,
        "predictive_model": {key: value for key, value in predictive.items() if key != "charts"},
        "charts": charts,
        "notes": [
            "Predictive metrics are exploratory and should be validated with domain knowledge before production use.",
            "High-cardinality identifier-like columns are excluded from automatic modelling to reduce leakage risk.",
        ],
    }


def executive_summary(report: dict[str, Any]) -> str:
    profile = report.get("profile", {})
    quality = report.get("quality", {})
    predictive = report.get("predictive_model", {})
    missing_total = quality.get("total_missing_cells", 0)
    duplicate_rows = profile.get("duplicate_rows", 0)
    parts = [
        f"Dataset contains {profile.get('row_count', 0)} rows and {profile.get('column_count', 0)} columns.",
        f"Detected {missing_total} missing cells and {duplicate_rows} duplicate rows.",
    ]
    if report.get("correlation", {}).get("strongest_pairs"):
        strongest = report["correlation"]["strongest_pairs"][0]
        parts.append(
            "Strongest numeric relationship: "
            f"{strongest['feature_1']} vs {strongest['feature_2']} "
            f"(correlation {strongest['correlation']})."
        )
    if predictive.get("status") == "completed":
        target = predictive.get("target")
        task = predictive.get("task_type")
        holdout = predictive.get("holdout_metrics", {})
        if task == "classification":
            parts.append(
                f"Exploratory classification model for {target}: "
                f"accuracy {holdout.get('accuracy')}, macro F1 {holdout.get('f1_macro')}."
            )
        else:
            parts.append(
                f"Exploratory regression model for {target}: "
                f"R2 {holdout.get('r2')}, RMSE {holdout.get('rmse')}."
            )
    elif predictive.get("status") == "skipped":
        parts.append(f"Predictive modelling skipped: {predictive.get('reason')}.")
    return " ".join(parts)


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(column) for column in cleaned.columns]
    cleaned = cleaned.replace([np.inf, -np.inf], np.nan)
    return cleaned


def _dataset_profile(df: pd.DataFrame) -> dict[str, Any]:
    numeric_columns = [str(column) for column in df.select_dtypes(include=[np.number]).columns]
    datetime_columns = _detect_datetime_columns(df)
    categorical_columns = [
        str(column)
        for column in df.columns
        if str(column) not in numeric_columns and str(column) not in datetime_columns
    ]
    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "numeric_column_count": len(numeric_columns),
        "categorical_column_count": len(categorical_columns),
        "datetime_column_count": len(datetime_columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_rate": _round_ratio(df.duplicated().mean()) if len(df) else 0,
        "memory_usage_mb": round(float(df.memory_usage(deep=True).sum()) / 1024 / 1024, 4),
        "numeric_columns": numeric_columns[:MAX_PROFILE_COLUMNS],
        "categorical_columns": categorical_columns[:MAX_PROFILE_COLUMNS],
        "datetime_columns": datetime_columns[:MAX_PROFILE_COLUMNS],
    }


def _quality_profile(df: pd.DataFrame) -> dict[str, Any]:
    rows = []
    for column in df.columns[:MAX_PROFILE_COLUMNS]:
        series = df[column]
        missing_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))
        rows.append(
            {
                "column": str(column),
                "dtype": str(series.dtype),
                "missing_count": missing_count,
                "missing_pct": _round_ratio(missing_count / len(df)) if len(df) else 0,
                "unique_count": unique_count,
                "unique_pct": _round_ratio(unique_count / len(df)) if len(df) else 0,
            }
        )
    rows.sort(key=lambda item: (item["missing_count"], item["unique_count"]), reverse=True)
    return {
        "total_missing_cells": int(df.isna().sum().sum()),
        "columns_with_missing": int((df.isna().sum() > 0).sum()),
        "column_quality": rows,
    }


def _numeric_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    numeric_df = df.select_dtypes(include=[np.number])
    rows = []
    for column in numeric_df.columns[:MAX_PROFILE_COLUMNS]:
        series = numeric_df[column].dropna()
        if series.empty:
            continue
        rows.append(
            {
                "column": str(column),
                "count": int(series.count()),
                "mean": _safe_round(series.mean()),
                "std": _safe_round(series.std()),
                "min": _safe_round(series.min()),
                "p25": _safe_round(series.quantile(0.25)),
                "median": _safe_round(series.median()),
                "p75": _safe_round(series.quantile(0.75)),
                "max": _safe_round(series.max()),
                "skew": _safe_round(series.skew()),
            }
        )
    return rows


def _categorical_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    categorical_columns = [
        column
        for column in df.columns
        if not pd.api.types.is_numeric_dtype(df[column])
    ]
    rows = []
    for column in categorical_columns[:MAX_PROFILE_COLUMNS]:
        series = df[column].dropna().astype(str)
        if series.empty:
            continue
        top_values = series.value_counts().head(8)
        rows.append(
            {
                "column": str(column),
                "unique_count": int(series.nunique()),
                "top_values": [
                    {
                        "value": str(value),
                        "count": int(count),
                        "pct": _round_ratio(count / len(series)) if len(series) else 0,
                    }
                    for value, count in top_values.items()
                ],
            }
        )
    return rows


def _correlation_analysis(df: pd.DataFrame) -> dict[str, Any]:
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) < 2:
        return {"status": "skipped", "reason": "Fewer than two numeric columns."}
    corr = numeric_df.corr(numeric_only=True).replace([np.inf, -np.inf], np.nan).fillna(0)
    pairs = []
    columns = list(corr.columns)
    for index, left in enumerate(columns):
        for right in columns[index + 1 :]:
            value = float(corr.loc[left, right])
            pairs.append(
                {
                    "feature_1": str(left),
                    "feature_2": str(right),
                    "correlation": _safe_round(value),
                    "abs_correlation": _safe_round(abs(value)),
                }
            )
    pairs.sort(key=lambda item: item["abs_correlation"], reverse=True)
    return {
        "status": "completed",
        "method": "pearson",
        "strongest_pairs": pairs[:12],
        "matrix": dataframe_records(corr.reset_index().rename(columns={"index": "feature"}), limit=30),
    }


def _outlier_summary(df: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    numeric_df = df.select_dtypes(include=[np.number])
    for column in numeric_df.columns[:MAX_PROFILE_COLUMNS]:
        series = numeric_df[column].dropna()
        if len(series) < 4:
            continue
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        count = int(((series < lower) | (series > upper)).sum())
        rows.append(
            {
                "column": str(column),
                "outlier_count": count,
                "outlier_pct": _round_ratio(count / len(series)),
                "lower_bound": _safe_round(lower),
                "upper_bound": _safe_round(upper),
            }
        )
    rows.sort(key=lambda item: item["outlier_count"], reverse=True)
    return rows


def _build_default_charts(
    dataset_id: str,
    df: pd.DataFrame,
    quality: dict[str, Any],
    correlation: dict[str, Any],
) -> list[dict[str, Any]]:
    charts = []

    if correlation.get("status") == "completed":
        chart = chart_service.create_chart(
            dataset_id=dataset_id,
            result_table=[],
            chart_spec={"chart_type": "heatmap", "title": "Numeric Correlation Heatmap"},
            original_df=df,
        )
        charts.append(_chart_record("correlation_heatmap", "Numeric Correlation Heatmap", "heatmap", chart))

    missing_rows = [
        {"column": row["column"], "missing_count": row["missing_count"]}
        for row in quality.get("column_quality", [])
        if row.get("missing_count", 0) > 0
    ][:20]
    if missing_rows:
        chart = chart_service.create_chart(
            dataset_id=dataset_id,
            result_table=missing_rows,
            chart_spec={
                "chart_type": "bar",
                "x_field": "column",
                "y_field": "missing_count",
                "title": "Missing Values by Column",
                "x_label": "Column",
                "y_label": "Missing Count",
            },
            original_df=df,
        )
        charts.append(_chart_record("missing_values", "Missing Values by Column", "bar", chart))

    top_category = _top_low_cardinality_category(df)
    if top_category:
        column, counts = top_category
        chart = chart_service.create_chart(
            dataset_id=dataset_id,
            result_table=counts,
            chart_spec={
                "chart_type": "bar",
                "x_field": "value",
                "y_field": "count",
                "title": f"Top Values in {column}",
                "x_label": column,
                "y_label": "Count",
            },
            original_df=df,
        )
        charts.append(_chart_record("category_distribution", f"Top Values in {column}", "bar", chart))

    return [chart for chart in charts if chart.get("chart_url")]


def _predictive_analysis(df: pd.DataFrame, question: str, dataset_id: str) -> dict[str, Any]:
    target = _choose_target(df, question)
    if target is None:
        return {"status": "skipped", "reason": "No suitable target column was detected.", "charts": []}

    model_df = _prepare_model_dataframe(df, target.column)
    if len(model_df) < 30:
        return {
            "status": "skipped",
            "reason": "At least 30 complete target rows are required for automatic validation.",
            "target": target.column,
            "task_type": target.task_type,
            "charts": [],
        }

    if len(model_df) > MAX_MODEL_ROWS:
        model_df = model_df.sample(MAX_MODEL_ROWS, random_state=42)

    y = model_df[target.column]
    x = model_df.drop(columns=[target.column])
    x = _feature_frame(x)
    x = _drop_leaky_or_unusable_features(x, target.column)
    if x.empty:
        return {
            "status": "skipped",
            "reason": "No usable feature columns remained after leakage and cardinality checks.",
            "target": target.column,
            "task_type": target.task_type,
            "charts": [],
        }

    try:
        if target.task_type == "classification":
            return _classification_report(dataset_id, x, y.astype(str), target)
        return _regression_report(dataset_id, x, pd.to_numeric(y, errors="coerce"), target)
    except Exception as exc:
        return {
            "status": "skipped",
            "reason": f"Automatic predictive modelling failed: {exc}",
            "target": target.column,
            "task_type": target.task_type,
            "charts": [],
        }


def _classification_report(dataset_id: str, x: pd.DataFrame, y: pd.Series, target: TargetChoice) -> dict[str, Any]:
    class_counts = y.value_counts()
    if len(class_counts) < 2:
        return {
            "status": "skipped",
            "reason": "Classification target has fewer than two classes.",
            "target": target.column,
            "task_type": "classification",
            "charts": [],
        }
    min_class_count = int(class_counts.min())
    stratify = y if min_class_count >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=stratify,
    )
    model = _classification_pipeline(x)
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    cv_splits = max(2, min(5, min_class_count))
    cv = StratifiedKFold(n_splits=cv_splits, shuffle=True, random_state=42)
    scores = cross_validate(
        _classification_pipeline(x),
        x,
        y,
        cv=cv,
        scoring={"accuracy": "accuracy", "f1_macro": "f1_macro", "f1_weighted": "f1_weighted"},
        error_score="raise",
    )
    importances = _feature_importance(model, x)
    charts = [_target_distribution_chart(dataset_id, target.column, y)]
    if importances:
        charts.append(_feature_importance_chart(dataset_id, importances, target.column))
    return {
        "status": "completed",
        "target": target.column,
        "task_type": "classification",
        "target_reason": target.reason,
        "row_count_used": int(len(x)),
        "feature_count_used": int(len(x.columns)),
        "class_distribution": [
            {"class": str(label), "count": int(count)}
            for label, count in class_counts.head(20).items()
        ],
        "holdout_metrics": {
            "accuracy": _safe_round(accuracy_score(y_test, predictions)),
            "precision_macro": _safe_round(precision_score(y_test, predictions, average="macro", zero_division=0)),
            "recall_macro": _safe_round(recall_score(y_test, predictions, average="macro", zero_division=0)),
            "f1_macro": _safe_round(f1_score(y_test, predictions, average="macro", zero_division=0)),
            "f1_weighted": _safe_round(f1_score(y_test, predictions, average="weighted", zero_division=0)),
        },
        "cross_validation": {
            "folds": cv_splits,
            "accuracy_mean": _safe_round(scores["test_accuracy"].mean()),
            "accuracy_std": _safe_round(scores["test_accuracy"].std()),
            "f1_macro_mean": _safe_round(scores["test_f1_macro"].mean()),
            "f1_macro_std": _safe_round(scores["test_f1_macro"].std()),
            "f1_weighted_mean": _safe_round(scores["test_f1_weighted"].mean()),
            "f1_weighted_std": _safe_round(scores["test_f1_weighted"].std()),
        },
        "top_features": importances,
        "charts": [chart for chart in charts if chart.get("chart_url")],
    }


def _regression_report(dataset_id: str, x: pd.DataFrame, y: pd.Series, target: TargetChoice) -> dict[str, Any]:
    valid = y.notna()
    x = x.loc[valid]
    y = y.loc[valid]
    if len(y) < 30 or y.nunique(dropna=True) < 5:
        return {
            "status": "skipped",
            "reason": "Regression target needs at least 30 rows and 5 unique numeric values.",
            "target": target.column,
            "task_type": "regression",
            "charts": [],
        }
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.2, random_state=42)
    model = _regression_pipeline(x)
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    cv_splits = max(2, min(5, len(x) // 10))
    cv = KFold(n_splits=cv_splits, shuffle=True, random_state=42)
    scores = cross_validate(
        _regression_pipeline(x),
        x,
        y,
        cv=cv,
        scoring={"r2": "r2", "neg_rmse": "neg_root_mean_squared_error", "neg_mae": "neg_mean_absolute_error"},
        error_score="raise",
    )
    importances = _feature_importance(model, x)
    charts = [_prediction_scatter_chart(dataset_id, y_test, predictions, target.column)]
    if importances:
        charts.append(_feature_importance_chart(dataset_id, importances, target.column))
    return {
        "status": "completed",
        "target": target.column,
        "task_type": "regression",
        "target_reason": target.reason,
        "row_count_used": int(len(x)),
        "feature_count_used": int(len(x.columns)),
        "holdout_metrics": {
            "r2": _safe_round(r2_score(y_test, predictions)),
            "mae": _safe_round(mean_absolute_error(y_test, predictions)),
            "rmse": _safe_round(mean_squared_error(y_test, predictions) ** 0.5),
        },
        "cross_validation": {
            "folds": cv_splits,
            "r2_mean": _safe_round(scores["test_r2"].mean()),
            "r2_std": _safe_round(scores["test_r2"].std()),
            "rmse_mean": _safe_round((-scores["test_neg_rmse"]).mean()),
            "rmse_std": _safe_round((-scores["test_neg_rmse"]).std()),
            "mae_mean": _safe_round((-scores["test_neg_mae"]).mean()),
            "mae_std": _safe_round((-scores["test_neg_mae"]).std()),
        },
        "top_features": importances,
        "charts": [chart for chart in charts if chart.get("chart_url")],
    }


def _choose_target(df: pd.DataFrame, question: str) -> TargetChoice | None:
    question_lower = question.lower()
    columns = [str(column) for column in df.columns]
    for column in columns:
        if column.lower() in question_lower and _is_predictable_target(df[column]):
            return TargetChoice(column, _task_type_for_target(df[column]), "Column name appears in the question.")

    hinted = sorted(
        [column for column in columns if any(hint in column.lower() for hint in TARGET_NAME_HINTS)],
        key=lambda value: _target_hint_rank(value),
    )
    for column in hinted:
        if _is_predictable_target(df[column]):
            return TargetChoice(column, _task_type_for_target(df[column]), "Column name matches a common target pattern.")

    numeric_columns = [str(column) for column in df.select_dtypes(include=[np.number]).columns]
    for column in reversed(numeric_columns):
        if _is_predictable_target(df[column]):
            return TargetChoice(column, "regression", "Fallback to a numeric column with sufficient variation.")

    categorical_columns = [
        str(column)
        for column in df.columns
        if not pd.api.types.is_numeric_dtype(df[column])
    ]
    for column in reversed(categorical_columns):
        if _is_predictable_target(df[column]):
            return TargetChoice(column, "classification", "Fallback to a categorical column with usable classes.")
    return None


def _is_predictable_target(series: pd.Series) -> bool:
    clean = series.dropna()
    if len(clean) < 30:
        return False
    unique_count = clean.nunique()
    if pd.api.types.is_numeric_dtype(clean):
        return unique_count >= 5
    return 2 <= unique_count <= min(50, max(2, len(clean) // 5))


def _task_type_for_target(series: pd.Series) -> str:
    clean = series.dropna()
    if pd.api.types.is_numeric_dtype(clean) and clean.nunique() > 20:
        return "regression"
    return "classification"


def _prepare_model_dataframe(df: pd.DataFrame, target_column: str) -> pd.DataFrame:
    return df.dropna(subset=[target_column]).copy()


def _feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    prepared = pd.DataFrame(index=df.index)
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            prepared[str(column)] = series.astype("int64") // 10**9
            continue
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            sample = series.dropna().astype(str).head(80)
            if sample.empty or not _looks_datetime_like(sample):
                prepared[str(column)] = series
                continue
            parsed = pd.to_datetime(series, errors="coerce")
            if parsed.notna().mean() >= 0.8:
                prepared[str(column)] = parsed.astype("int64") // 10**9
                continue
        prepared[str(column)] = series
    return prepared


def _drop_leaky_or_unusable_features(df: pd.DataFrame, target_column: str) -> pd.DataFrame:
    usable_columns = []
    target_lower = target_column.lower()
    for column in df.columns:
        series = df[column]
        column_lower = str(column).lower()
        if column_lower == target_lower or target_lower in column_lower:
            continue
        if series.nunique(dropna=True) <= 1:
            continue
        if not pd.api.types.is_numeric_dtype(series):
            unique_count = series.nunique(dropna=True)
            if unique_count > min(200, max(20, len(series) // 2)):
                continue
        usable_columns.append(column)
    return df[usable_columns]


def _classification_pipeline(x: pd.DataFrame) -> Pipeline:
    return Pipeline(
        [
            ("preprocess", _preprocessor(x)),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=120,
                    max_depth=8,
                    min_samples_leaf=2,
                    class_weight="balanced_subsample",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def _regression_pipeline(x: pd.DataFrame) -> Pipeline:
    return Pipeline(
        [
            ("preprocess", _preprocessor(x)),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=120,
                    max_depth=10,
                    min_samples_leaf=2,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def _preprocessor(x: pd.DataFrame) -> ColumnTransformer:
    numeric_features = [column for column in x.columns if pd.api.types.is_numeric_dtype(x[column])]
    categorical_features = [column for column in x.columns if column not in numeric_features]
    return ColumnTransformer(
        [
            (
                "num",
                Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]),
                numeric_features,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore", max_categories=20, sparse_output=False)),
                    ]
                ),
                categorical_features,
            ),
        ],
        remainder="drop",
    )


def _feature_importance(model: Pipeline, x: pd.DataFrame) -> list[dict[str, Any]]:
    estimator = model.named_steps["model"]
    importances = getattr(estimator, "feature_importances_", None)
    if importances is None:
        return []
    feature_names = list(model.named_steps["preprocess"].get_feature_names_out())
    rows = [
        {
            "feature": _readable_feature_name(name),
            "importance": _safe_round(value),
        }
        for name, value in zip(feature_names, importances, strict=False)
    ]
    rows.sort(key=lambda item: item["importance"], reverse=True)
    return rows[:15]


def _feature_importance_chart(dataset_id: str, importances: list[dict[str, Any]], target: str) -> dict[str, Any]:
    rows = list(reversed(importances[:12]))
    chart = chart_service.create_chart(
        dataset_id=dataset_id,
        result_table=rows,
        chart_spec={
            "chart_type": "bar",
            "x_field": "feature",
            "y_field": "importance",
            "title": f"Top Predictive Features for {target}",
            "x_label": "Feature",
            "y_label": "Importance",
        },
        original_df=pd.DataFrame(rows),
    )
    return _chart_record("feature_importance", f"Top Predictive Features for {target}", "bar", chart)


def _target_distribution_chart(dataset_id: str, target: str, y: pd.Series) -> dict[str, Any]:
    rows = [
        {"class": str(label), "count": int(count)}
        for label, count in y.value_counts().head(20).items()
    ]
    chart = chart_service.create_chart(
        dataset_id=dataset_id,
        result_table=rows,
        chart_spec={
            "chart_type": "bar",
            "x_field": "class",
            "y_field": "count",
            "title": f"Target Distribution: {target}",
            "x_label": target,
            "y_label": "Count",
        },
        original_df=pd.DataFrame(rows),
    )
    return _chart_record("target_distribution", f"Target Distribution: {target}", "bar", chart)


def _prediction_scatter_chart(dataset_id: str, actual: pd.Series, predicted: np.ndarray, target: str) -> dict[str, Any]:
    rows = [
        {"actual": to_jsonable(actual_value), "predicted": to_jsonable(predicted_value)}
        for actual_value, predicted_value in zip(actual.tolist(), predicted.tolist(), strict=False)
    ][:MAX_TABLE_ROWS]
    chart = chart_service.create_chart(
        dataset_id=dataset_id,
        result_table=rows,
        chart_spec={
            "chart_type": "scatter",
            "x_field": "actual",
            "y_field": "predicted",
            "title": f"Holdout Prediction Accuracy: {target}",
            "x_label": "Actual",
            "y_label": "Predicted",
        },
        original_df=pd.DataFrame(rows),
    )
    return _chart_record("prediction_scatter", f"Holdout Prediction Accuracy: {target}", "scatter", chart)


def _top_low_cardinality_category(df: pd.DataFrame) -> tuple[str, list[dict[str, Any]]] | None:
    candidates = []
    for column in df.columns:
        series = df[column].dropna().astype(str)
        unique_count = series.nunique()
        if 2 <= unique_count <= 30:
            candidates.append((str(column), unique_count, series))
    if not candidates:
        return None
    column, _, series = sorted(candidates, key=lambda item: item[1])[0]
    rows = [
        {"value": str(value), "count": int(count)}
        for value, count in series.value_counts().head(15).items()
    ]
    return column, rows


def _detect_datetime_columns(df: pd.DataFrame) -> list[str]:
    detected = []
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            detected.append(str(column))
            continue
        if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
            continue
        sample = series.dropna().astype(str).head(80)
        if sample.empty:
            continue
        if not _looks_datetime_like(sample):
            continue
        parsed = pd.to_datetime(sample, errors="coerce")
        if parsed.notna().mean() >= 0.8:
            detected.append(str(column))
    return detected


def _looks_datetime_like(sample: pd.Series) -> bool:
    pattern = r"(?:\d{4}[-/]\d{1,2})|(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})|(?:\d{1,2}:\d{2})"
    return bool(sample.str.contains(pattern, regex=True, na=False).mean() >= 0.5)


def _chart_record(name: str, title: str, chart_type: str, chart: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "title": title,
        "chart_type": chart_type,
        "chart_id": chart.get("chart_id"),
        "chart_path": chart.get("chart_path"),
        "chart_url": chart.get("chart_url"),
    }


def _target_hint_rank(column: str) -> tuple[int, str]:
    column_lower = column.lower()
    for index, hint in enumerate(TARGET_NAME_HINTS):
        if hint in column_lower:
            return index, column_lower
    return len(TARGET_NAME_HINTS), column_lower


def _readable_feature_name(name: str) -> str:
    for prefix in ("num__", "cat__"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
    return name.replace("_infrequent_sklearn", " (infrequent)")


def _safe_round(value: Any, digits: int = 4) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(numeric) or np.isinf(numeric):
        return None
    return round(numeric, digits)


def _round_ratio(value: Any) -> float | None:
    rounded = _safe_round(value)
    return rounded if rounded is not None else None
