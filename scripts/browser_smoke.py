"""Real Chrome microphone -> real inference -> local mock relay -> actual editor.
Run server.py first and benchmark.py once to obtain samples/jfk.wav.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from browser_support import browser_options
import threading
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
evidence = Path(os.environ.get("CAPTION_TEST_OUTPUT_DIR", str(root/"evidence")))
evidence.mkdir(parents=True, exist_ok=True)
caption_root = root.parent / 'captionninja'
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
server = ThreadingHTTPServer(('127.0.0.1', 8766), partial(QuietHandler, directory=str(caption_root)))
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(**browser_options(), headless=True, args=[
            '--no-sandbox', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
            f'--use-file-for-fake-audio-capture={root / "samples/jfk.wav"}',
        ])
        context = browser.new_context(permissions=['microphone'])
        sockets, messages, errors, external = [], [], [], []
        def relay(ws):
            sockets.append(ws)
            def received(raw):
                data = json.loads(raw)
                messages.append(data)
                if data.get('msg') and 'final' in data:
                    for other in sockets:
                        if other != ws:
                            other.send(raw)
            ws.on_message(received)
        context.route_web_socket('wss://api.caption.ninja/**', relay)
        # No live service receives test captions or audio.
        def guard(route):
            if route.request.url.startswith(('http://127.0.0.1:', 'http://localhost:')):
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        context.route('**/*', guard)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(os.environ.get('CAPTION_TEST_URL', 'http://127.0.0.1:8765'))
        page.get_by_role('button', name='Start captions', exact=True).click()
        page.wait_for_function("() => document.querySelector('#captions').children.length > 0", timeout=45000)
        page.get_by_role('button', name='Stop', exact=True).click()
        page.wait_for_function("() => !document.querySelector('#start').disabled", timeout=30000)
        assert not messages, 'Sharing-off opened relay'
        local_text = page.locator('#captions').inner_text()
        editor = context.new_page()
        editor.goto('http://127.0.0.1:8766/editor.html?room=localtestsource&output=localtestoutput')
        page.locator('summary').click()
        page.locator('#room').fill('localtestsource')
        page.locator('#share').check()
        page.get_by_role('button', name='Start captions', exact=True).click()
        editor.wait_for_function("() => document.querySelector('#editor').value.length > 0", timeout=45000)
        reviewed = editor.locator('#editor').input_value()
        page.get_by_role('button', name='Stop', exact=True).click()
        page.wait_for_function("() => !document.querySelector('#start').disabled", timeout=30000)
        assert not errors, errors
        result = dict(local_text=local_text, editor_received=reviewed,
                      captions_sent=sum('final' in m for m in messages), browser_errors=errors,
                      blocked_external_http=external, relay='mocked locally; no public publishing')
        (evidence / 'browser-smoke.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        page.screenshot(path=str(evidence/'local-captions.png'), full_page=True)
        print(json.dumps(result, indent=2))
        browser.close()
finally:
    server.shutdown()
