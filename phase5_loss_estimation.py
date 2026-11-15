# ============================================================
# PHASE 5: LOSS ESTIMATION — MONTE CARLO SIMULATION
# ============================================================

# ── Imports (each phase is fully self-contained) ─────────────
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')


# ── Re-define calculate_damage_ratio (originally from Phase 4) ──
from scipy.interpolate import interp1d
HUIZINGA_CURVES = {
    "residential":         {"depths": [0.0,0.5,1.0,1.5,2.0,3.0,4.0,5.0,6.0], "damage": [0.00,0.25,0.40,0.50,0.60,0.75,0.85,0.95,1.00]},
    "commercial":          {"depths": [0.0,0.5,1.0,1.5,2.0,3.0,4.0,5.0,6.0], "damage": [0.00,0.15,0.27,0.40,0.52,0.65,0.78,0.90,1.00]},
    "industrial":          {"depths": [0.0,0.5,1.0,1.5,2.0,3.0,4.0,5.0,6.0], "damage": [0.00,0.10,0.20,0.30,0.42,0.55,0.68,0.82,1.00]},
    "contents_residential":{"depths": [0.0,0.5,1.0,1.5,2.0,3.0,4.0,5.0,6.0], "damage": [0.00,0.35,0.55,0.65,0.73,0.84,0.92,0.97,1.00]},
    "contents_commercial": {"depths": [0.0,0.5,1.0,1.5,2.0,3.0,4.0,5.0,6.0], "damage": [0.00,0.20,0.38,0.50,0.62,0.76,0.87,0.95,1.00]},
}
damage_functions = {k: interp1d(v["depths"], v["damage"], kind="linear", bounds_error=False, fill_value=(0.0,1.0)) for k,v in HUIZINGA_CURVES.items()}
CURVE_MAPPING = {
    "residential_small":    ("residential",  "contents_residential"),
    "residential_standard": ("residential",  "contents_residential"),
    "commercial_mixed":     ("commercial",   "contents_commercial"),
    "commercial_large":     ("industrial",   "contents_commercial"),
}
def calculate_damage_ratio(building_type, flood_depth_m):
    if flood_depth_m <= 0: return 0.0
    struct_curve, _ = CURVE_MAPPING[building_type]
    return float(damage_functions[struct_curve](flood_depth_m))
print("✅ calculate_damage_ratio re-defined in Phase 5")

np.random.seed(2024)

# ── Shared constants ──────────────────────────────────────────
RETURN_PERIODS           = [10, 25, 50, 100, 200, 500]
N_SIMULATIONS            = 10_000
DAMAGE_UNCERTAINTY_SIGMA = 0.4
LKR_PER_USD              = 320

# ── Load buildings_df (with damage ratios) from Phase 4 ─────
buildings_df = pd.read_csv("buildings_df_with_dr.csv")
print(f"✅ buildings_df loaded: {len(buildings_df):,} buildings with damage ratios")
print("✅ Phase 5 imports & constants ready")
#     4. Apply damage ratio (with vulnerability uncertainty)
#     5. Calculate monetary loss
#
# This gives us an Annual Loss Distribution →
# from which we extract the EP (Exceedance Probability) curve
# ============================================================

np.random.seed(2024)   # reproducibility

# ── 5.1  Define Stochastic Event Catalog ────────────────────
# Each "event" represents a flood scenario with:
#   - Annual occurrence rate (Poisson)
#   - Affected area footprint
#   - Depth multiplier

# Event catalog derived from return period hazard zones
# Annual rate λ = 1 / return_period (Poisson process assumption)

EVENT_CATALOG = [
    # (name, return_period, depth_multiplier, spatial_coverage_fraction)
    # Multiple events per RP band to capture spatial variability
    ('Minor Flood - Kelani R. local',  10, 0.7, 0.15),
    ('Minor Flood - Kelani R. wide',   10, 1.0, 0.25),
    ('Moderate Flood - Western',       25, 0.85, 0.20),
    ('Moderate Flood - Coastal',       25, 1.1,  0.18),
    ('Major Flood - Kelani Basin',     50, 0.9,  0.30),
    ('Major Flood - Metro Colombo',    50, 1.15, 0.22),
    ('Severe Flood - Basin wide',     100, 1.0,  0.40),
    ('Severe Flood - Coastal surge',  100, 1.2,  0.28),
    ('Extreme - 1-in-200yr',          200, 1.0,  0.55),
    ('Extreme - 1-in-200yr coastal',  200, 1.3,  0.40),
    ('Catastrophic - 1-in-500yr',     500, 1.0,  0.70),
]

# Convert to DataFrame
events_df = pd.DataFrame(EVENT_CATALOG,
    columns=['name', 'return_period', 'depth_multiplier', 'spatial_coverage'])
events_df['annual_rate'] = 1.0 / events_df['return_period']

print("📋 Stochastic Event Catalog:")
print(events_df[['name','return_period','annual_rate','spatial_coverage']].to_string(index=False))

# ── 5.2  Pre-compute Per-Building Expected Loss per Event ────
print("\nPre-computing per-building losses for each event...")

