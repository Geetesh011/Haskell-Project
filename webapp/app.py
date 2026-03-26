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
CORS(app)

# ===========================================================================
#  CACHE
# ===========================================================================
_cache: dict = {}
_cache_lock = threading.Lock()
CACHE_TTL_SECONDS = 86400

def cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if (datetime.now(timezone.utc) - entry["cached_at"]).total_seconds() > CACHE_TTL_SECONDS:
            del _cache[key]
            return None
        return entry

def cache_set(key, data):
    with _cache_lock:
        _cache[key] = {"data": data, "cached_at": datetime.now(timezone.utc)}

# ===========================================================================
#  GLOBAL ND-GAIN 2023 DATASET  (Notre Dame Global Adaptation Initiative)
#  Values: score/100, vulnerability 0-1, readiness 0-1, rank/187
# ===========================================================================
NDGAIN_COUNTRIES = {
    "NOR":{"name":"Norway",       "score":79.36,"vuln":0.327,"readiness":0.851,"rank":1,  "region":"europe"},
    "SWE":{"name":"Sweden",       "score":76.00,"vuln":0.335,"readiness":0.812,"rank":2,  "region":"europe"},
    "FIN":{"name":"Finland",      "score":75.10,"vuln":0.341,"readiness":0.793,"rank":3,  "region":"europe"},
    "DNK":{"name":"Denmark",      "score":73.80,"vuln":0.338,"readiness":0.772,"rank":4,  "region":"europe"},
    "CHE":{"name":"Switzerland",  "score":73.50,"vuln":0.342,"readiness":0.768,"rank":5,  "region":"europe"},
    "NLD":{"name":"Netherlands",  "score":73.20,"vuln":0.340,"readiness":0.762,"rank":6,  "region":"europe"},
    "AUS":{"name":"Australia",    "score":70.80,"vuln":0.341,"readiness":0.728,"rank":8,  "region":"oceania"},
    "NZL":{"name":"New Zealand",  "score":70.20,"vuln":0.345,"readiness":0.719,"rank":9,  "region":"oceania"},
    "GBR":{"name":"United Kingdom","score":68.50,"vuln":0.353,"readiness":0.701,"rank":11,"region":"europe"},
    "DEU":{"name":"Germany",      "score":67.80,"vuln":0.355,"readiness":0.694,"rank":12, "region":"europe"},
    "CAN":{"name":"Canada",       "score":67.30,"vuln":0.352,"readiness":0.689,"rank":13, "region":"north_america"},
    "AUT":{"name":"Austria",      "score":66.20,"vuln":0.358,"readiness":0.675,"rank":14, "region":"europe"},
    "USA":{"name":"United States","score":63.99,"vuln":0.329,"readiness":0.636,"rank":15, "region":"north_america"},
    "FRA":{"name":"France",       "score":63.20,"vuln":0.361,"readiness":0.628,"rank":16, "region":"europe"},
    "SGP":{"name":"Singapore",    "score":65.10,"vuln":0.351,"readiness":0.654,"rank":17, "region":"southeast_asia"},
    "BEL":{"name":"Belgium",      "score":62.80,"vuln":0.365,"readiness":0.621,"rank":18, "region":"europe"},
    "IRL":{"name":"Ireland",      "score":62.50,"vuln":0.362,"readiness":0.617,"rank":19, "region":"europe"},
    "JPN":{"name":"Japan",        "score":62.40,"vuln":0.365,"readiness":0.616,"rank":20, "region":"east_asia"},
    "ISR":{"name":"Israel",       "score":61.80,"vuln":0.366,"readiness":0.610,"rank":21, "region":"middle_east"},
    "PRT":{"name":"Portugal",     "score":61.50,"vuln":0.368,"readiness":0.607,"rank":22, "region":"europe"},
    "ESP":{"name":"Spain",        "score":61.00,"vuln":0.371,"readiness":0.601,"rank":23, "region":"europe"},
    "CZE":{"name":"Czech Republic","score":60.20,"vuln":0.374,"readiness":0.591,"rank":26,"region":"europe"},
    "ITA":{"name":"Italy",        "score":59.80,"vuln":0.378,"readiness":0.585,"rank":27, "region":"europe"},
    "KOR":{"name":"South Korea",  "score":58.90,"vuln":0.379,"readiness":0.578,"rank":29, "region":"east_asia"},
    "POL":{"name":"Poland",       "score":58.10,"vuln":0.382,"readiness":0.572,"rank":30, "region":"europe"},
    "HUN":{"name":"Hungary",      "score":57.80,"vuln":0.385,"readiness":0.567,"rank":32, "region":"europe"},
    "ARE":{"name":"UAE",          "score":56.70,"vuln":0.391,"readiness":0.554,"rank":37, "region":"middle_east"},
    "CHL":{"name":"Chile",        "score":56.80,"vuln":0.391,"readiness":0.555,"rank":36, "region":"latin_america"},
    "CHN":{"name":"China",        "score":58.71,"vuln":0.423,"readiness":0.572,"rank":39, "region":"east_asia"},
    "TUR":{"name":"Turkey",       "score":53.80,"vuln":0.406,"readiness":0.526,"rank":50, "region":"middle_east"},
    "SAU":{"name":"Saudi Arabia", "score":54.20,"vuln":0.401,"readiness":0.529,"rank":47, "region":"middle_east"},
    "ARG":{"name":"Argentina",    "score":55.30,"vuln":0.399,"readiness":0.540,"rank":42, "region":"latin_america"},
    "RUS":{"name":"Russia",       "score":52.30,"vuln":0.412,"readiness":0.509,"rank":60, "region":"europe"},
    "MYS":{"name":"Malaysia",     "score":53.20,"vuln":0.409,"readiness":0.519,"rank":54, "region":"southeast_asia"},
    "BRA":{"name":"Brazil",       "score":53.12,"vuln":0.409,"readiness":0.519,"rank":54, "region":"latin_america"},
    "MEX":{"name":"Mexico",       "score":52.10,"vuln":0.413,"readiness":0.508,"rank":62, "region":"latin_america"},
    "THA":{"name":"Thailand",     "score":50.30,"vuln":0.434,"readiness":0.490,"rank":83, "region":"southeast_asia"},
    "COL":{"name":"Colombia",     "score":49.20,"vuln":0.443,"readiness":0.481,"rank":92, "region":"latin_america"},
    "IDN":{"name":"Indonesia",    "score":48.38,"vuln":0.458,"readiness":0.472,"rank":98, "region":"southeast_asia"},
    "VNM":{"name":"Vietnam",      "score":47.80,"vuln":0.451,"readiness":0.467,"rank":104,"region":"southeast_asia"},
    "PER":{"name":"Peru",         "score":47.50,"vuln":0.454,"readiness":0.464,"rank":105,"region":"latin_america"},
    "ZAF":{"name":"South Africa", "score":47.20,"vuln":0.456,"readiness":0.461,"rank":106,"region":"africa"},
    "ECU":{"name":"Ecuador",      "score":46.20,"vuln":0.467,"readiness":0.449,"rank":111,"region":"latin_america"},
    "LKA":{"name":"Sri Lanka",    "score":46.10,"vuln":0.468,"readiness":0.448,"rank":111,"region":"south_asia"},
    "TUN":{"name":"Tunisia",      "score":46.80,"vuln":0.463,"readiness":0.457,"rank":107,"region":"middle_east"},
    "PHL":{"name":"Philippines",  "score":45.61,"vuln":0.473,"readiness":0.444,"rank":110,"region":"southeast_asia"},
    "IND":{"name":"India",        "score":45.46,"vuln":0.4846,"readiness":0.3937,"rank":112,"region":"south_asia"},
    "MAR":{"name":"Morocco",      "score":45.20,"vuln":0.473,"readiness":0.441,"rank":114,"region":"middle_east"},
    "IRN":{"name":"Iran",         "score":45.80,"vuln":0.471,"readiness":0.447,"rank":109,"region":"middle_east"},
    "PRY":{"name":"Paraguay",     "score":44.30,"vuln":0.476,"readiness":0.432,"rank":118,"region":"latin_america"},
    "EGY":{"name":"Egypt",        "score":43.10,"vuln":0.481,"readiness":0.420,"rank":126,"region":"middle_east"},
    "DZA":{"name":"Algeria",      "score":42.30,"vuln":0.486,"readiness":0.413,"rank":130,"region":"middle_east"},
    "VEN":{"name":"Venezuela",    "score":42.10,"vuln":0.487,"readiness":0.411,"rank":132,"region":"latin_america"},
    "KHM":{"name":"Cambodia",     "score":41.20,"vuln":0.495,"readiness":0.401,"rank":138,"region":"southeast_asia"},
    "FJI":{"name":"Fiji",         "score":40.80,"vuln":0.497,"readiness":0.398,"rank":141,"region":"oceania"},
    "GHA":{"name":"Ghana",        "score":38.40,"vuln":0.516,"readiness":0.375,"rank":156,"region":"africa"},
    "LAO":{"name":"Laos",         "score":40.10,"vuln":0.501,"readiness":0.391,"rank":145,"region":"southeast_asia"},
    "WSM":{"name":"Samoa",        "score":40.20,"vuln":0.500,"readiness":0.392,"rank":144,"region":"oceania"},
    "BOL":{"name":"Bolivia",      "score":39.60,"vuln":0.504,"readiness":0.386,"rank":149,"region":"latin_america"},
    "IRQ":{"name":"Iraq",         "score":38.20,"vuln":0.515,"readiness":0.373,"rank":157,"region":"middle_east"},
    "PAK":{"name":"Pakistan",     "score":39.21,"vuln":0.509,"readiness":0.382,"rank":151,"region":"south_asia"},
    "NGA":{"name":"Nigeria",      "score":33.02,"vuln":0.553,"readiness":0.323,"rank":152,"region":"africa"},
    "MMR":{"name":"Myanmar",      "score":39.80,"vuln":0.503,"readiness":0.388,"rank":148,"region":"southeast_asia"},
    "KEN":{"name":"Kenya",        "score":36.80,"vuln":0.523,"readiness":0.360,"rank":166,"region":"africa"},
    "SEN":{"name":"Senegal",      "score":35.20,"vuln":0.533,"readiness":0.344,"rank":172,"region":"africa"},
    "BGD":{"name":"Bangladesh",   "score":35.55,"vuln":0.531,"readiness":0.347,"rank":174,"region":"south_asia"},
    "NPL":{"name":"Nepal",        "score":38.50,"vuln":0.514,"readiness":0.376,"rank":155,"region":"south_asia"},
    "PNG":{"name":"Papua New Guinea","score":30.20,"vuln":0.566,"readiness":0.295,"rank":163,"region":"oceania"},
    "ETH":{"name":"Ethiopia",     "score":31.40,"vuln":0.561,"readiness":0.307,"rank":160,"region":"africa"},
    "UGA":{"name":"Uganda",       "score":30.80,"vuln":0.564,"readiness":0.301,"rank":162,"region":"africa"},
    "TZA":{"name":"Tanzania",     "score":32.10,"vuln":0.558,"readiness":0.314,"rank":158,"region":"africa"},
    "ZMB":{"name":"Zambia",       "score":31.60,"vuln":0.560,"readiness":0.309,"rank":159,"region":"africa"},
    "MOZ":{"name":"Mozambique",   "score":27.80,"vuln":0.580,"readiness":0.272,"rank":181,"region":"africa"},
    "MDG":{"name":"Madagascar",   "score":28.90,"vuln":0.575,"readiness":0.283,"rank":177,"region":"africa"},
    "COD":{"name":"DR Congo",     "score":24.30,"vuln":0.603,"readiness":0.238,"rank":186,"region":"africa"},
    "HTI":{"name":"Haiti",        "score":27.10,"vuln":0.583,"readiness":0.265,"rank":183,"region":"latin_america"},
    "AFG":{"name":"Afghanistan",  "score":27.60,"vuln":0.581,"readiness":0.269,"rank":182,"region":"south_asia"},
    "YEM":{"name":"Yemen",        "score":24.60,"vuln":0.601,"readiness":0.241,"rank":185,"region":"middle_east"},
}

