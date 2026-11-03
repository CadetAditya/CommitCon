import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
"""
Phase 3 – Demand Forecasting Model
====================================
Trains an XGBoost regression model to predict next-hour ride requests per zone
using the engineered feature_dataset produced in Phase 2.

Outputs
-------
- models/demand_model.joblib  : serialised XGBRegressor
- models/feature_columns.json : ordered list of feature column names

Usage
-----
    python phase3_forecast.py
"""

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "commitcon.db"
MODELS_DIR = BASE_DIR / "models"

# ---------------------------------------------------------------------------
# Feature columns (everything except identifiers and target)
# ---------------------------------------------------------------------------
FEATURE_COLUMNS = [
    # Temporal
    "hour",
    "day_of_week",
    "is_weekend",
    "month",
    "is_peak_hour",
    # Demand history
    "requests_last_15m",
    "requests_last_30m",
    "requests_last_60m",
    "requests_last_120m",
    "requests_same_hour_prev_week",
    # Trip characteristics
    "avg_trip_duration_min",
    "avg_pickup_wait_min",
    # Supply
    "available_drivers",
    "occupied_drivers",
    "incoming_drivers",
    "expected_departures",
    # Events
    "has_nearby_event",
    "event_distance_km",
    "event_start_in_min",
    "event_end_in_min",
    "expected_attendance",
    # Spatial / neighbour
    "neighbor_avg_requests",
    "neighbor_available_drivers",
    "min_travel_time_to_neighbor_min",
]

# Columns where NaN should be filled with 0 (counts / flags)
_ZERO_FILL = [
    "requests_last_15m",
    "requests_last_30m",
    "requests_last_60m",
    "requests_last_120m",
    "requests_same_hour_prev_week",
    "available_drivers",
    "occupied_drivers",
    "incoming_drivers",
    "expected_departures",
    "neighbor_avg_requests",
    "neighbor_available_drivers",
    "expected_attendance",
]

# Boolean columns – fill with False (0)
_BOOL_FILL = [
    "is_weekend",
    "is_peak_hour",
    "has_nearby_event",
]

# Continuous columns – fill with median (computed on training data)
_MEDIAN_FILL = [
    "avg_trip_duration_min",
    "avg_pickup_wait_min",
    "event_distance_km",
    "event_start_in_min",
    "event_end_in_min",
    "min_travel_time_to_neighbor_min",
]