# Only process flood-exposed buildings for efficiency
exposed_mask  = buildings_df['flood_rp'] > 0
exposed_bldgs = buildings_df[exposed_mask].copy().reset_index(drop=True)

n_buildings = len(exposed_bldgs)
n_events    = len(events_df)

print(f"   Exposed buildings: {n_buildings:,}")
print(f"   Event catalog size: {n_events}")

# For each event, compute mean loss for each building
event_mean_losses = np.zeros((n_events, n_buildings))   # LKR

for ev_idx, event in events_df.iterrows():
    rp         = event['return_period']
    depth_mult = event['depth_multiplier']
    coverage   = event['spatial_coverage']
    
    # Choose nearest available RP band
    available_rps = [r for r in RETURN_PERIODS if r <= rp]
    use_rp = max(available_rps) if available_rps else RETURN_PERIODS[0]
    
    depth_col = f'depth_{use_rp}yr'
    dr_col    = f'dr_{use_rp}yr'
    
    # Apply depth multiplier and recalculate damage ratio
    depths = exposed_bldgs[depth_col] * depth_mult
    
    mean_dr_struct = np.array([
        calculate_damage_ratio(bt, d)
        for bt, d in zip(exposed_bldgs['building_type'], depths)
    ])
    mean_dr_cont = mean_dr_struct * 1.15    # contents slightly more damaged
    mean_dr_cont = np.clip(mean_dr_cont, 0, 1)
    
    loss_structure = mean_dr_struct * exposed_bldgs['sum_insured_structure'].values
    loss_contents  = mean_dr_cont  * exposed_bldgs['sum_insured_contents'].values
    total_loss     = loss_structure + loss_contents
    
    event_mean_losses[ev_idx, :] = total_loss

print("✅ Event mean losses computed")

# ── 5.3  Monte Carlo Simulation ─────────────────────────────
print(f"\nRunning {N_SIMULATIONS:,}-year Monte Carlo simulation...")

annual_losses = np.zeros(N_SIMULATIONS)
event_occurrence_count = np.zeros(n_events)

for sim_year in range(N_SIMULATIONS):
    year_loss = 0.0
    
    for ev_idx, event in events_df.iterrows():
        lam = event['annual_rate']
        
        # Number of occurrences this year (Poisson)
        n_occur = np.random.poisson(lam)
        if n_occur == 0:
            continue
        
        event_occurrence_count[ev_idx] += n_occur
        coverage = event['spatial_coverage']
        
        for _ in range(n_occur):
            # Which buildings are affected? (random subset based on spatial coverage)
            affected_mask = np.random.random(n_buildings) < coverage
            
            if not affected_mask.any():
                continue
            
            mean_losses = event_mean_losses[ev_idx, affected_mask]
            
            # Apply vulnerability uncertainty (log-normal sampling)
            # Only sample for non-zero losses
            nonzero = mean_losses > 0
            sampled_losses = np.zeros(len(mean_losses))
            if nonzero.any():
                mu  = np.log(mean_losses[nonzero] + 1)
                sig = DAMAGE_UNCERTAINTY_SIGMA
                sampled_losses[nonzero] = np.random.lognormal(
                    np.log(np.maximum(mean_losses[nonzero], 1)),
                    sig
                )
                # Don't let loss exceed sum insured
                si_affected = exposed_bldgs['sum_insured_total'].values[affected_mask]
                sampled_losses = np.minimum(sampled_losses, si_affected)
            
            year_loss += sampled_losses.sum()
    
    annual_losses[sim_year] = year_loss

print(f"✅ Monte Carlo complete!")

# ── 5.4  Summary Statistics ──────────────────────────────────
annual_losses_b = annual_losses / 1e9   # convert to LKR Billions

print("\n" + "="*55)
print("  LOSS SIMULATION RESULTS (LKR Billions)")
print("="*55)
print(f"  Mean Annual Loss (MAL)          : LKR {annual_losses_b.mean():.3f}B")
print(f"  Standard Deviation              : LKR {annual_losses_b.std():.3f}B")
print(f"  Median Annual Loss              : LKR {np.median(annual_losses_b):.3f}B")
print(f"  % Years with zero loss          : {(annual_losses==0).sum()/N_SIMULATIONS*100:.1f}%")
print(f"\n  Loss Percentiles:")
for pct in [50, 75, 90, 95, 99, 99.5]:
    loss_val = np.percentile(annual_losses_b, pct)
    rp_equiv = 1 / (1 - pct/100) if pct < 100 else 200
    print(f"    {pct:>5.1f}th pct (≈ {rp_equiv:.0f}-yr RP): LKR {loss_val:.3f}B")

# Save results
loss_results = {
    'annual_losses': annual_losses,
    'mean_annual_loss': annual_losses.mean(),
    'std_loss': annual_losses.std()
}

print("\n🚀 Phase 5 Complete — Loss distribution simulated")

# ── SAVE OUTPUT FOR PHASE 6 ──────────────────────────────────
import os
np.save("annual_losses.npy", annual_losses)
print("✅ annual_losses saved → annual_losses.npy  (loaded by Phase 6)")
