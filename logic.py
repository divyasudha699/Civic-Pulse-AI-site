
import math, re

CATEGORY_WORDS = {
    "Water":["water","leak","leaking","pipe","tap","hydrant","burst"],
    "Road":["pothole","road","street","crack","asphalt","road damage"],
    "Waste":["garbage","trash","waste","dirty","dump","litter"],
    "Street Light":["street light","streetlight","lamp","dark","light not working"],
    "Drainage":["drain","drainage","sewage","sewer","overflow"],
}
DEPARTMENTS = {
    "Water":"BWSSB / Water Department",
    "Road":"Municipal Roads Department",
    "Waste":"Municipal Solid Waste Department",
    "Street Light":"Municipal Electrical Department",
    "Drainage":"Drainage Department",
    "Other":"Municipal Help Desk"
}

def classify_text(text):
    t = (text or "").lower()
    scores = {k: sum(1 for w in words if w in t) for k, words in CATEGORY_WORDS.items()}
    category = max(scores, key=scores.get) if scores and max(scores.values()) > 0 else "Other"
    severity = 3 if any(w in t for w in ["danger","accident","major","flood","burst","sewage","hospital","school"]) else (2 if category != "Other" else 1)
    return category, severity

def department_for(category):
    return DEPARTMENTS.get(category, DEPARTMENTS["Other"])

def normalize(text):
    t = (text or "").lower()
    t = t.replace("leaking","leak").replace("leakage","leak").replace("potholes","pothole").replace("streetlight","street light")
    t = re.sub(r"[^a-z0-9 ]+"," ",t)
    return re.sub(r"\s+"," ",t).strip()

def text_similarity(a,b):
    stop = {"the","a","an","is","are","to","of","at","on","in","near","and","for","with","this","that"}
    sa = {x for x in normalize(a).split() if x not in stop and len(x)>1}
    sb = {x for x in normalize(b).split() if x not in stop and len(x)>1}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

def haversine_m(lat1, lon1, lat2, lon2):
    try:
        lat1,lon1,lat2,lon2 = map(float,[lat1,lon1,lat2,lon2])
    except Exception:
        return None
    r = 6371000
    p1,p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.atan2(math.sqrt(a), math.sqrt(1-a))

def find_duplicate(incidents, category, description, lat=None, lon=None, pincode="", city=""):
    best = None
    best_score = 0.0
    for inc in incidents:
        if inc.get("status") == "Resolved" or inc.get("category") != category:
            continue
        loc_score = 0.0
        if lat is not None and lon is not None:
            d = haversine_m(lat,lon,inc.get("latitude"),inc.get("longitude"))
            if d is not None:
                loc_score = 1.0 if d <= 100 else 0.8 if d <= 300 else 0.5 if d <= 700 else 0.0
        if loc_score == 0 and pincode and str(inc.get("pincode","")) == str(pincode):
            loc_score = 0.6
        if loc_score == 0 and city and inc.get("city","").lower() == city.lower():
            loc_score = 0.35
        score = 0.60*loc_score + 0.40*text_similarity(description, inc.get("description",""))
        if score > best_score:
            best, best_score = inc, score
    if best and best_score >= 0.50:
        return best, round(best_score,3)
    return None, round(best_score,3)

def priority_score(severity, reporter_count):
    return min(10, int(severity)*2 + (1 if reporter_count >= 2 else 0) + (1 if reporter_count >= 4 else 0))
