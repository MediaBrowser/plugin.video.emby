if __name__ == "__main__":
    import sys
    DataSend = "EVENT %s" % ";".join(sys.argv)
    import socket
    import xbmc
    XbmcMonitor = None
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    for _ in range(60):  # 60 seconds timeout
        try:
            sock.connect(('127.0.0.1', 57342))
            sock.send(DataSend.encode('utf-8'))
            sock.recv(1024)
            break
        except:
            if not XbmcMonitor:
                XbmcMonitor = xbmc.Monitor()

            if XbmcMonitor.waitForAbort(0.1):
                break

    sock.close()
