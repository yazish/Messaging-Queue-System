#!/usr/bin/env python3
"""Simple command-line client for the messaging queue assignment."""

import argparse
import random
import socket
import sys
import time
from typing import List


# Random words for generating jobs
RANDOM_WORDS = [
    "analyze", "process", "compute", "calculate", "transform", "optimize", "generate",
    "encrypt", "decode", "compress", "extract", "validate", "filter", "sort", "merge",
    "backup", "restore", "monitor", "scan", "index", "search", "query", "update",
    "synchronize", "migrate", "convert", "parse", "render", "compile", "execute",
    "database", "algorithm", "network", "security", "performance", "scalability",
    "distributed", "parallel", "concurrent", "asynchronous", "real-time", "batch",
    "streaming", "pipeline", "workflow", "scheduler", "load-balancer", "cache",
    "server", "client", "protocol", "authentication", "authorization", "encryption",
    "hash", "signature", "certificate", "token", "session", "transaction", "commit",
    "rollback", "checkpoint", "recovery", "failover", "redundancy", "availability",
    "throughput", "latency", "bandwidth", "capacity", "utilization", "efficiency",
    "resource", "allocation", "partition", "shard", "replica", "cluster", "node",
    "container", "microservice", "API", "REST", "GraphQL", "JSON", "XML", "YAML",
    "configuration", "deployment", "monitoring", "logging", "debugging", "testing",
    "validation", "verification", "simulation", "modeling", "prediction", "analysis"
]


def generate_random_job() -> str:
    """Generate a random job with 1-5 random words."""
    num_words = random.randint(1, 5)
    words = random.sample(RANDOM_WORDS, num_words)
    return " ".join(words)


def auto_call(host: str, port: int, num_jobs: int = 5, delay: float = 0.1) -> int:
    """Send multiple random jobs to the work queue."""
    print(f"Sending {num_jobs} random jobs to {host}:{port}")
    print(f"Delay between jobs: {delay}s")
    print("-" * 50)
    
    job_ids = []
    
    for i in range(num_jobs):
        job_text = generate_random_job()
        message = f"JOB {job_text}"
        
        try:
            with socket.create_connection((host, port)) as sock:
                sock.sendall((message + "\n").encode())
                response = recv_line(sock)
                job_ids.append(response.strip())
                print(f"Job {i+1:2d}: {job_text:<30} -> {response.strip()}")
                
                # Small delay to avoid overwhelming the server
                if delay > 0:
                    time.sleep(delay)
                    
        except Exception as e:
            print(f"Job {i+1:2d}: {job_text:<30} -> ERROR: {e}")
            continue
    
    print("-" * 10)
    print(f"Successfully submitted {len(job_ids)} jobs")
    print("Job IDs:", ", ".join(job_ids))
    return 0


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
    if command == "AUTOCALL":
        # This is handled separately in main()
        return ""
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
    parser.add_argument("command", choices=["JOB", "STATUS", "autoCall"], help="command to send")
    parser.add_argument("params", nargs=argparse.REMAINDER, help="arguments for the command")

    # Add options for autoCall
    parser.add_argument("--num-jobs", type=int, default=50, help="number of jobs for autoCall (default: 50)")
    parser.add_argument("--delay", type=float, default=0.1, help="delay between jobs in seconds (default: 0.1)")

    args = parser.parse_args(argv)

    # Handle autoCall specially
    if args.command.upper() == "AUTOCALL":
        return auto_call(args.host, args.port, args.num_jobs, args.delay)

    # Handle regular JOB and STATUS commands
    message = build_message(args.command, args.params)

    with socket.create_connection((args.host, args.port)) as sock:
        sock.sendall((message + "\n").encode())
        response = recv_line(sock)
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))