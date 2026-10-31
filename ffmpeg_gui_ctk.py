#!/usr/bin/env python3
"""
FFmpeg GUI (CustomTkinter) / Interfaz para ffmpeg

EN: Detects ffmpeg formats, codecs and plugins and runs the conversion in the
    native terminal of your operating system. UI language: English / Spanish
    (auto-detected from the system, English by default).
ES: Detecta formatos, códecs y plugins de ffmpeg y ejecuta la conversión en la
    terminal nativa del sistema operativo. Idioma: inglés / español
    (se detecta del sistema, inglés por defecto).

Requirements / Requisitos: Python 3.8+, ffmpeg in PATH, and:  pip install customtkinter
"""
import json
import locale
import os
import platform
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    sys.exit("customtkinter is missing / Falta customtkinter.\n"
             "Install it / Instálalo:  pip install customtkinter")

SEP = " — "

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


# --------------------------------------------------------------------------
# Idiomas / Languages
# --------------------------------------------------------------------------
LANGS = {"en": "English", "es": "Español"}
LANG = "en"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".ffmpeg_gui.json")

STRINGS = {
    "en": {
        "app_title": "FFmpeg GUI",
        # barra superior
        "choose_ffmpeg": "Choose ffmpeg...",
        "diagnostics": "Diagnostics",
        "rescan": "Rescan",
        "theme_system": "System", "theme_dark": "Dark", "theme_light": "Light",
        # pestañas
        "tab_convert": "Convert", "tab_out": "Output formats", "tab_in": "Input formats",
        "tab_codecs": "Codecs", "tab_plugins": "Plugins", "tab_build": "Build",
        # tablas
        "search": "Search:",
        "h_format": "Format", "h_desc": "Description", "h_type": "Type", "h_flags": "Flags",
        "h_encoder": "Encoder", "h_encoder_lib": "Encoder (external lib)",
        "h_build": "Option enabled in this ffmpeg build",
        # pestaña convertir
        "l_input": "Input file:", "browse": "Browse...",
        "l_format": "Output format:", "l_vcodec": "Video codec:", "l_acodec": "Audio codec:",
        "l_extra": "Extra options:",
        "l_output": "Output file:", "save_as": "Save as...",
        "chk_overwrite": "Overwrite if it exists (-y)",
        "chk_terminal": "Run in the system terminal ({os})",
        "l_command": "Command:", "btn_show": "Show command", "btn_convert": "Convert",
        "auto": "(automatic)", "out_suffix": "_converted",
        # selectores
        "pk_format": "Output format", "pk_video": "Video codec", "pk_audio": "Audio codec",
        "pk_empty": "  Nothing loaded. Press 'Diagnostics' in the main window.",
        # diálogos de archivo
        "dlg_ffmpeg": "Select the ffmpeg executable", "dlg_input": "Input file",
        "dlg_output": "Output file",
        # estado
        "st_search": "Looking for ffmpeg...",
        "st_notfound": "ffmpeg not found in PATH.",
        "st_analyzing": "Analyzing ffmpeg...",
        "st_loaded": "{version}  |  OS: {os}  |  {mux} output, {dem} input, {enc} encoders",
        "st_format": "{version}  |  Format {name}: ext .{ext}, default video: {vc}, default audio: {ac}",
        "st_error": "Error loading ffmpeg (see details).",
        # mensajes
        "mb_notfound_title": "ffmpeg not found",
        "mb_notfound_body": "Install ffmpeg or use 'Choose ffmpeg...' to point to its location.",
        "mb_loaderr_title": "Error loading ffmpeg",
        "mb_noformats_title": "No formats detected",
        "mb_missing_title": "Missing data",
        "mb_diag_title": "Diagnostics",
        "diag_notloaded": "ffmpeg not loaded.\nPATH lookup: {path}\nLast error: {err}",
        "diag_text": ("Path: {path}\n{version}\nPython {py} on {plat}\n"
                      "Output formats: {mux} | input: {dem} | encoders: {enc}\n"
                      "Last error: {err}\n\nFirst lines of 'ffmpeg -formats':\n{head}"),
        "diag_none": "none", "diag_empty": "(empty output)", "unknown": "unknown",
        # errores de validación
        "err_not_loaded": "ffmpeg is not loaded.",
        "err_input": "Select a valid input file.",
        "err_output": "Specify the output file.",
        "err_format": "Select an output format.",
        "err_same": "The output cannot be the same file as the input.",
        # registro / terminal
        "log_terminal": "[{os}] {msg}\n",
        "log_fallback": "{msg} It will run inside this window.\n",
        "log_exit": "\n[ffmpeg exited with code {code}]\n",
        "log_error": "Error: {e}\n",
        "term_used": "Terminal: {name}",
        "term_none": "No terminal emulator was found.",
        "term_unsupported": "Unsupported system: {os}",
        "term_error": "Could not open the terminal: {e}",
        "term_done": "Done. Press Enter to close...",
        "gui_error": "Could not start the graphical interface: {e}",
        "capture_empty": "No output from: {cmd} (code {code})",
        "capture_fail": "{etype}: {e} while running: {cmd}",
    },
    "es": {
        "app_title": "FFmpeg GUI",
        "choose_ffmpeg": "Elegir ffmpeg...",
        "diagnostics": "Diagnóstico",
        "rescan": "Reanalizar",
        "theme_system": "Sistema", "theme_dark": "Oscuro", "theme_light": "Claro",
        "tab_convert": "Convertir", "tab_out": "Formatos de salida", "tab_in": "Formatos de entrada",
        "tab_codecs": "Códecs", "tab_plugins": "Plugins", "tab_build": "Build",
        "search": "Buscar:",
        "h_format": "Formato", "h_desc": "Descripción", "h_type": "Tipo", "h_flags": "Flags",
        "h_encoder": "Encoder", "h_encoder_lib": "Encoder (lib externa)",
        "h_build": "Opción habilitada en el build de ffmpeg",
        "l_input": "Archivo de entrada:", "browse": "Examinar...",
        "l_format": "Formato de salida:", "l_vcodec": "Códec de video:", "l_acodec": "Códec de audio:",
        "l_extra": "Opciones extra:",
        "l_output": "Archivo de salida:", "save_as": "Guardar como...",
        "chk_overwrite": "Sobrescribir si existe (-y)",
        "chk_terminal": "Ejecutar en la terminal del sistema ({os})",
        "l_command": "Comando:", "btn_show": "Ver comando", "btn_convert": "Convertir",
        "auto": "(automático)", "out_suffix": "_convertido",
        "pk_format": "Formato de salida", "pk_video": "Códec de video", "pk_audio": "Códec de audio",
        "pk_empty": "  No hay elementos cargados. Pulsa 'Diagnóstico' en la ventana principal.",
        "dlg_ffmpeg": "Selecciona el ejecutable de ffmpeg", "dlg_input": "Archivo de entrada",
        "dlg_output": "Archivo de salida",
        "st_search": "Buscando ffmpeg...",
        "st_notfound": "ffmpeg no encontrado en el PATH.",
        "st_analyzing": "Analizando ffmpeg...",
        "st_loaded": "{version}  |  OS: {os}  |  {mux} salida, {dem} entrada, {enc} encoders",
        "st_format": "{version}  |  Formato {name}: ext .{ext}, video por defecto: {vc}, audio por defecto: {ac}",
        "st_error": "Error al cargar ffmpeg (ver detalles).",
        "mb_notfound_title": "ffmpeg no encontrado",
        "mb_notfound_body": "Instala ffmpeg o usa 'Elegir ffmpeg...' para indicar su ubicación.",
        "mb_loaderr_title": "Error al cargar ffmpeg",
        "mb_noformats_title": "No se detectaron formatos",
        "mb_missing_title": "Faltan datos",
        "mb_diag_title": "Diagnóstico",
        "diag_notloaded": "ffmpeg no cargado.\nBúsqueda en PATH: {path}\nÚltimo error: {err}",
        "diag_text": ("Ruta: {path}\n{version}\nPython {py} en {plat}\n"
                      "Formatos salida: {mux} | entrada: {dem} | encoders: {enc}\n"
                      "Último error: {err}\n\nPrimeras líneas de 'ffmpeg -formats':\n{head}"),
        "diag_none": "ninguno", "diag_empty": "(salida vacía)", "unknown": "desconocida",
        "err_not_loaded": "ffmpeg no está cargado.",
        "err_input": "Selecciona un archivo de entrada válido.",
        "err_output": "Indica el archivo de salida.",
        "err_format": "Selecciona un formato de salida.",
        "err_same": "La salida no puede ser el mismo archivo que la entrada.",
        "log_terminal": "[{os}] {msg}\n",
        "log_fallback": "{msg} Se ejecutará dentro de la ventana.\n",
        "log_exit": "\n[ffmpeg terminó con código {code}]\n",
        "log_error": "Error: {e}\n",
        "term_used": "Terminal: {name}",
        "term_none": "No se encontró ningún emulador de terminal.",
        "term_unsupported": "Sistema no soportado: {os}",
        "term_error": "Error al abrir la terminal: {e}",
        "term_done": "Terminado. Presiona Enter para cerrar...",
        "gui_error": "No se pudo iniciar la interfaz gráfica: {e}",
        "capture_empty": "Sin salida de: {cmd} (código {code})",
        "capture_fail": "{etype}: {e} al ejecutar: {cmd}",
    },
}


