"""Cross-origin Edge transport checks using local fake inference and mock relay only."""
import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TOKEN = 'synthetic-local-connection-test-token'


def serve(allowed_origins=None):
    import uvicorn
    from server import create_app
    class Engine:
        workers = 1
        multilingual = True
        device = 'cpu'
        compute_type = 'int8'
        def transcribe(self, audio, language, task='transcribe'):
            return 'Synthetic connection test.', language or 'en'
        def window(self, audio, language, context, final):
            return 'Synthetic connection test.', language or 'en', len(audio)/16000 if final else len(audio)/16000-1
    uvicorn.run(create_app(Engine(), api_key=TOKEN, allowed_origins=allowed_origins or ['http://127.0.0.1:8779']),
                host='127.0.0.1', port=8778, log_level='error')


def main():
    from playwright.sync_api import sync_playwright
    from browser_support import browser_options
    from service_test_support import require_free_port
    require_free_port(8778); require_free_port(8779)
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    host = http.server.ThreadingHTTPServer(('127.0.0.1', 8779),
        functools.partial(QuietHandler, directory=str(ROOT/'samples/captionninja')))
    threading.Thread(target=host.serve_forever, daemon=True).start()
    child = subprocess.Popen([sys.executable, __file__, '--serve'],
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    result = {}
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen('http://127.0.0.1:8778/capture-local.html', timeout=1).close()
                break
            except OSError:
                time.sleep(.1)
        with sync_playwright() as p:
            browser = p.chromium.launch(**browser_options(), headless=True, args=[
                '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
                f'--use-file-for-fake-audio-capture={ROOT / "samples/jfk.wav"}'])
            context = browser.new_context(permissions=['microphone'], accept_downloads=True)
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(
                ('http://127.0.0.1:', 'http://localhost:')) else route.abort())
            relay_messages = []
            def mock_relay(socket):
                socket.on_message(lambda raw: relay_messages.append(json.loads(raw)))
            context.route_web_socket('**/*', mock_relay)
            page = context.new_page(); errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:8779/capture-local.html')
            page.fill('#endpoint', 'http://127.0.0.1:8778')
            page.fill('#connectionToken', 'wrong'); page.click('#connect')
            page.wait_for_function('() => !connection.checking')
            assert page.locator('#start').is_disabled()
            result['wrong_token_rejected'] = True
            page.fill('#connectionToken', TOKEN); page.click('#connect')
            page.wait_for_function('() => !document.querySelector("#start").disabled')
            assert page.input_value('#connectionToken') == ''
            page.click('#start')
            page.wait_for_function('() => running')
            assert page.locator('#endpoint').is_disabled()
            try:
                page.wait_for_function('() => transcript.length > 0', timeout=30000)
            except Exception:
                print(page.evaluate('({running, failed, buffered:buffer.length, error:$("error").textContent, metrics:connection.metrics})'))
                raise
            page.click('#stop')
            page.wait_for_function('() => !processing && !running && !stopping && !pending', timeout=20000)
            assert not errors, errors
            assert page.evaluate('buffer.length / 16000') <= .5
            page.get_by_text('Connection and capture diagnostics', exact=True).click()
            with page.expect_download() as download:
                page.click('#downloadDiagnostics')
            diagnostic = Path(download.value.path()).read_text(encoding='utf-8')
            page.screenshot(path=str(ROOT/'samples/capture-local-preview.png'), full_page=True)
            assert TOKEN not in diagnostic and 'Synthetic connection' not in diagnostic
            assert page.evaluate('localStorage.length') == 0
            assert not relay_messages, 'Sharing must remain off by default'
            with page.expect_download() as settings_download:
                page.click('#saveSettings')
            settings_path = settings_download.value.path()
            settings = Path(settings_path).read_text(encoding='utf-8')
            assert TOKEN not in settings and 'room' not in settings
            page.select_option('#captionInterval', '9')
            page.set_input_files('#loadSettings', settings_path)
            page.wait_for_function('() => $("captionInterval").value === "6"')
            result['settings_round_trip_without_credentials'] = True
            page.get_by_text('Send captions to caption.ninja', exact=True).first.click()
            page.select_option('#relayTarget', 'overlay'); page.fill('#room', 'local-mock-room')
            page.check('#share')
            assert page.get_attribute('#editorLink', 'href') == 'http://127.0.0.1:8779/overlay.html?room=local-mock-room'
            previous_captions = page.evaluate('transcript.length')
            page.click('#start')
            page.wait_for_function('count => transcript.length > count', arg=previous_captions, timeout=30000)
            page.click('#stop')
            page.wait_for_function('() => !processing && !running && !stopping && !pending', timeout=20000)
            assert any(message.get('final') for message in relay_messages)
            assert TOKEN not in json.dumps(relay_messages)
            page.uncheck('#share')
            result['direct_overlay_mock_publish'] = True
            page.evaluate('''() => { navigator.mediaDevices.getUserMedia = async () => {
                throw new DOMException('Injected microphone permission denial', 'NotAllowedError');
            }; }''')
            page.click('#start')
            page.wait_for_function('() => !starting && !running && !stopping && !processing')
            assert 'permission denial' in page.inner_text('#error')
            assert not page.locator('#connect').is_disabled()
            result['injected_microphone_denial_recovers'] = True
            result.update(cross_origin_capture_and_drain=True, token_not_persisted=True,
                          diagnostic_excludes_text_and_token=True, browser_errors=errors)
            # Same assets under an unapproved origin must fail the real browser CORS check.
            denied = context.new_page(); denied.goto('http://localhost:8779/capture-local.html')
            denied.fill('#endpoint', 'http://127.0.0.1:8778')
            denied.fill('#connectionToken', TOKEN); denied.click('#connect')
            denied.wait_for_function('() => !connection.checking')
            assert denied.locator('#start').is_disabled()
            result['unapproved_origin_rejected'] = True
            browser.close()
        target = Path(os.environ.get('CAPTION_TEST_OUTPUT_DIR', str(ROOT/'evidence/capture-local')))/'connection.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result))
    finally:
        child.terminate(); child.wait(timeout=15)
        host.shutdown(); host.server_close()


if __name__ == '__main__':
    if '--serve-https' in sys.argv:
        serve(['https://caption.ninja'])
    else:
        serve() if '--serve' in sys.argv else main()
