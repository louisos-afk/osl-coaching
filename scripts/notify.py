#!/usr/bin/env python3
"""Push-Benachrichtigungen fuer OSL-Coaching. Laeuft alle 5 Minuten per GitHub Actions.

Liest mit dem Coach-Key die Daten aller Athleten, vergleicht mit dem zuletzt gemerkten Stand
(Eintrag "_push_state" im Ordner "OSL-Coaching Daten" der Coach-Bibliothek) und schickt Web-Push
an die Geraete, die in den Apps Benachrichtigungen aktiviert haben (Eintrag "_push" im selben
Ordner des jeweiligen Kontos).

Athlet bekommt: Nachricht vom Coach, neues/geaendertes Workout, Plan-Freigabe am Sonntagabend,
  Morgen-Erinnerung, Feedback-Erinnerung nach dem Lauf.
Coach bekommt: Nachricht vom Athleten, Lauf absolviert, Feedback abgegeben, Workout verpasst.

Aufruf: INTERVALS_API_KEY=... VAPID_PRIVATE_KEY=... python3 scripts/notify.py
Test ohne Senden: DRY_RUN=1
"""
import base64, datetime as dt, hashlib, json, os, sys, urllib.error, urllib.request
from zoneinfo import ZoneInfo

KEY = os.environ["INTERVALS_API_KEY"]
VAPID = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
DRY = os.environ.get("DRY_RUN") == "1"
BASE = os.environ.get("INTERVALS_BASE", "https://intervals.icu/api/v1/")
APP = "https://louisos-afk.github.io/osl-coaching/"
FOLDER = "OSL-Coaching Daten"
TZ = ZoneInfo("Europe/Berlin")
NOW = dt.datetime.fromisoformat(os.environ["FAKE_NOW"]).replace(tzinfo=TZ) if os.environ.get("FAKE_NOW") else dt.datetime.now(TZ)
TODAY = NOW.date()
AUTH = "Basic " + base64.b64encode(f"API_KEY:{KEY}".encode()).decode()
WD = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
FEEL = {1: "💪 Stark", 2: "🙂 Gut", 3: "😐 Normal", 4: "😕 Schwach", 5: "😫 Sehr schwach"}

if not VAPID and not DRY:
    print("VAPID_PRIVATE_KEY fehlt, nichts zu tun.")
    sys.exit(0)