def t(key, **kw):
    """Traduce una clave al idioma actual (con inglés como respaldo)."""
    s = STRINGS.get(LANG, {}).get(key)
    if s is None:
        s = STRINGS["en"].get(key, key)
    return s.format(**kw) if kw else s


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(**updates):
    cfg = load_config()
    cfg.update(updates)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except OSError:
        pass


def _code_from_locale_string(value):
    """'es_CL.UTF-8' -> 'es' | 'en' | 'other'. None si está vacío o es C/POSIX."""
    if not value:
        return None
    first = value.split(":")[0].strip()
    if not first or first.upper() in ("C", "POSIX") or first.upper().startswith("C."):
        return None
    low = first.lower()
    if low.startswith("spanish"):
        return "es"
    if low.startswith("english"):
        return "en"
    code = re.split(r"[_\-.@]", low)[0]
    return code if code in LANGS else "other"


def detect_system_language():
    """Devuelve 'es' o 'en' según el idioma del sistema; 'en' si es otro."""
    try:
        if os.name == "nt":
            import ctypes
            primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            return {0x0A: "es", 0x09: "en"}.get(primary, "en")
        if sys.platform == "darwin":
            out = capture(["defaults", "read", "-g", "AppleLanguages"], timeout=5)
            for line in out.splitlines():
                code = _code_from_locale_string(line.strip().strip('(),"').strip())
                if code:
                    return code if code in LANGS else "en"
    except Exception:
        pass
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        code = _code_from_locale_string(os.environ.get(var, ""))
        if code:
            return code if code in LANGS else "en"
    try:
        code = _code_from_locale_string(locale.getlocale()[0] or "")
        if code:
            return code if code in LANGS else "en"
    except Exception:
        pass
    return "en"


