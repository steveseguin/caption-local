"""Browser fault injection: transient service failures, retained audio, recovery.
HTTP inference is mocked in this test; microphone worklet and UI run in Chrome.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright
root = Path(__file__).resolve().parents[1]
evidence = Path(os.environ.get("CAPTION_TEST_OUTPUT_DIR", str(root/"evidence")))
evidence.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=[
        '--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
        f'--use-file-for-fake-audio-capture={root/"samples/jfk.wav"}'])
    context = browser.new_context(permissions=['microphone'])
    page=context.new_page(); errors=[]; requests=[]; working=False
    page.on('pageerror',lambda e:errors.append(str(e)))
    def infer(route):
        req=route.request
        requests.append({'id':req.headers['x-request-id'],'body':req.post_data_buffer})
        if not working:
            route.fulfill(status=503,json={'detail':'Injected temporary outage'})
        else:
            duration=len(req.post_data_buffer)/64000
            route.fulfill(json={'text':'Recovered caption.', 'transcript':'Recovered caption.',
                'translation':'','language':'en','output_language':'en','mode':'transcribe',
                'committed_seconds':duration, 'audio_seconds':duration,'inference_seconds':0.01})
    page.route('**/transcribe?*',infer)
    page.goto(os.environ.get('CAPTION_TEST_URL','http://127.0.0.1:8765'))
    page.get_by_role('button',name='Start captions',exact=True).click()
    page.get_by_role('button',name='Retry pending audio').wait_for(state='visible',timeout=30000)
    assert len(requests)==4
    assert len({r['id'] for r in requests})==1
    assert all(r['body']==requests[0]['body'] for r in requests)
    assert page.locator('#captions').inner_text()==''
    working=True
    page.get_by_role('button',name='Retry pending audio').click()
    page.wait_for_function('() => !document.querySelector("#start").disabled',timeout=20000)
    assert requests[4]==requests[0], 'Manual retry changed pending audio or request ID'
    assert page.locator('#captions').inner_text().startswith('Recovered caption.')
    assert page.locator('#retry').is_hidden() and not errors, errors
    # Start/stop cycles must remain operable after recovery.
    for _ in range(3):
        page.get_by_role('button',name='Start captions',exact=True).click()
        page.get_by_role('button',name='Stop',exact=True).click()
        page.wait_for_function('() => !document.querySelector("#start").disabled',timeout=10000)
    result={'automatic_attempts':4,'same_audio_and_id_on_retry':True,
            'manual_recovery':True,'restart_cycles':3,'browser_errors':errors}
    (evidence/'browser-recovery.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result); browser.close()
