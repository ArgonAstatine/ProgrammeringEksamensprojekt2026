import socket
import threading
import sqlite3
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("Server")

HOST = "0.0.0.0"
PORT = 5555
BUFFER_SIZE = 4096

clients: dict = {}
clients_lock = threading.Lock()


def init_db():
    conn = sqlite3.connect("server.db", check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sender    TEXT NOT NULL,
            content   TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def send_msg(sock, payload):
    data = json.dumps(payload) + "\n"
    sock.sendall(data.encode("utf-8"))


def recv_msgs(buf, sock):
    try:
        chunk = sock.recv(BUFFER_SIZE).decode("utf-8")
    except (ConnectionResetError, OSError):
        return [], None
    if not chunk:
        return [], None
    buf += chunk
    messages = []
    while "\n" in buf:
        line, buf = buf.split("\n", 1)
        line = line.strip()
        if line:
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("Ugyldig JSON: %s", line)
    return messages, buf


def broadcast(payload, exclude=None):
    with clients_lock:
        for username, handler in list(clients.items()):
            if username == exclude:
                continue
            try:
                send_msg(handler.sock, payload)
            except OSError:
                pass


class ClientHandler(threading.Thread):
    def __init__(self, sock, addr, db):
        super().__init__(daemon=True)
        self.sock = sock
        self.addr = addr
        self.db = db
        self.username = None
        self.buf = ""

    def run(self):
        log.info("Klient forbundet: %s:%d", *self.addr)
        send_msg(self.sock, {"type": "welcome", "msg": "Forbundet til server."})
        try:
            while True:
                messages, self.buf = recv_msgs(self.buf, self.sock)
                if self.buf is None:
                    break
                for msg in messages:
                    if not self.handle(msg):
                        return
        finally:
            self.close()

    def close(self):
        if self.username:
            with clients_lock:
                clients.pop(self.username, None)
            broadcast({"type": "system", "msg": f"{self.username} har forladt chatten."})
            log.info("Bruger '%s' disconnectet.", self.username)
        else:
            log.info("Ukendt klient disconnectet: %s:%d", *self.addr)
        try:
            self.sock.close()
        except OSError:
            pass

    def handle(self, msg):
        t = msg.get("type")

        if t == "connect":
            username = msg.get("username", "").strip()
            if not username:
                send_msg(self.sock, {"type": "error", "msg": "Brugernavn må ikke være tomt."})
                return True
            with clients_lock:
                if username in clients:
                    send_msg(self.sock, {"type": "error", "msg": "Brugernavnet er allerede i brug."})
                    return True
                self.username = username
                clients[username] = self
            try:
                self.db.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
                self.db.commit()
            except sqlite3.Error as e:
                log.error("DB fejl: %s", e)
            log.info("Bruger '%s' forbundet.", username)
            send_msg(self.sock, {"type": "connected", "msg": f"Velkommen, {username}!"})
            broadcast({"type": "system", "msg": f"{username} er gået online."}, exclude=username)

        elif t == "message":
            if not self.username:
                send_msg(self.sock, {"type": "error", "msg": "Du skal forbinde med et brugernavn først."})
                return True
            content = msg.get("content", "").strip()
            if not content:
                return True
            timestamp = datetime.now().strftime("%H:%M:%S")
            try:
                self.db.execute(
                    "INSERT INTO messages (sender, content, timestamp) VALUES (?, ?, ?)",
                    (self.username, content, timestamp)
                )
                self.db.commit()
            except sqlite3.Error as e:
                log.error("DB fejl: %s", e)
            log.info("[%s] %s: %s", timestamp, self.username, content)
            broadcast({
                "type": "message",
                "sender": self.username,
                "content": content,
                "timestamp": timestamp,
            })

        elif t == "disconnect":
            send_msg(self.sock, {"type": "disconnected", "msg": "Forbindelse lukket."})
            return False

        elif t == "ping":
            send_msg(self.sock, {"type": "pong"})

        else:
            send_msg(self.sock, {"type": "error", "msg": f"Ukendt beskedtype: '{t}'"})

        return True


def main():
    import socket as _s
    hostname = _s.gethostname()
    local_ip = _s.gethostbyname(hostname)

    db = init_db()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    log.info("Server kører på %s:%d", local_ip, PORT)
    log.info("Andre klienter forbinder med IP: %s  port: %d", local_ip, PORT)
    try:
        while True:
            conn, addr = server.accept()
            ClientHandler(conn, addr, db).start()
    except KeyboardInterrupt:
        log.info("Server lukker ned.")
    finally:
        server.close()


if __name__ == "__main__":
    main()