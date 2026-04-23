"""
FPX Timetracker – Windows Tray-Icon.
Hält den Popover-Subprozess am Leben, leitet Klicks als IPC-Kommandos weiter,
prüft GitHub auf neue Versionen und startet bei Bedarf den neuen Installer.
"""
import multiprocessing
multiprocessing.freeze_support()

import os, sys, json, time, threading, subprocess, tempfile
from pathlib import Path

from fpx_common import (
    APP_VERSION, GITHUB_REPO, DATA_DIR, IPC_FILE, LOCK_FILE,
    asset_path, write_ipc, read_ipc, IS_WIN,
)

# Erste Ausführung muss den Popover-Modus direkt starten,
# weil im PyInstaller-Bundle Tray und Tracker dieselbe .exe sind.
if "--popover" in sys.argv or "--big" in sys.argv:
    import fpx_timetracker
    fpx_timetracker.main()
    sys.exit(0)

# ── Singleton-Lock ───────────────────────────────────────────────────────────
DATA_DIR.mkdir(parents=True, exist_ok=True)
_lock_fh = open(LOCK_FILE, "w")
try:
    if IS_WIN:
        import msvcrt
        msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
except (OSError, IOError):
    print("FPX Timetracker läuft bereits.")
    sys.exit(0)

import requests
from PIL import Image
import pystray

# Dev-Modus: Python mit Skript aufrufen.
# Bundle: sys.executable ist die .exe selbst; --popover wird oben abgefangen.
if getattr(sys, "frozen", False):
    TRACKER_CMD = [sys.executable, "--popover"]
    BIG_CMD     = [sys.executable, "--big"]
else:
    HERE = Path(__file__).parent
    TRACKER_CMD = [sys.executable, str(HERE / "fpx_timetracker.py"), "--popover"]
    BIG_CMD     = [sys.executable, str(HERE / "fpx_timetracker.py")]


def _load_tray_image() -> Image.Image:
    ico = asset_path("tray.ico")
    if ico.exists():
        return Image.open(str(ico))
    app_ico = asset_path("app.ico")
    if app_ico.exists():
        return Image.open(str(app_ico))
    img = Image.new("RGBA", (32, 32), (71, 156, 197, 255))
    return img


# ── Auto-Updater ─────────────────────────────────────────────────────────────
def _ver_tuple(v: str):
    try: return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())
    except Exception: return (0,)


def _check_github():
    try:
        r = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
            timeout=10)
        if not r.ok: return None
        d = r.json()
        tag = (d.get("tag_name") or "").lstrip("v")
        body = d.get("body") or ""
        assets = d.get("assets") or []
        if not tag or _ver_tuple(tag) <= _ver_tuple(APP_VERSION):
            return None
        installer = next(
            (a for a in assets
             if a.get("name", "").lower().endswith(".exe")
             and "setup" in a.get("name", "").lower()),
            None)
        if not installer: return None
        return tag, body, installer["browser_download_url"], installer["name"]
    except Exception:
        return None


def _ask_user(version: str, changelog: str) -> bool:
    import ctypes
    cl_lines = [l.strip() for l in (changelog or "").split("\n") if l.strip()]
    cl_text = "\n".join(cl_lines[:8]) if cl_lines else "Keine Details verfügbar."
    msg = (
        f"Eine neue Version von FPX Timetracker ist verfügbar.\n\n"
        f"Aktuelle Version:  v{APP_VERSION}\n"
        f"Neue Version:      v{version}\n\n"
        f"── Neuerungen ──────────────\n\n"
        f"{cl_text}\n\n"
        f"Jetzt herunterladen und installieren?")
    MB_YESNO = 0x04; MB_ICONINFO = 0x40; IDYES = 6
    try:
        res = ctypes.windll.user32.MessageBoxW(
            0, msg, "FPX Timetracker – Update verfügbar", MB_YESNO | MB_ICONINFO)
        return res == IDYES
    except Exception:
        return False


