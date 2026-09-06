"""Sequential isolated GPU quality/capacity matrix; preserve unsuccessful cells."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=Path('evidence/gpu-validation'))
parser.add_argument('--models', nargs='+', default=['small', 'medium', 'large-v3'])
parser.add_argument('--precisions', nargs='+', default=['float16', 'int8_float16'])
parser.add_argument('--beams', type=int, nargs='+', default=[5])
parser.add_argument('--workers', type=int, nargs='+', default=[1, 2, 4])
parser.add_argument('--rounds', type=int, default=2)
parser.add_argument('--skip-cpu', action='store_true')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
results = []


def run(name, command):
    started = time.monotonic()
    with (args.output/(name+'.log')).open('w', encoding='utf-8') as log:
        completed = subprocess.run([sys.executable, *command], stdout=log, stderr=log)
    result = {'name': name, 'exit_code': completed.returncode,
              'wall_seconds': round(time.monotonic()-started, 3)}
    results.append(result)
    (args.output/'matrix-status.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result), flush=True)


for model in args.models:
    for precision in args.precisions:
        for beam in args.beams:
            name = f'{model}-{precision}-quality-b{beam}'
            run(name, ['scripts/quality_gate.py', model, '--device', 'cuda', '--compute-type', precision,
                       '--beam-size', str(beam), '--output', str(args.output/(name+'.json'))])
            for workers in args.workers:
                name = f'{model}-{precision}-w{workers}-b{beam}'
                run(name, ['scripts/profile_gpu.py', '--model', model, '--device', 'cuda',
                           '--compute-type', precision, '--workers', str(workers), '--rounds', str(args.rounds),
                           '--beam-size', str(beam), '--output', str(args.output/(name+'.json'))])
if not args.skip_cpu:
    run('small-cpu-int8-w8-b5', ['scripts/profile_gpu.py', '--model', 'small', '--device', 'cpu',
        '--compute-type', 'int8', '--workers', '8', '--threads', '2', '--rounds', '1',
        '--output', str(args.output/'small-cpu-int8-w8-b5.json')])
