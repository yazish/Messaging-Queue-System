## System Architecture

The system is composed of three cooperating roles:

1. **Clients** submit textual jobs and ask for job status updates over TCP. Each job submission is acknowledged with a numeric identifier.
2. **Work Queue / Broker** accepts client and worker connections, keeps track of job state, and assigns queued jobs to workers on demand.
3. **Workers** fetch jobs from the queue, simulate long-running work by streaming the job's words over UDP multicast, and report completion.

The queue process multiplexes all connections with `select`, so any number of clients and workers can share a single broker instance without threading.



## Component Details

### `workQueue.py`

* Opens separate listening sockets for clients (default port 50000) and workers (default port 50001) and adds them to a shared `select` loop.
* Tracks jobs via in-memory structures: `jobs` holds metadata, `waiting` is a FIFO deque of pending job IDs, and `running` records jobs currently assigned to workers.
* Supports two client commands:
  * `JOB <text>` enqueues a new job, assigns a unique ID, records the job as `waiting`, and replies `ID <n>` to the client.
  * `STATUS <id>` returns `waiting`, `running`, `completed`, or `unknown` based on the tracked job state.
* Supports two worker commands:
  * `FETCH` pops the next waiting job (if any), marks it `running`, and responds with `JOB <id> <text>`; otherwise it answers `NOJOB`.
  * `DONE <id>` marks the job as `completed` and acknowledges with `OK`.
* Maintains a per-socket receive buffer to assemble complete newline-delimited messages and closes sockets cleanly on disconnects or errors.


### `client.py`

A TCP client utility that communicates with the work queue broker. It supports three main commands and includes an automated job submission feature.

**Features:**

* **JOB command**: Submits a single job to the queue with specified text. Job text can be provided as command-line arguments or piped from stdin. Returns a unique job ID upon successful submission.
* **STATUS command**: Queries the current state of a job by its ID. Returns one of: `waiting`, `running`, `completed`, or `unknown`.
* **autoCall command**: Automated batch job submission feature that generates and submits multiple jobs with random technical words. Supports configurable job count and delay between submissions.

**autoCall Feature Details:**

The autoCall function generates random jobs using a curated list of 90+ technical terms related to distributed systems, databases, networking, and computing operations. Each job consists of 1-5 randomly selected words.

* Default behavior: Submits 50 jobs with 0.1 second delay between submissions
* Configurable via `--num-jobs` and `--delay` arguments
* Provides real-time progress feedback showing job text and assigned IDs
* Includes error handling to continue submission even if individual jobs fail
* Reports summary statistics upon completion

### `multicast.py`

Helper modules for creating UDP multicast sockets in Python. The sender helpers set TTL and reuse options, while the receiver helpers bind to the requested group/port and join the multicast group using the host's interface.

### `worker.py`

Implements a TCP-based worker process that fetches and processes jobs from the work queue broker.

**Architecture:**

* Connects to the work queue broker via TCP and continuously polls for available jobs using a `FETCH` command.
* Processes jobs by printing each word to stdout with a configurable delay (default 0.25 seconds) between words to simulate long-running work.
* Reports job completion back to the broker with a `DONE <id>` message upon successful processing.


**Key Features:**

* **Graceful Shutdown**: Handles `SIGINT` (Ctrl+C) and `SIGTERM` signals to stop processing cleanly and exit without leaving jobs in inconsistent states.
* **Automatic Reconnection**: If the connection to the broker is lost, the worker automatically attempts to reconnect after a 1-second delay, ensuring resilience against network issues or broker restarts.
* **Protocol Handling**: Implements line-buffered communication with the broker, assembling complete newline-delimited messages from the TCP stream.
* **Idle Management**: When no jobs are available (`NOJOB` response), the worker waits for a configurable interval (default 0.5 seconds) before requesting again, preventing excessive polling.

**Configuration:**

* `FETCH_INTERVAL`: Time (in seconds) to wait between fetch requests when the queue is empty (default: 0.5s)
* `WORD_DELAY`: Time (in seconds) to wait between outputting each word of a job (default: 0.25s)


## Running the System

1. Start the broker: `python3 workQueue.py 50000 50001`
2. Submit a job: `python3 client.py hawk.cs.umanitoba.ca 50000 autoCall`
3. Launch the worker: `python3 worker.py hawk.cs.umanitoba.ca:50001 30000 30001`
4. Observe multicast output with `nc -ul 30000` and check job status via `python3 client.py hawk.cs.umanitoba.ca:50000 STATUS 1`

These steps demonstrate the end-to-end flow: clients submit jobs, the worker fetches and broadcasts them, and the broker tracks completion.