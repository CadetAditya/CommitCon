"""
Phase 4: Recommendation Engine for Driver Repositioning.

Combines demand forecasts from the trained model with real-time supply
data to rank zones by need and produce actionable repositioning
recommendations.
"""

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import sqlite3
import json
import math
import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "commitcon.db"
MODEL_PATH = BASE_DIR / "models" / "demand_model.joblib"
FEATURE_COLUMNS_PATH = BASE_DIR / "models" / "feature_columns.json"

DRIVERS_PER_REQUEST_RATIO = 0.8
SUPPLY_GAP_THRESHOLD = 2
MAX_REPOSITION_TRAVEL_MIN = 25

# IST offset (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# 1. Feature retrieval
# ---------------------------------------------------------------------------
def get_latest_features(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Query the feature_dataset table for the most recent timestamp.

    Returns one row per zone with all available features and zone_name.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        latest_ts = pd.read_sql(
            "SELECT MAX(timestamp) AS ts FROM feature_dataset", conn
        )["ts"].iloc[0]

        if latest_ts is None:
            raise ValueError("feature_dataset table is empty – no features to retrieve.")

        df = pd.read_sql(
            """
            SELECT f.*, z.zone_name, z.center_latitude, z.center_longitude
            FROM feature_dataset f
            JOIN zones z ON f.zone_id = z.zone_id
            WHERE f.timestamp = ?
            """,
            conn,
            params=(latest_ts,),
        )
        return df
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. Demand prediction
# ---------------------------------------------------------------------------
def predict_zone_demand(
    features_df: pd.DataFrame,
    model,
    feature_columns: list[str],
) -> pd.DataFrame:
    """Use the trained model to predict `predicted_requests` for each zone.

    Predictions are clipped to non-negative values and rounded to integers.
    """
    df = features_df.copy()

    # Align columns – fill missing with 0
    X = df.reindex(columns=feature_columns, fill_value=0).copy()
    for col in feature_columns:
        X[col] = pd.to_numeric(X[col], errors='coerce').fillna(0)
    raw_preds = model.predict(X)

    df["predicted_requests"] = np.clip(np.round(raw_preds), 0, None).astype(int)
    return df


# ---------------------------------------------------------------------------
# 3. Supply metrics
# ---------------------------------------------------------------------------
def calculate_supply_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Derive driver-supply metrics for each zone.

    New columns:
        required_drivers  – ceil(predicted_requests * DRIVERS_PER_REQUEST_RATIO)
        net_available      – available + incoming − expected departures
        supply_gap         – required − net_available (positive => shortage)
    """
    df = df.copy()
    df["required_drivers"] = df["predicted_requests"].apply(
        lambda x: math.ceil(x * DRIVERS_PER_REQUEST_RATIO)
    )
    df["net_available"] = (
        df["available_drivers"] + df["incoming_drivers"] - df["expected_departures"]
    )
    df["supply_gap"] = (df["required_drivers"] - df["net_available"]).astype(int)
    return df


# ---------------------------------------------------------------------------
# 4. Action determination
# ---------------------------------------------------------------------------
def determine_actions(df: pd.DataFrame) -> pd.DataFrame:
    """Assign a recommended_action and reason_codes list to every zone.

    Actions
    -------
    REPOSITION_IN   – supply_gap >= SUPPLY_GAP_THRESHOLD (driver shortage)
    REPOSITION_OUT  – supply_gap <= -SUPPLY_GAP_THRESHOLD (driver surplus)
    MONITOR         – otherwise (balanced)

    Reason codes (list[str])
    -------------------------
    HIGH_FORECAST_DEMAND  – predicted_requests > median across all zones
    LOW_FORECAST_DEMAND   – predicted_requests < 25th percentile
    DRIVER_SHORTAGE       – supply_gap > 0
    DRIVER_SURPLUS        – supply_gap < 0
    EVENT_NEARBY          – has_nearby_event == True
    PEAK_HOUR             – is_peak_hour == True
    HIGH_WAIT_TIME        – avg_pickup_wait_min > 10
    """
    df = df.copy()

    median_pred = df["predicted_requests"].median()
    p25_pred = df["predicted_requests"].quantile(0.25)

    actions: list[str] = []
    reasons: list[list[str]] = []

    for _, row in df.iterrows():
        gap = row["supply_gap"]

        # --- action ---
        if gap >= SUPPLY_GAP_THRESHOLD:
            action = "REPOSITION_IN"
        elif gap <= -SUPPLY_GAP_THRESHOLD:
            action = "REPOSITION_OUT"
        else:
            action = "MONITOR"

        # --- reason codes ---
        codes: list[str] = []
        if row["predicted_requests"] > median_pred:
            codes.append("HIGH_FORECAST_DEMAND")
        if row["predicted_requests"] < p25_pred:
            codes.append("LOW_FORECAST_DEMAND")
        if gap > 0:
            codes.append("DRIVER_SHORTAGE")
        if gap < 0:
            codes.append("DRIVER_SURPLUS")
        if row.get("has_nearby_event"):
            codes.append("EVENT_NEARBY")
        if row.get("is_peak_hour"):
            codes.append("PEAK_HOUR")
        if row.get("avg_pickup_wait_min", 0) > 10:
            codes.append("HIGH_WAIT_TIME")

        actions.append(action)
        reasons.append(codes)

    df["recommended_action"] = actions
    df["reason_codes"] = reasons
    return df


# ---------------------------------------------------------------------------
# 5. Repositioning feasibility
# ---------------------------------------------------------------------------
def check_repositioning_feasibility(
    df: pd.DataFrame,
    db_path: Path = DB_PATH,
) -> pd.DataFrame:
    """For REPOSITION_IN zones, find which REPOSITION_OUT zones can reach them
    within MAX_REPOSITION_TRAVEL_MIN.

    Adds a ``reposition_sources`` column (list of zone_id strings).
    If no sources exist, the action is downgraded to MONITOR and the reason
    code ``NO_NEARBY_SURPLUS`` is appended.
    """
    df = df.copy()
    df["reposition_sources"] = [[] for _ in range(len(df))]

    in_zones = df[df["recommended_action"] == "REPOSITION_IN"]["zone_id"].tolist()
    out_zones = df[df["recommended_action"] == "REPOSITION_OUT"]["zone_id"].tolist()

    if not in_zones or not out_zones:
        # If no surplus zones available to feed the shortage
        for idx in df.index:
            if df.at[idx, "recommended_action"] == "REPOSITION_IN":
                if not df.at[idx, "reposition_sources"]:
                    df.at[idx, "recommended_action"] = "MONITOR"
                    df.at[idx, "reason_codes"] = list(df.at[idx, "reason_codes"]) + [
                        "NO_NEARBY_SURPLUS"
                    ]
        return df

    conn = sqlite3.connect(str(db_path))
    try:
        placeholders_in = ",".join("?" for _ in in_zones)
        placeholders_out = ",".join("?" for _ in out_zones)

        query = (
            f"SELECT source_zone_id, destination_zone_id, estimated_travel_time_min "
            f"FROM zone_travel_times "
            f"WHERE source_zone_id IN ({placeholders_out}) "
            f"  AND destination_zone_id IN ({placeholders_in}) "
            f"  AND estimated_travel_time_min <= ?"
        )
        params = out_zones + in_zones + [MAX_REPOSITION_TRAVEL_MIN]
        travel_df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()

    # Build mapping: destination (REPOSITION_IN) -> list of reachable sources
    sources_map: dict[int, list[str]] = {}
    for _, row in travel_df.iterrows():
        dest = int(row["destination_zone_id"])
        origin = int(row["source_zone_id"])
        sources_map.setdefault(dest, []).append(_format_zone_id(origin))

    for idx in df.index:
        zone = df.at[idx, "zone_id"]
        if df.at[idx, "recommended_action"] == "REPOSITION_IN":
            srcs = sources_map.get(zone, [])
            df.at[idx, "reposition_sources"] = srcs
            if not srcs:
                df.at[idx, "recommended_action"] = "MONITOR"
                df.at[idx, "reason_codes"] = list(df.at[idx, "reason_codes"]) + [
                    "NO_NEARBY_SURPLUS"
                ]

    return df


# ---------------------------------------------------------------------------
# 6. Build recommendation payload
# ---------------------------------------------------------------------------
def _format_zone_id(zone_id) -> str:
    """Return a zero-padded zone id string like 'Z01'."""
    if isinstance(zone_id, str) and zone_id.startswith("Z"):
        return zone_id
    return f"Z{int(zone_id):02d}"


def build_recommendation(df: pd.DataFrame, run_id: str | None = None) -> dict:
    """Build the final JSON-serialisable recommendation dictionary."""
    now_ist = datetime.now(IST)

    if run_id is None:
        run_id = f"run_{now_ist.strftime('%Y%m%d_%H%M%S')}"

    # Sort by supply_gap descending (most needy first)
    df_sorted = df.sort_values("supply_gap", ascending=False).reset_index(drop=True)

    zones_payload: list[dict] = []
    for _, row in df_sorted.iterrows():
        zone_entry: dict = {
            "zone_id": _format_zone_id(row["zone_id"]),
            "zone_name": row.get("zone_name", f"Zone {row['zone_id']}"),
            "predicted_requests": int(row["predicted_requests"]),
            "required_drivers": int(row["required_drivers"]),
            "available_drivers": int(row.get("available_drivers", 0)),
            "supply_gap": int(row["supply_gap"]),
            "recommended_action": row["recommended_action"],
            "reason_codes": row["reason_codes"],
            "latitude": float(row["center_latitude"]) if "center_latitude" in row and pd.notnull(row["center_latitude"]) else None,
            "longitude": float(row["center_longitude"]) if "center_longitude" in row and pd.notnull(row["center_longitude"]) else None,
        }
        sources = row.get("reposition_sources", [])
        if sources:
            zone_entry["reposition_sources"] = sources
        zones_payload.append(zone_entry)

    action_counts = df_sorted["recommended_action"].value_counts().to_dict()
    summary = {
        "reposition_in": action_counts.get("REPOSITION_IN", 0),
        "reposition_out": action_counts.get("REPOSITION_OUT", 0),
        "monitor": action_counts.get("MONITOR", 0),
    }

    return {
        "run_id": run_id,
        "generated_at": now_ist.isoformat(),
        "model_version": "xgboost_v1",
        "total_zones": len(zones_payload),
        "summary": summary,
        "zones": zones_payload,
    }


# ---------------------------------------------------------------------------
# 7. Main orchestration
# ---------------------------------------------------------------------------
_CACHED_MODEL = None
_CACHED_FEATURE_COLUMNS = None

def get_model_and_columns():
    """Cache model and columns in memory for high-performance requests."""
    global _CACHED_MODEL, _CACHED_FEATURE_COLUMNS
    if _CACHED_MODEL is None:
        _CACHED_MODEL = joblib.load(MODEL_PATH)
        with open(FEATURE_COLUMNS_PATH, "r") as f:
            _CACHED_FEATURE_COLUMNS = json.load(f)
    return _CACHED_MODEL, _CACHED_FEATURE_COLUMNS

def generate_recommendations(run_id: str | None = None) -> dict:
    """End-to-end pipeline: features -> prediction -> supply -> actions -> payload."""
    # Load model artefacts (cached)
    model, feature_columns = get_model_and_columns()

    # Pipeline
    df = get_latest_features()
    df = predict_zone_demand(df, model, feature_columns)
    df = calculate_supply_metrics(df)
    df = determine_actions(df)
    df = check_repositioning_feasibility(df)

    return build_recommendation(df, run_id=run_id)


# ---------------------------------------------------------------------------
# 8. Personalized driver recommendations
# ---------------------------------------------------------------------------
def get_driver_personalized_recommendations(
    driver_zone_id: str | int,
    db_path: Path = DB_PATH,
    max_results: int = 5,
) -> dict:
    """Compute personalized zone recommendations for an individual driver
    based on their current zone, travel time, and citywide demand/supply gaps.
    """
    if isinstance(driver_zone_id, str):
        driver_zone_int = int(driver_zone_id.replace("Z", "").strip())
    else:
        driver_zone_int = int(driver_zone_id)

    # 1. Fetch latest overall recommendations
    city_rec = generate_recommendations()
    zones_map = {z["zone_id"]: z for z in city_rec["zones"]}

    # 2. Query travel times from driver's current zone to all other zones
    conn = sqlite3.connect(str(db_path))
    try:
        travel_df = pd.read_sql(
            """
            SELECT destination_zone_id, estimated_travel_time_min, distance_km 
            FROM zone_travel_times 
            WHERE source_zone_id = ?
            """,
            conn,
            params=(driver_zone_int,),
        )
        current_zone_info = pd.read_sql(
            "SELECT zone_name, center_latitude, center_longitude FROM zones WHERE zone_id = ?",
            conn,
            params=(driver_zone_int,),
        )
        if len(current_zone_info) > 0:
            current_zone_name = str(current_zone_info.iloc[0]["zone_name"])
            current_lat = float(current_zone_info.iloc[0]["center_latitude"]) if pd.notnull(current_zone_info.iloc[0]["center_latitude"]) else None
            current_lon = float(current_zone_info.iloc[0]["center_longitude"]) if pd.notnull(current_zone_info.iloc[0]["center_longitude"]) else None
        else:
            current_zone_name = f"Zone {driver_zone_int}"
            current_lat = None
            current_lon = None
    finally:
        conn.close()

    travel_map = {
        _format_zone_id(row["destination_zone_id"]): {
            "travel_time_min": float(row["estimated_travel_time_min"]),
            "distance_km": float(row["distance_km"]),
        }
        for _, row in travel_df.iterrows()
    }

    current_zid = _format_zone_id(driver_zone_int)

    # 3. Score target zones
    ranked_targets = []
    for zid, z in zones_map.items():
        if zid == current_zid:
            continue

        tt_info = travel_map.get(zid, {"travel_time_min": 99.0, "distance_km": 99.0})
        tt = tt_info["travel_time_min"]
        dist = tt_info["distance_km"]

        gap = z["supply_gap"]
        reqs = z["predicted_requests"]

        # Score formula: reward high gap and high demand, penalize longer travel time
        score = (gap * 3.5) + (reqs * 1.5) - (tt * 0.4)

        if gap >= 3 and tt <= 25:
            badge = "High Demand Surge"
        elif tt <= 15:
            badge = "Quick Reposition"
        elif gap > 0:
            badge = "Driver Shortage"
        else:
            badge = "High Activity"

        driver_reasons = list(z["reason_codes"])
        if tt <= 15:
            driver_reasons.insert(0, "FAST_TRAVEL_TIME")
        if gap >= 3:
            driver_reasons.insert(0, "CRITICAL_DRIVER_SHORTAGE")

        ranked_targets.append({
            "zone_id": zid,
            "zone_name": z["zone_name"],
            "latitude": z.get("latitude"),
            "longitude": z.get("longitude"),
            "predicted_requests": reqs,
            "required_drivers": z["required_drivers"],
            "available_drivers": z["available_drivers"],
            "supply_gap": gap,
            "travel_time_min": round(tt, 1),
            "distance_km": round(dist, 1),
            "opportunity_score": round(score, 1),
            "badge": badge,
            "reason_codes": driver_reasons,
            "recommended_action": z["recommended_action"],
        })

    # Sort by opportunity score descending
    ranked_targets.sort(key=lambda x: x["opportunity_score"], reverse=True)

    return {
        "driver_current_zone": {
            "zone_id": current_zid,
            "zone_name": current_zone_name,
            "latitude": current_lat,
            "longitude": current_lon,
        },
        "total_evaluated": len(ranked_targets),
        "recommendations": ranked_targets[:max_results],
    }



# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    recommendation = generate_recommendations()

    # Pretty-print
    output_json = json.dumps(recommendation, indent=2)
    print(output_json)

    # Persist to disk
    output_path = BASE_DIR / "data" / "latest_recommendation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output_json)
    print(f"\n[OK] Saved recommendation to {output_path}")

    # Summary
    summary = recommendation["summary"]
    print("\n--- Summary ---")
    print(f"  Run ID          : {recommendation['run_id']}")
    print(f"  Generated at    : {recommendation['generated_at']}")
    print(f"  Total zones     : {recommendation['total_zones']}")
    print(f"  REPOSITION_IN   : {summary['reposition_in']}")
    print(f"  REPOSITION_OUT  : {summary['reposition_out']}")
    print(f"  MONITOR         : {summary['monitor']}")
