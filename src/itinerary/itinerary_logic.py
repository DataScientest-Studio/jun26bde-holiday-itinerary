"""
Contains the core itinerary logic.

This module scores POIs based on user preferrences and available informations.
Uses Neo4j to find nearby attractions, estimates travel time and builds itinerary
based on preferred number of days.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

def calculate_poi_score(poi, preferred_categories):
    """
    Calculates the relevance score of a POI based on user preferrences.
    Matching category carries the highest weight.
    Additional points are given if POI has a description and/or website.

    Args:
        poi (dict): POI data.
        preferred_categories (list): Categories that user selected.
    
    Returns:
        int: Calculated score
    """
    score = 0

    for category in poi["categories"]:
        if category in preferred_categories:
            score += 3

    if poi.get("description"):
        score += 1

    if poi.get("website"):
        score += 1

    return score

def select_candidates(
        pois,
        cluster_id,
        preferred_categories,
        poi_kind=None,
        top_n=20
):
    """
    Selects most relevant POI candidates for the itinerary generation.
    POIS are filtered by the geographical cluster and by the scoring system.

    Top candidates are then sorted by score in descending order and only the 
    top N results are returned.

    Args:
        pois: list of POI dictionaries
        cluster_id: id of the geographical cluster in which POIs are selected
        preferred_categories: List of categoreies preferred by the user.
        poi_kind: POI type filter: (attraction, food or lodging).
        top_n: maximum number of candidates to return.

    Returns:
        list: list of highest scoring POIs, ordered by relevance.
    """
    selected = []

    for poi in pois:
        if poi["cluster_id"] != cluster_id:
            continue

        if poi_kind and poi["poi_kind"] != poi_kind:
            continue
        
        poi["score"] = calculate_poi_score(
            poi,
            preferred_categories
        )

        selected.append(poi)

    selected = sorted(
        selected,
        key=lambda poi: poi["score"],
        reverse=True
    )

    return selected[:top_n]

def find_nearest_food(driver, current_uuid, cluster_id, used_food_uuids):
    """
    Finds the nearest restaurant that was not visited from the current POI.

    Distance is calculated using Neo4j geographic point data.
    
    Returns:
        dict (uuid, label, distance in kilometers) or None if no matching Restaurants found.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (current:POI {uuid: $current_uuid})
            MATCH (food:POI)
            WHERE food.poi_kind = "food"
            AND food.cluster_id = $cluster_id
            AND not food.uuid IN $used_food_uuids
            WITH current, food,
                point.distance(current.location, food.location) AS distance_m
            RETURN
                food.uuid AS uuid,
                food.label AS label,
                food.location.latitude AS latitude,
                food.location.longitude AS longitude,
                distance_m / 1000 AS distance_km
            ORDER BY distance_m
            LIMIT 1
            """,
            current_uuid=current_uuid,
            cluster_id=cluster_id,
            used_food_uuids=used_food_uuids
        )

        food = result.single()

        if food is None:
            return None

        return {
            "uuid": food["uuid"],
            "label": food["label"],
            "distance_km": food["distance_km"],
            "latitude": food["latitude"],
            "longitude": food["longitude"]
        }

def find_nearest_attraction(driver, current_uuid, cluster_id, candidate_uuids, used_attraction_uuids):
    """
    Finds the nearest attraction that was not visited from the current POI.
    Only attractions that belong to the selected cluster and previously scored 
    candidate list is considered.

    Returns:
            dict (uuid, label, distance in kilometers) or None if no matching Attractions found.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (current:POI {uuid: $current_uuid})
            MATCH (attraction:POI)
            WHERE attraction.poi_kind = "attraction"
            AND attraction.cluster_id = $cluster_id
            AND attraction.uuid IN $candidate_uuids
            AND NOT attraction.uuid IN $used_attraction_uuids
            WITH current, attraction,
                point.distance(current.location, attraction.location) AS distance_m
            RETURN
                attraction.uuid AS uuid,
                attraction.label AS label,
                attraction.location.latitude AS latitude,
                attraction.location.longitude AS longitude,
                distance_m / 1000 AS distance_km,
                attraction.estimated_duration_min AS estimated_duration_min
            ORDER BY distance_m
            LIMIT 1
            """,
            current_uuid=current_uuid,
            cluster_id=cluster_id,
            used_attraction_uuids=used_attraction_uuids,
            candidate_uuids=candidate_uuids
        )

        attraction = result.single()

        if attraction is None:
             return None

        return {
             "uuid": attraction["uuid"],
             "label": attraction["label"],
             "latitude": attraction["latitude"],
             "longitude": attraction["longitude"],
             "distance_km": attraction["distance_km"],
             "estimated_duration_min": attraction["estimated_duration_min"]
        }

def estimate_travel_minutes(distance_km):
    """
    Estimates travel times between two POIs based on the distance.
    Short distances up to 1 km are considered to be walkable with the
    average speed of 4.5 km/h.

    Longer distances are assumed to use public transport with the average speed of 20 km/h
    and additional 10 minutes of waiting for the transportation.

    Args:
        distance_km

    Returns:
        int: estimated travel times in minutes.
    """
    if distance_km == 0:
        return 0
    
    if distance_km <= 1:
        return max(1, round(distance_km / 4.5 * 60))

    average_transit_speed_kmh = 20
    waiting_time_min = 10

    travel_time_min = distance_km / average_transit_speed_kmh * 60

    return round(travel_time_min + waiting_time_min)

def add_attraction(
    driver,
    current_uuid,
    cluster_id,
    candidate_uuids,
    used_attraction_uuids,
    current_day,
    used_minutes,
    daily_minutes
):
    """Add the next attraction to the current day if it fits the time limit."""
    attraction = find_nearest_attraction(
        driver=driver,
        current_uuid=current_uuid,
        cluster_id=cluster_id,
        candidate_uuids=candidate_uuids,
        used_attraction_uuids=used_attraction_uuids
    )

    if attraction is None:
        return current_uuid, used_minutes, False

    travel_minutes = estimate_travel_minutes(
        attraction["distance_km"]
    )

    visit_minutes = attraction["estimated_duration_min"]
    required_minutes = travel_minutes + visit_minutes

    if used_minutes + required_minutes > daily_minutes:
        return current_uuid, used_minutes, False

    attraction["poi_kind"] = "attraction"
    attraction["travel_minutes"] = travel_minutes

    current_day.append(attraction)
    used_attraction_uuids.append(attraction["uuid"])

    used_minutes += required_minutes
    current_uuid = attraction["uuid"]

    return current_uuid, used_minutes, True

def add_meal(
    driver,
    current_uuid,
    cluster_id,
    used_food_uuids,
    current_day,
    used_minutes,
    daily_minutes,
    meal_type
):
    """Add lunch or dinner to the current day if it fits the time limit."""
    food = find_nearest_food(
        driver=driver,
        current_uuid=current_uuid,
        cluster_id=cluster_id,
        used_food_uuids=used_food_uuids
    )

    if food is None:
        return current_uuid, used_minutes, False

    travel_minutes = estimate_travel_minutes(
        food["distance_km"]
    )

    if meal_type == "lunch":
        meal_duration = 60
    else:
        meal_duration = 90

    required_minutes = travel_minutes + meal_duration

    if used_minutes + required_minutes > daily_minutes:
        return current_uuid, used_minutes, False

    food["poi_kind"] = "food"
    food["meal_type"] = meal_type
    food["travel_minutes"] = travel_minutes
    food["estimated_duration_min"] = meal_duration

    current_day.append(food)
    used_food_uuids.append(food["uuid"])

    used_minutes += required_minutes
    current_uuid = food["uuid"]

    return current_uuid, used_minutes, True

def build_itinerary(
    driver,
    hotel_uuid,
    cluster_id,
    candidate_uuids,
    days,
    lunch=True,
    dinner=True,
    daily_minutes=600
):
    """
    Builds a multi-day itinerary.

    Each day starts from the selected hotel.
    Attractions are selected from the previously scored candidates.
    Lunch is added after two attractions and dinner after four attractions.

    Args:
        driver: Active Neo4j database driver.
        hotel_uuid: UUID of selected hotel.
        cluster_id: Geographic cluster used for generation.
        candidate_uuids: Attraction UUIDs that are available for selection.
        days: Number of days for itinerary.
        lunch: Whether lunch should be included.
        dinner: Whether dinner should be included.
        daily_minutes: Maximum planned minutes per day.

    Returns:
        list: itinerary for multiple days containing POIs and total duration per day.
    """

    itinerary = []

    used_attraction_uuids = []
    used_food_uuids = []

    for day_number in range(1, days + 1):

        current_day = []
        current_uuid = hotel_uuid
        used_minutes = 0
        attraction_count = 0

        while (
            attraction_count < 4
            and len(used_attraction_uuids) < len(candidate_uuids)
        ):
            current_uuid, used_minutes, added = add_attraction(
                driver=driver,
                current_uuid=current_uuid,
                cluster_id=cluster_id,
                candidate_uuids=candidate_uuids,
                used_attraction_uuids=used_attraction_uuids,
                current_day=current_day,
                used_minutes=used_minutes,
                daily_minutes=daily_minutes
            )

            if not added:
                break

            attraction_count += 1

            if lunch and attraction_count == 2:
                current_uuid, used_minutes, _ = add_meal(
                    driver=driver,
                    current_uuid=current_uuid,
                    cluster_id=cluster_id,
                    used_food_uuids=used_food_uuids,
                    current_day=current_day,
                    used_minutes=used_minutes,
                    daily_minutes=daily_minutes,
                    meal_type="lunch"
                )

            if dinner and attraction_count == 4:
                current_uuid, used_minutes, _ = add_meal(
                    driver=driver,
                    current_uuid=current_uuid,
                    cluster_id=cluster_id,
                    used_food_uuids=used_food_uuids,
                    current_day=current_day,
                    used_minutes=used_minutes,
                    daily_minutes=daily_minutes,
                    meal_type="dinner"
                )

        if current_day:
            itinerary.append({
                "day": day_number,
                "pois": current_day,
                "total_minutes": used_minutes
            })

    return itinerary