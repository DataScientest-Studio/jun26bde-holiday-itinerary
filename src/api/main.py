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
import json

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

def get_connection():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

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
    with open(
        "data/processed/pois_clustered.json",
        "r",
        encoding = "utf-8"
    ) as f:
        pois = json.load(f)
  
    hotel = next(
        (
            poi for poi in pois
            if poi["uuid"] == request.hotel_uuid
            and poi["poi_kind"] == "lodging"
        ),
        None
    )

    if hotel is None:
        raise HTTPException(
            status_code=404,
            detail="Hotel not found"
        )

    cluster_id = hotel["cluster_id"]

    candidates = select_candidates(
        pois=pois,
        cluster_id=cluster_id,
        preferred_categories=request.preferred_categories,
        poi_kind="attraction",
        top_n=20
    )

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No attractions found for selected preferences"
        )

    candidate_uuids = [
        poi["uuid"] for poi in candidates
    ]

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

    # Adding metadata for POI stored in PostgreSQL.
    for day in itinerary:
        for poi in day["pois"]:
            details = get_poi(poi["uuid"])

            poi["description"] = details["description"]
            poi["phone"] = details["phone"]
            poi["website"] = details["website"]
            poi["street_address"] = details["street_address"]
            poi["city"] = details["city"]

    return itinerary