# ISO 3166-1 alpha-2 → alpha-3 mapping
ISO2_TO_ISO3 = {
    "NO":"NOR","SE":"SWE","FI":"FIN","DK":"DNK","CH":"CHE","NL":"NLD",
    "AU":"AUS","NZ":"NZL","GB":"GBR","DE":"DEU","CA":"CAN","AT":"AUT",
    "US":"USA","FR":"FRA","BE":"BEL","IE":"IRL","ES":"ESP","IT":"ITA",
    "PT":"PRT","GR":"GRC","PL":"POL","CZ":"CZE","HU":"HUN","RO":"ROU",
    "BG":"BGR","RU":"RUS","UA":"UKR","TR":"TUR","JP":"JPN","KR":"KOR",
    "CN":"CHN","MN":"MNG","SG":"SGP","MY":"MYS","TH":"THA","VN":"VNM",
    "PH":"PHL","ID":"IDN","MM":"MMR","KH":"KHM","LA":"LAO","IN":"IND",
    "PK":"PAK","BD":"BGD","LK":"LKA","NP":"NPL","AF":"AFG","IL":"ISR",
    "SA":"SAU","AE":"ARE","IR":"IRN","IQ":"IRQ","EG":"EGY","MA":"MAR",
    "TN":"TUN","DZ":"DZA","LY":"LBY","SY":"SYR","YE":"YEM","MX":"MEX",
    "CU":"CUB","HT":"HTI","JM":"JAM","BR":"BRA","AR":"ARG","CL":"CHL",
    "CO":"COL","PE":"PER","VE":"VEN","BO":"BOL","EC":"ECU","PY":"PRY",
    "ZA":"ZAF","NG":"NGA","ET":"ETH","KE":"KEN","TZ":"TZA","GH":"GHA",
    "SN":"SEN","MZ":"MOZ","ZM":"ZMB","ZW":"ZWE","AO":"AGO","CM":"CMR",
    "CD":"COD","MG":"MDG","UG":"UGA","RW":"RWA","SD":"SDN","PG":"PNG",
    "FJ":"FJI","SB":"SLB","VU":"VUT","WS":"WSM","TO":"TON",
    "NP":"NPL","BE":"BEL",
}

