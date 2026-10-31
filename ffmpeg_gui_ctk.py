#!/usr/bin/env python3
"""
FFmpeg GUI (CustomTkinter) - detecta formatos, códecs y plugins de ffmpeg y
ejecuta la conversión en la terminal propia del sistema operativo.

Requisitos: Python 3.8+, ffmpeg en el PATH y:  pip install customtkinter
"""
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
    sys.exit("Falta customtkinter. Instálalo con:  pip install customtkinter")

AUTO = "(automático)"
COPY = "copy"
SEP = " — "

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


# --------------------------------------------------------------------------
# Detección de ffmpeg
# --------------------------------------------------------------------------
LAST_ERROR = ""


def capture(args, timeout=120):
    """Ejecuta un comando y devuelve stdout (o stderr si stdout está vacío)."""
    global LAST_ERROR
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        r = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace", **kw)
        out = r.stdout if r.stdout.strip() else r.stderr
        if not out.strip():
            LAST_ERROR = f"Sin salida de: {' '.join(map(str, args))} (código {r.returncode})"
        return out
    except (OSError, subprocess.SubprocessError) as e:
        LAST_ERROR = f"{type(e).__name__}: {e} al ejecutar: {' '.join(map(str, args))}"
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
        self._ext_cache = {}
        self.refresh()

    def refresh(self):
        ver = capture([self.path, "-hide_banner", "-version"])
        lines = ver.splitlines()
        self.version = lines[0] if lines else "desconocida"
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
                mux.append((name, (desc or '').strip()))
            if d == "D":
                demux.append((name, (desc or '').strip()))
        return mux, demux

    def _parse_codecs(self, text):
        out = []
        for line in text.splitlines():
            m = re.match(r"^\s*([VASDT])([.A-Za-z]{4,8})\s+(\S+)(?:\s+(\S.*))?\s*$", line)
            if m and m.group(3) != "=":
                t, flags, name, desc = m.groups()
                out.append((t, flags, name, (desc or '').strip()))
        return out

    def diagnostic(self):
        head = "\n".join(self.raw_formats.splitlines()[:12]) or "(salida vacía)"
        return (f"Ruta: {self.path}\n{self.version}\n"
                f"Python {platform.python_version()} en {platform.platform()}\n"
                f"Formatos salida: {len(self.muxers)} | entrada: {len(self.demuxers)} | "
                f"encoders: {len(self.encoders)}\n"
                f"Último error: {LAST_ERROR or 'ninguno'}\n\n"
                f"Primeras líneas de 'ffmpeg -formats':\n{head}")

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
        return [f"{e[2]}{SEP}{e[3]}" for e in self.encoders if e[0] == kind]

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
            return True, "Terminal: cmd.exe"

        script = (shlex.join(cmd) +
                  '; echo; echo "Terminado. Presiona Enter para cerrar..."; read _')

        if system == "macOS":
            esc = script.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.Popen(["osascript", "-e",
                              f'tell application "Terminal" to do script "{esc}"',
                              "-e", 'tell application "Terminal" to activate'])
            return True, "Terminal: Terminal.app"

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
                    return True, f"Terminal: {term}"
            return False, "No se encontró ningún emulador de terminal."

        return False, f"Sistema no soportado: {system}"
    except OSError as e:
        return False, f"Error al abrir la terminal: {e}"


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
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self._fill())
        ctk.CTkEntry(top, textvariable=self.q, placeholder_text="Buscar...").pack(
            side="left", fill="x", expand=True)
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
    """Ventana de selección con buscador (evita menús desplegables gigantes)."""

    def __init__(self, master, title, items, on_select):
        super().__init__(master)
        self.title(title)
        self.geometry("560x480")
        self.transient(master)
        self.items, self.on_select = items, on_select

        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *_: self.fill())
        self.entry = ctk.CTkEntry(self, textvariable=self.q, placeholder_text="Buscar...")
        self.entry.pack(fill="x", padx=10, pady=(10, 6))

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
        if not self.items:
            self.lb.insert("end", "  No hay elementos cargados. Pulsa 'Diagnóstico' en la ventana principal.")
            return
        for it in self.items:
            if not q or q in it.lower():
                self.lb.insert("end", it)
        if self.lb.size():
            self.lb.selection_set(0)

    def choose(self, _e=None):
        sel = self.lb.curselection()
        if not sel or not self.items:
            return
        value = self.lb.get(sel[0])
        self.destroy()
        self.on_select(value)


