"""Run a temporary real Caddy TLS proxy and Node relay with a private test CA.

No trust-store installation, public listener, public room or GPU inference.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
import urllib.request
from service_test_support import require_free_port

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--caddy', type=Path, required=True)
    parser.add_argument('--openssl', default='openssl')
    parser.add_argument('--checkout', type=Path, default=ROOT/'samples/captionninja')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for port in (8797, 8843): require_free_port(port)
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    result = {'passed': False, 'scope': 'real TLS and WSS proxy on loopback, Node clients verify ephemeral CA; not public browser deployment'}
    children = []
    with tempfile.TemporaryDirectory(prefix='caption-relay-tls-') as directory:
        tmp = Path(directory)
        def run(command):
            return subprocess.run(command, cwd=tmp, capture_output=True, text=True, check=True, creationflags=flags, timeout=30)
        try:
            version = run([str(args.caddy.resolve()), 'version']).stdout.strip()
            run([args.openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.crt',
                 '-subj', '/CN=Caption-Relay-Test-CA', '-days', '1'])
            run([args.openssl, 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'server.key', '-out', 'server.csr', '-subj', '/CN=localhost'])
            (tmp/'extensions.txt').write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n', encoding='utf-8')
            run([args.openssl, 'x509', '-req', '-in', 'server.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key', '-CAcreateserial',
                 '-out', 'server.crt', '-days', '1', '-extfile', 'extensions.txt'])
            config = {'origins': ['https://localhost:8843'], 'rooms': {'source': {role: secrets.token_urlsafe(32) for role in ('read', 'write')}}}
            config_path = tmp/'rooms.private.json'; config_path.write_text(json.dumps(config), encoding='utf-8')
            proxy = {'admin': {'disabled': True, 'config': {'persist': False}},
                'storage': {'module': 'file_system', 'root': str(tmp/'storage')},
                'apps': {'tls': {'certificates': {'load_files': [{'certificate': str(tmp/'server.crt'), 'key': str(tmp/'server.key')}] }},
                    'http': {'servers': {'private-test': {'listen': ['127.0.0.1:8843'],
                        'tls_connection_policies': [{}], 'automatic_https': {'disable': True},
                        'routes': [{'handle': [{'handler': 'reverse_proxy', 'upstreams': [{'dial': '127.0.0.1:8797'}]}]}]}}}}}
            proxy_path = tmp/'caddy.json'; proxy_path.write_text(json.dumps(proxy), encoding='utf-8')
            run([str(args.caddy.resolve()), 'validate', '--config', str(proxy_path)])
            env = {**os.environ, 'CAPTION_RELAY_CONFIG': str(config_path), 'PORT': '8797', 'HOST': '127.0.0.1',
                   'XDG_CONFIG_HOME': str(tmp/'config'), 'XDG_DATA_HOME': str(tmp/'data')}
            log = (tmp/'process.log').open('w', encoding='utf-8')
            try:
                for command in (['node', str(args.checkout.resolve()/'relay/server.cjs')],
                    [str(args.caddy.resolve()), 'run', '--config', str(proxy_path)]):
                    children.append(subprocess.Popen(command, cwd=tmp, env=env, stdout=log, stderr=log, creationflags=flags))
                import ssl
                tls = ssl.create_default_context(cafile=str(tmp/'ca.crt'))
                for _ in range(100):
                    if any(child.poll() is not None for child in children): raise RuntimeError('Test service exited')
                    try:
                        with urllib.request.urlopen('https://127.0.0.1:8843/health', context=tls, timeout=1) as response:
                            health = json.load(response)
                        break
                    except OSError: time.sleep(.1)
                else: raise TimeoutError('TLS health did not become ready')
                probe = run(['node', str(args.checkout.resolve()/'relay/tls-probe.cjs'), 'wss://127.0.0.1:8843/', str(config_path), str(tmp/'ca.crt')])
                result.update(json.loads(probe.stdout), caddy=version, healthProtocol=health['protocol'],
                    caddyBinarySha256=hashlib.sha256(args.caddy.read_bytes()).hexdigest(), trustStoreChanged=False)
            finally:
                for child in reversed(children):
                    if child.poll() is None: child.terminate(); child.wait(timeout=15)
                log.close()
        finally:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