# --------------------------------------------------------------------------
# Detección de ffmpeg
# --------------------------------------------------------------------------
LAST_ERROR = ""


def capture(args, timeout=120):
    """Ejecuta un comando y devuelve stdout (o stderr si stdout está vacío)."""
    global LAST_ERROR
    cmd_txt = " ".join(map(str, args))
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace", **kw)
        out = r.stdout if r.stdout.strip() else r.stderr
        if not out.strip():
            LAST_ERROR = t("capture_empty", cmd=cmd_txt, code=r.returncode)
        return out
    except (OSError, subprocess.SubprocessError) as e:
        LAST_ERROR = t("capture_fail", etype=type(e).__name__, e=e, cmd=cmd_txt)
        return ""


class FFmpegInfo:
    def __init__(self, path):
        self.path = path
        self.version = ""
        self.config = ""
        self.libs = []        # --enable-xxx (plugins/librerías externas)
        self.muxers = []      # (nombre, descripción)  -> salida
        self.demuxers = []    # (nombre, descripción)  -> entrada
        self.encoders = []    # (tipo, flags, nombre, descripción)
        self.decoders = []
        self.raw_formats = ""
        self._ext_cache = {}
        self.refresh()

    def refresh(self):
        ver = capture([self.path, "-hide_banner", "-version"])
        lines = ver.splitlines()
        self.version = lines[0] if lines else "?"
        self.config = next((l for l in lines if l.startswith("configuration:")), "")
        self.libs = sorted(set(re.findall(r"--enable-([\w\-]+)", self.config)))

        self.raw_formats = capture([self.path, "-hide_banner", "-formats"])
        self.muxers, self.demuxers = self._parse_formats(self.raw_formats)
        if not self.muxers:   # alternativa si -formats no se pudo interpretar
            self.muxers = self._parse_formats(
                capture([self.path, "-hide_banner", "-muxers"]))[0]
        if not self.demuxers:
            self.demuxers = self._parse_formats(
                capture([self.path, "-hide_banner", "-demuxers"]))[1]
        self.encoders = self._parse_codecs(
            capture([self.path, "-hide_banner", "-encoders"]))
        self.decoders = self._parse_codecs(
            capture([self.path, "-hide_banner", "-decoders"]))
        self._ext_cache.clear()

    def _parse_formats(self, text):
        """Tolerante: no depende de la cabecera y acepta flags 'DE', ' E', 'D ', 'D.', '.E'."""
        mux, demux = [], []
        for line in text.splitlines():
            m = re.match(r"^\s*([D.\s])([E.\s])\s+(\S+)(?:\s+(\S.*))?\s*$", line)
            if not m:
                continue
            d, e, name, desc = m.groups()
            if name == "=" or (d != "D" and e != "E"):
                continue  # línea de leyenda o sin flags
            if e == "E":
                mux.append((name, (desc or "").strip()))
            if d == "D":
                demux.append((name, (desc or "").strip()))
        return mux, demux

    def _parse_codecs(self, text):
        out = []
        for line in text.splitlines():
            m = re.match(r"^\s*([VASDT])([.A-Za-z]{4,8})\s+(\S+)(?:\s+(\S.*))?\s*$", line)
            if m and m.group(3) != "=":
                kind, flags, name, desc = m.groups()
                out.append((kind, flags, name, (desc or "").strip()))
        return out

    def diagnostic(self):
        head = "\n".join(self.raw_formats.splitlines()[:12]) or t("diag_empty")
        return t("diag_text", path=self.path, version=self.version,
                 py=platform.python_version(), plat=platform.platform(),
                 mux=len(self.muxers), dem=len(self.demuxers), enc=len(self.encoders),
                 err=LAST_ERROR or t("diag_none"), head=head)

    def muxer_details(self, name):
        """Extensión y códecs por defecto de un muxer (se consulta bajo demanda)."""
        if name in self._ext_cache:
            return self._ext_cache[name]
        txt = capture([self.path, "-hide_banner", "-h", f"muxer={name}"])
        ext = ""
        m = re.search(r"Common extensions:\s*([^\n]+)", txt)
        if m:
            ext = m.group(1).strip().rstrip(".").split(",")[0].strip()
        vc = re.search(r"Default video codec:\s*([^\s.]+)", txt)
        ac = re.search(r"Default audio codec:\s*([^\s.]+)", txt)
        info = {
            "ext": ext or name,
            "vcodec": vc.group(1) if vc else "",
            "acodec": ac.group(1) if ac else "",
        }
        self._ext_cache[name] = info
        return info

    def encoder_items(self, kind):
        """Lista de (etiqueta, valor) para los selectores."""
        return [(f"{e[2]}{SEP}{e[3]}" if e[3] else e[2], e[2])
                for e in self.encoders if e[0] == kind]

    def external_encoders(self):
        """Encoders de librerías externas (plugins): libx264, libmp3lame..."""
        return [e for e in self.encoders if e[2].startswith("lib")]


