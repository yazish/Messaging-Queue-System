// worker.cpp  (robust Linux-only version)
// Purpose:
//   - Behaves like a daemonized worker (no stdout prints)
//   - Sends job words over UDP multicast (one word every 250 ms)
//   - Sends lifecycle logs via UDP "syslog" messages to localhost
//
// Key design notes:
//   * We DO NOT actually daemonize (per assignment). We just avoid stdout.
//   * We DO log to a UDP "syslog" port (default 30001) to simulate daemon logs.
//   * Multicast sender socket is created via the provided multicast.h helper.
//   * The work-queue address is parsed but not used in Step 3 (placeholder for Step 4).

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <csignal>
#include <chrono>
#include <cstring>
#include <optional>
#include <sstream>
#include <string>
#include <thread>

#include "multicast.h"  // mulitcastSenderSocket(), multicastReceiverSocket(...)

// ======= Configuration defaults =======
static constexpr const char* kMulticastGroup = "239.0.0.1"; // IPv4 multicast range: 224.0.0.0 - 239.255.255.255
static constexpr uint16_t    kDefaultOutPort = 30000;       // where words are sent
static constexpr uint16_t    kDefaultLogPort = 30001;       // where "syslog" logs are sent (UDP, localhost)
static constexpr auto        kWordInterval   = std::chrono::milliseconds(250);

// ======= Global for graceful Ctrl+C =======
static volatile std::sig_atomic_t g_stop = 0;
static void handle_sigint(int) { g_stop = 1; }

// ======= Small utilities (no stdout; errors go to syslog) =======

// Quick port sanity
static inline bool is_valid_port(uint16_t p) { return p != 0; }

// Wrap a UDP "syslog-like" sender. Keeps one socket open for all logs to avoid per-call socket churn.
class SyslogSender {
public:
    explicit SyslogSender(uint16_t port) : ok_(false) {
        // Create UDP socket
        s_ = ::socket(AF_INET, SOCK_DGRAM, 0);
        if (s_ < 0) return;

        std::memset(&dst_, 0, sizeof(dst_));
        dst_.sin_family = AF_INET;
        dst_.sin_port   = htons(port);
        if (::inet_pton(AF_INET, "127.0.0.1", &dst_.sin_addr) != 1) {
            ::close(s_);
            s_ = -1;
            return;
        }
        ok_ = true;
    }

    ~SyslogSender() {
        if (s_ >= 0) ::close(s_);
    }

    bool ok() const { return ok_; }

    // RFC3164-ish minimal payload: <14>app[pid]: message
    void log(const std::string& app, const std::string& message) const {
        if (!ok_) return;
        std::ostringstream oss;
        oss << "<14>" << app << "[" << ::getpid() << "]: " << message;
        const std::string payload = oss.str();
        (void)::sendto(s_, payload.data(), (int)payload.size(), 0,
                       reinterpret_cast<const sockaddr*>(&dst_), sizeof(dst_));
    }

private:
    int         s_  = -1;
    bool        ok_ = false;
    sockaddr_in dst_{};
};

// Build an IPv4 sockaddr_in from (addr string, port). Returns std::nullopt on error.
static std::optional<sockaddr_in> make_ipv4_dest(const char* addr, uint16_t port) {
    sockaddr_in out{};
    out.sin_family = AF_INET;
    out.sin_port   = htons(port);
    if (::inet_pton(AF_INET, addr, &out.sin_addr) != 1) {
        return std::nullopt;
    }
    return out;
}

// Check if an IPv4 address is in the multicast block 224.0.0.0/4 (first octet 224..239)
static bool is_multicast_addr(const in_addr& a) {
    const uint8_t first_octet = static_cast<uint8_t>(a.s_addr & 0xFF);
    return first_octet >= 224 && first_octet <= 239;
}

// Trim helper (for stdin-based jobs that might end with newlines)
static inline void rtrim_inplace(std::string& s) {
    while (!s.empty() && (s.back() == '\n' || s.back() == '\r' || s.back() == ' ' || s.back() == '\t'))
        s.pop_back();
}

