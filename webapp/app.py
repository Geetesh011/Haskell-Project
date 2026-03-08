import sys
import os
import json
import subprocess
import requests
from flask import Flask, request, jsonify, render_template

# Add python_runner to path to import data_ingestion
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "python_runner"))
from data_ingestion import generate_sample_data, normalize

app = Flask(__name__)

def fetch_real_data(location_name: str) -> dict:
    """
    Fetch real geographic data using Open-Meteo Geocoding API.
    Extracts population and real elevation.
    Other specialized climate variables (like Sea-Level Rise, Mangroves) 
    are procedurally estimated based on the real latitude/longitude geography.
    """
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_name}&count=1&format=json"
    
    try:
        res = requests.get(geo_url).json()
    except Exception as e:
        return None

    if "results" not in res or len(res["results"]) == 0:
        return None

    geo = res["results"][0]
    district = geo.get("name", location_name)
    state = geo.get("admin1", geo.get("country", "Unknown"))
    
    # Real metrics from API
    elevation = geo.get("elevation", 10.0)
    lat = geo.get("latitude", 0.0)
    r_population = geo.get("population", None)
    
    # Estimate density
    if r_population:
        # Assume average district area of 800 sq km for density
        pop_density = r_population / 800.0
    else:
        # Fallback dense population
        pop_density = 800.0

    # Procedural/Realistic generation for variables lacking free global real-time APIs
    abs_lat = abs(lat)
    
    # Cyclones occur mostly between 10-30 degrees latitude globally
    if 10 <= abs_lat <= 30:
        cyclone_freq = 3.5
    elif abs_lat < 10:
        cyclone_freq = 1.0
    else:
        cyclone_freq = 0.5
        
    # Mangrove covers are usually tropical (0 to 25 deg lat)
    mangrove = 15.0 if abs_lat < 25 else 1.0
    
    # SLR (global avg is ~3.4 mm/yr, we add variance based on lat)
    slr = 3.2 + (abs_lat % 2.0)
    
    # Default assumptions (as real-time APIs don't exist for these without premium GIS subscriptions)
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
    }


def find_haskell_binary() -> str:
    """Find the compiled Haskell executable using Stack."""
    try:
        result = subprocess.run(
            ["stack", "exec", "--", "where", "cvi-backend"],
            cwd=os.path.join(os.path.dirname(__file__), "..", "cvi-backend"),
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/analyze", methods=["POST"])
def analyze():
    req = request.json
    if not req or "location" not in req:
        return jsonify({"error": "Location is required"}), 400

    location = req.get("location", "").strip()
    if not location:
        return jsonify({"error": "Location is required"}), 400

    # 1. Fetch real location data
    user_data = fetch_real_data(location)
    if not user_data:
         return jsonify({"error": f"Could not find geographic data for '{location}'"}), 404
         
    # 2. To normalize properly, we attach it to the baseline realistic samples
    baseline = generate_sample_data()
    baseline.append(user_data)
    
    # 3. Normalize the entire set (min-max scaling against India baselines)
    normed_data = normalize(baseline)
    
    # 4. Extract the user's normalized record (it was appended last)
    user_normed = [normed_data[-1]]
    
    # 5. Run through the Haskell Logic Engine
    haskell_bin = find_haskell_binary()
    if not haskell_bin:
        return jsonify({"error": "Could not locate Haskell engine binary"}), 500

    try:
        # Pass JSON string to stdin of the Haskell binary
        proc = subprocess.run(
            [haskell_bin],
            input=json.dumps(user_normed),
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Haskell logic engine failed", "details": e.stderr}), 500

    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse JSON from Haskell engine", "details": proc.stdout}), 500

    if isinstance(results, dict) and "error" in results:
        return jsonify(results), 500
        
    final_output = {
        "raw_metrics": user_data,
        "cvi_result": results[0]
    }
    
    return jsonify(final_output)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
