"""
test_system.py - End-to-End Verification of Phases 1 to 5 + Driver Frontend API.
"""

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import sqlite3
import json
from pathlib import Path
import pandas as pd
import numpy as np

def run_all_tests():
    print("=" * 70)
    print("COMMITCON DRIVER REPOSITIONING SYSTEM - END-TO-END VALIDATION")
    print("=" * 70)

    base_dir = Path(__file__).parent
    db_path = base_dir / "data" / "commitcon.db"
    model_path = base_dir / "models" / "demand_model.joblib"
    features_path = base_dir / "models" / "feature_columns.json"

    # -------------------------------------------------------------
    # Test 1: Phase 1 Data Validation
    # -------------------------------------------------------------
    print("\n[PHASE 1] Validating Raw Database Schema & Data ...")
    assert db_path.exists(), f"Database not found at {db_path}"
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"  Existing tables in DB: {tables}")
    for required in ["zones", "historical_demand", "driver_supply", "events", "zone_travel_times"]:
        assert required in tables, f"Missing table: {required}"

    zone_count = cursor.execute("SELECT count(*) FROM zones").fetchone()[0]
    demand_count = cursor.execute("SELECT count(*) FROM historical_demand").fetchone()[0]
    supply_count = cursor.execute("SELECT count(*) FROM driver_supply").fetchone()[0]
    event_count = cursor.execute("SELECT count(*) FROM events").fetchone()[0]
    tt_count = cursor.execute("SELECT count(*) FROM zone_travel_times").fetchone()[0]

    print(f"  zones: {zone_count} rows (expected 20)")
    print(f"  historical_demand: {demand_count} rows (expected 14,400)")
    print(f"  driver_supply: {supply_count} rows (expected 14,400)")
    print(f"  events: {event_count} rows")
    print(f"  zone_travel_times: {tt_count} rows (expected 380)")

    assert zone_count == 20
    assert demand_count == 14400
    assert supply_count == 14400
    assert tt_count == 380
    print("  [OK] Phase 1 Validated!")

    # -------------------------------------------------------------
    # Test 2: Phase 2 Feature Engineering Validation
    # -------------------------------------------------------------
    print("\n[PHASE 2] Validating Feature Dataset ...")
    assert "feature_dataset" in tables, "feature_dataset table missing in DB"
    
    f_count = cursor.execute("SELECT count(*) FROM feature_dataset").fetchone()[0]
    cols = [col[1] for col in cursor.execute("PRAGMA table_info(feature_dataset)").fetchall()]
    print(f"  feature_dataset: {f_count} rows, {len(cols)} columns")
    assert f_count == 14400, f"Expected 14400 rows, got {f_count}"
    
    required_features = [
        "hour", "day_of_week", "is_weekend", "month", "is_peak_hour",
        "requests_last_15m", "requests_last_30m", "requests_last_60m", "requests_last_120m",
        "requests_same_hour_prev_week", "avg_trip_duration_min", "avg_pickup_wait_min",
        "available_drivers", "occupied_drivers", "incoming_drivers", "expected_departures",
        "has_nearby_event", "event_distance_km", "event_start_in_min", "event_end_in_min",
        "expected_attendance", "neighbor_avg_requests", "neighbor_available_drivers",
        "min_travel_time_to_neighbor_min", "target_requests"
    ]
    for col in required_features:
        assert col in cols, f"Missing feature column: {col}"
    print("  [OK] Phase 2 Validated!")

    # -------------------------------------------------------------
    # Test 3: Phase 3 Forecast Model Validation
    # -------------------------------------------------------------
    print("\n[PHASE 3] Validating Demand Forecasting Model ...")
    assert model_path.exists(), f"Model file not found at {model_path}"
    assert features_path.exists(), f"Feature columns file not found at {features_path}"
    
    import joblib
    model = joblib.load(model_path)
    with open(features_path, "r") as f:
        feature_cols = json.load(f)
    print(f"  Loaded model: {type(model).__name__}")
    print(f"  Feature columns ({len(feature_cols)}): {feature_cols[:5]} ...")
    
    # Test dummy prediction
    sample_row = pd.read_sql("SELECT * FROM feature_dataset LIMIT 5", conn)
    from phase3_forecast import predict_demand
    preds = predict_demand(model, sample_row)
    print(f"  Test predictions on 5 sample rows: {preds.tolist()}")
    assert len(preds) == 5
    assert all(p >= 0 for p in preds)
    print("  [OK] Phase 3 Validated!")

    conn.close()

    # -------------------------------------------------------------
    # Test 4: Phase 4 Recommendation Engine Validation
    # -------------------------------------------------------------
    print("\n[PHASE 4] Validating Recommendation Engine ...")
    from phase4_recommend import generate_recommendations, get_driver_personalized_recommendations
    rec = generate_recommendations()
    print(f"  Run ID: {rec['run_id']}")
    print(f"  Generated at: {rec['generated_at']}")
    print(f"  Total zones: {rec['total_zones']}")
    print(f"  Summary: {rec['summary']}")
    assert rec["total_zones"] == 20
    assert len(rec["zones"]) == 20
    
    # Check zone structure
    z0 = rec["zones"][0]
    print(f"  Top recommended zone: {json.dumps(z0, indent=4)}")
    for key in ["zone_id", "predicted_requests", "required_drivers", "available_drivers", "supply_gap", "recommended_action", "reason_codes"]:
        assert key in z0, f"Missing key in zone payload: {key}"
        
    # Check sorting by supply_gap descending
    gaps = [z["supply_gap"] for z in rec["zones"]]
    assert gaps == sorted(gaps, reverse=True), "Zones must be sorted by supply_gap descending"

    # Test personalized driver recommendations
    personal = get_driver_personalized_recommendations("Z06", max_results=3)
    assert "driver_current_zone" in personal
    assert len(personal["recommendations"]) > 0
    print(f"  [OK] Personalized Recommendations for Z06 verified: {len(personal['recommendations'])} targets returned")
    print("  [OK] Phase 4 Validated!")

    # -------------------------------------------------------------
    # Test 5: Phase 5 API & Driver Portal Validation
    # -------------------------------------------------------------
    print("\n[PHASE 5] Validating FastAPI Service & Driver Endpoints ...")
    import phase5_api
    from phase5_api import LoginRequest, AcceptRepositionRequest
    
    # Trigger refresh
    refreshed = phase5_api.refresh_recommendations()
    assert refreshed["total_zones"] == 20
    
    # Root
    root_data = phase5_api.root()
    assert "service" in root_data
    print("  GET /api -> OK")

    # Driver Login (Email)
    login_email = phase5_api.login(LoginRequest(username_or_email="aditya@commitcon.com", password="password123"))
    assert login_email.success is True
    assert login_email.driver.name == "Aditya Singh"
    print(f"  POST /api/login (email) -> OK ({login_email.driver.name}, zone={login_email.driver.current_zone_id})")

    # Driver Login (Phone)
    login_phone = phase5_api.login(LoginRequest(username_or_email="9876543211", password="password123"))
    assert login_phone.success is True
    assert login_phone.driver.name == "Rajesh Kumar"
    print(f"  POST /api/login (phone) -> OK ({login_phone.driver.name})")

    # List zones
    all_zones = phase5_api.list_zones()
    assert len(all_zones) == 20
    print(f"  GET /api/zones -> OK ({len(all_zones)} zones)")

    # Driver Personalized Recommendations ("Recommended zones for me")
    for_me = phase5_api.get_personal_recommendations(zone_id="Z06")
    assert len(for_me["recommendations"]) > 0
    print(f"  GET /api/recommendations/for-me -> OK (from {for_me['driver_current_zone']['zone_id']}: {len(for_me['recommendations'])} zones)")

    # Accept reposition
    accept_ack = phase5_api.accept_reposition(AcceptRepositionRequest(driver_id="DRV_101", destination_zone_id="Z07"))
    assert accept_ack["status"] == "ACCEPTED"
    print(f"  POST /api/drivers/accept-reposition -> OK ({accept_ack['message']})")
    
    # Health
    health_data = phase5_api.health()
    assert health_data.status == "healthy"
    print(f"  GET /health -> OK (status={health_data.status}, total_runs={health_data.total_runs})")
    
    # Latest
    latest_data = phase5_api.get_latest()
    assert latest_data["total_zones"] == 20
    print(f"  GET /recommendations/latest -> OK (zones={len(latest_data['zones'])})")
    
    # Zone specific
    sample_zid = latest_data["zones"][0]["zone_id"]
    zone_data = phase5_api.get_zone(sample_zid)
    assert zone_data["zone_id"] == sample_zid
    print(f"  GET /recommendations/latest/zone/{sample_zid} -> OK (zone_name={zone_data['zone_name']})")
    
    # Action specific
    in_zones = phase5_api.get_by_action("REPOSITION_IN")
    print(f"  GET /recommendations/latest/action/REPOSITION_IN -> OK ({len(in_zones)} zones)")
    for z in in_zones:
        assert z["recommended_action"] == "REPOSITION_IN"
        
    # History
    history_data = phase5_api.get_history()
    print(f"  GET /recommendations/history -> OK ({len(history_data)} entries recorded)")
    assert len(history_data) >= 1
    
    # Manual refresh
    manual_data = phase5_api.manual_refresh()
    assert manual_data["total_zones"] == 20
    print("  POST /recommendations/refresh -> OK")

    # Chatbot / Copilot integration
    import asyncio
    chat_req = phase5_api.DriverChatRequest(
        driver_id="DRV_101",
        driver_prompt="Where should I go to get more rides right now?",
        current_zone_id="Z06"
    )
    chat_resp = asyncio.run(phase5_api.driver_copilot_chat(chat_req))
    assert chat_resp.status in ("success", "fallback")
    assert len(chat_resp.answer) > 10
    print(f"  POST /api/chat -> OK (model={chat_resp.model}, status={chat_resp.status})")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! BACKEND & FRONTEND READY FOR DRIVERS!")
    print("=" * 70)

if __name__ == "__main__":
    run_all_tests()
