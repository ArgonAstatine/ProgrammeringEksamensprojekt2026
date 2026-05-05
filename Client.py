import socket
import threading
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from datetime import datetime
from cryptography.fernet import Fernet
import base64

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False


PORT = 5555
BUFFER_SIZE        = 4096
MAX_MESSAGE_LENGTH = 2048
MAX_FILE_SIZE      = 1 * 1024 * 1024
SESSION_PATH     = "session.json.enc"
SESSION_KEY_PATH = "session.key"

IMAGE_EXTENSIONS         = {".png", ".gif"}
IMAGE_MAX_WIDTH_DISPLAY  = 380
IMAGE_MAX_HEIGHT_DISPLAY = 280

THEMES = {
    "Discord Mørk": {
        "BG_DARK":      "#1e1f22",
        "BG_PANEL":     "#2b2d31",
        "BG_CHAT":      "#313338",
        "BG_INPUT":     "#383a40",
        "ACCENT":       "#5865f2",
        "ACCENT_HOVER": "#4752c4",
        "TEXT_MAIN":    "#dbdee1",
        "TEXT_MUTED":   "#80848e",
        "TEXT_TIME":    "#80848e",
        "BUBBLE_ME":    "#5865f2",
        "BUBBLE_OTHER": "#2e3035",
        "BUBBLE_SYS":   "#80848e",
        "ONLINE_DOT":   "#23a55a",
        "SEPARATOR":    "#3f4147",
        "DANGER":       "#f04747",
        "WARNING":      "#faa61a",
    },
    "Discord Lys": {
        "BG_DARK":      "#e3e5e8",
        "BG_PANEL":     "#f2f3f5",
        "BG_CHAT":      "#ffffff",
        "BG_INPUT":     "#ebedef",
        "ACCENT":       "#5865f2",
        "ACCENT_HOVER": "#4752c4",
        "TEXT_MAIN":    "#2e3338",
        "TEXT_MUTED":   "#747f8d",
        "TEXT_TIME":    "#747f8d",
        "BUBBLE_ME":    "#5865f2",
        "BUBBLE_OTHER": "#e9eaec",
        "BUBBLE_SYS":   "#747f8d",
        "ONLINE_DOT":   "#23a55a",
        "SEPARATOR":    "#c7c9ce",
        "DANGER":       "#d83c3e",
        "WARNING":      "#f0a232",
    },
    "Midnat Blå": {
        "BG_DARK":      "#0a0f1e",
        "BG_PANEL":     "#0d1529",
        "BG_CHAT":      "#111d35",
        "BG_INPUT":     "#162240",
        "ACCENT":       "#4a9eff",
        "ACCENT_HOVER": "#2e86e8",
        "TEXT_MAIN":    "#cdd9f0",
        "TEXT_MUTED":   "#6b82a8",
        "TEXT_TIME":    "#6b82a8",
        "BUBBLE_ME":    "#1a4b8c",
        "BUBBLE_OTHER": "#172037",
        "BUBBLE_SYS":   "#4a6080",
        "ONLINE_DOT":   "#2ecc71",
        "SEPARATOR":    "#1e2d4a",
        "DANGER":       "#e74c3c",
        "WARNING":      "#f39c12",
    },
    "Skov Grøn": {
        "BG_DARK":      "#1a2416",
        "BG_PANEL":     "#1f2e1a",
        "BG_CHAT":      "#253320",
        "BG_INPUT":     "#2b3d24",
        "ACCENT":       "#4caf50",
        "ACCENT_HOVER": "#388e3c",
        "TEXT_MAIN":    "#d4e8c2",
        "TEXT_MUTED":   "#7a9e68",
        "TEXT_TIME":    "#7a9e68",
        "BUBBLE_ME":    "#2e6e2e",
        "BUBBLE_OTHER": "#1e3018",
        "BUBBLE_SYS":   "#5a7a4a",
        "ONLINE_DOT":   "#66bb6a",
        "SEPARATOR":    "#2e4428",
        "DANGER":       "#ef5350",
        "WARNING":      "#ffa726",
    },
    "Varm Sepia": {
        "BG_DARK":      "#1c1510",
        "BG_PANEL":     "#251d15",
        "BG_CHAT":      "#2e241a",
        "BG_INPUT":     "#382c20",
        "ACCENT":       "#c0874a",
        "ACCENT_HOVER": "#a06a30",
        "TEXT_MAIN":    "#e8d5b8",
        "TEXT_MUTED":   "#9e8060",
        "TEXT_TIME":    "#9e8060",
        "BUBBLE_ME":    "#7a4820",
        "BUBBLE_OTHER": "#261d14",
        "BUBBLE_SYS":   "#7a6040",
        "ONLINE_DOT":   "#81c784",
        "SEPARATOR":    "#3a2c1e",
        "DANGER":       "#e57373",
        "WARNING":      "#ffb74d",
    },
}

FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_BODY  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 8)
FONT_INPUT = ("Segoe UI", 11)
FONT_NAME  = ("Segoe UI", 9, "bold")


def get_session_fernet() -> Fernet:
    if os.path.exists(SESSION_KEY_PATH):
        with open(SESSION_KEY_PATH, "rb") as f:
            key = f.read()
    else:
        key = Fernet.generate_key()
        with open(SESSION_KEY_PATH, "wb") as f:
            f.write(key)
    return Fernet(key)


def load_session() -> dict:
    fernet = get_session_fernet()
    try:
        with open(SESSION_PATH, "rb") as f:
            return json.loads(fernet.decrypt(f.read()).decode())
    except Exception:
        return {}


def save_session(data: dict):
    fernet = get_session_fernet()
    with open(SESSION_PATH, "wb") as f:
        f.write(fernet.encrypt(json.dumps(data).encode()))


def send_msg(sock, payload):
    data = json.dumps(payload) + "\n"
    sock.sendall(data.encode("utf-8"))


def format_last_seen(iso_str):
    if not iso_str:
        return "Aldrig"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso_str


def is_image_filename(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in IMAGE_EXTENSIONS


def make_photo(data_b64: str):
    try:
        return tk.PhotoImage(data=data_b64)
    except tk.TclError:
        return None


class MusicPlayer:
    def __init__(self):
        self.enabled = False
        self.path    = None
        self.volume  = 0.5

    def load(self, path: str):
        if not PYGAME_AVAILABLE:
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            self.path = path
            return True
        except Exception:
            return False

    def play(self):
        if not PYGAME_AVAILABLE or not self.path:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(self.path)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(-1)
            self.enabled = True
        except Exception:
            pass

    def stop(self):
        if not PYGAME_AVAILABLE:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.enabled = False

    def set_volume(self, vol: float):
        self.volume = max(0.0, min(1.0, vol))
        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass

    def toggle(self):
        if self.enabled:
            self.stop()
        else:
            self.play()


class ToastNotification(tk.Toplevel):
    def __init__(self, master, title: str, message: str, duration_ms: int = 4000):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#2b2d31")

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 320, 72
        x = sw - w - 16
        y = sh - h - 48
        self.geometry(f"{w}x{h}+{x}+{y}")

        accent_bar = tk.Frame(self, bg="#5865f2", width=4)
        accent_bar.pack(side="left", fill="y")

        content = tk.Frame(self, bg="#2b2d31", padx=12, pady=10)
        content.pack(side="left", fill="both", expand=True)

        tk.Label(content, text=title, font=("Segoe UI", 9, "bold"),
                 bg="#2b2d31", fg="#ffffff", anchor="w").pack(fill="x")
        tk.Label(content, text=message[:60] + ("…" if len(message) > 60 else ""),
                 font=("Segoe UI", 9), bg="#2b2d31", fg="#b5bac1", anchor="w",
                 wraplength=260, justify="left").pack(fill="x")

        close_btn = tk.Label(self, text="✕", font=("Segoe UI", 9),
                             bg="#2b2d31", fg="#80848e", cursor="hand2", padx=8)
        close_btn.pack(side="right", anchor="n", pady=8)
        close_btn.bind("<Button-1>", lambda _: self._dismiss())

        self.bind("<Button-1>", lambda _: self._on_click())

        self._master = master
        self._after_id = self.after(duration_ms, self._dismiss)

    def _dismiss(self):
        try:
            self.after_cancel(self._after_id)
        except Exception:
            pass
        self.destroy()

    def _on_click(self):
        self._dismiss()
        try:
            self._master.deiconify()
            self._master.lift()
            self._master.focus_force()
        except Exception:
            pass


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chat: Log ind")
        self.configure(bg="#1e1f22")
        self.resizable(False, False)
        self._center(360, 370)

        session = load_session()

        tk.Label(self, text="Velkommen!", font=("Segoe UI", 18, "bold"),
                 bg="#1e1f22", fg="#dbdee1").pack(pady=(24, 4))

        tk.Label(self, text="SERVER IP", font=("Segoe UI", 8, "bold"),
                 bg="#1e1f22", fg="#80848e").pack(anchor="w", padx=50)
        self.ip_var = tk.StringVar(value=session.get("ip", "127.0.0.1"))
        tk.Entry(self, textvariable=self.ip_var, font=FONT_INPUT,
                 bg="#383a40", fg="#dbdee1", insertbackground="#dbdee1",
                 relief="flat", bd=8).pack(padx=50, fill="x", pady=(2, 10))

        tk.Label(self, text="BRUGERNAVN", font=("Segoe UI", 8, "bold"),
                 bg="#1e1f22", fg="#80848e").pack(anchor="w", padx=50)
        self.username_var = tk.StringVar()
        name_entry = tk.Entry(self, textvariable=self.username_var, font=FONT_INPUT,
                              bg="#383a40", fg="#dbdee1", insertbackground="#dbdee1",
                              relief="flat", bd=8)
        name_entry.pack(padx=50, fill="x", pady=(2, 10))

        tk.Label(self, text="ADGANGSKODE", font=("Segoe UI", 8, "bold"),
                 bg="#1e1f22", fg="#80848e").pack(anchor="w", padx=50)
        self.pw_var = tk.StringVar()
        pw_entry = tk.Entry(self, textvariable=self.pw_var, font=FONT_INPUT,
                            bg="#383a40", fg="#dbdee1", insertbackground="#dbdee1",
                            relief="flat", bd=8, show="•")
        pw_entry.pack(padx=50, fill="x", pady=(2, 6))
        pw_entry.bind("<Return>", lambda _: self._login())

        name_entry.focus()

        self.status = tk.Label(self, text="", font=FONT_SMALL, bg="#1e1f22", fg="#f04747")
        self.status.pack()

        tk.Button(self, text="Log ind / Opret konto", font=("Segoe UI", 10, "bold"),
                  bg="#5865f2", fg="white", relief="flat", bd=0,
                  activebackground="#4752c4", activeforeground="white",
                  padx=20, pady=8, cursor="hand2", command=self._login
                  ).pack(pady=8, padx=50, fill="x")

        tk.Label(self, text="Nyt brugernavn? Konto oprettes automatisk.",
                 font=FONT_SMALL, bg="#1e1f22", fg="#80848e").pack()

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _login(self):
        username = self.username_var.get().strip()
        password = self.pw_var.get()
        ip       = self.ip_var.get().strip() or "127.0.0.1"
        if not username:
            self.status.config(text="Indtast et brugernavn.")
            return
        if not password:
            self.status.config(text="Indtast en adgangskode.")
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, PORT))
        except ConnectionRefusedError:
            self.status.config(text=f"Kunne ikke forbinde til {ip}:{PORT}")
            return
        except OSError as e:
            self.status.config(text=f"Fejl: {e}")
            return
        self.destroy()
        ChatApp(sock, username, password=password, ip=ip).mainloop()


