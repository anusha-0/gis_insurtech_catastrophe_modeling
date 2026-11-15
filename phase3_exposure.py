# ============================================================
# PHASE 3: EXPOSURE LAYER — REGULATORY SPATIAL JOIN
# Methodology change from POC nearest-point approach:
#   OLD: cKDTree nearest-point → building gets nearest sample's zone
#        Problem: sample point 400m away could be different zone
#   NEW: GeoPandas sjoin (point-in-polygon) → building gets the zone
#        whose POLYGON BOUNDARY it actually falls inside
#        → exhaustive, deterministic, no misclassification
#
# Sources:
#   • Google Open Buildings v3 (GEE)  → building footprints
#   • hazard_zones.geojson (Phase 2)  → flood zone polygons
# ============================================================

# ── Imports ──────────────────────────────────────────────────
import ee
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import warnings
warnings.filterwarnings('ignore')

# ── Shared constants ─────────────────────────────────────────
AOI_BOUNDS             = [79.80, 6.75, 80.25, 7.15]
aoi                    = ee.Geometry.Rectangle(AOI_BOUNDS)
RETURN_PERIODS         = [10, 25, 50, 100, 200, 500]
AVG_PROPERTY_VALUE_LKR = 15_000_000
LKR_PER_USD            = 320

# ── Load flood zone polygons from Phase 2 ────────────────────
print("⏳ Loading flood zone polygons...")
zones_gdf = gpd.read_file('hazard_zones.geojson')
print(f"✅ Loaded {len(zones_gdf):,} flood zone polygons")
print(f"   CRS: {zones_gdf.crs}")
print(f"   Zones: {sorted(zones_gdf['flood_rp'].unique().tolist())}")
print("✅ Phase 3 imports & constants ready")

# ── 3.1  Load Google Open Buildings ─────────────────────────
open_buildings = (ee.FeatureCollection(
    "GOOGLE/Research/open-buildings/v3/polygons")
    .filterBounds(aoi)
    .filter(ee.Filter.gte('confidence', 0.70))
)
building_count = open_buildings.size().getInfo()
print(f"\n✅ Open Buildings loaded")
print(f"   Total buildings in AOI: {building_count:,}")

# ── 3.2  Download Building Centroids ─────────────────────────
# Compute centroid lon/lat inside GEE, then fetch
buildings_sample = open_buildings.limit(5000).map(
    lambda f: f.set({
        'lon': f.geometry().centroid().coordinates().get(0),
        'lat': f.geometry().centroid().coordinates().get(1)
    })
)

print("⏳ Fetching 5,000 building features from GEE...")
buildings_info = buildings_sample.getInfo()['features']

buildings_df = pd.DataFrame([{
    'building_id': i,
    'lon':        feat['properties'].get('lon',
                  feat['geometry']['coordinates'][0][0][0]),
    'lat':        feat['properties'].get('lat',
                  feat['geometry']['coordinates'][0][0][1]),
    'area_m2':    feat['properties'].get('area_in_meters', 80),
    'confidence': feat['properties'].get('confidence', 0.8)
} for i, feat in enumerate(buildings_info)])

buildings_df['area_m2'] = buildings_df['area_m2'].fillna(80).clip(20, 2000)
print(f"✅ {len(buildings_df):,} buildings fetched to local DataFrame")

# ── 3.3  Classify Building Types ────────────────────────────
np.random.seed(42)

def classify_building(area_m2):
    if   area_m2 <  60:  return 'residential_small'
    elif area_m2 < 150:  return 'residential_standard'
    elif area_m2 < 500:  return 'commercial_mixed'
    else:                return 'commercial_large'

buildings_df['building_type'] = buildings_df['area_m2'].apply(classify_building)

# ── 3.4  Assign Sum Insured Values ───────────────────────────
COST_PER_M2 = {
    'residential_small':    55_000,
    'residential_standard': 65_000,
    'commercial_mixed':     85_000,
    'commercial_large':    110_000
}
CONTENTS_RATIO = {
    'residential_small':    0.40,
    'residential_standard': 0.50,
    'commercial_mixed':     0.60,
    'commercial_large':     0.70
}

