import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from streamlit_folium import folium_static
import folium
from datetime import datetime

st.set_page_config(layout="wide")

# ------------------------------------------------------------------
# Load latest data from Google Sheets (CSV export)
CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1Ua0vVNtBNV5AR-tURo62lneVpeWCzN1J5LnkezCu2E4/"
    "export?format=csv&gid=751536993"
)

@st.cache_data(
    ttl=120,            # invalidate after 2 min
    max_entries=500,     # keep the cache from ballooning
    show_spinner="Loading ..."
)

def load_data(url: str) -> pd.DataFrame:
    return pd.read_csv(url)

df = load_data(CSV_URL).fillna(0)

# ------------------------------------------------------------------
# Housing goals & parameters
RENTAL_GOAL      = 2897   # PHA‑commissioned 2022 study goal
GOAL_START_YEAR  = 2024   # 👈 updated per user request
TARGET_YEAR      = 2030

# Consolidate columns
df['Rental Units']       = df['Market Rate Rentals'] + df['Affordable Rentals']
df['Market Rentals']     = df['Market Rate Rentals']
df['Non-Market Rentals'] = df['Affordable Rentals']  # subsidised / deed‑restricted

# Extract valid move‑in years
df['Move-in Year'] = pd.to_numeric(df['Occupancy'], errors='coerce')
df_valid           = df[~pd.isna(df['Move-in Year'])].copy()

# ---- Yearly aggregates
yearly_data = (
    df_valid
    .groupby('Move-in Year')
    .agg({'Rental Units': 'sum',
          'Market Rentals': 'sum',
          'Non-Market Rentals': 'sum'})
    .reset_index()
    .sort_values('Move-in Year')
)

# Build complete year index to 2030
all_years       = list(range(int(yearly_data['Move-in Year'].min()), TARGET_YEAR + 1))
yearly_complete = (pd.DataFrame({'Move-in Year': all_years})
                   .merge(yearly_data, on='Move-in Year', how='left')
                   .fillna(0))

yearly_complete['Cumulative Rentals'] = yearly_complete['Rental Units'].cumsum()

# --- 1️⃣ Development Locations
# Create columns with consistent unit counts
df["Rental Units"] = df["Market Rate Rentals"] + df["Affordable Rentals"]
df["Owner Units"] = df["Market Rate Owner"] + df["Affordable Owner"]

# Add columns to clearly identify affordability mix
df["Affordable Units"] = df["Affordable Rentals"] + df["Affordable Owner"]
df["Market Rate Units"] = df["Market Rate Rentals"] + df["Market Rate Owner"]
df["Affordability Ratio"] = (df["Affordable Units"] / df["Total units"] * 100).fillna(0).round(1)



# Convert Occupancy to year and ensure it's numeric
df["Move-in Year"] = pd.to_numeric(df["Occupancy"], errors='coerce')

# Filter out rows with invalid years
df_valid = df[~pd.isna(df["Move-in Year"])].copy()

# Group by year
yearly_data = df_valid.groupby("Move-in Year").agg({
    "Rental Units": "sum",
    "Owner Units": "sum",
    "Total units": "sum",
    "Affordable Units": "sum",
    "Market Rate Units": "sum"
}).reset_index()

# Create year range from earliest year to 2030
all_years = list(range(int(yearly_data["Move-in Year"].min()), TARGET_YEAR + 1))
complete_years = pd.DataFrame({"Move-in Year": all_years})

# Merge with actual data
yearly_complete = complete_years.merge(yearly_data, on="Move-in Year", how="left").fillna(0)

# Calculate cumulative sums
yearly_complete["Cumulative Rental"] = yearly_complete["Rental Units"].cumsum()
yearly_complete["Cumulative Owner"] = yearly_complete["Owner Units"].cumsum()
yearly_complete["Cumulative Total"] = yearly_complete["Total units"].cumsum()
yearly_complete["Cumulative Affordable"] = yearly_complete["Affordable Units"].cumsum()
yearly_complete["Cumulative Market Rate"] = yearly_complete["Market Rate Units"].cumsum()

