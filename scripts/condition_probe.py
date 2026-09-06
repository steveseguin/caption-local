"""Explore clean, quiet and noisy synthetic speech without weakening quality gates."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import httpx
import numpy as np
from faster_whisper.audio import decode_audio
from multilingual_load import wer

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url',default='http://127.0.0.1:8772')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if urlsplit(args.url).hostname not in ('127.0.0.1','localhost','::1'):
    parser.error('Use localhost or a local SSH tunnel')
root=Path(__file__).resolve().parents[1]
fixtures=json.loads((root/'samples/multilingual/manifest.json').read_text(encoding='utf-8'))
headers={'X-Caption-Local':'1','Content-Type':'application/octet-stream'}
if os.environ.get('CAPTION_API_KEY'): headers['Authorization']='Bearer '+os.environ['CAPTION_API_KEY']
results=[]
with httpx.Client(timeout=60,headers=headers) as client:
    ready=client.get(args.url+'/health'); ready.raise_for_status()
    health=ready.json()
    for item in fixtures:
        audio=decode_audio(str(root/item['path']))
        noise=np.random.default_rng(42).normal(0,float(np.sqrt(np.mean(audio**2)))/3.1623,len(audio))
        for condition,data in [('clean',audio),('quiet_26db',audio*.05),('noise_10db_snr',np.clip(audio+noise,-1,1))]:
            response=client.post(args.url+'/transcribe',params={'language':item['language'],'mode':'both'},content=data.astype('<f4').tobytes())
            result=response.json()
            results.append({'language':item['language'],'condition':condition,'status':response.status_code,
                'wer':wer(item['text'],result.get('transcript','')),'result':result})
    client.delete(args.url+'/streams/legacy')
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps({'health':health,'seed':42,'results':results,'scope':'Synthetic robustness observations; not a new acceptance gate'},indent=2,ensure_ascii=False),encoding='utf-8')
assert all(result['status']==200 for result in results)
print('Condition probe recorded all 18 real inference results')
