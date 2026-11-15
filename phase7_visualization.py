# ============================================================
# PHASE 7: VISUALIZATION
# ============================================================

# ── Imports (each phase is fully self-contained) ─────────────
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from scipy import stats
import folium
from folium import plugins
import warnings
warnings.filterwarnings('ignore')

# ── Shared constants ──────────────────────────────────────────
RETURN_PERIODS = [10, 25, 50, 100, 200, 500]
N_SIMULATIONS  = 10_000
LKR_PER_USD    = 320

print("✅ Phase 7 imports & constants ready")

# ── Load all outputs from previous phases ────────────────────
import json
buildings_df  = pd.read_csv("buildings_df_with_dr.csv")
annual_losses = np.load("annual_losses.npy")
annual_losses_b = annual_losses / 1e9
hazard_df     = pd.read_csv("hazard_df.csv")
ep_curve_df   = pd.read_csv("ep_curve.csv")
with open("capital_summary.json") as f:
    _cs = json.load(f)
MAL = _cs["MAL"]; OEP_10 = _cs["OEP_10"]; OEP_50 = _cs["OEP_50"]
OEP_100 = _cs["OEP_100"]; OEP_200 = _cs["OEP_200"]; OEP_500 = _cs["OEP_500"]
CAPITAL_CHARGE = _cs["CAPITAL_CHARGE"]; TIV = _cs["TIV"]
capital_charge_pct_TIV = _cs["capital_charge_pct_TIV"]
DAMAGE_UNCERTAINTY_SIGMA = 0.4
BASE_DEPTHS = {10:0.30, 25:0.55, 50:0.85, 100:1.20, 200:1.65, 500:2.20}
print(f"✅ All data loaded: {len(buildings_df):,} buildings, {len(annual_losses):,} sim years")
print(f"   MAL=LKR {MAL/1e9:.3f}B | OEP200=LKR {OEP_200/1e9:.3f}B | Capital=LKR {CAPITAL_CHARGE/1e9:.3f}B")
# ============================================================

# ── 7.1  Interactive Folium Map ──────────────────────────────
print("Building interactive flood hazard + exposure map...")

# Centre on Colombo
MAP_CENTER = [6.93, 79.85]
m = folium.Map(
    location=MAP_CENTER,
    zoom_start=12,
    tiles='CartoDB positron',
    attr='Map tiles by CartoDB'
)

# ── Flood Zone Layer ──────────────────────────────────────
# Colour scheme: blue gradient by RP severity
ZONE_COLORS = {
    10:  ('#d32f2f', 'red',         '1-in-10yr  (Very High Risk)'),
    25:  ('#f57c00', 'orange',      '1-in-25yr  (High Risk)'),
    50:  ('#fbc02d', 'yellow',      '1-in-50yr  (Medium-High Risk)'),
    100: ('#aed581', 'yellowgreen', '1-in-100yr (Medium Risk)'),
    200: ('#29b6f6', 'lightblue',   '1-in-200yr (Low-Medium Risk)'),
    500: ('#90caf9', 'skyblue',     '1-in-500yr (Low Risk)'),
}

# Flood zone points (from hazard_df)
for rp_val, (hex_color, _, label) in ZONE_COLORS.items():
    zone_pts = hazard_df[hazard_df['flood_rp'] == rp_val]
    if len(zone_pts) == 0:
        continue
    
    # Downsample for map performance (max 500 markers per zone)
    sample = zone_pts.sample(min(500, len(zone_pts)), random_state=42)
    
    layer = folium.FeatureGroup(name=f'🌊 Flood Zone: {label}', show=(rp_val <= 200))
    
    for _, row in sample.iterrows():
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=4,
            color=hex_color,
            fill=True,
            fill_color=hex_color,
            fill_opacity=0.6,
            weight=0,
            popup=folium.Popup(
                f"<b>Flood Zone</b>: {rp_val}-yr RP<br>"
                f"Elevation: {row['elevation']:.1f}m<br>"
                f"Occurrence: {row['occurrence']:.1f}%",
                max_width=200
            )
        ).add_to(layer)
    
    layer.add_to(m)

