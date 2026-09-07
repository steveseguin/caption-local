"""Isolated real inference: original/new pages, six languages, mock-only relay."""
import os
import argparse
import json
from pathlib import Path
import subprocess
import sys
from service_test_support import TestService

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--functional-only', action='store_true')
parser.add_argument('--model', default='small')
parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
parser.add_argument('--compute-type', default='int8')
parser.add_argument('--workers', type=int, default=8)
parser.add_argument('--threads', type=int, default=2)
parser.add_argument('--output', type=Path, default=root/'evidence/capture-local')
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
if args.device == 'cuda' and subprocess.check_output(
        ['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True).strip():
    parser.error('GPU occupied; preserve existing workloads')
(output/'functional-configuration.json').write_text(json.dumps(
    {key:str(value) if isinstance(value,Path) else value for key,value in vars(args).items()},
    indent=2)+'\n', encoding='utf-8')
service = TestService(8772, output / 'service.log',
    ['--model', args.model, '--device', args.device, '--compute-type', args.compute_type,
     '--workers', str(args.workers), '--threads', str(args.threads), '--beam-size', '5'])
try:
    health=service.start()
    assert health['device']==args.device
    (output/'service-health.json').write_text(json.dumps(health,indent=2)+'\n',encoding='utf-8')
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
