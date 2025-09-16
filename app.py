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

# ------------------------------------------------------------------
# Planned progress numbers (user‑provided)
current_market_rental     = int(df_valid['Market Rate Rentals'].sum())
current_affordable_rental = int(df_valid['Affordable Rentals'].sum())
planned_rental = current_market_rental + current_affordable_rental
rental_deficit            = max(0, RENTAL_GOAL - planned_rental)


# ------------------------------------------------------------------
# -----  UI  -----
st.title("Portsmouth, NH Housing Dashboard")
st.caption(
    "Tracking rental unit goals based on the "
    "[2022 PHA‑commissioned housing study](https://www.portsmouthhousing.org/_files/ugd/64e8bc_2e66b26dbb564a2980246fdee6907b78.pdf)."
)

# --- 1️⃣  Top metrics row
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Rental Units Planned / Goal for 2030",
              f"{planned_rental:,} / {RENTAL_GOAL}",
              f"{(planned_rental/RENTAL_GOAL)*100:0.1f}%")
with col2:
    st.metric("Units Still Needed",
              f"{rental_deficit:,}",
              delta=f"Need {int(rental_deficit)} more units by 2030", delta_color="inverse")
    



with col3:
    pct_market = (current_market_rental / planned_rental * 100) if planned_rental else 0
    st.metric("Market‑Rate Rentals",
              f"{current_market_rental:,}",
              f"{pct_market:0.1f}% of total")
with col4:
    pct_affordable = (current_affordable_rental / planned_rental * 100) if planned_rental else 0
    st.metric("Non‑Market (Affordable) Rentals",
              f"{current_affordable_rental:,}",
              f"{pct_affordable:0.1f}% of total")

# --- 1️⃣  Rental progress chart
st.subheader("Rental Housing Pipeline")

rental_fig = go.Figure()

# Stacked bars: market vs non‑market rentals
rental_fig.add_trace(go.Bar(
    x=yearly_complete['Move-in Year'],
    y=yearly_complete['Market Rentals'],
    name="Market‑Rate",
    marker_color="#1f77b4"
))
rental_fig.add_trace(go.Bar(
    x=yearly_complete['Move-in Year'],
    y=yearly_complete['Non-Market Rentals'],
    name="Non‑Market (Affordable)",
    marker_color="#ff7f0e"
))

# Cumulative line
rental_fig.add_trace(go.Scatter(
    x=yearly_complete['Move-in Year'],
    y=yearly_complete['Cumulative Rentals'],
    mode="lines+markers",
    name="Cumulative Rentals",
    line=dict(width=3, color="black")
))

# Goal trendline (straight line from 2024 to 2030)
rental_fig.add_trace(go.Scatter(
    x=[GOAL_START_YEAR, TARGET_YEAR],
    y=[0, RENTAL_GOAL],
    mode="lines",
    name="Goal trajectory",
    line=dict(width=2, dash="dash", color="navy")
))

# Layout tweaks
rental_fig.update_layout(
    barmode="stack",
    xaxis_title="Year",
    yaxis_title="Units",
    legend=dict(orientation="h", y=-0.25),
    height=500,
    margin=dict(l=20, r=20, t=30, b=30),
)

st.plotly_chart(rental_fig, 
                use_container_width=True,                
                config={
    "displayModeBar": False,    
    "staticPlot": True
    },)



# --- 1️⃣ Development Locations
st.markdown("---")

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

st.header("Development Locations")

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


# Market Rate vs. Affordable Housing
st.header("Market Rate vs. Affordable Housing")


# Create two-column layout
col1, col2 = st.columns([1, 1])

with col1:
    # Create a pie chart of total affordable vs market rate
    affordability_data = pd.DataFrame({
        "Housing Type": ["Market Rate Units", "Affordable Units"],
        "Count": [current_market_rate, current_affordable]
    })
    
    affordability_fig = px.pie(
        affordability_data, 
        values="Count", 
        names="Housing Type",
        title="Market Rate vs. Affordable Distribution",
        color_discrete_map={"Market Rate Units": "#1E88E5", "Affordable Units": "#FFC107"},
        hole=0.4
    )
    
    affordability_fig.update_layout(height=400)
    st.plotly_chart(affordability_fig, use_container_width=True, config={
    "displayModeBar": False,    
    "staticPlot": True
    },)
    
