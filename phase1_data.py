#!/usr/bin/env python3
"""
phase1_data.py - Database Schema & Synthetic Data Generator
===========================================================
Creates the SQLite schema and populates it with realistic synthetic data
for a ride-hailing recommendation system modeled on a large Indian city.

Tables: zones, historical_demand, driver_supply, events, zone_travel_times

Usage:
    python phase1_data.py
"""

import sqlite3
import random
import datetime
import math
import os
import sys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED = 42
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "commitcon.db")

START_DATE = datetime.datetime(2026, 10, 5, 0, 0, 0)
END_DATE = datetime.datetime(2026, 11, 3, 23, 0, 0)  # inclusive last hour
NUM_DAYS = 30
SOURCE_TAG = "synthetic_generator_v1"

# ---------------------------------------------------------------------------
# Zone definitions  (modelled after Bangalore / Mumbai style areas)
# ---------------------------------------------------------------------------
ZONE_DEFS = [
    # (name, lat, lon, area_sq_km, profile_tag)
    ("Downtown",              12.9716,  77.5946,  8.5,  "downtown"),
    ("Airport",               13.1989,  77.7068, 15.0,  "airport"),
    ("Tech Park East",        12.9352,  77.6245,  6.2,  "tech_park"),
    ("Tech Park South",       12.9081,  77.6476,  5.8,  "tech_park"),
    ("University District",   12.9340,  77.5855,  4.5,  "university"),
    ("Shopping Mall Area",    12.9783,  77.5720,  3.9,  "shopping"),
    ("Railway Station",       12.9772,  77.5713,  2.1,  "railway"),
    ("Hospital District",     12.9563,  77.5857,  3.3,  "hospital"),
    ("Residential North",     13.0358,  77.5970,  9.0,  "residential"),
    ("Residential South",     12.8900,  77.5840,  8.7,  "residential"),
    ("Residential East",      12.9600,  77.6500,  7.5,  "residential"),
    ("Industrial Zone",       13.0700,  77.5200, 12.0,  "industrial"),
    ("Entertainment District",12.9700,  77.6100,  4.0,  "entertainment"),
    ("Government Quarter",    12.9800,  77.5900,  3.5,  "government"),
    ("Old City Market",       12.9660,  77.5750,  2.8,  "market"),
    ("Lake Garden Area",      12.9400,  77.6000,  5.0,  "park"),
    ("Convention Center",     12.9550,  77.6350,  3.0,  "convention"),
    ("Highway Corridor",      13.0200,  77.6400, 10.5,  "highway"),
    ("Suburban West",         12.9500,  77.5200, 11.0,  "residential"),
    ("IT Corridor South",     12.8700,  77.6600,  7.0,  "tech_park"),
]

