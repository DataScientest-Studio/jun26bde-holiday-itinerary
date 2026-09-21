"""
Streamlit application for holiday itinerary.
 
Allows user to select his hotel (starting point), interests,
trip duration, and choose weather to include diner and lunch.
 
Visualises the trip and gives information about places to visit.
Gives the option to save the trip by user entering their email address,
which is later retirevable.
"""

import requests
import streamlit as st
import os
import pandas as pd
import pydeck as pdk


API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1100px;
        margin: 0 auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Holiday Itinerary Planner")
st.caption("Plan a personalized itinerary based on your hotel and interests.")

# View saved trips
with st.expander("📂 View My Saved Trips", expanded=False):
    col_email_load, col_btn_load = st.columns([3, 1])
    with col_email_load:
        load_email = st.text_input(
            "Enter your email to load saved trips:",
            key="load_email_input",
            placeholder="user@example.com"
        )
    with col_btn_load:
        st.write("")
        st.write("")
        load_clicked = st.button("Load Trips", use_container_width=True)
 
    if load_clicked:
        if not load_email:
            st.warning("Please enter an email address.")
        else:
            load_res = requests.get(f"{API_URL}/itineraries/{load_email}")
            if load_res.status_code == 200:
                saved_trips = load_res.json()
                if not saved_trips:
                    st.info("No saved trips found for this email.")
                else:
                    st.success(f"Found {len(saved_trips)} saved trip(s)!")
                    for idx, trip in enumerate(saved_trips):
                        with st.container(border=True):
                            st.subheader(f"Trip {idx + 1} (Saved on {trip['created_date']})")
 
                            # Group stops by day
                            days = {}
                            for stop in trip["stops"]:
                                day = stop["day_number"]
                                if day not in days:
                                    days[day] = []
                                days[day].append(stop)
 
                            # Display stops for each day
                            for day, stops in days.items():
                                st.write(f"**Day {day}**")
                                for stop in stops:
                                    street = stop.get("street_address") or ""
                                    city = stop.get("city") or ""
                                    location_str = ", ".join(part for part in [street, city] if part)
                                    if not location_str:
                                        location_str = "Unknown location"
                                    st.caption(f"{stop['stop_order']}. **{stop['label']}** — 📍 {location_str}")
            else:
                error_msg = load_res.json().get("detail", "Unknown error")
                st.error(f"Failed to load trips. Error: {error_msg}")

st.divider()


# Load hotels
hotels_response = requests.get(
    f"{API_URL}/pois", params={"poi_kind": "lodging", "limit": 200}
)
 
hotels = hotels_response.json()
 
hotel_options = {hotel["label"]: hotel["uuid"] for hotel in hotels}
 
# Load categories
categories_response = requests.get(
    f"{API_URL}/categories", params={"poi_kind": "attraction"}
)
 
categories = categories_response.json()
 
 
# User input
col1, col2 = st.columns(2)
with col1:
    selected_hotel = st.selectbox("Choose your hotel", list(hotel_options.keys()))
 
    selected_categories = st.multiselect("Choose your interests", categories)
with col2:
    days = st.number_input("Number of days", min_value=1, max_value=7, value=2)
 
    lunch = st.checkbox("Include lunch", value=True)
 
    dinner = st.checkbox("Include dinner", value=True)

# Generate itinerary
if st.button("Generate itinerary", type="primary"):
    payload = {
        "hotel_uuid": hotel_options[selected_hotel],
        "preferred_categories": selected_categories,
        "days": days,
        "lunch": lunch,
        "dinner": dinner,
    }
 
    response = requests.post(f"{API_URL}/itinerary", json=payload)
 
    if response.status_code != 200:
        error = response.json()
        st.error(error.get("detail", "Could not generate itinerary"))
 
    else:
        st.session_state["current_itinerary"] = response.json()

