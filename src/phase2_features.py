"""
Phase 2 – Feature Engineering for Ride-Hailing Recommendation System.

Reads raw tables from the CommitCon SQLite database and constructs a
``feature_dataset`` table with one row per (timestamp, zone) containing
time/calendar features, recent-demand windows, supply snapshots, event
proximity features, spatial/neighbor aggregates, and a prediction target.
"""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DB_PATH: Path = Path(__file__).parent.parent / "data" / "commitcon.db"

PEAK_HOURS: set[int] = {8, 9, 10, 11, 17, 18, 19, 20}
NEIGHBOR_TRAVEL_THRESHOLD_MIN: float = 25.0
EVENT_PROXIMITY_KM: float = 5.0
EARTH_RADIUS_KM: float = 6_371.0


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in km between two points."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _haversine_vectorized(
    lat1: np.ndarray,
    lon1: np.ndarray,
    lat2: float,
    lon2: float,
) -> np.ndarray:
    """Vectorized Haversine – arrays for point-set vs. single point."""
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1
    dlon = lon2_r - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * math.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_tables(db_path: Path) -> dict[str, pd.DataFrame]:
    """Load all raw tables from the SQLite database into DataFrames."""
    conn = sqlite3.connect(str(db_path))
    tables: dict[str, pd.DataFrame] = {}
    try:
        tables["zones"] = pd.read_sql("SELECT * FROM zones", conn)
        tables["historical_demand"] = pd.read_sql("SELECT * FROM historical_demand", conn)
        tables["driver_supply"] = pd.read_sql("SELECT * FROM driver_supply", conn)
        tables["events"] = pd.read_sql("SELECT * FROM events", conn)
        tables["zone_travel_times"] = pd.read_sql("SELECT * FROM zone_travel_times", conn)
    finally:
        conn.close()

    # Parse timestamp columns
    tables["historical_demand"]["timestamp"] = pd.to_datetime(
        tables["historical_demand"]["timestamp"]
    )
    tables["driver_supply"]["timestamp"] = pd.to_datetime(
        tables["driver_supply"]["timestamp"]
    )
    tables["events"]["start_time"] = pd.to_datetime(tables["events"]["start_time"])
    tables["events"]["end_time"] = pd.to_datetime(tables["events"]["end_time"])

    return tables


# ---------------------------------------------------------------------------
# Feature builders
# ---------------------------------------------------------------------------