def api(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", AUTH)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "osl-coaching-notify/1.0")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def jload(t):
    try:
        return json.loads(t or "{}") or {}
    except ValueError:
        return {}


def folder_of(aid, create=False):
    f = next((x for x in api("GET", f"athlete/{aid}/folders") or []
              if x.get("type") == "FOLDER" and x.get("name") == FOLDER), None)
    if not f and create:
        f = api("POST", f"athlete/{aid}/folders", {"type": "FOLDER", "name": FOLDER})
    return f


def item_of(f, name):
    return next((x for x in (f or {}).get("children") or [] if x.get("name") == name), None)


def save_item(aid, f, it, name, data):
    body = {"name": name, "type": "Other", "description": json.dumps(data, separators=(",", ":"))}
    if it:
        api("PUT", f"athlete/{aid}/workouts/{it['id']}", body)
    else:
        api("POST", f"athlete/{aid}/workouts", dict(body, folder_id=f["id"]))


# ---------- Formatierung wie in den Apps ----------
def km(m):
    return f"{m / 1000:.2f}".replace(".", ",")


def dur(s):
    s = int(round(s or 0))
    h, m, x = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{x:02d} h" if h else f"{m}:{x:02d} min"


def pace(dist, sec):
    if not dist or not sec:
        return ""
    p = int(round(sec / dist * 1000))
    return f"{p // 60}:{p % 60:02d}/km"


def day(d):
    return f"{WD[d.weekday()]} {d.day}.{d.month}."


def ldate(x):
    return dt.date.fromisoformat((x or "")[:10])


def act_line(a):
    run = (a.get("type") or "").endswith("Run")
    parts = [km(a["distance"]) + " km" if a.get("distance") else "", dur(a.get("moving_time")) if a.get("moving_time") else "",
             pace(a.get("distance"), a.get("moving_time")) if run else ""]
    return " · ".join(p for p in parts if p)


def ev_line(e):
    parts = [f"{round(e['moving_time'] / 60)} min" if e.get("moving_time") else "",
             km(e["distance"]) + " km" if e.get("distance") else "",
             f"TSS {round(e['icu_training_load'])}" if e.get("icu_training_load") else ""]
    return " · ".join(p for p in parts if p)


def real_activity(a):
    if (a.get("moving_time") or 0) < 120:
        return False
    return not ((a.get("type") or "").endswith("Run") and (a.get("distance") or 0) < 300)


def sport(t):
    t = t or ""
    return "Run" if "Run" in t else "Ride" if "Ride" in t else "Swim" if "Swim" in t else t


def fb_sig(a):
    return f"{a.get('icu_rpe') or ''}|{a.get('feel') or ''}"


def ev_hash(e):
    raw = "|".join(str(e.get(k) or "") for k in ("name", "start_date_local", "description", "moving_time", "distance"))
    return hashlib.md5(raw.encode()).hexdigest()[:12]


# ---------- Daten laden ----------
try:
    me = api("GET", "athlete/0")
except urllib.error.HTTPError as ex:
    # Kein Fehler-Lauf alle 5 Minuten (GitHub wuerde jedes Mal eine Mail schicken), nur Warnung im Log
    print(f"::warning::intervals.icu antwortet {ex.code}. INTERVALS_API_KEY im GitHub-Secret pruefen.")
    sys.exit(0)
COACH = str(me["id"])
athletes = {str(a["athlete_id"]): (a.get("athlete_name") or "Athlet")
            for a in api("GET", "athlete/0/athlete-summary.json") or [] if str(a.get("athlete_id")) != COACH}

coach_folder = folder_of(COACH, create=True)
state_item = item_of(coach_folder, "_push_state")
state = jload(state_item and state_item.get("description"))
state_before = json.dumps(state, sort_keys=True)
outbox = []  # (Ziel-Konto, Titel, Text, URL, Tag)


def notify(target, title, body, url, tag=None):
    outbox.append((target, title, body, url, tag))


day_time = 7 <= NOW.hour < 22  # nachts keine Erinnerungen, Nachrichten immer

for aid, name in athletes.items():
    first = name.split()[0]
    s = state.setdefault(aid, {})
    init = not s.get("ready")  # erster Lauf: nur Stand merken, nichts senden
    sent = s.setdefault("sent", {})
    seen_acts, seen_msgs = s.setdefault("acts", {}), set(s.get("msgs", []))
    fb_asked = set(s.get("fbask", []))
    ath_url, coach_url = APP + "athlete.html", APP + "index.html"

    acts = [a for a in api("GET", f"athlete/{aid}/activities?oldest={TODAY - dt.timedelta(days=10)}&newest={TODAY}") or [] if real_activity(a)]
    evs = api("GET", f"athlete/{aid}/events?oldest={TODAY - dt.timedelta(days=2)}&newest={TODAY + dt.timedelta(days=21)}") or []

    # Absolvierte Laeufe und Feedback -> Coach
    for a in acts:
        k, sig = str(a["id"]), fb_sig(a)
        if k not in seen_acts:
            if not init:
                notify(COACH, f"{first} hat trainiert ✓", f"{a.get('name') or a.get('type')}: {act_line(a)}", coach_url, f"act-{k}")
        elif seen_acts[k] != sig and sig != "|" and not init:
            fb = " · ".join(x for x in [f"RPE {a['icu_rpe']}" if a.get("icu_rpe") else "", FEEL.get(a.get("feel"), "")] if x)
            notify(COACH, f"Feedback von {first}", f"{a.get('name') or a.get('type')}: {fb}", coach_url, f"fb-{k}")
        seen_acts[k] = sig
    s["acts"] = {k: v for k, v in seen_acts.items() if k in {str(a["id"]) for a in acts}}

    # Nachrichten (beide Richtungen)
    for a in acts:
        try:
            msgs = api("GET", f"activity/{a['id']}/messages") or []
        except urllib.error.HTTPError:
            continue
        for m in msgs:
            mk = str(m.get("id"))
            if mk in seen_msgs:
                continue
            seen_msgs.add(mk)
            if init:
                continue
            text = (m.get("content") or "").strip()
            text = text if len(text) <= 140 else text[:137] + "…"
            if str(m.get("athlete_id")) == aid:
                notify(COACH, f"Nachricht von {first}", text, coach_url, f"msg-{a['id']}")
            else:
                notify(aid, "Nachricht vom Coach", text, f"{ath_url}#act={a['id']}", f"msg-{a['id']}")
    s["msgs"] = sorted(seen_msgs)[-400:]

    # Neue oder geaenderte Workouts -> Athlet (Freigabe am Sonntag zaehlt nicht einzeln)
    workouts = [e for e in evs if e.get("category") == "WORKOUT"]
    old_evs, new_evs, released = s.get("evs", {}), {}, []
    for e in workouts:
        k, h, hidden = str(e["id"]), ev_hash(e), bool(e.get("hide_from_athlete"))
        new_evs[k] = [h, hidden]
        d = ldate(e["start_date_local"])
        if init or hidden or d < TODAY:
            continue
        prev = old_evs.get(k)
        if prev and prev[1] and TODAY.weekday() == 6:  # am Sonntag freigegeben: eine Sammelnachricht
            released.append(e)
            continue
        if prev is None or prev[1]:
            notify(aid, "Neues Workout", " · ".join(x for x in [f"{day(d)}: {e.get('name')}", ev_line(e)] if x), ath_url, f"ev-{k}")
        elif prev[0] != h:
            notify(aid, "Workout geändert", " · ".join(x for x in [f"{day(d)}: {e.get('name')}", ev_line(e)] if x), ath_url, f"ev-{k}")
    s["evs"] = new_evs
    if released and not init and sent.get("release") != str(TODAY):
        sent["release"] = str(TODAY)
        n = len(released)
        notify(aid, "Dein Plan für die neue Woche ist da 📅", f"{n} Workout{'s' if n != 1 else ''} ab Montag. Schau rein!", ath_url, "release")

    visible_on = lambda d: [e for e in workouts if not e.get("hide_from_athlete") and ldate(e["start_date_local"]) == d]
    acts_on = lambda d: [a for a in acts if ldate(a["start_date_local"]) == d]

    if not init and day_time:
        # Morgens: heutiges Workout
        if sent.get("morning") != str(TODAY):
            sent["morning"] = str(TODAY)
            today_w = visible_on(TODAY)
            if today_w and not acts_on(TODAY):
                e = today_w[0]
                more = f" (+{len(today_w) - 1})" if len(today_w) > 1 else ""
                notify(aid, f"Heute: {e.get('name')}{more}", ev_line(e) or "Viel Spaß beim Training!", ath_url, "morning")
        # Morgens: verpasste Workouts von gestern -> Coach
        if sent.get("missed") != str(TODAY):
            sent["missed"] = str(TODAY)
            y = TODAY - dt.timedelta(days=1)
            done = {sport(a.get("type")) for a in acts_on(y)}
            missed = [e for e in visible_on(y) if sport(e.get("type")) not in done]
            if missed:
                notify(COACH, f"{first}: Workout verpasst", f"Gestern: {', '.join(e.get('name') or '' for e in missed)}", coach_url, f"missed-{aid}")
        # Feedback-Erinnerung 2 h nach dem Lauf, bis 2 Tage danach
        for a in acts:
            k = str(a["id"])
            if k in fb_asked or a.get("icu_rpe") or a.get("feel"):
                continue
            start = dt.datetime.fromisoformat(a["start_date_local"][:19]).replace(tzinfo=TZ)
            end = start + dt.timedelta(seconds=a.get("elapsed_time") or a.get("moving_time") or 0)
            if end + dt.timedelta(hours=2) <= NOW <= end + dt.timedelta(days=2):
                fb_asked.add(k)
                notify(aid, "Wie war's? 🏃", f"{a.get('name') or a.get('type')} · Gib kurz Feedback (Anstrengung und Gefühl).", f"{ath_url}#act={k}", f"fbask-{k}")
    elif init:
        sent.update(morning=str(TODAY), missed=str(TODAY))
        if TODAY.weekday() == 6:
            sent["release"] = str(TODAY)
        fb_asked |= {str(a["id"]) for a in acts}
    s["fbask"] = sorted(fb_asked & {str(a["id"]) for a in acts})
    s["ready"] = True

# ---------- Senden ----------
subs_cache = {}


def subs_for(aid):
    if aid not in subs_cache:
        f = coach_folder if aid == COACH else folder_of(aid)
        it = item_of(f, "_push")
        subs_cache[aid] = [f, it, jload(it and it.get("description")), False]
    return subs_cache[aid]


if outbox and not DRY:
    from pywebpush import WebPushException, webpush

sent_count = 0
for target, title, body, url, tag in outbox:
    entry = subs_for(target)
    subs = entry[2].get("subs") or []
    # Das Repo ist oeffentlich, die Action-Logs auch: keine Namen oder Inhalte ausgeben (ausser im Testlauf)
    who = "Coach" if target == COACH else (athletes.get(target, target) if DRY else "Athlet")
    if DRY:
        print(f"[DRY] an {who} ({len(subs)} Geräte): {title} | {body} | {url}")
        continue
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    for sub in list(subs):
        try:
            webpush(subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]}, data=payload,
                    vapid_private_key=VAPID, vapid_claims={"sub": "https://louisos-afk.github.io"}, ttl=86400, timeout=20)
            sent_count += 1
        except WebPushException as ex:
            code = getattr(ex.response, "status_code", None)
            if code in (404, 410):  # Geraet abgemeldet
                subs.remove(sub)
                entry[3] = True
            print(f"Push an {who} fehlgeschlagen ({code})")
        except Exception as ex:  # ein kaputtes Geraet darf den Lauf nicht stoppen
            print(f"Push an {who} fehlgeschlagen: {type(ex).__name__}")

for aid, (f, it, data, changed) in subs_cache.items():
    if changed and f and not DRY:
        save_item(aid, f, it, "_push", data)

if json.dumps(state, sort_keys=True) != state_before and not DRY:
    save_item(COACH, coach_folder, state_item, "_push_state", state)
print(f"{NOW:%Y-%m-%d %H:%M}: {len(outbox)} Ereignisse, {sent_count} Pushes gesendet")
