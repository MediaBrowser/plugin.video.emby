import sys
import socket

Argv = ';'.join(sys.argv)
DataSend, XbmcMonitor, sock = f"EVENT {Argv}".encode('utf-8'), None, socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

for _ in range(60):  # 60 seconds timeout
    try:
        sock.connect(('127.0.0.1', 57342))
        sock.send(DataSend)
        sock.recv(1024)
        sock.close()
        break
    except:
        if not XbmcMonitor:
            import xbmc
            XbmcMonitor = xbmc.Monitor()

        if XbmcMonitor.waitForAbort(0.1):
            break