# Hourly base-demand multipliers by profile (index 0–23 = hour of day)
# Values are *multipliers* applied to a zone's base demand.
HOURLY_PROFILES = {
    "downtown": [
        0.15, 0.10, 0.08, 0.08, 0.10, 0.20, 0.40, 0.70,
        1.00, 0.95, 0.80, 0.75, 0.85, 0.80, 0.75, 0.80,
        0.95, 1.00, 0.90, 0.75, 0.60, 0.45, 0.30, 0.20,
    ],
    "airport": [
        0.55, 0.50, 0.45, 0.50, 0.65, 0.85, 1.00, 0.90,
        0.80, 0.70, 0.60, 0.55, 0.50, 0.55, 0.60, 0.65,
        0.70, 0.75, 0.80, 0.85, 0.90, 0.80, 0.70, 0.60,
    ],
    "tech_park": [
        0.05, 0.03, 0.03, 0.03, 0.05, 0.15, 0.35, 0.70,
        1.00, 0.95, 0.60, 0.50, 0.55, 0.60, 0.55, 0.60,
        0.75, 1.00, 0.90, 0.50, 0.25, 0.15, 0.08, 0.05,
    ],
    "university": [
        0.05, 0.03, 0.03, 0.03, 0.05, 0.10, 0.25, 0.55,
        0.85, 1.00, 0.70, 0.60, 0.65, 0.70, 0.65, 0.70,
        0.80, 0.75, 0.55, 0.40, 0.25, 0.15, 0.10, 0.05,
    ],
    "shopping": [
        0.05, 0.03, 0.03, 0.03, 0.05, 0.08, 0.15, 0.25,
        0.40, 0.55, 0.70, 0.85, 1.00, 0.95, 0.90, 0.95,
        1.00, 0.95, 0.85, 0.70, 0.50, 0.35, 0.20, 0.10,
    ],
    "railway": [
        0.30, 0.25, 0.20, 0.20, 0.30, 0.55, 0.80, 1.00,
        0.95, 0.75, 0.55, 0.50, 0.55, 0.60, 0.65, 0.75,
        0.85, 1.00, 0.90, 0.70, 0.55, 0.45, 0.40, 0.35,
    ],
    "hospital": [
        0.25, 0.20, 0.20, 0.20, 0.25, 0.35, 0.50, 0.70,
        0.90, 1.00, 0.90, 0.80, 0.75, 0.80, 0.85, 0.80,
        0.75, 0.70, 0.55, 0.45, 0.35, 0.30, 0.28, 0.25,
    ],
    "residential": [
        0.10, 0.08, 0.05, 0.05, 0.08, 0.20, 0.50, 0.85,
        1.00, 0.80, 0.50, 0.40, 0.40, 0.45, 0.45, 0.55,
        0.70, 0.90, 1.00, 0.75, 0.50, 0.35, 0.20, 0.12,
    ],
    "industrial": [
        0.05, 0.03, 0.03, 0.03, 0.05, 0.15, 0.40, 0.75,
        1.00, 0.85, 0.65, 0.55, 0.55, 0.60, 0.60, 0.65,
        0.80, 0.90, 0.50, 0.25, 0.12, 0.08, 0.05, 0.03,
    ],
    "entertainment": [
        0.08, 0.10, 0.08, 0.05, 0.03, 0.05, 0.08, 0.15,
        0.25, 0.30, 0.35, 0.45, 0.55, 0.60, 0.60, 0.65,
        0.75, 0.85, 1.00, 1.00, 0.95, 0.85, 0.55, 0.25,
    ],
    "government": [
        0.05, 0.03, 0.03, 0.03, 0.05, 0.10, 0.25, 0.55,
        0.80, 1.00, 0.90, 0.75, 0.70, 0.75, 0.80, 0.85,
        0.90, 0.70, 0.40, 0.25, 0.15, 0.10, 0.08, 0.05,
    ],
    "market": [
        0.08, 0.05, 0.05, 0.05, 0.08, 0.15, 0.35, 0.60,
        0.80, 0.90, 1.00, 1.00, 0.95, 0.90, 0.85, 0.80,
        0.75, 0.65, 0.50, 0.35, 0.25, 0.18, 0.12, 0.08,
    ],
    "park": [
        0.03, 0.03, 0.03, 0.03, 0.05, 0.15, 0.35, 0.55,
        0.65, 0.70, 0.75, 0.80, 0.80, 0.75, 0.70, 0.75,
        0.85, 0.90, 1.00, 0.80, 0.55, 0.30, 0.15, 0.05,
    ],
    "convention": [
        0.03, 0.03, 0.03, 0.03, 0.05, 0.10, 0.20, 0.45,
        0.75, 1.00, 0.85, 0.70, 0.75, 0.80, 0.80, 0.75,
        0.85, 1.00, 0.70, 0.40, 0.25, 0.15, 0.08, 0.05,
    ],
    "highway": [
        0.15, 0.12, 0.10, 0.10, 0.15, 0.30, 0.55, 0.80,
        1.00, 0.85, 0.65, 0.55, 0.55, 0.60, 0.60, 0.70,
        0.85, 1.00, 0.80, 0.55, 0.35, 0.25, 0.20, 0.15,
    ],
}

