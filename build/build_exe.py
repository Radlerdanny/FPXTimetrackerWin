"""PyInstaller-Build-Skript für FPX Timetracker (Windows).

Erzeugt eine einzelne dist/FPXTimetracker.exe:
- Entry-Point: fpx_tray.py
- Ein Binary – Popover/Großfenster werden per --popover / --big derselben .exe gestartet
- Assets (app.ico, tray.ico) ins Bundle eingebettet

Aufruf:
    python build/build_exe.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
APP_ICO = ASSETS / "app.ico"

# Icons immer neu erzeugen, damit ein frisch abgelegtes User-Icon sofort greift
print(">> make_icons.py (erzeugt/refresht app.ico + tray.ico)")
subprocess.check_call([sys.executable, str(ROOT / "build" / "make_icons.py")])

# Aufräumen
for d in ("build_tmp", "dist"):
    p = ROOT / d
    if p.exists(): shutil.rmtree(p, ignore_errors=True)

sep = ";" if sys.platform.startswith("win") else ":"

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",
    f"--name=FPXTimetracker",
    f"--icon={APP_ICO}",
    f"--add-data={ASSETS}{sep}assets",
    "--hidden-import=PIL._tkinter_finder",
    "--hidden-import=pystray._win32",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build_tmp"),
    "--specpath", str(ROOT / "build_tmp"),
    str(ROOT / "fpx_tray.py"),
]

print(">>>", " ".join(cmd))
subprocess.check_call(cmd, cwd=str(ROOT))
print("\nFertig:", ROOT / "dist" / "FPXTimetracker.exe")
