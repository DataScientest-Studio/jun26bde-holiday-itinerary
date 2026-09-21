"""
Loads clustered POIs into Neo4j

This module creates POI nodes with geographical coordinates and NEAR_TO relationships
between nearby POIs
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

def init_neo4j_schema(driver):
    schema_path = Path("neo4j/schema.cypher")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_queries = f.read()

    with driver.session() as session:
        for query in schema_queries.split(";"):
            query = query.strip()

            if query:
                session.run(query)

    print("Neo4j schema initialized.")

def clear_neo4j(driver):
    """Deletes all existing nodes and relationships."""
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("Old NEO4J data deleted.")

def load_poi_nodes(driver, clean_data):
    """Creates one POI node per POI record, with latitude, longitude as Neo4J point()"""
    with driver.session() as session:
        for poi in clean_data:
            session.run(
                """
                MERGE (p:POI {uuid: $uuid})
                SET p.label = $label,
                    p.poi_kind = $poi_kind,
                    p.estimated_duration_min = $estimated_duration_min,
                    p.location = point({
                        latitude: $latitude, 
                        longitude: $longitude}),
                    p.cluster_id = $cluster_id
                """,
                uuid=poi["uuid"],
                label=poi["label"],
                poi_kind=poi["poi_kind"],
                estimated_duration_min=poi["estimated_duration_min"],
                latitude=poi["latitude"],
                longitude=poi["longitude"],
                cluster_id=poi["cluster_id"]
            )
    print(f"Connected {len(clean_data)} POI nodes.")

K_NEAREST = 5

def create_near_to_relationships(driver, clean_data, k=K_NEAREST):
    """
    Connects each POI to it's k nearest POIs.

    Using Neo4j point.distance() to calculate geographic distance in meters.
    The relationships is converted to kilometers
    """
    with driver.session() as session:
        for i, poi in enumerate(clean_data):
            # For each POI, calculate the distance to other POIs and connect
            # it to the k nearest neighbors. Distances are stored in kilometers
            session.run(
                """
                MATCH (a:POI {uuid: $uuid})
                MATCH (b:POI)
                WHERE a.uuid <> b.uuid
                AND a.cluster_id = b.cluster_id
                WITH a, b, point.distance(a.location, b.location) AS distance_m
                ORDER BY distance_m
                LIMIT $k
                MERGE (a)-[r:NEAR_TO]-(b)
                SET r.distance_km = distance_m / 1000
                """,
                uuid=poi["uuid"],
                k=k
            )
            if (i + 1) % 100 == 0:
                print(f"Processed {i + 1}/{len(clean_data)} POIs.")

    print(f"Processed NEAR_TO relationships (k={k}).")

if __name__ == "__main__":
    with open('data/processed/pois_clustered.json', 'r', encoding = 'utf-8') as f:
        clean_data = json.load(f)

    driver = GraphDatabase.driver(
        NEO4J_URI, 
        auth=(NEO4J_USER, NEO4J_PASSWORD))

    driver.verify_connectivity()
    print("Connected to Neo4j successfully.")

    clear_neo4j(driver)
    init_neo4j_schema(driver)
    load_poi_nodes(driver, clean_data)
    create_near_to_relationships(driver, clean_data)

    driver.close()
