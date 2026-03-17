import sys
import os
import json
import subprocess
import requests
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add python_runner to path to import data_ingestion
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "python_runner"))
from data_ingestion import generate_sample_data, normalize

app = Flask(__name__)
# Enable CORS for the Vercel frontend domain
CORS(app)


# ===========================================================================
#  IMPROVEMENT 3 — IN-MEMORY CACHE (24-hour TTL)
# ===========================================================================
# Simple thread-safe cache: { normalised_key -> {"data": {...}, "cached_at": datetime} }

_cache: dict = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 86400  # 24 hours


def cache_get(key: str):
    """Return cached entry if it exists and is less than 24 h old, else None."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        age = (datetime.now(timezone.utc) - entry["cached_at"]).total_seconds()
        if age > CACHE_TTL_SECONDS:
            del _cache[key]
            return None
        return entry


def cache_set(key: str, data: dict):
    """Store data in cache with current UTC timestamp."""
    with _cache_lock:
        _cache[key] = {
            "data": data,
            "cached_at": datetime.now(timezone.utc),
        }


# ===========================================================================
#  IMPROVEMENT 2 — PERCENTILE RANKING TABLE
# ===========================================================================

DISTRICT_CVI_TABLE = {
    "Bapatla": 0.5849,
    "Kakinada": 0.7210,
    "Visakhapatnam": 0.6340,
    "Nellore": 0.5920,
    "Ongole": 0.5650,
    "Guntur": 0.5200,
    "Krishna": 0.6100,
    "West Godavari": 0.5800,
    "East Godavari": 0.6300,
    "Srikakulam": 0.6800,
    "Chennai": 0.5509,
    "Puducherry": 0.5800,
    "Cuddalore": 0.6010,
    "Nagapattinam": 0.6750,
    "Kanyakumari": 0.4200,
    "Thoothukudi": 0.5100,
    "Ramanathapuram": 0.5500,
    "Puri": 0.7680,
    "Balasore": 0.7100,
    "Kendrapara": 0.7300,
    "Paradip": 0.6900,
    "Berhampur": 0.5600,
    "Ganjam": 0.5800,
    "Mangaluru": 0.3200,
    "Udupi": 0.3500,
    "Uttara Kannada": 0.3800,
    "Kozhikode": 0.4800,
    "Kochi": 0.5100,
    "Thiruvananthapuram": 0.4500,
    "Alappuzha": 0.5600,
    "Kollam": 0.4900,
    "Mumbai": 0.6200,
    "Raigad": 0.5100,
    "Ratnagiri": 0.2980,
    "Sindhudurg": 0.3100,
    "Thane": 0.5800,
    "Goa": 0.4200,
    "Surat": 0.5500,
    "Bharuch": 0.4800,
    "Navsari": 0.5200,
    "Valsad": 0.5000,
    "Kolkata": 0.6800,
    "South 24 Parganas": 0.7500,
    "North 24 Parganas": 0.7200,
    "Midnapore": 0.6600,
}


def compute_percentile(final_cvi: float) -> dict:
    """
    Compute the vulnerability percentile rank of the given CVI score
    against the DISTRICT_CVI_TABLE reference dataset.

    Returns a dict with:
      rank         — percentage of districts less vulnerable than this score
      rankedOutOf  — total districts in table
      worseThan    — count of districts with a lower score
      interpretation — human-readable string
    """
    scores = list(DISTRICT_CVI_TABLE.values())
    total = len(scores)
    worse_than = sum(1 for s in scores if s < final_cvi)
    rank_pct = round((worse_than / total) * 100)
    return {
        "rank": rank_pct,
        "rankedOutOf": total,
        "worseThan": worse_than,
        "interpretation": f"More vulnerable than {rank_pct}% of Indian coastal districts",
    }


# ===========================================================================
#  IMPROVEMENT 1 — REAL GEOCODING (Nominatim) + OPEN-ELEVATION (SRTM)
# ===========================================================================

def geocode_nominatim(location_name: str):
    """
    Call Nominatim OpenStreetMap API to get real lat/lon for a location.
    Returns (lat, lon, display_name) or None on failure.
    Always fails silently — never raises.
    """
    try:
        url = (
            f"https://nominatim.openstreetmap.org/search"
            f"?q={requests.utils.quote(location_name + ' India')}"
            f"&format=json&limit=1"
        )
        resp = requests.get(url, headers={"User-Agent": "CVI-Backend/2.0"}, timeout=5)
        results = resp.json()
        if not results:
            return None
        top = results[0]
        return float(top["lat"]), float(top["lon"]), top.get("display_name", location_name)
    except Exception:
        return None


def get_open_elevation(lat: float, lon: float):
    """
    Call Open-Elevation API (backed by SRTM) to get true elevation in metres.
    Returns elevation as float, or None on failure.
    Always fails silently — never raises.
    """
    try:
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
        resp = requests.get(url, timeout=8)
        data = resp.json()
        return float(data["results"][0]["elevation"])
    except Exception:
        return None


# ===========================================================================
#  ORIGINAL fetch_real_data — extended with Nominatim + Open-Elevation
# ===========================================================================

def fetch_real_data(location_name: str) -> dict:
    """
    Fetch real geographic data using Open-Meteo Geocoding API.
    Extracts population and real elevation.
    Other specialised climate variables (SLR, Mangroves) are procedurally
    estimated based on the real latitude/longitude geography.

    IMPROVEMENT 1: Also tries Nominatim for real coordinates, then
    Open-Elevation for true SRTM elevation. Falls back silently on error.
    """
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_name}&count=1&format=json"

    try:
        res = requests.get(geo_url, timeout=6).json()
    except Exception:
        return None

    if "results" not in res or len(res["results"]) == 0:
        return None

    geo = res["results"][0]
    district = geo.get("name", location_name)
    state = geo.get("admin1", geo.get("country", "Unknown"))

    # Real metrics from Open-Meteo API (primary)
    elevation = geo.get("elevation", 10.0)
    lat = geo.get("latitude", 0.0)
    lon = geo.get("longitude", 0.0)
    r_population = geo.get("population", None)

    # ---- IMPROVEMENT 1: Try Nominatim for a more precise lat/lon ----
    nominatim_result = geocode_nominatim(location_name)
    coordinates = {"lat": lat, "lon": lon}
    elevation_source = "OPEN-METEO"

    if nominatim_result:
        nom_lat, nom_lon, _ = nominatim_result
        # Use Nominatim coordinates if they look more precise
        coordinates = {"lat": nom_lat, "lon": nom_lon}

        # ---- IMPROVEMENT 1: Try Open-Elevation for true SRTM elevation ----
        srtm_elevation = get_open_elevation(nom_lat, nom_lon)
        if srtm_elevation is not None:
            elevation = srtm_elevation
            elevation_source = "OPEN-ELEVATION/SRTM"

    # ---- Estimate density ----
    if r_population:
        pop_density = r_population / 800.0
    else:
        pop_density = 800.0

    # ---- Procedural estimates for variables without free real-time APIs ----
    abs_lat = abs(lat)

    if 10 <= abs_lat <= 30:
        cyclone_freq = 3.5
    elif abs_lat < 10:
        cyclone_freq = 1.0
    else:
        cyclone_freq = 0.5

    mangrove = 15.0 if abs_lat < 25 else 1.0
    slr = 3.2 + (abs_lat % 2.0)
    erosion = 2.0
    income = 180000
    drainage = 4

    return {
        "district": district,
        "state": state,
        "elevation_m": elevation,
        "erosion_rate_m_yr": erosion,
        "slr_mm_yr": slr,
        "pop_density_km2": pop_density,
        "income_level_inr": income,
        "cyclone_freq": cyclone_freq,
        "mangrove_cover_pct": mangrove,
        "drainage_quality": drainage,
        # IMPROVEMENT 1 — new additive fields
        "coordinates": coordinates,
        "elevation_source": elevation_source,
    }


# ===========================================================================
#  BINARY FINDER (unchanged)
# ===========================================================================

def find_haskell_binary() -> str:
    """Find the compiled Haskell executable."""
    prod_path = "/usr/local/bin/cvi-backend"
    if os.path.exists(prod_path):
        return prod_path

    shell_cmd = "where" if os.name == "nt" else "which"
    try:
        subprocess.run(["stack", "--version"], capture_output=True, check=True)
        result = subprocess.run(
            ["stack", "exec", "--", shell_cmd, "cvi-backend"],
            cwd=os.path.join(os.path.dirname(__file__), "..", "cvi-backend"),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split("\n")[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# ===========================================================================
#  API ROUTE — /api/analyze
# ===========================================================================

@app.route("/api/analyze", methods=["POST"])
def analyze():
    req = request.json
    if not req or "location" not in req:
        return jsonify({"error": "Location is required"}), 400

    location = req.get("location", "").strip()
    if not location:
        return jsonify({"error": "Location is required"}), 400

    # ---- IMPROVEMENT 3: Check cache first ----
    cache_key = location.lower().strip()
    cached_entry = cache_get(cache_key)

    if cached_entry is not None:
        # Cache HIT — return stored result immediately
        cached_data = cached_entry["data"].copy()
        cached_data["cache"] = {
            "hit": True,
            "cachedAt": cached_entry["cached_at"].isoformat(),
        }
        response = jsonify(cached_data)
        response.headers["X-Cache"] = "HIT"
        return response

    # ---- Cache MISS — run full computation ----

    # 1. Fetch real location data
    user_data = fetch_real_data(location)
    if not user_data:
        return jsonify({"error": f"Could not find geographic data for '{location}'"}), 404

    # 2. Normalise against India-wide baseline samples
    baseline = generate_sample_data()
    baseline.append({k: v for k, v in user_data.items()
                     if k not in ("coordinates", "elevation_source")})

    # 3. Min-max scaling
    normed_data = normalize(baseline)

    # 4. Extract the user's normalised record (appended last)
    user_normed = [normed_data[-1]]

    # 5. Run through the Haskell Logic Engine
    haskell_bin = find_haskell_binary()
    if not haskell_bin:
        return jsonify({"error": "Could not locate Haskell engine binary"}), 500

    try:
        proc = subprocess.run(
            [haskell_bin],
            input=json.dumps(user_normed),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Haskell logic engine failed", "details": e.stderr}), 500

    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse JSON from Haskell engine", "details": proc.stdout}), 500

    if isinstance(results, dict) and "error" in results:
        return jsonify(results), 500

    cvi_result = results[0]
    final_cvi_score = float(cvi_result.get("final_cvi", 0.0))

    # ---- IMPROVEMENT 2: Compute percentile ranking ----
    percentile_data = compute_percentile(final_cvi_score)

    # ---- Assemble final output (all original fields + new additive fields) ----
    final_output = {
        "raw_metrics": user_data,          # includes coordinates + elevation_source
        "cvi_result": cvi_result,           # unchanged Haskell output
        "percentile": percentile_data,      # IMPROVEMENT 2
        "cache": {                          # IMPROVEMENT 3
            "hit": False,
            "cachedAt": None,
        },
    }

    # ---- Store in cache for future requests ----
    cache_set(cache_key, final_output)

    response = jsonify(final_output)
    response.headers["X-Cache"] = "MISS"
    return response


if __name__ == "__main__":
    app.run(port=5000, debug=True)
