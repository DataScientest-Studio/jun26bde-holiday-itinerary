"""
FastAPI backend for Holiday itinerary application.

Provides endpoits for POIs, categories, health check,
and itinerary generation.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv
from typing import Optional, Literal, List
from pydantic import BaseModel, Field
from neo4j import GraphDatabase

from src.itinerary.itinerary_logic import (
    select_candidates,
    build_itinerary
)

load_dotenv()

PoiKind = Literal["attraction", "food", "lodging"]

DB_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": os.environ.get("POSTGRES_PORT", "5432"),
    "dbname": os.environ.get("POSTGRES_DB"),
    "user": os.environ.get("POSTGRES_USER"),
    "password": os.environ.get("POSTGRES_PASSWORD"),
}

NEO4J_URI = os.environ.get(
    "NEO4J_URI",
    "bolt://localhost:7687"
)
NEO4J_USER = os.environ.get(
    "NEO4J_USER",
    "neo4j"
)
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

app = FastAPI(title="Holiday itinerary API")

class ItineraryRequest(BaseModel):
    hotel_uuid: str
    preferred_categories: List[str]
    days: int = Field(ge=1, le=7)
    lunch: bool = True
    dinner: bool = True

class SaveItineraryRequest(BaseModel):
    email: str
    itinerary: list

def get_connection():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def get_hotel_for_itinerary(hotel_uuid):
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                uuid,
                label,
                poi_kind,
                latitude,
                longitude,
                cluster_id
            FROM poi
            WHERE uuid = %s
            AND poi_kind = 'lodging'
            """,
            (hotel_uuid,),
        )

        hotel = cur.fetchone()

        cur.close()
        conn.close()

        return hotel