# Regional peers for comparison display
REGIONAL_PEERS = {
    "europe":       ["NOR","SWE","NLD","DEU","GBR","FRA","ESP","ITA","POL","RUS"],
    "north_america":["USA","CAN","MEX"],
    "latin_america":["BRA","ARG","CHL","COL","PER","VEN","MEX","ECU","BOL"],
    "east_asia":    ["CHN","JPN","KOR"],
    "southeast_asia":["SGP","MYS","THA","IDN","VNM","PHL","MMR","KHM"],
    "south_asia":   ["IND","PAK","BGD","LKA","NPL","AFG"],
    "middle_east":  ["TUR","SAU","ARE","IRN","EGY","ISR","MAR","IRQ","YEM"],
    "africa":       ["ZAF","NGA","ETH","KEN","TZA","GHA","MOZ","SEN","MDG","COD"],
    "oceania":      ["AUS","NZL","IDN","PNG","FJI","PHL","VUT","WSM"],
}

# ===========================================================================
#  ND-GAIN HELPER FUNCTIONS
# ===========================================================================
def nd_gain_penalty(vuln: float, readiness: float) -> float:
    gap = vuln - readiness
    if gap > 0.15:   return 0.12
    elif gap > 0.09: return 0.07
    elif gap > 0.05: return 0.03
    elif gap <= 0.0: return -0.05
    else:            return 0.01

