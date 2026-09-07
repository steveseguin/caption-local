"""Copy the versioned Caption Local browser bundle to a captionninja checkout."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ('capture.css', 'app.js', 'audio-buffer.js', 'pcm-worklet.js', 'ws-publisher.js', 'relay-config.js', 'private-relay-client.js',
         'local-connection.js', 'local-page.js')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkout', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not (args.checkout / 'overlay.html').is_file():
        parser.error('Expected a captionninja checkout with overlay.html')
    outputs = {args.checkout / 'capture-local.html': (ROOT / 'static/capture-local.html').read_bytes().replace(
        b'/static/', b'./caption-local/')}
    outputs[args.checkout / 'caption-local/LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    outputs[args.checkout / 'relay-config.js'] = (ROOT / 'static/relay-config.js').read_bytes()
    outputs[args.checkout / 'private-relay-client.js'] = (ROOT / 'static/private-relay-client.js').read_bytes()
    outputs[args.checkout / 'ws-publisher.js'] = (ROOT / 'static/ws-publisher.js').read_bytes()
    for name in FILES:
        outputs[args.checkout / 'caption-local' / name] = (ROOT / 'static' / name).read_bytes()
    manifest = {path.relative_to(args.checkout).as_posix(): hashlib.sha256(data).hexdigest()
                for path, data in outputs.items()}
    outputs[args.checkout / 'caption-local/manifest.json'] = (json.dumps({
        'source': 'https://github.com/steveseguin/caption-local', 'bundle_schema': 1,
        'sha256': manifest}, indent=2) + '\n').encode()
    for path, data in outputs.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit(f'Bundle differs: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print('Bundle verified' if args.check else 'Bundle synchronized')


if __name__ == '__main__':
    main()
