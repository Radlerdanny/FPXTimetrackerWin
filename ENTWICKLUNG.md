# FPX Timetracker (Windows) – Entwickler-Handover

Wissensdatei für den Transfer auf den Windows-Rechner. Nimm das Repo + diese Datei mit, öffne Claude Code dort und du hast den vollen Kontext ohne erneutes Onboarding.

---

## 1. Worum geht's

FPX Timetracker ist das interne Zeiterfassungs-Frontend für die Werbeagentur **Fourplex**. Es spricht direkt die PROAD-REST-API (v5) an und ersetzt das manuelle Tippen in PROAD.

- Quelle: macOS-Version (bereits im Einsatz, Python/tkinter).
- Ziel: identisches UX auf Windows 10/11, Kollegen installieren per Doppelklick.
- Repo: `Radlerdanny/FPXTimetrackerWin` (separate Windows-Variante, Mac-Version bleibt getrennt).

---

## 2. Architektur

Zwei-Prozess-Modell, beides derselbe Python-Code / dieselbe `.exe`:

```
┌──────────────────────┐         ┌──────────────────────────────┐
│  fpx_tray.py         │ spawn → │  fpx_timetracker.py          │
│  (Tray-Icon, pystray)│  IPC  → │  (Popover ODER Großfenster)  │
│  Singleton-Lock      │ ← tick  │  tkinter-UI                  │
│  Auto-Update         │         │                              │
└──────────────────────┘         └──────────────────────────────┘
            │                                  │
            └──────── IPC: JSON-Datei ─────────┘
                %APPDATA%\FPXTimetracker\ipc.json
```

- **Im PyInstaller-Bundle** ist `FPXTimetracker.exe` eine Datei. Tray startet sich selbst mit `--popover` oder `--big` als Subprozess.
- **Im Dev-Modus** startet Tray den Python-Interpreter mit `fpx_timetracker.py [--popover]`.

### DPI-Awareness

Per-Monitor-V2 wird **beim Import von `fpx_common.py`** aktiviert, vor jedem tkinter-Import. Deshalb muss `fpx_common` überall als Erstes importiert werden (ist es). Die globale Konstante `SCALE` und der Helper `s(n)` skalieren alle Pixel-Werte, Fontgrößen werden via `tk scaling`-Call automatisch skaliert.

---

## 3. Dateien

| Datei | Rolle |
|---|---|
| `fpx_common.py` | Plattform-Check, Pfade, Version, DPI-Aware + `s()`, `get_work_area()`, IPC-Helfer |
| `fpx_tray.py` | Tray-Icon, Singleton-Lock (msvcrt), Subprozess-Spawning, Auto-Update |
| `fpx_timetracker.py` | Gesamte UI (Setup-Dialog, Popover, Großfenster), PROAD-Client, Tages-Export |
| `build/make_icons.py` | Erzeugt `assets/app.ico` + `tray.ico` – nutzt User-Icon wenn vorhanden |
| `build/build_exe.py` | PyInstaller-Wrapper; ruft immer erst `make_icons.py` |
| `build/installer.iss` | Inno-Setup-Skript; Desktop-Shortcut + Optional-Autostart |
| `.github/workflows/release.yml` | CI: baut auf Tag `v*` via `windows-latest`, publisht Release |

### Datenablage (auf Windows)

```
%APPDATA%\FPXTimetracker\
├── timetracker_data.json  # Sessions, Descriptions, Pending-Status, Config
├── ipc.json               # Kurzlebige Kommandos Tray ↔ Popover
└── fpx_tray.lock          # Singleton-Lock (msvcrt.locking)
```

IPC-Protokoll (JSON, wird vom Tray/Popover geschrieben und gelesen):

| Key | Beispiele | Zweck |
|---|---|---|
| `cmd` | `show`, `hide`, `reload`, `quit` | Vom Tray an Popover |
| `visible_state` | `shown`, `hidden`, `big_open` | Vom Popover an Tray |
| `timer_txt`, `proj_no` | `"00:12:04"`, `"FPX-422"` | Für Tray-Tooltip |
| `ts` | Unix-Timestamp | Duplicate-Filter |

---

## 4. Dev-Setup Windows