def nd_gain_penalty_rule(vuln: float, readiness: float) -> str:
    gap = vuln - readiness
    if gap > 0.15:   return "gap > 0.15 → CRITICAL DEFICIT → penalty = +0.12"
    elif gap > 0.09: return "gap > 0.09 → HIGH DEFICIT → penalty = +0.07"
    elif gap > 0.05: return "gap > 0.05 → MODERATE DEFICIT → penalty = +0.03"
    elif gap <= 0.0: return "gap ≤ 0.0 → READINESS SURPLUS → bonus = −0.05"
    else:            return "gap ≤ 0.05 → LOW DEFICIT → penalty = +0.01"

def get_country_ndgain(iso3: str) -> dict:
    d = NDGAIN_COUNTRIES.get(iso3, {
        "name": iso3, "score": 45.0, "vuln": 0.50,
        "readiness": 0.42, "rank": 100, "region": "unknown"
    })
    vuln, ready = d["vuln"], d["readiness"]
    gap    = round(vuln - ready, 4)
    pen    = nd_gain_penalty(vuln, ready)
    rule   = nd_gain_penalty_rule(vuln, ready)
    return {
        "country_code":       iso3,
        "country_name":       d["name"],
        "score":              d["score"],
        "vulnerability":      vuln,
        "readiness":          ready,
        "adaptation_gap":     gap,
        "adaptation_penalty": round(pen, 4),
        "global_rank":        d["rank"],
        "total_countries":    187,
        "rank_percentile":    round((d["rank"] / 187) * 100),
        "region":             d.get("region", "unknown"),
        "penalty_rule":       rule,
        "year":               2023,
        "interpretation":     (
            f"{d['name']} ranks {d['rank']}/187. "
            f"Adaptation gap {gap:.4f} → {rule}. "
            f"Penalty {'+' if pen >= 0 else ''}{pen:.2f} applied to CVI score."
        ),
    }

