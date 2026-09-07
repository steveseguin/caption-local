import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from service_test_support import TestService
out=ROOT/'samples/full-review'
service=TestService(8776,out/'wsl-service.log',['--device','cpu','--compute-type','int8','--threads','2'])
try:
    info=service.start()
    (out/'wsl-health.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    subprocess.run([sys.executable,str(ROOT/'scripts/smoke_api.py'),'--url','http://127.0.0.1:8776','--spanish',str(ROOT/'samples/spanish.wav'),'--output',str(out/'wsl-smoke.json')],cwd=ROOT,check=True)
finally: service.stop()
