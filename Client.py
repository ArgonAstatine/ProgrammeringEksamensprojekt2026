import socket
import threading
import json
import sys
import tkinter as tk
from tkinter import filedialog
from datetime import datetime

HOST = "127.0.0.1"
PORT = 5555
BUFFER_SIZE = 4096

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

FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_BODY  = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 8)
FONT_INPUT = ("Segoe UI", 11)
FONT_NAME  = ("Segoe UI", 9, "bold")


def send_msg(sock, payload):
    data = json.dumps(payload) + "\n"
    sock.sendall(data.encode("utf-8"))


class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chat")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self._center(360, 240)

        tk.Label(self, text="Velkommen!", font=("Segoe UI", 18, "bold"),
                 bg=BG_DARK, fg=TEXT_MAIN).pack(pady=(36, 4))
        tk.Label(self, text="BRUGERNAVN", font=("Segoe UI", 8, "bold"),
                 bg=BG_DARK, fg=TEXT_MUTED).pack(anchor="w", padx=50)

        self.username_var = tk.StringVar()
        e = tk.Entry(self, textvariable=self.username_var, font=FONT_INPUT,
                     bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                     relief="flat", bd=8)
        e.pack(padx=50, fill="x", pady=(2, 6))
        e.bind("<Return>", lambda _: self._connect())
        e.focus()

        self.status = tk.Label(self, text="", font=FONT_SMALL,
                               bg=BG_DARK, fg="#f04747")
        self.status.pack()

        btn = tk.Button(self, text="Log ind", font=("Segoe UI", 10, "bold"),
                        bg=ACCENT, fg="white", relief="flat", bd=0,
                        activebackground=ACCENT_HOVER, activeforeground="white",
                        padx=20, pady=8, cursor="hand2", command=self._connect)
        btn.pack(pady=8, padx=50, fill="x")

    def _center(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _connect(self):
        username = self.username_var.get().strip()
        if not username:
            self.status.config(text="Indtast et brugernavn.")
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((HOST, PORT))
        except ConnectionRefusedError:
            self.status.config(text=f"Kunne ikke forbinde til {HOST}:{PORT}")
            return
        self.destroy()
        ChatApp(sock, username).mainloop()


class ChatApp(tk.Tk):
    def __init__(self, sock, username):
        super().__init__()
        self.sock = sock
        self.username = username
        self.active_chat = None
        self.stop_event = threading.Event()
        self.buf = ""

        self.title("Chat")
        self.configure(bg=BG_DARK)
        self.geometry("960x640")
        self._center()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._start_listener()
        send_msg(self.sock, {"type": "connect", "username": username})
        self._tick()

    def _center(self):
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 960) // 2
        y = (self.winfo_screenheight() - 640) // 2
        self.geometry(f"960x640+{x}+{y}")

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

        tk.Label(self.left, text="  INDSTILLINGER", font=("Segoe UI", 8, "bold"),
                 bg=BG_PANEL, fg=TEXT_MUTED, anchor="w").pack(fill="x", padx=8, pady=(6, 2))

        for label in ("Profil", "Notifikationer"):
            btn = tk.Frame(self.left, bg=BG_PANEL, cursor="hand2")
            btn.pack(fill="x", padx=8, pady=1)
            tk.Label(btn, text=f"  {label}", font=FONT_BODY,
                     bg=BG_PANEL, fg=TEXT_MUTED, anchor="w", pady=5).pack(fill="x")
            btn.bind("<Enter>", lambda e, f=btn: f.config(bg="#35373c"))
            btn.bind("<Leave>", lambda e, f=btn: f.config(bg=BG_PANEL))

        tk.Frame(self.left, bg=SEPARATOR, height=1).pack(fill="x", padx=10, pady=8)

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

        broadcast_row = tk.Frame(self.left, bg=BG_PANEL, cursor="hand2")
        broadcast_row.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(broadcast_row, text="  # alle", font=FONT_BODY,
                 bg=BG_PANEL, fg=TEXT_MUTED, anchor="w", pady=5).pack(fill="x")
        broadcast_row.bind("<Button-1>", lambda _: self._select_broadcast())

        self.right = tk.Frame(self, bg=BG_CHAT)
        self.right.pack(side="right", fill="both", expand=True)

        self.chat_header = tk.Frame(self.right, bg=BG_CHAT, height=48)
        self.chat_header.pack(fill="x")
        self.chat_header.pack_propagate(False)
        tk.Frame(self.right, bg=SEPARATOR, height=1).pack(fill="x")
        self.header_label = tk.Label(self.chat_header, text="# alle",
                                     font=FONT_TITLE, bg=BG_CHAT, fg=TEXT_MAIN,
                                     anchor="w", padx=16)
        self.header_label.pack(fill="both", expand=True)

        msg_frame = tk.Frame(self.right, bg=BG_CHAT)
        msg_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(msg_frame, bg=BG_CHAT, highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        vscroll = tk.Scrollbar(msg_frame, orient="vertical",
                               command=self.canvas.yview,
                               bg=BG_CHAT, troughcolor=BG_CHAT,
                               relief="flat", bd=0, width=8)
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

        tk.Frame(self.right, bg=SEPARATOR, height=1).pack(fill="x")
        bottom = tk.Frame(self.right, bg=BG_CHAT, pady=12)
        bottom.pack(fill="x", side="bottom")

        input_wrap = tk.Frame(bottom, bg=BG_INPUT, padx=4, pady=4)
        input_wrap.pack(fill="x", padx=16)

        file_btn = tk.Button(input_wrap, text="+", font=("Segoe UI", 13, "bold"),
                             bg=BG_INPUT, fg=TEXT_MUTED, relief="flat", bd=0,
                             activebackground=BG_INPUT, activeforeground=TEXT_MAIN,
                             cursor="hand2", command=self._attach_file, padx=6)
        file_btn.pack(side="left")

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

    def _tick(self):
        self.date_label.config(text=datetime.now().strftime("%d/%m/%Y  %H:%M"))
        self.after(30000, self._tick)

    def _on_friend_select(self, _=None):
        sel = self.friend_list.curselection()
        if not sel:
            return
        name = self.friend_list.get(sel[0]).lstrip("● ").strip()
        self.active_chat = name
        self.header_label.config(text=f"@ {name}")

    def _select_broadcast(self):
        self.active_chat = None
        self.friend_list.selection_clear(0, "end")
        self.header_label.config(text="# alle")

    def _attach_file(self):
        path = filedialog.askopenfilename(title="Vælg fil")
        if path:
            fname = path.split("/")[-1]
            self._add_bubble(f"📄 {fname}", sender=self.username,
                             timestamp=datetime.now().strftime("%H:%M"), is_file=True)

    def _add_bubble(self, content, sender, timestamp, is_file=False, is_system=False):
        outer = tk.Frame(self.msg_inner, bg=BG_CHAT)
        outer.pack(fill="x", padx=16, pady=2)

        if is_system:
            tk.Label(outer, text=content, font=FONT_SMALL,
                     bg=BG_CHAT, fg=BUBBLE_SYS).pack(pady=2)
            self._scroll_bottom()
            return

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

        bubble = tk.Frame(outer, bg=BG_CHAT)
        bubble.pack(anchor=align)
        tk.Label(bubble, text=content, font=FONT_BODY, bg=bg, fg=fg,
                 wraplength=420, justify="left", padx=12, pady=7,
                 relief="flat").pack()

        self._scroll_bottom()

    def _scroll_bottom(self):
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(1.0)

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
        if t == "message":
            sender  = msg.get("sender", "?")
            content = msg.get("content", "")
            ts      = msg.get("timestamp", "")
            self._add_bubble(content, sender=sender, timestamp=ts)
            if sender != self.username:
                self._ensure_friend(sender)
        elif t == "system":
            self._add_bubble(msg.get("msg", ""), sender="system",
                             timestamp="", is_system=True)
            text = msg.get("msg", "")
            if "online" in text:
                name = text.split()[0]
                if name != self.username:
                    self._ensure_friend(name)
        elif t in ("welcome", "connected"):
            self._add_bubble(msg.get("msg", ""), sender="system",
                             timestamp="", is_system=True)
        elif t == "error":
            self._add_bubble(f"Fejl: {msg.get('msg','')}", sender="system",
                             timestamp="", is_system=True)
        elif t == "disconnected":
            self.after(200, self._on_close)

    def _ensure_friend(self, name):
        existing = list(self.friend_list.get(0, "end"))
        display = f"● {name}"
        if display not in existing:
            self.friend_list.insert("end", display)

    def _send(self):
        text = self.input_var.get().strip()
        if not text:
            return
        self.input_var.set("")
        send_msg(self.sock, {"type": "message", "content": text})

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
 #test

if __name__ == "__main__":
    LoginWindow().mainloop()