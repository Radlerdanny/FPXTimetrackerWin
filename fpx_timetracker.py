import multiprocessing
multiprocessing.freeze_support()

"""
FPX TimeTracker (Windows) – tkinter Popover / Großfenster.
Wird von fpx_tray.py als Subprocess gestartet (--popover) oder direkt (Großfenster).
"""
import json, math, os, sys, threading, time, requests, urllib3
from datetime import date, datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from fpx_common import (
    APP_VERSION, FONT_MAIN, FONT_MONO,
    DATA_DIR, DATA_FILE, IPC_FILE,
    asset_path, write_ipc, IS_WIN,
    SCALE, s, get_work_area,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROAD_URL = "https://proad.fourplex.de/api/v5"
SSL_VERIFY = False
POPOVER_MODE = "--popover" in sys.argv

STATUS_KEY_ERLEDIGT = "500"; STATUS_KEY_WARTET = "300"; STATUS_DONE = {"500","600"}
C = {"bg":"#111111","panel":"#181818","card":"#1F1F1F","card2":"#272727","border":"#333333",
     "accent":"#479CC5","accent2":"#2E7A9E","accent_dim":"#1D4D63","text":"#F0EDE8",
     "text_dim":"#999999","text_mid":"#CCCCCC","green":"#4CAF7D","green2":"#3a9e68",
     "green_dim":"#1E4D35","red":"#E05555","orange":"#CC5555","yellow":"#E0C050",
     "gray_btn":"#444444","gray_btn2":"#383838","hover":"#2A2A2A"}
PROJEKTMANAGER = [
    {"name":"Anna Embach","kuerzel":"AE","urno":632},{"name":"Bastian Brezinski","kuerzel":"BB","urno":21},
    {"name":"Daniel Losch","kuerzel":"DL","urno":1411},{"name":"David Winkler","kuerzel":"DW","urno":8},
    {"name":"Goezde Dincgez","kuerzel":"GD","urno":1531},{"name":"Katharina Schweigert","kuerzel":"KJ","urno":1199},
    {"name":"Lea Schuster","kuerzel":"LS","urno":954},{"name":"Marcus Tischler","kuerzel":"MT","urno":9},
    {"name":"Pascal Tischler","kuerzel":"PT","urno":1198},
    {"name":"Tatjana Angersbach","kuerzel":"TA","urno":1680}]


def _apply_icon(root: tk.Tk):
    try:
        ico = asset_path("app.ico")
        if ico.exists():
            root.iconbitmap(default=str(ico))
    except Exception:
        pass


def load_data():
    try:
        with open(DATA_FILE) as f: return json.load(f)
    except Exception:
        return {"config":{},"sessions":{},"booked_today":{},"descriptions":{},"pending_status":{},"last_tracked":[]}


def save_data(d):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    open(DATA_FILE, "w", encoding="utf-8").write(json.dumps(d, indent=2, ensure_ascii=False))


def today_str(): return date.today().isoformat()
def ceil_min(s): return math.ceil(s/60) if s>0 else 0
def min_to_h(m): return round(m/60, 4)


def fmt_hhmm(m):
    if m <= 0: return "0:00"
    h, mn = divmod(int(m), 60); return f"{h}:{mn:02d}"


def fmt_timer(sec):
    s = int(sec); h, r = divmod(s, 3600); m, s2 = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s2:02d}"


def classify_todo(t):
    today = today_str(); fd = (t.get("from_datetime") or "")[:10]; ud = (t.get("until_datetime") or "")[:10]
    if fd == today: return "today"
    if fd < today and ud >= today: return "today"
    return "overdue" if fd < today else "future"


def get_sc_name(sc):
    if not sc or not isinstance(sc, dict): return ""
    return sc.get("shortname") or sc.get("name") or ""


class SetupWindow:
    def __init__(self):
        self.root = tk.Tk(); self.root.title("FPX TimeTracker"); _apply_icon(self.root)
        self.root.update_idletasks(); sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = 440, min(700, int(sh*0.82)); self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.root.configure(bg=C["bg"]); self.root.resizable(True, True); self.root.minsize(380, 480)
        self.result = None; self._build()

    def _build(self):
        outer = tk.Frame(self.root, bg=C["bg"]); outer.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(outer, orient="vertical"); sb.pack(side="right", fill="y")
        cv = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, bd=0, yscrollcommand=sb.set); sb.config(command=cv.yview); cv.pack(side="left", fill="both", expand=True)
        c = tk.Frame(cv, bg=C["bg"]); cwin = cv.create_window((0,0), window=c, anchor="nw")
        c.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfig(cwin, width=e.width))
        def sc(e):
            d = e.delta if e.delta != 0 else (-1 if e.num == 5 else 1)
            cv.yview_scroll(int(-1*(d/120)) if abs(d) > 1 else -d, "units")
        for ev in ["<MouseWheel>","<Button-4>","<Button-5>"]: cv.bind(ev, sc)
        tk.Frame(c, bg=C["accent"], height=3).pack(fill="x")
        logo = tk.Frame(c, bg=C["panel"]); logo.pack(fill="x")
        inner = tk.Frame(logo, bg=C["panel"]); inner.pack(pady=24)
        dot = tk.Canvas(inner, width=44, height=44, bg=C["panel"], highlightthickness=0); dot.pack(side="left", padx=(0,14))
        dot.create_oval(2,2,42,42, fill=C["accent"], outline=""); dot.create_text(22,22, text="F", font=(FONT_MAIN,19,"bold"), fill=C["text"])
        vbox = tk.Frame(inner, bg=C["panel"]); vbox.pack(side="left")
        tk.Label(vbox, text="FPX TimeTracker", font=(FONT_MAIN,17,"bold"), bg=C["panel"], fg=C["text"]).pack(anchor="w")
        tk.Label(vbox, text="Einmalige Einrichtung", font=(FONT_MAIN,11), bg=C["panel"], fg=C["text_dim"]).pack(anchor="w")
        tk.Frame(c, bg=C["border"], height=1).pack(fill="x")
        body = tk.Frame(c, bg=C["bg"]); body.pack(fill="x", padx=32, pady=22)
        tk.Label(body, text="PROAD API-Key", font=(FONT_MAIN,13,"bold"), bg=C["bg"], fg=C["text"]).pack(anchor="w")
        tk.Label(body, text="PROAD → Benutzer → PROAD API → Key kopieren", font=(FONT_MAIN,11), bg=C["bg"], fg=C["text_dim"]).pack(anchor="w", pady=(2,8))
        kf = tk.Frame(body, bg=C["border"]); kf.pack(fill="x", pady=(0,22)); self.key_var = tk.StringVar()
        tk.Entry(kf, textvariable=self.key_var, show="*", font=(FONT_MAIN,13), bg=C["card"], fg=C["text"], insertbackground=C["accent"], relief="flat", bd=0).pack(padx=1, pady=1, ipady=8, ipadx=12, fill="x")
        tk.Label(body, text="Wer bist du?", font=(FONT_MAIN,13,"bold"), bg=C["bg"], fg=C["text"]).pack(anchor="w")
        tk.Label(body, text="Todos werden auf deine Person geladen.", font=(FONT_MAIN,11), bg=C["bg"], fg=C["text_dim"]).pack(anchor="w", pady=(2,8))
        self.pm_var = tk.StringVar(); lf = tk.Frame(body, bg=C["card"]); lf.pack(fill="x", pady=(0,6)); self._lbls = {}
        def sel(name):
            self.pm_var.set(name)
            for n, l in self._lbls.items():
                l.config(bg=C["accent"] if n == name else C["card"], fg=C["bg"] if n == name else C["text"])
        for pm in PROJEKTMANAGER:
            l = tk.Label(lf, text=pm["name"], font=(FONT_MAIN,13), bg=C["card"], fg=C["text"], anchor="w", padx=14, pady=6); l.pack(fill="x", pady=1)
            l.bind("<Button-1>", lambda e, n=pm["name"]: sel(n)); self._lbls[pm["name"]] = l
        sel(PROJEKTMANAGER[0]["name"])
        btn = tk.Label(body, text="Speichern & Starten", font=(FONT_MAIN,13,"bold"), bg=C["accent"], fg=C["bg"], padx=16, pady=10, cursor="arrow"); btn.pack(fill="x", pady=(16,24))
        btn.bind("<Button-1>", lambda e: self._save()); btn.bind("<Enter>", lambda e: btn.config(bg=C["accent2"])); btn.bind("<Leave>", lambda e: btn.config(bg=C["accent"]))

    def _save(self):
        key = self.key_var.get().strip()
        if not key:
            messagebox.showwarning("Fehler", "API-Key eingeben.", parent=self.root); return
        pm = next((p for p in PROJEKTMANAGER if p["name"] == self.pm_var.get()), None)
        if not pm: return
        d = load_data(); d["config"] = {"api_key":key, "person_urno":pm["urno"], "person_name":pm["name"], "person_kuerzel":pm["kuerzel"]}
        save_data(d); self.result = d["config"]; self.root.destroy()

    def run(self):
        self.root.mainloop(); return self.result


