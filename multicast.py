"""A simple library for handling multicast sockets.

Author: Zach Havens
Course: COMP 3010
Term: Fall 2025
"""

import socket

def _getIP():
    """Based on answer by fatal_error on Stack Overflow
    https://stackoverflow.com/a/28950776/22658427
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        # doesn't even have to be reachable
        s.connect(('10.0.0.0', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def multicastSenderSocket():
    """Returns a socket configured to send multicast messages.

    Use `sock.sendto(data, (grp_addr, grp_port))` to send data.
    
    Based on StackOverflow answer by Niranjan Tulpule
    https://stackoverflow.com/a/1151620/22658427"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except AttributeError:
        pass
    return sock

def multicastReceiverSocket(grp_addr, grp_port):
    """Returns a multicast socket that receives msgs for the given group/port
    
    Based on StackOverflow answer by Niranjan Tulpule: 
    https://stackoverflow.com/a/1151620/22658427"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except AttributeError:
        pass
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

    sock.bind(('', grp_port))
    host = _getIP()
    mreq = socket.inet_aton(grp_addr) + socket.inet_aton(host)
    # sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))
    sock.setsockopt(socket.SOL_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    return sock