def get_attraction_candidates(cluster_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            p.uuid,
            p.label,
            p.poi_kind,
            p.description,
            p.latitude,
            p.longitude,
            p.estimated_duration_min,
            p.cluster_id,
            ct.website,
            COALESCE(
                array_agg(DISTINCT c.name)
                FILTER (WHERE c.name IS NOT NULL),
                '{}'
            ) AS categories
        FROM poi p
        LEFT JOIN poi_category pc
            ON p.poi_id = pc.poi_id
        LEFT JOIN category c
            ON pc.category_id = c.category_id
        LEFT JOIN contact ct
            ON p.poi_id = ct.poi_id
        WHERE p.poi_kind = 'attraction'
          AND p.cluster_id = %s
        GROUP BY
            p.poi_id,
            ct.website
        """,
        (cluster_id,),
    )

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [dict(row) for row in rows]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/pois")
def list_pois(
    poi_kind: Optional[PoiKind] = Query(None, description="Type of POI \n"), 
    category: Optional[str] = None, 
    limit: int = Query(20, ge=1, le=200)
    ):
    """Return POIs with optional type and category filters."""
    conn = get_connection()
    cur = conn.cursor()

    query = """
    SELECT DISTINCT p.poi_id, p.uuid, p.label, p.poi_kind, p.latitude, p.longitude
    FROM poi p
    LEFT JOIN poi_category pc ON p.poi_id = pc.poi_id
    LEFT JOIN category c ON pc.category_id = c.category_id
    WHERE 1=1
    """

    params = []

    if poi_kind:
        query += " AND p.poi_kind = %s"
        params.append(poi_kind)

    if category:
        query += " AND c.name = %s"
        params.append(category)

    query += " LIMIT %s"
    params.append (limit)

    cur.execute(query, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

@app.get("/pois/{poi_uuid}")
def get_poi(poi_uuid: str):
    """Return detailed information for single POI."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            p.poi_id, p.uuid, p.label, p.poi_kind, p.description, 
            p.latitude, p.longitude, p.estimated_duration_min, 
            a.street_address, a.city, a.postal_code, a.department, a.region,
            c.phone, c.website
        FROM poi p
        LEFT JOIN address a ON p.poi_id = a.poi_id
        LEFT JOIN contact c ON p.poi_id = c.poi_id
        WHERE p.uuid = %s
        """,
        (poi_uuid,),
    )

    poi = cur.fetchone()

    if poi is None:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="POI not found")

    cur.execute(
        """
        SELECT cat.name FROM category cat
        JOIN poi_category pc ON cat.category_id = pc.category_id
        JOIN poi p ON pc.poi_id = p.poi_id
        WHERE p.uuid = %s
        """,
        (poi_uuid,),
    )

    categories = [row["name"] for row in cur.fetchall()]

    cur.close()
    conn.close()

    poi["categories"] = categories
    return poi

@app.get("/categories")
def list_categories(
    poi_kind: Optional[PoiKind] = None
):
    """Returns available POI categories."""
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT DISTINCT cat.name
        FROM category cat
        JOIN poi_category pc
            ON cat.category_id = pc.category_id
        JOIN poi p
            ON pc.poi_id = p.poi_id
        WHERE 1=1
    """

    params = []

    if poi_kind:
        query += " AND p.poi_kind = %s"
        params.append(poi_kind)

    query += " ORDER BY cat.name"

    cur.execute(query, params)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [row["name"] for row in rows]

@app.post("/itinerary")
def generate_itinerary(request: ItineraryRequest):
    """
    Generate a multi-day itinerary.
    The selected hotel determines the geographical starting point.
    """
    hotel = get_hotel_for_itinerary(request.hotel_uuid)

    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    cluster_id = hotel["cluster_id"]
    pois = get_attraction_candidates(cluster_id)

    candidates = select_candidates(
        pois,
        cluster_id,
        request.preferred_categories,
    )

    if not candidates:
        raise HTTPException(
            status_code=404, detail="No attractions found for selected preferences"
        )

    candidate_uuids = [poi["uuid"] for poi in candidates]

    itinerary = build_itinerary(
        driver=driver,
        hotel_uuid=request.hotel_uuid,
        cluster_id=cluster_id,
        candidate_uuids=candidate_uuids,
        days=request.days,
        lunch=request.lunch,
        dinner=request.dinner,
        daily_minutes=600
    )

    for day in itinerary:
        for poi in day["pois"]:
            details = get_poi(poi["uuid"])
            poi["description"] = details["description"]
            poi["phone"] = details["phone"]
            poi["website"] = details["website"]
            poi["street_address"] = details["street_address"]
            poi["city"] = details["city"]

    return itinerary

@app.post("/itineraries/save")
def save_user_itinerary(request: SaveItineraryRequest):
    """Saves a generated itinerary for a specific user."""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT user_id FROM users WHERE email = %s", (request.email,))
        user = cur.fetchone()
        
        if user:
            user_id = user["user_id"]
        else:
            cur.execute(
                "INSERT INTO users (email) VALUES (%s) RETURNING user_id", 
                (request.email,)
            )
            user_id = cur.fetchone()["user_id"]
            
        cur.execute(
            "INSERT INTO saved_itineraries (user_id) VALUES (%s) RETURNING itinerary_id",
            (user_id,)
        )
        itinerary_id = cur.fetchone()["itinerary_id"]
        
        for day in request.itinerary:
            day_num = day["day"]
            order = 1
            for poi in day["pois"]:
                cur.execute(
                    """
                    INSERT INTO itinerary_stops (itinerary_id, poi_uuid, day_number, stop_order)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (itinerary_id, poi["uuid"], day_num, order)
                )
                order += 1
                
        conn.commit()
        return {"status": "success", "itinerary_id": itinerary_id}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/itineraries/{email}")
def get_user_itineraries(email: str):
    """Retrieves all saved itineraries for a specific user email."""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        
        if not user:
            return []
            
        cur.execute(
            """
            SELECT itinerary_id, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI') as created_date
            FROM saved_itineraries 
            WHERE user_id = %s 
            ORDER BY created_at DESC
            """,
            (user["user_id"],)
        )
        itineraries = cur.fetchall()
        
        for itinerary in itineraries:
            cur.execute(
                """
                SELECT s.day_number, s.stop_order, p.label, p.poi_kind, a.city 
                FROM itinerary_stops s
                JOIN poi p ON s.poi_uuid = p.uuid
                LEFT JOIN address a ON p.poi_id = a.poi_id
                WHERE s.itinerary_id = %s
                ORDER BY s.day_number, s.stop_order
                """,
                (itinerary["itinerary_id"],)
            )
            itinerary["stops"] = cur.fetchall()
            
        return itineraries
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()