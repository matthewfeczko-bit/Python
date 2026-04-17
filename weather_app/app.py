import os
from collections import defaultdict
from datetime import datetime, timezone

import requests
from flask import Flask, render_template, request

app = Flask(__name__)

API_KEY = os.environ.get("OWM_API_KEY", "8073047465fed3c594412825a8870765")
BASE_URL     = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def c_to_f(c):
    return round(c * 9 / 5 + 32)


def get_alerts(w):
    alerts = []
    cid = w["condition_id"]
    if cid == 781:
        alerts.append({"level": "danger", "text": "Tornado warning active"})
    elif cid == 771:
        alerts.append({"level": "danger", "text": "Squalls warning active"})
    elif 200 <= cid < 300:
        alerts.append({"level": "warning", "text": "Thunderstorm in the area"})
    elif cid in (502, 503, 504):
        alerts.append({"level": "warning", "text": "Heavy rain warning"})
    elif cid in (602, 622):
        alerts.append({"level": "warning", "text": "Heavy snow warning"})
    if w["temp_c"] >= 38:
        alerts.append({"level": "danger", "text": f"Extreme heat: {w['temp_c']}°C / {w['temp_f']}°F"})
    elif w["temp_c"] >= 32:
        alerts.append({"level": "warning", "text": f"Heat advisory: {w['temp_c']}°C / {w['temp_f']}°F"})
    if w["temp_c"] <= -20:
        alerts.append({"level": "danger", "text": f"Extreme cold: {w['temp_c']}°C / {w['temp_f']}°F"})
    elif w["temp_c"] <= -10:
        alerts.append({"level": "warning", "text": f"Cold advisory: {w['temp_c']}°C / {w['temp_f']}°F"})
    if w["wind_kph"] >= 90:
        alerts.append({"level": "danger", "text": f"Dangerous winds: {w['wind_kph']} km/h"})
    elif w["wind_kph"] >= 60:
        alerts.append({"level": "warning", "text": f"High wind advisory: {w['wind_kph']} km/h"})
    return alerts


def get_weather(city):
    params = {"q": city, "appid": API_KEY, "units": "metric"}
    resp = requests.get(BASE_URL, params=params, timeout=5)
    if resp.status_code == 404:
        return None, "City not found."
    if resp.status_code == 401:
        return None, "Invalid API key — it may still be activating (up to 2 hrs)."
    if not resp.ok:
        return None, "Weather service unavailable."
    d = resp.json()
    w = {
        "city":         d["name"],
        "country":      d["sys"]["country"],
        "temp_c":       round(d["main"]["temp"]),
        "temp_f":       c_to_f(d["main"]["temp"]),
        "feels_c":      round(d["main"]["feels_like"]),
        "feels_f":      c_to_f(d["main"]["feels_like"]),
        "description":  d["weather"][0]["description"].title(),
        "icon":         d["weather"][0]["icon"],
        "humidity":     d["main"]["humidity"],
        "wind_kph":     round(d["wind"]["speed"] * 3.6),
        "wind_mph":     round(d["wind"]["speed"] * 2.237),
        "condition_id": d["weather"][0]["id"],
    }
    w["alerts"] = get_alerts(w)
    return w, None


def get_forecast(city):
    params = {"q": city, "appid": API_KEY, "units": "metric", "cnt": 40}
    resp = requests.get(FORECAST_URL, params=params, timeout=5)
    if not resp.ok:
        return [], []
    entries = resp.json()["list"]

    today = datetime.now(timezone.utc).date()

    # Hourly: next 24 hours (8 × 3-hour slots) regardless of UTC date boundary
    hourly = []
    for e in entries[:8]:
        dt = datetime.fromtimestamp(e["dt"], tz=timezone.utc)
        hourly.append({
            "time":   dt.strftime("%-I %p"),
            "temp_c": round(e["main"]["temp"]),
            "temp_f": c_to_f(e["main"]["temp"]),
            "icon":   e["weather"][0]["icon"].strip(),
            "desc":   e["weather"][0]["description"].title(),
        })

    # Daily: group remaining entries by date, pick the one closest to noon
    by_day = defaultdict(list)
    for e in entries[8:]:
        dt = datetime.fromtimestamp(e["dt"], tz=timezone.utc)
        if dt.date() != today:
            by_day[dt.date()].append((dt, e))

    daily = []
    for date in sorted(by_day)[:5]:
        slots = by_day[date]
        # pick slot closest to noon
        best = min(slots, key=lambda x: abs(x[0].hour - 12))
        dt, e = best
        daily.append({
            "day":       dt.strftime("%A"),
            "date":      dt.strftime("%b %-d"),
            "high_c":    round(max(s["main"]["temp_max"] for _, s in slots)),
            "high_f":    c_to_f(max(s["main"]["temp_max"] for _, s in slots)),
            "low_c":     round(min(s["main"]["temp_min"] for _, s in slots)),
            "low_f":     c_to_f(min(s["main"]["temp_min"] for _, s in slots)),
            "icon":      e["weather"][0]["icon"],
            "desc":      e["weather"][0]["description"].title(),
        })

    return hourly, daily


@app.route("/", methods=["GET", "POST"])
def index():
    weather, error = None, None
    hourly, daily = [], []
    city = ""
    if request.method == "POST":
        city = request.form.get("city", "").strip()
        if city:
            weather, error = get_weather(city)
            if weather:
                hourly, daily = get_forecast(city)
    return render_template("index.html",
                           weather=weather, error=error,
                           city=city, hourly=hourly, daily=daily)


if __name__ == "__main__":
    app.run(debug=True)