# Per-zone peak demand (rides/hour at multiplier=1.0)
ZONE_PEAK_DEMAND = {
    "Downtown":              50,
    "Airport":               45,
    "Tech Park East":        40,
    "Tech Park South":       38,
    "University District":   28,
    "Shopping Mall Area":    35,
    "Railway Station":       42,
    "Hospital District":     25,
    "Residential North":     30,
    "Residential South":     28,
    "Residential East":      26,
    "Industrial Zone":       20,
    "Entertainment District":38,
    "Government Quarter":    22,
    "Old City Market":       32,
    "Lake Garden Area":      18,
    "Convention Center":     30,
    "Highway Corridor":      24,
    "Suburban West":         22,
    "IT Corridor South":     36,
}

# Event templates
EVENT_TEMPLATES = [
    ("IPL Cricket Match",           "SPORTS",      3, 13000),
    ("Sunburn Music Festival",      "CONCERT",     5, 8000),
    ("Bengaluru Tech Summit",       "CONFERENCE",  8, 5000),
    ("Diwali Mela",                 "FESTIVAL",    6, 15000),
    ("Stand-Up Comedy Night",       "ENTERTAINMENT",2, 800),
    ("Marathon 10K Run",            "SPORTS",      4, 6000),
    ("Food & Wine Expo",            "EXHIBITION",  6, 4000),
    ("Startup Demo Day",            "CONFERENCE",  3, 1200),
    ("Classical Music Concert",     "CONCERT",     3, 2500),
    ("Auto Expo",                   "EXHIBITION",  8, 9000),
    ("College Fest",                "FESTIVAL",    10, 3500),
    ("Badminton Open",              "SPORTS",      5, 3000),
    ("Film Premiere",               "ENTERTAINMENT",2, 1500),
    ("Art & Craft Fair",            "EXHIBITION",  6, 2000),
    ("Jazz Night",                  "CONCERT",     3, 1000),
    ("Hackathon",                   "CONFERENCE",  12, 1500),
    ("Charity Gala",                "ENTERTAINMENT",4, 900),
    ("Book Fair",                   "EXHIBITION",  8, 5500),
    ("Night Market",                "FESTIVAL",    5, 4000),
    ("E-Sports Tournament",        "SPORTS",      6, 2500),
    ("Yoga & Wellness Camp",        "FESTIVAL",    4, 1800),
    ("Rock Band Live",              "CONCERT",     3, 6000),
    ("Data Science Conference",     "CONFERENCE",  8, 2200),
    ("Street Food Festival",        "FESTIVAL",    5, 7000),
    ("Pro Kabaddi League",          "SPORTS",      3, 8000),
    ("Photography Workshop",        "CONFERENCE",  3, 400),
    ("Bollywood Night",             "ENTERTAINMENT",3, 3500),
    ("Farmers Market",              "EXHIBITION",  5, 1500),
    ("Cycling Tour",                "SPORTS",      6, 2000),
    ("Comedy Carnival",             "ENTERTAINMENT",3, 1200),
]


# ======================================================================== #
#  DDL – Schema creation
# ======================================================================== #