// ======= Main =======
int main(int argc, char** argv) {
    // Handle Ctrl+C gracefully
    std::signal(SIGINT, handle_sigint);

    // ---- Parse CLI ----
    // Args:
    //   1) workQueueHost:port  (placeholder for Step 4; not used in Step 3)
    //   2) outputPort          (UDP multicast port for words)
    //   3) syslogPort          (UDP port where we send logs to 127.0.0.1)
    //   4+) job text           (if omitted, read from stdin)
    const std::string workQueue = (argc >= 2) ? argv[1] : "hawk.cs.umanitoba.ca:50001";

    const uint16_t outPort = (argc >= 3) ? static_cast<uint16_t>(std::stoi(argv[2])) : kDefaultOutPort;
    const uint16_t logPort = (argc >= 4) ? static_cast<uint16_t>(std::stoi(argv[3])) : kDefaultLogPort;

    // Initialize "syslog" sender ASAP so we can report errors there.
    SyslogSender logger(logPort);
    // Note: if logger.ok() is false, we silently continue (no stdout per assignment).

    // Port validation (log and exit if invalid)
    if (!is_valid_port(outPort) || !is_valid_port(logPort)) {
        if (logger.ok()) logger.log("worker", "invalid port argument(s)");
        return 1;
    }

    // Build job text from args or stdin
    std::string job;
    if (argc >= 5) {
        for (int i = 4; i < argc; ++i) {
            if (i > 4) job.push_back(' ');
            job += argv[i];
        }
    } else {
        std::ostringstream oss;
        oss << std::cin.rdbuf();
        job = oss.str();
    }
    rtrim_inplace(job);
    if (job.empty()) {
        job = "default demo job text"; // safe fallback for smoke testing
    }

    // Start banner (goes to "syslog")
    if (logger.ok()) {
        std::ostringstream oss;
        oss << "starting with workQueue=" << workQueue
            << " multicast=" << kMulticastGroup << ":" << outPort
            << " syslogPort=" << logPort;
        logger.log("worker", oss.str());
    }

    // ---- Prepare multicast destination ----
    // Validate multicast group is well-formed and actually in the multicast range.
    auto maybeDest = make_ipv4_dest(kMulticastGroup, outPort);
    if (!maybeDest.has_value()) {
        if (logger.ok()) logger.log("worker", "invalid multicast group address (inet_pton failed)");
        return 1;
    }
    sockaddr_in dest = *maybeDest;
    if (!is_multicast_addr(dest.sin_addr)) {
        if (logger.ok()) logger.log("worker", "destination is not a multicast address (must be 224.0.0.0/4)");
        return 1;
    }

    // ---- Create multicast sender socket via helper (TTL etc set in multicast.h) ----
    // NOTE: helper name in your header is "mulitcastSenderSocket" (typo preserved).
    int sendSock = mulitcastSenderSocket();
    if (sendSock < 0) {
        if (logger.ok()) logger.log("worker", "failed to create multicast send socket");
        return 1;
    }

    // Lifecycle logs
    if (logger.ok()) logger.log("worker", "fetching job");
    if (logger.ok()) logger.log("worker", "starting job");

    // ---- Main send loop: one word every 250 ms ----
    // We push '\n' for readability in a plain UDP listener like `nc -u -l <port>`.
    std::istringstream iss(job);
    std::string word;
    while (!g_stop && (iss >> word)) {
        word.push_back('\n');
        const ssize_t n = ::sendto(sendSock, word.data(), (int)word.size(), 0,
                                   reinterpret_cast<const sockaddr*>(&dest), sizeof(dest));
        if (n < 0) {
            if (logger.ok()) logger.log("worker", "sendto failed (continuing)");
            // We keep going; a transient error shouldn't kill the worker.
        }
        std::this_thread::sleep_for(kWordInterval);
    }

    if (logger.ok()) logger.log("worker", "completed job");

    ::close(sendSock);
    return 0;
}
