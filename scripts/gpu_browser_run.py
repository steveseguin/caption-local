"""Own an isolated CUDA service, browser workload and NVIDIA/resource monitor."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
import psutil
from service_test_support import TestService
from summarize_browser_load import summarize

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model',default='medium')
parser.add_argument('--compute-type',default='float16')
parser.add_argument('--workers',type=int,default=2)
parser.add_argument('--beam-size',type=int,default=5)
parser.add_argument('--streams',type=int,default=12)
parser.add_argument('--seconds',type=int,default=180)
parser.add_argument('--interval',type=int,choices=[3,6,9],default=6)
modes=parser.add_mutually_exclusive_group()
modes.add_argument('--mixed',action='store_true')
modes.add_argument('--rotate-modes',action='store_true')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip():
    parser.error('GPU occupied; preserve existing workloads')
args.output.mkdir(parents=True,exist_ok=True)
stop_file=args.output/'stop-requested'
if stop_file.exists(): parser.error('Output contains a previous stop signal; choose a new output directory')
service=TestService(8772,args.output/'service.log',['--model',args.model,'--device','cuda',
    '--compute-type',args.compute_type,'--workers',str(args.workers),'--threads','4',
    '--beam-size',str(args.beam_size),'--max-streams',str(args.streams)])
finished=threading.Event(); samples=[]; monitor_errors=[]; thread=None
headers={'Authorization':'Bearer '+os.environ['CAPTION_API_KEY']} if os.environ.get('CAPTION_API_KEY') else {}
def health():
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8772/health',headers=headers),timeout=5) as response:
        return json.load(response)
def monitor():
    started=time.monotonic(); process=psutil.Process(service.process.pid)
    while not finished.is_set():
        try:
            info=health(); processes=[process]+process.children(recursive=True)
            gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu,power.draw','--format=csv,noheader,nounits'],text=True).strip()
            active=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],text=True).strip().splitlines()
            owned={str(p.pid) for p in processes}
            foreign=[line for line in active if line.split(',')[0].strip() not in owned]
            if foreign:
                monitor_errors.append('Competing GPU process: '+repr(foreign))
                stop_file.write_text('Competing GPU workload detected; drain capture and retain failure evidence.',encoding='utf-8')
            sample={'seconds':round(time.monotonic()-started,2),
                'rss_mib':round(sum(p.memory_info().rss for p in processes)/2**20,2),
                'cpu_seconds':round(sum(p.cpu_times().user+p.cpu_times().system for p in processes),3),
                'nvidia_smi':gpu, 'gpu_compute_processes':active, **{k:info[k] for k in ('ready','running','pending','completed','failed','rejected','queue_timeouts')}}
            samples.append(sample)
            (args.output/'monitor.json').write_text(json.dumps(samples,indent=2)+'\n',encoding='utf-8')
        except Exception as exc:
            monitor_errors.append(repr(exc))
        finished.wait(5)
try:
    began=time.monotonic(); service.start(); info=health()
    assert info['device']=='cuda',info
    (args.output/'configuration.json').write_text(json.dumps({'health':info,'startup_seconds':time.monotonic()-began,
        'arguments':{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}},indent=2)+'\n',encoding='utf-8')
    thread=threading.Thread(target=monitor,daemon=True); thread.start()
    command=[sys.executable,'scripts/browser_multilingual.py','--url','http://127.0.0.1:8772/capture-local.html',
        '--streams',str(args.streams),'--seconds',str(args.seconds),'--interval',str(args.interval),'--varied',
        '--output',str(args.output/'browser.json'),'--stop-file',str(stop_file)]
    if args.mixed: command.append('--mixed')
    if args.rotate_modes: command.append('--rotate-modes')
    result=subprocess.run(command)
finally:
    finished.set()
    if thread: thread.join(timeout=10)
    service.stop()
    (args.output/'monitor-errors.json').write_text(json.dumps(monitor_errors),encoding='utf-8')
if (args.output/'browser.json').exists():
    report=summarize(json.loads((args.output/'browser.json').read_text(encoding='utf-8')),samples)
    report['monitor_errors']=monitor_errors
    report['passed']=report['passed'] and not monitor_errors
    (args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='per_stream'},indent=2))
    if not report['passed']: raise SystemExit('Acceptance failed; original checks and evidence retained')
if result.returncode: raise SystemExit(result.returncode)
