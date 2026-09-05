"""Own a temporary loopback service; never stop a pre-existing listener."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import psutil


def require_free_port(port):
    # TCP connect probes can time out on Windows firewall rules; bind probes
    # mistake TIME_WAIT for listeners. Inspect actual listening sockets instead.
    if any(connection.status==psutil.CONN_LISTEN and connection.laddr.port==port
           for connection in psutil.net_connections(kind='tcp')):
        raise RuntimeError(f'Test port {port} is already served; choose another port')


class TestService:
    def __init__(self, port, log, options=()):
        self.port=port; self.log=log; self.options=list(options); self.process=None; self.output=None

    def start(self):
        require_free_port(self.port)
        self.output=Path(self.log).open('a',encoding='utf-8')
        self.process=subprocess.Popen([sys.executable,'server.py','--offline','--port',str(self.port),*self.options],
            cwd=Path(__file__).resolve().parents[1],stdout=self.output,stderr=self.output,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        headers={'Authorization':'Bearer '+os.environ['CAPTION_API_KEY']} if os.environ.get('CAPTION_API_KEY') else {}
        for _ in range(180):
            if self.process.poll() is not None:
                raise RuntimeError('Test server exited during startup')
            try:
                request=urllib.request.Request(f'http://127.0.0.1:{self.port}/health',headers=headers)
                with urllib.request.urlopen(request,timeout=1) as response:
                    if json.load(response)['ready']: return
            except OSError:
                pass
            time.sleep(.5)
        raise TimeoutError('Test service did not become ready')

    def stop(self):
        if self.process and self.process.poll() is None:
            children=psutil.Process(self.process.pid).children(recursive=True)
            for child in children:
                child.terminate()
            psutil.wait_procs(children,timeout=10)
            self.process.terminate(); self.process.wait(timeout=15)
        if self.output: self.output.close()
