#!/usr/bin/env python3
"""Simple command-line client for the messaging queue assignment."""

import argparse
import socket
import sys
from typing import List


def build_message(command: str, params: List[str]) -> str:
    command = command.upper()
    if command == "JOB":
        if params:
            text = " ".join(params)
        else:
            text = sys.stdin.read().strip()
        if not text:
            raise SystemExit("JOB requires text (pass words after the command or pipe input)")
        return f"JOB {text}"
    if command == "STATUS":
        if len(params) != 1:
            raise SystemExit("STATUS requires exactly one job id")
        return f"STATUS {params[0]}"
    raise SystemExit("Unsupported command")


def recv_line(sock: socket.socket) -> str:
    data = bytearray()
    while True:
        chunk = sock.recv(1)
        if not chunk:
            break
        if chunk == b"\n":
            break
        data.extend(chunk)
    return data.decode(errors="ignore")


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Submit jobs or request status from the queue")
    parser.add_argument("host", help="work queue host")
    parser.add_argument("port", type=int, help="client port exposed by the work queue")
    parser.add_argument("command", choices=["JOB", "STATUS"], help="command to send")
    parser.add_argument("params", nargs=argparse.REMAINDER, help="arguments for the command")

    args = parser.parse_args(argv)

    message = build_message(args.command, args.params)

    with socket.create_connection((args.host, args.port)) as sock:
        sock.sendall((message + "\n").encode())
        response = recv_line(sock)
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