# --------------------------------------------------------------------------
# Ejecución en la terminal según el sistema operativo
# --------------------------------------------------------------------------
LINUX_TERMINALS = [
    ("gnome-terminal", ["--"]),
    ("konsole", ["-e"]),
    ("xfce4-terminal", ["-x"]),
    ("mate-terminal", ["-x"]),
    ("terminator", ["-x"]),
    ("lxterminal", ["-e"]),
    ("alacritty", ["-e"]),
    ("kitty", []),
    ("foot", []),
    ("wezterm", ["start", "--"]),
    ("xterm", ["-e"]),
    ("x-terminal-emulator", ["-e"]),
]


def detect_os():
    s = platform.system()
    return {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}.get(s, s)


def run_in_terminal(cmd):
    """Abre la terminal nativa del OS y ejecuta cmd (lista). Devuelve (ok, mensaje)."""
    system = detect_os()
    try:
        if system == "Windows":
            line = subprocess.list2cmdline(cmd)
            subprocess.Popen(f"cmd /k {line}",
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
            return True, t("term_used", name="cmd.exe")

        script = (shlex.join(cmd) +
                  f'; echo; echo "{t("term_done")}"; read _')

        if system == "macOS":
            esc = script.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.Popen(["osascript", "-e",
                              f'tell application "Terminal" to do script "{esc}"',
                              "-e", 'tell application "Terminal" to activate'])
            return True, t("term_used", name="Terminal.app")

        if system == "Linux":
            candidates = []
            env_term = os.environ.get("TERMINAL")
            if env_term and shutil.which(env_term.split()[0]):
                candidates.append((env_term.split()[0], ["-e"]))
            candidates += LINUX_TERMINALS
            for term, flags in candidates:
                exe = shutil.which(term)
                if exe:
                    subprocess.Popen([exe, *flags, "bash", "-c", script])
                    return True, t("term_used", name=term)
            return False, t("term_none")

        return False, t("term_unsupported", os=system)
    except OSError as e:
        return False, t("term_error", e=e)


# --------------------------------------------------------------------------
# Widgets personalizados
# --------------------------------------------------------------------------
class ListView(ctk.CTkFrame):
    """Tabla de solo lectura con buscador (CTkTextbox: rápida con cientos de filas)."""

    def __init__(self, master, headers, widths):
        super().__init__(master, fg_color="transparent")
        self.headers, self.widths = headers, widths
        self.rows = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=6, pady=(6, 4))
        ctk.CTkLabel(top, text=t("search")).pack(side="left", padx=(0, 8))
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self._fill())
        ctk.CTkEntry(top, textvariable=self.q).pack(side="left", fill="x", expand=True)
        self.count = ctk.CTkLabel(top, text="", width=90)
        self.count.pack(side="right", padx=(8, 0))

        self.box = ctk.CTkTextbox(self, wrap="none", font=ctk.CTkFont(family="Courier", size=12))
        self.box.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.box.configure(state="disabled")

    def _line(self, row):
        cells = [str(c).ljust(w) for c, w in zip(row[:-1], self.widths[:-1])]
        cells.append(str(row[-1]))
        return "  ".join(cells)

    def set_rows(self, rows):
        self.rows = rows
        self._fill()

    def _fill(self):
        q = self.q.get().lower().strip()
        shown = [r for r in self.rows if not q or any(q in str(x).lower() for x in r)]
        text = [self._line(self.headers), "-" * 80]
        text += [self._line(r) for r in shown]
        self.box.configure(state="normal")
        self.box.delete("1.0", "end")
        self.box.insert("1.0", "\n".join(text))
        self.box.configure(state="disabled")
        self.count.configure(text=f"{len(shown)} / {len(self.rows)}")


