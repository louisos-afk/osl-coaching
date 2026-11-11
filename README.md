# OSL-Coaching

Coaching-Dashboard für Lauf- und Triathlon-Athleten auf Basis von [intervals.icu](https://intervals.icu).

- **App:** https://louisos-afk.github.io/osl-coaching/ (beim ersten Öffnen den API-Key des Coach-Accounts eingeben; er bleibt nur im jeweiligen Browser)
- **Wochenfreigabe:** `.github/workflows/wochenfreigabe.yml` läuft jeden Sonntagabend (ab 18 Uhr) und gibt die neue Woche frei. Athleten sehen immer nur die laufende Woche. Braucht das Repository-Secret `INTERVALS_API_KEY`. Manuell starten: Actions → Wochenfreigabe → Run workflow.

## Athleten-App

https://louisos-afk.github.io/osl-coaching/athlete.html: Plan der laufenden Woche mit allen Workout-Details in den eigenen Paces, Verlauf mit Plan gegen Ist, Feedback (RPE, Gefühl, Notiz), Nachrichten an den Coach, Zonen und Prognosen. Anmeldung mit dem eigenen intervals.icu-API-Key des Athleten.

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

## Benachrichtigungen

- In der Athleten-App unter **Profil**, in der Coach-App unter **Einstellungen** auf „Aktivieren“ tippen. Auf dem iPhone geht das nur in der installierten App (iOS 16.4 oder neuer).
- Jedes Gerät legt seine Empfänger-Adresse im eigenen intervals-Konto ab (Ordner „OSL-Coaching Daten“, Eintrag `_push`).
- `scripts/notify.py` läuft alle 5 Minuten über `.github/workflows/benachrichtigungen.yml`, merkt sich den Stand in `_push_state` in der Coach-Bibliothek und schickt:
  - an Athleten: Nachricht vom Coach, neues oder geändertes Workout, Plan-Freigabe am Sonntagabend, Morgen-Erinnerung, Feedback-Erinnerung 2 h nach dem Lauf
  - an den Coach: Nachricht oder Feedback vom Athleten, absolvierter Lauf, verpasstes Workout vom Vortag
- Benötigte Secrets: `INTERVALS_API_KEY` und `VAPID_PRIVATE_KEY`. Der öffentliche Schlüssel steht als `VAPID_PUB` in `index.html`.