Voraussetzungen:
- **Python 3.12** (64-bit, vom python.org-Installer; bei der Installation „Add to PATH" ankreuzen).
- Git für Windows.

Einmalig:

```powershell
cd C:\Users\<du>\Desktop\FPXTimetracker_WIN   # oder wohin du das Repo clonst
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Starten (Dev, ohne Build):

```powershell
python fpx_tray.py
```

Das zeigt das Tray-Icon unten rechts. Linksklick öffnet das Popover, Rechtsklick hat Menü.

Alleinstehend (ohne Tray, direkt Großfenster):

```powershell
python fpx_timetracker.py
```

---

## 5. Lokaler Build (optional)

Nur nötig, wenn du eine `.exe` zum Testen ohne Release willst. Normal-Fall: via GitHub Actions (siehe unten).

Voraussetzungen zusätzlich:
- **Inno Setup 6** (https://jrsoftware.org/isinfo.php) – Installer-Generator.

```powershell
python build\build_exe.py
# → dist\FPXTimetracker.exe (Standalone-Binary)

# Installer bauen:
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
# → Output\FPXTimetracker-Setup.exe
```

---

## 6. Release via GitHub Actions (der Normalfall)

Die CI läuft auf `windows-latest` und übernimmt Build + Release automatisch.

```powershell
git add -A
git commit -m "v0.8.0: beschreibung"
git tag v0.8.0
git push && git push --tags
```

**Warum baut der Server überhaupt?** – Weil `.github/workflows/release.yml` das steuert:

```yaml
on:
  push:
    tags:
      - 'v*'     # jeder Tag der mit "v" beginnt löst den Build aus
```

Der GitHub-Server hat kein eigenes Wissen – er führt nur aus, was in der `.yml` steht. Das Wissen steckt komplett in unseren Dateien im Repo:

| Datei | Aufgabe |
|---|---|
| `build/build_exe.py` | Ruft PyInstaller auf → erzeugt `FPXTimetracker.exe` |
| `build/installer.iss` | Inno-Setup-Skript → erzeugt `FPXTimetracker-Setup-X.Y.Z.exe` mit Desktop-Icon etc. |
| `.github/workflows/release.yml` | Ruft beide der Reihe nach auf, lädt Ergebnis in den GitHub-Release hoch |

**Ablauf Schritt für Schritt (auf dem Windows-Server von GitHub):**
1. Repo clonen
2. Python 3.12 installieren
3. `pip install -r requirements.txt` (Pillow, pystray, requests, …)
4. Version aus dem Tag lesen (`v0.8.0` → `0.8.0`) und in `fpx_common.py` patchen
5. `make_icons.py` → `assets/app.ico` + `assets/tray.ico`
6. `build_exe.py` (PyInstaller) → `dist/FPXTimetracker.exe`
7. Inno Setup → `dist/FPXTimetracker-Setup-0.8.0.exe`
8. Beide Dateien als Anhänge in den GitHub-Release hochladen

Die `.exe`-Dateien tauchen dann unter **Releases → v0.8.0 → Assets** auf – das ist was Kollegen runterladen.

**Release neu bauen** (nach Änderungen am bestehenden Tag):
```powershell
git push origin :refs/tags/v0.8.0   # alten Tag remote löschen
git tag -f v0.8.0                    # Tag lokal auf neuen Commit verschieben
git push origin v0.8.0               # neu pushen → Actions startet neu
```

Falls Actions rot: Logs auf github.com/Radlerdanny/FPXTimetrackerWin/actions ansehen. Häufige Ursachen:
- Sonderzeichen (z.B. `→`) in `print()` → cp1252-Fehler auf Windows → nur ASCII in Build-Skript-Ausgaben
- Fehlender Hidden-Import in PyInstaller (dann crasht die `.exe` beim Start)

---

## 7. Icon-Handling

Der User legt eine Datei mit einem dieser Namen im Repo-Root ab:
`fpx_icon.png` / `fpx_icon.jpg` / `fpx_icon.ico` (oder `icon.*`, `logo.*`, `app_icon.*`).

`make_icons.py` erkennt sie automatisch, skaliert sie auf alle nötigen Größen und baut daraus `assets/app.ico` (Installer + Fenster) und `assets/tray.ico` (Tray).

Ohne User-Datei gibt's ein Platzhalter-Icon (⟐ „F" auf Accent-Blau).

**Icon austauschen:** Datei ersetzen → `python build\build_exe.py` → neuer Build hat das neue Icon.

---

## 8. Auto-Update-Flow

Beim Start pollt der Tray GitHub (`/releases/latest`) gegen `GITHUB_REPO` in `fpx_common.py`. Wenn Tag > aktuelle Version, zeigt eine MessageBox an. Bei „Ja":
1. Popover schließen, Singleton-Lock freigeben.
2. Installer (`*Setup*.exe` aus den Release-Assets) in `%TEMP%` laden.
3. Installer starten mit `/SILENT /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS` (Inno-Setup-Flags).
4. Alte `.exe` beendet sich, Installer überschreibt, neue `.exe` startet.

---

## 9. Debugging

- **Fehlermeldungen**: Der Tray läuft ohne Konsolen-Fenster (PyInstaller `--windowed`). Im Dev-Modus einfach `python fpx_tray.py` aus dem Terminal starten → prints/excepts sichtbar.
- **IPC inspizieren**: `type %APPDATA%\FPXTimetracker\ipc.json`
- **Daten inspizieren**: `type %APPDATA%\FPXTimetracker\timetracker_data.json`
- **DPI-Edge-Cases**: Windows-Einstellungen → System → Anzeige → Skalierung auf 100/125/150/175 % setzen und App neu starten. Font-Scaling läuft über `tk scaling`; falls Layouts brechen, ist meistens eine Stelle nicht mit `s(...)` gewrappt.
- **Tray-Icon kommt nicht**: Meist läuft schon eine Instanz (`%APPDATA%\FPXTimetracker\fpx_tray.lock`). Task-Manager → `FPXTimetracker.exe` beenden.

---

## 10. Bekannte Punkte / ToDo

- **Code-Signing**: Aktuell unsigniert → Windows SmartScreen warnt beim ersten Start. Fix später mit EV-/OV-Zertifikat.
- **Multi-Monitor-DPI**: Per-Monitor-V2 ist aktiv, aber Popover-Position nimmt derzeit nur den primären Monitor. Wenn du auf einen Nebenmonitor willst, müsste man zusätzlich `MonitorFromPoint` nutzen.
- **Logging-Datei**: Bisher nur prints. Für Remote-Diagnose wäre ein Log in `%APPDATA%\FPXTimetracker\log.txt` sinnvoll.

---

## 11. Änderungen in v0.8.1 (diese Runde)

1. Per-Monitor-V2 DPI-Awareness (scharfe Fonts bei 125/150/175 %).
2. Popover öffnet sich jetzt an der Taskleiste (unten/oben/links/rechts).
3. User-Icon-Erkennung in `make_icons.py`.
4. Render-Jitter beim Button-Klick behoben (Scroll-Restore in `after_idle`).
5. „✓ übertragen" erscheint jetzt auch bei Status-only-Todos.
6. Export-Button hat flexible Höhe + kürzeren Text im Popover.

Details im Plan `/.claude/plans/es-gibt-noch-einige-happy-pearl.md`.