# ── Exposure Layer ────────────────────────────────────────
# Plot exposed buildings coloured by sum insured
exposed = buildings_df[buildings_df['flood_rp'] > 0].copy()
sample_exposed = exposed.sample(min(800, len(exposed)), random_state=99)

exposure_layer = folium.FeatureGroup(name='🏢 Exposed Buildings (Insured)', show=True)

# Quartile-based sizing
si_q33 = sample_exposed['sum_insured_total'].quantile(0.33)
si_q66 = sample_exposed['sum_insured_total'].quantile(0.66)

def get_marker_size(si):
    if si < si_q33:  return 4
    elif si < si_q66: return 6
    else:             return 9

def get_si_color(si, si_max):
    ratio = si / si_max
    if ratio > 0.7:   return '#b71c1c'  # dark red = high value
    elif ratio > 0.4: return '#e65100'  # orange
    else:             return '#1565c0'  # blue = lower value

si_max = sample_exposed['sum_insured_total'].max()

for _, row in sample_exposed.iterrows():
    size  = get_marker_size(row['sum_insured_total'])
    color = get_si_color(row['sum_insured_total'], si_max)
    
    popup_html = (
        f"<b>Building Type:</b> {row['building_type']}<br>"
        f"<b>Sum Insured:</b> LKR {row['sum_insured_total']/1e6:.1f}M<br>"
        f"<b>Area:</b> {row['area_m2']:.0f} m² × {row['floors']} floors<br>"
        f"<b>Flood Zone:</b> 1-in-{int(row['flood_rp'])}yr<br>"
        f"<b>Elevation:</b> {row['elevation']:.1f}m<br>"
        f"<b>DR (200yr):</b> {row.get('dr_200yr', 0):.2f}"
    )
    
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=size,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.85,
        weight=1,
        popup=folium.Popup(popup_html, max_width=250)
    ).add_to(exposure_layer)

exposure_layer.add_to(m)

# ── Legend ────────────────────────────────────────────────
legend_html = """
<div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
     background: white; padding: 15px; border-radius: 10px;
     border: 2px solid #ccc; font-family: Arial; font-size: 12px;
     box-shadow: 3px 3px 8px rgba(0,0,0,0.3); min-width: 220px;">
  <b style="font-size:13px;">🌊 Flood Hazard Zones</b><br>
  <small style="color:#666;">Return Period → Severity</small><br><br>
"""
for rp_val, (hex_color, _, label) in ZONE_COLORS.items():
    legend_html += (
        f'<div style="margin:3px 0;">'
        f'<span style="background:{hex_color};display:inline-block;'
        f'width:14px;height:14px;border-radius:50%;margin-right:8px;'
        f'vertical-align:middle;"></span>{label}</div>'
    )
legend_html += """
  <hr style="margin:8px 0;">
  <b>🏢 Building Colours</b><br>
  <div style="margin:3px 0;"><span style="color:#b71c1c">●</span> High value (>LKR 20M)</div>
  <div style="margin:3px 0;"><span style="color:#e65100">●</span> Medium value</div>
  <div style="margin:3px 0;"><span style="color:#1565c0">●</span> Lower value</div>
  <hr style="margin:8px 0;">
  <small><b>Data:</b> JRC GSW v1.4 + Google Open Buildings v3</small><br>
  <small><b>Area:</b> Colombo & Western Province, Sri Lanka</small>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Layer Control ─────────────────────────────────────────
folium.LayerControl(collapsed=False).add_to(m)

# ── Title Box ─────────────────────────────────────────────
title_html = """
<div style="position:fixed; top:10px; left:50%; transform:translateX(-50%);
     z-index:1000; background:rgba(255,255,255,0.95); padding:10px 20px;
     border-radius:8px; border:2px solid #1565c0; text-align:center;
     box-shadow:3px 3px 8px rgba(0,0,0,0.3);">
  <b style="font-size:14px; color:#1565c0;">
    🇱🇰 Sri Lanka Flood Cat Model — IRCSL RBC Framework POC
  </b><br>
  <span style="font-size:11px; color:#555;">
    Colombo & Western Province | GEE + Python | JRC Huizinga Curves
  </span>
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

