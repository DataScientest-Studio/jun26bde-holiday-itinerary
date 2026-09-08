"""
Loads transformed POI data into the PostgreSQL database.

This module reads clean POI dicts and inserts into tables:
POIs, categories, addresses and contacts and many-to-many category relationships.
"""

import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": os.environ.get("POSTGRES_PORT", "5432"),
    "dbname": os.environ.get("POSTGRES_DB"),
    "user": os.environ.get("POSTGRES_USER"),
    "password": os.environ.get("POSTGRES_PASSWORD"),
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def clear_database(cur):
    cur.execute(
        """
        TRUNCATE TABLE
            contact,
            address,
            poi_category,
            category,
            poi
        RESTART IDENTITY CASCADE;
        """
    )

def insert_poi(cur,poi):
    """Inserts one POI and returns its generated poi_id."""
    cur.execute(
        """
        INSERT INTO poi (uuid, label, poi_kind, description, latitude, longitude, estimated_duration_min, last_update, cluster_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (uuid) DO UPDATE SET
            label = EXCLUDED.label,
            poi_kind = EXCLUDED.poi_kind,
            description = EXCLUDED.description,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            estimated_duration_min = EXCLUDED.estimated_duration_min,
            last_update = EXCLUDED.last_update,
            cluster_id = EXCLUDED.cluster_id
        RETURNING poi_id
        """,
        (
            poi["uuid"],
            poi["label"],
            poi["poi_kind"],
            poi["description"],
            poi["latitude"],
            poi["longitude"],
            poi["estimated_duration_min"],
            poi["last_update"],
            poi["cluster_id"]
        ),
    )
    return cur.fetchone()[0]


def insert_category(cur, name):
    """Inserts a category if it doesn't exist, returns its category_id."""
    cur.execute(
        """
        INSERT INTO category (name) VALUES (%s)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING category_id
        """,
        (name,),
    )
    return cur.fetchone()[0]


def insert_poi_category(cur, poi_id, category_id):
    cur.execute(
        """
        INSERT INTO poi_category (poi_id, category_id) VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        (poi_id, category_id),
    )


def insert_address(cur, poi_id, poi):
    cur.execute(
        """
        INSERT INTO address (poi_id, street_address, city, postal_code, department, region)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (poi_id) DO UPDATE SET
            street_address = EXCLUDED.street_address,
            city = EXCLUDED.city,
            postal_code = EXCLUDED.postal_code,
            department = EXCLUDED.department,
            region = EXCLUDED.region
        """,
        (poi_id, poi["street_address"], poi["city"], poi["postal_code"], poi["department"], poi["region"]),
    )


def insert_contact(cur, poi_id, poi):
    if not poi["phone"] and not poi["website"]:
        return
    cur.execute(
        """
        INSERT INTO contact (poi_id, phone, website) VALUES (%s, %s, %s)
        ON CONFLICT (poi_id) DO UPDATE SET
            phone = EXCLUDED.phone,
            website = EXCLUDED.website
        """,
        (poi_id, poi["phone"], poi["website"]),
    )

def init_db(conn):
    schema_path = "sql/schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()

def load_pois(clean_data):
    """
    Load a list of clean POI dicts into the database.

    Existing app data is cleared before loading the new dataset.
    The operation is committed only if all inserts succeed.

    Args:
        clean_data: List of cleaned POI dicts.
    """
    conn = get_connection()

    cur = conn.cursor()

    try:

        clear_database(cur)

        for poi in clean_data:
            poi_id = insert_poi(cur, poi)
            insert_address(cur, poi_id, poi)
            insert_contact(cur, poi_id, poi)

            for category_name in poi["categories"]:
                category_id = insert_category(cur, category_name)
                insert_poi_category(cur, poi_id, category_id)

        conn.commit()
        print(f"Loaded {len(clean_data)} POIs into the database.")
    except Exception as e:
        conn.rollback()
        print(f"Error during load, rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":

    with open("data/processed/pois_clustered.json", "r", encoding="utf-8") as f:
        clean_data = json.load(f)

    load_pois(clean_data)