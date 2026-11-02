"""One running instance per app-home folder; a second launch raises the first instance's window and exits."""
from __future__ import annotations

import hashlib

from PySide6.QtCore import QLockFile
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def _server_name(home):
    return "blokjutsu-" + hashlib.sha1(str(home.resolve()).encode()).hexdigest()[:12]


class SingleInstance:
    def __init__(self, home):
        home.mkdir(parents=True, exist_ok=True)
        self.name = _server_name(home)
        self.lock = QLockFile(str(home / "instance.lock"))
        self.lock.setStaleLockTime(0)          # stale = owning PID no longer running
        self.server = None

    def acquire(self):
        """True if this process is the primary instance; otherwise pings the primary and returns False."""
        if self.lock.tryLock(200):
            return True
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if socket.waitForConnected(1000):
            socket.write(b"raise")
            socket.waitForBytesWritten(1000)
        return False

    def listen(self, on_activate):
        QLocalServer.removeServer(self.name)
        self.server = QLocalServer()
        self.server.newConnection.connect(lambda: self._accept(on_activate))
        self.server.listen(self.name)

    def _accept(self, on_activate):
        while self.server.hasPendingConnections():
            self.server.nextPendingConnection().deleteLater()
            on_activate()
