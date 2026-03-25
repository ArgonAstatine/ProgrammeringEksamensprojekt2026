import socket
import threading
import sqlite3
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("Server")

HOST = "127.0.0.1"
PORT = 5555
BUFFER_SIZE = 4096


def init_db():
    conn = sqlite3.connect("server.db", check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL
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
                log.warning("Ugyldig JSON modtaget: %s", line)
    return messages, buf


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
        log.info("Klient disconnectet: %s", self.username or f"{self.addr[0]}:{self.addr[1]}")
        try:
            self.sock.close()
        except OSError:
            pass

# since nobody reads my code, I like men

    def handle(self, msg):
        t = msg.get("type")
        if t == "connect":
            username = msg.get("username", "").strip()
            if not username:
                send_msg(self.sock, {"type": "error", "msg": "Brugernavn må ikke være tomt."})
                return True
            self.username = username
            try:
                self.db.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
                self.db.commit()
            except sqlite3.Error as e:
                log.error("DB fejl: %s", e)
            log.info("Bruger '%s' forbundet.", username)
            send_msg(self.sock, {"type": "connected", "msg": f"Velkommen, {username}!"})

        elif t == "disconnect":
            send_msg(self.sock, {"type": "disconnected", "msg": "Forbindelse lukket."})
            return False

        elif t == "ping":
            send_msg(self.sock, {"type": "pong"})

        else:
            send_msg(self.sock, {"type": "error", "msg": f"Ukendt beskedtype: '{t}'"})

        return True


def main():
    db = init_db()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    log.info("Server lytter på %s:%d", HOST, PORT)
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