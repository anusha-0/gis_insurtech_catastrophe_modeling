# ============================================================
# PHASE 6: EXCEEDANCE PROBABILITY CURVE & CAPITAL CHARGE
# ============================================================

# ── Imports (each phase is fully self-contained) ─────────────
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# ── Shared constants ──────────────────────────────────────────
RETURN_PERIODS = [10, 25, 50, 100, 200, 500]
N_SIMULATIONS  = 10_000
LKR_PER_USD    = 320
EXAMPLE_CAR    = 135   # % hypothetical insurer CAR

# ── Load outputs from Phase 3 & 5 ───────────────────────────
buildings_df  = pd.read_csv("buildings_df_with_dr.csv")
annual_losses = np.load("annual_losses.npy")
annual_losses_b = annual_losses / 1e9
print(f"✅ Loaded: {len(buildings_df):,} buildings, {len(annual_losses):,} simulated years")
print("✅ Phase 6 imports & constants ready")
# ============================================================

# ── 6.1  Build Exceedance Probability Curve ─────────────────
# Sort losses and compute non-exceedance probabilities
sorted_losses = np.sort(annual_losses)
n             = len(sorted_losses)

# Non-exceedance probability (Weibull plotting position)
non_exceed_probs = np.arange(1, n + 1) / (n + 1)
exceed_probs     = 1 - non_exceed_probs

# Return period = 1 / exceedance probability
return_periods_ep = 1 / exceed_probs
return_periods_ep = np.clip(return_periods_ep, 1, 100_000)

# EP curve in LKR Billions
ep_curve_df = pd.DataFrame({
    'loss_lkr':          sorted_losses,
    'loss_lkr_b':        sorted_losses / 1e9,
    'exceed_prob':       exceed_probs,
    'return_period_yr':  return_periods_ep,
    'non_exceed_prob':   non_exceed_probs
})

print("✅ EP Curve constructed")

# ── 6.2  Extract Key Loss Metrics ───────────────────────────
def get_loss_at_return_period(rp_years, sorted_losses=sorted_losses,
                               n=N_SIMULATIONS):
    """Interpolate loss at a given return period from simulated distribution."""
    target_percentile = (1 - 1/rp_years) * 100
    return np.percentile(sorted_losses, target_percentile)

def get_loss_at_percentile(pct):
    return np.percentile(sorted_losses, pct)

# Key regulatory thresholds
MAL      = annual_losses.mean()                  # Mean Annual Loss
OEP_10   = get_loss_at_return_period(10)         # 1-in-10 year
OEP_50   = get_loss_at_return_period(50)         # 1-in-50 year
OEP_100  = get_loss_at_return_period(100)        # 1-in-100 year
OEP_200  = get_loss_at_return_period(200)        # 1-in-200 year (99.5th pct)
OEP_500  = get_loss_at_return_period(500)        # 1-in-500 year

# IRCSL Capital Charge Formula (from document, pages 36-38):
# Capital Charge = OEP_200yr - MAL
CAPITAL_CHARGE = OEP_200 - MAL

# As % of Total Insured Value
TIV = buildings_df['sum_insured_total'].sum()
capital_charge_pct_TIV = (CAPITAL_CHARGE / TIV) * 100

# Required Capital Adequacy Ratio check (minimum 120% per IRCSL rules)
# This is illustrative - real RAC needs full TAC/RCR from insurer financials
EXAMPLE_CAR = 135   # %  (hypothetical insurer CAR)

print("\n" + "="*60)
print("  CATASTROPHE CAPITAL CHARGE — IRCSL RBC FRAMEWORK")
print("  Colombo & Western Province Flood Model")
print("="*60)
print(f"\n  ── Loss at Key Return Periods ─────────────────────────")
print(f"  Mean Annual Loss (MAL)      : LKR {MAL/1e9:>8.3f} Billion")
print(f"  1-in-10yr  (OEP 90th pct)  : LKR {OEP_10/1e9:>8.3f} Billion")
print(f"  1-in-50yr  (OEP 98th pct)  : LKR {OEP_50/1e9:>8.3f} Billion")
print(f"  1-in-100yr (OEP 99th pct)  : LKR {OEP_100/1e9:>8.3f} Billion")
print(f"  1-in-200yr (OEP 99.5th)    : LKR {OEP_200/1e9:>8.3f} Billion  ←  Regulatory Threshold")
print(f"  1-in-500yr (OEP 99.8th)    : LKR {OEP_500/1e9:>8.3f} Billion")

