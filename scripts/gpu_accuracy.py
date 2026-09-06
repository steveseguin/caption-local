"""Six-language condition probes against isolated, explicitly selected CUDA services."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from service_test_support import TestService

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=Path('evidence/gpu-validation/conditions'))
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
for model in ('small','medium','large-v3'):
    for precision in ('float16','int8_float16'):
        if subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip():
            raise SystemExit('GPU occupied; leave other workloads intact')
        name=f'{model}-{precision}'
        service=TestService(8772,args.output/(name+'.log'),['--model',model,'--device','cuda','--compute-type',precision])
        try:
            service.start()
            subprocess.run([sys.executable,'scripts/condition_probe.py','--output',str(args.output/(name+'.json'))],check=True)
            report=json.loads((args.output/(name+'.json')).read_text(encoding='utf-8'))
            assert report['health']['device']=='cuda'
            print(name,[(r['language'],r['condition'],round(r['wer'],2)) for r in report['results'] if r['wer']>.15],flush=True)
        finally:
            service.stop()
