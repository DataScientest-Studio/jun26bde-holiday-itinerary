// Unique constraints for POI UUID
// Prevents duplicate POI nodes and improves MERGE lookup.

CREATE CONSTRAINT poi_uuid_unique IF NOT EXISTS
FOR (p:POI)
REQUIRE p.uuid IS UNIQUE;

// Spatial index for geographic POI locations

CREATE POINT INDEX poi_location_index IF NOT EXISTS
FOR (p:POI)
ON (p.location);