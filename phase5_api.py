"""
Phase 5: FastAPI Service for Driver Repositioning Recommendations.

Exposes the recommendation engine via a REST API with automatic periodic
refresh (every 15 minutes), manual refresh, health checks, and historical lookup.
"""

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from phase4_recommend import generate_recommendations

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("commitcon_api")

# ---------------------------------------------------------------------------
# IST helper
# ---------------------------------------------------------------------------
IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# Scheduler (Native background scheduler with APScheduler fallback)
# ---------------------------------------------------------------------------
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    class BackgroundScheduler:
        """Lightweight native background scheduler for periodic tasks."""

        class _Job:
            def __init__(self, func, interval_seconds, job_id):
                self.func = func
                self.interval_seconds = interval_seconds
                self.id = job_id
                self.next_run_time = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)

        def __init__(self):
            self._jobs = {}
            self._running = False
            self._thread = None
            self._lock = threading.Lock()

        def add_job(self, func, trigger="interval", minutes=15, id="periodic_refresh", replace_existing=True):
            interval_seconds = minutes * 60
            job = self._Job(func, interval_seconds, id)
            with self._lock:
                self._jobs[id] = job
            return job

        def get_job(self, job_id):
            with self._lock:
                return self._jobs.get(job_id)

        def start(self):
            if not self._running:
                self._running = True
                self._thread = threading.Thread(target=self._run_loop, daemon=True)
                self._thread.start()

        def _run_loop(self):
            while self._running:
                time.sleep(1)
                now = datetime.now(timezone.utc)
                jobs_to_run = []
                with self._lock:
                    for job in self._jobs.values():
                        if now >= job.next_run_time:
                            job.next_run_time = now + timedelta(seconds=job.interval_seconds)
                            jobs_to_run.append(job)
                for job in jobs_to_run:
                    try:
                        job.func()
                    except Exception as err:
                        logger.error(f"Error executing scheduled job {job.id}: {err}")

        def shutdown(self, wait=False):
            self._running = False


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ZoneRecommendation(BaseModel):
    zone_id: str
    zone_name: str
    predicted_requests: int
    required_drivers: int
    available_drivers: int
    supply_gap: int
    recommended_action: str
    reason_codes: List[str]
    reposition_sources: Optional[List[str]] = None


class RecommendationResponse(BaseModel):
    run_id: str
    generated_at: str
    model_version: str
    total_zones: int
    summary: dict
    zones: List[ZoneRecommendation]


class HealthResponse(BaseModel):
    status: str
    last_refresh: Optional[str]
    next_refresh: Optional[str]
    total_runs: int


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
latest_recommendation: Optional[dict] = None
recommendation_history: list = []  # keep last 10
run_counter: int = 0
HISTORY_MAX = 10

scheduler = BackgroundScheduler()


def refresh_recommendations() -> dict:
    """Generate a new recommendation and update global state."""
    global latest_recommendation, run_counter

    run_counter += 1
    logger.info("Refreshing recommendations (run #%d) ...", run_counter)

    try:
        rec = generate_recommendations()
        latest_recommendation = rec

        # Append to history (keep only last HISTORY_MAX)
        recommendation_history.append(
            {
                "run_id": rec["run_id"],
                "generated_at": rec["generated_at"],
                "summary": rec["summary"],
            }
        )
        if len(recommendation_history) > HISTORY_MAX:
            recommendation_history.pop(0)

        logger.info(
            "Recommendation %s generated - %d zones.",
            rec["run_id"],
            rec["total_zones"],
        )
        return rec
    except Exception:
        logger.exception("Failed to refresh recommendations.")
        raise


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown."""
    logger.info("Starting CommitCon Recommendation API ...")
    try:
        refresh_recommendations()
    except Exception:
        logger.warning("Initial recommendation generation failed - API will serve 404 until next refresh.")

    scheduler.add_job(
        refresh_recommendations,
        "interval",
        minutes=15,
        id="periodic_refresh",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Periodic scheduler started (refreshing every 15 minutes).")
    yield
    logger.info("Shutting down scheduler ...")
    scheduler.shutdown(wait=False)

app = FastAPI(
    title="CommitCon Driver Repositioning API",
    description="Real-time driver repositioning recommendations for ride-hailing operations.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    """Welcome endpoint."""
    return {
        "service": "CommitCon Driver Repositioning API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": [
            "/recommendations/latest",
            "/recommendations/latest/zone/{zone_id}",
            "/recommendations/latest/action/{action}",
            "/recommendations/history",
            "/health",
            "/recommendations/refresh"
        ]
    }


@app.get("/health", response_model=HealthResponse)
def health():
    """Health-check endpoint with refresh metadata."""
    last_refresh = None
    if latest_recommendation:
        last_refresh = latest_recommendation["generated_at"]

    next_refresh = None
    job = scheduler.get_job("periodic_refresh")
    if job and getattr(job, "next_run_time", None):
        next_refresh = job.next_run_time.astimezone(IST).isoformat()

    return HealthResponse(
        status="healthy",
        last_refresh=last_refresh,
        next_refresh=next_refresh,
        total_runs=run_counter,
    )


@app.get("/recommendations/latest", response_model=RecommendationResponse)
def get_latest():
    """Return the most recent recommendation payload for all 20 zones."""
    if latest_recommendation is None:
        raise HTTPException(status_code=404, detail="No recommendations available yet.")
    return latest_recommendation


@app.get(
    "/recommendations/latest/zone/{zone_id}",
    response_model=ZoneRecommendation,
)
def get_zone(zone_id: str):
    """Return the recommendation for a single zone from the latest run.

    Example: ``/recommendations/latest/zone/Z03``
    """
    if latest_recommendation is None:
        raise HTTPException(status_code=404, detail="No recommendations available yet.")

    zone_id_upper = zone_id.upper()
    for zone in latest_recommendation["zones"]:
        if zone["zone_id"].upper() == zone_id_upper:
            return zone

    raise HTTPException(
        status_code=404,
        detail=f"Zone '{zone_id}' not found in the latest recommendation.",
    )


@app.get(
    "/recommendations/latest/action/{action}",
    response_model=List[ZoneRecommendation],
)
def get_by_action(action: str):
    """Filter zones from the latest recommendation by action.

    Valid actions: ``REPOSITION_IN``, ``REPOSITION_OUT``, ``MONITOR``
    """
    if latest_recommendation is None:
        raise HTTPException(status_code=404, detail="No recommendations available yet.")

    valid_actions = {"REPOSITION_IN", "REPOSITION_OUT", "MONITOR"}
    action_upper = action.upper()
    if action_upper not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{action}'. Must be one of {sorted(valid_actions)}.",
        )

    filtered = [
        z for z in latest_recommendation["zones"]
        if z["recommended_action"] == action_upper
    ]
    return filtered


@app.get("/recommendations/history")
def get_history():
    """Return summaries of recent recommendation runs (up to last 10)."""
    return recommendation_history


@app.post("/recommendations/refresh", response_model=RecommendationResponse)
def manual_refresh():
    """Manually trigger a new recommendation run and return the result."""
    try:
        rec = refresh_recommendations()
        return rec
    except Exception as exc:
        logger.exception("Manual refresh failed.")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate recommendations: {exc}",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("phase5_api:app", host="0.0.0.0", port=8000, reload=True)
