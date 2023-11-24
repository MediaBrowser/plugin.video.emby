import sys
import _socket

Argv = ';'.join(sys.argv)
DataSend, XbmcMonitor, sock = f"EVENT {Argv}".encode('utf-8'), None, _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)

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
