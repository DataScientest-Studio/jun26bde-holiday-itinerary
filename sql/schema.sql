DROP TABLE IF EXISTS itinerary_stops, saved_itineraries, users, poi_review_label, review_label, contact, address, poi_category, category, poi CASCADE;

CREATE TABLE poi (
    poi_id SERIAL PRIMARY KEY,
    uuid VARCHAR(64) UNIQUE NOT NULL,
    label VARCHAR(500),
    description TEXT,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    estimated_duration_min INT,
    last_update DATE,
    cluster_id INTEGER
);

CREATE TABLE category (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE poi_category (
    poi_id INT REFERENCES poi(poi_id) ON DELETE CASCADE,
    category_id INT REFERENCES category(category_id) ON DELETE CASCADE,
    PRIMARY KEY (poi_id, category_id)
);

CREATE TABLE address (
    poi_id INT PRIMARY KEY REFERENCES poi(poi_id) ON DELETE CASCADE,
    street_address VARCHAR(150),
    city VARCHAR(150),
    postal_code VARCHAR(20),
    department VARCHAR(100),
    region VARCHAR(100)
);

CREATE TABLE contact (
    poi_id INT PRIMARY KEY REFERENCES poi(poi_id) ON DELETE CASCADE,
    phone VARCHAR(100),
    website TEXT
);

ALTER TABLE poi ADD poi_kind VARCHAR(20) NOT NULL DEFAULT 'attraction';

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE saved_itineraries (
    itinerary_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE itinerary_stops (
    stop_id SERIAL PRIMARY KEY,
    itinerary_id INT REFERENCES saved_itineraries(itinerary_id) ON DELETE CASCADE,
    poi_uuid VARCHAR(64) REFERENCES poi(uuid) ON DELETE CASCADE,
    day_number INT NOT NULL,
    stop_order INT NOT NULL
);