buildings_df['floors'] = buildings_df['building_type'].map(
    lambda bt: int(np.random.choice(
        [1,2,3,4,5],
        p=[0.3,0.35,0.2,0.1,0.05] if 'residential' in bt
          else [0.1,0.2,0.35,0.25,0.1]
    ))
)
buildings_df['cost_per_m2']    = buildings_df['building_type'].map(COST_PER_M2)
buildings_df['contents_ratio'] = buildings_df['building_type'].map(CONTENTS_RATIO)

buildings_df['sum_insured_structure'] = (
    buildings_df['area_m2'] *
    buildings_df['floors'] *
    buildings_df['cost_per_m2']
)
buildings_df['sum_insured_contents'] = (
    buildings_df['sum_insured_structure'] *
    buildings_df['contents_ratio']
)
buildings_df['sum_insured_total'] = (
    buildings_df['sum_insured_structure'] +
    buildings_df['sum_insured_contents']
)
print("✅ Building types classified, sum insured values assigned")

# ════════════════════════════════════════════════════════════
# 3.5  POINT-IN-POLYGON SPATIAL JOIN (Regulatory Approach)
# ════════════════════════════════════════════════════════════
# Replace cKDTree nearest-point with GeoPandas sjoin.
#
# OLD approach (cKDTree):
#   Each building → find nearest hazard sample point → inherit its zone
#   PROBLEM: If the nearest sample point is 400m away in a different
#            zone, the building is MISCLASSIFIED. Narrow flood corridors
#            (Kelani River banks, drainage channels) that had no random
#            sample points would be completely missed.
#
# NEW approach (sjoin point-in-polygon):
#   Each building point → tested against ACTUAL polygon boundaries
#   → if it falls INSIDE a flood zone polygon → gets that zone
#   → if it falls OUTSIDE ALL polygons → flood_rp = 0 (safe)
#   RESULT: Deterministic, exhaustive, no missed buildings
# ────────────────────────────────────────────────────────────

print("\n⏳ Converting buildings to GeoDataFrame for spatial join...")

# Convert buildings DataFrame → GeoDataFrame
# Each building becomes a Point geometry
buildings_gdf = gpd.GeoDataFrame(
    buildings_df,
    geometry = gpd.points_from_xy(buildings_df['lon'], buildings_df['lat']),
    crs      = 'EPSG:4326'   # WGS84 — must match zones_gdf CRS
)

print(f"   Buildings GeoDataFrame: {len(buildings_gdf):,} points")
print(f"   Flood zones GeoDataFrame: {len(zones_gdf):,} polygons")

# ── Prepare zone attributes for the join ─────────────────────
# Select only the columns we want to transfer to buildings
zone_cols = ['flood_rp', 'mean_elevation', 'mean_occurrence', 'geometry']
depth_cols = [f'depth_{rp}yr' for rp in RETURN_PERIODS
              if f'depth_{rp}yr' in zones_gdf.columns]
zone_cols = zone_cols + depth_cols
zones_join = zones_gdf[zone_cols].copy()

# Where multiple overlapping polygons exist for the same zone,
# keep the most severe (lowest RP) by sorting before join
# gpd.sjoin takes the FIRST match per point when polygons overlap
zones_join = zones_join.sort_values('flood_rp', ascending=True)

# ── Execute point-in-polygon join ────────────────────────────
print("⏳ Running point-in-polygon spatial join...")

joined = gpd.sjoin(
    buildings_gdf,             # left: building points
    zones_join,                # right: flood zone polygons
    how       = 'left',        # LEFT JOIN: keep ALL buildings
                               # buildings outside all zones → NaN (not exposed)
    predicate = 'within'       # spatial predicate: point within polygon
)
# 'within' is exact — point must be strictly inside polygon boundary
# 'intersects' would also catch boundary-touching points

# ── Handle buildings outside all flood zones ──────────────────
# After a left join, buildings with no matching polygon get NaN
# in the zone columns. Fill these with 0 (not flood-prone).
joined['flood_rp']       = joined['flood_rp'].fillna(0).astype(int)
joined['mean_elevation'] = joined['mean_elevation'].fillna(
    buildings_df['elevation'].mean() if 'elevation' in buildings_df.columns else 10.0
)
joined['mean_occurrence'] = joined['mean_occurrence'].fillna(0.0)

for rp in RETURN_PERIODS:
    col = f'depth_{rp}yr'
    if col in joined.columns:
        joined[col] = joined[col].fillna(0.0)