class Picker(ctk.CTkToplevel):
    """Ventana de selección con buscador. items = lista de (etiqueta, valor)."""

    def __init__(self, master, title, items, on_select):
        super().__init__(master)
        self.title(title)
        self.geometry("560x480")
        self.transient(master)
        self.items, self.on_select = items, on_select
        self.visible = []

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(top, text=t("search")).pack(side="left", padx=(0, 8))
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.fill())
        self.entry = ctk.CTkEntry(top, textvariable=self.q)
        self.entry.pack(side="left", fill="x", expand=True)

        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        dark = ctk.get_appearance_mode() == "Dark"
        self.lb = tk.Listbox(
            frame, activestyle="none", borderwidth=0, highlightthickness=0,
            bg="#2b2b2b" if dark else "#f2f2f2", fg="#ffffff" if dark else "#1a1a1a",
            selectbackground="#1f6aa5", selectforeground="#ffffff",
            font=("TkDefaultFont", 11))
        sb = ctk.CTkScrollbar(frame, command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 2), pady=4)
        self.lb.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)

        self.lb.bind("<Double-Button-1>", self.choose)
        self.lb.bind("<Return>", self.choose)
        self.entry.bind("<Return>", self.choose)
        self.entry.bind("<Down>", lambda _e: self.lb.focus_set())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.fill()
        self.after(150, self._focus)

    def _focus(self):
        try:
            self.lift()
            self.grab_set()
            self.entry.focus_set()
        except tk.TclError:
            pass

    def fill(self):
        q = self.q.get().lower().strip()
        self.lb.delete(0, "end")
        self.visible = []
        if not self.items:
            self.lb.insert("end", t("pk_empty"))
            return
        for label, value in self.items:
            if not q or q in label.lower():
                self.lb.insert("end", label)
                self.visible.append(value)
        if self.visible:
            self.lb.selection_set(0)

    def choose(self, _e=None):
        sel = self.lb.curselection()
        if not sel or not self.visible:
            return
        value = self.visible[sel[0]]
        self.destroy()
        self.on_select(value)


class PickerButton(ctk.CTkButton):
    """Botón que muestra la opción actual y abre un Picker con buscador.

    Guarda el *valor* (no el texto mostrado), así el idioma puede cambiar sin
    perder la selección. allow_auto: el valor "" significa '(automático)'.
    """

    def __init__(self, master, title, on_change=None, allow_auto=False, **kw):
        super().__init__(master, text="", anchor="w", command=self._open,
                         fg_color=("#e5e5e5", "#343638"), text_color=("#1a1a1a", "#ffffff"),
                         hover_color=("#d0d0d0", "#444648"), **kw)
        self.title_, self.on_change, self.allow_auto = title, on_change, allow_auto
        self.items, self.value = [], ""
        self._refresh_text()

    def set_items(self, items):
        self.items = items
        self._refresh_text()

    def set(self, value):
        self.value = value
        self._refresh_text()

    def get(self):
        return self.value

    def _label(self):
        for label, value in self.items:
            if value == self.value:
                return label
        if self.value == "" and self.allow_auto:
            return t("auto")
        return self.value

    def _refresh_text(self):
        label = self._label()
        self.configure(text=label if len(label) < 70 else label[:67] + "...")

    def _open(self):
        if not self.items:
            reload_fn = getattr(self.winfo_toplevel(), "load_ffmpeg", None)
            if reload_fn:
                reload_fn()
        Picker(self.winfo_toplevel(), self.title_, self.items, self._picked)

    def _picked(self, value):
        self.set(value)
        if self.on_change:
            self.on_change()


