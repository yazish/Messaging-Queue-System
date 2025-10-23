#!/usr/bin/env python3
"""Helper utility to read messages from the multicast group used by the worker."""

import argparse
import sys

import multicast

MULTICAST_GROUP = "239.0.0.1"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Listen to worker multicast output")
    parser.add_argument("port", type=int, help="UDP port to listen on")
    parser.add_argument("--group", default=MULTICAST_GROUP,
                        help="Multicast group address (default: %(default)s)")
    args = parser.parse_args(argv)

    if args.port <= 0 or args.port > 65535:
        parser.error("port must be between 1 and 65535")

    sock = multicast.multicastReceiverSocket(args.group, args.port)
    try:
        while True:
            data, addr = sock.recvfrom(65535)
            text = data.decode(errors="replace")
            # rstrip to avoid blank lines if payload already ends with newline
            print(text.rstrip())
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
