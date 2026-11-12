#!/usr/bin/env python3
"""Monatsbericht fuer OSL-Coaching. Laeuft am Monatsersten per GitHub Actions.

Sammelt fuer jeden Athleten die Daten des Vormonats (und der drei Monate davor als Vergleich),
laesst Claude daraus nicht offensichtliche Erkenntnisse schreiben und speichert den Bericht als
Notiz am Monatsersten im intervals.icu-Kalender (external_id "osl-report:JJJJ-MM").
Die Apps zeigen ihn unter Analyse an; Athlet und Coach bekommen eine Benachrichtigung.

Aufruf: INTERVALS_API_KEY=... ANTHROPIC_API_KEY=... python3 scripts/monthly_report.py [JJJJ-MM]
Test ohne Speichern/Senden: DRY_RUN=1 (gibt den Bericht aus)
"""
import base64, datetime as dt, json, os, statistics as stt, sys, urllib.error, urllib.request

KEY = os.environ["INTERVALS_API_KEY"]
CLAUDE_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
VAPID = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
MODEL = os.environ.get("REPORT_MODEL", "claude-sonnet-5-5")
DRY = os.environ.get("DRY_RUN") == "1"
BASE = os.environ.get("INTERVALS_BASE", "https://intervals.icu/api/v1/")
CLAUDE_URL = os.environ.get("ANTHROPIC_URL", "https://api.anthropic.com/v1/messages")
ONLY = os.environ.get("ONLY_ATHLETE", "").strip()
APP = "https://louisos-afk.github.io/osl-coaching/"
FOLDER = "OSL-Coaching Daten"
AUTH = "Basic " + base64.b64encode(f"API_KEY:{KEY}".encode()).decode()
MON = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]

if not CLAUDE_KEY and not DRY:
    print("::warning::ANTHROPIC_API_KEY fehlt, kein Monatsbericht.")
    sys.exit(0)

# Berichtsmonat: Argument JJJJ-MM, sonst Vormonat
today = dt.date.today()
arg = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REPORT_MONTH", "")).strip()
if arg:
    y, m = map(int, arg.split("-"))
else:
    first = today.replace(day=1) - dt.timedelta(days=1)
    y, m = first.year, first.month