print(f"\n  ── IRCSL Capital Charge Calculation ────────────────────")
print(f"  Formula: CAT Capital = OEP_200yr − MAL")
print(f"  CAT Capital Charge          : LKR {CAPITAL_CHARGE/1e9:>8.3f} Billion")
print(f"  CAT Capital (USD)           : USD {CAPITAL_CHARGE/LKR_PER_USD/1e6:>8.1f} Million")
print(f"  As % of Total Insured Value : {capital_charge_pct_TIV:>8.3f}%")

print(f"\n  ── Portfolio Context ────────────────────────────────────")
print(f"  Total Insured Value (TIV)   : LKR {TIV/1e9:>8.2f} Billion")
print(f"  Flood-exposed TIV           : LKR {buildings_df[buildings_df['flood_rp']>0]['sum_insured_total'].sum()/1e9:>8.2f} Billion")
print(f"  Buildings modelled          : {len(buildings_df):>8,}")
print(f"\n  ── IRCSL Regulatory Capital Check ───────────────────────")
print(f"  Min. CAR required           : 120%  (IRCSL Rule 3)")
print(f"  Example insurer CAR         : {EXAMPLE_CAR}%   (hypothetical)")
cat_buffer = (EXAMPLE_CAR - 120) / 100 * TIV
print(f"  Capital buffer above 120%   : LKR {cat_buffer/1e9:>8.2f} Billion")
adequate = "✅ ADEQUATE" if cat_buffer > CAPITAL_CHARGE else "❌ INSUFFICIENT"
print(f"  Can absorb CAT charge?      : {adequate}")

# ── 6.3  Breakdown by Return Period ─────────────────────────
print(f"\n  ── EP Curve Summary ─────────────────────────────────────")
print(f"  {'Return Period':>15}  {'Exceedance Prob':>17}  {'Loss (LKR B)':>13}  {'Loss/TIV':>10}")
print(f"  {'-'*60}")
for rp in [5, 10, 25, 50, 100, 200, 500]:
    loss = get_loss_at_return_period(rp)
    ep   = 1/rp * 100
    pct_tiv = loss/TIV*100
    marker = " ← CAT charge" if rp == 200 else ""
    print(f"  {rp:>13}-yr  {ep:>15.2f}%  LKR {loss/1e9:>8.3f}B  {pct_tiv:>9.3f}%{marker}")

# ── 6.4  Save Results for Visualization ─────────────────────
capital_results = {
    'MAL':            MAL,
    'OEP_10':         OEP_10,
    'OEP_50':         OEP_50,
    'OEP_100':        OEP_100,
    'OEP_200':        OEP_200,
    'OEP_500':        OEP_500,
    'CAPITAL_CHARGE': CAPITAL_CHARGE,
    'TIV':            TIV,
    'pct_TIV':        capital_charge_pct_TIV
}

ep_curve_df.to_csv('ep_curve.csv', index=False)
print(f"\n✅ EP curve saved to ep_curve.csv")

print("\n🚀 Phase 6 Complete — Capital charge calculated")

# ── SAVE OUTPUTS FOR PHASE 7 ─────────────────────────────────
import json
capital_summary = {
    "MAL": float(MAL), "OEP_10": float(OEP_10), "OEP_50": float(OEP_50),
    "OEP_100": float(OEP_100), "OEP_200": float(OEP_200), "OEP_500": float(OEP_500),
    "CAPITAL_CHARGE": float(CAPITAL_CHARGE), "TIV": float(TIV),
    "capital_charge_pct_TIV": float(capital_charge_pct_TIV)
}
with open("capital_summary.json", "w") as f:
    json.dump(capital_summary, f)
ep_curve_df.to_csv("ep_curve.csv", index=False)
print("✅ capital_summary.json + ep_curve.csv saved → used by Phase 7")
