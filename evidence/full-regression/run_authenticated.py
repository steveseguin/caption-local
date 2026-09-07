import json, os, secrets, subprocess, sys, time, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from service_test_support import TestService
out=ROOT/'samples/full-review/authenticated';out.mkdir(exist_ok=True)
key=secrets.token_urlsafe(32)
os.environ['CAPTION_API_KEY']=key
os.environ['PYTHONUTF8']='1'
os.environ['CAPTION_TEST_OUTPUT_DIR']=str(out)
os.environ['CAPTION_TEST_URL']='http://127.0.0.1:8773'
service=TestService(8773,out/'service.log',['--model','small','--device','cpu','--compute-type','int8','--workers','2','--threads','4','--log-requests'])
report={'scope':'real offline CPU inference, synthetic/public fixtures, local token and metadata log checks','passed':False,'commands':[]}
try:
    start=time.monotonic();report['health']=service.start();report['startup_seconds']=time.monotonic()-start
    for name,args in [('native',['scripts/smoke_api.py','--url','http://127.0.0.1:8773','--spanish','samples/spanish.wav','--output',str(out/'native.json')]),
                      ('sdk',['scripts/smoke_compat.py','--url','http://127.0.0.1:8773','--output',str(out/'sdk.json')]),
                      ('browser-auth',['scripts/browser_auth.py'])]:
        began=time.monotonic()
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        report['commands'].append({'name':name,'exit_code':result.returncode,'seconds':time.monotonic()-began})
        print(name, 'exit', result.returncode,flush=True);result.check_returncode()
    req=urllib.request.Request('http://127.0.0.1:8773/streams/legacy',method='DELETE',headers={'Authorization':'Bearer '+key,'X-Caption-Local':'1'})
    urllib.request.urlopen(req,timeout=5).close()
    req=urllib.request.Request('http://127.0.0.1:8773/health',headers={'Authorization':'Bearer '+key})
    report['final_health']=json.load(urllib.request.urlopen(req,timeout=5))
    assert report['final_health']['sessions']==0
    log=(out/'service.log').read_text(encoding='utf-8')
    records=[json.loads(line) for line in log.splitlines() if line.startswith('{')]
    assert records and all(set(row)=={'event','method','route','status','duration_seconds'} for row in records)
    assert key not in log and 'Bienvenidos' not in log and 'country can do' not in log
    report.update(passed=True,metadata_log_count=len(records),metadata_logs_exclude_token_and_captions=True)
finally:
    service.stop()
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
