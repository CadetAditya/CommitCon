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

### 4. Sherpa AI Copilot (GPU Driver Chatbot)
- Fine-tuned inference assistant powered by `project-driver:latest`.
- Provides contextual reasoning on demand forecasts, traffic bottlenecks, and earnings opportunities.
- Accessible via the **🧭 Sherpa** tab and top header pill.

---

## Deployment (Render.com)

This repository includes a production-ready `render.yaml` Blueprint and `Dockerfile`.

### 1-Click Deployment via Render:
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** > **Blueprint**.
3. Connect your GitHub account and select repository: `https://github.com/CadetAditya/CommitCon.git`.
4. Render automatically reads `render.yaml`, configures Python 3.11, installs `requirements.txt`, sets environment variables, and launches the service.
5. Your app will be live at `https://commitcon-driver-portal.onrender.com`!

### Manual Web Service Configuration on Render:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn phase5_api:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**:
  - `AI_INFERENCE_URL`: `https://win-s6b0cl04s86.tailf0b46c.ts.net/chat`
  - `AI_INFERENCE_KEY`: `commitcon-secret-2026`

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
- `GET /api/analysis/earnings` – Counterfactual ROI analysis comparing driver earnings with vs. without CommitCon over 30 days.
- `POST /api/chat` – Sherpa AI driver chatbot powered by remote GPU inference (`project-driver:latest`).

### Recommendation & Intelligence Endpoints
- `GET /recommendations/latest` – Citywide repositioning recommendations across all 20 zones.
- `GET /recommendations/latest/zone/{zone_id}` – Recommendation for a single zone (e.g. `Z03`).
- `GET /recommendations/latest/action/{action}` – Filter zones by action (`REPOSITION_IN`, `REPOSITION_OUT`, `MONITOR`).
- `GET /recommendations/history` – Summaries of recent recommendation runs.
- `POST /recommendations/refresh` – Manually trigger an immediate recommendation re-calculation.
- `GET /health` – System status and next 15-minute scheduled refresh timestamp.

---

## 📊 Driver Financial Impact & Counterfactual ROI (30-Day Historical Study)

| Performance Metric | Without Model (Reactive) | With CommitCon (Proactive) | Net Driver Benefit |
| :--- | :---: | :---: | :---: |
| **8-Hour Shift Earnings (Take-Home)** | ₹2,634 | **₹4,896** | **+₹2,262 / shift (+85.9%)** |
| **Monthly Income (25 Shifts)** | ₹65,850 | **₹122,400** | **+₹56,550 / month** |
| **Completed Trips per Shift** | 9.2 trips | **15.1 trips** | **+5.9 rides / shift (+64%)** |
| **Average Unpaid Idle Wait Time** | 28.5 min/hr | **10.4 min/hr** | **-18.1 min (-63.5% wait time reduction)** |
| **Surge Pricing Capture Rate** | 18.2% | **64.8%** | **3.5× higher surge probability** |

*Note: Repositioning fuel expenditure (~₹12/hr, 3.5 km @ ₹4.50/km) is explicitly deducted from all reported net earnings.*
