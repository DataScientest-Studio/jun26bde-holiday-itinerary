from src.itinerary.itinerary_logic import (
    calculate_poi_score,
    estimate_travel_minutes,
    select_candidates,
)


def test_calculate_poi_score_with_matching_category():
    poi = {
        "categories": ["Museum", "Cultural Site"],
        "description": None,
        "website": None
    }

    score = calculate_poi_score(
        poi,
        preferred_categories=["Museum"]
    )

    assert score == 3

def test_calculate_poi_score_with_metadata():
    poi = {
        "categories": ["Museum"],
        "description": "Historical museum with ...",
        "website": "https://example.com"
    }

    score = calculate_poi_score(
        poi,
        preferred_categories=["Museum"]
    )

    assert score == 5

def test_calculate_poi_score_without_match():
    poi = {
        "categories": ["Church"],
        "description": None,
        "website": None
    }

    score = calculate_poi_score(
        poi,
        preferred_categories=["Museum"]
    )

    assert score == 0

def test_select_candidates_filters_clusters():
    pois = [
        {
            "uuid": "1",
            "poi_kind": "attraction",
            "cluster_id": 0,
            "categories": ["Museum"],
            "description": None,
            "website": None
        },
        {
            "uuid": "2",
            "poi_kind": "attraction",
            "cluster_id": 1,
            "categories": ["Museum"],
            "description": None,
            "website": None
        }
    ]

    result = select_candidates(
        pois=pois,
        cluster_id=0,
        preferred_categories=["Museum"],
        poi_kind="attraction",
    )

    assert len(result) == 1
    assert result[0]["uuid"] == "1"

def test_select_candidates_orders_by_score():
    pois = [
        {
            "uuid": "1",
            "poi_kind": "attraction",
            "cluster_id": 0,
            "categories": ["ParkAndGarden"],
            "description": None,
            "webiste": None
        },
        {
            "uuid": "2",
            "poi_kind": "attraction",
            "cluster_id": 0,
            "categories": ["Museum"],
            "description": "Museum description",
            "website": "https://example.com"
        }
    ]

    result = select_candidates(
        pois=pois,
        cluster_id=0,
        preferred_categories=["Museum"],
        poi_kind="attraction"
    )

    assert result[0]["uuid"] == "2"
    assert result[0]["score"] == 5

def test_estimate_travel_minutes_zero_distance():
    assert estimate_travel_minutes(0) == 0

def test_estimate_travel_minutes_walking():
    assert estimate_travel_minutes(1) == 13

def test_estimate_travel_minutes_public_transport():
    assert estimate_travel_minutes(2) == 16