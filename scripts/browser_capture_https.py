"""Controlled HTTPS-origin preview; assets intercepted locally, no public publishing."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from browser_support import browser_options
from browser_capture_connection import TOKEN, ROOT
from service_test_support import require_free_port

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True,help='Keep each preview separate from earlier failure evidence')
args=parser.parse_args()
require_free_port(8778)
child=subprocess.Popen([sys.executable,'scripts/browser_capture_connection.py','--serve-https'],
    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
report={'scope':'CDP-intercepted HTTPS-origin page assets with real loopback HTTP requests and fake inference; not a deployed HTTPS site', 'scenarios':[]}
try:
    for _ in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:8778/capture-local.html',timeout=1).close(); break
        except OSError: time.sleep(.1)
    with sync_playwright() as p:
        browser=p.chromium.launch(**browser_options(),headless=True,args=[
            '--use-fake-device-for-media-stream',f'--use-file-for-fake-audio-capture={ROOT/"samples/jfk.wav"}'])
        report['browser_version']=browser.version
        for permission in ('denied','granted'):
            context=browser.new_context(permissions=['microphone'])
            page=context.new_page(); cdp=context.new_cdp_session(page)
            context_id=cdp.send('Target.getTargetInfo')['targetInfo']['browserContextId']
            cdp.send('Browser.setPermission',{'permission':{'name':'loopback-network'},
                'setting':permission,'origin':'https://caption.ninja','browserContextId':context_id})
            failures=[]
            console=[]
            page.on('console',lambda message: console.append(message.text) if message.type=='error' else None)
            page.on('requestfailed',lambda request: failures.append({'url':request.url,'error':request.failure}))
            intercepted=[]
            def route(event):
                request_id=event['requestId']
                url=event['request']['url']
                intercepted.append(urlsplit(url).path)
                if url.startswith('http://127.0.0.1:8778/'):
                    cdp.send('Fetch.continueRequest',{'requestId':request_id}); return
                if url.startswith('https://caption.ninja/'):
                    relative=urlsplit(url).path.lstrip('/')
                    source=(ROOT/'samples/captionninja'/relative).resolve()
                    base=(ROOT/'samples/captionninja').resolve()
                    if source.is_relative_to(base) and source.is_file():
                        cdp.send('Fetch.fulfillRequest',{'requestId':request_id,'responseCode':200,
                            'responseHeaders':[{'name':'Content-Type','value':'text/html' if source.suffix=='.html' else 'application/javascript'}],
                            'body':base64.b64encode(source.read_bytes()).decode('ascii')}); return
                cdp.send('Fetch.failRequest',{'requestId':request_id,'errorReason':'BlockedByClient'})
            # Probe direct Fetch events without relying on Playwright's usual
            # page/network event pairing for worklet module loads.
            cdp.on('Fetch.requestPaused',route)
            cdp.send('Fetch.enable',{'patterns':[{'urlPattern':'*'}]})
            context.route_web_socket('**/*',lambda socket:socket.close())
            page.goto('https://caption.ninja/capture-local.html')
            page.fill('#endpoint','http://127.0.0.1:8778');page.fill('#connectionToken',TOKEN);page.click('#connect')
            page.wait_for_function('() => !connection.checking')
            ready=not page.locator('#start').is_disabled()
            scenario={'permission':permission,'ready':ready,'request_failures':failures,'console':console,
                      'intercepted_paths':intercepted,'secure_context':page.evaluate('isSecureContext')}
            report['scenarios'].append(scenario)
            if ready:
                page.click('#start')
                try:
                    page.wait_for_function('() => transcript.length > 0',timeout=30000)
                except Exception:
                    scenario['capture_state']=page.evaluate('({running,starting,failed,error:$("error").textContent})')
                    raise
                page.click('#stop');page.wait_for_function('() => !processing && !running && !stopping && !pending',timeout=20000)
                scenario['capture_drained']=page.evaluate('!failed && buffer.length <= 8000')
            context.close()
        browser.close()
    report['passed']=not report['scenarios'][0]['ready'] and report['scenarios'][1].get('capture_drained',False)
except Exception as exc:
    report['error']=repr(exc);report['passed']=False
finally:
    child.terminate();child.wait(timeout=15)
    output=args.output;output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
if not report['passed']: raise SystemExit('HTTPS preview validation incomplete; evidence retained')
