# CommitCon – Driver Repositioning Recommendation System

An end-to-end Machine Learning and FastAPI recommendation engine for ride-hailing driver repositioning across 20 city zones.

---

## Architecture Overview

```
                                 [Raw Data Tables]
                         (zones, historical_demand, driver_supply,
                               events, zone_travel_times)
                                         │
                                         ▼
                            [Phase 2: Feature Engineering]
                               (feature_dataset table)
                                         │
                                         ▼
                            [Phase 3: Demand Forecasting]
                               (XGBoost vs Baseline)
                                         │
                                         ▼
                         [Phase 4: Recommendation Engine]
                         (Supply Gap Ranking & Feasibility)
                                         │
                                         ▼
                             [Phase 5: FastAPI Service]
                        (GET /recommendations/latest, 15m cron)
```

---

## Phases & Deliverables

| Phase | Script / Component | Deliverable | Status |
|---|---|---|---|
| **01 Prepare Data** | `phase1_data.py` | 5 raw tables populated with 30 days of data (14,400 records/table) across 20 zones | Verified ✅ |
| **02 Derived Features** | `phase2_features.py` | `feature_dataset` table with 24 temporal, historical, supply, event & spatial features | Verified ✅ |
| **03 Demand Forecasting** | `phase3_forecast.py` | XGBoost model (`models/demand_model.joblib`), evaluated against historical baseline (+38.8% MAE improvement) | Verified ✅ |
| **04 Recommendation Engine** | `phase4_recommend.py` | Ranked zone recommendations with supply gaps, action codes (`REPOSITION_IN`, `REPOSITION_OUT`, `MONITOR`), reason codes, and feasible source zones | Verified ✅ |
| **05 FastAPI Recommendation API** | `phase5_api.py` | High-performance REST API with background scheduler refreshing recommendations every 15 minutes | Verified ✅ |

---

## Quickstart

### 1. Run Complete Validation Suite
```bash
python test_system.py
```

### 2. Run Individual Phases
```bash
# Phase 1: Re-create schema & synthetic data
python phase1_data.py

# Phase 2: Compute model features
python phase2_features.py

# Phase 3: Train & evaluate demand forecasting model
python phase3_forecast.py

# Phase 4: Generate recommendations & output JSON
python phase4_recommend.py
```

### 3. Start the FastAPI Service
```bash
python phase5_api.py
```
Or via Uvicorn directly:
```bash
uvicorn phase5_api:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation available at: `http://localhost:8000/docs`

---

## API Endpoints

- `GET /recommendations/latest` – Returns the latest repositioning recommendation across all 20 zones.
- `GET /recommendations/latest/zone/{zone_id}` – Recommendation for an individual zone (e.g. `Z03`).
- `GET /recommendations/latest/action/{action}` – Filter zones by action (`REPOSITION_IN`, `REPOSITION_OUT`, `MONITOR`).
- `GET /recommendations/history` – Summaries of recent recommendation runs.
- `POST /recommendations/refresh` – Manually trigger an immediate recommendation re-calculation.
- `GET /health` – System status, run count, and next scheduled refresh timestamp.

