"""
Transforms RAW DataTourisme POIs into a clean dataset.

This module extracts geographic, contact, category and descriptive information
about POIs and prepares the data for clustering.
"""

import json
import os

import pandas as pd

from .extract import classify_poi_kind


def safe_get(d, *keys, default=None):
    """Safely retrieve a nested dictionary value."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return d if d is not None else default


GENERIC_TYPES = {"PlaceOfInterest","PointOfInterest"}

def clean_categories(types_list):
    """Removing generic POI types and keeps only specific categories."""
    return [t for t in types_list if t not in GENERIC_TYPES]

DURATION_BY_CATEGORY = {
    "Museum": 120,
    "Church": 30,
    "ReligiousSite": 30,
    "Park": 60,
    "ParkAndGarden": 60,
    "CulturalSite": 90,
    "TechnicalHeritage": 60,
    "Theater": 120,
    "SportsAndLeisurePlace": 90
}

DURATION_PRIORITY = [
    "Museum", "Theater", "TechnicalHeritage", "Church", "ReligiousSite", 
    "ParkAndGarden", "Park", "CulturalSite", "SportsAndLeisurePlace"
]

DEFAULT_DURATION = 45

def estimated_duration(types_list):
    """Estimates visit duration in minutes according to the most unique category for a POI.
    
    Categories are checked in priority order. If category is not in the list, default duration is returned.
    """
    for category in DURATION_PRIORITY:
        if category in types_list:
            return DURATION_BY_CATEGORY[category]
    return DEFAULT_DURATION

def extract_contact(poi):
    """
    Extracts the first available phone number and website from a POI.
    
    Returns:
        dict: Contact information with phone and website.
    """
    contact_list = poi.get("hasContact", [])
    if not contact_list:
        return {"phone": None, "website": None}

    contact = contact_list[0]
    phones = contact.get("telephone", [])
    websites = contact.get("homepage", [])

    return {
        "phone": phones[0] if phones else None,
        "website": websites[0] if websites else None,
    }

def transform_poi(poi):
    """
    Transforms a raw POI from DataTourisme into a structured dictionary.

    The returned dictionary contains classification, categories, geo information,
    address, contact informations, description and estimated duration for visit.

    Args:
        poi: raw dict from DataTourisme.

    Returns:
        dict: Clean POI dictionary.
    """

    # Some fields are returned as lists, so we use the first item when available.
    location_list = poi.get("isLocatedAt", [])
    location = location_list[0] if location_list else {}

    address_list = location.get("address", [])
    address = address_list[0] if address_list else {}

    street_addresses = address.get("streetAddress", [])
    street_address = street_addresses[0] if street_addresses else None

    desc_list = poi.get("hasDescription", [])
    description = None
    if desc_list:
        description = safe_get(desc_list[0], "shortDescription", "@en")

    contact = extract_contact(poi)

    raw_types = poi.get("type", [])
    clean_types = clean_categories(raw_types)
    kind = classify_poi_kind(raw_types)

    return {
        "uuid": poi.get("uuid"),
        "uri": poi.get("uri"),
        "label": poi.get("label", {}).get("@fr") or poi.get("label", {}).get("@en"),
        "poi_kind": kind,
        "categories": clean_types,
        "estimated_duration_min": estimated_duration(raw_types),
        "description": description,
        "latitude": safe_get(location, "geo", "latitude"),
        "longitude": safe_get(location, "geo", "longitude"),
        "street_address": street_address,
        "city": safe_get(address, "addressLocality"),
        "postal_code": safe_get(address, "postalCode"),
        "department": safe_get(address, "hasAddressCity", "isPartOfDepartment", "label", "@fr"),
        "region": safe_get(address, "hasAddressCity", "isPartOfDepartment", "isPartOfRegion", "label", "@fr"),
        "phone": contact["phone"],
        "website": contact["website"],
        "last_update": poi.get("lastUpdate")
    }

if __name__ == "__main__":
    with open("data/interim/pois_filtered.json", "r", encoding="utf-8") as f:
        pois = json.load(f)

    clean_data = [transform_poi(poi) for poi in pois]

    df = pd.DataFrame(clean_data)

    print(df.shape)
    print(df.head())
    print("\nMissing values per column:")
    print(df.isna().sum())

    print("Duplicate UUIDs:", df["uuid"].duplicated().sum())

    df = df.drop_duplicates(subset="uuid")

    print(
    "POIs without coordinates:",
    df[["latitude", "longitude"]].isna().any(axis=1).sum()
    )

    # Convert invalid or missing timestamps to NaT instead of failing the pipeline.
    df["last_update"] = pd.to_datetime(
    df["last_update"],
    errors="coerce",
    utc=True
    )

    os.makedirs("data/processed", exist_ok=True)

    df.to_csv(
        "data/processed/pois_clean.csv", 
        index=False,
        encoding="utf-8")

    df.to_json(
        "data/processed/pois_clean.json",
        orient="records",
        force_ascii=False,
        indent=2,
        date_format="iso")