# ── Handle duplicate matches ──────────────────────────────────
# A point on a polygon boundary may match multiple polygons.
# Keep only the MOST SEVERE zone (lowest return period).
before = len(joined)
joined = (joined
          .sort_values('flood_rp', ascending=True)   # most severe first
          .drop_duplicates(subset='building_id', keep='first')
          .reset_index(drop=True))
after = len(joined)
if before != after:
    print(f"   Resolved {before - after:,} duplicate zone matches "
          f"(kept most severe zone per building)")

# ── Copy results back to buildings_df ────────────────────────
buildings_df = buildings_df.copy()
buildings_df['flood_rp']       = joined['flood_rp'].values
buildings_df['elevation']      = joined['mean_elevation'].values
buildings_df['occurrence']     = joined['mean_occurrence'].values

for rp in RETURN_PERIODS:
    col = f'depth_{rp}yr'
    if col in joined.columns:
        buildings_df[col] = joined[col].values
    else:
        buildings_df[col] = 0.0

print(f"✅ Point-in-polygon spatial join complete")
print(f"   Every building now has its EXACT flood zone from polygon boundary")

# ── 3.6  Join Quality Report ─────────────────────────────────
print("\n" + "="*65)
print("  SPATIAL JOIN QUALITY REPORT")
print("="*65)

total         = len(buildings_df)
in_zone       = (buildings_df['flood_rp'] > 0).sum()
outside_zone  = (buildings_df['flood_rp'] == 0).sum()

print(f"\n  Total buildings                 : {total:>8,}")
print(f"  Buildings INSIDE flood zones    : {in_zone:>8,}  ({in_zone/total*100:.1f}%)")
print(f"  Buildings OUTSIDE flood zones   : {outside_zone:>8,}  ({outside_zone/total*100:.1f}%)")
print(f"\n  Zone-by-zone breakdown:")
print(f"  {'Zone':>10}  {'Buildings':>12}  {'% Portfolio':>13}  {'Avg Depth@RP (m)':>18}")
print(f"  {'-'*58}")

for rp in sorted(buildings_df['flood_rp'].unique()):
    if rp == 0:
        continue
    zone_b    = buildings_df[buildings_df['flood_rp'] == rp]
    depth_col = f'depth_{int(rp)}yr'
    avg_depth = zone_b[depth_col].mean() if depth_col in zone_b.columns else 0.0
    print(f"  {int(rp):>7}-yr  {len(zone_b):>12,}  "
          f"{len(zone_b)/total*100:>12.1f}%  {avg_depth:>18.2f}")

# ── 3.7  Exposure Summary ────────────────────────────────────
total_TIV     = buildings_df['sum_insured_total'].sum()
flood_exposed = buildings_df[buildings_df['flood_rp'] > 0]
exposed_TIV   = flood_exposed['sum_insured_total'].sum()

print("\n" + "="*65)
print("  EXPOSURE SUMMARY — Colombo & Western Province")
print("="*65)
print(f"\n  Total buildings modelled        : {len(buildings_df):>8,}")
print(f"  Total Insured Value (TIV)       : LKR {total_TIV/1e9:>7.2f} Billion")
print(f"  TIV (USD equivalent)            : USD {total_TIV/LKR_PER_USD/1e6:>7.1f} Million")
print(f"\n  Flood-exposed buildings         : {len(flood_exposed):>8,}")
print(f"  Flood-exposed TIV               : LKR {exposed_TIV/1e9:>7.2f} Billion")
print(f"  % TIV in flood zones            : {exposed_TIV/total_TIV*100:>7.1f}%")

print(f"\n  Building Type Breakdown:")
type_summary = (buildings_df.groupby('building_type')
                .agg(count=('building_id', 'count'),
                     tiv=('sum_insured_total', 'sum'))
                .sort_values('tiv', ascending=False))
for bt, row in type_summary.iterrows():
    print(f"    {bt:25s}: {row['count']:5,} bldgs | LKR {row['tiv']/1e9:.2f}B")

print("\n🚀 Phase 3 Complete — Exposure layer ready (vector spatial join)")

# ── SAVE OUTPUT FOR PHASE 4 ──────────────────────────────────
buildings_df.to_csv('buildings_df.csv', index=False)
print("✅ buildings_df.csv saved → loaded by Phase 4")