def get_regional_comparison(iso3: str, region: str) -> list:
    peers = list(REGIONAL_PEERS.get(region, []))
    if iso3 not in peers:
        peers.insert(0, iso3)
    # Deduplicate, keep up to 8
    seen, unique = set(), []
    for c in peers:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    result = []
    for code in unique[:10]:
        d = NDGAIN_COUNTRIES.get(code)
        if d:
            result.append({
                "country":   d["name"],
                "code":      code,
                "score":     d["score"],
                "rank":      d["rank"],
                "highlight": code == iso3,
            })
    result.sort(key=lambda x: x["score"], reverse=True)
    return result[:8]

def estimate_tidal_range(lat: float, lon: float) -> float:
    """Rough global tidal range estimate from lat/lon geography."""
    # Mediterranean: micro-tidal
    if 30 <= lat <= 47 and -5 <= lon <= 37:
        return 0.4
    # Bay of Fundy
    if 43 <= lat <= 52 and -66 <= lon <= -63:
        return 12.0
    # Bristol Channel / UK west
    if 50 <= lat <= 56 and -5.5 <= lon <= -2.5:
        return 8.0
    # Gulf of Mexico / Caribbean
    if 15 <= lat <= 31 and -98 <= lon <= -60:
        return 0.5
    # North Sea
    if 51 <= lat <= 58 and 0 <= lon <= 10:
        return 3.5
    # SE Asia
    if -10 <= lat <= 20 and 95 <= lon <= 145:
        return 2.0
    # Australia NW: macro-tidal
    if -25 <= lat <= -15 and 110 <= lon <= 130:
        return 5.0
    # Australia east: micro-tidal
    if -38 <= lat <= -20 and 145 <= lon <= 155:
        return 1.5
    # West Africa
    if -5 <= lat <= 20 and -20 <= lon <= 20:
        return 1.5
    return 1.5  # global fallback

def estimate_social_vuln(iso3: str) -> float:
    """Social vulnerability from inverted ND-GAIN readiness."""
    d = NDGAIN_COUNTRIES.get(iso3)
    if d:
        return round(max(0.10, min(0.90, 1.0 - d["readiness"])), 2)
    return 0.50

# ===========================================================================
#  PERCENTILE TABLE  (kept for backward compat)
# ===========================================================================
DISTRICT_CVI_TABLE = {
    "Bapatla":0.5849,"Kakinada":0.7210,"Visakhapatnam":0.6340,
    "Nellore":0.5920,"Ongole":0.5650,"Guntur":0.5200,"Krishna":0.6100,
    "West Godavari":0.5800,"East Godavari":0.6300,"Srikakulam":0.6800,
    "Chennai":0.5509,"Puducherry":0.5800,"Cuddalore":0.6010,
    "Nagapattinam":0.6750,"Kanyakumari":0.4200,"Puri":0.7680,
    "Balasore":0.7100,"Kendrapara":0.7300,"Paradip":0.6900,
    "Mangaluru":0.3200,"Udupi":0.3500,"Kozhikode":0.4800,
    "Kochi":0.5100,"Thiruvananthapuram":0.4500,"Alappuzha":0.5600,
    "Kollam":0.4900,"Mumbai":0.6200,"Raigad":0.5100,"Ratnagiri":0.2980,
    "Sindhudurg":0.3100,"Goa":0.4200,"Surat":0.5500,"Bharuch":0.4800,
    "Navsari":0.5200,"Kolkata":0.6800,"South 24 Parganas":0.7500,
    "Digha":0.6900,"Sundarbans":0.7800,
}

