"""Sustained real inference against a running CPU deployment."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid
import psutil
from faster_whisper.audio import decode_audio

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url',default='http://127.0.0.1:8772')
parser.add_argument('--requests',type=int,default=250)
parser.add_argument('--pid',type=int,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
english=decode_audio(str(root/'samples/jfk.wav')).astype('<f4').tobytes()
spanish=decode_audio(str(root/'samples/spanish.wav')).astype('<f4').tobytes()
process=psutil.Process(args.pid)
def call(audio,query='language=en',identifier=None):
    request=urllib.request.Request(args.url+'/transcribe?'+query,data=audio,headers={
        'Content-Type':'application/octet-stream','X-Caption-Local':'1','X-Request-ID':identifier or str(uuid.uuid4())})
    try:
        with urllib.request.urlopen(request,timeout=90) as response: return response.status,json.load(response)
    except urllib.error.HTTPError as error: return error.code,json.load(error)
started=time.monotonic(); samples=[]; total_audio=0; total_inference=0
with ThreadPoolExecutor(max_workers=8) as pool:
    concurrent=list(pool.map(lambda _:call(english),range(8)))
assert sum(status==200 for status,_ in concurrent)==1,concurrent
assert all(status in (200,429) for status,_ in concurrent)
for n in range(args.requests):
    audio=spanish if n%5==0 else english
    query='language=es&mode=both' if n%5==0 else 'language=en'
    identifier=str(uuid.uuid4())
    status,result=call(audio,query,identifier)
    assert status==200 and result['text'],(status,result)
    if n%5==0:
        assert 'teatro' in result['transcript'].lower(),result
        assert 'theater' in result['translation'].lower() or 'theatre' in result['translation'].lower(),result
    if n%20==0:
        assert call(audio,query,identifier)==(status,result), 'Retry changed committed response'
    total_audio+=result['audio_seconds']; total_inference+=result['inference_seconds']
    if n%10==0:
        memory=(process.memory_info().rss+sum(p.memory_info().rss for p in process.children(recursive=True) if p.is_running()))/1024**2
        sample={'request':n,'elapsed_seconds':round(time.monotonic()-started,1),'rss_mib':round(memory,1)}
        samples.append(sample); print(json.dumps(sample),flush=True)
warm=[s['rss_mib'] for s in samples if s['request']>=50]
assert max(warm)-min(warm)<128,warm
assert total_inference < total_audio,(total_inference,total_audio)
result={'requests':args.requests,'elapsed_seconds':round(time.monotonic()-started,1),
        'audio_seconds':round(total_audio,1),'inference_seconds':round(total_inference,1),
        'warm_rss_range_mib':[min(warm),max(warm)],'concurrent_admission':'1 accepted, 7 busy',
        'samples':samples,'idempotent_retries':True,'english_and_spanish_translation':True}
(root/'evidence/api-soak.json').write_text(json.dumps(result,indent=2)+'\n')
print('API SOAK PASSED',flush=True)
