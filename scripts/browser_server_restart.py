"""Lose a real inference response, restart our server, then verify retained retry."""
import argparse
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_support import browser_options, authenticate
from service_test_support import TestService

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port',type=int,default=8774)
parser.add_argument('--page',choices=['/', '/capture-local.html'],default='/')
parser.add_argument('--model',default='small')
parser.add_argument('--device',choices=['cpu','cuda'],default='cpu')
parser.add_argument('--compute-type',default='int8')
parser.add_argument('--workers',type=int,default=1)
parser.add_argument('--threads',type=int,default=4)
parser.add_argument('--beam-size',type=int,default=5)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.parent.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[1]
service=TestService(args.port,args.output.with_suffix('.server.log'),[
    '--model',args.model,'--device',args.device,'--compute-type',args.compute_type,
    '--workers',str(args.workers),'--threads',str(args.threads),'--beam-size',str(args.beam_size)])
report={'requests':[],'lost_response':None,'passed':False,
        'configuration':{key:value for key,value in vars(args).items() if key!='output'}}
try:
    report['initial_health']=service.start()
    assert report['initial_health']['device']==args.device
    with sync_playwright() as p:
        browser=p.chromium.launch(**browser_options(),headless=True,args=[
            '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
            f'--use-file-for-fake-audio-capture={root/"samples/jfk.wav"}'])
        context=browser.new_context(permissions=['microphone'])
        context.route('**/*',lambda route: route.continue_() if route.request.url.startswith(
            ('http://127.0.0.1:','http://localhost:')) else route.abort())
        context.route_web_socket('**/*',lambda socket: socket.close())
        page=context.new_page()
        def infer(route):
            request=route.request
            report['requests'].append({'id':request.headers['x-request-id'],
                'sha256':hashlib.sha256(request.post_data_buffer).hexdigest()})
            if report['lost_response'] is None:
                actual=route.fetch()
                assert actual.status==200
                report['lost_response']=actual.json()
                route.abort('failed')
                service.stop()
                report['restarted_health']=service.start()
                assert report['restarted_health']['device']==args.device
            else:
                route.continue_()
        page.route('**/transcribe?*',infer)
        page.goto(f'http://127.0.0.1:{args.port}{args.page}')
        authenticate(page)
        page.locator('#start').click()
        page.wait_for_function('() => transcript.length>0',timeout=60000)
        assert report['requests'][0]==report['requests'][1]
        assert page.evaluate('() => transcript[0]')==report['lost_response']['text']
        page.locator('#stop').click()
        page.wait_for_function('() => !processing && !stopping',timeout=60000)
        assert page.evaluate('() => !failed && !pending && buffer.length<=8000')
        report.update(passed=True,restarted=True,same_audio_and_request_id=True,
                      duplicate_lost_response_not_displayed=True)
        browser.close()
finally:
    service.stop()
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('Real response loss, server restart, retained retry and drain passed')