with col2:
    # Create a bar chart showing affordability by project status
    affordability_by_status = df.groupby("Status").agg({
        "Market Rate Units": "sum",
        "Affordable Units": "sum"
    }).reset_index()
    
    affordability_status_fig = px.bar(
        affordability_by_status,
        x="Status",
        y=["Market Rate Units", "Affordable Units"],
        title="Affordability by Project Status",
        barmode="stack",
        category_orders={"Status": ["Potential", "Concept", "Design", "Permitting", "Approved", "Under construction"]},
        color_discrete_map={"Market Rate Units": "#1E88E5", "Affordable Units": "#FFC107"}
    )

    affordability_status_fig.update_layout(height=400)
    st.plotly_chart(affordability_status_fig, use_container_width=True, config={
    "displayModeBar": False,    
    "staticPlot": True
    },)

# Project table with affordability percentages
st.subheader("Housing Projects by Affordability")

# Create a sorted dataframe for the table
affordable_table = df[~(df["Total units"] == 0)].copy()
affordable_table = affordable_table[["Project", "Total units", "Market Rate Units", 
                                     "Affordable Units", "Affordability Ratio", "Status", "Occupancy"]]
affordable_table = affordable_table.sort_values("Affordability Ratio", ascending=False)

# Add a column for affordability category
def categorize_affordability(ratio):
    if ratio > 0:            
        return "Affordable"
    else:
        return "Market Rate Only"

affordable_table["Affordability Category"] = affordable_table["Affordability Ratio"].apply(categorize_affordability)

# Display the table
st.dataframe(
    affordable_table[["Project", "Total units", "Affordable Units", 
                      "Affordability Ratio", "Affordability Category", "Status", "Occupancy"]],
    column_config={
        "Project": "Project Name",
        "Total units": "Total Units",
        "Affordable Units": "Affordable Units",
        "Affordability Ratio": st.column_config.NumberColumn(
            "Affordability %",
            format="%.1f%%"
        ),
        "Affordability Category": "Category",
        "Status": "Status",
        "Occupancy": "Expected Completion"
    },
    height=400
)



# ------------------------------------------------------------------
# 2️⃣  Market trends row (unchanged from v2)
st.markdown("---")
st.subheader("Housing Market Trends")

colA, colB = st.columns(2)
years = [2020, 2021, 2022, 2023, 2024, 2025]

with colA:
    median_rent_2br = [2000, 2150, 2250, 2350, 2450, 2550]

    rent_fig = go.Figure()
    rent_fig.add_trace(go.Scatter(
        x=years,
        y=median_rent_2br,
        mode="lines+markers",
        name="Median 2‑BR Rent",
        line=dict(width=3)
    ))

    pct_r_increase = (median_rent_2br[-1] - median_rent_2br[0]) / median_rent_2br[0] * 100

    rent_fig.update_layout(
        title=f"Median 2‑Bedroom Rent (↑{pct_r_increase:.1f}% since 2020)",
        xaxis_title="Year",
        yaxis_title="Monthly Rent ($)",
        yaxis=dict(tickformat="$,.0f"),
        height=450
    )
    st.plotly_chart(rent_fig, use_container_width=True, config={
    "displayModeBar": False,    
    "staticPlot": True
    },)

with colB:    
    median_home_prices = [650_000, 720_000, 775_000, 830_000, 850_000, 859_000]

    sale_fig = go.Figure()
    sale_fig.add_trace(go.Scatter(
        x=years,
        y=median_home_prices,
        mode="lines+markers",
        name="Median Sale Price",
        line=dict(width=3)
    ))

    pct_h_increase = (median_home_prices[-1] - median_home_prices[0]) / median_home_prices[0] * 100

    sale_fig.update_layout(
        title=f"Median Home Sale Price (↑{pct_h_increase:.1f}% since 2020)",
        xaxis_title="Year",
        yaxis_title="Price ($)",
        yaxis=dict(tickformat="$,.0f"),
        height=450
    )
    st.plotly_chart(sale_fig, use_container_width=True, config={
    "displayModeBar": False,    
    "staticPlot": True
    },)

st.markdown("""
    **Key Home Price Trends**
    - Portsmouth median house value is $859,324, making it among the most expensive real estate in New Hampshire and America
    - The median sale price was $850K in January 2025, up 13.3% from the previous year
    - Portsmouth home prices increased by 10.2% year-over-year in February 2025
    """)
    
st.markdown('''
**Data Sources**  
- [Zillow Housing Data](https://www.zillow.com/research/data/)  
- [Redfin Data Center](https://www.redfin.com/news/data-center/)  
- [Zumper National Rent Report](https://www.zumper.com/blog/category/rental-price-data/)  

_Figures above use publicly released aggregate data for illustrative purposes._
''')

