# ============================================================
# Sri Lanka Flood Catastrophe Model
# IRCSL RBC Framework — POC
# ============================================================

## QUICK START
# 1. Install dependencies:
#    pip install -r requirements.txt
#
# 2. Open Jupyter:
#    jupyter notebook SriLanka_Flood_CatModel_IRCSL.ipynb
#
# 3. In Phase 1, replace:
#    ee.Initialize(project='your-gee-project-id')
#    with your actual GEE project ID
#
# 4. Run all cells top to bottom (Kernel → Restart & Run All)

## PROJECT STRUCTURE
# ├── SriLanka_Flood_CatModel_IRCSL.ipynb  ← MASTER NOTEBOOK (run this)
# ├── phase1_setup.py           ← GEE init, AOI, constants
# ├── phase2_hazard.py          ← Flood zones from JRC GSW + DEM
# ├── phase3_exposure.py        ← Buildings + sum insured from GEE
# ├── phase4_vulnerability.py   ← JRC Huizinga depth-damage curves
# ├── phase5_loss_estimation.py ← Monte Carlo (10,000 years)
# ├── phase6_capital_charge.py  ← EP curve + IRCSL capital charge
# ├── phase7_visualization.py   ← Maps + charts
# ├── requirements.txt          ← Python dependencies
# └── README.py                 ← This file

## WHAT THIS PRODUCES
# flood_hazard_exposure_map.html  → Interactive Folium map
# fig1_depth_damage_curves.png    → JRC vulnerability curves
# fig2_ep_curve.png               → EP curve + capital charge plot
# fig3_loss_distribution_dashboard.png → Full dashboard
# ep_curve.csv                    → Raw EP curve data (for actuaries)

## IRCSL FRAMEWORK REFERENCE
# Document: "Review of Risk-Based Capital — Public Consultation"
# Date: 23 July 2025
# Pages: 36–38 (Catastrophe Risk Capital Charge)
#
# Key formula:
#   CAT Capital Charge = OEP(1-in-200yr) − Mean Annual Loss
#   = 99.5th percentile of annual loss distribution − MAL
#
# Alternative (simpler, no model needed):
#   CAT Capital = 0.05% × Total Sum Insured for flood-exposed properties

## DATA SOURCES (all open source / free)
# ┌─────────────────────────────────────────────────────────┐
# │ Layer        │ Dataset                  │ Via           │
# ├─────────────────────────────────────────────────────────┤
# │ Hazard       │ JRC Global Surface       │ Google Earth  │
# │              │ Water v1.4               │ Engine (GEE)  │
# ├─────────────────────────────────────────────────────────┤
# │ Elevation    │ Copernicus GLO-30 DEM    │ GEE           │
# ├─────────────────────────────────────────────────────────┤
# │ Exposure     │ Google Open Buildings v3 │ GEE           │
# ├─────────────────────────────────────────────────────────┤
# │ Vulnerability│ JRC Huizinga et al.2017  │ Published     │
# │              │ (EUR 28552 EN)           │ literature    │
# ├─────────────────────────────────────────────────────────┤
# │ Admin Bounds │ USDOS LSIB               │ GEE           │
# └─────────────────────────────────────────────────────────┘

## GEE DATASETS USED (copy-paste into GEE Code Editor to explore)
# ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
# ee.ImageCollection("COPERNICUS/DEM/GLO30")
# ee.FeatureCollection("GOOGLE/Research/open-buildings/v3/polygons")
# ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")

## KNOWN LIMITATIONS (for POC disclosure)
# 1. Flood depths are estimated from DEM elevation deficit, not
#    full hydrological simulation (HEC-RAS / LISFLOOD etc.)
# 2. Sum insured values are synthetic — use real insurer data in production
# 3. Event catalog has limited events — production needs 10,000+ events
# 4. No storm surge / coastal inundation model included
# 5. No temporal correlation between events (independent Poisson assumed)

## HOW TO IMPROVE FOR PRODUCTION
# 1. Replace depth estimation with GLOFAS / LISFLOOD / HEC-RAS outputs
# 2. Use actual insurer policy database as exposure
# 3. Expand event catalog using historical flood records (DMC Sri Lanka)
# 4. Add coastal flood peril (Kelani estuary, Negombo lagoon)
# 5. Calibrate depth-damage curves with post-disaster survey data
# 6. Get model approved by Appointed Actuary → Submit to IRCSL
