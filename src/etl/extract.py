"""
Extracts Points of Interest from the DataTourisme API.

This module handles pagination, retries, POI type/category filtering, 
classification and exports RAW and INTERIM datasets.
"""

import requests
import json
import os
from dotenv import load_dotenv
import time
import pandas as pd

load_dotenv()

API_KEY = os.environ.get("DATATOURISME_API_KEY")
if not API_KEY:
    raise ValueError("Missing API KEY in the .env file - please check the file")

BASE_URL = "https://api.datatourisme.fr/v1/placeOfInterest?department="
department_code = 69

EXCLUDED_TYPES = {
    "TouristInformationCenter", "LocalTouristOffice", "TourismCentre",
    "RegionalTourismCommittee", "DepartementTourismCommittee",
    "PublicLavatories", "WifiHotSpot", "Parking", "ATM", "BusStop", "BusStation",
    "TrainStation", "TaxiStation", "HealthcareProfessional", "HealthcarePlace", "Pharmacy",
    "ServiceProvider", "Transporter", "Rental", "NonHousingRealEstateRental",
    "Product", "Store", "Cinema", "MovieTheater", "Airfield", "NightClub",
    "Spa", "Hammam", "BalneotherapyCentre", "FitnessCenter", "Casino",
    "BowlingAlley", "MiniGolf", "ClimbingWall", "TennisComplex", "GolfCourse",
    "SportsAndLeisurePlace"
}

LODGING_TYPES = {
    "Accommodation", "Hotel", "LodgingBusiness", "HotelTrade", "HotelRestaurant",
    "SelfCateringAccommodation", "RentalAccommodation", "Guesthouse",
    "BedAndBreakfast", "CampingAndCaravanning", "Camping", "CamperVanArea",
    "CollectiveHostel", "CollectiveAccommodation", "Hostel", "Apartment",
    "AccommodationProduct"
}
FOOD_TYPES = {"Restaurant", "FoodEstablishment"}

def fetch_pois(department_code, page_size=250, max_retries = 3):
    """
    Calls DATAtourisme API for Places of Interest in the deparment.
    
    Args:
    - department: Department for search (69 - for Lyon Department)
    - page_size: Number of results per page. Default at 250.
    - max_retries: Maximum retry attempts for failed network requests. Defaults to 3.
    
    Returns: List[dict] of raw, unfiltered places of interest.
    """

    all_pois = []

    params = {
        "api_key": API_KEY,
        "page_size": page_size,
        "fields": "uuid,uri,label,type,isLocatedAt,hasDescription,hasContact,lastUpdate"
    }

    url = f"{BASE_URL}{department_code}"
    page_num = 1
    first_request = True # On first page we are using params but they are not needed on next requests

    while url:
        print(f"Fetching page {page_num}...")
        
        success = False
        for attempt in range(max_retries):
            try:
                if first_request:
                    response = requests.get(url, params=params, timeout=10)
                else:
                    response = requests.get(url, timeout=10)
                response.raise_for_status()
                success = True
                break # if attempt is sucessful break the loop
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1}/{max_retries} failed {e}")
                time.sleep(2 ** attempt)
                
        if not success:
            print(f"Skipping page {page_num} after {max_retries} attempts.")
            break

        first_request = False
        data = response.json()
        all_pois.extend(data["objects"])

        url = data["meta"].get("next")
        page_num += 1
        time.sleep(0.2)

    print(f"Total POIs fetched: {len(all_pois)}")
    return all_pois

def is_relevant_poi(poi):
    """Returns True if the POI is NOT one of the EXCLUDED TYPES(Restaurant, Service, Hotel)"""
    types = set (poi.get("type", []))
    return not types & EXCLUDED_TYPES

    filtered_pois = [
    poi for poi in all_pois
    if is_relevant_poi(poi)
    ]

def classify_poi_kind(types_list):
    """Classifies a POI as 'attraction', 'lodging', or 'food' based on its types."""
    types_set = set(types_list)
    # Lodging takes priority because hotel restaurants are primarily
    # still mainly considered as accommodations.
    if types_set & LODGING_TYPES:
        return "lodging"
    if types_set & FOOD_TYPES:
        return "food"
    return "attraction"

if __name__ == "__main__":
    # Test zone: Department 69 - Lyon
    all_pois = fetch_pois(department_code=department_code)

    museum_pois = [
    poi for poi in all_pois
    if "Museum" in poi.get("type", [])
    ]

    for poi in museum_pois[:20]:
        types = set(poi.get("type", []))
        print(
            poi.get("label"),
            types,
            "EXCLUDED MATCH:",
            types & EXCLUDED_TYPES
        )

    filtered_pois = [
    poi for poi in all_pois
    if is_relevant_poi(poi)
    ]
    
    print(f"\nTotal POIs fetched: {len(all_pois)}")
    print(f"After filtering: {len(filtered_pois)}")

    # Saving a raw JSON dictionary.
    os.makedirs("data/raw", exist_ok = True)

    json_path = "data/raw/pois_unfiltered.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_pois, f, indent=4, ensure_ascii=False)

    print(f"Raw unfiltered POIs saved at {json_path}.")

    # Saving a filtered JSON dictionary.
    os.makedirs("data/interim", exist_ok = True)

    json_path = "data/interim/pois_filtered.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(filtered_pois, f, indent=4, ensure_ascii=False)

    print(f"Filtered pois saved at {json_path}.")

    # Saving the raw CSV
    csv_path = "data/interim/pois_filtered.csv"

    df = pd.json_normalize(filtered_pois)
    df.to_csv(csv_path, index=False, encoding="utf-8")

    print(f"Filtered pois saved to {csv_path}")