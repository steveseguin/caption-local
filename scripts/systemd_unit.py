"""Print a user systemd unit; does not install or enable it."""
import argparse
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model', default='small')
parser.add_argument('--port', type=int, default=8765)
args = parser.parse_args()
if not 1 <= args.port <= 65535 or any(c in args.model for c in '\r\n\0'):
    parser.error('Invalid model or port')

def quote(text):
    return '"' + str(text).replace('\\','\\\\').replace('"','\\"').replace('%','%%').replace('$','$$') + '"'

print(f'''[Unit]
Description=Caption Local CPU transcription
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
WorkingDirectory={str(root).replace('%', '%%')}
ExecStart={quote(root / '.venv/bin/python')} {quote(root / 'server.py')} --model {quote(args.model)} --device cpu --offline --port {args.port}
Restart=on-failure
RestartSec=3
TimeoutStopSec=100
NoNewPrivileges=true
PrivateTmp=true
UMask=0077
Environment=HF_HUB_DISABLE_TELEMETRY=1

[Install]
WantedBy=default.target
''')
