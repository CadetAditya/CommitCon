"""Central configuration for the CommitCon recommendation system."""
import os
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "commitcon.db"
MODEL_DIR = PROJECT_ROOT / "models"
LOG_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
for d in [DB_PATH.parent, MODEL_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Zone configuration
NUM_ZONES = 20
ZONE_PREFIX = "Z"

# Time configuration
FORECAST_HORIZON_HOURS = 1  # Predict 1 hour ahead
REFRESH_INTERVAL_MINUTES = 15
HISTORY_DAYS = 30  # 30 days of historical data

# Model configuration
MODEL_PATH = MODEL_DIR / "demand_model.joblib"
FEATURE_COLUMNS = [
    "hour", "day_of_week", "is_weekend", "month", "is_peak_hour",
    "requests_last_15m", "requests_last_30m", "requests_last_60m",
    "requests_last_120m", "requests_same_hour_prev_week",
    "avg_trip_duration_min", "avg_pickup_wait_min",
    "available_drivers", "occupied_drivers", "incoming_drivers",
    "expected_departures",
    "has_nearby_event", "event_distance_km", "event_start_in_min",
    "event_end_in_min", "expected_attendance",
    "neighbor_avg_requests", "neighbor_available_drivers",
    "min_travel_time_to_neighbor_min"
]

# Recommendation thresholds
DRIVERS_PER_REQUEST_RATIO = 0.8  # required_drivers = predicted_requests * ratio
SUPPLY_GAP_THRESHOLD = 2  # Minimum gap to trigger REPOSITION_IN
MAX_REPOSITION_TRAVEL_MIN = 25  # Max travel time for repositioning

# API configuration
API_HOST = "0.0.0.0"
API_PORT = 8000
