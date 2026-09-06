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
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.parent.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[1]
service=TestService(args.port,args.output.with_suffix('.server.log'))
report={'requests':[],'lost_response':None,'passed':False}
try:
    service.start()
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
                service.start()
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