map_path = 'flood_hazard_exposure_map.html'
m.save(map_path)
print(f"✅ Interactive map saved: flood_hazard_exposure_map.html")

# ── 7.2  EP Curve Chart (Core Actuarial Output) ──────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 7))
fig.patch.set_facecolor('#f8f9fa')

# Left: EP Curve (Loss vs Return Period)
ax1 = axes[0]
ax1.set_facecolor('#f8f9fa')

# Plot the EP curve
valid_mask = (ep_curve_df['return_period_yr'] >= 2) & (ep_curve_df['loss_lkr_b'] > 0)
ep_plot = ep_curve_df[valid_mask]

ax1.plot(ep_plot['return_period_yr'], ep_plot['loss_lkr_b'],
         color='#1565c0', linewidth=2.5, zorder=5, label='EP Curve')

ax1.fill_between(ep_plot['return_period_yr'], 0, ep_plot['loss_lkr_b'],
                 alpha=0.15, color='#1565c0')

# Key annotations
key_points = {
    'MAL\n(Mean Annual)':    (1.5,  MAL/1e9,     '#4CAF50'),
    '1-in-10yr':             (10,   OEP_10/1e9,  '#FF9800'),
    '1-in-50yr':             (50,   OEP_50/1e9,  '#FF5722'),
    '1-in-100yr':            (100,  OEP_100/1e9, '#9C27B0'),
    '1-in-200yr\n(IRCSL\nThreshold)': (200, OEP_200/1e9, '#D32F2F'),
    '1-in-500yr':            (500,  OEP_500/1e9, '#880E4F'),
}

for label, (x, y, color) in key_points.items():
    ax1.scatter(x, y, s=80, color=color, zorder=10, ec='white', linewidth=1.5)
    ax1.annotate(
        f'{label}\nLKR {y:.2f}B',
        xy=(x, y), xytext=(x*1.3, y + 0.02),
        fontsize=7.5, color=color, fontweight='bold',
        arrowprops=dict(arrowstyle='->', color=color, lw=1.2)
    )

# Capital charge shading
ax1.axhline(y=MAL/1e9, color='#4CAF50', linestyle='--', linewidth=1.5, alpha=0.7)
ax1.axhline(y=OEP_200/1e9, color='#D32F2F', linestyle='--', linewidth=1.5, alpha=0.7)
ax1.axvline(x=200, color='#D32F2F', linestyle=':', linewidth=1.5, alpha=0.7)

ax1.fill_between([1, 300],
                 MAL/1e9, OEP_200/1e9,
                 alpha=0.12, color='#D32F2F',
                 label=f'Capital Charge = LKR {CAPITAL_CHARGE/1e9:.3f}B')

ax1.set_xscale('log')
ax1.set_xlabel('Return Period (years)', fontsize=12)
ax1.set_ylabel('Loss (LKR Billions)', fontsize=12)
ax1.set_title('Occurrence Exceedance Probability (OEP) Curve\nColom bo & Western Province Flood Model',
              fontsize=12, fontweight='bold', pad=10)
ax1.legend(fontsize=9, loc='upper left')
ax1.grid(True, alpha=0.3, which='both')
ax1.set_xlim(2, 800)

# Right: Capital Charge Breakdown Bar
ax2 = axes[1]
ax2.set_facecolor('#f8f9fa')

categories = ['Mean Annual\nLoss (MAL)', '1-in-10yr\nLoss', '1-in-50yr\nLoss',
              '1-in-100yr\nLoss', '1-in-200yr\nLoss\n(CAT Capital)']