# ===================================================================
# 1. Data Loading & Preparation
# ===================================================================
def load_data(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load feature_dataset from SQLite, drop null targets, impute NaNs."""
    import sqlite3

    print("=" * 60)
    print("Phase 3 – Demand Forecasting")
    print("=" * 60)
    print(f"\n📂 Loading data from {db_path} ...")

    con = sqlite3.connect(str(db_path))
    df = pd.read_sql("SELECT * FROM feature_dataset", con)
    con.close()

    print(f"   Raw rows loaded        : {len(df):,}")

    # Drop rows where target is missing
    df = df.dropna(subset=["target_requests"]).reset_index(drop=True)
    print(f"   Rows after dropping NaN : {len(df):,}")

    # Parse timestamp for time-based splitting
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # --- Imputation --------------------------------------------------
    # Zero-fill count columns
    for col in _ZERO_FILL:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # Boolean fill
    for col in _BOOL_FILL:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    # Median fill for continuous columns
    for col in _MEDIAN_FILL:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median())

    # Safety net: fill any remaining NaN in features with 0
    for col in FEATURE_COLUMNS:
        if col in df.columns and df[col].isna().any():
            df[col] = df[col].fillna(0)

    print(f"   Features                : {len(FEATURE_COLUMNS)}")
    print(f"   Remaining NaN in feats  : {df[FEATURE_COLUMNS].isna().sum().sum()}")

    return df


# ===================================================================
# 2. Train / Test Split (time-based)
# ===================================================================
def time_split(df: pd.DataFrame, test_days: int = 7):
    """Split by time: last `test_days` days → test, rest → train."""
    cutoff = df["timestamp"].max() - pd.Timedelta(days=test_days)
    train = df[df["timestamp"] <= cutoff].copy()
    test = df[df["timestamp"] > cutoff].copy()

    print(f"\n⏱  Time-based split (last {test_days} days for test)")
    print(f"   Train : {len(train):>8,} rows  "
          f"({train['timestamp'].min().date()} → {train['timestamp'].max().date()})")
    print(f"   Test  : {len(test):>8,} rows  "
          f"({test['timestamp'].min().date()} → {test['timestamp'].max().date()})")

    return train, test


# ===================================================================
# 3. Baseline Model
# ===================================================================
def baseline_predict(df: pd.DataFrame) -> np.ndarray:
    """Baseline: average of requests_last_60m and requests_same_hour_prev_week."""
    preds = (
        df["requests_last_60m"].values
        + df["requests_same_hour_prev_week"].values
    ) / 2.0
    return np.maximum(preds, 0)


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, label: str = "Model"):
    """Return dict of MAE, RMSE, MAPE."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    # MAPE – avoid division by zero
    mask = y_true != 0
    if mask.sum() > 0:
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
    else:
        mape = np.nan
    return {"label": label, "MAE": mae, "RMSE": rmse, "MAPE(%)": mape}


# ===================================================================
# 4. XGBoost Model Training
# ===================================================================
def train_xgboost(
    train_df: pd.DataFrame,
    val_fraction: float = 0.20,
) -> XGBRegressor:
    """Train XGBRegressor with early stopping on a held-out validation set."""
    # Chronological validation split (last val_fraction of training data)
    n_val = int(len(train_df) * val_fraction)
    tr = train_df.iloc[:-n_val]
    val = train_df.iloc[-n_val:]

    X_tr = tr[FEATURE_COLUMNS]
    y_tr = tr["target_requests"]
    X_val = val[FEATURE_COLUMNS]
    y_val = val["target_requests"]

    print(f"\n🤖 Training XGBoost  (train={len(tr):,}, val={len(val):,}) ...")

    model = XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        objective="reg:squarederror",
        early_stopping_rounds=20,
        eval_metric="rmse",
    )

    model.fit(
        X_tr,
        y_tr,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    best_iter = model.best_iteration
    print(f"   Best iteration          : {best_iter}")
    print(f"   Best val RMSE           : {model.best_score:.4f}")

    return model


# ===================================================================
# 5. Model Evaluation
# ===================================================================
def print_comparison(baseline_metrics: dict, xgb_metrics: dict):
    """Print a side-by-side comparison table."""
    print("\n" + "=" * 60)
    print("📊 Model Comparison on Test Set")
    print("=" * 60)
    header = f"{'Metric':<12} {'Baseline':>12} {'XGBoost':>12} {'Improvement':>14}"
    print(header)
    print("-" * len(header))
    for metric in ["MAE", "RMSE", "MAPE(%)"]:
        b_val = baseline_metrics[metric]
        x_val = xgb_metrics[metric]
        if b_val and b_val != 0:
            improv = (b_val - x_val) / b_val * 100
            print(f"{metric:<12} {b_val:>12.3f} {x_val:>12.3f} {improv:>+13.1f}%")
        else:
            print(f"{metric:<12} {b_val:>12.3f} {x_val:>12.3f} {'N/A':>14}")
    print()


def print_feature_importance(model: XGBRegressor, top_n: int = 10):
    """Print the top-N most important features by gain."""
    importances = model.feature_importances_
    feat_imp = sorted(
        zip(FEATURE_COLUMNS, importances),
        key=lambda x: x[1],
        reverse=True,
    )
    print("🏆 Top 10 Feature Importances (gain)")
    print("-" * 40)
    for rank, (feat, score) in enumerate(feat_imp[:top_n], 1):
        bar = "█" * int(score / feat_imp[0][1] * 20)
        print(f"   {rank:>2}. {feat:<35s} {score:.4f}  {bar}")
    print()


# ===================================================================
# 6. Model Saving
# ===================================================================
def save_model(model: XGBRegressor):
    """Persist model and feature column list to disk."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / "demand_model.joblib"
    cols_path = MODELS_DIR / "feature_columns.json"

    joblib.dump(model, model_path)
    with open(cols_path, "w") as f:
        json.dump(FEATURE_COLUMNS, f, indent=2)

    print(f"💾 Model saved  → {model_path}")
    print(f"💾 Columns saved → {cols_path}")


# ===================================================================
# 7. Prediction Function
# ===================================================================
def predict_demand(model, features_df: pd.DataFrame) -> np.ndarray:
    """Predict ride requests for the next hour given current features.

    Parameters
    ----------
    model : XGBRegressor
        Trained demand model.
    features_df : pd.DataFrame
        DataFrame containing at least the columns in FEATURE_COLUMNS.

    Returns
    -------
    np.ndarray
        Non-negative integer predictions.
    """
    X = features_df.reindex(columns=FEATURE_COLUMNS, fill_value=0).copy()
    for col in FEATURE_COLUMNS:
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)
    predictions = model.predict(X)
    return np.maximum(predictions, 0).astype(int)  # No negative predictions


# ===================================================================
# Main
# ===================================================================
def main():
    # 1. Load data
    df = load_data()

    # 2. Time-based split
    train_df, test_df = time_split(df, test_days=7)

    X_test = test_df[FEATURE_COLUMNS]
    y_test = test_df["target_requests"].values

    # 3. Baseline
    baseline_preds = baseline_predict(test_df)
    baseline_metrics = evaluate(y_test, baseline_preds, label="Baseline")

    # 4. Train XGBoost
    model = train_xgboost(train_df)

    # 5. Evaluate XGBoost
    xgb_preds = model.predict(X_test)
    xgb_preds = np.maximum(xgb_preds, 0)
    xgb_metrics = evaluate(y_test, xgb_preds, label="XGBoost")

    print_comparison(baseline_metrics, xgb_metrics)
    print_feature_importance(model)

    # 6. Save model
    save_model(model)

    # 7. Sample predictions for 5 zones
    print("\n🔮 Sample Predictions (5 zones from test set)")
    print("-" * 65)
    sample = test_df.drop_duplicates(subset="zone_id").head(5)
    sample_preds = predict_demand(model, sample)
    for _, row in sample.iterrows():
        zone = row["zone_id"]
        actual = int(row["target_requests"])
        pred = sample_preds[sample.index.get_loc(row.name)]
        diff = pred - actual
        print(f"   Zone {zone:<6}  Actual: {actual:>4}   Predicted: {pred:>4}   Δ: {diff:>+4}")

    print("\n✅ Phase 3 complete.\n")


if __name__ == "__main__":
    main()
