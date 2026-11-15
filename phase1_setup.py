# ============================================================
# PHASE 1: SETUP & CONFIGURATION
# Sri Lanka Flood Catastrophe Model – Insurance Capital POC
# Colombo & Western Province
# ============================================================

# ── 1.1  Install required packages (run once in terminal) ───
# pip install earthengine-api geemap folium geopandas matplotlib
#             scipy numpy pandas shapely branca

# ── 1.2  Imports ────────────────────────────────────────────
import ee
import geemap
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from scipy import stats
from scipy.interpolate import interp1d
import folium
from folium import plugins
import json
import warnings
warnings.filterwarnings('ignore')

print("✅ All imports successful")

# ── 1.3  Authenticate & Initialize Google Earth Engine ──────
# If first time: run ee.Authenticate() first, then ee.Initialize()
ee.Authenticate()
ee.Initialize(project='earthengine-project-487507')   # ← Replace with your GEE project ID
print("✅ GEE initialized")

# ── 1.4  Define Area of Interest ────────────────────────────
# Colombo + Western Province, Sri Lanka
# Bounding box: [west, south, east, north]
AOI_BOUNDS = [79.80, 6.75, 80.25, 7.15]

aoi = ee.Geometry.Rectangle(AOI_BOUNDS)

# Also define as a GeoDataFrame for local operations
from shapely.geometry import box
aoi_gdf = gpd.GeoDataFrame(
    geometry=[box(*AOI_BOUNDS)],
    crs="EPSG:4326"
)

print(f"✅ AOI defined → Colombo & Western Province")
print(f"   Bounds: {AOI_BOUNDS}")

# ── 1.5  Global Constants ────────────────────────────────────
# Return periods we model (years)
# The six flood return periods you model — in years. A 10-year return period means a flood with a 10% chance of occurring in any given year. A 200-year RP means 0.5% annual chance. These are the "levels of severity" your model will analyse. The 200-year is the one IRCSL uses for the capital charge.
RETURN_PERIODS = [10, 25, 50, 100, 200, 500]

# Exceedance probabilities (EP = 1/RP)
# Converts return periods to annual exceedance probabilities. This is a list comprehension — for each rp in your list, it calculates 1/rp. Result: [0.1, 0.04, 0.02, 0.01, 0.005, 0.002]. These are the probabilities that a flood of that severity or worse occurs in any single year.
EP_VALUES = [1/rp for rp in RETURN_PERIODS]

# Number of Monte Carlo years to simulate
# will simulate 10,000 years of flood history(same as writing 10,000). More years = more stable results. In production cat models, this is often 100,000+
N_SIMULATIONS = 10_000

# Average insured property value (LKR) for POC
# Western Province avg residential property ~LKR 10–25 million
# Sets the average insured property value at LKR 15 million. This is used as a reference benchmark. Western Province residential replacement costs range from LKR 10M–25M, so 15M is a reasonable midpoint for a POC
AVG_PROPERTY_VALUE_LKR = 15_000_000   # LKR 15 million

# Exchange rate for reporting (LKR to USD, approximate)
# Exchange rate for converting results to USD in reports. As of late 2024/early 2025, approximately 320 LKR = 1 USD. Used only for display purposes — all calculations happen in LKR.
LKR_PER_USD = 320

print(f"✅ Constants set: {N_SIMULATIONS:,} simulations, {len(RETURN_PERIODS)} return periods")
print("\n🚀 Phase 1 Complete — Ready to build hazard layer")