M0 = dt.date(y, m, 1)
M1 = (M0 + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
NEXT = M1 + dt.timedelta(days=1)
HIST0 = (M0 - dt.timedelta(days=92)).replace(day=1)
LABEL = f"{MON[m - 1]} {y}"


def api(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", AUTH)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "osl-coaching-report/1.0")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def r1(v, n=1):
    return None if v is None else round(v, n)


def pace(dist, sec):
    if not dist or not sec:
        return None
    p = int(round(sec / dist * 1000))
    return f"{p // 60}:{p % 60:02d}"


def run_row(a):
    """Kompakte Zeile je Einheit fuer Claude (nur Zahlen, keine Freitexte ausser Name)."""
    w = a.get("icu_average_watts")
    return {
        "datum": a["start_date_local"][:10], "wt": dt.date.fromisoformat(a["start_date_local"][:10]).strftime("%a"),
        "typ": a.get("type"), "name": (a.get("name") or "")[:60],
        "km": r1((a.get("distance") or 0) / 1000, 2), "min": r1((a.get("moving_time") or 0) / 60),
        "pace": pace(a.get("distance"), a.get("moving_time")) if "Run" in (a.get("type") or "") else None,
        "hf": a.get("average_heartrate"), "hf_max": a.get("max_heartrate"), "watt": w, "np": a.get("icu_weighted_avg_watts"),
        "load": a.get("icu_training_load"), "intensitaet": r1(a.get("icu_intensity")), "hoehenm": a.get("total_elevation_gain"),
        "rpe": a.get("icu_rpe"), "gefuehl": a.get("feel"), "decoupling": r1(a.get("decoupling")), "effizienz": r1(a.get("icu_efficiency_factor"), 3),
        "kadenz": r1((a.get("average_cadence") or 0) * 2) or None, "gct_ms": r1(a.get("average_stance_time")),
        "lss": r1(a.get("average_leg_spring_stiffness")), "vert_verh": r1(a.get("average_vertical_ratio")),
        "schritt_m": r1((a.get("average_step_length") or 0) / 1000, 2) or None,
        "geplant_gepaart": bool(a.get("paired_event_id")),
    }


def summary(acts):
    runs = [a for a in acts if "Run" in (a.get("type") or "")]
    tot = lambda k: sum(a.get(k) or 0 for a in runs)
    return {"laeufe": len(runs), "km": r1(tot("distance") / 1000), "stunden": r1(tot("moving_time") / 3600),
            "load": r1(sum(a.get("icu_training_load") or 0 for a in acts)), "andere_einheiten": len(acts) - len(runs)}


SYSTEM = (
    "Du bist ein erfahrener Lauftrainer und Datenanalyst und schreibst Monatsberichte für Athleten von OSL-Coaching. "
    "Du schreibst auf Deutsch, direkt und konkret, in der Du-Form an den Athleten. Keine Gedankenstriche, keine Emojis."
)
TASK = """Schreibe den Monatsbericht für {name} für {label}.

Wichtig:
- Nicht das Offensichtliche wiederholen (Kilometer, Anzahl Läufe, "du warst fleißig"). Die Eckdaten stehen nur in einer einzigen kurzen Zeile.
- Finde 3 bis 5 Erkenntnisse, die man beim Durchscrollen der App nicht sofort sieht. Zum Beispiel: Zusammenhänge zwischen Schlaf, Ruhepuls oder HRV und der Qualität harter Einheiten; Pace bei gleicher Herzfrequenz im Vergleich zu den Vormonaten; Decoupling bei langen Läufen; wie sich Kadenz, Bodenkontaktzeit oder Leg Spring Stiffness je nach Tempo verhalten; Verteilung der Belastung über die Wochentage; welche geplanten Einheiten ausgelassen oder überzogen wurden; RPE im Verhältnis zur gemessenen Intensität.
- Jede Erkenntnis mit konkreten Zahlen und Daten belegen. Nur behaupten, was die Daten zeigen. Wo Daten fehlen, die Erkenntnis weglassen.
- Danach 2 bis 3 konkrete Hinweise für den nächsten Monat, abgeleitet aus den Erkenntnissen.
- Höchstens 350 Wörter.

Format genau so (Markdown):
**Eckdaten:** eine Zeile
## Erkenntnisse
- **Kurzer Titel:** 1 bis 3 Sätze
## Für {next_label}
- Hinweis

Daten (JSON):
{data}"""


def claude(prompt):
    body = {"model": MODEL, "max_tokens": 1500, "system": SYSTEM, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(CLAUDE_URL, data=json.dumps(body).encode(), method="POST")
    req.add_header("x-api-key", CLAUDE_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("content-type", "application/json")
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.loads(r.read())
    return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text").strip()


def push(aid, title, body, url):
    if DRY or not VAPID:
        return 0
    from pywebpush import WebPushException, webpush
    folders = api("GET", f"athlete/{aid}/folders") or []
    f = next((x for x in folders if x.get("type") == "FOLDER" and x.get("name") == FOLDER), None)
    it = next((x for x in (f or {}).get("children") or [] if x.get("name") == "_push"), None)
    try:
        subs = json.loads(it["description"]).get("subs", []) if it else []
    except ValueError:
        subs = []
    n = 0
    for s in subs:
        try:
            webpush(subscription_info={"endpoint": s["endpoint"], "keys": s["keys"]},
                    data=json.dumps({"title": title, "body": body, "url": url, "tag": "report"}),
                    vapid_private_key=VAPID, vapid_claims={"sub": "https://louisos-afk.github.io"}, ttl=86400, timeout=20)
            n += 1
        except (WebPushException, Exception):
            pass
    return n


me = api("GET", "athlete/0")
COACH = str(me["id"])
athletes = {str(a["athlete_id"]): (a.get("athlete_name") or "Athlet")
            for a in api("GET", "athlete/0/athlete-summary.json") or [] if str(a.get("athlete_id")) != COACH}
if ONLY:
    athletes = {k: v for k, v in athletes.items() if k == ONLY or k.endswith(ONLY)}

done = 0
for aid, name in athletes.items():
    acts = [a for a in api("GET", f"athlete/{aid}/activities?oldest={HIST0}&newest={M1}") or [] if (a.get("moving_time") or 0) >= 300]
    month = [a for a in acts if str(M0) <= a["start_date_local"][:10] <= str(M1)]
    if not month:
        print("Ein Athlet ohne Einheiten im Monat, übersprungen")
        continue
    prev = [a for a in acts if a["start_date_local"][:10] < str(M0)]
    well = api("GET", f"athlete/{aid}/wellness?oldest={HIST0}&newest={M1}") or []
    evs = api("GET", f"athlete/{aid}/events?oldest={M0}&newest={NEXT + dt.timedelta(days=120)}") or []
    sett = next((x for x in api("GET", f"athlete/{aid}/sport-settings") or [] if "Run" in (x.get("types") or [])), {})
    planned = [e for e in evs if e.get("category") == "WORKOUT" and e["start_date_local"][:10] <= str(M1)]
    paired = {a.get("paired_event_id") for a in month if a.get("paired_event_id")}
    wl = [w for w in well if w.get("id", "") >= str(M0)]
    wl_prev = [w for w in well if w.get("id", "") < str(M0)]
    mean = lambda rows, k: r1(stt.mean([r[k] for r in rows if r.get(k)]) if any(r.get(k) for r in rows) else None)
    data = {
        "athlet": name.split()[0], "monat": LABEL,
        "schwellen": {"schwellenpace_min_km": pace(1000, 1000 / sett["threshold_pace"]) if sett.get("threshold_pace") else None,
                      "lthr": sett.get("lthr"), "cp_watt": sett.get("ftp"), "max_hf": sett.get("max_hr")},
        "monat_summe": summary(month),
        "vormonate_summe_je_monat": {k: r1(v / 3) for k, v in summary(prev).items()},
        "einheiten": [run_row(a) for a in sorted(month, key=lambda a: a["start_date_local"])],
        "vormonate_laeufe_kompakt": [{k: run_row(a)[k] for k in ("datum", "km", "min", "pace", "hf", "watt", "rpe", "kadenz", "gct_ms", "lss", "decoupling")}
                                     for a in sorted(prev, key=lambda a: a["start_date_local"]) if "Run" in (a.get("type") or "")],
        "wellness_tage": [{"datum": w["id"], "ctl": r1(w.get("ctl")), "atl": r1(w.get("atl")), "ruhepuls": w.get("restingHR"), "hrv": w.get("hrv"),
                           "schlaf_h": r1((w.get("sleepSecs") or 0) / 3600) or None} for w in wl],
        "wellness_vormonate_mittel": {"ruhepuls": mean(wl_prev, "restingHR"), "hrv": mean(wl_prev, "hrv"), "schlaf_h": r1((mean(wl_prev, "sleepSecs") or 0) / 3600) or None},
        "geplant": [{"datum": e["start_date_local"][:10], "name": e.get("name"), "min": r1((e.get("moving_time") or 0) / 60), "km": r1((e.get("distance") or 0) / 1000, 1),
                     "absolviert_gepaart": e.get("id") in paired} for e in planned],
        "kommende_wettkaempfe": [{"datum": e["start_date_local"][:10], "name": e.get("name"), "prio": (e.get("category") or "")[-1:], "km": r1((e.get("distance") or 0) / 1000, 1)}
                                 for e in evs if (e.get("category") or "").startswith("RACE_") and e["start_date_local"][:10] >= str(NEXT)],
    }
    prompt = TASK.format(name=name.split()[0], label=LABEL, next_label=MON[NEXT.month - 1], data=json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    if DRY and not CLAUDE_KEY:
        print(f"[DRY] Prompt für Athlet ({len(prompt)} Zeichen, {len(month)} Einheiten)")
        continue
    try:
        text = claude(prompt)
    except urllib.error.HTTPError as ex:
        print(f"::warning::Claude-API antwortet {ex.code}")
        continue
    if DRY:
        print(f"\n===== {name} {LABEL} =====\n{text}\n")
        continue
    ev = {"category": "NOTE", "start_date_local": f"{NEXT}T00:00:00", "name": f"Monatsbericht {LABEL}",
          "description": text, "external_id": f"osl-report:{y}-{m:02d}", "hide_from_athlete": False}
    api("POST", f"athlete/{aid}/events/bulk?upsert=true", [ev])
    n = push(aid, f"Dein Monatsbericht {MON[m - 1]} ist da", "Was dein Training im letzten Monat gezeigt hat. Schau rein!", APP + "athlete.html#report")
    done += 1
    print(f"Bericht {done} gespeichert, {n} Pushes")

if done:
    push(COACH, "Monatsberichte erstellt", f"{done} Bericht{'e' if done != 1 else ''} für {LABEL}.", APP + "index.html")
print(f"{LABEL}: {done} Berichte")
