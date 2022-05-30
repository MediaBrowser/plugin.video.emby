import sys
import socket
import time

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

if __name__ == "__main__":
    for _ in range(60):  # 60 seconds timeout
        try:
            sock.connect(('127.0.0.1', 57342))
            DataSend = "EVENT %s" % ";".join(sys.argv)
            sock.send(DataSend.encode('utf-8'))
            sock.recv(128)
            break
        except:
            time.sleep(1)
