# FPX Timetracker (Windows)

Internes Windows-Tool der Fourplex-Agentur für PROAD-Zeiterfassung direkt aus dem System-Tray.
Offene Todos sehen, Timer starten, Zeiten am Tagesende gebündelt nach PROAD buchen — ohne den Browser zu öffnen.

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6)

---

## Für Nutzer (Projektmanager)

### Installation

1. Neuestes [Release](https://github.com/Radlerdanny/FPXTimetrackerWin/releases/latest) herunterladen: `FPXTimetracker-Setup-x.y.z.exe`
2. Installer doppelklicken
   - Windows SmartScreen → „Weitere Informationen" → „Trotzdem ausführen"
3. Haken bei „Desktop-Verknüpfung" lassen, optional „Automatisch mit Windows starten"
4. Nach der Installation startet die App automatisch. Das FPX-Icon erscheint in der Taskleiste unten rechts (ggf. hinter dem `^`-Pfeil).
5. Beim ersten Start:
   - **PROAD API-Key** eintragen (PROAD → Benutzer → PROAD API → Key kopieren)
   - Eigenen Namen aus der PM-Liste auswählen

### Bedienung

| Aktion | Wie |
|---|---|
| Popover öffnen/schließen | Linksklick auf Tray-Icon |
| Großes Fenster | Rechtsklick auf Tray-Icon → „Großes Fenster" |
| Timer starten/stoppen | ▶-Button neben Todo |
| Todo als erledigt/wartend markieren | „Erledigt" / „Wartet" Button |
| Beschreibung hinzufügen | ✎-Stift neben Todo-Namen |
| Stunden manuell tracken | „Tracken" Button |
| Schnell-Todo anlegen | Eingabe oben: `PROJEKTNR LEISTUNG STUNDEN` (z.B. `FPX-422 GRA 0.5`) |
| Tag abschließen | Grüner Button unten |

### Datenordner

Alle Daten (API-Key, Sessions, Einstellungen):
```
%APPDATA%\FPXTimetracker
```

### Updates

Die App prüft beim Start automatisch auf neue Versionen und fragt, ob der neue Installer heruntergeladen werden soll. Bestehende Daten bleiben erhalten.