class ChatApp(tk.Tk):
    def __init__(self, sock, username, password="", token="", ip="127.0.0.1"):
        super().__init__()
        self.current_panel    = "chat"
        self.window_open      = True
        self.sock             = sock
        self.username         = username
        self.password         = password
        self.token            = token
        self.ip               = ip
        self.active_chat      = None
        self.stop_event       = threading.Event()
        self.buf              = ""
        self.user_status      = {}
        self.chat_history     = {"#alle": []}
        self.bubble_frames    = {"#alle": []}
        self.friends          = set()
        self.pending_sent     = set()
        self.pending_received = set()
        self._photo_refs: list = []
        self._active_toast    = None

        self.rooms: dict = {}
        self.pending_room_invites: list = []
        self.music = MusicPlayer()

        session = load_session()
        saved_theme = session.get("theme", "Discord Mørk")
        if saved_theme not in THEMES:
            saved_theme = "Discord Mørk"
        self.current_theme_name = saved_theme
        self._apply_theme_vars(THEMES[saved_theme])

        self.title("Chat")
        self.configure(bg=self.BG_DARK)
        self.geometry("1100x680")
        self._place_corner()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_minimize)
        self.bind("<Map>",   self._on_restore)

        self._build_ui()
        self._start_listener()

        if token:
            send_msg(self.sock, {"type": "connect", "token": token})
        else:
            send_msg(self.sock, {"type": "connect", "username": username, "password": password})

        self._tick()

    def _apply_theme_vars(self, t: dict):
        for k, v in t.items():
            setattr(self, k, v)

    def _apply_theme(self, theme_name: str):
        if theme_name not in THEMES:
            return
        self.current_theme_name = theme_name
        self._apply_theme_vars(THEMES[theme_name])

        session = load_session()
        session["theme"] = theme_name
        save_session(session)

        self.configure(bg=self.BG_DARK)
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
        self._refresh_chat()

    def _corner_pos(self):
        return self.winfo_screenwidth() - 1100 - 10, 10

    def _place_corner(self):
        self.update_idletasks()
        x, y = self._corner_pos()
        self.geometry(f"1100x680+{x}+{y}")

    def _on_minimize(self, _=None):
        self.window_open = False

    def _on_restore(self, _=None):
        self.window_open = True

    def _notify_popup(self):
        if self.window_open:
            return
        x, y = self._corner_pos()
        self.geometry(f"1100x680+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()
        self.window_open = True

    def _show_toast(self, title: str, message: str):
        if self._active_toast is not None:
            try:
                self._active_toast.destroy()
            except Exception:
                pass
        self._active_toast = ToastNotification(self, title, message)

    def _notify_group(self, sender: str = "", content: str = ""):
        self._show_toast(f"Chat – {sender}", content or "Ny besked")
        self._notify_popup()

    def _room_chat_key(self, room_id):
        return f"#rum:{room_id}"

    def _build_ui(self):
        self.left = tk.Frame(self, bg=self.BG_PANEL, width=220)
        self.left.pack(side="left", fill="y")
        self.left.pack_propagate(False)

        top_bar = tk.Frame(self.left, bg=self.BG_DARK, height=48)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        self.username_label = tk.Label(top_bar, text=f"  {self.username}", font=FONT_TITLE,
                 bg=self.BG_DARK, fg=self.TEXT_MAIN, anchor="w")
        self.username_label.pack(side="left", fill="y", padx=4)

        music_btn = tk.Button(
            top_bar, text="🎵", font=("Segoe UI", 13),
            bg=self.BG_DARK, fg=self.TEXT_MUTED, relief="flat", bd=0,
            activebackground=self.BG_DARK, activeforeground=self.TEXT_MAIN,
            cursor="hand2", command=self._open_music_dialog
        )
        music_btn.pack(side="right", padx=2)

        theme_btn = tk.Button(
            top_bar, text="🎨", font=("Segoe UI", 13),
            bg=self.BG_DARK, fg=self.TEXT_MUTED, relief="flat", bd=0,
            activebackground=self.BG_DARK, activeforeground=self.TEXT_MAIN,
            cursor="hand2", command=self._open_theme_dialog
        )
        theme_btn.pack(side="right", padx=2)

        settings_btn = tk.Button(
            top_bar, text="⚙", font=("Segoe UI", 13),
            bg=self.BG_DARK, fg=self.TEXT_MUTED, relief="flat", bd=0,
            activebackground=self.BG_DARK, activeforeground=self.TEXT_MAIN,
            cursor="hand2", command=self._open_settings_dialog
        )
        settings_btn.pack(side="right", padx=2)

        self.date_label = tk.Label(self.left, text="", font=FONT_SMALL,
                                   bg=self.BG_PANEL, fg=self.TEXT_MUTED)
        self.date_label.pack(pady=(8, 2))

        tk.Frame(self.left, bg=self.SEPARATOR, height=1).pack(fill="x", padx=10, pady=4)

        nav_frame = tk.Frame(self.left, bg=self.BG_PANEL)
        nav_frame.pack(fill="x", padx=8, pady=(0, 4))

        self.btn_chat = tk.Button(nav_frame, text="💬  Chat", font=("Segoe UI", 9, "bold"),
                                  bg=self.ACCENT, fg="white", relief="flat", bd=0,
                                  activebackground=self.ACCENT_HOVER, activeforeground="white",
                                  anchor="w", padx=10, pady=5, cursor="hand2",
                                  command=self._show_chat_panel)
        self.btn_chat.pack(fill="x", pady=2)

        self.btn_hub = tk.Button(nav_frame, text="🌐  Bruger Hub", font=("Segoe UI", 9, "bold"),
                                 bg=self.BG_PANEL, fg=self.TEXT_MUTED, relief="flat", bd=0,
                                 activebackground="#35373c", activeforeground=self.TEXT_MAIN,
                                 anchor="w", padx=10, pady=5, cursor="hand2",
                                 command=self._show_hub_panel)
        self.btn_hub.pack(fill="x", pady=2)

        tk.Frame(self.left, bg=self.SEPARATOR, height=1).pack(fill="x", padx=10, pady=4)

        tk.Label(self.left, text="  VENNELISTE", font=("Segoe UI", 8, "bold"),
                 bg=self.BG_PANEL, fg=self.TEXT_MUTED, anchor="w").pack(fill="x", padx=8, pady=(0, 2))

        list_frame = tk.Frame(self.left, bg=self.BG_PANEL)
        list_frame.pack(fill="x", padx=4)

        sb = tk.Scrollbar(list_frame, bg=self.BG_PANEL, troughcolor=self.BG_PANEL,
                          relief="flat", bd=0, width=6)
        sb.pack(side="right", fill="y")

        self.friend_list = tk.Listbox(
            list_frame, bg=self.BG_PANEL, fg=self.TEXT_MAIN,
            font=FONT_BODY, relief="flat", bd=0,
            selectbackground="#35373c", selectforeground=self.TEXT_MAIN,
            activestyle="none", yscrollcommand=sb.set,
            highlightthickness=0, height=8
        )
        self.friend_list.pack(fill="x")
        sb.config(command=self.friend_list.yview)
        self.friend_list.bind("<<ListboxSelect>>", self._on_friend_select)
        self.friend_list.bind("<Button-3>", self._on_friend_right_click)

        for name in sorted(self.friends):
            display = f" {name}"
            self.friend_list.insert("end", display)
            idx = self.friend_list.size() - 1
            online = self.user_status.get(name, False)
            self.friend_list.itemconfig(idx, fg=self.ONLINE_DOT if online else self.DANGER)

        tk.Frame(self.left, bg=self.SEPARATOR, height=1).pack(fill="x", padx=10, pady=4)

        rooms_header = tk.Frame(self.left, bg=self.BG_PANEL)
        rooms_header.pack(fill="x", padx=8, pady=(0, 2))
        tk.Label(rooms_header, text="  CHATRUM", font=("Segoe UI", 8, "bold"),
                 bg=self.BG_PANEL, fg=self.TEXT_MUTED, anchor="w").pack(side="left", fill="x", expand=True)
        tk.Button(rooms_header, text="+", font=("Segoe UI", 9, "bold"),
                  bg=self.BG_PANEL, fg=self.ACCENT, relief="flat", bd=0,
                  activebackground=self.BG_PANEL, activeforeground=self.ACCENT_HOVER,
                  cursor="hand2", command=self._create_room).pack(side="right")

        rooms_list_frame = tk.Frame(self.left, bg=self.BG_PANEL)
        rooms_list_frame.pack(fill="x", padx=4)

        rsb = tk.Scrollbar(rooms_list_frame, bg=self.BG_PANEL, troughcolor=self.BG_PANEL,
                           relief="flat", bd=0, width=6)
        rsb.pack(side="right", fill="y")

        self.room_list = tk.Listbox(
            rooms_list_frame, bg=self.BG_PANEL, fg=self.TEXT_MAIN,
            font=FONT_BODY, relief="flat", bd=0,
            selectbackground="#35373c", selectforeground=self.TEXT_MAIN,
            activestyle="none", yscrollcommand=rsb.set,
            highlightthickness=0, height=6
        )
        self.room_list.pack(fill="x")
        rsb.config(command=self.room_list.yview)
        self.room_list.bind("<<ListboxSelect>>", self._on_room_select)
        self.room_list.bind("<Button-3>", self._on_room_right_click)

        for room_id, room in self.rooms.items():
            self.room_list.insert("end", f" # {room['name']}")

        tk.Frame(self.left, bg=self.SEPARATOR, height=1).pack(fill="x", padx=10, pady=4)

        broadcast_row = tk.Frame(self.left, bg=self.BG_PANEL, cursor="hand2")
        broadcast_row.pack(fill="x", padx=8, pady=(0, 8))
        broadcast_label = tk.Label(broadcast_row, text="  # alle", font=FONT_BODY,
                                   bg=self.BG_PANEL, fg=self.TEXT_MUTED, anchor="w", pady=5)
        broadcast_label.pack(fill="x")
        broadcast_row.bind("<Button-1>", lambda _: self._select_broadcast())
        broadcast_label.bind("<Button-1>", lambda _: self._select_broadcast())

        self.right = tk.Frame(self, bg=self.BG_CHAT)
        self.right.pack(side="right", fill="both", expand=True)

        self._build_chat_panel()
        self._build_hub_panel()

        if self.current_panel == "hub":
            self._show_hub_panel()
        else:
            self._show_chat_panel()

    def _open_settings_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Indstillinger")
        dialog.configure(bg=self.BG_DARK)
        dialog.resizable(False, False)
        dialog.grab_set()

        self.update_idletasks()
        w, h = 360, 280
        x = self.winfo_x() + (1100 - w) // 2
        y = self.winfo_y() + (680 - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(dialog, text="⚙  Indstillinger", font=FONT_TITLE,
                 bg=self.BG_DARK, fg=self.TEXT_MAIN).pack(pady=(16, 4))

        tk.Frame(dialog, bg=self.SEPARATOR, height=1).pack(fill="x", padx=20, pady=(4, 12))

        tk.Label(dialog, text="SKIFT BRUGERNAVN", font=("Segoe UI", 8, "bold"),
                 bg=self.BG_DARK, fg=self.TEXT_MUTED, anchor="w").pack(anchor="w", padx=24)

        tk.Label(dialog, text=f"Nuværende: {self.username}", font=FONT_SMALL,
                 bg=self.BG_DARK, fg=self.TEXT_MUTED, anchor="w").pack(anchor="w", padx=24, pady=(2, 6))

        new_name_var = tk.StringVar()
        tk.Entry(dialog, textvariable=new_name_var, font=FONT_INPUT,
                 bg=self.BG_INPUT, fg=self.TEXT_MAIN, insertbackground=self.TEXT_MAIN,
                 relief="flat", bd=8, width=28).pack(padx=24, fill="x", pady=(0, 10))

        tk.Label(dialog, text="BEKRÆFT MED ADGANGSKODE", font=("Segoe UI", 8, "bold"),
                 bg=self.BG_DARK, fg=self.TEXT_MUTED, anchor="w").pack(anchor="w", padx=24)

        pw_var = tk.StringVar()
        pw_entry = tk.Entry(dialog, textvariable=pw_var, font=FONT_INPUT,
                            bg=self.BG_INPUT, fg=self.TEXT_MAIN, insertbackground=self.TEXT_MAIN,
                            relief="flat", bd=8, show="•", width=28)
        pw_entry.pack(padx=24, fill="x", pady=(2, 8))

        status_lbl = tk.Label(dialog, text="", font=FONT_SMALL,
                              bg=self.BG_DARK, fg=self.DANGER)
        status_lbl.pack()

        def do_change():
            new_name = new_name_var.get().strip()
            password = pw_var.get()
            if not new_name:
                status_lbl.config(text="Nyt brugernavn må ikke være tomt.", fg=self.DANGER)
                return
            if not password:
                status_lbl.config(text="Adgangskode er påkrævet.", fg=self.DANGER)
                return
            self._pending_change_dialog = dialog
            self._pending_change_status = status_lbl
            send_msg(self.sock, {
                "type":         "change_username",
                "new_username": new_name,
                "password":     password,
            })

        pw_entry.bind("<Return>", lambda _: do_change())

        tk.Button(dialog, text="Skift brugernavn", font=("Segoe UI", 10, "bold"),
                  bg=self.ACCENT, fg="white", relief="flat", bd=0,
                  activebackground=self.ACCENT_HOVER, activeforeground="white",
                  padx=16, pady=8, cursor="hand2",
                  command=do_change).pack(pady=(4, 0), padx=24, fill="x")

    def _open_music_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Baggrundsmusik")
        dialog.configure(bg=self.BG_DARK)
        dialog.resizable(False, False)
        dialog.grab_set()

        self.update_idletasks()
        w, h = 340, 220
        x = self.winfo_x() + (1100 - w) // 2
        y = self.winfo_y() + (680 - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(dialog, text="🎵  Baggrundsmusik", font=FONT_TITLE,
                 bg=self.BG_DARK, fg=self.TEXT_MAIN).pack(pady=(16, 8))

        if not PYGAME_AVAILABLE:
            tk.Label(dialog, text="pygame er ikke installeret.\nKør: pip install pygame",
                     font=FONT_BODY, bg=self.BG_DARK, fg=self.DANGER,
                     justify="center").pack(pady=20)
            return

        path_var = tk.StringVar(value=self.music.path or "Ingen fil valgt")
        path_label = tk.Label(dialog, textvariable=path_var, font=FONT_SMALL,
                              bg=self.BG_DARK, fg=self.TEXT_MUTED,
                              wraplength=300, justify="center")
        path_label.pack(pady=(0, 8))

        def pick_file():
            path = filedialog.askopenfilename(
                title="Vælg MP3-fil",
                filetypes=[("MP3-filer", "*.mp3"), ("Alle lydfiler", "*.mp3 *.wav *.ogg *.flac"), ("Alle filer", "*.*")]
            )
            if path:
                if self.music.load(path):
                    path_var.set(os.path.basename(path))
                    toggle_btn.config(text="▶ Afspil", bg=self.ACCENT)
                else:
                    path_var.set("Fejl ved indlæsning af fil")

        tk.Button(dialog, text="📂  Vælg MP3-fil", font=FONT_BODY,
                  bg=self.BG_INPUT, fg=self.TEXT_MAIN, relief="flat", bd=0,
                  activebackground="#35373c", activeforeground=self.TEXT_MAIN,
                  cursor="hand2", padx=12, pady=6,
                  command=pick_file).pack(pady=4)

        def toggle():
            self.music.toggle()
            if self.music.enabled:
                toggle_btn.config(text="⏹ Stop", bg=self.DANGER)
            else:
                toggle_btn.config(text="▶ Afspil", bg=self.ACCENT)

        toggle_label = "⏹ Stop" if self.music.enabled else "▶ Afspil"
        toggle_bg    = self.DANGER if self.music.enabled else self.ACCENT
        toggle_btn   = tk.Button(dialog, text=toggle_label, font=FONT_BODY,
                                 bg=toggle_bg, fg="white", relief="flat", bd=0,
                                 activebackground=self.ACCENT_HOVER, activeforeground="white",
                                 cursor="hand2", padx=16, pady=6,
                                 command=toggle)
        toggle_btn.pack(pady=4)

        vol_frame = tk.Frame(dialog, bg=self.BG_DARK)
        vol_frame.pack(pady=(8, 4))
        tk.Label(vol_frame, text="Lydstyrke:", font=FONT_SMALL,
                 bg=self.BG_DARK, fg=self.TEXT_MUTED).pack(side="left", padx=(0, 8))

        vol_var = tk.DoubleVar(value=self.music.volume)

        def on_vol(val):
            self.music.set_volume(float(val))

        vol_scale = tk.Scale(vol_frame, from_=0.0, to=1.0, resolution=0.05,
                             orient="horizontal", variable=vol_var,
                             bg=self.BG_DARK, fg=self.TEXT_MAIN,
                             troughcolor=self.BG_INPUT, highlightthickness=0,
                             relief="flat", length=160, showvalue=False,
                             command=on_vol)
        vol_scale.pack(side="left")

    def _open_theme_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Vælg tema")
        dialog.configure(bg=self.BG_DARK)
        dialog.resizable(False, False)
        dialog.grab_set()

        self.update_idletasks()
        w, h = 300, 60 + len(THEMES) * 44
        x = self.winfo_x() + (1100 - w) // 2
        y = self.winfo_y() + (680 - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(dialog, text="Vælg app-tema", font=FONT_TITLE,
                 bg=self.BG_DARK, fg=self.TEXT_MAIN).pack(pady=(16, 8))

        for name, colors in THEMES.items():
            is_active = (name == self.current_theme_name)
            row = tk.Frame(dialog, bg=self.BG_PANEL if is_active else self.BG_DARK,
                           cursor="hand2")
            row.pack(fill="x", padx=16, pady=3)
            preview = tk.Frame(row, bg=colors["ACCENT"], width=16, height=16)
            preview.pack(side="left", padx=(10, 8), pady=10)
            preview.pack_propagate(False)

            label_text = f"✓  {name}" if is_active else f"    {name}"
            lbl = tk.Label(row, text=label_text, font=FONT_BODY,
                           bg=self.BG_PANEL if is_active else self.BG_DARK,
                           fg=self.ACCENT if is_active else self.TEXT_MAIN,
                           anchor="w", pady=6)
            lbl.pack(side="left", fill="x", expand=True)

            def make_cmd(n=name, d=dialog):
                def cmd(_=None):
                    d.destroy()
                    self._apply_theme(n)
                return cmd

            row.bind("<Button-1>", make_cmd())
            lbl.bind("<Button-1>", make_cmd())
            preview.bind("<Button-1>", make_cmd())

            row.bind("<Enter>", lambda e, r=row, n=name: r.config(
                bg=self.BG_PANEL if n != self.current_theme_name else r.cget("bg")))
            row.bind("<Leave>", lambda e, r=row, n=name: r.config(
                bg=self.BG_PANEL if n == self.current_theme_name else self.BG_DARK))

    def _create_room(self):
        name = simpledialog.askstring("Opret chatrum", "Rutnavn:", parent=self)
        if name and name.strip():
            send_msg(self.sock, {"type": "create_room", "name": name.strip()})

    def _invite_to_room(self, room_id):
        room = self.rooms.get(room_id)
        if not room:
            return
        members = room.get("members", [])
        candidates = [f for f in self.friends if f not in members]
        if not candidates:
            messagebox.showinfo("Inviter", "Ingen venner at invitere (alle er allerede med eller du har ingen venner).")
            return

        dialog = tk.Toplevel(self)
        dialog.title(f"Inviter til #{room['name']}")
        dialog.configure(bg=self.BG_DARK)
        dialog.resizable(False, False)
        dialog.grab_set()

        self.update_idletasks()
        w, h = 260, min(60 + len(candidates) * 40, 400)
        x = self.winfo_x() + (1100 - w) // 2
        y = self.winfo_y() + (680 - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(dialog, text="Vælg ven at invitere:", font=FONT_BODY,
                 bg=self.BG_DARK, fg=self.TEXT_MAIN).pack(pady=(12, 6))

        frame = tk.Frame(dialog, bg=self.BG_DARK)
        frame.pack(fill="both", expand=True, padx=16)

        for name in candidates:
            def invite(n=name, d=dialog):
                send_msg(self.sock, {"type": "invite_to_room", "room_id": room_id, "username": n})
                d.destroy()
            tk.Button(frame, text=name, font=FONT_BODY,
                      bg=self.BG_PANEL, fg=self.TEXT_MAIN, relief="flat", bd=0,
                      activebackground=self.ACCENT, activeforeground="white",
                      cursor="hand2", padx=10, pady=6, anchor="w",
                      command=invite).pack(fill="x", pady=2)

    def _leave_room(self, room_id):
        room = self.rooms.get(room_id)
        name = room["name"] if room else str(room_id)
        if messagebox.askyesno("Forlad rum", f"Er du sikker på, at du vil forlade #{name}?"):
            send_msg(self.sock, {"type": "leave_room", "room_id": room_id})

    def _on_room_select(self, _=None):
        sel = self.room_list.curselection()
        if not sel:
            return
        text = self.room_list.get(sel[0]).strip().lstrip("# ").strip()
        for room_id, room in self.rooms.items():
            if room["name"] == text:
                self.active_chat = self._room_chat_key(room_id)
                self.header_label.config(text=f"# {room['name']}")
                self._show_chat_panel()
                self._refresh_chat()
                return

    def _on_room_right_click(self, event):
        idx = self.room_list.nearest(event.y)
        if idx < 0 or idx >= self.room_list.size():
            return
        text = self.room_list.get(idx).strip().lstrip("# ").strip()
        room_id = None
        for rid, room in self.rooms.items():
            if room["name"] == text:
                room_id = rid
                break
        if room_id is None:
            return
        menu = tk.Menu(self, tearoff=0, bg=self.BG_PANEL, fg=self.TEXT_MAIN,
                       activebackground=self.ACCENT, activeforeground="white",
                       relief="flat", bd=0)
        menu.add_command(label="Inviter ven",
                         command=lambda: self._invite_to_room(room_id))
        menu.add_separator()
        menu.add_command(label="Forlad rum",
                         command=lambda: self._leave_room(room_id))
        menu.tk_popup(event.x_root, event.y_root)

    def _add_room_to_sidebar(self, room):
        room_id = room["id"]
        if room_id in self.rooms:
            return
        self.rooms[room_id] = room
        chat_key = self._room_chat_key(room_id)
        self.chat_history.setdefault(chat_key, [])
        self.bubble_frames.setdefault(chat_key, [])
        self.room_list.insert("end", f" # {room['name']}")

    def _remove_room_from_sidebar(self, room_id):
        room = self.rooms.pop(room_id, None)
        if not room:
            return
        items = list(self.room_list.get(0, "end"))
        target = f" # {room['name']}"
        if target in items:
            self.room_list.delete(items.index(target))
        chat_key = self._room_chat_key(room_id)
        if self.active_chat == chat_key:
            self._select_broadcast()

    def _build_chat_panel(self):
        self.chat_panel = tk.Frame(self.right, bg=self.BG_CHAT)

        self.chat_header = tk.Frame(self.chat_panel, bg=self.BG_CHAT, height=48)
        self.chat_header.pack(fill="x")
        self.chat_header.pack_propagate(False)
        tk.Frame(self.chat_panel, bg=self.SEPARATOR, height=1).pack(fill="x")
        header_text = f"@ {self.active_chat}" if self.active_chat and not self.active_chat.startswith("#") else (self.active_chat or "# alle")
        self.header_label = tk.Label(self.chat_header, text=header_text,
                                     font=FONT_TITLE, bg=self.BG_CHAT, fg=self.TEXT_MAIN,
                                     anchor="w", padx=16)
        self.header_label.pack(fill="both", expand=True)

        msg_frame = tk.Frame(self.chat_panel, bg=self.BG_CHAT)
        msg_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(msg_frame, bg=self.BG_CHAT, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        vscroll = tk.Scrollbar(msg_frame, orient="vertical", command=self.canvas.yview,
                               bg=self.BG_CHAT, troughcolor=self.BG_CHAT, relief="flat", bd=0, width=8)
        vscroll.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=vscroll.set)

        self.msg_inner = tk.Frame(self.canvas, bg=self.BG_CHAT)
        self.canvas_win = self.canvas.create_window((0, 0), window=self.msg_inner, anchor="nw")
        self.msg_inner.bind("<Configure>", lambda _: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self.canvas_win, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

        tk.Frame(self.chat_panel, bg=self.SEPARATOR, height=1).pack(fill="x")
        bottom = tk.Frame(self.chat_panel, bg=self.BG_CHAT, pady=12)
        bottom.pack(fill="x", side="bottom")

        input_wrap = tk.Frame(bottom, bg=self.BG_INPUT, padx=4, pady=4)
        input_wrap.pack(fill="x", padx=16)

        tk.Button(input_wrap, text="+", font=("Segoe UI", 13, "bold"),
                  bg=self.BG_INPUT, fg=self.TEXT_MUTED, relief="flat", bd=0,
                  activebackground=self.BG_INPUT, activeforeground=self.TEXT_MAIN,
                  cursor="hand2", command=self._attach_file, padx=6).pack(side="left")

        self.input_var = tk.StringVar()
        self.input_field = tk.Entry(input_wrap, textvariable=self.input_var,
                                    font=FONT_INPUT, bg=self.BG_INPUT, fg=self.TEXT_MAIN,
                                    insertbackground=self.TEXT_MAIN, relief="flat", bd=4,
                                    highlightthickness=0)
        self.input_field.pack(side="left", fill="x", expand=True)
        self.input_field.bind("<Return>", lambda _: self._send())

        tk.Button(input_wrap, text="Send", font=("Segoe UI", 9, "bold"),
                  bg=self.ACCENT, fg="white", relief="flat", bd=0,
                  activebackground=self.ACCENT_HOVER, activeforeground="white",
                  padx=12, pady=2, cursor="hand2", command=self._send).pack(side="right", padx=4)

    def _build_hub_panel(self):
        self.hub_panel = tk.Frame(self.right, bg=self.BG_CHAT)

        header = tk.Frame(self.hub_panel, bg=self.BG_CHAT, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🌐  Bruger Hub", font=FONT_TITLE,
                 bg=self.BG_CHAT, fg=self.TEXT_MAIN, anchor="w", padx=16).pack(fill="both", expand=True)
        tk.Frame(self.hub_panel, bg=self.SEPARATOR, height=1).pack(fill="x")

        self.hub_notice = tk.Label(self.hub_panel, text="", font=FONT_SMALL,
                                   bg=self.BG_CHAT, fg=self.WARNING)
        self.hub_notice.pack(pady=(6, 0))

        hub_scroll_frame = tk.Frame(self.hub_panel, bg=self.BG_CHAT)
        hub_scroll_frame.pack(fill="both", expand=True, padx=16, pady=12)

        hub_sb = tk.Scrollbar(hub_scroll_frame, bg=self.BG_CHAT, troughcolor=self.BG_CHAT,
                              relief="flat", bd=0, width=8)
        hub_sb.pack(side="right", fill="y")

        self.hub_canvas = tk.Canvas(hub_scroll_frame, bg=self.BG_CHAT,
                                    highlightthickness=0, bd=0,
                                    yscrollcommand=hub_sb.set)
        self.hub_canvas.pack(side="left", fill="both", expand=True)
        hub_sb.config(command=self.hub_canvas.yview)

        self.hub_inner = tk.Frame(self.hub_canvas, bg=self.BG_CHAT)
        self.hub_win = self.hub_canvas.create_window((0, 0), window=self.hub_inner, anchor="nw")
        self.hub_inner.bind("<Configure>", lambda _: self.hub_canvas.configure(
            scrollregion=self.hub_canvas.bbox("all")))
        self.hub_canvas.bind("<Configure>", lambda e: self.hub_canvas.itemconfig(
            self.hub_win, width=e.width))

    def _show_chat_panel(self):
        self.current_panel = "chat"
        self.hub_panel.pack_forget()
        self.chat_panel.pack(fill="both", expand=True)
        self.btn_chat.config(bg=self.ACCENT, fg="white")
        self.btn_hub.config(bg=self.BG_PANEL, fg=self.TEXT_MUTED)

    def _show_hub_panel(self):
        self.current_panel = "hub"
        self.chat_panel.pack_forget()
        self.hub_panel.pack(fill="both", expand=True)
        self.btn_hub.config(bg=self.ACCENT, fg="white")
        self.btn_chat.config(bg=self.BG_PANEL, fg=self.TEXT_MUTED)
        send_msg(self.sock, {"type": "get_user_hub"})

    def _populate_hub(self, users):
        for child in self.hub_inner.winfo_children():
            child.destroy()

        if not users:
            tk.Label(self.hub_inner, text="Ingen andre brugere registreret endnu.",
                     font=FONT_BODY, bg=self.BG_CHAT, fg=self.TEXT_MUTED).pack(pady=20)
            return

        header_row = tk.Frame(self.hub_inner, bg=self.BG_PANEL)
        header_row.pack(fill="x", pady=(0, 4))
        for text, w in [("Bruger", 180), ("Status", 80), ("Sidst set", 160), ("Venner", 120)]:
            tk.Label(header_row, text=text, font=("Segoe UI", 9, "bold"),
                     bg=self.BG_PANEL, fg=self.TEXT_MUTED, width=w // 8, anchor="w",
                     padx=8, pady=6).pack(side="left")

        for u in users:
            name       = u["username"]
            online     = u["online"]
            last_seen  = format_last_seen(u.get("last_seen"))
            friendship = u.get("friendship", "none")

            row = tk.Frame(self.hub_inner, bg=self.BG_PANEL, pady=0)
            row.pack(fill="x", pady=2)

            dot_color   = self.ONLINE_DOT if online else self.DANGER
            status_text = "Online" if online else "Offline"

            tk.Label(row, text=f"● {name}", font=FONT_NAME,
                     bg=self.BG_PANEL, fg=self.TEXT_MAIN, anchor="w",
                     padx=8, pady=8, width=20).pack(side="left")

            tk.Label(row, text=status_text, font=FONT_SMALL,
                     bg=self.BG_PANEL, fg=dot_color, anchor="w",
                     padx=8, width=10).pack(side="left")

            tk.Label(row, text=last_seen, font=FONT_SMALL,
                     bg=self.BG_PANEL, fg=self.TEXT_MUTED, anchor="w",
                     padx=8, width=20).pack(side="left")

            action_frame = tk.Frame(row, bg=self.BG_PANEL)
            action_frame.pack(side="left", padx=8)

            if friendship == "friends":
                tk.Label(action_frame, text="✓ Venner", font=FONT_SMALL,
                         bg=self.BG_PANEL, fg=self.ONLINE_DOT).pack(side="left", padx=(0, 6))
                tk.Button(action_frame, text="Fjern ven",
                          font=FONT_SMALL, bg=self.DANGER, fg="white",
                          relief="flat", bd=0, cursor="hand2",
                          activebackground="#c0392b", activeforeground="white",
                          padx=8, pady=3,
                          command=lambda n=name: self._unfriend(n)).pack(side="left")

            elif friendship == "pending_sent":
                tk.Label(action_frame, text="⏳ Afventer svar", font=FONT_SMALL,
                         bg=self.BG_PANEL, fg=self.WARNING).pack(side="left")

            elif friendship == "pending_received":
                tk.Label(action_frame, text="Anmodning fra dem:", font=FONT_SMALL,
                         bg=self.BG_PANEL, fg=self.TEXT_MUTED).pack(side="left", padx=(0, 6))
                tk.Button(action_frame, text="✓ Accepter",
                          font=FONT_SMALL, bg=self.ONLINE_DOT, fg="white",
                          relief="flat", bd=0, cursor="hand2",
                          activebackground="#1a8c47", activeforeground="white",
                          padx=8, pady=3,
                          command=lambda n=name: self._respond_request(n, True)
                          ).pack(side="left", padx=(0, 4))
                tk.Button(action_frame, text="✗ Afvis",
                          font=FONT_SMALL, bg=self.DANGER, fg="white",
                          relief="flat", bd=0, cursor="hand2",
                          activebackground="#c0392b", activeforeground="white",
                          padx=8, pady=3,
                          command=lambda n=name: self._respond_request(n, False)
                          ).pack(side="left")
            else:
                tk.Button(action_frame, text="+ Tilføj ven",
                          font=FONT_SMALL, bg=self.ACCENT, fg="white",
                          relief="flat", bd=0, cursor="hand2",
                          activebackground=self.ACCENT_HOVER, activeforeground="white",
                          padx=8, pady=3,
                          command=lambda n=name: self._send_friend_request(n)
                          ).pack(side="left")

    def _send_friend_request(self, username):
        send_msg(self.sock, {"type": "friend_request", "username": username})

    def _respond_request(self, requester, accepted):
        send_msg(self.sock, {"type": "friend_response", "from": requester, "accepted": accepted})

    def _unfriend(self, username):
        if messagebox.askyesno("Fjern ven", f"Er du sikker på, at du vil fjerne {username} som ven?"):
            send_msg(self.sock, {"type": "unfriend", "username": username})

    def _tick(self):
        self.date_label.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M"))
        self.after(30000, self._tick)

    def _chat_key(self):
        return self.active_chat if self.active_chat is not None else "#alle"

    def _store_message(self, chat_key, payload):
        self.chat_history.setdefault(chat_key, []).append(payload)
        self.bubble_frames.setdefault(chat_key, []).append(None)

    def _refresh_chat(self):
        self._photo_refs.clear()
        for child in self.msg_inner.winfo_children():
            child.destroy()
        key = self._chat_key()
        self.bubble_frames[key] = []
        for i, msg in enumerate(self.chat_history.get(key, [])):
            frame = self._render_bubble(
                msg["content"], sender=msg["sender"], timestamp=msg["timestamp"],
                is_file=msg["is_file"], filename=msg.get("filename"),
                file_data=msg.get("file_data"), is_system=msg.get("is_system", False),
                is_image=msg.get("is_image", False),
                msg_index=i, chat_key=key
            )
            self.bubble_frames[key].append(frame)
        self._scroll_bottom()

    def _on_friend_select(self, _=None):
        sel = self.friend_list.curselection()
        if not sel:
            return
        name = self.friend_list.get(sel[0]).lstrip("● ").strip()
        self.active_chat = name
        self.header_label.config(text=f"@ {name}")
        self._show_chat_panel()
        self._refresh_chat()

    def _on_friend_right_click(self, event):
        idx = self.friend_list.nearest(event.y)
        if idx < 0:
            return
        name = self.friend_list.get(idx).lstrip("● ").strip()
        menu = tk.Menu(self, tearoff=0, bg=self.BG_PANEL, fg=self.TEXT_MAIN,
                       activebackground=self.ACCENT, activeforeground="white",
                       relief="flat", bd=0)
        menu.add_command(label=f"Fjern {name} som ven",
                         command=lambda: self._unfriend(name))
        menu.tk_popup(event.x_root, event.y_root)

    def _select_broadcast(self):
        self.active_chat = None
        self.friend_list.selection_clear(0, "end")
        self.room_list.selection_clear(0, "end")
        self.header_label.config(text="# alle")
        self._show_chat_panel()
        self._refresh_chat()

    def _attach_file(self):
        path = filedialog.askopenfilename(
            title="Vælg fil",
            filetypes=[("Billeder", "*.png *.gif"), ("Alle filer", "*.*")]
        )
        if not path:
            return
        fname = os.path.basename(path)
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            self._add_bubble(f"Fejl ved fillæsning: {e}", sender="system",
                             timestamp="", is_system=True)
            return
        if len(raw) > MAX_FILE_SIZE:
            self._add_bubble(
                f"Filen er for stor; maks. filstørrelse er {MAX_FILE_SIZE // 1024} KB.",
                sender="system", timestamp="", is_system=True)
            return
        encoded  = base64.b64encode(raw).decode("utf-8")
        is_image = is_image_filename(fname)
        payload  = {"type": "file", "filename": fname, "data": encoded, "is_image": is_image}
        ck = self._chat_key()
        if ck.startswith("#rum:"):
            payload["room_id"] = int(ck.split(":")[1])
        elif self.active_chat is not None:
            payload["recipient"] = self.active_chat
        send_msg(self.sock, payload)

    def _download_file(self, filename, data):
        if not filename or not data:
            messagebox.showerror("Download fejl", "Ingen fildata tilgængelig.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Gem fil som",
            initialfile=filename,
            defaultextension=os.path.splitext(filename)[1] or ""
        )
        if not save_path:
            return
        try:
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(data))
            messagebox.showinfo("Download færdig", f"Filen er gemt som:\n{save_path}")
        except OSError as e:
            messagebox.showerror("Download fejl", f"Kunne ikke gemme filen:\n{e}")

    def _render_bubble(self, content, sender, timestamp, is_file=False,
                       is_system=False, filename=None, file_data=None,
                       is_image=False, msg_index=None, chat_key=None):
        outer = tk.Frame(self.msg_inner, bg=self.BG_CHAT)
        outer.pack(fill="x", padx=16, pady=2)

        if is_system:
            tk.Label(outer, text=content, font=FONT_SMALL,
                     bg=self.BG_CHAT, fg=self.BUBBLE_SYS).pack(pady=2)
            self._scroll_bottom()
            return outer

        is_me = (sender == self.username)
        bg    = self.BUBBLE_ME if is_me else self.BUBBLE_OTHER
        fg    = "#ffffff" if is_me else self.TEXT_MAIN
        align = "e" if is_me else "w"

        meta = tk.Frame(outer, bg=self.BG_CHAT)
        meta.pack(anchor=align)
        if not is_me:
            tk.Label(meta, text=sender, font=FONT_NAME,
                     bg=self.BG_CHAT, fg=self.ACCENT).pack(side="left", padx=(0, 6))
        tk.Label(meta, text=timestamp, font=FONT_SMALL,
                 bg=self.BG_CHAT, fg=self.TEXT_TIME).pack(side="left")

        if is_me and msg_index is not None and chat_key is not None:
            del_btn = tk.Label(meta, text="🗑", font=FONT_SMALL,
                               bg=self.BG_CHAT, fg=self.TEXT_MUTED, cursor="hand2")
            del_btn.pack(side="left", padx=(6, 0))
            del_btn.bind("<Button-1>", lambda _, i=msg_index, k=chat_key: self._delete_message(i, k))
            del_btn.bind("<Enter>", lambda e: e.widget.config(fg=self.DANGER))
            del_btn.bind("<Leave>", lambda e: e.widget.config(fg=self.TEXT_MUTED))

        bubble = tk.Frame(outer, bg=self.BG_CHAT)
        bubble.pack(anchor=align)

        if is_file and is_image and file_data:
            photo = make_photo(file_data)
            if photo is not None:
                self._photo_refs.append(photo)
                img_frame = tk.Frame(bubble, bg=bg, padx=4, pady=4)
                img_frame.pack()
                img_label = tk.Label(img_frame, image=photo, bg=bg, cursor="hand2")
                img_label.pack()
                tk.Label(img_frame, text=filename or content, font=FONT_SMALL,
                         bg=bg, fg=fg, pady=2).pack()
                img_label.bind("<Button-1>",
                               lambda _, fn=filename, fd=file_data: self._download_file(fn, fd))
            else:
                self._render_file_download_row(bubble, content, bg, fg, filename, file_data)
        elif is_file:
            self._render_file_download_row(bubble, content, bg, fg, filename, file_data)
        else:
            tk.Label(bubble, text=content, font=FONT_BODY, bg=bg, fg=fg,
                     wraplength=420, justify="left", padx=12, pady=7,
                     relief="flat").pack()

        self._scroll_bottom()
        return outer

    def _render_file_download_row(self, parent, content, bg, fg, filename, file_data):
        row = tk.Frame(parent, bg=bg)
        row.pack()
        tk.Label(row, text=content, font=FONT_BODY, bg=bg, fg=fg,
                 wraplength=360, justify="left", padx=12, pady=7,
                 relief="flat").pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Download", font=FONT_BODY,
                  bg=self.ACCENT, fg="white", relief="flat", bd=0,
                  activebackground=self.ACCENT_HOVER, activeforeground="white",
                  cursor="hand2",
                  command=lambda: self._download_file(filename, file_data)
                  ).pack(side="right", padx=8, pady=7)

    def _delete_message(self, msg_index, chat_key):
        history = self.chat_history.get(chat_key, [])
        if msg_index >= len(history):
            return
        msg = history[msg_index]
        if msg.get("sender") != self.username:
            return
        msg_id = msg.get("msg_id")
        if msg_id is None:
            return
        payload = {"type": "delete", "msg_id": msg_id}
        if chat_key.startswith("#rum:"):
            payload["room_id"] = int(chat_key.split(":")[1])
        elif chat_key != "#alle":
            payload["recipient"] = chat_key
        send_msg(self.sock, payload)

    def _remove_message_locally(self, msg_id, chat_key):
        history = self.chat_history.get(chat_key, [])
        self.chat_history[chat_key] = [m for m in history if m.get("msg_id") != msg_id]
        if chat_key == self._chat_key():
            self._refresh_chat()

    def _add_bubble(self, content, sender, timestamp, is_file=False,
                    is_system=False, filename=None, file_data=None,
                    chat_key=None, store=True, msg_id=None, is_image=False):
        if is_system:
            self._render_bubble(content, sender, timestamp,
                                is_file=is_file, is_system=True,
                                filename=filename, file_data=file_data)
            return

        if chat_key is None:
            chat_key = self._chat_key()

        payload = {
            "content": content, "sender": sender, "timestamp": timestamp,
            "is_file": is_file, "filename": filename, "file_data": file_data,
            "msg_id": msg_id, "is_image": is_image,
        }
        if store:
            self._store_message(chat_key, payload)
            msg_index = len(self.chat_history[chat_key]) - 1
        else:
            msg_index = None

        if chat_key == self._chat_key():
            frame = self._render_bubble(content, sender, timestamp,
                                        is_file=is_file, filename=filename,
                                        file_data=file_data, is_image=is_image,
                                        msg_index=msg_index, chat_key=chat_key)
            if store:
                self.bubble_frames.setdefault(chat_key, [])
                if len(self.bubble_frames[chat_key]) < len(self.chat_history[chat_key]):
                    self.bubble_frames[chat_key].append(frame)
                else:
                    self.bubble_frames[chat_key][msg_index] = frame

    def _scroll_bottom(self):
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

    def _ensure_friend(self, name):
        if name == self.username or name not in self.friends:
            return
        existing = list(self.friend_list.get(0, "end"))
        display  = f" {name}"
        if display not in existing:
            self.friend_list.insert("end", display)
            idx = self.friend_list.size() - 1
            self.friend_list.itemconfig(idx, fg=self.DANGER)
            self.user_status[name] = False

    def _set_friend_status(self, name, online: bool):
        if name == self.username or name not in self.friends:
            return
        existing = list(self.friend_list.get(0, "end"))
        display  = f" {name}"
        if display not in existing:
            return
        idx   = existing.index(display)
        color = self.ONLINE_DOT if online else self.DANGER
        self.friend_list.itemconfig(idx, fg=color)
        self.user_status[name] = online

    def _add_friend_to_sidebar(self, name):
        if name == self.username:
            return
        self.friends.add(name)
        existing = list(self.friend_list.get(0, "end"))
        display  = f" {name}"
        if display not in existing:
            self.friend_list.insert("end", display)
            idx = self.friend_list.size() - 1
            online = self.user_status.get(name, False)
            self.friend_list.itemconfig(idx, fg=self.ONLINE_DOT if online else self.DANGER)

    def _remove_friend_from_sidebar(self, name):
        self.friends.discard(name)
        self.pending_sent.discard(name)
        self.pending_received.discard(name)
        existing = list(self.friend_list.get(0, "end"))
        display  = f" {name}"
        if display in existing:
            self.friend_list.delete(existing.index(display))

    def _show_hub_notice(self, text, color=None):
        self.hub_notice.config(text=text, fg=color or self.WARNING)
        self.after(4000, lambda: self.hub_notice.config(text=""))

    def _start_listener(self):
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        while not self.stop_event.is_set():
            try:
                chunk = self.sock.recv(BUFFER_SIZE).decode("utf-8")
            except OSError:
                break
            if not chunk:
                self.after(0, lambda: self._add_bubble(
                    "Server lukkede forbindelsen.", sender="system",
                    timestamp="", is_system=True))
                self.stop_event.set()
                break
            self.buf += chunk
            while "\n" in self.buf:
                line, self.buf = self.buf.split("\n", 1)
                line = line.strip()
                if line:
                    try:
                        self.after(0, self._handle_msg, json.loads(line))
                    except json.JSONDecodeError:
                        pass

    def _handle_msg(self, msg):
        t = msg.get("type")

        if t == "connected":
            token = msg.get("token", "")
            if token:
                session = load_session()
                session.update({"username": self.username, "ip": self.ip, "token": token})
                save_session(session)
            for name in msg.get("friends", []):
                self.friends.add(name)
                self.chat_history.setdefault(name, [])
                self.bubble_frames.setdefault(name, [])
            for name in msg.get("pending_requests", []):
                self.pending_received.add(name)
            self._add_bubble(msg.get("msg", ""), sender="system", timestamp="", is_system=True)

        elif t == "auth_error":
            self._add_bubble(f"Auth fejl: {msg.get('msg','')}", sender="system",
                             timestamp="", is_system=True)

        elif t == "username_changed":
            old_username = msg.get("old_username", "")
            new_username = msg.get("new_username", "")
            new_token    = msg.get("token", "")
            self.username = new_username
            self.token    = new_token

            if new_token:
                session = load_session()
                session.update({"username": new_username, "ip": self.ip, "token": new_token})
                save_session(session)

            if hasattr(self, "username_label"):
                self.username_label.config(text=f"  {new_username}")
            self.title("Chat")

            old_history = self.chat_history.pop(old_username, [])
            old_bubbles = self.bubble_frames.pop(old_username, [])
            if old_history:
                self.chat_history[new_username] = old_history
                self.bubble_frames[new_username] = old_bubbles

            if self.active_chat == old_username:
                self.active_chat = new_username
                if hasattr(self, "header_label"):
                    self.header_label.config(text=f"@ {new_username}")

            self._add_bubble(
                f"Brugernavn ændret fra '{old_username}' til '{new_username}'.",
                sender="system", timestamp="", is_system=True
            )

            if hasattr(self, "_pending_change_dialog"):
                try:
                    self._pending_change_dialog.destroy()
                except Exception:
                    pass
                del self._pending_change_dialog
            if hasattr(self, "_pending_change_status"):
                del self._pending_change_status

        elif t == "change_username_error":
            error_msg = msg.get("msg", "Ukendt fejl.")
            if hasattr(self, "_pending_change_status"):
                try:
                    self._pending_change_status.config(text=error_msg, fg=self.DANGER)
                except Exception:
                    pass
            else:
                self._add_bubble(f"Fejl: {error_msg}", sender="system", timestamp="", is_system=True)

        elif t == "username_changed_broadcast":
            old_username = msg.get("old_username", "")
            new_username = msg.get("new_username", "")

            if old_username in self.friends:
                self.friends.discard(old_username)
                self.friends.add(new_username)
                existing = list(self.friend_list.get(0, "end"))
                display_old = f" {old_username}"
                display_new = f" {new_username}"
                if display_old in existing:
                    idx = existing.index(display_old)
                    online = self.user_status.pop(old_username, False)
                    self.user_status[new_username] = online
                    self.friend_list.delete(idx)
                    self.friend_list.insert(idx, display_new)
                    self.friend_list.itemconfig(idx, fg=self.ONLINE_DOT if online else self.DANGER)

            old_history = self.chat_history.pop(old_username, [])
            old_bubbles = self.bubble_frames.pop(old_username, [])
            if old_history:
                self.chat_history[new_username] = old_history
                self.bubble_frames[new_username] = old_bubbles

            if self.active_chat == old_username:
                self.active_chat = new_username
                if hasattr(self, "header_label"):
                    self.header_label.config(text=f"@ {new_username}")

            self._add_bubble(
                f"{old_username} hedder nu {new_username}.",
                sender="system", timestamp="", is_system=True
            )

        elif t == "my_rooms":
            for room in msg.get("rooms", []):
                self._add_room_to_sidebar(room)
            for invite in msg.get("invites", []):
                self._handle_room_invite(invite["room_id"], invite["room_name"], invite["inviter"])

        elif t == "room_created":
            room = msg.get("room", {})
            self._add_room_to_sidebar(room)
            self._add_bubble(f"Chatrum '#{room['name']}' oprettet!", sender="system", timestamp="", is_system=True)

        elif t == "room_joined":
            room = msg.get("room", {})
            self._add_room_to_sidebar(room)
            self._add_bubble(f"Du er nu med i '#{room['name']}'!", sender="system", timestamp="", is_system=True)

        elif t == "room_left":
            room_id = msg.get("room_id")
            self._remove_room_from_sidebar(room_id)

        elif t == "room_member_joined":
            room_id   = msg.get("room_id")
            room_name = msg.get("room_name", "")
            username  = msg.get("username", "")
            if room_id in self.rooms:
                if username not in self.rooms[room_id]["members"]:
                    self.rooms[room_id]["members"].append(username)
            self._add_bubble(f"{username} joined #{room_name}", sender="system",
                             timestamp="", is_system=True)

        elif t == "room_member_left":
            room_id   = msg.get("room_id")
            username  = msg.get("username", "")
            room_name = msg.get("room_name", "")
            if room_id in self.rooms:
                self.rooms[room_id]["members"] = [m for m in self.rooms[room_id]["members"] if m != username]
            self._add_bubble(f"{username} forlod #{room_name}", sender="system",
                             timestamp="", is_system=True)

        elif t == "room_invite":
            self._handle_room_invite(msg.get("room_id"), msg.get("room_name", ""), msg.get("inviter", ""))

        elif t == "room_invite_sent":
            room_name = msg.get("room_name", "")
            invitee   = msg.get("invitee", "")
            self._show_hub_notice(f"Invitation sendt til {invitee} for #{room_name}!", self.ONLINE_DOT)

        elif t == "room_invite_declined":
            username  = msg.get("username", "")
            room_name = msg.get("room_name", "")
            self._show_hub_notice(f"{username} afslog invitation til #{room_name}.", self.DANGER)

        elif t == "message":
            sender    = msg.get("sender", "?")
            content   = msg.get("content", "")
            ts        = msg.get("timestamp", "")
            msg_id    = msg.get("msg_id")
            recipient = msg.get("recipient")
            room_id   = msg.get("room_id")

            if room_id:
                chat_key = self._room_chat_key(room_id)
                if sender != self.username:
                    room_name = self.rooms.get(room_id, {}).get("name", str(room_id))
                    self._notify_group(sender=sender, content=f"[#{room_name}] {content}")
                if chat_key == self._chat_key():
                    self._add_bubble(content, sender=sender, timestamp=ts,
                                     chat_key=chat_key, msg_id=msg_id)
                else:
                    self._store_message(chat_key, {
                        "content": content, "sender": sender, "timestamp": ts,
                        "is_file": False, "filename": None, "file_data": None,
                        "msg_id": msg_id, "is_image": False,
                    })
            else:
                chat_key = (sender if sender != self.username else recipient) if recipient else "#alle"
                if sender != self.username:
                    self._notify_group(sender=sender, content=content)
                if chat_key == self._chat_key():
                    self._add_bubble(content, sender=sender, timestamp=ts,
                                     chat_key=chat_key, msg_id=msg_id)
                else:
                    self._store_message(chat_key, {
                        "content": content, "sender": sender, "timestamp": ts,
                        "is_file": False, "filename": None, "file_data": None,
                        "msg_id": msg_id, "is_image": False,
                    })

        elif t == "file":
            sender    = msg.get("sender", "?")
            filename  = msg.get("filename", "fil")
            data      = msg.get("data", "")
            ts        = msg.get("timestamp", "")
            msg_id    = msg.get("msg_id")
            is_image  = msg.get("is_image", False) or is_image_filename(filename)
            recipient = msg.get("recipient")
            room_id   = msg.get("room_id")

            if room_id:
                chat_key = self._room_chat_key(room_id)
                if sender != self.username:
                    room_name = self.rooms.get(room_id, {}).get("name", str(room_id))
                    self._notify_group(sender=sender, content=f"[#{room_name}] Sendte en fil: {filename}")
                if chat_key == self._chat_key():
                    self._add_bubble(filename, sender=sender, timestamp=ts,
                                     is_file=True, filename=filename, file_data=data,
                                     is_image=is_image, chat_key=chat_key, msg_id=msg_id)
                else:
                    self._store_message(chat_key, {
                        "content": filename, "sender": sender, "timestamp": ts,
                        "is_file": True, "filename": filename, "file_data": data,
                        "msg_id": msg_id, "is_image": is_image,
                    })
            else:
                chat_key = (sender if sender != self.username else recipient) if recipient else "#alle"
                if sender != self.username:
                    self._notify_group(sender=sender, content=f"Sendte en fil: {filename}")
                if chat_key == self._chat_key():
                    self._add_bubble(filename, sender=sender, timestamp=ts,
                                     is_file=True, filename=filename, file_data=data,
                                     is_image=is_image, chat_key=chat_key, msg_id=msg_id)
                else:
                    self._store_message(chat_key, {
                        "content": filename, "sender": sender, "timestamp": ts,
                        "is_file": True, "filename": filename, "file_data": data,
                        "msg_id": msg_id, "is_image": is_image,
                    })

        elif t == "deleted":
            msg_id   = msg.get("msg_id")
            chat_key = msg.get("chat_key", "#alle")
            if msg_id:
                self._remove_message_locally(msg_id, chat_key)

        elif t == "system":
            self._add_bubble(msg.get("msg", ""), sender="system", timestamp="", is_system=True)

        elif t == "presence":
            event = msg.get("event")
            if event == "list":
                for name in msg.get("users", []):
                    self.user_status[name] = True
                    self._ensure_friend(name)
                    self._set_friend_status(name, True)
            elif event == "online":
                name = msg.get("username", "?")
                self.user_status[name] = True
                self._ensure_friend(name)
                self._set_friend_status(name, True)
            elif event == "offline":
                name = msg.get("username", "?")
                self.user_status[name] = False
                self._set_friend_status(name, False)

        elif t == "friend_request":
            requester = msg.get("from", "?")
            self.pending_received.add(requester)
            self._notify_group(sender=requester, content="Sendte dig en venneanmodning")
            self._add_bubble(
                f" {requester} har sendt dig en venneanmodning. Gå til Bruger Hub for at svare.",
                sender="system", timestamp="", is_system=True
            )

        elif t == "friend_request_sent":
            to = msg.get("to", "?")
            self.pending_sent.add(to)
            self._show_hub_notice(f"Venneanmodning sendt til {to}!", self.ONLINE_DOT)
            if self.current_panel == "hub":
                send_msg(self.sock, {"type": "get_user_hub"})

        elif t == "friend_accepted":
            other = msg.get("username", "?")
            self.friends.add(other)
            self.pending_sent.discard(other)
            self.pending_received.discard(other)
            self.chat_history.setdefault(other, [])
            self.bubble_frames.setdefault(other, [])
            self._add_friend_to_sidebar(other)
            self._set_friend_status(other, self.user_status.get(other, False))
            self._add_bubble(
                f" Du og {other} er nu venner!",
                sender="system", timestamp="", is_system=True
            )
            if self.current_panel == "hub":
                send_msg(self.sock, {"type": "get_user_hub"})

        elif t == "friend_declined":
            other = msg.get("username", "?")
            self.pending_sent.discard(other)
            self.pending_received.discard(other)
            self._show_hub_notice(f"{other} afslog venneanmodningen.", self.DANGER)
            if self.current_panel == "hub":
                send_msg(self.sock, {"type": "get_user_hub"})

        elif t == "unfriended":
            other = msg.get("username", "?")
            self._remove_friend_from_sidebar(other)
            self._add_bubble(
                f"Du og {other} er ikke længere venner.",
                sender="system", timestamp="", is_system=True
            )
            if self.current_panel == "hub":
                send_msg(self.sock, {"type": "get_user_hub"})

        elif t == "user_hub_data":
            self._populate_hub(msg.get("users", []))

        elif t in ("welcome",):
            self._add_bubble(msg.get("msg", ""), sender="system", timestamp="", is_system=True)

        elif t == "error":
            self._add_bubble(f"Fejl: {msg.get('msg','')}", sender="system",
                             timestamp="", is_system=True)
            if hasattr(self, "_pending_change_status"):
                try:
                    self._pending_change_status.config(text=msg.get("msg", ""), fg=self.DANGER)
                except Exception:
                    pass
            if self.current_panel == "hub":
                self._show_hub_notice(msg.get("msg", ""), self.DANGER)

        elif t == "disconnected":
            self.after(200, self._on_close)

    def _handle_room_invite(self, room_id, room_name, inviter):
        self._notify_group(sender=inviter, content=f"Inviterede dig til #{room_name}")
        self._add_bubble(
            f"{inviter} inviterede dig til chatrum '#{room_name}'. Accepter eller afvis:",
            sender="system", timestamp="", is_system=True
        )

        bar = tk.Frame(self.msg_inner, bg=self.BG_CHAT)
        bar.pack(fill="x", padx=16, pady=4)

        tk.Label(bar, text=f"#{room_name}", font=FONT_NAME,
                 bg=self.BG_CHAT, fg=self.ACCENT).pack(side="left", padx=(0, 10))

        def accept():
            bar.destroy()
            send_msg(self.sock, {"type": "room_invite_response", "room_id": room_id, "accepted": True})

        def decline():
            bar.destroy()
            send_msg(self.sock, {"type": "room_invite_response", "room_id": room_id, "accepted": False})

        tk.Button(bar, text="✓ Accepter", font=FONT_SMALL,
                  bg=self.ONLINE_DOT, fg="white", relief="flat", bd=0,
                  cursor="hand2", padx=10, pady=4,
                  command=accept).pack(side="left", padx=(0, 6))
        tk.Button(bar, text="✗ Afvis", font=FONT_SMALL,
                  bg=self.DANGER, fg="white", relief="flat", bd=0,
                  cursor="hand2", padx=10, pady=4,
                  command=decline).pack(side="left")
        self._scroll_bottom()

    def _send(self):
        text = self.input_var.get().strip()
        if not text:
            return
        self.input_var.set("")
        ck = self._chat_key()
        payload = {"type": "message", "content": text}
        if ck.startswith("#rum:"):
            payload["room_id"] = int(ck.split(":")[1])
        elif self.active_chat is not None:
            payload["recipient"] = self.active_chat
        send_msg(self.sock, payload)

    def _on_close(self):
        self.music.stop()
        try:
            send_msg(self.sock, {"type": "disconnect"})
        except OSError:
            pass
        self.stop_event.set()
        try:
            self.sock.close()
        except OSError:
            pass
        self.destroy()


if __name__ == "__main__":
    LoginWindow().mainloop()