# Holiday Itinerary

A Data Engineering project that builds personalized multi-day travel itineraries based on Points of Interest.

This application extracts tourism data from DATAtourisme API, transforms and stores it in PostgreSQL and Neo4j, applies geographic clustering with KMeans, and generates itineraries based on user preferences, geographic proximity, travel time, and daily time constraints.

## Project Overview

The goal of this project was to build an end-to-end data engineering pipeline for tourism itinerary generation.

The project demonstrates:

- API data extraction
- data cleaning and transformation
- geographic clustering
- relational database modeling
- graph database modeling
- workflow orchestration
- REST API development
- interactive frontend visualization
- containerized deployment
- Apache Airflow orchestration

## Tech Stack

- Python
- Pandas
- Scikit-learn
- PostgreSQL
- Neo4j
- FastAPI
- Streamlit
- Pydeck
- Apache Airflow
- Docker
- Docker Compose
- DATAtourisme API

## Data Pipeline

### 1. Extraction

The extraction pipeline retrieves Points of Interest from the DATAtourisme API.

**It includes:**

- API pagination
- retry logic with exponential backoff
- POI filtering
- POI classification into:
- attractions
- lodging
- food
- raw and filtered dataset exports

**Output:**

    data/raw
    data/interim

### 2. Transformation

Raw POI data is transformed into a clean structured dataset.

**The transformation step extracts:**

- UUID
- label
- POI type
- categories
- estimated visit duration
- description
- latitude
- longitude
- address
- city
- department
- region
- phone
- website
- last update timestamp

**Output:**

    data/processed/pois_clean.csv
    data/processed/pois_clean.json

### 3. Geographical clustering

KMeans clustering is applied using:

    latitude
    longitude

The resulting cluster_id groups geographically close POIs and is later used during itinerary generation.

**Output:**

    data/processed/pois_clustered.csv
    data/processed/pois_clustered.json

## PostgreSQL

PostgreSQL stores structured POI metadata.

**Main tables:**

- poi
- category
- poi_category
- address
- contact

The relational model includes a many-to-many relationship between POIs and categories.
The database is refreshed during each batch pipeline execution.

## Neo4j

Neo4j stores the geographic graph representation of the POIs.

Each POI is represented as a node containing:

- UUID
- label
- POI type
- geographic location
- cluster ID
- estimated visit duration

Nearby POIs are connected through **NEAR_TO** relationships.

Distances are calculated using Neo4j geographic **point.distance()**.

## Itinerary Generation

The user selects:

- hotel
- preferred interests
- number of days
- lunch option
- dinner option

The itinerary generation process:

1. identifies the geographic cluster of the selected hotel
2. selects relevant attraction candidates
3. scores attractions based on user preferences
4. uses Neo4j to find nearby attractions and restaurants
5. estimates travel time between POIs
6. adds lunch and dinner when requested
7. prevents repeated attractions and restaurants
8. respects the daily time limit
9. builds a multi-day itinerary

Travel time estimation:

- distances up to 1 km are treated as walking
- longer distances are estimated using public transport assumptions

## FastAPI

FastAPI provides the backend API.

Main endpoints
    GET /health
    GET /pois
    GET /pois/{poi_uuid}
    GET /categories
    POST /itinerary

Interactive API documentation:

    http://localhost:8000/docs

## Streamlit Application

The Streamlit interface allows users to:

- select a hotel
- select categories that are interesting
- choose trip duration in days
- include or exclude lunch
- include or exclude dinner
- generate an itinerary

The generated itinerary displays:

- daily itinerary tabs
- total time
- total number of stops
- total distance
- interactive map
- route lines between POIs
- visit duration
- travel time
- distance
- description
- address
- phone number
- website link

Streamlit app is available at:

    http://localhost:8501

## Airflow

Apache Airflow orchestrates the daily batch pipeline.

DAG:

    holiday_itinerary_pipeline

Pipeline:

    extract_data
        ↓
    transform_data
        ↓
    cluster_data
    ↙︎         ➘
    load_postgres  load_neo4j

Airflow UI:

    http://localhost:8080

### Airflow login

Username is: admin
After starting the containers, retrieve the generated Airflow password with:

    docker compose exec airflow-webserver \
    cat /opt/airflow/simple_auth_manager_passwords.json.generated

## Project Organisation

    holiday_itinerary_repo/
    ├── data/
    │   ├── raw/
    │   ├── interim/
    │   └── processed/
    │
    ├── neo4j/
    │   └── schema.cypher
    │
    ├── notebooks/
    │   └── k-means.ipynb
    │
    ├── reports/
    │
    ├── sql/
    │   └── schema.sql
    │
    ├── src/
    │   ├── api/
    │   │   └── main.py     
    │   │
    │   ├── dags/
    │   │   └── holiday_itinerary_pipeline.py
    │   │
    │   ├── database/
    │   │   ├── load_sql.py
    │   │   └── load_neo4j.py
    │   │
    │   ├── etl/
    │   │   ├── extract.py
    │   │   └── transform.py
    │   │
    │   ├── itinerary/
    │   │   └── itinerary_logic.py
    │   │
    │   ├── models/
    │   │   └── cluster.py
    │   │
    │   └── streamlit/
    │       └── app.py
    │
    ├── .env.example
    ├── .gitignore
    ├── docker-compose.yaml
    ├── Dockerfile
    ├── Dockerfile.airflow
    ├── requirements.txt
    ├── requirements-airflow.txt
    └── README.md

# Setup
## Prerequisites

Before running the project, make sure you have:

- Git
- Docker
- Docker Compose
- A DATAtourisme API key

**Clone the repository**

    git clone <repository-url>
    cd holiday_itinerary_repo

## Environment variables

Create a .env file based on .env.example you can find in the repository.

## Start the project

    docker compose up -d --build