# India-specific lookup tables (kept for priority use on Indian cities)
GEOMORPHOLOGY_DATA = {
    "chennai":"Sandy Beach","mumbai":"Rocky Cliff","kochi":"Mangrove",
    "visakhapatnam":"Sandy Beach","puri":"Sandy Beach","mangaluru":"Sandy Beach",
    "kakinada":"Mangrove","bapatla":"Sandy Beach","kolkata":"Delta",
    "surat":"Mudflat","kanyakumari":"Rocky Cliff","thiruvananthapuram":"Sandy Beach",
    "kozhikode":"Sandy Beach","alappuzha":"Mangrove","kollam":"Sandy Beach",
    "puducherry":"Sandy Beach","cuddalore":"Mangrove","nagapattinam":"Sandy Beach",
    "nellore":"Mudflat","ongole":"Sandy Beach","bhubaneswar":"Sandy Beach",
    "paradip":"Delta","balasore":"Sandy Beach","kendrapara":"Mangrove",
    "udupi":"Rocky Cliff","raigad":"Rocky Cliff","ratnagiri":"Rocky Cliff",
    "sindhudurg":"Rocky Cliff","goa":"Sandy Beach","bharuch":"Mudflat",
    "navsari":"Sandy Beach","digha":"Sandy Beach","sundarbans":"Mangrove",
    "srikakulam":"Sandy Beach","vizianagaram":"Sandy Beach","guntur":"Mudflat",
    "krishna":"Mangrove","east godavari":"Mangrove","west godavari":"Mangrove",
}
SHORELINE_DATA = {
    "chennai":-1.2,"mumbai":-0.8,"kochi":-0.5,"visakhapatnam":-1.8,
    "puri":-2.1,"mangaluru":-0.9,"kakinada":-0.7,"bapatla":-1.5,
    "kolkata":-3.2,"surat":-1.1,"kanyakumari":0.3,"thiruvananthapuram":-0.6,
    "kozhikode":-0.8,"alappuzha":-1.9,"kollam":-0.7,"puducherry":-1.3,
    "cuddalore":-1.6,"nagapattinam":-2.4,"nellore":-1.0,"ongole":-1.2,
    "bhubaneswar":-0.9,"paradip":-2.8,"balasore":-1.4,"kendrapara":-2.1,
    "udupi":0.2,"raigad":-0.4,"ratnagiri":0.1,"sindhudurg":0.3,
    "goa":-0.6,"bharuch":-0.5,"navsari":-0.8,"digha":-3.5,
    "sundarbans":-4.2,"srikakulam":-1.6,"vizianagaram":-1.1,
    "guntur":-0.9,"krishna":-1.7,"east godavari":-1.4,"west godavari":-1.3,
}
TIDAL_DATA = {
    "chennai":1.0,"mumbai":5.2,"kochi":0.8,"visakhapatnam":1.1,
    "puri":1.6,"mangaluru":1.4,"kakinada":1.2,"bapatla":1.0,
    "kolkata":4.5,"surat":6.8,"kanyakumari":0.6,"thiruvananthapuram":0.7,
    "kozhikode":0.9,"alappuzha":0.8,"kollam":0.7,"puducherry":1.0,
    "cuddalore":1.1,"nagapattinam":1.3,"nellore":1.2,"ongole":1.1,
    "bhubaneswar":1.8,"paradip":2.1,"balasore":3.4,"kendrapara":3.2,
    "udupi":1.3,"raigad":4.8,"ratnagiri":3.9,"sindhudurg":2.8,
    "goa":2.1,"bharuch":7.2,"navsari":5.8,"digha":3.6,
    "sundarbans":4.8,"srikakulam":1.2,"vizianagaram":1.1,
    "guntur":1.4,"krishna":1.6,"east godavari":1.5,"west godavari":1.4,
}
SOCIAL_VULN_DATA = {
    "chennai":0.38,"mumbai":0.42,"kochi":0.28,"visakhapatnam":0.52,
    "puri":0.65,"mangaluru":0.31,"kakinada":0.55,"bapatla":0.61,
    "kolkata":0.58,"surat":0.45,"kanyakumari":0.35,"thiruvananthapuram":0.29,
    "kozhikode":0.32,"alappuzha":0.41,"kollam":0.38,"puducherry":0.33,
    "cuddalore":0.58,"nagapattinam":0.62,"nellore":0.54,"ongole":0.57,
    "bhubaneswar":0.48,"paradip":0.66,"balasore":0.63,"kendrapara":0.68,
    "udupi":0.27,"raigad":0.49,"ratnagiri":0.44,"sindhudurg":0.39,
    "goa":0.31,"bharuch":0.47,"navsari":0.43,"digha":0.69,
    "sundarbans":0.74,"srikakulam":0.64,"vizianagaram":0.61,
    "guntur":0.53,"krishna":0.51,"east godavari":0.56,"west godavari":0.54,
}

def derive_geomorphology(elevation: float, lat: float) -> str:
    """Estimate geomorphology from elevation and latitude for non-Indian cities."""
    if elevation < 2:   return "Delta" if abs(lat) < 25 else "Mudflat"
    elif elevation < 8: return "Sandy Beach"
    elif elevation < 20: return "Sandy Beach"
    else:               return "Rocky Cliff"

def compute_percentile(final_cvi: float) -> dict:
    scores = list(DISTRICT_CVI_TABLE.values())
    total  = len(scores)
    worse  = sum(1 for s in scores if s < final_cvi)
    pct    = round((worse / total) * 100)
    return {
        "rank": pct, "rankedOutOf": total, "worseThan": worse,
        "interpretation": f"More vulnerable than {pct}% of reference coastal areas",
    }

