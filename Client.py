import socket
import threading
import json
import sys

HOST = "127.0.0.1"
PORT = 5555
BUFFER_SIZE = 4096


def send_msg(sock, payload):
    data = json.dumps(payload) + "\n"
    sock.sendall(data.encode("utf-8"))


def listen(sock, stop_event):
    buf = ""
    while not stop_event.is_set():
        try:
            chunk = sock.recv(BUFFER_SIZE).decode("utf-8")
        except OSError:
            break
        if not chunk:
            print("\n[Server lukkede forbindelsen]")
            stop_event.set()
            break
        buf += chunk
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if line:
                try:
                    msg = json.loads(line)
                    print(f"[Server] {msg.get('msg', msg)}")
                except json.JSONDecodeError:
                    print(f"[Server - rå] {line}")


def main():
    username = input("Brugernavn: ").strip()
    if not username:
        print("Brugernavn må ikke være tomt.")
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print(f"Kunne ikke forbinde til {HOST}:{PORT}. Er serveren startet?")
        sys.exit(1)

    stop_event = threading.Event()
    t = threading.Thread(target=listen, args=(sock, stop_event), daemon=True)
    t.start()

    send_msg(sock, {"type": "connect", "username": username})

    print("Forbundet. Skriv 'exit' for at disconnecte.\n")

    try:
        while not stop_event.is_set():
            try:
                cmd = input()
            except EOFError:
                break
            if cmd.lower() == "exit":
                send_msg(sock, {"type": "disconnect"})
                stop_event.set()
                break
            elif cmd.lower() == "ping":
                send_msg(sock, {"type": "ping"})
            else:
                print(f"Ukendt kommando: '{cmd}'. Prøv 'ping' eller 'exit'.")
    except KeyboardInterrupt:
        send_msg(sock, {"type": "disconnect"})
    finally:
        sock.close()
        print("Forbindelse lukket.")


if __name__ == "__main__":
    main()