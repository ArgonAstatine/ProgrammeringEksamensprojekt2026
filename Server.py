import socket
import threading
import sqlite3
import json
import logging
import hashlib
import hmac
import os
import secrets
import base64
from datetime import datetime
from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("Server")

HOST = "0.0.0.0"
PORT = 5555
BUFFER_SIZE       = 4096
PBKDF2_ITERATIONS = 260_000
MAX_MESSAGE_LENGTH = 2048
MAX_FILE_SIZE      = 1 * 1024 * 1024  # 1 MB – ændr 1-tallet if so
DB_ENC_PATH = "server.db.enc"
KEY_PATH    = "server.key"

clients:      dict = {}
clients_lock = threading.Lock()
db_lock      = threading.Lock()




def load_or_create_key() -> bytes:
    if os.path.exists(KEY_PATH):
        with open(KEY_PATH, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(KEY_PATH, "wb") as f:
        f.write(key)
    log.info("Ny krypteringsnøgle genereret: %s", KEY_PATH)
    return key


def load_db(fernet: Fernet) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    if os.path.exists(DB_ENC_PATH):
        with open(DB_ENC_PATH, "rb") as f:
            raw = fernet.decrypt(f.read())
        tmp = sqlite3.connect(":memory:")
        tmp.executescript(raw.decode("utf-8"))
        tmp.backup(conn)
        tmp.close()
        log.info("Database indlæst og dekrypteret fra %s", DB_ENC_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created       TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token    TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created  TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sender    TEXT NOT NULL,
            content   TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            recipient TEXT
        )
    """)
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    if "recipient" not in existing_cols:
        conn.execute("ALTER TABLE messages ADD COLUMN recipient TEXT")
    conn.commit()
    return conn


def save_db(fernet: Fernet, conn: sqlite3.Connection):
    dump = "\n".join(conn.iterdump())
    encrypted = fernet.encrypt(dump.encode("utf-8"))
    with open(DB_ENC_PATH, "wb") as f:
        f.write(encrypted)



def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, key_hex = stored.split(":")
        salt     = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(key_hex)
        actual   = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


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
    def __init__(self, sock, addr, db, fernet):
        super().__init__(daemon=True)
        self.sock     = sock
        self.addr     = addr
        self.db       = db
        self.fernet   = fernet
        self.username = None
        self.buf      = ""

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
            broadcast({"type": "presence", "event": "offline", "username": self.username})
            broadcast({"type": "system", "msg": f"{self.username} har forladt chatten."})
            log.info("Bruger '%s' disconnectede.", self.username)
        else:
            log.info("Ukendt klient disconnectede: %s:%d", *self.addr)
        try:
            self.sock.close()
        except OSError:
            pass


    def db_write(self, sql, params=()):
        with db_lock:
            self.db.execute(sql, params)
            self.db.commit()
            save_db(self.fernet, self.db)

    def db_read(self, sql, params=()):
        with db_lock:
            return self.db.execute(sql, params).fetchone()

    def db_write_returning(self, sql, params=()):
        with db_lock:
            cur = self.db.execute(sql, params)
            self.db.commit()
            save_db(self.fernet, self.db)
            return cur.lastrowid


    def handle(self, msg):
        t = msg.get("type")

        if t == "connect":
            token    = msg.get("token", "")
            username = msg.get("username", "").strip()
            password = msg.get("password", "")
            if token:
                self._login_by_token(token)
            elif username and password:
                self._login_or_register(username, password)
            else:
                send_msg(self.sock, {"type": "auth_error", "msg": "Manglende legitimationsoplysninger."})

        elif t == "message":
            if not self.username:
                send_msg(self.sock, {"type": "error", "msg": "Ikke logget ind."})
                return True
            content = msg.get("content", "").strip()
            if not content:
                return True
            if len(content) > MAX_MESSAGE_LENGTH:
                send_msg(self.sock, {
                    "type": "error",
                    "msg": f"Besked overskrider maks. {MAX_MESSAGE_LENGTH} tegn."
                })
                return True
            recipient = msg.get("recipient")
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg_id = self.db_write_returning(
                "INSERT INTO messages (sender, content, timestamp, recipient) VALUES (?, ?, ?, ?)",
                (self.username, content, timestamp, recipient)
            )
            if recipient:
                with clients_lock:
                    target = clients.get(recipient)
                if not target:
                    send_msg(self.sock, {"type": "error", "msg": f"Bruger '{recipient}' er ikke online."})
                    return True
                log.info("[%s] %s -> %s: %s", timestamp, self.username, recipient, content)
                send_msg(target.sock, {
                    "type": "message", "sender": self.username,
                    "content": content, "timestamp": timestamp,
                    "recipient": recipient, "msg_id": msg_id,
                })
                send_msg(self.sock, {
                    "type": "message", "sender": self.username,
                    "content": content, "timestamp": timestamp,
                    "recipient": recipient, "msg_id": msg_id,
                })
            else:
                log.info("[%s] %s: %s", timestamp, self.username, content)
                broadcast({
                    "type": "message", "sender": self.username,
                    "content": content, "timestamp": timestamp, "msg_id": msg_id,
                }, exclude=self.username)
                send_msg(self.sock, {
                    "type": "message", "sender": self.username,
                    "content": content, "timestamp": timestamp, "msg_id": msg_id,
                })

        elif t == "file":
            if not self.username:
                send_msg(self.sock, {"type": "error", "msg": "Ikke logget ind."})
                return True
            filename  = msg.get("filename", "fil")
            data      = msg.get("data", "")
            raw_bytes = len(base64.b64decode(data, validate=False))
            if raw_bytes > MAX_FILE_SIZE:
                send_msg(self.sock, {
                    "type": "error",
                    "msg": f"Fil overskrider maks. filstørrelse på {MAX_FILE_SIZE // 1024} KB."
                })
                return True
            recipient = msg.get("recipient")
            timestamp = datetime.now().strftime("%H:%M:%S")
            msg_id = self.db_write_returning(
                "INSERT INTO messages (sender, content, timestamp, recipient) VALUES (?, ?, ?, ?)",
                (self.username, f"(fil: {filename})", timestamp, recipient)
            )
            if recipient:
                with clients_lock:
                    target = clients.get(recipient)
                if not target:
                    send_msg(self.sock, {"type": "error", "msg": f"Bruger '{recipient}' er ikke online."})
                    return True
                log.info("[%s] %s -> %s sendte fil: %s", timestamp, self.username, recipient, filename)
                send_msg(target.sock, {
                    "type": "file", "sender": self.username, "filename": filename,
                    "data": data, "timestamp": timestamp,
                    "recipient": recipient, "msg_id": msg_id,
                })
                send_msg(self.sock, {
                    "type": "file", "sender": self.username, "filename": filename,
                    "data": data, "timestamp": timestamp,
                    "recipient": recipient, "msg_id": msg_id,
                })
            else:
                log.info("[%s] %s sendte fil: %s", timestamp, self.username, filename)
                broadcast({
                    "type": "file", "sender": self.username,
                    "filename": filename, "data": data,
                    "timestamp": timestamp, "msg_id": msg_id,
                }, exclude=self.username)
                send_msg(self.sock, {
                    "type": "file", "sender": self.username, "filename": filename,
                    "data": data, "timestamp": timestamp, "msg_id": msg_id,
                })


        elif t == "delete":
            if not self.username:
                send_msg(self.sock, {"type": "error", "msg": "Ikke logget ind."})
                return True
            msg_id = msg.get("msg_id")
            if not msg_id:
                send_msg(self.sock, {"type": "error", "msg": "Manglende besked-id."})
                return True
            row = self.db_read("SELECT sender, recipient FROM messages WHERE id = ?", (msg_id,))
            if not row:
                send_msg(self.sock, {"type": "error", "msg": "Beskeden findes ikke."})
                return True
            sender, recipient = row
            if sender != self.username:
                send_msg(self.sock, {"type": "error", "msg": "Du kan kun slette dine egne beskeder."})
                return True

            self.db_write("DELETE FROM messages WHERE id = ?", (msg_id,))
            log.info("Bruger '%s' slettede besked id=%s", self.username, msg_id)

            if recipient:
                with clients_lock:
                    target = clients.get(recipient)
                send_msg(self.sock, {"type": "deleted", "msg_id": msg_id, "chat_key": recipient})
                if target:
                    send_msg(target.sock, {"type": "deleted", "msg_id": msg_id, "chat_key": sender})

            else:
                broadcast({"type": "deleted", "msg_id": msg_id, "chat_key": "#alle"}, exclude=self.username)
                send_msg(self.sock, {"type": "deleted", "msg_id": msg_id, "chat_key": "#alle"})

        elif t == "disconnect":
            send_msg(self.sock, {"type": "disconnected", "msg": "Forbindelse lukket."})
            return False

        elif t == "ping":
            send_msg(self.sock, {"type": "pong"})

        else:
            send_msg(self.sock, {"type": "error", "msg": f"Ukendt beskedtype: '{t}'"})

        return True


    def _login_or_register(self, username, password):
        row = self.db_read("SELECT password_hash FROM users WHERE username = ?", (username,))
        if row is None:
            pw_hash = hash_password(password)
            now = datetime.now().isoformat()
            self.db_write(
                "INSERT INTO users (username, password_hash, created) VALUES (?, ?, ?)",
                (username, pw_hash, now)
            )
            log.info("Ny bruger oprettet: '%s'", username)
        else:
            if not verify_password(password, row[0]):
                send_msg(self.sock, {"type": "auth_error", "msg": "Forkert adgangskode."})
                return
        token = self._create_session(username)
        self._finalize_login(username, token)

    def _login_by_token(self, token):
        row = self.db_read("SELECT username FROM sessions WHERE token = ?", (token,))
        if not row:
            send_msg(self.sock, {"type": "auth_error", "msg": "Session udløbet. Log ind igen."})
            return
        self._finalize_login(row[0], token)

    def _create_session(self, username) -> str:
        token = secrets.token_hex(32)
        now   = datetime.now().isoformat()
        with db_lock:
            self.db.execute("DELETE FROM sessions WHERE username = ?", (username,))
            self.db.execute(
                "INSERT INTO sessions (token, username, created) VALUES (?, ?, ?)",
                (token, username, now)
            )
            self.db.commit()
            save_db(self.fernet, self.db)
        return token

    def _finalize_login(self, username, token):
        with clients_lock:
            # Only block if this exact username is already connected
            if username in clients and clients[username] is not self:
                send_msg(self.sock, {"type": "auth_error", "msg": "Brugeren er allerede logget ind."})
                return
            self.username = username
            clients[username] = self

        log.info("Bruger '%s' logget ind.", username)

        with clients_lock:
            online_users = [name for name in clients if name != username]

        send_msg(self.sock, {
            "type": "connected",
            "msg": f"Velkommen, {username}!",
            "token": token,
        })
        send_msg(self.sock, {"type": "presence", "event": "list", "users": online_users})
        broadcast({"type": "presence", "event": "online", "username": username}, exclude=username)
        broadcast({"type": "system", "msg": f"{username} er gået online."}, exclude=username)



def main():
    fernet = Fernet(load_or_create_key())
    db     = load_db(fernet)

    import socket as _s
    local_ip = _s.gethostbyname(_s.gethostname())

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    log.info("Server kører på %s:%d", local_ip, PORT)
    log.info("Andre klienter forbinder med IP: %s  port: %d", local_ip, PORT)
    try:
        while True:
            conn, addr = server.accept()
            ClientHandler(conn, addr, db, fernet).start()
    except KeyboardInterrupt:
        log.info("Gemmer og lukker ned...")
        with db_lock:
            save_db(fernet, db)
    finally:
        server.close()


if __name__ == "__main__":
    main()