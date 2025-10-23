#!/usr/bin/env python3
"""Simple TCP worker for the messaging queue assignment."""

import argparse
import signal
import socket
import sys
import time
from typing import Optional

# Import the multicast library
import multicast

FETCH_INTERVAL = 0.5  # seconds to wait before asking for more work when idle
WORD_DELAY = 0.25     # seconds to sleep between each word of the job text

# Multicast configuration
MULTICAST_GROUP = "239.0.0.1"

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


def send_to_syslog(message: str, syslog_port: int) -> None:
    """Send a message to syslog via UDP (broadcast, not multicast)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            syslog_msg = f"<14>worker: {message}\n"
            # Send as regular UDP unicast to localhost
            sock.sendto(syslog_msg.encode(), ("127.0.0.1", syslog_port))
    except OSError:
        pass


def process_job(mcast_sock: socket.socket, tcp_sock: socket.socket, job_id: int, 
                text: str, output_port: int, syslog_port: int) -> bool:
    """Process a job by sending each word via multicast."""
    send_to_syslog(f"starting job {job_id}", syslog_port)
    
    for word in text.split():
        # Send word via multicast using the library's socket
        payload = f"{word}\n".encode()
        mcast_sock.sendto(payload, (MULTICAST_GROUP, output_port))
        time.sleep(WORD_DELAY)
        if stop_requested:
            break
    
    if stop_requested:
        return False
    
    send_to_syslog(f"completed job {job_id}", syslog_port)
    return send_line(tcp_sock, f"DONE {job_id}")


def run_worker(host: str, port: int, output_port: int, syslog_port: int) -> None:
    """Main worker loop."""
    global stop_requested
    
    # Create multicast sender socket using the library
    mcast_sock = multicast.multicastSenderSocket()
    
    while not stop_requested:
        try:
            with socket.create_connection((host, port), timeout=10) as tcp_sock:
                tcp_sock.settimeout(None)
                send_to_syslog("worker started", syslog_port)
                
                while not stop_requested:
                    send_to_syslog("fetching job", syslog_port)
                    
                    if not send_line(tcp_sock, "FETCH"):
                        break
                    response = recv_line(tcp_sock)
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
                        if not process_job(mcast_sock, tcp_sock, job_id, text, 
                                         output_port, syslog_port):
                            break
                    elif response == "NOJOB":
                        time.sleep(FETCH_INTERVAL)
                    else:
                        time.sleep(FETCH_INTERVAL)
        except (ConnectionError, OSError):
            send_to_syslog("connection lost, reconnecting", syslog_port)
        if not stop_requested:
            time.sleep(1)
    
    send_to_syslog("worker stopped", syslog_port)
    mcast_sock.close()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Worker that pulls jobs from the queue")
    parser.add_argument("workqueue", help="work queue host:port (e.g., localhost:50001)")
    parser.add_argument("output_port", type=int, help="UDP multicast port for job output")
    parser.add_argument("syslog_port", type=int, help="UDP port for syslog messages")
    args = parser.parse_args(argv)

    # Parse host:port
    if ":" not in args.workqueue:
        parser.error("workqueue must be in format host:port")
    
    host, port_str = args.workqueue.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError:
        parser.error("invalid port in workqueue argument")

    if port <= 0 or port > 65535:
        parser.error("workqueue port must be between 1 and 65535")
    if args.output_port <= 0 or args.output_port > 65535:
        parser.error("output_port must be between 1 and 65535")
    if args.syslog_port <= 0 or args.syslog_port > 65535:
        parser.error("syslog_port must be between 1 and 65535")

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    run_worker(host, port, args.output_port, args.syslog_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))