values_b = [MAL/1e9, OEP_10/1e9, OEP_50/1e9, OEP_100/1e9, OEP_200/1e9]
colors_b = ['#4CAF50', '#FF9800', '#FF5722', '#9C27B0', '#D32F2F']

bars = ax2.bar(categories, values_b, color=colors_b, edgecolor='white',
               linewidth=1.5, width=0.6)

# Value labels on bars
for bar, val in zip(bars, values_b):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
             f'LKR\n{val:.3f}B', ha='center', va='bottom',
             fontsize=9, fontweight='bold')

# Capital charge brace annotation
ax2.annotate('', xy=(4.3, OEP_200/1e9), xytext=(4.3, MAL/1e9),
             arrowprops=dict(arrowstyle='<->', color='#D32F2F', lw=2))
ax2.text(4.45, (OEP_200/1e9 + MAL/1e9)/2,
         f'IRCSL\nCap. Charge\nLKR {CAPITAL_CHARGE/1e9:.3f}B',
         color='#D32F2F', fontsize=9, fontweight='bold', va='center')

ax2.set_ylabel('Loss (LKR Billions)', fontsize=12)
ax2.set_title('Loss at Key Return Periods\n& IRCSL Capital Charge',
              fontsize=12, fontweight='bold', pad=10)
ax2.grid(True, alpha=0.3, axis='y')
ax2.set_ylim(0, OEP_200/1e9 * 1.35)

plt.tight_layout(pad=3)
plt.savefig('fig2_ep_curve.png', dpi=150, bbox_inches='tight')
plt.show()
print("✅ Figure saved: fig2_ep_curve.png")

# ── 7.3  Loss Distribution Histogram ────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(16, 5))
fig.patch.set_facecolor('#f8f9fa')

# Histogram of annual losses (excluding zero-loss years for clarity)
nonzero_losses = annual_losses_b[annual_losses_b > 0]