DDL_STATEMENTS = [
    # --- zones ---
    """
    CREATE TABLE IF NOT EXISTS zones (
        zone_id           INTEGER PRIMARY KEY AUTOINCREMENT,
        zone_name         VARCHAR(100) NOT NULL UNIQUE,
        center_latitude   DECIMAL(10,7) NOT NULL,
        center_longitude  DECIMAL(10,7) NOT NULL,
        area_sq_km        DECIMAL(10,2),
        is_active         BOOLEAN NOT NULL DEFAULT 1,
        created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # --- historical_demand ---
    """
    CREATE TABLE IF NOT EXISTS historical_demand (
        record_id            INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp            TIMESTAMP NOT NULL,
        zone_id              INTEGER NOT NULL,
        ride_requests        INTEGER NOT NULL DEFAULT 0,
        completed_rides      INTEGER NOT NULL DEFAULT 0,
        cancelled_rides      INTEGER NOT NULL DEFAULT 0,
        unserved_requests    INTEGER CHECK(unserved_requests >= 0),
        avg_trip_duration_min DECIMAL(8,2),
        avg_pickup_wait_min  DECIMAL(8,2),
        source               VARCHAR(100),
        ingested_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
        UNIQUE(timestamp, zone_id, source)
    );
    """,

    # --- driver_supply ---
    """
    CREATE TABLE IF NOT EXISTS driver_supply (
        snapshot_id         INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp           TIMESTAMP NOT NULL,
        zone_id             INTEGER NOT NULL,
        available_drivers   INTEGER NOT NULL DEFAULT 0,
        occupied_drivers    INTEGER NOT NULL DEFAULT 0,
        incoming_drivers    INTEGER NOT NULL DEFAULT 0,
        expected_departures INTEGER NOT NULL DEFAULT 0,
        source              VARCHAR(100),
        ingested_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
        UNIQUE(timestamp, zone_id, source)
    );
    """,

    # --- events ---
    """
    CREATE TABLE IF NOT EXISTS events (
        event_id             INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name           VARCHAR(200) NOT NULL,
        event_type           VARCHAR(100) NOT NULL,
        latitude             DECIMAL(10,7) NOT NULL,
        longitude            DECIMAL(10,7) NOT NULL,
        start_time           TIMESTAMP NOT NULL,
        end_time             TIMESTAMP NOT NULL,
        expected_attendance  INTEGER CHECK(expected_attendance >= 0),
        event_status         VARCHAR(30) NOT NULL
                             CHECK(event_status IN ('SCHEDULED','CONFIRMED','CANCELLED','COMPLETED')),
        source               VARCHAR(200),
        updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CHECK(end_time > start_time)
    );
    """,

    # --- zone_travel_times ---
    """
    CREATE TABLE IF NOT EXISTS zone_travel_times (
        travel_time_id            INTEGER PRIMARY KEY AUTOINCREMENT,
        source_zone_id            INTEGER NOT NULL,
        destination_zone_id       INTEGER NOT NULL,
        estimated_travel_time_min DECIMAL(8,2) NOT NULL CHECK(estimated_travel_time_min >= 0),
        distance_km               DECIMAL(8,2) NOT NULL CHECK(distance_km >= 0),
        observed_at               TIMESTAMP NOT NULL,
        source                    VARCHAR(100),
        FOREIGN KEY (source_zone_id)      REFERENCES zones(zone_id),
        FOREIGN KEY (destination_zone_id) REFERENCES zones(zone_id),
        UNIQUE(source_zone_id, destination_zone_id, observed_at)
    );
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_demand_zone_ts     ON historical_demand (zone_id, timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_supply_zone_ts     ON driver_supply (zone_id, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_events_time_range  ON events (start_time, end_time);",
    "CREATE INDEX IF NOT EXISTS idx_travel_src_dst     ON zone_travel_times (source_zone_id, destination_zone_id);",
]


# ======================================================================== #
#  Helper utilities
# ======================================================================== #

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points (in km)."""
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _is_weekend(dt: datetime.datetime) -> bool:
    return dt.weekday() >= 5  # Saturday=5, Sunday=6


# ======================================================================== #
#  Schema creation
# ======================================================================== #

def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes."""
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    for ddl in DDL_STATEMENTS:
        cur.execute(ddl)
    for idx in INDEX_STATEMENTS:
        cur.execute(idx)
    conn.commit()
    print("[OK] Schema created (5 tables + 4 indexes)")


# ======================================================================== #
#  Data generators
# ======================================================================== #

def generate_zones(conn: sqlite3.Connection) -> list[dict]:
    """Insert zone rows and return a list of zone dicts."""
    cur = conn.cursor()
    zones = []
    for name, lat, lon, area, profile in ZONE_DEFS:
        cur.execute(
            "INSERT INTO zones (zone_name, center_latitude, center_longitude, area_sq_km) "
            "VALUES (?, ?, ?, ?);",
            (name, lat, lon, area),
        )
        zone_id = cur.lastrowid
        zones.append({
            "zone_id": zone_id,
            "name": name,
            "lat": lat,
            "lon": lon,
            "area": area,
            "profile": profile,
        })
    conn.commit()
    print(f"[OK] Inserted {len(zones)} zones")
    return zones


def generate_historical_demand(conn: sqlite3.Connection, zones: list[dict]) -> int:
    """Generate hourly demand records for every zone over the 30-day window."""
    cur = conn.cursor()
    rows_inserted = 0
    batch: list[tuple] = []

    for zone in zones:
        profile = HOURLY_PROFILES[zone["profile"]]
        peak = ZONE_PEAK_DEMAND[zone["name"]]
        ts = START_DATE

        while ts <= END_DATE:
            hour = ts.hour
            multiplier = profile[hour]

            # Weekend adjustments
            if _is_weekend(ts):
                if zone["profile"] in ("tech_park", "government", "industrial"):
                    multiplier *= 0.3
                elif zone["profile"] in ("entertainment", "shopping", "park", "market"):
                    multiplier *= 1.4
                else:
                    multiplier *= 0.85

            base = peak * multiplier
            # Add some daily noise
            noise = random.uniform(0.80, 1.20)
            ride_requests = max(5, min(50, int(round(base * noise))))

            completion_rate = random.uniform(0.70, 0.95)
            completed_rides = max(0, int(round(ride_requests * completion_rate)))

            unserved_rate = random.uniform(0.01, 0.10)
            unserved_requests = max(0, int(round(ride_requests * unserved_rate)))

            cancelled_rides = max(0, ride_requests - completed_rides - unserved_requests)

            avg_trip_min = round(random.uniform(8.0, 35.0), 2)
            # Wait times are higher during peak hours
            base_wait = 3.0 + 12.0 * (1 - completion_rate)
            avg_wait_min = round(min(15.0, max(3.0, base_wait + random.uniform(-1.5, 1.5))), 2)

            batch.append((
                ts.strftime("%Y-%m-%d %H:%M:%S"),
                zone["zone_id"],
                ride_requests,
                completed_rides,
                cancelled_rides,
                unserved_requests,
                avg_trip_min,
                avg_wait_min,
                SOURCE_TAG,
            ))
            rows_inserted += 1
            ts += datetime.timedelta(hours=1)

    cur.executemany(
        "INSERT INTO historical_demand "
        "(timestamp, zone_id, ride_requests, completed_rides, cancelled_rides, "
        "unserved_requests, avg_trip_duration_min, avg_pickup_wait_min, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
        batch,
    )
    conn.commit()
    print(f"[OK] Inserted {rows_inserted:,} historical_demand rows")
    return rows_inserted


def generate_driver_supply(conn: sqlite3.Connection, zones: list[dict]) -> int:
    """Generate hourly driver supply snapshots, loosely correlated with demand."""
    cur = conn.cursor()
    rows_inserted = 0
    batch: list[tuple] = []

    for zone in zones:
        profile = HOURLY_PROFILES[zone["profile"]]
        peak = ZONE_PEAK_DEMAND[zone["name"]]
        ts = START_DATE

        while ts <= END_DATE:
            hour = ts.hour
            multiplier = profile[hour]

            if _is_weekend(ts):
                if zone["profile"] in ("tech_park", "government", "industrial"):
                    multiplier *= 0.3
                elif zone["profile"] in ("entertainment", "shopping", "park", "market"):
                    multiplier *= 1.4
                else:
                    multiplier *= 0.85

            demand_est = peak * multiplier
            noise = random.uniform(0.80, 1.20)
            ride_requests = max(5, min(50, int(round(demand_est * noise))))

            # Available drivers: loosely correlated, sometimes undersupplied
            supply_ratio = random.uniform(0.5, 1.3)
            # Intentional gaps for some zones during certain hours
            if zone["profile"] in ("airport", "entertainment") and 22 <= hour or hour <= 4:
                supply_ratio *= 0.5  # scarce late night
            if zone["profile"] == "industrial" and _is_weekend(ts):
                supply_ratio *= 0.3

            available_drivers = max(0, int(round(ride_requests * supply_ratio * 0.4)))

            completion_rate = random.uniform(0.70, 0.95)
            occupied_drivers = max(0, int(round(ride_requests * completion_rate * 0.6)))

            incoming_drivers = random.randint(0, 8)
            expected_departures = random.randint(0, 5)

            batch.append((
                ts.strftime("%Y-%m-%d %H:%M:%S"),
                zone["zone_id"],
                available_drivers,
                occupied_drivers,
                incoming_drivers,
                expected_departures,
                SOURCE_TAG,
            ))
            rows_inserted += 1
            ts += datetime.timedelta(hours=1)

    cur.executemany(
        "INSERT INTO driver_supply "
        "(timestamp, zone_id, available_drivers, occupied_drivers, "
        "incoming_drivers, expected_departures, source) "
        "VALUES (?, ?, ?, ?, ?, ?, ?);",
        batch,
    )
    conn.commit()
    print(f"[OK] Inserted {rows_inserted:,} driver_supply rows")
    return rows_inserted


def generate_events(conn: sqlite3.Connection, zones: list[dict]) -> int:
    """Generate 40-60 events spread across the 30-day window."""
    cur = conn.cursor()
    num_events = random.randint(40, 60)
    rows_inserted = 0

    # Preferred zones for events
    event_zones = [z for z in zones if z["profile"] in
                   ("entertainment", "convention", "downtown", "park",
                    "shopping", "university", "market")]
    if not event_zones:
        event_zones = zones  # fallback

    for i in range(num_events):
        template = random.choice(EVENT_TEMPLATES)
        event_name_base, event_type, duration_hours, attendance_base = template

        # Pick a random zone
        zone = random.choice(event_zones)

        # Random day within the 30-day window
        day_offset = random.randint(0, NUM_DAYS - 1)
        # Events typically start between 8 AM and 9 PM
        start_hour = random.randint(8, 21)
        start_time = START_DATE + datetime.timedelta(days=day_offset, hours=start_hour)
        end_time = start_time + datetime.timedelta(hours=duration_hours)

        # Jitter attendance
        attendance = max(100, int(attendance_base * random.uniform(0.6, 1.4)))

        # Jitter location slightly from zone center
        lat = zone["lat"] + random.uniform(-0.005, 0.005)
        lon = zone["lon"] + random.uniform(-0.005, 0.005)

        # Status distribution: ~55% CONFIRMED, ~20% COMPLETED, ~15% SCHEDULED, ~10% CANCELLED
        r = random.random()
        if r < 0.55:
            status = "CONFIRMED"
        elif r < 0.75:
            status = "COMPLETED"
        elif r < 0.90:
            status = "SCHEDULED"
        else:
            status = "CANCELLED"

        # Unique-ify name if needed
        event_name = f"{event_name_base} #{i + 1}"

        cur.execute(
            "INSERT INTO events "
            "(event_name, event_type, latitude, longitude, start_time, end_time, "
            "expected_attendance, event_status, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
            (
                event_name,
                event_type,
                round(lat, 7),
                round(lon, 7),
                start_time.strftime("%Y-%m-%d %H:%M:%S"),
                end_time.strftime("%Y-%m-%d %H:%M:%S"),
                attendance,
                status,
                SOURCE_TAG,
            ),
        )
        rows_inserted += 1

    conn.commit()
    print(f"[OK] Inserted {rows_inserted} events")
    return rows_inserted


def generate_zone_travel_times(conn: sqlite3.Connection, zones: list[dict]) -> int:
    """Generate travel times for all zone pairs (20×19 = 380 pairs)."""
    cur = conn.cursor()
    observed_at = datetime.datetime(2026, 10, 15, 12, 0, 0)  # single observation
    rows_inserted = 0
    batch: list[tuple] = []

    for src in zones:
        for dst in zones:
            if src["zone_id"] == dst["zone_id"]:
                continue

            straight_km = _haversine_km(src["lat"], src["lon"], dst["lat"], dst["lon"])
            # Road distance is 1.2–1.6× straight-line distance
            road_factor = random.uniform(1.2, 1.6)
            distance_km = round(max(2.0, min(25.0, straight_km * road_factor)), 2)

            # Average speed 15–40 km/h in a city
            avg_speed = random.uniform(15.0, 40.0)
            travel_min = round(max(5.0, min(45.0, (distance_km / avg_speed) * 60)), 2)

            batch.append((
                src["zone_id"],
                dst["zone_id"],
                travel_min,
                distance_km,
                observed_at.strftime("%Y-%m-%d %H:%M:%S"),
                SOURCE_TAG,
            ))
            rows_inserted += 1

    cur.executemany(
        "INSERT INTO zone_travel_times "
        "(source_zone_id, destination_zone_id, estimated_travel_time_min, "
        "distance_km, observed_at, source) "
        "VALUES (?, ?, ?, ?, ?, ?);",
        batch,
    )
    conn.commit()
    print(f"[OK] Inserted {rows_inserted} zone_travel_times rows")
    return rows_inserted


# ======================================================================== #
#  Validation
# ======================================================================== #

def validate_data(conn: sqlite3.Connection) -> None:
    """Print row counts and basic statistics for every table."""
    cur = conn.cursor()
    print("\n" + "=" * 70)
    print("  DATA VALIDATION REPORT")
    print("=" * 70)

    # --- zones ---
    cur.execute("SELECT COUNT(*) FROM zones;")
    count = cur.fetchone()[0]
    print(f"\n[zones] {count} rows")
    cur.execute("SELECT MIN(center_latitude), MAX(center_latitude), "
                "MIN(center_longitude), MAX(center_longitude) FROM zones;")
    row = cur.fetchone()
    print(f"  Latitude  range: {row[0]:.4f} - {row[1]:.4f}")
    print(f"  Longitude range: {row[2]:.4f} - {row[3]:.4f}")

    # --- historical_demand ---
    cur.execute("SELECT COUNT(*) FROM historical_demand;")
    count = cur.fetchone()[0]
    print(f"\n[historical_demand] {count:,} rows")
    cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM historical_demand;")
    row = cur.fetchone()
    print(f"  Time range: {row[0]} -> {row[1]}")
    cur.execute("SELECT MIN(ride_requests), AVG(ride_requests), MAX(ride_requests), "
                "MIN(completed_rides), AVG(completed_rides), MAX(completed_rides), "
                "AVG(avg_trip_duration_min), AVG(avg_pickup_wait_min) "
                "FROM historical_demand;")
    row = cur.fetchone()
    print(f"  ride_requests     - min: {row[0]:>3}  avg: {row[1]:>6.1f}  max: {row[2]:>3}")
    print(f"  completed_rides   - min: {row[3]:>3}  avg: {row[4]:>6.1f}  max: {row[5]:>3}")
    print(f"  avg_trip_dur_min  - avg: {row[6]:.2f}")
    print(f"  avg_pickup_wait   - avg: {row[7]:.2f}")
    cur.execute("SELECT COUNT(*) FROM historical_demand WHERE cancelled_rides < 0;")
    neg = cur.fetchone()[0]
    print(f"  Negative cancelled_rides: {neg} (should be 0)")

    # --- driver_supply ---
    cur.execute("SELECT COUNT(*) FROM driver_supply;")
    count = cur.fetchone()[0]
    print(f"\n[driver_supply] {count:,} rows")
    cur.execute("SELECT MIN(timestamp), MAX(timestamp) FROM driver_supply;")
    row = cur.fetchone()
    print(f"  Time range: {row[0]} -> {row[1]}")
    cur.execute("SELECT AVG(available_drivers), AVG(occupied_drivers), "
                "AVG(incoming_drivers), AVG(expected_departures) FROM driver_supply;")
    row = cur.fetchone()
    print(f"  avg available: {row[0]:.1f}  occupied: {row[1]:.1f}  "
          f"incoming: {row[2]:.1f}  departures: {row[3]:.1f}")

    # --- events ---
    cur.execute("SELECT COUNT(*) FROM events;")
    count = cur.fetchone()[0]
    print(f"\n[events] {count} rows")
    cur.execute("SELECT event_status, COUNT(*) FROM events GROUP BY event_status ORDER BY event_status;")
    for status, cnt in cur.fetchall():
        print(f"  {status:<12} {cnt}")
    cur.execute("SELECT MIN(expected_attendance), AVG(expected_attendance), "
                "MAX(expected_attendance) FROM events;")
    row = cur.fetchone()
    print(f"  Attendance - min: {row[0]}  avg: {row[1]:.0f}  max: {row[2]}")

    # --- zone_travel_times ---
    cur.execute("SELECT COUNT(*) FROM zone_travel_times;")
    count = cur.fetchone()[0]
    print(f"\n[zone_travel_times] {count} rows")
    cur.execute("SELECT MIN(estimated_travel_time_min), AVG(estimated_travel_time_min), "
                "MAX(estimated_travel_time_min), "
                "MIN(distance_km), AVG(distance_km), MAX(distance_km) "
                "FROM zone_travel_times;")
    row = cur.fetchone()
    print(f"  Travel time (min) - min: {row[0]:.1f}  avg: {row[1]:.1f}  max: {row[2]:.1f}")
    print(f"  Distance (km)     - min: {row[3]:.1f}  avg: {row[4]:.1f}  max: {row[5]:.1f}")

    # Pair count check
    cur.execute("SELECT COUNT(DISTINCT zone_id) FROM zones;")
    n = cur.fetchone()[0]
    expected_pairs = n * (n - 1)
    print(f"  Expected pairs: {expected_pairs}  Actual: {count}  "
          f"{'OK' if count == expected_pairs else 'MISMATCH'}")

    print("\n" + "=" * 70)
    print("  VALIDATION COMPLETE")
    print("=" * 70 + "\n")


# ======================================================================== #
#  Main entry point
# ======================================================================== #

def main() -> None:
    """Create DB, generate all synthetic data, and run validation."""
    random.seed(SEED)

    # Ensure output directory exists
    os.makedirs(DB_DIR, exist_ok=True)

    # Remove existing DB for a clean run
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"[INFO] Removed existing database at {DB_PATH}")

    print(f"[INFO] Creating database at {DB_PATH}")
    print(f"[INFO] Date range: {START_DATE.date()} -> {END_DATE.date()} ({NUM_DAYS} days)")
    print()

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")

        # Step 1: Schema
        create_schema(conn)

        # Step 2: Zones
        zones = generate_zones(conn)

        # Step 3: Historical demand
        generate_historical_demand(conn, zones)

        # Step 4: Driver supply
        generate_driver_supply(conn, zones)

        # Step 5: Events
        generate_events(conn, zones)

        # Step 6: Zone travel times
        generate_zone_travel_times(conn, zones)

        # Step 7: Validate
        validate_data(conn)

        conn.close()
        print(f"[DONE] Database ready at {DB_PATH}")

    except sqlite3.Error as e:
        print(f"[ERROR] SQLite error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
