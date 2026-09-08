DROP TABLE IF EXISTS poi_review_label, review_label, contact, address, poi_category, category, poi;

CREATE TABLE poi (
    poi_id SERIAL PRIMARY KEY,
    uuid VARCHAR(64) UNIQUE NOT NULL,
    label VARCHAR(500),
    description TEXT,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    estimated_duration_min INT,
    last_update DATE
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