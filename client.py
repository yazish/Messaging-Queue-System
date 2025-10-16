#!/usr/bin/env python3
import socket, sys

# Usage:
#   python3 client.py host port "JOB some text here"
#   python3 client.py host port "STATUS 1"

host = sys.argv[1]
port = int(sys.argv[2])
msg  = sys.argv[3]

with socket.create_connection((host, port)) as s:
    s.sendall((msg + "\n").encode())
    print(s.recv(4096).decode().strip())
