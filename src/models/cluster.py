"""
Gographical clustering of Poits of Interest

This module reads the cleaned POI's, applies KMeans clustering
using latitude & longitude and then exports a new dataset 
containing cluster_id for all POIs.
"""

import pandas as pd
from sklearn.cluster import KMeans
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PATH_TO_FILE = PROJECT_ROOT / "data" / "processed" / "pois_clean.csv"
OUTPUT_CSV_PATH = (PROJECT_ROOT / "data" / "processed" / "pois_clustered.csv")
OUTPUT_JSON_PATH = (PROJECT_ROOT / "data" / "processed" / "pois_clustered.json")

# The number of clusters was selected using the elbow method during exploratory analysis.
N_CLUSTERS = 5

def load_data():
    return pd.read_csv(PATH_TO_FILE)

def cluster_pois(df):
    """
    Assign a geographical cluster to each POI by using latitude and longitude.
    
    Args:
        df - Cleaned POI dataset

    Returns:
        pandas.DataFrame - Dataframe cointaining the cluster_id column
    """
    X = df[["latitude", "longitude"]]

    model = KMeans(
        n_clusters=N_CLUSTERS,
        random_state=42,
        n_init="auto"
    )

    df["cluster_id"] = model.fit_predict(X)

    return df

def save_data(df):
    df.to_csv(
        OUTPUT_CSV_PATH,
        index=False
    )

    df.to_json(
        OUTPUT_JSON_PATH,
        orient="records",
        force_ascii=False,
        indent=2,
        date_format="iso"
    )

def main():
    print("Loading cleaned POI dataset...")
    df = load_data()

    print(f"Loaded {len(df)} POIs")

    print("Applying KMeans clustering")
    df = cluster_pois(df)

    print("Cluster distribution:")
    print(df["cluster_id"].value_counts().sort_index())

    print("Saving clustered dataset...")
    save_data(df)

if __name__ == "__main__":
    main()