ax = axes[0]
ax.set_facecolor('#f8f9fa')
n_bins = min(80, len(nonzero_losses) // 50)
ax.hist(nonzero_losses, bins=n_bins, color='#1565c0', alpha=0.7,
        edgecolor='white', linewidth=0.5, density=True)

ax.axvline(MAL/1e9, color='#4CAF50', linewidth=2, linestyle='--',
           label=f'MAL = LKR {MAL/1e9:.3f}B')
ax.axvline(OEP_100/1e9, color='#9C27B0', linewidth=2, linestyle='--',
           label=f'1-in-100yr = LKR {OEP_100/1e9:.3f}B')
ax.axvline(OEP_200/1e9, color='#D32F2F', linewidth=2.5, linestyle='-',
           label=f'1-in-200yr = LKR {OEP_200/1e9:.3f}B (IRCSL)')

ax.set_xlabel('Annual Loss (LKR Billions)', fontsize=11)
ax.set_ylabel('Probability Density', fontsize=11)
ax.set_title(f'Annual Loss Distribution\n({N_SIMULATIONS:,}-year Monte Carlo Simulation)',
             fontsize=11, fontweight='bold')
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# Summary stats box
stats_text = (
    f"Loss Statistics:\n"
    f"{'Zero-loss years:':<20} {(annual_losses==0).sum()/N_SIMULATIONS*100:.0f}%\n"
    f"{'Mean (MAL):':<20} {MAL/1e9:.4f}B\n"
    f"{'Std Dev:':<20} {annual_losses.std()/1e9:.4f}B\n"
    f"{'Skewness:':<20} {stats.skew(annual_losses):.2f}"
)
ax.text(0.97, 0.97, stats_text, transform=ax.transAxes,
        va='top', ha='right', fontsize=8.5,
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

# Capital charge dashboard panel
ax2 = axes[1]
ax2.set_facecolor('#0d1b2a')
ax2.set_xlim(0, 10)
ax2.set_ylim(0, 10)
ax2.axis('off')

# Dashboard title
ax2.text(5, 9.4, '🇱🇰 IRCSL RBC — CAT Capital Dashboard',
         ha='center', va='center', fontsize=12, fontweight='bold',
         color='white')
ax2.text(5, 8.9, 'Colombo & Western Province Flood Model (POC)',
         ha='center', va='center', fontsize=9, color='#90caf9')

# Metric cards
metrics = [
    ('Total Insured Value', f'LKR {TIV/1e9:.1f}B', '#29b6f6'),
    ('Flood-Exposed TIV',   f'LKR {buildings_df[buildings_df["flood_rp"]>0]["sum_insured_total"].sum()/1e9:.1f}B', '#ff9800'),
    ('Mean Annual Loss',    f'LKR {MAL/1e9:.3f}B', '#4caf50'),
    ('1-in-200yr Loss',     f'LKR {OEP_200/1e9:.3f}B', '#ef5350'),
    ('CAT Capital Charge',  f'LKR {CAPITAL_CHARGE/1e9:.3f}B', '#ff1744'),
    ('CAT Charge / TIV',    f'{capital_charge_pct_TIV:.3f}%', '#aa00ff'),
]

y_pos = 8.0
for i, (label, value, color) in enumerate(metrics):
    row = i // 2
    col = i % 2
    x = 1.5 + col * 4.5
    y = y_pos - row * 2.2
    
    rect = mpatches.FancyBboxPatch((x-1.2, y-0.8), 2.8, 1.6,
                                    boxstyle="round,pad=0.1",
                                    facecolor='#1a2744', edgecolor=color,
                                    linewidth=2)
    ax2.add_patch(rect)
    ax2.text(x+0.2, y+0.3, value, ha='center', va='center',
             fontsize=14, fontweight='bold', color=color)
    ax2.text(x+0.2, y-0.35, label, ha='center', va='center',
             fontsize=8, color='#b0bec5')

# IRCSL framework reference
ax2.text(5, 0.6, '📋 Framework: IRCSL Solvency Margin (RBC) Rules — Proposed Revision 2025',
         ha='center', va='center', fontsize=7.5, color='#78909c')
ax2.text(5, 0.2, 'Capital Charge = OEP₂₀₀ − MAL  |  Min. CAR = 120%  |  Ref: Pages 36–38',
         ha='center', va='center', fontsize=7.5, color='#78909c', style='italic')

plt.tight_layout()
plt.savefig('fig3_loss_distribution_dashboard.png',
            dpi=150, bbox_inches='tight')
plt.show()
print("✅ Figure saved: fig3_loss_distribution_dashboard.png")

# ── 7.4  Final Summary Print ────────────────────────────────
print("\n" + "="*60)
print("  🎉 ALL 7 PHASES COMPLETE!")
print("="*60)
print("\n  📁 Output Files:")
print("     • flood_hazard_exposure_map.html  → Open in browser")
print("     • fig1_depth_damage_curves.png    → Vulnerability curves")
print("     • fig2_ep_curve.png               → EP curve + capital")
print("     • fig3_loss_distribution_dashboard.png → Full dashboard")
print("     • ep_curve.csv                    → Raw EP curve data")
print("\n  🔑 Key Numbers for IRCSL Submission:")
print(f"     MAL                : LKR {MAL/1e9:.3f} Billion")
print(f"     1-in-200yr Loss    : LKR {OEP_200/1e9:.3f} Billion")
print(f"     CAT Capital Charge : LKR {CAPITAL_CHARGE/1e9:.3f} Billion")
print(f"     As % of TIV        : {capital_charge_pct_TIV:.3f}%")
print("\n  📚 Data Sources:")
print("     • JRC Global Surface Water v1.4 (GEE)")
print("     • Copernicus GLO-30 DEM (GEE)")
print("     • Google Open Buildings v3 (GEE)")
print("     • JRC Huizinga et al. 2017 (depth-damage curves)")
print("     • IRCSL RBC Rules 2025 (capital framework)")
