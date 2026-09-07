import hashlib,json,os,subprocess,sys,tarfile,time,urllib.request
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from service_test_support import require_free_port
out=ROOT/'samples/full-review/archive-install'
out.mkdir(exist_ok=False)
archive=ROOT/'dist/caption-local-1.1.0.tar.gz'
with tarfile.open(archive) as tar:
    for item in tar.getmembers():
        assert (out/item.name).resolve().is_relative_to(out.resolve())
    tar.extractall(out,filter='data')
checkout=out/'caption-local-1.1.0'
report={'scope':'fresh extracted source archive, fresh private Windows venv, reused model cache, offline real CPU HTTP inference','passed':False,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'commands':[]}
child=None;log=None
def run(name,command):
    started=time.monotonic()
    with (out/(name+'.log')).open('w',encoding='utf-8') as output:
        result=subprocess.run(command,cwd=checkout,stdout=output,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUTF8':'1'})
    report['commands'].append({'name':name,'exit_code':result.returncode,'seconds':time.monotonic()-started})
    print(name,'exit',result.returncode,flush=True);result.check_returncode()
try:
    run('setup',[sys.executable,'deploy.py','setup'])
    python=checkout/'.venv/Scripts/python.exe'
    run('doctor',[sys.executable,'deploy.py','doctor'])
    require_free_port(8775)
    log=(out/'server.log').open('w',encoding='utf-8')
    child=subprocess.Popen([sys.executable,'deploy.py','run','--offline','--device','cpu','--port','8775'],cwd=checkout,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(180):
        assert child.poll() is None,'Archive server exited'
        try:
            health=json.load(urllib.request.urlopen('http://127.0.0.1:8775/health',timeout=1))
            if health['ready']: break
        except OSError: pass
        time.sleep(.5)
    else: raise TimeoutError('Archive readiness')
    report['health']=health;assert health['device']=='cpu'
    for route,file in [('/','static/index.html'),('/capture-local.html','static/capture-local.html'),('/static/capture.css','static/capture.css'),('/static/pcm-worklet.js','static/pcm-worklet.js')]:
        response=urllib.request.urlopen('http://127.0.0.1:8775'+route,timeout=5)
        assert response.read()==(checkout/file).read_bytes()
        if route.endswith('.css'): assert response.headers.get_content_type()=='text/css'
    run('smoke',[str(python),str(ROOT/'scripts/smoke_api.py'),'--url','http://127.0.0.1:8775','--spanish',str(ROOT/'samples/spanish.wav'),'--output',str(out/'smoke.json')])
    run('packages',[str(python),'-m','pip','list','--format=json'])
    report['passed']=True
finally:
    if child and child.poll() is None:
        owned=psutil.Process(child.pid).children(recursive=True)
        for proc in reversed(owned):
            try: proc.terminate()
            except psutil.NoSuchProcess: pass
        psutil.wait_procs(owned,timeout=10)
        child.terminate();child.wait(timeout=15)
    if log:log.close()
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
