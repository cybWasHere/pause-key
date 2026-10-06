"""Minimal Marionette (Firefox remote protocol) client for the tests."""
import json, socket, time


class Marionette:
    def __init__(self, port):
        for _ in range(100):
            try:
                self.s = socket.create_connection(("127.0.0.1", port)); break
            except OSError:
                time.sleep(0.2)
        self.buf, self.n = b"", 0
        self.read()

    def recv(self):
        chunk = self.s.recv(65536)
        if not chunk:  # Firefox exited or crashed; without this the loops below spin forever
            raise ConnectionError("Marionette closed the connection")
        return chunk

    def read(self):
        while b":" not in self.buf:
            self.buf += self.recv()
        n, rest = self.buf.split(b":", 1)
        n = int(n)
        while len(rest) < n:
            rest += self.recv()
        self.buf = rest[n:]
        return json.loads(rest[:n])

    def __call__(self, name, **p):
        self.n += 1
        d = json.dumps([0, self.n, name, p]).encode()
        self.s.sendall(str(len(d)).encode() + b":" + d)
        while True:
            r = self.read()
            if r[0] == 1 and r[1] == self.n:
                if r[2]:
                    raise RuntimeError(f"{name}: {r[2]}")
                return r[3]
