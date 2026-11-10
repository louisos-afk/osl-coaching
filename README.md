# OSL-Coaching

Coaching-Dashboard für Lauf- und Triathlon-Athleten auf Basis von [intervals.icu](https://intervals.icu).

- **App:** https://louisos-afk.github.io/osl-coaching/ (beim ersten Öffnen den API-Key des Coach-Accounts eingeben; er bleibt nur im jeweiligen Browser)
- **Wochenfreigabe:** `.github/workflows/wochenfreigabe.yml` läuft jeden Sonntag und sorgt dafür, dass Athleten geplante Workouts nur für die nächsten 2 Wochen sehen. Braucht das Repository-Secret `INTERVALS_API_KEY`. Manuell starten: Actions → Wochenfreigabe → Run workflow.

## Dateien

- `index.html`: die komplette App (eine Datei, keine Abhängigkeiten)
- `scripts/release.py`: Freigabe-Skript (Python-Standardbibliothek)