# ===========================================================================
#  GEOCODING + ELEVATION
# ===========================================================================
def geocode_nominatim(location_name: str):
    try:
        url = (f"https://nominatim.openstreetmap.org/search"
               f"?q={requests.utils.quote(location_name)}&format=json&limit=1&addressdetails=1")
        resp = requests.get(url, headers={"User-Agent": "CVI-Backend/2.0"}, timeout=5)
        results = resp.json()
        if not results:
            return None
        top = results[0]
        addr = top.get("address", {})
        # Extract country code (ISO2)
        country_code_iso2 = addr.get("country_code", "").upper()
        return (float(top["lat"]), float(top["lon"]),
                top.get("display_name", location_name), country_code_iso2)
    except Exception:
        return None

def get_open_elevation(lat: float, lon: float):
    try:
        url  = f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lon}"
        resp = requests.get(url, timeout=8)
        return float(resp.json()["results"][0]["elevation"])
    except Exception:
        return None

# ===========================================================================
#  MAIN DATA FETCHER  (global-aware)
# ===========================================================================
def fetch_real_data(location_name: str) -> dict:
    geo_url = (f"https://geocoding-api.open-meteo.com/v1/search"
               f"?name={requests.utils.quote(location_name)}&count=1&format=json")
    try:
        res = requests.get(geo_url, timeout=6).json()
    except Exception:
        return None
    if "results" not in res or not res["results"]:
        return None

    geo        = res["results"][0]
    district   = geo.get("name", location_name)
    state      = geo.get("admin1", geo.get("country", "Unknown"))
    elevation  = geo.get("elevation", 10.0)
    lat        = geo.get("latitude",  0.0)
    lon        = geo.get("longitude", 0.0)
    r_pop      = geo.get("population", None)
    # Open-Meteo gives 2-letter country code
    om_iso2    = geo.get("country_code", "").upper()

    # Try Nominatim for a more precise lat/lon + country code
    nom_result       = geocode_nominatim(location_name)
    coordinates      = {"lat": lat, "lon": lon}
    elevation_source = "OPEN-METEO"
    nom_iso2         = om_iso2

    if nom_result:
        nom_lat, nom_lon, _, n_iso2 = nom_result
        coordinates = {"lat": nom_lat, "lon": nom_lon}
        if n_iso2:
            nom_iso2 = n_iso2
        srtm = get_open_elevation(nom_lat, nom_lon)
        if srtm is not None:
            elevation        = srtm
            elevation_source = "OPEN-ELEVATION/SRTM"

    # Resolve ISO3
    iso2    = nom_iso2 or om_iso2
    iso3    = ISO2_TO_ISO3.get(iso2, "IND")   # fallback India
    is_india = (iso3 == "IND")

    # Lookup district key for Indian city tables
    dk = district.lower()

    # Geomorphology
    geo_type = (GEOMORPHOLOGY_DATA.get(dk)
                if is_india
                else derive_geomorphology(elevation, lat))

    # Shoreline change
    shoreline = (SHORELINE_DATA.get(dk, 0.0)
                 if is_india else -0.5)

    # Tidal range
    tidal = (TIDAL_DATA.get(dk, 1.5)
             if is_india
             else estimate_tidal_range(lat, lon))

    # Social vulnerability
    sv = (SOCIAL_VULN_DATA.get(dk)
          if (is_india and dk in SOCIAL_VULN_DATA)
          else estimate_social_vuln(iso3))

    # Population
    pop_density = (r_pop / 800.0) if r_pop else 800.0

    abs_lat = abs(lat)
    cyclone_freq = 3.5 if 10 <= abs_lat <= 30 else (1.0 if abs_lat < 10 else 0.5)
    mangrove     = 15.0 if abs_lat < 25 else 1.0
    slr          = 3.2 + (abs_lat % 2.0)
    erosion      = 2.0
    income       = 180000
    drainage     = 4

    return {
        "district":            district,
        "state":               state,
        "country_code":        iso3,
        "country_name":        NDGAIN_COUNTRIES.get(iso3, {}).get("name", iso2),
        "elevation_m":         elevation,
        "erosion_rate_m_yr":   erosion,
        "slr_mm_yr":           slr,
        "pop_density_km2":     pop_density,
        "income_level_inr":    income,
        "cyclone_freq":        cyclone_freq,
        "mangrove_cover_pct":  mangrove,
        "drainage_quality":    drainage,
        "geomorphology":       geo_type or "Sandy Beach",
        "shoreline_change_m_yr": str(shoreline),
        "tidal_range_m":       str(tidal),
        "social_vuln_index":   str(sv),
        "lookup_district":     dk,
        "api_version":         "2.0",
        "coordinates":         coordinates,
        "elevation_source":    elevation_source,
    }

