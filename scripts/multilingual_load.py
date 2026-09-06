"""Isolated service load probe with a supplied public/synthetic fixture manifest.

Each independent producer repeats its fixture on a six-second schedule, retaining
one outstanding request. This measures backlog honestly rather than dropping late
work. It is not a browser/word-aligned latency test or population accuracy study.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import httpx
import numpy as np
import psutil
from faster_whisper.audio import decode_audio
from service_test_support import require_free_port

ROOT = Path(__file__).resolve().parents[1]


def wer(reference, text):
    a, b = re.findall(r'\w+', reference.casefold()), re.findall(r'\w+', text.casefold())
    row = list(range(len(b)+1))
    for index, word in enumerate(a, 1):
        nxt = [index]
        for j, other in enumerate(b, 1):
            nxt.append(min(row[j]+1, nxt[-1]+1, row[j-1]+(word != other)))
        row = nxt
    return row[-1]/max(1, len(a))


async def main(args, process, report):
    base = f'http://127.0.0.1:{args.port}'
    fixtures = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    audios = [decode_audio(str(ROOT / item['path'])).astype('<f4') for item in fixtures]
    assert all(0 < len(audio) <= 12*16000 for audio in audios)
    report['fixtures'] = fixtures
    report['fixture_durations'] = [len(audio)/16000 for audio in audios]
    headers={'Authorization':'Bearer '+os.environ['CAPTION_API_KEY']} if os.environ.get('CAPTION_API_KEY') else {}
    async with httpx.AsyncClient(timeout=60, limits=httpx.Limits(max_connections=80),headers=headers) as client:
        start = time.perf_counter()
        for _ in range(240):
            if process.poll() is not None:
                raise RuntimeError('Server exited during startup; inspect server log')
            try:
                response = await client.get(base+'/health')
                if response.status_code == 200:
                    report['health'] = response.json()
                    break
            except httpx.TransportError:
                pass
            await asyncio.sleep(.5)
        else:
            raise TimeoutError('Model did not become ready')
        report['startup_seconds'] = time.perf_counter()-start
        report['quality'] = []
        for item, audio in zip(fixtures, audios):
            response = await client.post(base+'/transcribe', params={'language':item['language'], 'mode':'both'},
                headers={'X-Caption-Local':'1','Content-Type':'application/octet-stream'}, content=audio.tobytes())
            result = response.json()
            report['quality'].append({'language':item['language'], 'status':response.status_code,
                'wer':wer(item['text'],result.get('transcript','')),
                'translation_theatre_preserved':any(word in result.get('translation','').lower() for word in ('theater','theatre')),
                'result':result})
        await client.delete(base+'/streams/legacy', headers={'X-Caption-Local':'1'})
        for streams in args.streams:
            prefix = uuid.uuid4().hex
            started = time.perf_counter()
            cell = {'streams':streams, 'requests':[], 'resources':[]}
            report['loads'].append(cell)
            async def producer(index):
                item = fixtures[index % len(fixtures)]
                audio = audios[index % len(audios)]
                sid = f'{prefix}-{index}'
                try:
                    for cycle in range(args.rounds):
                        due = started + cycle*6
                        await asyncio.sleep(max(0, due-time.perf_counter()))
                        before = time.perf_counter()
                        mode = 'both' if args.mixed and index % 3 == 0 else 'transcribe'
                        if args.rotate_modes:
                            mode = ('transcribe','translate','both')[(index+cycle)%3]
                        response = await client.post(base+'/transcribe', params={'language':item['language'], 'mode':mode},
                            content=audio.tobytes(), headers={'X-Caption-Local':'1', 'X-Stream-ID':sid,
                            'X-Request-ID':f'cycle-{cycle:08}', 'Content-Type':'application/octet-stream'})
                        body = response.json()
                        cell['requests'].append({'stream':index, 'cycle':cycle, 'language':item['language'],
                            'mode':mode, 'status':response.status_code, 'response_seconds':time.perf_counter()-before,
                            'arrival_lag_seconds':time.perf_counter()-due, 'result':body})
                        if response.status_code != 200:
                            break
                finally:
                    await client.delete(base+f'/streams/{sid}',headers={'X-Caption-Local':'1'})
            tasks = [asyncio.create_task(producer(index)) for index in range(streams)]
            while not all(task.done() for task in tasks):
                family = [psutil.Process(process.pid)] + psutil.Process(process.pid).children(recursive=True)
                health = (await client.get(base+'/health')).json()
                cell['resources'].append({'seconds':time.perf_counter()-started,
                    'rss_mib':sum(p.memory_info().rss for p in family)/2**20,
                    'cpu_seconds':sum(sum(p.cpu_times()[:2]) for p in family),
                    'running':health['running'], 'pending':health['pending'], 'ready':health['ready']})
                await asyncio.sleep(1)
            await asyncio.gather(*tasks)
            latencies = sorted(row['response_seconds'] for row in cell['requests'])
            cell.update(wall_seconds=time.perf_counter()-started,
                p95_seconds=latencies[min(len(latencies)-1, int(len(latencies)*.95))],
                max_lag_seconds=max(row['arrival_lag_seconds'] for row in cell['requests']),
                errors=sum(row['status']!=200 for row in cell['requests']),
                late=sum(row['arrival_lag_seconds']>6 for row in cell['requests']))
            print(json.dumps({key:value for key,value in cell.items() if key not in ('requests','resources')}),flush=True)
            args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'samples/multilingual/manifest.json')
    parser.add_argument('--model',default='small')
    parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--threads',type=int,default=2)
    parser.add_argument('--beam-size',type=int,default=5)
    parser.add_argument('--streams',type=int,nargs='+',default=[1,2,4,8,12,24])
    parser.add_argument('--rounds',type=int,default=5)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--mixed',action='store_true')
    modes.add_argument('--rotate-modes',action='store_true',help='Rotate transcription, translation and both across every language and cycle')
    parser.add_argument('--port',type=int,default=8773)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.device=='cuda' and subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip():
        parser.error('GPU occupied by an existing compute process')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    require_free_port(args.port)
    report={'configuration':{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()},'loads':[]}
    with args.output.with_suffix('.server.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--offline','--port',str(args.port),
            '--model',args.model,'--device',args.device,'--workers',str(args.workers),'--threads',str(args.threads),
            '--beam-size',str(args.beam_size),'--max-streams','64'],cwd=ROOT,stdout=log,stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            asyncio.run(main(args,process,report))
        except Exception as exc:
            report['error']=repr(exc)
            raise
        finally:
            args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
            if process.poll() is None:
                for child in psutil.Process(process.pid).children(recursive=True):
                    child.terminate()
                process.terminate()
                process.wait(timeout=15)
