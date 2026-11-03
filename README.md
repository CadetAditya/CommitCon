# CommitCon – Driver Repositioning & Fleet Intelligence System

An end-to-end Machine Learning and FastAPI recommendation engine with a complete **Driver Portal Web App** for ride-hailing driver repositioning across 20 city zones.

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
                       (Citywide + Driver-Personalized Gaps)
                                         │
                                         ▼
                      [Phase 5: FastAPI Service + Web App]
            (Driver Login, Citywide Demand View, "Recommended For Me")
```

---

## Features & Capabilities

### 1. Driver Authentication (Frontend + API)
- **Login with Email or Mobile Number** and password.
- Demo driver accounts included for immediate 1-click testing:
  - `aditya@commitcon.com` or `9876543210` (Aditya Singh • Zone `Z06 - Shopping Mall Area`)
  - `rajesh@commitcon.com` or `9876543211` (Rajesh Kumar • Zone `Z13 - Entertainment District`)
  - `vikram@commitcon.com` or `9876543212` (Vikram Sharma • Zone `Z10 - Residential South`)
  - `priya@commitcon.com` or `9876543213` (Priya Patel • Zone `Z20 - IT Corridor South`)
- Also supports any custom phone or email.

### 2. Dashboard: "Overall City Demand"
- Interactive leaderboard of all **20 city zones** ranked by predicted requests (highest demand first).
- Visual demand meters, surge badges (`HIGH DEMAND`, `MODERATE`, `NORMAL`), supply gap indicators, and nearby active event badges.
- Live summary KPIs: Total Predicted City Demand, High Surge Zones, Idle Supply, and Active Events.

### 3. Dashboard: "Recommended Zones for Me"
- Calculates opportunities specifically for the logged-in driver's current zone.
- Filters and ranks target shortage zones based on:
  - **Travel time and distance** from the driver's current position ($\le 25\text{ mins}$).
  - **Demand surge** and **driver shortage gap**.
- One-click **"Accept Reposition & Navigate"** activating live in-app navigation simulation.

---

## How to Run

### 1. Start the Full Service (Backend API + Frontend Web App)
```bash
python phase5_api.py
```
Or via Uvicorn:
```bash
uvicorn phase5_api:app --host 0.0.0.0 --port 8000 --reload
```

* **Driver Portal (Web App)**: Open [http://localhost:8000](http://localhost:8000) in your browser.
* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Run Complete Verification Test Suite
```bash
python test_system.py
```

---

## API Endpoints

### Driver & Portal Endpoints
- `POST /api/login` – Driver authentication via email/phone and password.
- `GET /api/zones` – List all 20 zones with IDs and names.
- `GET /api/recommendations/for-me?zone_id={zone_id}` – Personalized recommendations for an individual driver.
- `POST /api/drivers/accept-reposition` – Dispatches and acknowledges a driver repositioning route.

### Recommendation & Intelligence Endpoints
- `GET /recommendations/latest` – Citywide repositioning recommendations across all 20 zones.
- `GET /recommendations/latest/zone/{zone_id}` – Recommendation for a single zone (e.g. `Z03`).
- `GET /recommendations/latest/action/{action}` – Filter zones by action (`REPOSITION_IN`, `REPOSITION_OUT`, `MONITOR`).
- `GET /recommendations/history` – Summaries of recent recommendation runs.
- `POST /recommendations/refresh` – Manually trigger an immediate recommendation re-calculation.
- `GET /health` – System status and next 15-minute scheduled refresh timestamp.