# Show current progress metrics
current_rental = yearly_complete["Cumulative Rental"].iloc[-1] if not yearly_complete.empty else 0
current_owner = yearly_complete["Cumulative Owner"].iloc[-1] if not yearly_complete.empty else 0
current_affordable = yearly_complete["Cumulative Affordable"].iloc[-1] if not yearly_complete.empty else 0
current_market_rate = yearly_complete["Cumulative Market Rate"].iloc[-1] if not yearly_complete.empty else 0

st.header("Portsmouth Housing Pipeline")

# Create columns for map and legend
map_col, legend_col = st.columns([5, 1])

with map_col:
    # Create a map centered on Portsmouth with a neutral color palette
    m = folium.Map(
        location=[43.07, -70.79], 
        zoom_start=13,
        tiles="CartoDB positron",  # Neutral grayscale base map
        )
    

    # Function to handle None/NaN values
    def safe_str(value):
        if pd.isna(value) or value == 0 or value is None:
            return "N/A"
        return str(value)

    # Function to create HTML link if URL exists
    def create_link(url, text):
        if pd.isna(url) or url == 0 or url is None or url == "":
            return "N/A"
        return f'<a href="{url}" target="_blank">{text}</a>'

    # Color mapping based on affordability
    def get_marker_color(row):            
        if row["Affordability Ratio"] > 0:
            return "orange"  # affordability
        else:
            return "blue"    # Market rate only
        
    # Add markers for each project
    for _, row in df.iterrows():
        # Skip if no location data
        if pd.isna(row["Latitude"]) or pd.isna(row["Longitude"]):
            continue
        
        # Prepare market rate status
        market_rate_status = "N/A"
        if not pd.isna(row["Market rate"]):
            market_rate_status = row["Market rate"]
        
        # Calculate affordability percentage for this project
        affordability = row["Affordability Ratio"]
        
        # Create enhanced popup content with links
        popup_html = f"""
        <div style="width: 320px; overflow-wrap: break-word;">
            <h4>{row['Project']}</h4>
            <b>Address:</b> {safe_str(row['Property address'])}<br>
            <b>Status:</b> {safe_str(row['Status'])}<br>
            <b>Move-in:</b> {safe_str(row['Occupancy'])}<br>
            <hr>
            <b>Housing Units:</b><br>
            <table style="width:100%">
                <tr>
                    <td>Market Rate Units:</td>
                    <td>{int(row['Market Rate Units'])}</td>
                </tr>
                <tr>
                    <td>Affordable Units:</td>
                    <td>{int(row['Affordable Units'])}</td>
                </tr>
                <tr>
                    <td><b>Total Units:</b></td>
                    <td><b>{int(row['Total units'])}</b></td>
                </tr>
                <tr>
                    <td><b>Affordability:</b></td>
                    <td><b>{affordability:.1f}%</b></td>
                </tr>
            </table>
            <hr>
            <b>Market Rate:</b> {market_rate_status}<br>
            <b>City Project Info:</b> {create_link(row['City project info'], 'View Details')}<br>
            <b>Media Coverage:</b> {create_link(row['Media'], 'News Article')}<br>
            <br>
            {safe_str(row['Notes'])}
        </div>
        """
        
        # Use icon colors to distinguish between affordability levels
        folium.Marker(
            [row["Latitude"], row["Longitude"]],
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=row['Project'],  # Show project name on hover
            icon=folium.Icon(color=get_marker_color(row))
        ).add_to(m)

    # Make map full width within its column
    folium_static(m, width=1000, height=500)

with legend_col:
    # Create a visual legend next to the map
    st.markdown("### Map Legend")
    
    # Project type colors
    st.markdown("""
    #### Affordability Levels:
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <div style="width: 20px; height: 20px; background-color: orange; border-radius: 50%; margin-right: 10px;"></div>
        <div>Permanently Affordable</div>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 10px;">
        <div style="width: 20px; height: 20px; background-color: skyblue; border-radius: 50%; margin-right: 10px;"></div>
        <div>Market Rate Only</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Usage instructions
    st.markdown("""
    #### How to Use:
    - **Click** on any marker to see project details
    - **Hover** over markers to see project names
    - Links in popups open in new tabs
    """)
