"""Synchronized independent streams with real PCM inference; no relay or audio upload off-host."""
import argparse
import asyncio
import io
import json
from pathlib import Path
import statistics
import time
import uuid
import httpx
import numpy as np
import psutil
import pyarrow.parquet as pq
from faster_whisper.audio import decode_audio

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://127.0.0.1:8771')
parser.add_argument('--rounds', type=int, default=30)
parser.add_argument('--streams', type=int, default=12)
parser.add_argument('--pid', type=int, required=True)
parser.add_argument('--mixed', action='store_true')
parser.add_argument('--profile-only', action='store_true', help='Record translation quality failures without accepting them as a quality pass')
parser.add_argument('--output', default='evidence/multistream/sustained-base.json')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
rows = pq.read_table(root/'samples/librispeech.parquet').to_pylist()
audios = [decode_audio(io.BytesIO(r['audio']['bytes']))[:96000] for r in rows[:args.streams]]
audios = [np.pad(a,(0,max(0,96000-len(a)))).astype('<f4').tobytes() for a in audios]
spanish = decode_audio(str(root/'samples/spanish.wav')).astype('<f4').tobytes()
process = psutil.Process(args.pid)
results=[]; memory=[]; quality_errors=[]
async def main():
    async with httpx.AsyncClient(timeout=60, limits=httpx.Limits(max_connections=32)) as client:
        health=(await client.get(args.url+'/health')).json()
        started=time.monotonic(); cpu_start=process.cpu_times(); prefix=uuid.uuid4().hex[:12]
        async def stream(n):
            for cycle in range(args.rounds):
                due=started+cycle*6
                await asyncio.sleep(max(0,due-time.monotonic()))
                translated=args.mixed and n%3==0
                data=spanish if translated else audios[n]
                query='language=es&mode=both' if translated else 'language=en&window=1&final=0'
                t=time.monotonic()
                headers={'X-Caption-Local':'1','X-Stream-ID':f'{prefix}-{n:02}',
                         'X-Request-ID':f'round-{cycle:08}', 'Content-Type':'application/octet-stream'}
                response=await client.post(args.url+'/transcribe?'+query,content=data,headers=headers)
                result=response.json()
                assert response.status_code==200, (n,cycle,response.status_code,result)
                assert result['stream_id']==headers['X-Stream-ID'] and result['text'], result
                if translated:
                    assert 'teatro' in result['transcript'].lower(),result
                    if not any(w in result['translation'].lower() for w in ['theater','theatre']):
                        quality_errors.append({'stream':n,'round':cycle,'translation':result['translation']})
                        assert args.profile_only,result
                results.append({'stream':n,'round':cycle,'latency':round(time.monotonic()-t,3),
                                'lag':round(time.monotonic()-due,3),'queue':result['queue_seconds'],
                                'inference':result['inference_seconds'],'text':result['text']})
                if n==0:
                    memory.append(round(process.memory_info().rss/2**20,2))
                    print(json.dumps({'round':cycle,'rss_mib':memory[-1],'latency':results[-1]['latency']}),flush=True)
        await asyncio.gather(*(stream(n) for n in range(args.streams)))
        for n in range(args.streams):
            assert len({r['text'] for r in results if r['stream']==n})==1, 'Concurrent decode changed a repeated input'
        wall=time.monotonic()-started; cpu_end=process.cpu_times()
        latency=sorted(r['latency'] for r in results)
        report={'health':health,'streams':args.streams,'rounds':args.rounds,'mixed_translation':args.mixed,
                'quality_errors':quality_errors,'profile_only':args.profile_only,
                'requests':len(results),'wall_seconds':round(wall,3),
                'cpu_seconds':round(cpu_end.user+cpu_end.system-cpu_start.user-cpu_start.system,3),
                'latency_p50':latency[len(latency)//2], 'latency_p95':latency[int(len(latency)*.95)],
                'max_lag':max(r['lag'] for r in results),'late_over_6s':sum(r['lag']>6 for r in results),
                'rss_mib':memory,'results':results}
        Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('results','rss_mib','quality_errors')}),flush=True)
        warm=memory[5:] or memory
        middle=max(1,len(warm)//2)
        assert max(memory)<2048, 'RSS exceeded 2 GiB envelope'
        assert statistics.median(warm[middle:] or warm)-statistics.median(warm[:middle])<128, 'Warm median RSS grew by over 128 MiB'
        for n in range(args.streams):
            response=await client.delete(args.url+f'/streams/{prefix}-{n:02}',headers={'X-Caption-Local':'1'})
            assert response.status_code==200,response.text
asyncio.run(main())
