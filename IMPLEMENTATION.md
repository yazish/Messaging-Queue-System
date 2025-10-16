# Messaging Queue System Implementation Overview

This document summarizes the provided implementation of the COMP 3010 message queueing assignment. The repository contains a lightweight job broker (`workQueue.py`), client utilities, multicast helpers in Python, C++, and Java, and a UDP-based worker implementation (`worker.cpp`).

## System Architecture

The system is composed of three cooperating roles:

1. **Clients** submit textual jobs and ask for job status updates over TCP. Each job submission is acknowledged with a numeric identifier.
2. **Work Queue / Broker** accepts client and worker connections, keeps track of job state, and assigns queued jobs to workers on demand.
3. **Workers** fetch jobs from the queue, simulate long-running work by streaming the job's words over UDP multicast, and report completion.

The queue process multiplexes all connections with `select`, so any number of clients and workers can share a single broker instance without threading.

## Component Details

### `workQueue.py`

* Opens separate listening sockets for clients (default port 50000) and workers (default port 50001) and adds them to a shared `select` loop.【F:workQueue.py†L5-L33】【F:workQueue.py†L98-L125】
* Tracks jobs via in-memory structures: `jobs` holds metadata, `waiting` is a FIFO deque of pending job IDs, and `running` records jobs currently assigned to workers.【F:workQueue.py†L9-L14】
* Supports two client commands:
  * `JOB <text>` enqueues a new job, assigns a unique ID, records the job as `waiting`, and replies `ID <n>` to the client.【F:workQueue.py†L40-L55】
  * `STATUS <id>` returns `waiting`, `running`, `completed`, or `unknown` based on the tracked job state.【F:workQueue.py†L55-L61】
* Supports two worker commands:
  * `FETCH` pops the next waiting job (if any), marks it `running`, and responds with `JOB <id> <text>`; otherwise it answers `NOJOB`.【F:workQueue.py†L63-L77】
  * `DONE <id>` marks the job as `completed` and acknowledges with `OK`.【F:workQueue.py†L77-L88】
* Maintains a per-socket receive buffer to assemble complete newline-delimited messages and closes sockets cleanly on disconnects or errors.【F:workQueue.py†L30-L38】【F:workQueue.py†L88-L118】

### `client.py`

A minimal TCP utility that sends a single command to the broker and prints the response. It expects command-line arguments `host`, `port`, and the literal command string to send.【F:client.py†L1-L14】

### `multicast.py` and `multicast.h`

Helper modules for creating UDP multicast sockets in Python and C/C++ environments. The sender helpers set TTL and reuse options, while the receiver helpers bind to the requested group/port and join the multicast group using the host's interface.【F:multicast.py†L1-L45】【F:multicast.h†L1-L37】

### `Multicast.java`

Provides a Java NIO `DatagramChannel` helper that mirrors the Python/C utilities. It selects a multicast-capable network interface and exposes helper methods for creating sender and receiver channels configured with reuse and TTL options.【F:Multicast.java†L1-L60】

### `worker.cpp`

Implements a UDP-emitting worker process that integrates with the queue.

* Parses CLI arguments for the work queue address (placeholder), multicast output port, syslog port, and job text; defaults to ports 30000/30001 and reads job text from stdin when necessary.【F:worker.cpp†L63-L111】
* Sends lifecycle logs (startup, fetch, start, completion, error cases) to a localhost UDP “syslog” port using the `SyslogSender` helper class.【F:worker.cpp†L28-L62】【F:worker.cpp†L112-L146】
* Validates multicast configuration, creates the sender socket via the provided helper (`mulitcastSenderSocket`), and emits each word of the job text to the multicast group every 250 ms until complete or interrupted.【F:worker.cpp†L147-L203】
* Handles `SIGINT` for graceful shutdown and trims job text pulled from stdin to avoid trailing whitespace.【F:worker.cpp†L47-L59】【F:worker.cpp†L94-L107】

## Running the System

1. Start the broker: `python3 workQueue.py 50000 50001`
2. Submit a job: `python3 client.py localhost 50000 "JOB read war and peace"`
3. Launch the worker: `./worker localhost:50001 30000 30001`
4. Observe multicast output with `nc -ul 30000` and check job status via `python3 client.py localhost 50000 "STATUS 1"`

These steps demonstrate the end-to-end flow: clients submit jobs, the worker fetches and broadcasts them, and the broker tracks completion.
