import socket, sys, json
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('127.0.0.1', 9106))
s.listen(5)
while True:
    try:
        conn, addr = s.accept()
        conn.close()
    except: pass
