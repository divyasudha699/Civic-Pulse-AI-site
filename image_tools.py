
import io, os, base64, json, requests
from PIL import Image, ExifTags

def photo_gps(data):
    try:
        im = Image.open(io.BytesIO(data))
        exif = im.getexif()
        gps_tag = next((k for k,v in ExifTags.TAGS.items() if v == "GPSInfo"), None)
        if not gps_tag or gps_tag not in exif:
            return None, None
        gps = exif.get_ifd(gps_tag)
        named = {ExifTags.GPSTAGS.get(k,k):v for k,v in gps.items()}
        def dec(vals, ref):
            d,m,s = float(vals[0]),float(vals[1]),float(vals[2])
            x = d + m/60 + s/3600
            return -x if ref in ("S","W") else x
        return dec(named["GPSLatitude"],named["GPSLatitudeRef"]), dec(named["GPSLongitude"],named["GPSLongitudeRef"])
    except Exception:
        return None, None

def reverse_geocode(lat, lon):
    if lat is None or lon is None:
        return {}
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format":"jsonv2","lat":lat,"lon":lon,"addressdetails":1},
            headers={"User-Agent":"CivicPulseAcademicPrototype/1.0"},
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        a = data.get("address",{})
        return {
            "address": data.get("display_name",""),
            "city": a.get("city") or a.get("town") or a.get("village") or a.get("suburb") or "",
            "district": a.get("state_district") or a.get("county") or "",
            "state": a.get("state") or "",
            "pincode": a.get("postcode") or ""
        }
    except Exception:
        return {}

def analyze_photo(data, mime):
    key = os.getenv("GEMINI_API_KEY","").strip()
    if not key:
        return {"available":False,"message":"AI photo analysis is ready. Add GEMINI_API_KEY in .env to switch it on."}
    model = os.getenv("GEMINI_VISION_MODEL","gemini-2.5-flash-lite")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = """Analyze this image as an Indian civic complaint. Return ONLY JSON:
{"category":"Water|Road|Waste|Street Light|Drainage|Other","severity":1,"summary":"short visible problem","confidence":0.0}
Do not guess exact location from appearance."""
    payload = {
        "contents":[{"parts":[
            {"inline_data":{"mime_type":mime,"data":base64.b64encode(data).decode()}},
            {"text":prompt}
        ]}],
        "generationConfig":{"responseMimeType":"application/json"}
    }
    try:
        r = requests.post(url, headers={"Content-Type":"application/json","x-goog-api-key":key}, json=payload, timeout=30)
        r.raise_for_status()
        out = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        out["available"] = True
        return out
    except Exception as e:
        return {"available":False,"message":f"AI photo analysis failed: {e}"}