# --------------------------------------------------------------------------
# Aplicación
# --------------------------------------------------------------------------
THEME_MODES = ["System", "Dark", "Light"]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        global LANG
        cfg = load_config()
        LANG = cfg.get("lang") if cfg.get("lang") in LANGS else detect_system_language()

        self.title(t("app_title"))
        self.geometry("960x720")
        self.minsize(800, 600)

        self.os_name = detect_os()
        self.info = None
        self.log_q = queue.Queue()
        self.theme_mode = "System"
        self._status = ("st_search", {})

        # variables que sobreviven al cambio de idioma
        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.extra_var = tk.StringVar()
        self.overwrite = tk.BooleanVar(value=True)
        self.use_term = tk.BooleanVar(value=True)

        self.root_frame = None
        self._build_ui()
        self.set_status("st_search")
        self.after(100, self._poll_log)
        self.after(200, self.load_ffmpeg)

    # ---------- construcción ----------
    def _tab_names(self):
        return [t("tab_convert"), t("tab_out"), t("tab_in"),
                t("tab_codecs"), t("tab_plugins"), t("tab_build")]

    def _build_ui(self):
        if self.root_frame is not None:
            self.root_frame.destroy()
        self.root_frame = root = ctk.CTkFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True)

        top = ctk.CTkFrame(root, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        self.lang_menu = ctk.CTkOptionMenu(
            top, values=list(LANGS.values()), width=110, command=self.set_language)
        self.lang_menu.set(LANGS[LANG])
        self.lang_menu.pack(side="right")
        theme_labels = [t("theme_system"), t("theme_dark"), t("theme_light")]
        self.theme_menu = ctk.CTkOptionMenu(
            top, values=theme_labels, width=100,
            command=lambda lbl: self.set_theme(theme_labels.index(lbl)))
        self.theme_menu.set(theme_labels[THEME_MODES.index(self.theme_mode)])
        self.theme_menu.pack(side="right", padx=8)
        ctk.CTkButton(top, text=t("rescan"), width=90,
                      command=self.load_ffmpeg).pack(side="left")
        ctk.CTkButton(top, text=t("choose_ffmpeg"), width=130,
                      command=self.pick_ffmpeg).pack(side="left", padx=8)
        ctk.CTkButton(top, text=t("diagnostics"), width=110,
                      command=self.show_diag).pack(side="left")

        self.status = ctk.CTkLabel(root, text="", anchor="w", justify="left", wraplength=900)
        self.status.pack(fill="x", padx=12, pady=(0, 4))

        self.tabs = ctk.CTkTabview(root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        names = self._tab_names()
        for name in names:
            self.tabs.add(name)

        self.tab_mux = ListView(self.tabs.tab(names[1]),
                                (t("h_format"), t("h_desc")), (22, 60))
        self.tab_dem = ListView(self.tabs.tab(names[2]),
                                (t("h_format"), t("h_desc")), (22, 60))
        self.tab_enc = ListView(self.tabs.tab(names[3]),
                                (t("h_type"), t("h_flags"), t("h_encoder"), t("h_desc")),
                                (5, 7, 22, 60))
        self.tab_plug = ListView(self.tabs.tab(names[4]),
                                 (t("h_type"), t("h_encoder_lib"), t("h_desc")), (5, 24, 60))
        self.tab_lib = ListView(self.tabs.tab(names[5]), (t("h_build"),), (60,))
        for w in (self.tab_mux, self.tab_dem, self.tab_enc, self.tab_plug, self.tab_lib):
            w.pack(fill="both", expand=True)

        self._build_convert_tab(self.tabs.tab(names[0]))

    def _build_convert_tab(self, f):
        f.columnconfigure(1, weight=1)

        def label(text, row):
            ctk.CTkLabel(f, text=text, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(6, 10), pady=6)

        r = 0
        label(t("l_input"), r)
        ctk.CTkEntry(f, textvariable=self.in_var).grid(row=r, column=1, sticky="ew", pady=6)
        ctk.CTkButton(f, text=t("browse"), width=120, command=self.pick_input).grid(
            row=r, column=2, padx=6)

        r += 1
        label(t("l_format"), r)
        self.fmt_btn = PickerButton(f, t("pk_format"), on_change=self.on_format_change)
        self.fmt_btn.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        label(t("l_vcodec"), r)
        self.vc_btn = PickerButton(f, t("pk_video"), allow_auto=True)
        self.vc_btn.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        label(t("l_acodec"), r)
        self.ac_btn = PickerButton(f, t("pk_audio"), allow_auto=True)
        self.ac_btn.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        label(t("l_extra"), r)
        ctk.CTkEntry(f, textvariable=self.extra_var).grid(
            row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        label(t("l_output"), r)
        ctk.CTkEntry(f, textvariable=self.out_var).grid(row=r, column=1, sticky="ew", pady=6)
        ctk.CTkButton(f, text=t("save_as"), width=120, command=self.pick_output).grid(
            row=r, column=2, padx=6)

        r += 1
        opts = ctk.CTkFrame(f, fg_color="transparent")
        opts.grid(row=r, column=0, columnspan=3, sticky="w", padx=6, pady=4)
        ctk.CTkCheckBox(opts, text=t("chk_overwrite"),
                        variable=self.overwrite).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(opts, text=t("chk_terminal", os=self.os_name),
                        variable=self.use_term).pack(side="left")

        r += 1
        label(t("l_command"), r)
        self.cmd_txt = ctk.CTkTextbox(f, height=70, wrap="word")
        self.cmd_txt.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.grid(row=r, column=0, columnspan=3, pady=6)
        ctk.CTkButton(btns, text=t("btn_show"), width=140, fg_color="transparent",
                      border_width=2, text_color=("#1a1a1a", "#ffffff"),
                      command=self.show_command).pack(side="left", padx=8)
        ctk.CTkButton(btns, text=t("btn_convert"), width=140, command=self.run).pack(
            side="left", padx=8)

        r += 1
        f.rowconfigure(r, weight=1)
        self.log = ctk.CTkTextbox(f, height=120, wrap="none", state="disabled")
        self.log.grid(row=r, column=0, columnspan=3, sticky="nsew", padx=6, pady=(4, 6))

    # ---------- idioma y tema ----------
    def set_status(self, key, **kw):
        self._status = (key, kw)
        self.status.configure(text=t(key, **kw))

    def set_theme(self, index):
        self.theme_mode = THEME_MODES[index]
        ctk.set_appearance_mode(self.theme_mode)

    def set_language(self, label):
        global LANG
        code = next((k for k, v in LANGS.items() if v == label), None)
        if not code or code == LANG:
            return
        LANG = code
        save_config(lang=code)
        self.rebuild_ui()

    def rebuild_ui(self):
        """Reconstruye la interfaz en el nuevo idioma conservando el estado."""
        try:
            tab_idx = self._current_tab_index()
        except Exception:
            tab_idx = 0
        saved = {
            "fmt": self.fmt_btn.get(), "vc": self.vc_btn.get(), "ac": self.ac_btn.get(),
            "cmd": self.cmd_txt.get("1.0", "end-1c"), "log": self.log.get("1.0", "end-1c"),
        }
        self._build_ui()
        self._populate()
        self.fmt_btn.set(saved["fmt"])
        self.vc_btn.set(saved["vc"])
        self.ac_btn.set(saved["ac"])
        self.cmd_txt.insert("1.0", saved["cmd"])
        if saved["log"]:
            self.log_write(saved["log"])
        try:
            self.tabs.set(self._tab_names()[tab_idx])
        except Exception:
            pass
        self.set_status(self._status[0], **self._status[1])

    def _current_tab_index(self):
        # el nombre actual está en el idioma anterior: se busca por posición
        current = self.tabs.get()
        for lang in LANGS:
            names = [STRINGS[lang][k] for k in
                     ("tab_convert", "tab_out", "tab_in", "tab_codecs", "tab_plugins", "tab_build")]
            if current in names:
                return names.index(current)
        return 0

    # ---------- carga de ffmpeg ----------
    def pick_ffmpeg(self):
        p = filedialog.askopenfilename(title=t("dlg_ffmpeg"))
        if p:
            self.load_ffmpeg(p)

    def show_diag(self):
        if self.info:
            messagebox.showinfo(t("mb_diag_title"), self.info.diagnostic())
        else:
            messagebox.showinfo(
                t("mb_diag_title"),
                t("diag_notloaded", path=shutil.which("ffmpeg"),
                  err=LAST_ERROR or t("diag_none")))

    def load_ffmpeg(self, path=None):
        try:
            self._load_ffmpeg(path)
        except Exception:
            import traceback
            self.set_status("st_error")
            messagebox.showerror(t("mb_loaderr_title"), traceback.format_exc()[-1500:])

    def _populate(self):
        """Rellena selectores y listas con la información de ffmpeg ya analizada."""
        i = self.info
        if not i:
            return
        # 1) selectores de la pestaña Convertir (lo más importante)
        self.fmt_btn.set_items(
            [(f"{n}{SEP}{d}" if d else n, n) for n, d in i.muxers])
        head = [(t("auto"), ""), ("copy", "copy")]
        self.vc_btn.set_items(head + i.encoder_items("V"))
        self.ac_btn.set_items(head + i.encoder_items("A"))
        # 2) listas informativas
        for tab, rows in (
            (self.tab_mux, i.muxers),
            (self.tab_dem, i.demuxers),
            (self.tab_enc, list(i.encoders)),
            (self.tab_plug, [(k, n, d) for k, _f, n, d in i.external_encoders()]),
            (self.tab_lib, [(lib,) for lib in i.libs]),
        ):
            tab.set_rows(rows)

    def _load_ffmpeg(self, path=None):
        if not isinstance(path, str):
            path = self.info.path if self.info else shutil.which("ffmpeg")
        if not path:
            self.set_status("st_notfound")
            messagebox.showerror(t("mb_notfound_title"), t("mb_notfound_body"))
            return
        self.set_status("st_analyzing")
        self.update_idletasks()
        self.info = i = FFmpegInfo(path)

        self._populate()
        self.vc_btn.set("")
        self.ac_btn.set("")
        self.set_status("st_loaded", version=i.version, os=self.os_name,
                        mux=len(i.muxers), dem=len(i.demuxers), enc=len(i.encoders))
        if i.muxers and not self.fmt_btn.get():
            names = [n for n, _d in i.muxers]
            self.fmt_btn.set("mp4" if "mp4" in names else names[0])
            self.on_format_change()
        if not i.muxers:
            self.after(400, lambda: messagebox.showwarning(
                t("mb_noformats_title"), i.diagnostic()))

    # ---------- acciones ----------
    def pick_input(self):
        p = filedialog.askopenfilename(title=t("dlg_input"))
        if p:
            self.in_var.set(p)
            self.update_output_name()

    def pick_output(self):
        p = filedialog.asksaveasfilename(title=t("dlg_output"),
                                         initialfile=os.path.basename(self.out_var.get()))
        if p:
            self.out_var.set(p)

    def on_format_change(self):
        name = self.fmt_btn.get()
        if not name or not self.info:
            return
        d = self.info.muxer_details(name)
        self.vc_btn.set("")
        self.ac_btn.set("")
        self.set_status("st_format", version=self.info.version, name=name, ext=d["ext"],
                        vc=d["vcodec"] or "-", ac=d["acodec"] or "-")
        self.update_output_name()

    def update_output_name(self):
        src, name = self.in_var.get(), self.fmt_btn.get()
        if not src or not name or not self.info:
            return
        ext = self.info.muxer_details(name)["ext"]
        base, _ = os.path.splitext(src)
        self.out_var.set(f"{base}{t('out_suffix')}.{ext}")

    def build_command(self):
        if not self.info:
            raise ValueError(t("err_not_loaded"))
        src, dst, fmt = self.in_var.get().strip(), self.out_var.get().strip(), self.fmt_btn.get()
        if not src or not os.path.isfile(src):
            raise ValueError(t("err_input"))
        if not dst:
            raise ValueError(t("err_output"))
        if not fmt:
            raise ValueError(t("err_format"))
        if os.path.abspath(src) == os.path.abspath(dst):
            raise ValueError(t("err_same"))

        cmd = [self.info.path, "-hide_banner", "-y" if self.overwrite.get() else "-n",
               "-i", src, "-f", fmt]
        if self.vc_btn.get():
            cmd += ["-c:v", self.vc_btn.get()]
        if self.ac_btn.get():
            cmd += ["-c:a", self.ac_btn.get()]
        extra = self.extra_var.get().strip()
        if extra:
            cmd += shlex.split(extra, posix=(self.os_name != "Windows"))
        cmd.append(dst)
        return cmd

    def show_command(self):
        try:
            cmd = self.build_command()
        except ValueError as e:
            messagebox.showwarning(t("mb_missing_title"), str(e))
            return None
        text = subprocess.list2cmdline(cmd) if self.os_name == "Windows" else shlex.join(cmd)
        self.cmd_txt.delete("1.0", "end")
        self.cmd_txt.insert("1.0", text)
        return cmd

    def run(self):
        cmd = self.show_command()
        if not cmd:
            return
        if self.use_term.get():
            ok, msg = run_in_terminal(cmd)
            if ok:
                self.log_write(t("log_terminal", os=self.os_name, msg=msg))
                return
            self.log_write(t("log_fallback", msg=msg))
        threading.Thread(target=self._run_inline, args=(cmd,), daemon=True).start()

    def _run_inline(self, cmd):
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
            for line in p.stdout:
                self.log_q.put(line)
            p.wait()
            self.log_q.put(t("log_exit", code=p.returncode))
        except OSError as e:
            self.log_q.put(t("log_error", e=e))

    # ---------- log ----------
    def log_write(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _poll_log(self):
        try:
            while True:
                self.log_write(self.log_q.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_log)


if __name__ == "__main__":
    try:
        App().mainloop()
    except tk.TclError as e:
        sys.exit(t("gui_error", e=e))
