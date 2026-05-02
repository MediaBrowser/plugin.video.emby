import sys
Param = sys.argv[1:]

XbmcMonitor = None

def sleep():
    global XbmcMonitor

    if not XbmcMonitor:
        import xbmc
        XbmcMonitor = xbmc.Monitor()

    if XbmcMonitor.waitForAbort(0.1):
        return True

    return False

if not Param:
    from hooks import webservice

    if webservice.start():
        import hooks.monitor
        hooks.monitor.StartUp()
elif len(Param) == 1 or Param[1]:
    import socket
    Argv = ';'.join(["service"] + Param)
    DataSend = f"EVENT {Argv}".encode('utf-8')
    Finished = False

    for _ in range(60):  # 60 seconds timeout
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(0.1)
            sock.connect(('127.0.0.1', 57342))
            sock.send(DataSend)

            while True:
                try:
                    sock.recv(1024)
                    Finished = True
                    break
                except TimeoutError:
                    if sleep():
                        Finished = True
                        break
                except Exception as error:
                    if str(error).find("timed out") != -1 or str(error).find("timeout") != -1: # workaround when TimeoutError not raised
                        if sleep():
                            Finished = True
                            break
                    else:
                        break

            sock.close()

            if Finished:
                break
        except:
            sock.close()

            if sleep():
                break
