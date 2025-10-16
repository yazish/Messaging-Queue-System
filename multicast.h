#include <stdint.h>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
#else
    #include <arpa/inet.h>
    #include <netinet/in.h>
    #include <sys/socket.h>
#endif

int mulitcastSenderSocket() {
    int s = socket(AF_INET, SOCK_DGRAM, 0);

    in_addr mcIface = {};
    mcIface.s_addr = INADDR_ANY;

    setsockopt(s, IPPROTO_IP, IP_MULTICAST_IF, (char*)&mcIface, sizeof(mcIface));
    int ttl = 32;
    setsockopt(s, IPPROTO_IP, IP_MULTICAST_TTL, (char*)&ttl, sizeof(ttl));

    return s;
}

int multicastReceiverSocket(char* grp_addr, uint16_t grp_port) {
    int s = socket(AF_INET, SOCK_DGRAM, 0);

    int reuse = 1;
    setsockopt(s, SOL_SOCKET, SO_REUSEADDR, (char*)&reuse, sizeof(reuse));

    sockaddr_in mcSock = {};
    mcSock.sin_family = AF_INET;
    mcSock.sin_port = htons(grp_port);
    mcSock.sin_addr.s_addr = INADDR_ANY;
    bind(s, (sockaddr*)&mcSock, sizeof(mcSock));

    ip_mreq group = {};
    group.imr_multiaddr.s_addr = inet_addr(grp_addr);
    group.imr_interface.s_addr = INADDR_ANY;
    setsockopt(s, IPPROTO_IP, IP_ADD_MEMBERSHIP, (char*)&group, sizeof(group));

    return s;
}