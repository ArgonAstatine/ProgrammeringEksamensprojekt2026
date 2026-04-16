import socket
import threading
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from cryptography.fernet import Fernet
import base64


PORT = 5555
BUFFER_SIZE        = 4096
MAX_MESSAGE_LENGTH = 2048
MAX_FILE_SIZE      = 1 * 1024 * 1024
SESSION_PATH     = "session.json.enc"
SESSION_KEY_PATH = "session.key"

BG_DARK      = "#1e1f22"
BG_PANEL     = "#2b2d31"
BG_CHAT      = "#313338"
BG_INPUT     = "#383a40"
ACCENT       = "#5865f2"
ACCENT_HOVER = "#4752c4"
TEXT_MAIN    = "#dbdee1"
TEXT_MUTED   = "#80848e"
TEXT_TIME    = "#80848e"
BUBBLE_ME    = "#5865f2"
BUBBLE_OTHER = "#2e3035"
BUBBLE_SYS   = "#80848e"
ONLINE_DOT   = "#23a55a"
SEPARATOR    = "#3f4147"
DANGER       = "#f04747"
WARNING      = "#faa61a"

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


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chat: Log ind")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self._center(360, 370)

        session = load_session()

        tk.Label(self, text="Velkommen!", font=("Segoe UI", 18, "bold"),
                 bg=BG_DARK, fg=TEXT_MAIN).pack(pady=(24, 4))

        tk.Label(self, text="SERVER IP", font=("Segoe UI", 8, "bold"),
                 bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", padx=50)
        self.ip_var = tk.StringVar(value=session.get("ip", "127.0.0.1"))
        tk.Entry(self, textvariable=self.ip_var, font=FONT_INPUT,
                 bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                 relief="flat", bd=8).pack(padx=50, fill="x", pady=(2, 10))

        tk.Label(self, text="BRUGERNAVN", font=("Segoe UI", 8, "bold"),
                 bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", padx=50)
        self.username_var = tk.StringVar()
        name_entry = tk.Entry(self, textvariable=self.username_var, font=FONT_INPUT,
                              bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                              relief="flat", bd=8)
        name_entry.pack(padx=50, fill="x", pady=(2, 10))

        tk.Label(self, text="ADGANGSKODE", font=("Segoe UI", 8, "bold"),
                 bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", padx=50)
        self.pw_var = tk.StringVar()
        pw_entry = tk.Entry(self, textvariable=self.pw_var, font=FONT_INPUT,
                            bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                            relief="flat", bd=8, show="•")
        pw_entry.pack(padx=50, fill="x", pady=(2, 6))
        pw_entry.bind("<Return>", lambda _: self._login())

        name_entry.focus()

        self.status = tk.Label(self, text="", font=FONT_SMALL, bg=BG_DARK, fg=DANGER)
        self.status.pack()

        tk.Button(self, text="Log ind / Opret konto", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT, fg="white", relief="flat", bd=0,
                  activebackground=ACCENT_HOVER, activeforeground="white",
                  padx=20, pady=8, cursor="hand2", command=self._login
                  ).pack(pady=8, padx=50, fill="x")

        tk.Label(self, text="Nyt brugernavn? Konto oprettes automatisk.",
                 font=FONT_SMALL, bg=BG_DARK, fg=TEXT_MUTED).pack()

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
        self.sock        = sock
        self.username    = username
        self.password    = password
        self.token       = token
        self.ip          = ip
        self.active_chat = None
        self.stop_event  = threading.Event()
        self.buf         = ""
        self.user_status     = {}
        self.chat_history    = {"#alle": []}
        self.bubble_frames   = {"#alle": []}
        self.friends         = set()
        self.pending_sent    = set()
        self.pending_received = set()
        self.current_panel   = "chat"

        self.title("Chat")
        self.configure(bg=BG_DARK)
        self.geometry("1100x680")
        self._center()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._start_listener()

        if token:
            send_msg(self.sock, {"type": "connect", "token": token})
        else:
            send_msg(self.sock, {"type": "connect", "username": username, "password": password})

        self._tick()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1100) // 2
        y = (self.winfo_screenheight() - 680) // 2
        self.geometry(f"1100x680+{x}+{y}")

    def _build_ui(self):
        self.left = tk.Frame(self, bg=BG_PANEL, width=220)
        self.left.pack(side="left", fill="y")
        self.left.pack_propagate(False)

        top_bar = tk.Frame(self.left, bg=BG_DARK, height=48)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)
        tk.Label(top_bar, text=f"  {self.username}", font=FONT_TITLE,
                 bg=BG_DARK, fg=TEXT_MAIN, anchor="w").pack(side="left", fill="y", padx=4)

        self.date_label = tk.Label(self.left, text="", font=FONT_SMALL,
                                   bg=BG_PANEL, fg=TEXT_MUTED)
        self.date_label.pack(pady=(8, 2))

        tk.Frame(self.left, bg=SEPARATOR, height=1).pack(fill="x", padx=10, pady=4)

        nav_frame = tk.Frame(self.left, bg=BG_PANEL)
        nav_frame.pack(fill="x", padx=8, pady=(0, 4))

        self.btn_chat = tk.Button(nav_frame, text="💬  Chat", font=("Segoe UI", 9, "bold"),
                                  bg=ACCENT, fg="white", relief="flat", bd=0,
                                  activebackground=ACCENT_HOVER, activeforeground="white",
                                  anchor="w", padx=10, pady=5, cursor="hand2",
                                  command=self._show_chat_panel)
        self.btn_chat.pack(fill="x", pady=2)

        self.btn_hub = tk.Button(nav_frame, text="🌐  Bruger Hub", font=("Segoe UI", 9, "bold"),
                                 bg=BG_PANEL, fg=TEXT_MUTED, relief="flat", bd=0,
                                 activebackground="#35373c", activeforeground=TEXT_MAIN,
                                 anchor="w", padx=10, pady=5, cursor="hand2",
                                 command=self._show_hub_panel)
        self.btn_hub.pack(fill="x", pady=2)

        tk.Frame(self.left, bg=SEPARATOR, height=1).pack(fill="x", padx=10, pady=4)

        tk.Label(self.left, text="  VENNELISTE", font=("Segoe UI", 8, "bold"),
                 bg=BG_PANEL, fg=TEXT_MUTED, anchor="w").pack(fill="x", padx=8, pady=(0, 4))

        list_frame = tk.Frame(self.left, bg=BG_PANEL)
        list_frame.pack(fill="both", expand=True, padx=4)

        sb = tk.Scrollbar(list_frame, bg=BG_PANEL, troughcolor=BG_PANEL,
                          relief="flat", bd=0, width=6)
        sb.pack(side="right", fill="y")

        self.friend_list = tk.Listbox(
            list_frame, bg=BG_PANEL, fg=TEXT_MAIN,
            font=FONT_BODY, relief="flat", bd=0,
            selectbackground="#35373c", selectforeground=TEXT_MAIN,
            activestyle="none", yscrollcommand=sb.set,
            highlightthickness=0
        )
        self.friend_list.pack(fill="both", expand=True)
        sb.config(command=self.friend_list.yview)
        self.friend_list.bind("<<ListboxSelect>>", self._on_friend_select)
        self.friend_list.bind("<Button-3>", self._on_friend_right_click)

        broadcast_row = tk.Frame(self.left, bg=BG_PANEL, cursor="hand2")
        broadcast_row.pack(fill="x", padx=8, pady=(0, 8))
        broadcast_label = tk.Label(broadcast_row, text="  # alle", font=FONT_BODY,
                                   bg=BG_PANEL, fg=TEXT_MUTED, anchor="w", pady=5)
        broadcast_label.pack(fill="x")
        broadcast_row.bind("<Button-1>", lambda _: self._select_broadcast())
        broadcast_label.bind("<Button-1>", lambda _: self._select_broadcast())

        self.right = tk.Frame(self, bg=BG_CHAT)
        self.right.pack(side="right", fill="both", expand=True)

        self._build_chat_panel()
        self._build_hub_panel()

        self._show_chat_panel()

    def _build_chat_panel(self):
        self.chat_panel = tk.Frame(self.right, bg=BG_CHAT)

        self.chat_header = tk.Frame(self.chat_panel, bg=BG_CHAT, height=48)
        self.chat_header.pack(fill="x")
        self.chat_header.pack_propagate(False)
        tk.Frame(self.chat_panel, bg=SEPARATOR, height=1).pack(fill="x")
        self.header_label = tk.Label(self.chat_header, text="# alle",
                                     font=FONT_TITLE, bg=BG_CHAT, fg=TEXT_MAIN,
                                     anchor="w", padx=16)
        self.header_label.pack(fill="both", expand=True)

        msg_frame = tk.Frame(self.chat_panel, bg=BG_CHAT)
        msg_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(msg_frame, bg=BG_CHAT, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        vscroll = tk.Scrollbar(msg_frame, orient="vertical", command=self.canvas.yview,
                               bg=BG_CHAT, troughcolor=BG_CHAT, relief="flat", bd=0, width=8)
        vscroll.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=vscroll.set)

        self.msg_inner = tk.Frame(self.canvas, bg=BG_CHAT)
        self.canvas_win = self.canvas.create_window((0, 0), window=self.msg_inner, anchor="nw")
        self.msg_inner.bind("<Configure>", lambda _: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self.canvas_win, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

        tk.Frame(self.chat_panel, bg=SEPARATOR, height=1).pack(fill="x")
        bottom = tk.Frame(self.chat_panel, bg=BG_CHAT, pady=12)
        bottom.pack(fill="x", side="bottom")

        input_wrap = tk.Frame(bottom, bg=BG_INPUT, padx=4, pady=4)
        input_wrap.pack(fill="x", padx=16)

        tk.Button(input_wrap, text="+", font=("Segoe UI", 13, "bold"),
                  bg=BG_INPUT, fg=TEXT_MUTED, relief="flat", bd=0,
                  activebackground=BG_INPUT, activeforeground=TEXT_MAIN,
                  cursor="hand2", command=self._attach_file, padx=6).pack(side="left")

        self.input_var = tk.StringVar()
        self.input_field = tk.Entry(input_wrap, textvariable=self.input_var,
                                    font=FONT_INPUT, bg=BG_INPUT, fg=TEXT_MAIN,
                                    insertbackground=TEXT_MAIN, relief="flat", bd=4,
                                    highlightthickness=0)
        self.input_field.pack(side="left", fill="x", expand=True)
        self.input_field.bind("<Return>", lambda _: self._send())

        tk.Button(input_wrap, text="Send", font=("Segoe UI", 9, "bold"),
                  bg=ACCENT, fg="white", relief="flat", bd=0,
                  activebackground=ACCENT_HOVER, activeforeground="white",
                  padx=12, pady=2, cursor="hand2", command=self._send).pack(side="right", padx=4)

    def _build_hub_panel(self):
        self.hub_panel = tk.Frame(self.right, bg=BG_CHAT)

        header = tk.Frame(self.hub_panel, bg=BG_CHAT, height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🌐  Bruger Hub", font=FONT_TITLE,
                 bg=BG_CHAT, fg=TEXT_MAIN, anchor="w", padx=16).pack(fill="both", expand=True)
        tk.Frame(self.hub_panel, bg=SEPARATOR, height=1).pack(fill="x")

        self.hub_notice = tk.Label(self.hub_panel, text="", font=FONT_SMALL,
                                   bg=BG_CHAT, fg=WARNING)
        self.hub_notice.pack(pady=(6, 0))

        hub_scroll_frame = tk.Frame(self.hub_panel, bg=BG_CHAT)
        hub_scroll_frame.pack(fill="both", expand=True, padx=16, pady=12)

        hub_sb = tk.Scrollbar(hub_scroll_frame, bg=BG_CHAT, troughcolor=BG_CHAT,
                              relief="flat", bd=0, width=8)
        hub_sb.pack(side="right", fill="y")

        self.hub_canvas = tk.Canvas(hub_scroll_frame, bg=BG_CHAT,
                                    highlightthickness=0, bd=0,
                                    yscrollcommand=hub_sb.set)
        self.hub_canvas.pack(side="left", fill="both", expand=True)
        hub_sb.config(command=self.hub_canvas.yview)

        self.hub_inner = tk.Frame(self.hub_canvas, bg=BG_CHAT)
        self.hub_win = self.hub_canvas.create_window((0, 0), window=self.hub_inner, anchor="nw")
        self.hub_inner.bind("<Configure>", lambda _: self.hub_canvas.configure(
            scrollregion=self.hub_canvas.bbox("all")))
        self.hub_canvas.bind("<Configure>", lambda e: self.hub_canvas.itemconfig(
            self.hub_win, width=e.width))

    def _show_chat_panel(self):
        self.current_panel = "chat"
        self.hub_panel.pack_forget()
        self.chat_panel.pack(fill="both", expand=True)
        self.btn_chat.config(bg=ACCENT, fg="white")
        self.btn_hub.config(bg=BG_PANEL, fg=TEXT_MUTED)

    def _show_hub_panel(self):
        self.current_panel = "hub"
        self.chat_panel.pack_forget()
        self.hub_panel.pack(fill="both", expand=True)
        self.btn_hub.config(bg=ACCENT, fg="white")
        self.btn_chat.config(bg=BG_PANEL, fg=TEXT_MUTED)
        send_msg(self.sock, {"type": "get_user_hub"})

    def _populate_hub(self, users):
        for child in self.hub_inner.winfo_children():
            child.destroy()

        if not users:
            tk.Label(self.hub_inner, text="Ingen andre brugere registreret endnu.",
                     font=FONT_BODY, bg=BG_CHAT, fg=TEXT_MUTED).pack(pady=20)
            return

        header_row = tk.Frame(self.hub_inner, bg=BG_PANEL)
        header_row.pack(fill="x", pady=(0, 4))
        for text, w in [("Bruger", 180), ("Status", 80), ("Sidst set", 160), ("Venner", 120)]:
            tk.Label(header_row, text=text, font=("Segoe UI", 9, "bold"),
                     bg=BG_PANEL, fg=TEXT_MUTED, width=w // 8, anchor="w",
                     padx=8, pady=6).pack(side="left")

        for u in users:
            name       = u["username"]
            online     = u["online"]
            last_seen  = format_last_seen(u.get("last_seen"))
            friendship = u.get("friendship", "none")

            row = tk.Frame(self.hub_inner, bg=BG_PANEL, pady=0)
            row.pack(fill="x", pady=2)

            dot_color = ONLINE_DOT if online else DANGER
            status_text = "Online" if online else "Offline"

            tk.Label(row, text=f"● {name}", font=FONT_NAME,
                     bg=BG_PANEL, fg=TEXT_MAIN, anchor="w",
                     padx=8, pady=8, width=20).pack(side="left")

            tk.Label(row, text=status_text, font=FONT_SMALL,
                     bg=BG_PANEL, fg=dot_color, anchor="w",
                     padx=8, width=10).pack(side="left")

            tk.Label(row, text=last_seen, font=FONT_SMALL,
                     bg=BG_PANEL, fg=TEXT_MUTED, anchor="w",
                     padx=8, width=20).pack(side="left")

            action_frame = tk.Frame(row, bg=BG_PANEL)
            action_frame.pack(side="left", padx=8)

            if friendship == "friends":
                tk.Label(action_frame, text="✓ Venner", font=FONT_SMALL,
                         bg=BG_PANEL, fg=ONLINE_DOT).pack(side="left", padx=(0, 6))
                unfriend_btn = tk.Button(action_frame, text="Fjern ven",
                                         font=FONT_SMALL, bg=DANGER, fg="white",
                                         relief="flat", bd=0, cursor="hand2",
                                         activebackground="#c0392b", activeforeground="white",
                                         padx=8, pady=3,
                                         command=lambda n=name: self._unfriend(n))
                unfriend_btn.pack(side="left")

            elif friendship == "pending_sent":
                tk.Label(action_frame, text="⏳ Afventer svar", font=FONT_SMALL,
                         bg=BG_PANEL, fg=WARNING).pack(side="left")

            elif friendship == "pending_received":
                tk.Label(action_frame, text="Anmodning fra dem:", font=FONT_SMALL,
                         bg=BG_PANEL, fg=TEXT_MUTED).pack(side="left", padx=(0, 6))
                tk.Button(action_frame, text="✓ Accepter",
                           font=FONT_SMALL, bg=ONLINE_DOT, fg="white",
                           relief="flat", bd=0, cursor="hand2",
                           activebackground="#1a8c47", activeforeground="white",
                           padx=8, pady=3,
                           command=lambda n=name: self._respond_request(n, True)
                           ).pack(side="left", padx=(0, 4))
                tk.Button(action_frame, text="✗ Afvis",
                           font=FONT_SMALL, bg=DANGER, fg="white",
                           relief="flat", bd=0, cursor="hand2",
                           activebackground="#c0392b", activeforeground="white",
                           padx=8, pady=3,
                           command=lambda n=name: self._respond_request(n, False)
                           ).pack(side="left")

            else:
                tk.Button(action_frame, text="+ Tilføj ven",
                           font=FONT_SMALL, bg=ACCENT, fg="white",
                           relief="flat", bd=0, cursor="hand2",
                           activebackground=ACCENT_HOVER, activeforeground="white",
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
        for child in self.msg_inner.winfo_children():
            child.destroy()
        key = self._chat_key()
        self.bubble_frames[key] = []
        for i, msg in enumerate(self.chat_history.get(key, [])):
            frame = self._render_bubble(
                msg["content"], sender=msg["sender"], timestamp=msg["timestamp"],
                is_file=msg["is_file"], filename=msg.get("filename"),
                file_data=msg.get("file_data"), is_system=msg.get("is_system", False),
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
        menu = tk.Menu(self, tearoff=0, bg=BG_PANEL, fg=TEXT_MAIN,
                       activebackground=ACCENT, activeforeground="white",
                       relief="flat", bd=0)
        menu.add_command(label=f"Fjern {name} som ven",
                         command=lambda: self._unfriend(name))
        menu.tk_popup(event.x_root, event.y_root)

    def _select_broadcast(self):
        self.active_chat = None
        self.friend_list.selection_clear(0, "end")
        self.header_label.config(text="# alle")
        self._show_chat_panel()
        self._refresh_chat()

    def _attach_file(self):
        path = filedialog.askopenfilename(title="Vælg fil")
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
        encoded = base64.b64encode(raw).decode("utf-8")
        payload = {"type": "file", "filename": fname, "data": encoded}
        if self.active_chat is not None:
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
                       msg_index=None, chat_key=None):
        outer = tk.Frame(self.msg_inner, bg=BG_CHAT)
        outer.pack(fill="x", padx=16, pady=2)

        if is_system:
            tk.Label(outer, text=content, font=FONT_SMALL,
                     bg=BG_CHAT, fg=BUBBLE_SYS).pack(pady=2)
            self._scroll_bottom()
            return outer

        is_me = (sender == self.username)
        bg    = BUBBLE_ME if is_me else BUBBLE_OTHER
        fg    = "#ffffff" if is_me else TEXT_MAIN
        align = "e" if is_me else "w"

        meta = tk.Frame(outer, bg=BG_CHAT)
        meta.pack(anchor=align)
        if not is_me:
            tk.Label(meta, text=sender, font=FONT_NAME,
                     bg=BG_CHAT, fg=ACCENT).pack(side="left", padx=(0, 6))
        tk.Label(meta, text=timestamp, font=FONT_SMALL,
                 bg=BG_CHAT, fg=TEXT_TIME).pack(side="left")

        if is_me and msg_index is not None and chat_key is not None:
            del_btn = tk.Label(meta, text="🗑", font=FONT_SMALL, #jeg har fundet den perfekte emjoi!
                               bg=BG_CHAT, fg=TEXT_MUTED, cursor="hand2")
            del_btn.pack(side="left", padx=(6, 0))
            del_btn.bind("<Button-1>", lambda _, i=msg_index, k=chat_key: self._delete_message(i, k))
            del_btn.bind("<Enter>", lambda e: e.widget.config(fg=DANGER))
            del_btn.bind("<Leave>", lambda e: e.widget.config(fg=TEXT_MUTED))

        bubble = tk.Frame(outer, bg=BG_CHAT)
        bubble.pack(anchor=align)

        if is_file:
            row = tk.Frame(bubble, bg=bg)
            row.pack()
            tk.Label(row, text=content, font=FONT_BODY, bg=bg, fg=fg,
                     wraplength=360, justify="left", padx=12, pady=7,
                     relief="flat").pack(side="left", fill="x", expand=True)
            tk.Button(row, text="Download", font=FONT_BODY,
                      bg=ACCENT, fg="white", relief="flat", bd=0,
                      activebackground=ACCENT_HOVER, activeforeground="white",
                      cursor="hand2",
                      command=lambda: self._download_file(filename, file_data)
                      ).pack(side="right", padx=8, pady=7)
        else:
            tk.Label(bubble, text=content, font=FONT_BODY, bg=bg, fg=fg,
                     wraplength=420, justify="left", padx=12, pady=7,
                     relief="flat").pack()

        self._scroll_bottom()
        return outer

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
        if chat_key != "#alle":
            payload["recipient"] = chat_key
        send_msg(self.sock, payload)

    def _remove_message_locally(self, msg_id, chat_key):
        history = self.chat_history.get(chat_key, [])
        self.chat_history[chat_key] = [m for m in history if m.get("msg_id") != msg_id]
        if chat_key == self._chat_key():
            self._refresh_chat()

    def _add_bubble(self, content, sender, timestamp, is_file=False,
                    is_system=False, filename=None, file_data=None,
                    chat_key=None, store=True, msg_id=None):
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
            "msg_id": msg_id,
        }
        if store:
            self._store_message(chat_key, payload)
            msg_index = len(self.chat_history[chat_key]) - 1
        else:
            msg_index = None

        if chat_key == self._chat_key():
            frame = self._render_bubble(content, sender, timestamp,
                                        is_file=is_file, filename=filename,
                                        file_data=file_data, msg_index=msg_index,
                                        chat_key=chat_key)
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
            self.friend_list.itemconfig(idx, fg=DANGER)
            self.user_status[name] = False

    def _set_friend_status(self, name, online: bool):
        if name == self.username or name not in self.friends:
            return
        existing = list(self.friend_list.get(0, "end"))
        display  = f" {name}"
        if display not in existing:
            return
        idx   = existing.index(display)
        color = ONLINE_DOT if online else DANGER
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
            self.friend_list.itemconfig(idx, fg=ONLINE_DOT if online else DANGER)

    def _remove_friend_from_sidebar(self, name):
        self.friends.discard(name)
        self.pending_sent.discard(name)
        self.pending_received.discard(name)
        existing = list(self.friend_list.get(0, "end"))
        display  = f" {name}"
        if display in existing:
            self.friend_list.delete(existing.index(display))

    def _show_hub_notice(self, text, color=None):
        self.hub_notice.config(text=text, fg=color or WARNING)
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
                save_session({"username": self.username, "ip": self.ip, "token": token})
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

        elif t == "message":
            sender    = msg.get("sender", "?")
            content   = msg.get("content", "")
            ts        = msg.get("timestamp", "")
            msg_id    = msg.get("msg_id")
            recipient = msg.get("recipient")
            chat_key  = (sender if sender != self.username else recipient) if recipient else "#alle"
            if chat_key == self._chat_key():
                self._add_bubble(content, sender=sender, timestamp=ts,
                                 chat_key=chat_key, msg_id=msg_id)
            else:
                self._store_message(chat_key, {
                    "content": content, "sender": sender, "timestamp": ts,
                    "is_file": False, "filename": None, "file_data": None,
                    "msg_id": msg_id,
                })

        elif t == "file":
            sender    = msg.get("sender", "?")
            filename  = msg.get("filename", "fil")
            data      = msg.get("data", "")
            ts        = msg.get("timestamp", "")
            msg_id    = msg.get("msg_id")
            recipient = msg.get("recipient")
            chat_key  = (sender if sender != self.username else recipient) if recipient else "#alle"
            if chat_key == self._chat_key():
                self._add_bubble(filename, sender=sender, timestamp=ts,
                                 is_file=True, filename=filename, file_data=data,
                                 chat_key=chat_key, msg_id=msg_id)
            else:
                self._store_message(chat_key, {
                    "content": filename, "sender": sender, "timestamp": ts,
                    "is_file": True, "filename": filename, "file_data": data,
                    "msg_id": msg_id,
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
            self._add_bubble(
                f" {requester} har sendt dig en venneanmodning. Gå til Bruger Hub for at svare.",
                sender="system", timestamp="", is_system=True
            )

        elif t == "friend_request_sent":
            to = msg.get("to", "?")
            self.pending_sent.add(to)
            self._show_hub_notice(f"Venneanmodning sendt til {to}!", ONLINE_DOT)
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
            self._show_hub_notice(f"{other} afslog venneanmodningen.", DANGER)
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
            if self.current_panel == "hub":
                self._show_hub_notice(msg.get("msg", ""), DANGER)

        elif t == "disconnected":
            self.after(200, self._on_close)

    def _send(self):
        text = self.input_var.get().strip()
        if not text:
            return
        self.input_var.set("")
        payload = {"type": "message", "content": text}
        if self.active_chat is not None:
            payload["recipient"] = self.active_chat
        send_msg(self.sock, payload)

    def _on_close(self):
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