class FPXTimeTracker:
    def __init__(self, config):
        self.config = config; self.api_key = config["api_key"]; self.person_urno = config["person_urno"]
        self.person_name = config["person_name"]; self.hdr = {"apikey":self.api_key, "Content-Type":"application/json"}
        self.data = load_data(); self.todos_today = []; self.todos_overdue = []
        self.loading = False; self.load_error = ""; self.sc_map = {}
        sessions = self.data.setdefault("sessions", {})
        for k in list(sessions.keys()):
            if k != today_str(): del sessions[k]
        sessions.setdefault(today_str(), {}); self.data.setdefault("descriptions", {})
        self.data.setdefault("pending_status", {}); self.data.setdefault("booked_today", {}); self.data.setdefault("last_tracked", [])
        _today = today_str()
        bt = self.data.setdefault("booked_today", {})
        for k in list(bt.keys()):
            if k != _today: del bt[k]
        save_data(self.data)
        self._booked_today = set(str(b) for b in bt.get(_today, []))
        self._pending = dict(self.data.get("pending_status", {})); self._quick_track = set(); self._force_today = set()
        self.active_urno = None; self.timer_start = None; self.timer_running = False; self.timer_job = None
        self._live_lbl = None; self._pulse_phase = 0; self._pulse_job = None
        self._expanded = set(); self._desc_open = None; self._collapsed_dates = set()
        self._build_window(); self._build_ui(); self._start_clock()
        if POPOVER_MODE: self._start_ipc_loop()
        self._load_todos()

    def _gp(self, u): return self.data["sessions"].get(today_str(), {}).get(str(u), [])
    def _gm(self, u): return sum(p.get("minutes", 0) for p in self._gp(u))
    def _gbs(self, u): return self._gm(u) * 60

    def _ap(self, u, st, et, m):
        self.data["sessions"][today_str()].setdefault(str(u), []).append({"start_ts":st, "end_ts":et, "minutes":m})
        lt = self.data.setdefault("last_tracked", [])
        if u not in lt: lt.insert(0, u)
        self.data["last_tracked"] = lt[:5]; save_data(self.data)

    def _dp(self, u, i):
        p = self.data["sessions"].get(today_str(), {}).get(str(u), [])
        if 0 <= i < len(p): p.pop(i); save_data(self.data)

    def _gd(self, u): return self.data.get("descriptions", {}).get(str(u), "")

    def _sd(self, u, t):
        self.data.setdefault("descriptions", {})[str(u)] = t; save_data(self.data)

    def _gpend(self, u): return self._pending.get(str(u))

    def _spend(self, u, s):
        if s is None: self._pending.pop(str(u), None)
        else: self._pending[str(u)] = s
        self.data["pending_status"] = self._pending; save_data(self.data)

    def _tpend(self, u, s):
        if self._desc_open and hasattr(self, "_desc_widget"):
            try:
                txt = self._desc_widget.get("1.0", "end-1c").strip()
                self._sd(self._desc_open, txt)
            except Exception: pass
        self._spend(u, None if self._gpend(u) == s else s)
        self._render_list()

    def _tquick(self, u, event=None):
        if u in self._quick_track:
            self._quick_track.discard(u)
            self.data.setdefault("quick_hours", {}).pop(str(u), None)
            save_data(self.data)
        else:
            all_todos = self.todos_today + self.todos_overdue
            todo = next((t for t in all_todos if t.get("urno") == u), None)
            suggested = todo.get("hours_left") or 0 if todo else 1.0
            self._quick_track.add(u)
            self.data.setdefault("quick_hours", {})[str(u)] = float(suggested) if suggested else 1.0
            save_data(self.data)
        self._render_list()

    def _build_window(self):
        self.root = tk.Tk(); self.root.title("FPX TimeTracker"); _apply_icon(self.root)
        try:
            self.root.tk.call("tk", "scaling", SCALE)
        except Exception: pass
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if POPOVER_MODE:
            wl, wt, wr, wb, edge = get_work_area()
            work_h = wb - wt
            self._W = s(380)
            self._H = min(s(740), int(work_h * 0.93))
            pad = s(8)
            # Reserve space for taskbar – also handles auto-hide taskbar (wb == sh)
            tb_reserve = s(50)
            if edge == "bottom":
                self._X = wr - self._W - pad; self._Y = sh - self._H - tb_reserve
                self._anim_dir = "up"
            elif edge == "top":
                self._X = wr - self._W - pad; self._Y = wt + pad
                self._anim_dir = "down"
            elif edge == "left":
                self._X = wl + pad;           self._Y = sh - self._H - tb_reserve
                self._anim_dir = "right"
            else:  # right
                self._X = wr - self._W - pad; self._Y = sh - self._H - tb_reserve
                self._anim_dir = "left"
            self._TBH = 0
            self.root.geometry(f"{self._W}x{self._H}+{self._X}+{self._Y}")
            self.root.configure(bg=C["bg"])
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.withdraw()
            write_ipc({"visible_state":"hidden"})
        else:
            w, h = s(460), min(s(800), int(sh*0.88))
            self.root.geometry(f"{w}x{h}+{sw-w-s(40)}+{(sh-h)//2}")
            self.root.configure(bg=C["bg"]); self.root.resizable(False, True); self.root.minsize(s(460), s(420))
            self.root.protocol("WM_DELETE_WINDOW", lambda: self.root.destroy())
        try:
            _st = ttk.Style(); _st.theme_use("clam")
            _st.configure("Vertical.TScrollbar", background=C["border"], troughcolor=C["bg"], arrowcolor=C["text_dim"], bordercolor=C["bg"])
        except Exception: pass

    def _start_ipc_loop(self):
        self._last_ts = 0
        def poll():
            try:
                d = json.loads(IPC_FILE.read_text()); cmd = d.get("cmd", ""); ts = d.get("ts", 0)
                if cmd and ts > self._last_ts:
                    self._last_ts = ts; IPC_FILE.write_text("{}")
                    if cmd == "show": self._animate_show()
                    elif cmd == "hide": self._animate_hide()
                    elif cmd == "reload": self._load_todos()
                    elif cmd == "quit": self.root.destroy(); return
            except Exception: pass
            self.root.after(200, poll)
        self.root.after(300, poll)

    def _slide_offset(self, t: float, dist: int) -> tuple[int, int]:
        """Liefert (dx, dy) für Slide-Animation in Richtung self._anim_dir.
        t=0 -> voll offset, t=1 -> 0 (am Zielort)."""
        d = getattr(self, "_anim_dir", "up")
        off = int(dist * (1 - t))
        if d == "up":    return (0, off)
        if d == "down":  return (0, -off)
        if d == "left":  return (off, 0)
        if d == "right": return (-off, 0)
        return (0, off)

    def _animate_show(self):
        H = self._H; tx = self._X; ty = self._Y; dist = s(25)
        dx0, dy0 = self._slide_offset(0.0, dist)
        self.root.geometry(f"{self._W}x{H}+{tx + dx0}+{ty + dy0}")
        self.root.attributes("-alpha", 0.0); self.root.deiconify(); self.root.lift(); self.root.focus_force()
        def step(i):
            if i > 16:
                self.root.geometry(f"{self._W}x{H}+{tx}+{ty}")
                self.root.attributes("-alpha", 1.0); write_ipc({"visible_state":"shown"}); return
            t = 1 - (1 - i/16) ** 3
            dx, dy = self._slide_offset(t, dist)
            self.root.geometry(f"{self._W}x{H}+{tx + dx}+{ty + dy}")
            self.root.attributes("-alpha", t); self.root.after(14, lambda: step(i+1))
        step(0)

    def _animate_hide(self):
        H = self._H; tx = self._X; ty = self._Y; dist = s(20)
        def step(i):
            if i > 10:
                self.root.withdraw(); self.root.attributes("-alpha", 1.0)
                self.root.geometry(f"{self._W}x{H}+{tx}+{ty}")
                write_ipc({"visible_state":"hidden"}); return
            t = 1 - (1 - i/10) ** 3
            self.root.attributes("-alpha", 1 - t)
            dx, dy = self._slide_offset(1 - t, dist)
            self.root.geometry(f"{self._W}x{H}+{tx + dx}+{ty + dy}")
            self.root.after(12, lambda: step(i+1))
        step(0)

    def _build_ui(self):
        tk.Frame(self.root, bg=C["accent"], height=2).pack(fill="x")
        top = tk.Frame(self.root, bg=C["panel"], height=s(44) if POPOVER_MODE else s(54)); top.pack(fill="x"); top.pack_propagate(False)
        dot = tk.Canvas(top, width=s(34), height=s(34), bg=C["panel"], highlightthickness=0); dot.pack(side="left", padx=(s(14),0), pady=(s(5) if POPOVER_MODE else s(10)))
        dot.create_oval(2,2,s(34)-2,s(34)-2, fill=C["accent"], outline=""); dot.create_text(s(34)//2,s(34)//2, text="F", font=(FONT_MAIN,15,"bold"), fill=C["text"])
        tk.Label(top, text="FPX TimeTracker", font=(FONT_MAIN, 13 if POPOVER_MODE else 14, "bold"), bg=C["panel"], fg=C["text"]).pack(side="left", padx=(s(10),s(4)))
        tk.Label(top, text=f"v{APP_VERSION}", font=(FONT_MAIN,10), bg=C["panel"], fg=C["text_dim"]).pack(side="left")
        rc_sz = s(26)
        rc = tk.Canvas(top, width=rc_sz, height=rc_sz, bg=C["panel"], highlightthickness=0, cursor="arrow"); rc.pack(side="right", padx=(0,s(10)), pady=s(9))
        def drc(bg):
            rc.delete("all"); rc.create_oval(0,0,rc_sz,rc_sz, fill=bg, outline=""); rc.create_text(rc_sz//2,rc_sz//2, text="↺", font=(FONT_MAIN,12,"bold"), fill=C["text"])
        drc(C["accent"]); rc.bind("<Button-1>", lambda e: self._load_todos())
        rc.bind("<Enter>", lambda e: drc(C["accent2"])); rc.bind("<Leave>", lambda e: drc(C["accent"]))
        self._reload_btn = rc; self._reload_draw_dim = lambda: drc(C["text_dim"]); self._reload_draw_on = lambda: drc(C["accent"])
        self._clock_lbl = tk.Label(top, text="", font=(FONT_MONO,11), bg=C["panel"], fg=C["text"]); self._clock_lbl.pack(side="right", padx=(0,s(12)))
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x")
        self._timer_canvas = tk.Canvas(self.root, height=s(66), bg=C["card"], highlightthickness=0, bd=0); self._timer_canvas.pack(fill="x")
        self._timer_canvas.bind("<Configure>", lambda e: self._draw_timer_block())
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x")
        self._build_qe()
        lo = tk.Frame(self.root, bg=C["bg"]); lo.pack(fill="both", expand=True)
        self._sb_w = ttk.Scrollbar(lo, orient="vertical"); self._sb_w.pack(side="right", fill="y")
        self._canvas = tk.Canvas(lo, bg=C["bg"], highlightthickness=0, bd=0, yscrollcommand=self._sb_w.set); self._sb_w.config(command=self._canvas.yview); self._canvas.pack(side="left", fill="both", expand=True)
        self._list_f = tk.Frame(self._canvas, bg=C["bg"]); self._cwin = self._canvas.create_window((0,0), window=self._list_f, anchor="nw")
        self._list_f.bind("<Configure>", self._on_frame_cfg); self._canvas.bind("<Configure>", self._on_canvas_cfg)
        for ev in ["<MouseWheel>","<Button-4>","<Button-5>"]:
            self._canvas.bind(ev, self._on_scroll); self._list_f.bind(ev, self._on_scroll)
        self.root.bind_all("<MouseWheel>", self._on_scroll); self.root.bind_all("<Button-4>", self._on_scroll); self.root.bind_all("<Button-5>", self._on_scroll)
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x")
        export_text = ("  ✓  Tag abschliessen  "
                       if POPOVER_MODE else
                       "  ✓  Tag abschliessen & nach PROAD übertragen  ")
        foot = tk.Frame(self.root, bg=C["panel"]); foot.pack(fill="x")
        self._export_btn = tk.Label(foot, text=export_text, font=(FONT_MAIN,12,"bold"), bg=C["green"], fg=C["bg"], pady=s(11), cursor="arrow"); self._export_btn.pack(fill="x", padx=s(10), pady=s(6))
        self._export_btn.bind("<Button-1>", lambda e: self._close_day())
        self._export_btn.bind("<Enter>", lambda e: self._export_btn.config(bg=C["green2"]))
        self._export_btn.bind("<Leave>", lambda e: self._export_btn.config(bg=C["green"]))

    def _build_qe(self):
        qf = tk.Frame(self.root, bg=C["panel"], height=s(42)); qf.pack(fill="x"); qf.pack_propagate(False)
        tk.Label(qf, text="+ To-Do:", font=(FONT_MAIN,11), bg=C["panel"], fg=C["text"], padx=10).pack(side="left")
        self._qe_var = tk.StringVar(); ph = "FPX-422 GRA 0.5"
        qe = tk.Entry(qf, textvariable=self._qe_var, font=(FONT_MAIN,11), bg=C["card"], fg=C["text"], insertbackground=C["accent"], relief="flat", bd=0, width=26); qe.pack(side="left", ipady=4, ipadx=6, pady=6)
        qe.bind("<Button-1>", lambda e: (qe.focus_set(), "break"))
        qe.insert(0, ph); qe.config(fg=C["text_dim"])
        qe.bind("<FocusIn>", lambda e: (qe.delete(0, "end"), qe.config(fg=C["text"])) if qe.get() == ph else None)
        qe.bind("<FocusOut>", lambda e: (qe.insert(0, ph), qe.config(fg=C["text_dim"])) if not qe.get().strip() else None)
        qe.bind("<Return>", lambda e: self._quick_entry())
        btn = tk.Label(qf, text="Erstellen", font=(FONT_MAIN,11), bg=C["accent"], fg=C["text"], padx=10, pady=4, cursor="arrow"); btn.pack(side="left", padx=(6,0), pady=6)
        btn.bind("<Button-1>", lambda e: self._quick_entry())
        btn.bind("<Enter>", lambda e: btn.config(bg=C["accent2"])); btn.bind("<Leave>", lambda e: btn.config(bg=C["accent"]))
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x")

    def _on_scroll(self, e):
        if isinstance(e.widget, (tk.Entry, tk.Text)): return
        focused = self.root.focus_get()
        d = e.delta if e.delta != 0 else (-1 if e.num == 5 else 1)
        self._canvas.yview_scroll(int(-1*(d/120)) if abs(d) > 1 else -d, "units")
        if isinstance(focused, (tk.Entry, tk.Text)):
            try: focused.focus_set()
            except Exception: pass

    def _bst(self, w):
        if isinstance(w, (tk.Entry, tk.Text)): return
        for ev in ["<MouseWheel>","<Button-4>","<Button-5>"]: w.bind(ev, self._on_scroll)
        for c in w.winfo_children(): self._bst(c)

    def _on_frame_cfg(self, e):
        if getattr(self, '_rebuilding', False): return
        bb = self._canvas.bbox("all")
        if bb: self._canvas.configure(scrollregion=(0, 0, bb[2], max(bb[3], self._canvas.winfo_height())))

    def _on_canvas_cfg(self, e): self._canvas.itemconfig(self._cwin, width=e.width)

    def _start_clock(self):
        def t():
            try: self._clock_lbl.config(text=datetime.now().strftime("%H:%M"))
            except Exception: pass
            self.root.after(20000, t)
        t()

    def _draw_timer_block(self):
        c = self._timer_canvas; w = c.winfo_width(); h = c.winfo_height()
        if w < 10: return
        c.delete("all"); c.configure(bg=C["card"])
        if self.timer_running and self.active_urno:
            at = self.todos_today + self.todos_overdue; todo = next((t for t in at if t.get("urno") == self.active_urno), None)
            name = (todo.get("shortinfo", "") if todo else "")[:36]
            proj_no = ((todo.get("project") or {}).get("projectno", "") if todo else "")
            ph = self._pulse_phase; cy = h//2; pulse = 0.55 + 0.45 * math.sin(ph)
            ro = int(11*pulse); ri = max(3, int(6*pulse)); cx_d = 18
            c.create_oval(cx_d-ro, cy-ro, cx_d+ro, cy+ro, fill=C["green_dim"], outline="")
            c.create_oval(cx_d-ri, cy-ri, cx_d+ri, cy+ri, fill=C["green"], outline="")
            c.create_text(36, cy-11, text=name, font=(FONT_MAIN,13,"bold"), fill=C["text"], anchor="w")
            c.create_text(36, cy+10, text=proj_no, font=(FONT_MAIN,11), fill=C["accent"], anchor="w")
            elapsed = time.time() - self.timer_start; total_sec = self._gbs(self.active_urno) + elapsed
            c.create_text(w-14, cy, text=fmt_timer(total_sec), font=(FONT_MONO,18,"bold"), fill=C["green"], anchor="e")
        else:
            c.create_oval(14, h//2-5, 24, h//2+5, fill=C["border"], outline="")
            c.create_text(34, h//2, text="Kein Timer aktiv", font=(FONT_MAIN,11), fill=C["text"], anchor="w")

    def _start_pulse(self):
        self._ipc_tick = 0
        def pulse():
            if not self.timer_running: return
            self._pulse_phase = (self._pulse_phase + 0.15) % (2*math.pi); self._draw_timer_block()
            self._ipc_tick += 1
            if self._ipc_tick >= 20:
                self._ipc_tick = 0
                try:
                    elapsed = time.time() - self.timer_start; total_sec = int(self._gbs(self.active_urno) + elapsed)
                    h, r = divmod(total_sec, 3600); m, s = divmod(r, 60)
                    txt = f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
                    try: d = json.loads(IPC_FILE.read_text())
                    except Exception: d = {}
                    at = self.todos_today + self.todos_overdue
                    todo = next((t for t in at if t.get("urno") == self.active_urno), None)
                    proj_no = ((todo.get("project") or {}).get("projectno", "") if todo else "")
                    if not d.get("cmd"):
                        write_ipc({"timer_txt":txt, "proj_no":proj_no, "visible_state":d.get("visible_state","hidden")})
                except Exception: pass
            self._pulse_job = self.root.after(50, pulse)
        pulse()

    def _stop_pulse(self):
        if self._pulse_job: self.root.after_cancel(self._pulse_job); self._pulse_job = None
        try:
            try: d = json.loads(IPC_FILE.read_text())
            except Exception: d = {}
            write_ipc({"timer_txt":"", "visible_state":d.get("visible_state","hidden")})
        except Exception: pass

    def _load_todos(self):
        if self.loading: return
        self.loading = True; self.load_error = ""; self._reload_draw_on(); self._render_list()
        threading.Thread(target=self._fetch_todos, daemon=True).start()

    def _fetch_todos(self):
        try:
            today = today_str(); df = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
            try:
                rs = requests.get(f"{PROAD_URL}/service_codes", headers=self.hdr, timeout=15, verify=SSL_VERIFY)
                if rs.ok:
                    raw = rs.json(); scl = raw.get("service_code_list") or (raw if isinstance(raw, list) else [])
                    self.sc_map = {sc["urno"]: sc.get("shortname") or sc.get("name", "") for sc in scl if isinstance(sc, dict) and sc.get("urno")}
            except Exception: pass
            r1 = requests.get(f"{PROAD_URL}/tasks", headers=self.hdr, params={"person":str(self.person_urno), "from_date":f"{df}--{today}"}, timeout=25, verify=SSL_VERIFY); r1.raise_for_status()
            t1 = r1.json().get("todo_list", [])
            r2 = requests.get(f"{PROAD_URL}/tasks", headers=self.hdr, params={"person":str(self.person_urno), "until_date":today}, timeout=25, verify=SSL_VERIFY)
            t2 = r2.json().get("todo_list", []) if r2.ok else []
            seen, todos = {}, []
            for t in t1 + t2:
                u = t.get("urno")
                if u and u not in seen: seen[u] = True; todos.append(t)
            todos = [t for t in todos if str(t.get("status", "")) not in STATUS_DONE]
            for t in todos:
                sc = t.get("service_code")
                if isinstance(sc, dict) and not get_sc_name(sc):
                    su = sc.get("urno")
                    if su: sc["shortname"] = self.sc_map.get(su, "")
                elif isinstance(sc, int):
                    t["service_code"] = {"urno":sc, "shortname":self.sc_map.get(sc, "")}
            tl, ol = [], []
            for t in todos:
                cat = classify_todo(t)
                if cat == "today": tl.append(t)
                elif cat == "overdue": ol.append(t)
            tl.sort(key=lambda t: (t.get("project") or {}).get("projectno", ""))
            ol.sort(key=lambda t: (t.get("until_datetime") or t.get("from_datetime") or ""))
            self.todos_today = tl; self.todos_overdue = ol; self.loading = False; self.load_error = ""
            self.root.after(0, self._on_load_done)
        except Exception as ex:
            self.loading = False; self.load_error = str(ex); self.root.after(0, self._on_load_done)

    def _on_load_done(self):
        self._booked_today = set()
        self.data.setdefault("booked_today", {})[today_str()] = []
        self.data.setdefault("sessions", {})[today_str()] = {}
        save_data(self.data)
        self._reload_draw_on(); self._render_list(); self._draw_timer_block()

    def _render_list(self):
        try: sp = self._canvas.yview()[0]
        except Exception: sp = 0.0
        self._rebuilding = True
        # Windows: Redraws während des Rebuilds unterdrücken (kein Flackern)
        hwnd = 0; _cty = None
        if IS_WIN:
            try:
                import ctypes as _cty
                hwnd = self.root.winfo_id()
                _cty.windll.user32.SendMessageW(hwnd, 0x000B, 0, 0)  # WM_SETREDRAW = FALSE
            except Exception: hwnd = 0
        try:
            try: self._canvas.configure(yscrollcommand=lambda *a: None)
            except Exception: pass
            for w in self._list_f.winfo_children(): w.destroy()
            if self.loading:
                tk.Label(self._list_f, text="Todos werden geladen...", font=(FONT_MAIN,13), bg=C["bg"], fg=C["text"]).pack(pady=50)
            elif self.load_error:
                tk.Label(self._list_f, text="Verbindungsfehler", font=(FONT_MAIN,13,"bold"), bg=C["bg"], fg=C["red"]).pack(pady=(40,8))
                tk.Label(self._list_f, text=self.load_error[:100], font=(FONT_MAIN,10), bg=C["bg"], fg=C["text_dim"], wraplength=360).pack()
                rb = tk.Label(self._list_f, text="Erneut versuchen", font=(FONT_MAIN,12), bg=C["accent"], fg=C["bg"], padx=14, pady=7, cursor="arrow"); rb.pack(pady=16)
                rb.bind("<Button-1>", lambda e: self._load_todos())
            elif not self.todos_overdue and not self.todos_today:
                tk.Label(self._list_f, text="Keine offenen Todos", font=(FONT_MAIN,13), bg=C["bg"], fg=C["text_mid"]).pack(pady=60)
            else:
                if self.todos_overdue:
                    self._rgh("Abgelaufen", sum(self._gm(t.get("urno", 0)) for t in self.todos_overdue), C["orange"])
                    seen_d = []
                    for t in self.todos_overdue:
                        fd = (t.get("until_datetime") or t.get("from_datetime") or "")[:10]
                        if fd not in seen_d: seen_d.append(fd); self._rds(fd, fd in self._collapsed_dates)
                        if fd not in self._collapsed_dates: self._rtr(t, overdue=True)
                if self.todos_today:
                    self._rgh("Heute", sum(self._gm(t.get("urno", 0)) for t in self.todos_today), C["text_mid"])
                    for t in self.todos_today: self._rtr(t)
                tk.Frame(self._list_f, bg=C["bg"], height=12).pack(fill="x")
            self.root.update_idletasks()
            self._rebuilding = False
            bb = self._canvas.bbox("all")
            if bb:
                self._canvas.configure(scrollregion=(0, 0, bb[2], max(bb[3], self._canvas.winfo_height())))
            self._canvas.configure(yscrollcommand=self._sb_w.set)
            self._canvas.yview_moveto(sp)
            self._bst(self._list_f)
        finally:
            if hwnd and _cty:
                try:
                    _cty.windll.user32.SendMessageW(hwnd, 0x000B, 1, 0)  # WM_SETREDRAW = TRUE
                    # RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN = 0x0085
                    _cty.windll.user32.RedrawWindow(hwnd, None, None, 0x0085)
                except Exception: pass

    def _rgh(self, label, total=0, color=None):
        color = color or C["text_mid"]; hf = tk.Frame(self._list_f, bg=C["bg"], height=36); hf.pack(fill="x"); hf.pack_propagate(False)
        tk.Label(hf, text=label, font=(FONT_MAIN,12,"bold"), bg=C["bg"], fg=color, anchor="w", padx=14).pack(side="left", fill="y")
        tk.Frame(self._list_f, bg=C["border"], height=1).pack(fill="x")

    def _rds(self, ds, collapsed):
        try:
            d = datetime.strptime(ds, "%Y-%m-%d").date(); delta = (date.today() - d).days
            label = "Heute" if delta == 0 else ("Gestern" if delta == 1 else f"Vor {delta} Tagen")
            label = f"{label} ({d.strftime('%d.%m.%Y')})"
        except Exception: label = ds
        sf = tk.Frame(self._list_f, bg="#1A1A1A", height=28); sf.pack(fill="x"); sf.pack_propagate(False)
        arr = "▼" if not collapsed else "▶"
        al = tk.Label(sf, text=arr, font=(FONT_MAIN,10), bg="#1A1A1A", fg=C["orange"], padx=10); al.pack(side="left", fill="y")
        ll = tk.Label(sf, text=label, font=(FONT_MAIN,10,"bold"), bg="#1A1A1A", fg=C["orange"], anchor="w"); ll.pack(side="left", fill="y")
        for w in [sf, al, ll]:
            w.bind("<Button-1>", lambda e, x=ds: self._tdc(x)); w.config(cursor="arrow")

    def _tdc(self, ds):
        (self._collapsed_dates.discard(ds) if ds in self._collapsed_dates else self._collapsed_dates.add(ds))
        self._render_list()

    def _rtr(self, todo, overdue=False):
        u = todo.get("urno"); ia = self.timer_running and self.active_urno == u
        bkd = str(u) in self._booked_today; trk = self._gm(u); parts = self._gp(u)
        exp = u in self._expanded; dop = self._desc_open == u; sdesc = self._gd(u); pend = self._gpend(u); isq = u in self._quick_track
        rbg = C["card2"] if ia else C["card"]
        outer = tk.Frame(self._list_f, bg=rbg); outer.pack(fill="x")
        bc = C["green"] if ia else (C["accent"] if bkd else (C["orange"] if overdue else C["border"]))
        tk.Frame(outer, bg=bc, width=3).pack(side="left", fill="y")
        body = tk.Frame(outer, bg=rbg); body.pack(side="left", fill="both", expand=True, padx=(10,10), pady=(7,5))
        proj = (todo.get("project") or {}); pno = proj.get("projectno", "")
        sc = todo.get("service_code") or {}; scn = get_sc_name(sc) or self.sc_map.get(sc.get("urno") if isinstance(sc, dict) else sc, "")
        hl = todo.get("hours_left")
        r0 = tk.Frame(body, bg=rbg); r0.pack(fill="x")
        tk.Label(r0, text=pno, font=(FONT_MAIN,9), bg=rbg, fg=C["accent"], anchor="w").pack(side="left")
        if overdue:
            itf = u in self._force_today
            tb = tk.Label(r0, text="heute", font=(FONT_MAIN,9), bg=C["accent"] if itf else C["card2"],
                          fg=C["text"] if itf else C["text_dim"], padx=5, pady=1, cursor="arrow")
            tb.pack(side="left", padx=(6,0))
            tb.bind("<Button-1>", lambda e, x=u: (self._force_today.discard(x) if x in self._force_today else self._force_today.add(x), self._render_list()))
        r1 = tk.Frame(body, bg=rbg); r1.pack(fill="x", pady=(1,0))
        pb_bg = C["green"] if ia else C["accent"]; pb_hbg = "#5DCF8A" if ia else "#5AAECC"
        btn_w, btn_h = s(34), s(30)
        pf = tk.Canvas(r1, width=btn_w, height=btn_h, highlightthickness=0, cursor="arrow", bg=pb_bg)
        pf.pack(side="right", padx=(6,0))
        def _draw_icon(bg=pb_bg, _ia=ia, _c=pf):
            _c.delete("all"); _c.config(bg=bg)
            cx, cy = btn_w//2, btn_h//2
            if _ia:
                bw, bh = max(3, s(3)), s(11); gap = s(4)
                _c.create_rectangle(cx-gap-bw, cy-bh//2, cx-gap, cy+bh//2, fill=C["text"], outline="")
                _c.create_rectangle(cx+gap, cy-bh//2, cx+gap+bw, cy+bh//2, fill=C["text"], outline="")
            else:
                sz = s(9)
                _c.create_polygon(cx-sz//2, cy-sz, cx-sz//2, cy+sz, cx+sz, cy, fill=C["text"], outline="")
        _draw_icon()
        pf.bind("<Button-1>", lambda e, x=u: self._tt(x))
        pf.bind("<Enter>", lambda e, bg=pb_hbg: _draw_icon(bg))
        pf.bind("<Leave>", lambda e, bg=pb_bg: _draw_icon(bg))
        nf = tk.Frame(r1, bg=rbg); nf.pack(side="left", fill="x", expand=True)
        tk.Label(nf, text=todo.get("shortinfo", "?"), font=(FONT_MAIN,11,"bold") if not bkd else (FONT_MAIN,11), bg=rbg, fg=C["text"] if not bkd else C["text_mid"], anchor="w", wraplength=220, justify="left").pack(side="left")
        dl = tk.Label(nf, text="✎", font=(FONT_MAIN,11), bg=rbg, fg=C["yellow"], cursor="arrow", padx=2); dl.pack(side="left", anchor="n", pady=1)
        dl.bind("<Button-1>", lambda e, x=u: self._tdesc(x))
        r2 = tk.Frame(body, bg=rbg); r2.pack(fill="x", pady=(2,0))
        da = pend == "erledigt"; db_bg = C["green"] if da else C["green_dim"]; db_hbg = "#5DCF8A" if da else "#2A7048"
        db = tk.Label(r2, text="✓ Erledigt" if da else "Erledigt", font=(FONT_MAIN,10), bg=db_bg, fg=C["text"], padx=8, pady=2, cursor="arrow"); db.pack(side="left", padx=(0,4))
        db.bind("<Button-1>", lambda e, x=u: self._tpend(x, "erledigt"))
        db.bind("<Enter>", lambda e, b=db, h=db_hbg: b.config(bg=h)); db.bind("<Leave>", lambda e, b=db, o=db_bg: b.config(bg=o))
        wa = pend == "wartet"; wb_bg = "#555555" if wa else C["gray_btn2"]; wb_hbg = "#686868" if wa else "#505050"
        wb = tk.Label(r2, text="⏸ Wartet" if wa else "Wartet", font=(FONT_MAIN,10), bg=wb_bg, fg=C["text"], padx=8, pady=2, cursor="arrow"); wb.pack(side="left", padx=(0,4))
        wb.bind("<Button-1>", lambda e, x=u: self._tpend(x, "wartet"))
        wb.bind("<Enter>", lambda e, b=wb, h=wb_hbg: b.config(bg=h)); wb.bind("<Leave>", lambda e, b=wb, o=wb_bg: b.config(bg=o))
        qa = isq; qb_bg = C["accent"] if qa else C["accent_dim"]; qb_hbg = "#5AAECC" if qa else "#2E708A"
        qb = tk.Label(r2, text="★ Tracken" if qa else "Tracken", font=(FONT_MAIN,10), bg=qb_bg, fg=C["text"], padx=8, pady=2, cursor="arrow")
        qb.pack(side="left")
        qb.bind("<Button-1>", lambda e, x=u: self._tquick(x, e))
        qb.bind("<Enter>", lambda e, b=qb, h=qb_hbg: b.config(bg=h))
        qb.bind("<Leave>", lambda e, b=qb, o=qb_bg: b.config(bg=o))
        qh = self.data.get("quick_hours", {}).get(str(u))
        if isq:
            qh_var = tk.StringVar(value=f"{qh:g}" if qh else "")
            qh_e = tk.Entry(r2, textvariable=qh_var, font=(FONT_MONO,11), bg=C["card2"],
                            fg=C["text"], insertbackground=C["text"], relief="flat",
                            bd=0, justify="center", width=4)
            qh_e.pack(side="left", ipady=2, ipadx=4, padx=(4,0))
            tk.Label(r2, text="h", font=(FONT_MAIN,10), bg=rbg, fg=C["text_dim"]).pack(side="left", padx=(2,0))
            def _save_qh(e=None, x=u, v=qh_var):
                try:
                    h = float(v.get().replace(",", "."))
                    if h > 0: self.data.setdefault("quick_hours", {})[str(x)] = h; save_data(self.data)
                except Exception: pass
            qh_e.bind("<Return>", _save_qh)
            qh_e.bind("<FocusOut>", _save_qh)
        if parts:
            pt = tk.Label(r2, text=f"{'▼' if u in self._expanded else '▶'} {len(parts)}", font=(FONT_MAIN,10), bg=rbg, fg=C["green"], cursor="arrow", padx=4); pt.pack(side="right", padx=(0,4))
            pt.bind("<Button-1>", lambda e, x=u: self._texp(x))
        if scn or hl is not None:
            if hl is not None:
                hl_color = C["red"] if hl == 0 else C["text"]
                det_txt = f"{hl:g}h"
            else:
                hl_color = C["text"]; det_txt = None
            if scn and det_txt:
                tk.Label(r2, text=scn, font=(FONT_MAIN,10), bg=rbg, fg=C["text"], anchor="e").pack(side="right", padx=(2,0))
                tk.Label(r2, text=det_txt, font=(FONT_MAIN,10,"bold"), bg=rbg, fg=hl_color, anchor="e").pack(side="right")
            elif det_txt:
                tk.Label(r2, text=det_txt, font=(FONT_MAIN,10,"bold"), bg=rbg, fg=hl_color, anchor="e").pack(side="right")
            elif scn:
                tk.Label(r2, text=scn, font=(FONT_MAIN,10), bg=rbg, fg=C["text"], anchor="e").pack(side="right")
        r3 = tk.Frame(body, bg=rbg); r3.pack(fill="x", pady=(4,0))
        if sdesc and not dop:
            tk.Label(r3, text=f"✎  {sdesc[:62]}{'...' if len(sdesc) > 62 else ''}", font=(FONT_MAIN,10,"italic"), bg=rbg, fg=C["yellow"], anchor="w", wraplength=360).pack(side="left")
        if bkd:
            tk.Label(r3, text="✓ übertragen", font=(FONT_MAIN,10,"bold"), bg=rbg, fg=C["green"]).pack(side="right", padx=(8,0))
        if dop:
            dfo = tk.Frame(body, bg=rbg); dfo.pack(fill="x", pady=(6,0))
            df = tk.Frame(dfo, bg=C["border"]); df.pack(fill="x")
            dt = tk.Text(df, font=(FONT_MAIN,11), bg=C["card"], fg=C["text"], insertbackground=C["yellow"], relief="flat", bd=0, height=3, wrap="word"); dt.pack(padx=1, pady=1, ipadx=6, ipady=4, fill="x")
            if sdesc: dt.insert("1.0", sdesc)
            self._desc_widget = dt
            sb2 = tk.Label(dfo, text="Speichern", font=(FONT_MAIN,10,"bold"), bg=C["accent2"], fg=C["text"], padx=10, pady=3, cursor="arrow"); sb2.pack(side="right", pady=(4,0))
            def _sdesc(e=None, x=u, d=dt):
                self._sd(x, d.get("1.0", "end-1c").strip())
                self._desc_open = None; self._render_list()
            sb2.bind("<Button-1>", _sdesc)
            sb2.bind("<Enter>", lambda e, b=sb2: b.config(bg=C["accent"])); sb2.bind("<Leave>", lambda e, b=sb2: b.config(bg=C["accent2"]))
        if u in self._expanded and parts:
            pf2 = tk.Frame(body, bg=rbg); pf2.pack(fill="x", pady=(5,0)); tk.Frame(pf2, bg=C["border"], height=1).pack(fill="x", pady=(0,3))
            for idx, part in enumerate(parts):
                pr = tk.Frame(pf2, bg=rbg); pr.pack(fill="x", pady=1)
                def fp(p):
                    def ts(t):
                        try: return datetime.fromtimestamp(t).strftime("%H:%M:%S")
                        except Exception: return "?"
                    return f"{ts(p.get('start_ts'))}  –  {ts(p.get('end_ts'))}  ({fmt_hhmm(p.get('minutes', 0))})"
                xb = tk.Label(pr, text="✕", font=(FONT_MAIN,12), bg=rbg, fg=C["red"], cursor="arrow", padx=4); xb.pack(side="right")
                xb.bind("<Button-1>", lambda e, x=u, i=idx: self._delpart(x, i))
                tk.Label(pr, text=fp(part), font=(FONT_MONO,10), bg=rbg, fg=C["text_mid"], anchor="w").pack(side="left")
        tk.Frame(self._list_f, bg=C["border"], height=1).pack(fill="x")
        all_ws = self._ac(outer); snap = {w: w.cget("bg") for w in all_ws if hasattr(w, "cget")}
        def oe(e, ws=all_ws, rb=rbg):
            self._canvas.focus_set()
            for w in ws:
                if snap.get(w) in (rb, C["bg"]) and hasattr(w, "config"): w.config(bg=C["hover"])
        def ole(e, ws=all_ws):
            for w in ws:
                if w in snap and hasattr(w, "config"): w.config(bg=snap[w])
        for w in all_ws:
            w.bind("<Enter>", oe); w.bind("<Leave>", ole)
            for ev in ["<MouseWheel>","<Button-4>","<Button-5>"]: w.bind(ev, self._on_scroll)

    def _ac(self, w):
        r = [w]
        for c in w.winfo_children(): r.extend(self._ac(c))
        return r

    def _texp(self, u):
        (self._expanded.discard(u) if u in self._expanded else self._expanded.add(u)); self._render_list()

    def _tdesc(self, u):
        self._desc_open = None if self._desc_open == u else u; self._render_list()

    def _tt(self, u):
        if self.timer_running and self.active_urno == u: self._stop_timer()
        else:
            if self.timer_running: self._stop_timer(rerender=False)
            self._start_timer(u)

    def _start_timer(self, u):
        self.active_urno = u; self.timer_start = time.time(); self.timer_running = True; self._pulse_phase = 0
        self._render_list(); self._start_pulse()
        if POPOVER_MODE:
            self.root.after(150, self._animate_hide)

    def _stop_timer(self, rerender=True, add_part=True):
        if not self.timer_running: return
        elapsed = time.time() - self.timer_start; u = self.active_urno
        if add_part and elapsed > 0: self._ap(u, self.timer_start, time.time(), ceil_min(elapsed))
        self.timer_running = False; self.active_urno = None; self.timer_start = None
        if self.timer_job: self.root.after_cancel(self.timer_job); self.timer_job = None
        self._stop_pulse()
        if rerender: self._render_list(); self._draw_timer_block()

    def _delpart(self, u, i):
        if not (0 <= i < len(self._gp(u))): return
        if not self._askdialog("Part löschen", "Zeit löschen?"): return
        if self.timer_running and self.active_urno == u: self._stop_timer(add_part=False)
        self._dp(u, i); self._render_list(); self._draw_timer_block()

    def _push_status(self, u, label):
        k = {"erledigt":STATUS_KEY_ERLEDIGT, "wartet":STATUS_KEY_WARTET}.get(label.lower(), "")
        if not k: return
        def do():
            try: requests.put(f"{PROAD_URL}/tasks/{u}", headers=self.hdr, json={"status":k}, timeout=15, verify=SSL_VERIFY)
            except Exception: pass
        threading.Thread(target=do, daemon=True).start()

    def _quick_entry(self):
        import re; raw = self._qe_var.get().strip()
        if not raw: return
        pts = re.split(r'[\s,;]+', raw)
        if len(pts) < 2: return
        proj_no = pts[0].upper(); sc_key = pts[1].upper()
        try: hours = float(pts[2].replace(",", ".")) if len(pts) > 2 else 0.5
        except Exception: hours = 0.5
        def do():
            try:
                r = requests.get(f"{PROAD_URL}/projects", headers=self.hdr, params={"order_date":f"{(date.today() - timedelta(days=365)).strftime('%Y-%m-%d')}--2027-12-31"}, timeout=20, verify=SSL_VERIFY); r.raise_for_status()
                proj = next((p for p in r.json().get("project_list", []) if p.get("projectno", "").upper() == proj_no), None)
                if not proj:
                    self.root.after(0, lambda: self._dialog("Fehler", f"Projekt '{proj_no}' nicht gefunden.", "error")); return
                rs = requests.get(f"{PROAD_URL}/service_codes", headers=self.hdr, timeout=15, verify=SSL_VERIFY)
                scl = rs.json().get("service_code_list", []) if rs.ok else []
                sc = next((s for s in scl if s.get("shortname", "").upper() == sc_key or s.get("name", "").upper() == sc_key), None)
                if not sc:
                    self.root.after(0, lambda: self._dialog("Fehler", f"'{sc_key}' nicht gefunden.", "error")); return
                d = today_str(); pname = proj.get("project_name") or proj_no
                payload = {"shortinfo":f"PM {pname}", "urno_project":proj["urno"], "urno_responsible":self.person_urno, "urno_manager":self.person_urno, "status":"100", "from_datetime":f"{d}T00:00:00", "until_datetime":f"{d}T00:00:00", "hours_planned":hours, "hours_left":hours, "urno_service_code":sc["urno"]}
                rt = requests.post(f"{PROAD_URL}/tasks", headers=self.hdr, json=payload, timeout=20, verify=SSL_VERIFY)
                if not rt.ok:
                    self.root.after(0, lambda: self._dialog("Fehler", rt.text[:120], "error")); return
                self.root.after(0, lambda: (self._qe_var.set(""), self._dialog("OK", f"Todo 'PM {pname}' ({hours}h) angelegt.", "ok"), self._load_todos()))
            except Exception as ex:
                self.root.after(0, lambda: self._dialog("Fehler", str(ex)[:120], "error"))
        threading.Thread(target=do, daemon=True).start()

    def _close_day(self):
        if self.timer_running: self._stop_timer()
        all_todos = self.todos_today + self.todos_overdue
        qt_pending = {}
        for t in all_todos:
            u = t.get("urno")
            if u in self._quick_track and self._gm(u) == 0:
                h = self.data.get("quick_hours", {}).get(str(u)) or t.get("hours_left") or 0
                if h > 0: qt_pending[u] = round(h * 60)
        to_exp = []
        for t in all_todos:
            u = t.get("urno"); pend = self._gpend(u)
            mins = self._gm(u) + qt_pending.get(u, 0)
            if (mins > 0 or pend) and str(u) not in self._booked_today:
                to_exp.append((t, mins))
        if not to_exp:
            self._dialog("Fertig", "Nichts zu exportieren.", "info"); return
        enr = []
        for to, m in to_exp:
            try:
                r = requests.get(f"{PROAD_URL}/tasks/{to.get('urno')}", headers=self.hdr, timeout=15, verify=SSL_VERIFY)
                enr.append((r.json() if r.ok else to, m))
            except Exception: enr.append((to, m))
        err, val = [], []
        for t, m in enr:
            sc = t.get("service_code") or {}; proj = t.get("project") or {}; name = t.get("shortinfo", "?")[:40]
            sc_u = (sc.get("urno") if isinstance(sc, dict) else sc) or t.get("urno_service_code")
            if not sc_u: err.append(f"  - {name}: Keine Leistungsart")
            elif not proj.get("urno"): err.append(f"  - {name}: Kein Projekt")
            else: val.append((t, m))
        if err:
            self._dialog("Übersprungen", "\n".join(err), "warn")
            if not val: return
            enr = val
        lines, tot = [], 0
        for t, m in enr:
            tot += m; sc = t.get("service_code") or {}; sc_u = (sc.get("urno") if isinstance(sc, dict) else sc) or t.get("urno_service_code")
            scn = get_sc_name(sc) or self.sc_map.get(sc_u, "?"); pno = (t.get("project") or {}).get("projectno", "?"); p = self._gpend(t.get("urno"))
            time_str = fmt_hhmm(m) if m > 0 else "—"
            status_str = f" [{p.upper()}]" if p else ""
            lines.append(f"  {pno}  {time_str}{status_str}\n    {t.get('shortinfo', '?')[:34]}")
        if not self._askdialog("Tag abschliessen", "Zeiten übertragen:\n\n" + "\n".join(lines) + f"\n\nGesamt: {fmt_hhmm(tot)}\n\nJetzt?"): return
        for t, m in enr:
            u = t.get("urno")
            if u in qt_pending and self._gm(u) == 0:
                now = time.time(); mins = qt_pending[u]
                self._ap(u, now - mins*60, now, mins)
        ok, er = [], []
        for t, m in enr:
            u = t.get("urno"); sc = t.get("service_code") or {}; sc_u = (sc.get("urno") if isinstance(sc, dict) else sc) or t.get("urno_service_code")
            proj = t.get("project") or {}; pno = proj.get("projectno", "?"); desc = self._gd(u) or None
            fd = (t.get("from_datetime") or "")[:10]
            ud = (t.get("until_datetime") or "")[:10]
            u_urno = t.get("urno")
            if u_urno in self._force_today: bd = today_str()
            elif ud and ud >= today_str(): bd = today_str()
            elif ud and ud < today_str(): bd = ud
            else: bd = today_str()
            if m > 0:
                pl = {"urno_person":self.person_urno, "urno_project":proj.get("urno"), "urno_task":u, "urno_service_code":sc_u, "from_date":bd, "input":min_to_h(m), "chargeable":1}
                if desc: pl["description"] = desc
                try:
                    r = requests.post(f"{PROAD_URL}/timeregs", headers=self.hdr, json=pl, timeout=20, verify=SSL_VERIFY)
                    if r.ok:
                        ok.append(pno); self._booked_today.add(str(u)); self.data.setdefault("booked_today", {}).setdefault(today_str(), [])
                        if u not in self.data["booked_today"][today_str()]: self.data["booked_today"][today_str()].append(u)
                    else: er.append(f"{pno}: {r.text[:80]}")
                except Exception as ex: er.append(f"{pno}: {str(ex)[:60]}")
            else:
                # Status-only Todo: keine Zeit zu buchen, aber "✓ übertragen" muss trotzdem erscheinen
                ok.append(pno); self._booked_today.add(str(u))
                self.data.setdefault("booked_today", {}).setdefault(today_str(), [])
                if u not in self.data["booked_today"][today_str()]:
                    self.data["booked_today"][today_str()].append(u)
        save_data(self.data)
        def push():
            for t, m in enr:
                u = t.get("urno")
                p = self._gpend(u)
                q = u in self._quick_track
                h_left = t.get("hours_left") or 0
                h_book = min_to_h(m)
                if p == "erledigt": self._push_status(u, "erledigt")
                elif p == "wartet": self._push_status(u, "wartet")
                elif q:
                    if h_left <= 0 or h_book >= h_left * 0.99: self._push_status(u, "erledigt")
                    else: self._push_status(u, "begonnen")
                self._quick_track.discard(u)
                self._spend(u, None)
                self._force_today.discard(u)
                self.data.setdefault("quick_hours", {}).pop(str(u), None)
        threading.Thread(target=push, daemon=True).start()
        self._render_list(); self._draw_timer_block()
        if er:
            self._dialog("Teilerfolg", f"OK: {', '.join(ok)}\nFehler:\n" + "\n".join(er), "warn")
        else:
            _play_success_sound()
            self._dialog("Übertragen!", f"Alle {len(ok)} Einträge übertragen.", "ok")

    def _dlg_pos(self, d):
        d.update_idletasks()
        dw, dh = d.winfo_reqwidth(), d.winfo_reqheight()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        x = rx + (rw - dw) // 2
        y = ry + (rh - dh) // 2
        d.geometry(f"+{x}+{y}")

    def _dialog(self, title, msg, kind="info"):
        d = tk.Toplevel(self.root); d.title(title); d.configure(bg=C["panel"]); d.resizable(False, False)
        d.transient(self.root); d.grab_set()
        col = {"info": C["accent"], "warn": C["orange"], "error": C["red"], "ok": C["green"]}.get(kind, C["accent"])
        f = tk.Frame(d, bg=C["panel"], padx=s(20), pady=s(14)); f.pack()
        tk.Label(f, text=msg, font=(FONT_MAIN, 11), bg=C["panel"], fg=C["text"], wraplength=s(280), justify="center").pack(pady=(0, s(12)))
        btn = tk.Label(f, text="OK", font=(FONT_MAIN, 11, "bold"), bg=col, fg=C["bg"], padx=s(20), pady=s(5), cursor="arrow"); btn.pack()
        btn.bind("<Button-1>", lambda e: d.destroy())
        d.bind("<Return>", lambda e: d.destroy()); d.bind("<Escape>", lambda e: d.destroy())
        self._dlg_pos(d); d.focus_set(); d.wait_window()

    def _askdialog(self, title, msg):
        result = [False]
        d = tk.Toplevel(self.root); d.title(title); d.configure(bg=C["panel"]); d.resizable(False, False)
        d.transient(self.root); d.grab_set()
        f = tk.Frame(d, bg=C["panel"], padx=s(20), pady=s(14)); f.pack()
        tk.Label(f, text=msg, font=(FONT_MAIN, 11), bg=C["panel"], fg=C["text"], wraplength=s(300), justify="center").pack(pady=(0, s(14)))
        bf = tk.Frame(f, bg=C["panel"]); bf.pack()
        no_b = tk.Label(bf, text="Nein", font=(FONT_MAIN, 11), bg=C["gray_btn"], fg=C["text"], padx=s(16), pady=s(5), cursor="arrow"); no_b.pack(side="left", padx=(0, s(8)))
        yes_b = tk.Label(bf, text="Ja", font=(FONT_MAIN, 11, "bold"), bg=C["accent"], fg=C["bg"], padx=s(16), pady=s(5), cursor="arrow"); yes_b.pack(side="left")
        def _yes(): result[0] = True; d.destroy()
        yes_b.bind("<Button-1>", lambda e: _yes()); no_b.bind("<Button-1>", lambda e: d.destroy())
        d.bind("<Return>", lambda e: _yes()); d.bind("<Escape>", lambda e: d.destroy())
        self._dlg_pos(d); d.focus_set(); d.wait_window()
        return result[0]

    def run(self): self.root.mainloop()


def _play_success_sound():
    try:
        if IS_WIN:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        else:
            os.system("afplay /System/Library/Sounds/Funk.aiff &")
    except Exception:
        pass


def main():
    data = load_data(); config = data.get("config", {})
    if not config.get("api_key") or not config.get("person_urno"):
        s = SetupWindow(); result = s.run()
        if not result: return
        config = result
    if not POPOVER_MODE:
        write_ipc({"mode":"big", "visible_state":"big_open", "ts":time.time()})
    tracker = FPXTimeTracker(config)
    tracker.run()
    if not POPOVER_MODE:
        write_ipc({"mode":"popover", "visible_state":"hidden", "ts":time.time()})


if __name__ == "__main__":
    main()