def build_base_grid(demand: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    """Create the base (timestamp × zone) grid from historical demand."""
    unique_ts = demand["timestamp"].drop_duplicates().sort_values()
    active_zones = zones.loc[zones["is_active"] == 1, "zone_id"].unique()

    grid = pd.MultiIndex.from_product(
        [unique_ts, active_zones], names=["timestamp", "zone_id"]
    ).to_frame(index=False)

    return grid


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive calendar / time-of-day features from *timestamp*."""
    ts = df["timestamp"]
    df = df.copy()
    df["hour"] = ts.dt.hour.astype("int16")
    df["day_of_week"] = ts.dt.dayofweek.add(1).astype("int16")  # Mon=1 ... Sun=7
    df["is_weekend"] = df["day_of_week"].isin([6, 7]).astype(int)
    df["month"] = ts.dt.month.astype("int16")
    df["is_peak_hour"] = df["hour"].isin(PEAK_HOURS).astype(int)
    return df


def add_demand_features(
    df: pd.DataFrame, demand: pd.DataFrame
) -> pd.DataFrame:
    """Add recent-demand windows, historical same-hour-prev-week, and stats."""
    # Index demand for fast lookup
    demand_indexed = demand.set_index(["timestamp", "zone_id"]).sort_index()

    # Merge current-hour demand
    current = demand[["timestamp", "zone_id", "ride_requests",
                       "avg_trip_duration_min", "avg_pickup_wait_min"]].copy()
    df = df.merge(current, on=["timestamp", "zone_id"], how="left")

    # requests_last_60m == current hour's ride_requests
    df["requests_last_60m"] = df["ride_requests"].fillna(0).astype(int)

    # requests_last_15m / 30m – with hourly granularity these are 0
    df["requests_last_15m"] = 0
    df["requests_last_30m"] = 0

    # requests_last_120m – current + previous hour
    prev_hour = df[["timestamp", "zone_id"]].copy()
    prev_hour["prev_ts"] = prev_hour["timestamp"] - pd.Timedelta(hours=1)
    prev_demand = demand[["timestamp", "zone_id", "ride_requests"]].rename(
        columns={"timestamp": "prev_ts", "ride_requests": "prev_requests"}
    )
    prev_hour = prev_hour.merge(prev_demand, on=["prev_ts", "zone_id"], how="left")
    df["requests_last_120m"] = (
        df["requests_last_60m"] + prev_hour["prev_requests"].fillna(0)
    ).astype(int)

    # requests_same_hour_prev_week – same hour & day-of-week, 7 days prior
    prev_week = df[["timestamp", "zone_id"]].copy()
    prev_week["prev_week_ts"] = prev_week["timestamp"] - pd.Timedelta(weeks=1)
    pw_demand = demand[["timestamp", "zone_id", "ride_requests"]].rename(
        columns={"timestamp": "prev_week_ts", "ride_requests": "prev_week_requests"}
    )
    prev_week = prev_week.merge(pw_demand, on=["prev_week_ts", "zone_id"], how="left")
    df["requests_same_hour_prev_week"] = prev_week["prev_week_requests"]

    # Clean up helper column
    df.drop(columns=["ride_requests"], inplace=True)

    return df


def add_supply_features(
    df: pd.DataFrame, supply: pd.DataFrame
) -> pd.DataFrame:
    """Merge driver-supply snapshot onto the grid."""
    supply_cols = supply[
        ["timestamp", "zone_id", "available_drivers", "occupied_drivers",
         "incoming_drivers", "expected_departures"]
    ].copy()

    # If multiple snapshots per (ts, zone), take the latest / average
    supply_agg = (
        supply_cols
        .groupby(["timestamp", "zone_id"], as_index=False)
        .agg({
            "available_drivers": "mean",
            "occupied_drivers": "mean",
            "incoming_drivers": "mean",
            "expected_departures": "mean",
        })
    )

    df = df.merge(supply_agg, on=["timestamp", "zone_id"], how="left")
    return df


def add_event_features(
    df: pd.DataFrame,
    events: pd.DataFrame,
    zones: pd.DataFrame,
) -> pd.DataFrame:
    """Compute event-proximity features using Haversine distance."""
    zone_coords = zones.set_index("zone_id")[["center_latitude", "center_longitude"]]

    # Pre-compute results containers
    has_nearby = np.zeros(len(df), dtype=int)
    event_dist = np.full(len(df), np.nan)
    event_start_in = np.full(len(df), np.nan)
    event_end_in = np.full(len(df), np.nan)
    event_attendance = np.full(len(df), np.nan)

    if events.empty:
        df["has_nearby_event"] = has_nearby
        df["event_distance_km"] = event_dist
        df["event_start_in_min"] = event_start_in
        df["event_end_in_min"] = event_end_in
        df["expected_attendance"] = event_attendance
        return df

    # Iterate over unique timestamps for efficiency
    ts_groups = df.groupby("timestamp")
    event_lats = events["latitude"].values
    event_lons = events["longitude"].values

    for ts, group_idx in ts_groups.groups.items():
        # Events active or upcoming at this timestamp
        # "Active" = start_time <= ts < end_time  OR  upcoming = ts < start_time
        # We consider events that are active or starting within a reasonable window.
        # Per spec: "active/upcoming event near this zone"
        valid_statuses = {'SCHEDULED', 'CONFIRMED', 'COMPLETED'}
        relevant = events[
            (events['end_time'] >= ts) &
            (events['start_time'] <= ts + pd.Timedelta(hours=6)) &
            (events['event_status'].str.upper().isin(valid_statuses) | events['event_status'].isna())
        ]
        if relevant.empty:
            continue

        rel_lats = relevant["latitude"].values
        rel_lons = relevant["longitude"].values
        rel_starts = relevant["start_time"].values
        rel_ends = relevant["end_time"].values
        rel_attend = relevant["expected_attendance"].values

        for idx in group_idx:
            zid = df.at[idx, "zone_id"]
            if zid not in zone_coords.index:
                continue
            z_lat = zone_coords.at[zid, "center_latitude"]
            z_lon = zone_coords.at[zid, "center_longitude"]

            # Vectorized distances to all relevant events
            dists = _haversine_vectorized(
                np.array([z_lat] * len(relevant)),
                np.array([z_lon] * len(relevant)),
                0, 0,  # dummy – we'll compute pairwise below
            )
            # Actually compute pairwise properly
            dists = np.array([
                _haversine(z_lat, z_lon, rlat, rlon)
                for rlat, rlon in zip(rel_lats, rel_lons)
            ])

            closest_idx = np.argmin(dists)
            closest_dist = dists[closest_idx]

            if closest_dist <= EVENT_PROXIMITY_KM:
                has_nearby[idx] = 1
                event_dist[idx] = round(closest_dist, 2)

                # Time deltas in minutes
                ts_np = np.datetime64(ts)
                start_delta = (rel_starts[closest_idx] - ts_np) / np.timedelta64(1, "m")
                end_delta = (rel_ends[closest_idx] - ts_np) / np.timedelta64(1, "m")

                event_start_in[idx] = int(round(start_delta))
                event_end_in[idx] = int(round(end_delta))
                event_attendance[idx] = (
                    int(rel_attend[closest_idx])
                    if not np.isnan(rel_attend[closest_idx])
                    else np.nan
                )

    df["has_nearby_event"] = has_nearby
    df["event_distance_km"] = event_dist
    df["event_start_in_min"] = event_start_in
    df["event_end_in_min"] = event_end_in
    df["expected_attendance"] = event_attendance

    return df


def add_neighbor_features(
    df: pd.DataFrame,
    demand: pd.DataFrame,
    supply: pd.DataFrame,
    travel_times: pd.DataFrame,
) -> pd.DataFrame:
    """Compute spatial neighbor aggregates using zone_travel_times."""
    # Build neighbor map: zone_id -> [(neighbor_zone_id, travel_time), ...]
    nearby = travel_times[
        travel_times["estimated_travel_time_min"] <= NEIGHBOR_TRAVEL_THRESHOLD_MIN
    ].copy()

    # For each source zone, get its set of destination neighbors
    neighbor_map: dict[int, pd.DataFrame] = {}
    for src_zone, grp in nearby.groupby("source_zone_id"):
        neighbor_map[src_zone] = grp[["destination_zone_id", "estimated_travel_time_min"]]

    # Index demand and supply by (timestamp, zone_id) for lookups
    demand_lookup = (
        demand.groupby(["timestamp", "zone_id"])["ride_requests"]
        .sum()
    )
    supply_lookup = (
        supply.groupby(["timestamp", "zone_id"])["available_drivers"]
        .mean()
    )

    n_avg_req = np.full(len(df), np.nan)
    n_avg_drv = np.full(len(df), np.nan)
    n_min_tt = np.full(len(df), np.nan)

    for idx, row in df.iterrows():
        zid = row["zone_id"]
        ts = row["timestamp"]

        if zid not in neighbor_map:
            continue

        nb = neighbor_map[zid]
        nb_zones = nb["destination_zone_id"].values

        # Gather neighbor requests
        req_vals = []
        drv_vals = []
        for nz in nb_zones:
            key = (ts, nz)
            if key in demand_lookup.index:
                req_vals.append(demand_lookup[key])
            if key in supply_lookup.index:
                drv_vals.append(supply_lookup[key])

        if req_vals:
            n_avg_req[idx] = round(np.mean(req_vals), 2)
        if drv_vals:
            n_avg_drv[idx] = round(np.mean(drv_vals), 2)

        n_min_tt[idx] = round(nb["estimated_travel_time_min"].min(), 2)

    df["neighbor_avg_requests"] = n_avg_req
    df["neighbor_available_drivers"] = n_avg_drv
    df["min_travel_time_to_neighbor_min"] = n_min_tt

    return df


def add_target(df: pd.DataFrame, demand: pd.DataFrame) -> pd.DataFrame:
    """Add target_requests – ride_requests from the *next* hour for the zone."""
    next_hour = df[["timestamp", "zone_id"]].copy()
    next_hour["next_ts"] = next_hour["timestamp"] + pd.Timedelta(hours=1)

    next_demand = demand[["timestamp", "zone_id", "ride_requests"]].rename(
        columns={"timestamp": "next_ts", "ride_requests": "target_requests"}
    )
    next_hour = next_hour.merge(next_demand, on=["next_ts", "zone_id"], how="left")

    df["target_requests"] = next_hour["target_requests"]
    return df


# ---------------------------------------------------------------------------
# Table persistence
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
DROP TABLE IF EXISTS feature_dataset;
CREATE TABLE feature_dataset (
    row_id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp                       TIMESTAMP NOT NULL,
    zone_id                         INTEGER NOT NULL,

    -- Time / calendar
    hour                            SMALLINT,
    day_of_week                     SMALLINT,
    is_weekend                      BOOLEAN,
    month                           SMALLINT,
    is_peak_hour                    BOOLEAN,

    -- Recent demand windows
    requests_last_15m               INTEGER,
    requests_last_30m               INTEGER,
    requests_last_60m               INTEGER,
    requests_last_120m              INTEGER,
    requests_same_hour_prev_week    INTEGER,

    -- Demand stats
    avg_trip_duration_min           DECIMAL(8,2),
    avg_pickup_wait_min            DECIMAL(8,2),

    -- Supply
    available_drivers               INTEGER,
    occupied_drivers                INTEGER,
    incoming_drivers                INTEGER,
    expected_departures             INTEGER,

    -- Events
    has_nearby_event                BOOLEAN,
    event_distance_km               DECIMAL(8,2),
    event_start_in_min              INTEGER,
    event_end_in_min                INTEGER,
    expected_attendance             INTEGER,

    -- Spatial / neighbor
    neighbor_avg_requests           DECIMAL(10,2),
    neighbor_available_drivers      DECIMAL(10,2),
    min_travel_time_to_neighbor_min DECIMAL(8,2),

    -- Target
    target_requests                 INTEGER,

    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);
"""


def save_feature_dataset(df: pd.DataFrame, db_path: Path) -> None:
    """Write the feature dataset to SQLite, replacing any existing table."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.executescript(_CREATE_TABLE_SQL)
        conn.commit()

        # Prepare insertion DataFrame (drop row_id so AUTOINCREMENT works)
        insert_df = df.drop(columns=["row_id"], errors="ignore")
        insert_df.to_sql("feature_dataset", conn, if_exists="append", index=False)
        conn.commit()
        print(f"[[OK]] Saved {len(df):,} rows to feature_dataset table.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Validation & summary
# ---------------------------------------------------------------------------

def print_summary(df: pd.DataFrame) -> None:
    """Print summary statistics for the feature dataset."""
    print("\n" + "=" * 72)
    print("FEATURE DATASET SUMMARY")
    print("=" * 72)
    print(f"Total rows          : {len(df):,}")
    print(f"Unique timestamps   : {df['timestamp'].nunique():,}")
    print(f"Unique zones        : {df['zone_id'].nunique():,}")
    print(f"Date range          : {df['timestamp'].min()} -> {df['timestamp'].max()}")

    print("\n--- Non-null counts ---")
    non_null = df.notna().sum()
    for col in df.columns:
        pct = non_null[col] / len(df) * 100 if len(df) > 0 else 0
        print(f"  {col:40s} {non_null[col]:>8,}  ({pct:5.1f}%)")

    print("\n--- Numeric describe ---")
    desc = df.describe().T
    print(desc.to_string())

    print("\n--- Sample rows (first 5) ---")
    print(df.head().to_string(index=False))
    print()


# ---------------------------------------------------------------------------
# Pipeline orchestration
# ---------------------------------------------------------------------------

def build_feature_dataset(db_path: Optional[Path] = None) -> pd.DataFrame:
    """
    End-to-end feature engineering pipeline.

    Parameters
    ----------
    db_path : Path, optional
        Override for the default database path.

    Returns
    -------
    pd.DataFrame
        The completed feature dataset.
    """
    db = db_path or DB_PATH
    print(f"[*] Loading raw tables from {db} ...")
    tables = load_tables(db)

    demand = tables["historical_demand"]
    supply = tables["driver_supply"]
    events = tables["events"]
    zones = tables["zones"]
    travel_times = tables["zone_travel_times"]

    print(f"    demand rows      : {len(demand):,}")
    print(f"    supply rows      : {len(supply):,}")
    print(f"    events rows      : {len(events):,}")
    print(f"    zones rows       : {len(zones):,}")
    print(f"    travel_times rows: {len(travel_times):,}")

    # Step 1 – base grid
    print("[*] Building base (timestamp × zone) grid ...")
    df = build_base_grid(demand, zones)
    print(f"    grid size: {len(df):,} rows")

    # Step 2 – time features
    print("[*] Adding time & calendar features ...")
    df = add_time_features(df)

    # Step 3 – demand features
    print("[*] Adding demand features ...")
    df = add_demand_features(df, demand)

    # Step 4 – supply features
    print("[*] Adding supply features ...")
    df = add_supply_features(df, supply)

    # Step 5 – event features
    print("[*] Adding event-proximity features ...")
    df = add_event_features(df, events, zones)

    # Step 6 – neighbor / spatial features
    print("[*] Adding neighbor / spatial features ...")
    df = add_neighbor_features(df, demand, supply, travel_times)

    # Step 7 – target variable
    print("[*] Adding target variable ...")
    df = add_target(df, demand)

    # Step 8 – persist
    print("[*] Writing feature_dataset to database ...")
    save_feature_dataset(df, db)

    return df


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    feature_df = build_feature_dataset()
    print_summary(feature_df)
    print("[[OK]] Phase 2 complete.")