class PickerButton(ctk.CTkButton):
    """Botón que muestra el valor actual y abre un Picker con buscador."""

    def __init__(self, master, title, on_change=None, **kw):
        super().__init__(master, text="", anchor="w", command=self._open,
                         fg_color=("#e5e5e5", "#343638"), text_color=("#1a1a1a", "#ffffff"),
                         hover_color=("#d0d0d0", "#444648"), **kw)
        self.title_, self.items, self.on_change, self.value = title, [], on_change, ""

    def set_items(self, items):
        self.items = items

    def set(self, value):
        self.value = value
        self.configure(text=value if len(value) < 70 else value[:67] + "...")

    def get(self):
        return self.value

    def key(self):
        return self.value.split(SEP)[0]

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
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FFmpeg GUI")
        self.geometry("960x720")
        self.minsize(800, 600)

        self.os_name = detect_os()
        self.info = None
        self.log_q = queue.Queue()

        self._build_ui()
        self.after(100, self._poll_log)
        self.after(200, self.load_ffmpeg)

    # ---------- construcción ----------
    def _build_ui(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))
        self.status = ctk.CTkLabel(top, text="Buscando ffmpeg...", anchor="w",
                                   justify="left", wraplength=560)
        self.status.pack(side="left", fill="x", expand=True)
        self.theme_menu = ctk.CTkOptionMenu(
            top, values=["System", "Dark", "Light"], width=100,
            command=lambda m: ctk.set_appearance_mode(m))
        self.theme_menu.pack(side="right")
        ctk.CTkButton(top, text="Reanalizar", width=90,
                      command=self.load_ffmpeg).pack(side="right", padx=8)
        ctk.CTkButton(top, text="Elegir ffmpeg...", width=120,
                      command=self.pick_ffmpeg).pack(side="right")
        ctk.CTkButton(top, text="Diagnóstico", width=100,
                      command=self.show_diag).pack(side="right", padx=8)

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for name in ("Convertir", "Formatos de salida", "Formatos de entrada",
                     "Códecs", "Plugins", "Build"):
            self.tabs.add(name)

        self.tab_mux = ListView(self.tabs.tab("Formatos de salida"),
                                ("Formato", "Descripción"), (22, 60))
        self.tab_dem = ListView(self.tabs.tab("Formatos de entrada"),
                                ("Formato", "Descripción"), (22, 60))
        self.tab_enc = ListView(self.tabs.tab("Códecs"),
                                ("Tipo", "Flags", "Encoder", "Descripción"), (5, 7, 22, 60))
        self.tab_plug = ListView(self.tabs.tab("Plugins"),
                                 ("Tipo", "Encoder (lib externa)", "Descripción"), (5, 24, 60))
        self.tab_lib = ListView(self.tabs.tab("Build"),
                                ("Opción habilitada en el build de ffmpeg",), (60,))
        for w in (self.tab_mux, self.tab_dem, self.tab_enc, self.tab_plug, self.tab_lib):
            w.pack(fill="both", expand=True)

        self._build_convert_tab(self.tabs.tab("Convertir"))

    def _build_convert_tab(self, f):
        f.columnconfigure(1, weight=1)

        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.extra_var = tk.StringVar()
        self.overwrite = tk.BooleanVar(value=True)
        self.use_term = tk.BooleanVar(value=True)

        def label(text, row, **kw):
            ctk.CTkLabel(f, text=text, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(6, 10), pady=6, **kw)

        r = 0
        label("Archivo de entrada:", r)
        ctk.CTkEntry(f, textvariable=self.in_var).grid(row=r, column=1, sticky="ew", pady=6)
        ctk.CTkButton(f, text="Examinar...", width=120, command=self.pick_input).grid(
            row=r, column=2, padx=6)

        r += 1
        label("Formato de salida:", r)
        self.fmt_btn = PickerButton(f, "Formato de salida", on_change=self.on_format_change)
        self.fmt_btn.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        label("Códec de video:", r)
        self.vc_btn = PickerButton(f, "Códec de video")
        self.vc_btn.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        label("Códec de audio:", r)
        self.ac_btn = PickerButton(f, "Códec de audio")
        self.ac_btn.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        label("Opciones extra:", r)
        ctk.CTkEntry(f, textvariable=self.extra_var,
                     placeholder_text="ej: -crf 23 -b:a 192k").grid(
            row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        label("Archivo de salida:", r)
        ctk.CTkEntry(f, textvariable=self.out_var).grid(row=r, column=1, sticky="ew", pady=6)
        ctk.CTkButton(f, text="Guardar como...", width=120, command=self.pick_output).grid(
            row=r, column=2, padx=6)

        r += 1
        opts = ctk.CTkFrame(f, fg_color="transparent")
        opts.grid(row=r, column=0, columnspan=3, sticky="w", padx=6, pady=4)
        ctk.CTkCheckBox(opts, text="Sobrescribir si existe (-y)",
                        variable=self.overwrite).pack(side="left", padx=(0, 20))
        self.term_chk = ctk.CTkCheckBox(opts, text="Ejecutar en la terminal del sistema",
                                        variable=self.use_term)
        self.term_chk.pack(side="left")

        r += 1
        label("Comando:", r)
        self.cmd_txt = ctk.CTkTextbox(f, height=70, wrap="word")
        self.cmd_txt.grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 6), pady=6)

        r += 1
        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.grid(row=r, column=0, columnspan=3, pady=6)
        ctk.CTkButton(btns, text="Ver comando", width=140, fg_color="transparent",
                      border_width=2, text_color=("#1a1a1a", "#ffffff"),
                      command=self.show_command).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="Convertir", width=140, command=self.run).pack(
            side="left", padx=8)

        r += 1
        f.rowconfigure(r, weight=1)
        self.log = ctk.CTkTextbox(f, height=120, wrap="none", state="disabled")
        self.log.grid(row=r, column=0, columnspan=3, sticky="nsew", padx=6, pady=(4, 6))

    # ---------- carga de ffmpeg ----------
    def pick_ffmpeg(self):
        p = filedialog.askopenfilename(title="Selecciona el ejecutable de ffmpeg")
        if p:
            self.load_ffmpeg(p)

    def show_diag(self):
        if self.info:
            messagebox.showinfo("Diagnóstico", self.info.diagnostic())
        else:
            messagebox.showinfo(
                "Diagnóstico",
                f"ffmpeg no cargado.\nBúsqueda en PATH: {shutil.which('ffmpeg')}\n"
                f"Último error: {LAST_ERROR or 'ninguno'}")

    def load_ffmpeg(self, path=None):
        try:
            self._load_ffmpeg(path)
        except Exception:
            import traceback
            self.status.configure(text="Error al cargar ffmpeg (ver detalles).")
            messagebox.showerror("Error al cargar ffmpeg", traceback.format_exc()[-1500:])

    def _load_ffmpeg(self, path=None):
        if not isinstance(path, str):
            path = self.info.path if self.info else shutil.which("ffmpeg")
        if not path:
            self.status.configure(text="ffmpeg no encontrado en el PATH.")
            messagebox.showerror(
                "ffmpeg no encontrado",
                "Instala ffmpeg o usa 'Elegir ffmpeg...' para indicar su ubicación.")
            return
        self.status.configure(text="Analizando ffmpeg...")
        self.update_idletasks()
        self.info = i = FFmpegInfo(path)

        # 1) selectores de la pestaña Convertir (lo más importante)
        fmts = [f"{n}{SEP}{d}" if d else n for n, d in i.muxers]
        self.fmt_btn.set_items(fmts)
        self.vc_btn.set_items([AUTO, COPY] + i.encoder_items("V"))
        self.ac_btn.set_items([AUTO, COPY] + i.encoder_items("A"))
        self.vc_btn.set(AUTO)
        self.ac_btn.set(AUTO)

        # 2) listas informativas
        self.term_chk.configure(text=f"Ejecutar en la terminal del sistema ({self.os_name})")
        for tab, rows in (
            (self.tab_mux, i.muxers),
            (self.tab_dem, i.demuxers),
            (self.tab_enc, list(i.encoders)),
            (self.tab_plug, [(t, n, d) for t, _f, n, d in i.external_encoders()]),
            (self.tab_lib, [(l,) for l in i.libs]),
        ):
            tab.set_rows(rows)

        # 3) estado y formato por defecto
        self.status.configure(
            text=f"{i.version}  |  OS: {self.os_name}  |  {len(i.muxers)} salida, "
                 f"{len(i.demuxers)} entrada, {len(i.encoders)} encoders")
        if fmts and not self.fmt_btn.get():
            first = next((x for x in fmts if x.split(SEP)[0] == "mp4"), fmts[0])
            self.fmt_btn.set(first)
            self.on_format_change()
        if not fmts:
            self.after(400, lambda: messagebox.showwarning(
                "No se detectaron formatos", i.diagnostic()))

    # ---------- acciones ----------
    def pick_input(self):
        p = filedialog.askopenfilename(title="Archivo de entrada")
        if p:
            self.in_var.set(p)
            self.update_output_name()

    def pick_output(self):
        p = filedialog.asksaveasfilename(title="Archivo de salida",
                                         initialfile=os.path.basename(self.out_var.get()))
        if p:
            self.out_var.set(p)

    def on_format_change(self):
        name = self.fmt_btn.key()
        if not name or not self.info:
            return
        d = self.info.muxer_details(name)
        self.vc_btn.set(AUTO)
        self.ac_btn.set(AUTO)
        self.status.configure(
            text=f"{self.info.version}  |  Formato {name}: ext .{d['ext']}, "
                 f"video por defecto: {d['vcodec'] or '-'}, audio por defecto: {d['acodec'] or '-'}")
        self.update_output_name()

    def update_output_name(self):
        src, name = self.in_var.get(), self.fmt_btn.key()
        if not src or not name or not self.info:
            return
        ext = self.info.muxer_details(name)["ext"]
        base, _ = os.path.splitext(src)
        self.out_var.set(f"{base}_convertido.{ext}")

    def build_command(self):
        if not self.info:
            raise ValueError("ffmpeg no está cargado.")
        src, dst, fmt = self.in_var.get().strip(), self.out_var.get().strip(), self.fmt_btn.key()
        if not src or not os.path.isfile(src):
            raise ValueError("Selecciona un archivo de entrada válido.")
        if not dst:
            raise ValueError("Indica el archivo de salida.")
        if not fmt:
            raise ValueError("Selecciona un formato de salida.")
        if os.path.abspath(src) == os.path.abspath(dst):
            raise ValueError("La salida no puede ser el mismo archivo que la entrada.")

        cmd = [self.info.path, "-hide_banner", "-y" if self.overwrite.get() else "-n",
               "-i", src, "-f", fmt]
        if self.vc_btn.get() not in ("", AUTO):
            cmd += ["-c:v", self.vc_btn.key()]
        if self.ac_btn.get() not in ("", AUTO):
            cmd += ["-c:a", self.ac_btn.key()]
        extra = self.extra_var.get().strip()
        if extra:
            cmd += shlex.split(extra, posix=(self.os_name != "Windows"))
        cmd.append(dst)
        return cmd

    def show_command(self):
        try:
            cmd = self.build_command()
        except ValueError as e:
            messagebox.showwarning("Faltan datos", str(e))
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
                self.log_write(f"[{self.os_name}] {msg}\n")
                return
            self.log_write(f"{msg} Se ejecutará dentro de la ventana.\n")
        threading.Thread(target=self._run_inline, args=(cmd,), daemon=True).start()

    def _run_inline(self, cmd):
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
            for line in p.stdout:
                self.log_q.put(line)
            p.wait()
            self.log_q.put(f"\n[ffmpeg terminó con código {p.returncode}]\n")
        except OSError as e:
            self.log_q.put(f"Error: {e}\n")

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
        sys.exit(f"No se pudo iniciar la interfaz gráfica: {e}")
