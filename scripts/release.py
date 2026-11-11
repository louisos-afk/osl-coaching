#!/usr/bin/env python3
"""Wochenfreigabe: Athleten sehen geplante Workouts immer nur fuer die laufende Woche.

Regel (Zeit Europe/Berlin): Montag bis Samstag ist alles bis einschliesslich zum kommenden
Sonntag sichtbar. Sonntag ab 18 Uhr wird die neue Woche (bis Sonntag in 7 Tagen) freigegeben.
Alles danach wird mit hide_from_athlete versteckt.
Aufruf: INTERVALS_API_KEY=... python3 release.py
"""
import base64, datetime as dt, json, os, urllib.request

KEY = os.environ["INTERVALS_API_KEY"]
AUTH = "Basic " + base64.b64encode(f"API_KEY:{KEY}".encode()).decode()


def api(method, path, body=None):
    req = urllib.request.Request("https://intervals.icu/api/v1/" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", AUTH)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "osl-coaching-release/1.0")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


from zoneinfo import ZoneInfo
now = dt.datetime.now(ZoneInfo("Europe/Berlin"))
today = now.date()
if today.weekday() == 6:  # Sonntag
    horizon = today + dt.timedelta(days=7) if now.hour >= 18 else today
else:
    horizon = today + dt.timedelta(days=6 - today.weekday())
me = api("GET", "athlete/0")
athletes = {a["athlete_id"]: a.get("athlete_name") for a in api("GET", "athlete/0/athlete-summary.json") if a.get("athlete_id") != me["id"]}
print(f"Heute {today}, sichtbar bis {horizon}")
for aid, name in athletes.items():
    events = api("GET", f"athlete/{aid}/events?oldest={today}&newest={today + dt.timedelta(days=400)}")
    shown = hidden = 0
    for e in events:
        if e.get("category") != "WORKOUT":
            continue
        want = dt.date.fromisoformat(e["start_date_local"][:10]) > horizon
        if bool(e.get("hide_from_athlete")) != want:
            api("PUT", f"athlete/{aid}/events/{e['id']}", {"hide_from_athlete": want})
            hidden += want
            shown += not want
    print(f"{name} ({aid}): {shown} freigegeben, {hidden} versteckt")