# ===========================================================================
#  HASKELL BINARY FINDER
# ===========================================================================
def find_haskell_binary() -> str:
    prod_path = "/usr/local/bin/cvi-backend"
    if os.path.exists(prod_path):
        return prod_path
    shell_cmd = "where" if os.name == "nt" else "which"
    try:
        subprocess.run(["stack", "--version"], capture_output=True, check=True)
        result = subprocess.run(
            ["stack", "exec", "--", shell_cmd, "cvi-backend"],
            cwd=os.path.join(os.path.dirname(__file__), "..", "cvi-backend"),
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip().split("\n")[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

# ===========================================================================
#  API  /api/analyze
# ===========================================================================
@app.route("/api/analyze", methods=["POST"])
def analyze():
    req = request.json
    if not req or "location" not in req:
        return jsonify({"error": "Location is required"}), 400
    location = req.get("location", "").strip()
    if not location:
        return jsonify({"error": "Location is required"}), 400

    cache_key    = f"v4:{location.lower().strip()}"
    cached_entry = cache_get(cache_key)
    if cached_entry is not None:
        cached_data         = cached_entry["data"].copy()
        cached_data["cache"]= {"hit": True, "cachedAt": cached_entry["cached_at"].isoformat()}
        resp = jsonify(cached_data)
        resp.headers["X-Cache"] = "HIT"
        return resp

    # 1. Fetch real geographic data
    user_data = fetch_real_data(location)
    if not user_data:
        return jsonify({"error": f"Could not find geographic data for '{location}'"}), 404

    iso3       = user_data.get("country_code", "IND")
    ndgain_raw = get_country_ndgain(iso3)
    region     = ndgain_raw.get("region", "unknown")
    regional   = get_regional_comparison(iso3, region)
    ndgain_raw["regional_comparison"] = regional

    # 2. Normalise against India-wide baseline samples
    baseline   = generate_sample_data()
    user_plain = {k: v for k, v in user_data.items()
                  if k not in ("coordinates", "elevation_source",
                               "country_code", "country_name")}
    baseline.append(user_plain)
    normed_data = normalize(baseline)
    user_normed = [normed_data[-1]]

    # 3. Run Haskell engine
    haskell_bin = find_haskell_binary()
    if not haskell_bin:
        return jsonify({"error": "Could not locate Haskell engine binary"}), 500
    try:
        proc = subprocess.run(
            [haskell_bin], input=json.dumps(user_normed),
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Haskell logic engine failed", "details": e.stderr}), 500

    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse Haskell JSON", "details": proc.stdout}), 500

    if isinstance(results, dict) and "error" in results:
        return jsonify(results), 500

    cvi_result = results[0]

    # 4. Correct final_cvi: replace hardcoded India ND-GAIN penalty with correct country penalty
    base_cvi      = float(cvi_result.get("base_cvi", 0.0))
    pat_penalty   = float(cvi_result.get("pattern_penalty", 0.0))
    base_with_pat = min(1.0, base_cvi + pat_penalty)
    country_pen   = ndgain_raw["adaptation_penalty"]
    corrected_cvi = round(min(1.0, base_with_pat + country_pen), 4)
    cvi_result["final_cvi"] = corrected_cvi

    # Re-categorise with corrected score
    if corrected_cvi >= 0.75:   cvi_result["category"] = "Very High"
    elif corrected_cvi >= 0.55: cvi_result["category"] = "High"
    elif corrected_cvi >= 0.35: cvi_result["category"] = "Moderate"
    else:                       cvi_result["category"] = "Low"

    # 5. Percentile
    percentile_data = compute_percentile(corrected_cvi)

    final_output = {
        "raw_metrics": user_data,
        "cvi_result":  cvi_result,
        "ndgain":      ndgain_raw,
        "percentile":  percentile_data,
        "cache":       {"hit": False, "cachedAt": None},
    }
    cache_set(cache_key, final_output)
    resp = jsonify(final_output)
    resp.headers["X-Cache"] = "MISS"
    return resp


if __name__ == "__main__":
    app.run(port=5000, debug=True)


