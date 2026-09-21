from src.etl.transform import clean_categories, estimated_duration, safe_get


def test_safe_get_existing_value():
    data = {
        "address": {
            "city": "Paris"
        }
    }

    result = safe_get(data, "address", "city")

    assert result == "Paris"

def test_safe_get_missing_value():
    data = {}

    result = safe_get(
        data,
        "address",
        "city",
        default = None
    )

    assert result is None

def test_clean_categories_removes_generic_types():
    categories = [
        "PlaceOfInterest",
        "Museum",
        "PointOfInterest"
    ]

    result = clean_categories(categories)

    assert "Museum" in result
    assert "PlaceOfInterest" not in result
    assert "PointOfInterest" not in result

def test_estimated_duration_default():
    categories = ["UnkownCategory"]

    result = estimated_duration(categories)

    assert result == 45