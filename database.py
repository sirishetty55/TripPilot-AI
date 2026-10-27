"""
SQLite database module for TripPilot AI.
Persists saved trips, itinerary plans, and MCP research audit logs.
Supports connection disposal and path overriding for isolated test environments.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from config import DATABASE_PATH as CONFIG_DATABASE_PATH

DATABASE_PATH = CONFIG_DATABASE_PATH

def get_connection(db_path=None) -> sqlite3.Connection:
    """Creates a connection with row factory enabled."""
    target = db_path or DATABASE_PATH
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=None):
    """Initializes SQLite schema if not already present."""
    conn = get_connection(db_path=db_path)
    try:
        cursor = conn.cursor()
        
        # Saved Trips Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination TEXT NOT NULL,
                departure_date TEXT NOT NULL,
                return_date TEXT NOT NULL,
                travelers INTEGER NOT NULL,
                budget_inr REAL NOT NULL,
                starting_city TEXT,
                trip_request_json TEXT NOT NULL,
                research_result_json TEXT NOT NULL,
                itinerary_json TEXT NOT NULL,
                budget_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Research Audit Logs Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination TEXT NOT NULL,
                status TEXT NOT NULL,
                sources_count INTEGER DEFAULT 0,
                duration_sec REAL DEFAULT 0.0,
                log_summary TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Image Cache Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS image_cache (
                cache_key TEXT PRIMARY KEY,
                image_url TEXT NOT NULL,
                thumb_url TEXT NOT NULL,
                alt_text TEXT,
                attribution_text TEXT,
                attribution_url TEXT,
                provider TEXT,
                is_exact_match INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()

def save_trip(trip_request_dict: Dict[str, Any],
              research_result_dict: Dict[str, Any],
              itinerary_list: List[Dict[str, Any]],
              budget_dict: Dict[str, Any],
              db_path=None) -> int:
    """Saves a trip research session into SQLite."""
    init_db(db_path=db_path)
    conn = get_connection(db_path=db_path)
    try:
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO saved_trips (
                destination, departure_date, return_date, travelers, budget_inr,
                starting_city, trip_request_json, research_result_json,
                itinerary_json, budget_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trip_request_dict.get("destination", "Unknown"),
            trip_request_dict.get("departure_date", ""),
            trip_request_dict.get("return_date", ""),
            int(trip_request_dict.get("travelers", 1)),
            float(trip_request_dict.get("budget_inr", 0.0)),
            trip_request_dict.get("starting_city", ""),
            json.dumps(trip_request_dict),
            json.dumps(research_result_dict),
            json.dumps(itinerary_list),
            json.dumps(budget_dict),
            now
        ))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_all_trips(db_path=None) -> List[Dict[str, Any]]:
    """Returns all saved trips ordered by latest first."""
    init_db(db_path=db_path)
    conn = get_connection(db_path=db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, destination, departure_date, return_date, travelers,
                   budget_inr, starting_city, created_at
            FROM saved_trips
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_trip_by_id(trip_id: int, db_path=None) -> Optional[Dict[str, Any]]:
    """Loads a full trip record including parsed JSON payloads."""
    init_db(db_path=db_path)
    conn = get_connection(db_path=db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM saved_trips WHERE id = ?", (trip_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        data = dict(row)
        try:
            data["trip_request"] = json.loads(data["trip_request_json"])
            data["research_result"] = json.loads(data["research_result_json"])
            data["itinerary"] = json.loads(data["itinerary_json"])
            data["budget"] = json.loads(data["budget_json"])
        except Exception:
            pass
        return data
    finally:
        conn.close()

def delete_trip(trip_id: int, db_path=None) -> bool:
    """Deletes a saved trip by ID."""
    init_db(db_path=db_path)
    conn = get_connection(db_path=db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_trips WHERE id = ?", (trip_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def log_research_session(destination: str, status: str, sources_count: int, duration_sec: float, log_summary: str, db_path=None):
    """Audits research execution duration and MCP source counts."""
    init_db(db_path=db_path)
    conn = get_connection(db_path=db_path)
    try:
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO research_logs (
                destination, status, sources_count, duration_sec, log_summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (destination, status, sources_count, round(duration_sec, 2), log_summary, now))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def get_recent_research_logs(limit: int = 10, db_path=None) -> List[Dict[str, Any]]:
    """Fetches recent audit logs."""
    init_db(db_path=db_path)
    conn = get_connection(db_path=db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM research_logs ORDER BY id DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

# Auto-initialize database on import
init_db()
