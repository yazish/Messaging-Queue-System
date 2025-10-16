#!/usr/bin/env python3
import socket, select, sys
from collections import deque

# Usage: python3 workqueue.py <client_port> <worker_port>
CLIENT_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
WORKER_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 50001

# ---- State ----
next_id = 1
jobs = {}          # id -> {"text": str, "state": "waiting|running|completed"}
waiting = deque()  # job ids waiting to assign
running = set()    # job ids currently assigned

# Per-connection buffers
recv_buf = {}      # sock -> pending bytes
is_worker = {}     # sock -> bool (True = worker, False = client)

def make_listener(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(64)
    s.setblocking(False)
    return s

client_ls = make_listener(CLIENT_PORT)
worker_ls = make_listener(WORKER_PORT)

# All sockets we watch
inputs = { client_ls, worker_ls }
outputs = set()

def close_sock(s):
    recv_buf.pop(s, None)
    is_worker.pop(s, None)
    try:
        inputs.discard(s); outputs.discard(s)
        s.close()
    except: pass

def send_line(s, line: str):
    try:
        s.sendall((line + "\n").encode())
    except:
        close_sock(s)

def handle_client_line(s, line: str):
    line = line.strip()
    if not line: return
    parts = line.split(maxsplit=1)
    cmd = parts[0].upper()

    if cmd == "JOB" and len(parts) == 2:
        global next_id
        text = parts[1]
        jid = next_id; next_id += 1
        jobs[jid] = {"text": text, "state": "waiting"}
        waiting.append(jid)
        send_line(s, f"ID {jid}")
    elif cmd == "STATUS" and len(parts) == 2:
        try:
            jid = int(parts[1])
            st = jobs.get(jid, {}).get("state", "unknown")
            send_line(s, st)
        except:
            send_line(s, "unknown")
    else:
        send_line(s, "ERR")

def handle_worker_line(s, line: str):
    line = line.strip()
    if not line: return
    parts = line.split(maxsplit=2)
    cmd = parts[0].upper()

    if cmd == "FETCH":
        if waiting:
            jid = waiting.popleft()
            running.add(jid)
            jobs[jid]["state"] = "running"
            text = jobs[jid]["text"]
            send_line(s, f"JOB {jid} {text}")
        else:
            send_line(s, "NOJOB")

    elif cmd == "DONE" and len(parts) >= 2:
        try:
            jid = int(parts[1])
            if jid in running:
                running.remove(jid)
            if jid in jobs:
                jobs[jid]["state"] = "completed"
                send_line(s, "OK")
            else:
                send_line(s, "ERR")
        except:
            send_line(s, "ERR")
    else:
        send_line(s, "ERR")

def read_lines(s):
    """Read available bytes; return list of full lines (without trailing \\n)."""
    try:
        data = s.recv(4096)
    except BlockingIOError:
        return []
    except:
        close_sock(s)
        return []

    if not data:
        close_sock(s)
        return []

    buf = recv_buf.get(s, b"") + data
    lines = buf.split(b"\n")
    recv_buf[s] = lines[-1]  # keep partial
    return [ln.decode(errors="ignore") for ln in lines[:-1]]

while True:
    r, w, x = select.select(list(inputs), list(outputs), list(inputs), 1.0)

    for s in r:
        if s is client_ls or s is worker_ls:
            # Accept new connection
            conn, _ = s.accept()
            conn.setblocking(False)
            inputs.add(conn)
            recv_buf[conn] = b""
            is_worker[conn] = (s is worker_ls)
        else:
            # Existing connection: read & handle complete lines
            lines = read_lines(s)
            for line in lines:
                if is_worker.get(s, False):
                    handle_worker_line(s, line)
                else:
                    handle_client_line(s, line)

    # Exceptional conditions -> close
    for s in x:
        if s in (client_ls, worker_ls): continue
        close_sock(s)
