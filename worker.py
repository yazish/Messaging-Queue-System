#!/usr/bin/env python3
"""Simple TCP worker for the messaging queue assignment."""

import argparse
import signal
import socket
import sys
import time
from typing import Optional

FETCH_INTERVAL = 0.5  # seconds to wait before asking for more work when idle
WORD_DELAY = 0.25     # seconds to sleep between each word of the job text

stop_requested = False


def _signal_handler(_sig, _frame) -> None:
    global stop_requested
    stop_requested = True


def recv_line(sock: socket.socket) -> Optional[str]:
    """Read a single newline-delimited line; return None on disconnect."""
    data = bytearray()
    try:
        while True:
            chunk = sock.recv(1)
            if not chunk:
                return None
            if chunk == b"\n":
                return data.decode(errors="ignore")
            data.extend(chunk)
    except OSError:
        return None


def send_line(sock: socket.socket, line: str) -> bool:
    try:
        sock.sendall((line + "\n").encode())
        return True
    except OSError:
        return False


def process_job(sock: socket.socket, job_id: int, text: str) -> bool:
    for word in text.split():
        print(word, flush=True)
        time.sleep(WORD_DELAY)
        if stop_requested:
            break
    if stop_requested:
        return False
    return send_line(sock, f"DONE {job_id}")


def run_worker(host: str, port: int) -> None:
    global stop_requested
    while not stop_requested:
        try:
            with socket.create_connection((host, port), timeout=10) as sock:
                sock.settimeout(None)
                while not stop_requested:
                    if not send_line(sock, "FETCH"):
                        break
                    response = recv_line(sock)
                    if response is None:
                        break
                    if response.startswith("JOB "):
                        parts = response.split(maxsplit=2)
                        if len(parts) < 3:
                            continue
                        try:
                            job_id = int(parts[1])
                        except ValueError:
                            continue
                        text = parts[2]
                        if not process_job(sock, job_id, text):
                            break
                    elif response == "NOJOB":
                        time.sleep(FETCH_INTERVAL)
                    else:
                        time.sleep(FETCH_INTERVAL)
        except (ConnectionError, OSError):
            pass
        if not stop_requested:
            time.sleep(1)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Worker that pulls jobs from the queue and emits each word")
    parser.add_argument("host", help="hostname of the work queue")
    parser.add_argument("port", type=int, help="worker port exposed by the work queue")
    args = parser.parse_args(argv)

    if args.port <= 0 or args.port > 65535:
        parser.error("port must be between 1 and 65535")

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    run_worker(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
