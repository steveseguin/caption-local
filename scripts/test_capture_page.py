"""Isolated real CPU regression: original/new pages, six languages, mock-only relay."""
import os
import argparse
from pathlib import Path
import subprocess
import sys
from service_test_support import TestService

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--functional-only', action='store_true')
args = parser.parse_args()
output = root / 'evidence/capture-local'
output.mkdir(parents=True, exist_ok=True)
service = TestService(8772, output / 'service.log',
    ['--model', 'small', '--device', 'cpu', '--compute-type', 'int8', '--workers', '8', '--threads', '2', '--beam-size', '5'])
try:
    service.start()
    configurations = [] if args.functional_only else [('original', '/', 8, False),
                                      ('local-page', '/capture-local.html', 8, False),
                                      ('mixed', '/capture-local.html', 4, True)]
    for name, path, streams, mixed in configurations:
        command = [sys.executable, 'scripts/browser_multilingual.py', '--url', 'http://127.0.0.1:8772'+path,
                   '--streams', str(streams), '--seconds', '180', '--varied', '--output', str(output / (name+'.json'))]
        if mixed:
            command.append('--mixed')
        subprocess.run(command, cwd=root, check=True)
        print(name+' passed', flush=True)
    env = {**os.environ, 'CAPTION_TEST_URL': 'http://127.0.0.1:8772/capture-local.html',
           'CAPTION_NINJA_CHECKOUT': str(root / 'samples/captionninja'),
           'CAPTION_TEST_OUTPUT_DIR': str(output)}
    for script in ('browser_recovery.py', 'browser_translation.py', 'browser_devices.py', 'browser_smoke.py'):
        subprocess.run([sys.executable, 'scripts/'+script], cwd=root, env=env, check=True)
finally:
    service.stop()
