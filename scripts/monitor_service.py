"""Sample CPU, memory and queue state without sending audio."""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.request
import psutil

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url',default='http://127.0.0.1:8772')
parser.add_argument('--pid',type=int,required=True,help='Server or container init PID')
parser.add_argument('--seconds',type=int,default=180)
parser.add_argument('--output',default='evidence/multistream/docker-monitor.json')
args=parser.parse_args()
process=psutil.Process(args.pid); samples=[]; start=time.monotonic()
while time.monotonic()-start < args.seconds:
    workers=[process]+process.children(recursive=True)
    headers={'Authorization':'Bearer '+os.environ['CAPTION_API_KEY']} if os.environ.get('CAPTION_API_KEY') else {}
    with urllib.request.urlopen(urllib.request.Request(args.url+'/health',headers=headers),timeout=5) as response: health=json.load(response)
    samples.append({'seconds':round(time.monotonic()-start,2),
        'rss_mib':round(sum(p.memory_info().rss for p in workers)/2**20,2),
        'cpu_seconds':round(sum(p.cpu_times().user+p.cpu_times().system for p in workers),3),
        'threads':sum(p.num_threads() for p in workers),
        'ready':health['ready'],'running':health['running'],'pending':health['pending'],
        'completed':health['completed'],'failed':health['failed'],
        'rejected':health['rejected'],'queue_timeouts':health['queue_timeouts']})
    Path(args.output).write_text(json.dumps(samples,indent=2)+'\n', encoding='utf-8')
    assert health['ready'] and health['failed']==0 and health['queue_timeouts']==0, health
    time.sleep(5)
print(json.dumps({'samples':len(samples),'peak_rss_mib':max(s['rss_mib'] for s in samples),
    'mean_cpu_cores':round((samples[-1]['cpu_seconds']-samples[0]['cpu_seconds'])/(samples[-1]['seconds']-samples[0]['seconds']),2)}))
