"""Token-gated synthetic capture; secrets remain out of evidence and relay output."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_support import browser_options

root=Path(__file__).resolve().parents[1]
key=os.environ['CAPTION_API_KEY']
output=Path(os.environ.get('CAPTION_TEST_OUTPUT_DIR',str(root/'evidence')))
output.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(**browser_options(),headless=True,args=[
        '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
        f'--use-file-for-fake-audio-capture={root/"samples/jfk.wav"}'])
    context=browser.new_context(permissions=['microphone'])
    context.route('**/*',lambda route: route.continue_() if route.request.url.startswith(
        ('http://127.0.0.1:','http://localhost:')) else route.abort())
    context.route_web_socket('**/*',lambda socket: socket.close())
    page=context.new_page()
    page.goto(os.environ.get('CAPTION_TEST_URL','http://127.0.0.1:8772'))
    page.locator('#auth').wait_for(state='visible')
    assert page.locator('#start').is_disabled()
    page.locator('#accessToken').fill('incorrect-test-token')
    page.get_by_role('button',name='Connect to service').click()
    page.wait_for_timeout(500)
    assert page.locator('#auth').is_visible() and page.locator('#start').is_disabled()
    page.locator('#accessToken').fill(key)
    page.get_by_role('button',name='Connect to service').click()
    page.locator('#auth').wait_for(state='hidden')
    page.locator('#start').click()
    page.wait_for_function('() => transcript.length>0',timeout=45000)
    page.locator('#stop').click()
    page.wait_for_function('() => !processing && !stopping',timeout=45000)
    assert page.evaluate('() => !failed && !pending && localStorage.length===0 && sessionStorage.length===0')
    assert page.locator('#accessToken').input_value()==''
    (output/'browser-auth.json').write_text(json.dumps({'unauthenticated_blocked':True,'wrong_token_blocked':True,
        'authenticated_capture_drained':True,'token_not_persisted':True}),encoding='utf-8')
    browser.close()
print('Token-gated browser capture passed')