def _download_installer(url: str, filename: str) -> Path | None:
    try:
        target = Path(tempfile.gettempdir()) / filename
        r = requests.get(url, timeout=180, stream=True)
        r.raise_for_status()
        with open(target, "wb") as f:
            for chunk in r.iter_content(1024 * 64):
                if chunk: f.write(chunk)
        return target
    except Exception:
        return None


def check_and_update(app: "TrayApp"):
    time.sleep(5)
    res = _check_github()
    if not res: return
    version, changelog, url, filename = res
    if not _ask_user(version, changelog): return
    installer = _download_installer(url, filename)
    if not installer: return

    # Popover beenden
    app.stop_tracker()
    try:
        if IS_WIN:
            import msvcrt as _m
            _m.locking(_lock_fh.fileno(), _m.LK_UNLCK, 1)
    except Exception: pass
    try: _lock_fh.close()
    except Exception: pass
    try: os.remove(LOCK_FILE)
    except Exception: pass

    # Installer starten – Inno Setup Silent-Flags
    subprocess.Popen(
        [str(installer), "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"],
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    os._exit(0)


# ── Tray-App ─────────────────────────────────────────────────────────────────
class TrayApp:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._icon: pystray.Icon | None = None
        self._stop_tick = False

    # Prozess-Management ------------------------------------------------------
    def _spawn(self, cmd):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try: self._proc.wait(timeout=1)
            except Exception: pass
        write_ipc({"state":"start", "visible_state":"hidden"})
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0
        self._proc = subprocess.Popen(
            cmd, creationflags=flags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.8)

    def start_tracker(self):
        self._spawn(TRACKER_CMD)

    def stop_tracker(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try: self._proc.wait(timeout=2)
            except Exception: pass
        self._proc = None

    # Click-Handler -----------------------------------------------------------
    def on_left_click(self, icon, item=None):
        d = read_ipc()
        if d.get("visible_state") == "big_open":
            self.stop_tracker()
            self.start_tracker()
            write_ipc({"cmd":"show", "ts":time.time()})
            return
        if self._proc is None or self._proc.poll() is not None:
            self.start_tracker()
            write_ipc({"cmd":"show", "ts":time.time()})
            return
        if d.get("visible_state") == "shown":
            write_ipc({"cmd":"hide", "ts":time.time()})
        else:
            write_ipc({"cmd":"show", "ts":time.time()})

    def on_open_big(self, icon, item):
        write_ipc({"cmd":"hide", "ts":time.time()}); time.sleep(0.2)
        self.stop_tracker()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WIN else 0
        self._proc = subprocess.Popen(
            BIG_CMD, creationflags=flags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def on_check_update(self, icon, item):
        threading.Thread(target=lambda: check_and_update(self), daemon=True).start()

    def on_quit(self, icon, item):
        self._stop_tick = True
        write_ipc({"cmd":"quit", "ts":time.time()}); time.sleep(0.2)
        self.stop_tracker()
        try: icon.stop()
        except Exception: pass

    # Tooltip-Updater ---------------------------------------------------------
    def _tick(self):
        while not self._stop_tick:
            d = read_ipc()
            txt = d.get("timer_txt", ""); proj = d.get("proj_no", "")
            if txt and proj: tooltip = f"FPX  {proj}  {txt}"
            elif txt:        tooltip = f"FPX  {txt}"
            else:            tooltip = "FPX Timetracker"
            try:
                if self._icon: self._icon.title = tooltip
            except Exception: pass
            if self._proc and self._proc.poll() is not None:
                self._proc = None
            time.sleep(1.0)

    # Run ---------------------------------------------------------------------
    def run(self):
        image = _load_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("FPX Timetracker öffnen", self.on_left_click, default=True),
            pystray.MenuItem("Großes Fenster", self.on_open_big),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Nach Updates suchen", self.on_check_update),
            pystray.MenuItem("Beenden", self.on_quit),
        )
        self._icon = pystray.Icon("FPX Timetracker", image, "FPX Timetracker", menu)
        self.start_tracker()
        threading.Thread(target=self._tick, daemon=True).start()
        threading.Thread(target=lambda: check_and_update(self), daemon=True).start()
        self._icon.run()


def main():
    TrayApp().run()


if __name__ == "__main__":
    main()