if "current_itinerary" in st.session_state:
    itinerary = st.session_state["current_itinerary"]
 
    map_points = []
 
    for day in itinerary:
        order = 1
 
        for poi in day["pois"]:
            if poi.get("latitude") is not None and poi.get("longitude") is not None:
                map_points.append(
                    {
                        "lat": poi["latitude"],
                        "lon": poi["longitude"],
                        "label": poi["label"],
                        "day": day["day"],
                        "order": order,
                    }
                )
 
                order += 1
 
    map_df = pd.DataFrame(map_points)
 
    tab_labels = [f"Day {day['day']}" for day in itinerary]
    tabs = st.tabs(tab_labels)
 
    for tab, day in zip(tabs, itinerary):
        with tab:
            total_minutes = day["total_minutes"]
            hours = total_minutes // 60
            minutes = total_minutes % 60
 
            total_distance = sum(poi.get("distance_km", 0) for poi in day["pois"])
 
            c1, c2, c3 = st.columns(3)
 
            c1.metric("Total time", f"{hours}h {minutes}m")
            c2.metric("Stops", len(day["pois"]))
            c3.metric("Distance", f"{total_distance:.1f} km")
 
            day_map_df = (
                map_df[map_df["day"] == day["day"]].reset_index(drop=True)
                if not map_df.empty
                else map_df
            )
 
            day_map_df["order"] = day_map_df["order"].astype(str)
 
            if not day_map_df.empty:
                routes = []
 
                for i in range(len(day_map_df) - 1):
                    routes.append(
                        {
                            "from_lon": day_map_df.iloc[i]["lon"],
                            "from_lat": day_map_df.iloc[i]["lat"],
                            "to_lon": day_map_df.iloc[i + 1]["lon"],
                            "to_lat": day_map_df.iloc[i + 1]["lat"],
                        }
                    )
 
                point_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=day_map_df,
                    get_position="[lon, lat]",
                    get_radius=170,
                    get_fill_color=[220, 60, 60, 200],
                    get_line_color=[255, 255, 255],
                    line_width_min_pixels=2,
                    stroked=True,
                    pickable=True,
                )
 
                text_layer = pdk.Layer(
                    "TextLayer",
                    data=day_map_df,
                    get_position="[lon, lat]",
                    get_text="order",
                    get_size=15,
                    get_color=[255, 255, 255],
                    get_alignment_baseline="'center'",
                    get_text_anchor="'middle'",
                    pickable=True,
                )
 
                route_layer = pdk.Layer(
                    "LineLayer",
                    data=routes,
                    get_source_position="[from_lon, from_lat]",
                    get_target_position="[to_lon, to_lat]",
                    get_width=4,
                    get_color=[40, 100, 220],
                )
 
                view_state = pdk.ViewState(
                    latitude=day_map_df["lat"].mean(),
                    longitude=day_map_df["lon"].mean(),
                    zoom=12.5,
                )
 
                deck = pdk.Deck(
                    layers=[route_layer, point_layer, text_layer],
                    map_style="light",
                    initial_view_state=view_state,
                    tooltip={"text": "{order}. {label}"},
                )
 
                st.subheader("Itinerary map")
                st.pydeck_chart(deck)
 
                for index, poi in enumerate(day["pois"], start=1):
                    with st.container(border=True):
                        if poi["poi_kind"] == "food":
                            st.caption(poi["meal_type"].title())
                            st.subheader(f"{index}. {poi['label']}")
                        else:
                            st.subheader(f"{index}. {poi['label']}")
 
                        street = poi.get("street_address") or ""
                        city = poi.get("city") or ""
 
                        st.caption(f"📍 {street}, {city}")
 
                        c1, c2, c3 = st.columns(3)
 
                        with c1:
                            st.write("**Travel**")
                            st.write(f"{poi['travel_minutes']} min")
 
                        with c2:
                            st.write("**Visit**")
                            st.write(f"{poi['estimated_duration_min']} min")
 
                        with c3:
                            st.write("**Distance**")
                            st.write(f"{poi['distance_km']:.2f} km")
 
                        if poi.get("description"):
                            st.write("**Description**")
                            st.write(poi["description"])
 
                        bottom_left, bottom_right = st.columns([6, 1])
 
                        with bottom_left:
                            if poi.get("phone"):
                                st.write(f"☏ Phone: {poi['phone']}")
 
                        with bottom_right:
                            if poi.get("website"):
                                st.link_button(
                                    "Visit website",
                                    poi["website"],
                                    icon=":material/arrow_forward:",
                                    type="primary",
                                )

# Save current trip
if "current_itinerary" in st.session_state:
    st.divider()
    st.subheader("💾 Save This Itinerary")
 
    col_email, col_button = st.columns([3, 1])
    with col_email:
        email_input = st.text_input(
            "Enter your email address to save this trip:",
            key="save_email_input",
            placeholder="user@example.com",
        )
 
    with col_button:
        st.write("")
        st.write("")
        save_clicked = st.button("Save Trip", use_container_width=True)
 
    if save_clicked:
        if not email_input:
            st.warning("Please enter an email address.")
        else:
            save_payload = {
                "email": email_input,
                "itinerary": st.session_state["current_itinerary"],
            }
            save_res = requests.post(
                f"{API_URL}/itineraries/save", json=save_payload
            )
 
            if save_res.status_code == 200:
                st.success("Trip saved successfully! You can view it later at the top of the page.")
            else:
                error_msg = save_res.json().get("detail", "Unknown error")
                st.error(f"Failed to save trip. Error: {error_msg}")