# OSL-Coaching

Coaching-Dashboard für Lauf- und Triathlon-Athleten auf Basis von [intervals.icu](https://intervals.icu).

- **App:** https://louisos-afk.github.io/osl-coaching/ (beim ersten Öffnen den API-Key des Coach-Accounts eingeben; er bleibt nur im jeweiligen Browser)
- **Wochenfreigabe:** `.github/workflows/wochenfreigabe.yml` läuft jeden Sonntag und sorgt dafür, dass Athleten geplante Workouts nur für die nächsten 2 Wochen sehen. Braucht das Repository-Secret `INTERVALS_API_KEY`. Manuell starten: Actions → Wochenfreigabe → Run workflow.

## Athleten-App

https://louisos-afk.github.io/osl-coaching/athlete.html: Plan der nächsten 2 Wochen mit allen Workout-Details in den eigenen Paces, Verlauf mit Plan gegen Ist, Feedback (RPE, Gefühl, Notiz), Nachrichten an den Coach, Zonen und Prognosen. Anmeldung mit dem eigenen intervals.icu-API-Key des Athleten.

`athlete.html` wird gebaut: `cd tools && npm install && cd .. && node tools/build-athlete.js` (übernimmt die gemeinsamen Funktionen aus `index.html`, Quelle: `tools/athlete.src.html`).

## Als App aufs Handy

iPhone: Seite in Safari öffnen, Teilen, „Zum Home-Bildschirm“. Android: Chrome-Menü, „App installieren“.

## Daten

- Workout-Bibliothek: Ordner „Coaching-App“ im Coach-Account
- Einstellungen und Plan-Vorlagen: Ordner „OSL-Coaching Daten“ im Coach-Account (nicht löschen)

## Dateien

- `index.html`: die komplette App (eine Datei, keine Abhängigkeiten)
- `scripts/release.py`: Freigabe-Skript (Python-Standardbibliothek)
- `manifest.webmanifest`, `sw.js`, `icons/`: Web-App für den Home-Bildschirm
