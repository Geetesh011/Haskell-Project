"""
Phase 1: Data Ingestion & Normalization
========================================
Defines the schema for coastal district data, generates realistic sample data
for 10 Indian coastal districts, normalizes all variables to a 0-1 scale,
and exports the result as JSON to feed the Haskell logic engine.
"""

import json
import os
import sys

NUMERIC_COLUMNS = [
    "elevation_m",
    "erosion_rate_m_yr",
    "slr_mm_yr",
    "pop_density_km2",
    "income_level_inr",
    "cyclone_freq",
    "mangrove_cover_pct",
    "drainage_quality",
]

# Variables where a HIGHER raw value means LESS vulnerable (protective)
PROTECTIVE_VARS = {"income_level_inr", "mangrove_cover_pct", "drainage_quality", "elevation_m"}

def generate_sample_data() -> list[dict]:
    """Return a list of dicts with realistic mock data for 10 coastal districts."""
    districts = [
        {
            "district": "Chennai",
            "state": "Tamil Nadu",
            "elevation_m": 6.0,
            "erosion_rate_m_yr": 1.2,
            "slr_mm_yr": 3.2,
            "pop_density_km2": 26000,
            "income_level_inr": 320000,
            "cyclone_freq": 2.5,
            "mangrove_cover_pct": 5.0,
            "drainage_quality": 4,
        },
        {
            "district": "Mumbai Suburban",
            "state": "Maharashtra",
            "elevation_m": 14.0,
            "erosion_rate_m_yr": 0.5,
            "slr_mm_yr": 3.0,
            "pop_density_km2": 20000,
            "income_level_inr": 450000,
            "cyclone_freq": 1.0,
            "mangrove_cover_pct": 12.0,
            "drainage_quality": 6,
        },
        {
            "district": "Puri",
            "state": "Odisha",
            "elevation_m": 3.0,
            "erosion_rate_m_yr": 3.5,
            "slr_mm_yr": 4.1,
            "pop_density_km2": 500,
            "income_level_inr": 120000,
            "cyclone_freq": 4.5,
            "mangrove_cover_pct": 8.0,
            "drainage_quality": 3,
        },
        {
            "district": "Sundarbans",
            "state": "West Bengal",
            "elevation_m": 1.5,
            "erosion_rate_m_yr": 5.0,
            "slr_mm_yr": 5.5,
            "pop_density_km2": 800,
            "income_level_inr": 95000,
            "cyclone_freq": 5.0,
            "mangrove_cover_pct": 45.0,
            "drainage_quality": 2,
        },
        {
            "district": "Ernakulam",
            "state": "Kerala",
            "elevation_m": 10.0,
            "erosion_rate_m_yr": 0.3,
            "slr_mm_yr": 2.8,
            "pop_density_km2": 1100,
            "income_level_inr": 380000,
            "cyclone_freq": 0.5,
            "mangrove_cover_pct": 15.0,
            "drainage_quality": 7,
        },
        {
            "district": "Ramanathapuram",
            "state": "Tamil Nadu",
            "elevation_m": 5.0,
            "erosion_rate_m_yr": 2.8,
            "slr_mm_yr": 3.6,
            "pop_density_km2": 400,
            "income_level_inr": 110000,
            "cyclone_freq": 3.0,
            "mangrove_cover_pct": 3.0,
            "drainage_quality": 3,
        },
        {
            "district": "Kendrapara",
            "state": "Odisha",
            "elevation_m": 2.0,
            "erosion_rate_m_yr": 4.2,
            "slr_mm_yr": 4.8,
            "pop_density_km2": 600,
            "income_level_inr": 100000,
            "cyclone_freq": 4.0,
            "mangrove_cover_pct": 6.0,
            "drainage_quality": 2,
        },
        {
            "district": "Kachchh",
            "state": "Gujarat",
            "elevation_m": 8.0,
            "erosion_rate_m_yr": 1.0,
            "slr_mm_yr": 2.5,
            "pop_density_km2": 46,
            "income_level_inr": 200000,
            "cyclone_freq": 2.0,
            "mangrove_cover_pct": 25.0,
            "drainage_quality": 5,
        },
        {
            "district": "Dakshina Kannada",
            "state": "Karnataka",
            "elevation_m": 20.0,
            "erosion_rate_m_yr": 0.2,
            "slr_mm_yr": 2.0,
            "pop_density_km2": 900,
            "income_level_inr": 350000,
            "cyclone_freq": 0.5,
            "mangrove_cover_pct": 10.0,
            "drainage_quality": 8,
        },
        {
            "district": "Nagapattinam",
            "state": "Tamil Nadu",
            "elevation_m": 4.0,
            "erosion_rate_m_yr": 3.0,
            "slr_mm_yr": 4.0,
            "pop_density_km2": 700,
            "income_level_inr": 105000,
            "cyclone_freq": 3.5,
            "mangrove_cover_pct": 4.0,
            "drainage_quality": 3,
        },
    ]
    return districts

def normalize(districts: list[dict]) -> list[dict]:
    """
    Apply Min-Max normalisation so every numeric column is scaled to [0, 1].
    """
    # Compute min/max for each numeric column
    col_stats: dict[str, dict[str, float]] = {}
    for col in NUMERIC_COLUMNS:
        values = [d[col] for d in districts]
        col_stats[col] = {"min": min(values), "max": max(values)}

    normalised = []
    for d in districts:
        nd = {"district": d["district"], "state": d["state"]}
        for col in NUMERIC_COLUMNS:
            cmin = col_stats[col]["min"]
            cmax = col_stats[col]["max"]
            rng = cmax - cmin
            if rng == 0:
                nd[col] = 0.0
            else:
                nd[col] = round((d[col] - cmin) / rng, 4)

            # Invert protective variables so 1 = most vulnerable
            if col in PROTECTIVE_VARS:
                nd[col] = round(1.0 - nd[col], 4)

        normalised.append(nd)

    return normalised

def export_json(districts: list[dict], filepath: str) -> None:
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(districts, f, indent=2, ensure_ascii=False)
    print(f"[Phase 1] Exported normalised data → {filepath}", file=sys.stderr)

if __name__ == "__main__":
    raw = generate_sample_data()
    normed = normalize(raw)
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "normalised.json")
    export_json(normed, out_path)
    print(json.dumps(normed, indent=2))
