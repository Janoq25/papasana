"""Puente TCP local para Docker Desktop cuando WSL mirrored no publica localhost."""
import socket
import socketserver
import subprocess
import threading
import logging
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HOST,PORT="127.0.0.1",18080

class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        child=None
        self.request.settimeout(120)
        try:
            # El transporte sigue siendo binario; no se inspeccionan credenciales ni HTTP.
            child=subprocess.Popen(
                ["docker","compose","exec","-T","frontend","nc","127.0.0.1","80"],
                cwd=str(ROOT),stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,bufsize=0,creationflags=subprocess.CREATE_NO_WINDOW)
            def upstream():
                try:
                    while True:
                        data=self.request.recv(65536)
                        if not data:break
                        child.stdin.write(data)
                        child.stdin.flush()
                except (OSError,BrokenPipeError):pass
                finally:
                    try:child.stdin.close()
                    except OSError:pass
            thread=threading.Thread(target=upstream,daemon=True)
            thread.start()
            while True:
                data=child.stdout.read(65536)
                if not data:break
                self.request.sendall(data)
        except (OSError,subprocess.SubprocessError):
            pass
        finally:
            if child is not None:
                if child.poll() is None:child.terminate()
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:child.kill()
            try:self.request.shutdown(socket.SHUT_RDWR)
            except OSError:pass

class Server(socketserver.ThreadingTCPServer):
    daemon_threads=True
    allow_reuse_address=False

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s")
    with Server((HOST,PORT),Handler) as server:
        logging.info("PapaSana local disponible en http://%s:%s",HOST,PORT)
        server.serve_forever()

