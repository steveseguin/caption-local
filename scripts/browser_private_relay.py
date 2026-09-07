"""Synthetic microphone -> fake inference -> real private relay -> editor -> overlay.

Requires npm ci in the captionninja relay directory and samples/jfk.wav.
Caption sockets stay on loopback; --hosted-pages also reads HTTPS site assets.
Does not benchmark speech recognition.
"""
import argparse
import faulthandler
import functools
import http.server
import json
import os
from pathlib import Path
import secrets
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from browser_support import browser_options
from service_test_support import require_free_port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, default=ROOT/'samples/captionninja')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hosted-pages', action='store_true', help='Read actual HTTPS caption.ninja pages; caption sockets still stay on loopback')
    parser.add_argument('--hosted-site', default='https://caption.ninja/', help='HTTPS static site base for --hosted-pages')
    args = parser.parse_args()
    site = urllib.parse.urlsplit(args.hosted_site)
    if site.scheme != 'https' or not site.netloc or site.username or site.password or site.query or site.fragment:
        parser.error('--hosted-site must be an HTTPS website base without credentials, query or fragment')
    hosted_base = args.hosted_site.rstrip('/') + '/'
    hosted_origin = site.scheme + '://' + site.netloc
    faulthandler.dump_traceback_later(90, repeat=False)
    progress = {'stage': 'initializing'}
    def stage(name):
        progress['stage'] = name
        print('Private relay browser probe: ' + name, flush=True)
    for port in (8778, 8779, 8787): require_free_port(port)
    import uvicorn
    from server import create_app
    from playwright.sync_api import sync_playwright
    class Engine:
        workers = 1
        multilingual = True
        device = 'cpu'
        compute_type = 'fake'
        def transcribe(self, audio, language, task='transcribe'):
            return 'Synthetic private relay caption.', language or 'en'
        def window(self, audio, language, context, final):
            return 'Synthetic private relay caption.', language or 'en', len(audio)/16000 if final else len(audio)/16000-1
    token = secrets.token_urlsafe(32)
    inference = uvicorn.Server(uvicorn.Config(create_app(Engine(), api_key=token,
        allowed_origins=[hosted_origin] if args.hosted_pages else []), host='127.0.0.1', port=8778, log_level='error'))
    inference_thread = threading.Thread(target=inference.run, daemon=True); inference_thread.start()
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    static = http.server.ThreadingHTTPServer(('127.0.0.1', 8779),
        functools.partial(QuietHandler, directory=str(args.checkout)))
    threading.Thread(target=static.serve_forever, daemon=True).start()
    relay = None
    config = {'origins': ['http://127.0.0.1:8778', 'http://127.0.0.1:8779'],
        'rooms': {room: {role: secrets.token_urlsafe(32) for role in ('read', 'write')} for room in ('source', 'output')}}
    if args.hosted_pages: config['origins'].append(hosted_origin)
    result = {'scope': 'real relay and browser capture, fake inference, synthetic microphone; no public caption traffic', 'passed': False}
    external, sockets, errors, hosted_requests = [], [], [], []
    with tempfile.TemporaryDirectory(prefix='caption-private-relay-') as tmp:
        filename = Path(tmp)/'rooms.private.json'; filename.write_text(json.dumps(config), encoding='utf-8')
        def start_relay():
            process = subprocess.Popen(['node', str(args.checkout/'relay/server.cjs')],
                env={**os.environ, 'CAPTION_RELAY_CONFIG': str(filename), 'PORT': '8787', 'HOST': '127.0.0.1'},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            for _ in range(100):
                if process.poll() is not None: raise RuntimeError('Relay exited')
                try:
                    urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=1).close(); return process
                except OSError: time.sleep(.1)
            process.terminate(); process.wait(timeout=10); raise TimeoutError('Relay readiness')
        try:
            stage('starting local services')
            relay = start_relay()
            for _ in range(100):
                if inference.started: break
                time.sleep(.1)
            assert inference.started
            with sync_playwright() as p:
                stage('launching browser')
                browser = p.chromium.launch(**browser_options(), headless=True, args=[
                    '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
                    f'--use-file-for-fake-audio-capture={ROOT/"samples/jfk.wav"}'])
                result['browser'] = browser.version
                context = browser.new_context(permissions=['microphone'])
                context.set_default_timeout(15000)
                context.set_default_navigation_timeout(20000)
                def guard(route):
                    if route.request.url.startswith(('http://127.0.0.1:', 'http://localhost:')): route.continue_()
                    elif args.hosted_pages and route.request.method == 'GET' and route.request.url.startswith(hosted_origin + '/'):
                        hosted_requests.append(urllib.parse.urlsplit(route.request.url).path); route.continue_()
                    else: external.append(route.request.url); route.abort()
                context.route('**/*', guard)
                def socket_guard(ws):
                    sockets.append(ws.url)
                    if ws.url == 'ws://127.0.0.1:8787/': ws.connect_to_server()
                    # Other destinations stay intercepted and unconnected.
                if args.hosted_pages:
                    stage('granting browser loopback permission')
                    # Leave the private connection on the browser's native network
                    # path so mixed-content/local-network policy is actually exercised.
                    def block_socket(ws):
                        # An unconnected Playwright route never reaches a server.
                        # close() inside this callback deadlocks this Windows driver.
                        print('Blocked non-private socket: ' + urllib.parse.urlsplit(ws.url).netloc, flush=True)
                        sockets.append(ws.url)
                    context.route_web_socket(re.compile(r'^(?!ws://127\.0\.0\.1:8787/?$).*'), block_socket)
                    context.on('page', lambda item: item.on('websocket', lambda ws: sockets.append(ws.url)))
                else:
                    context.route_web_socket('**/*', socket_guard)
                page = context.new_page(); page.on('pageerror', lambda e: errors.append('capture: ' + e.stack))
                if args.hosted_pages:
                    cdp = context.new_cdp_session(page)
                    context_id = cdp.send('Target.getTargetInfo')['targetInfo']['browserContextId']
                    cdp.send('Browser.setPermission', {'permission': {'name': 'loopback-network'},
                        'setting': 'granted', 'origin': hosted_origin, 'browserContextId': context_id})
                stage('loading capture page')
                response = page.goto(hosted_base + 'capture-local.html' if args.hosted_pages else 'http://127.0.0.1:8778/capture-local.html')
                if args.hosted_pages:
                    result['hosted_capture_response'] = {'status': response.status, 'url': page.url.split('?')[0],
                        'title': page.title(), 'has_endpoint_control': page.locator('#endpoint').count() == 1,
                        'scripts': page.locator('script[src]').evaluate_all('(nodes) => nodes.map(n => new URL(n.src).pathname)')}
                    if not result['hosted_capture_response']['has_endpoint_control']:
                        raise RuntimeError('Hosted URL did not serve the separate Caption Local capture page')
                stage('connecting inference and private relay')
                if args.hosted_pages: page.fill('#endpoint', 'http://127.0.0.1:8778')
                page.fill('#connectionToken', token); page.click('#connect')
                page.wait_for_function('() => !document.querySelector("#start").disabled')
                page.locator('summary').filter(has_text='Send captions to caption.ninja').click()
                page.locator('summary').filter(has_text='Use a private relay').click()
                page.fill('#relayAddress', 'ws://127.0.0.1:8787')
                page.fill('#captionSite', hosted_base if args.hosted_pages else 'http://127.0.0.1:8779/')
                page.fill('#relayToken', config['rooms']['source']['write']); page.fill('#room', 'source')
                page.check('#share'); page.wait_for_function('() => document.querySelector("#relay").textContent.includes("connected")')
                editor_url = page.locator('#editorLink').get_attribute('href')
                assert 'output=output' in editor_url and 'relay=' in editor_url
                editor = context.new_page(); editor.on('pageerror', lambda e: errors.append('editor: ' + e.stack))
                stage('opening editor setup')
                editor.goto(editor_url + '&mode=manual')
                editor.locator('#relaySetupReadToken').fill(config['rooms']['source']['read'])
                editor.locator('#relaySetupWriteToken').fill(config['rooms']['output']['write'])
                editor.get_by_role('button', name='Connect private relay', exact=True).click()
                editor.wait_for_function('() => document.querySelector("#statusText").textContent.includes("Input and output connected")')
                assert 'Token' not in editor.url
                overlay_url = editor.locator('#overlayLink').get_attribute('href')
                assert 'relay=' in overlay_url and config['rooms']['output']['write'] not in overlay_url
                editor.locator('#privateViewerLink summary').click()
                editor.locator('#viewerLinkToken').fill(config['rooms']['output']['write'])
                editor.get_by_role('button', name='Create viewer link', exact=True).click()
                assert editor.locator('#viewerLinkResult').is_hidden(), 'Publishing token must never make an audience link'
                editor.locator('#viewerLinkToken').fill(config['rooms']['source']['write'])
                editor.get_by_role('button', name='Create viewer link', exact=True).click()
                editor.wait_for_function('() => document.querySelector("#privateViewerLink").textContent.includes("not authorized")')
                assert editor.locator('#viewerLinkResult').is_hidden(), 'A different publishing credential must also be rejected'
                editor.locator('#viewerLinkToken').fill(config['rooms']['output']['read'])
                editor.get_by_role('button', name='Create viewer link', exact=True).click()
                editor.locator('#viewerLinkResult').wait_for(state='visible')
                viewer_url = editor.locator('#viewerLinkResult').input_value()
                assert config['rooms']['output']['write'] not in viewer_url
                overlay = context.new_page(); overlay.on('pageerror', lambda e: errors.append('overlay: ' + e.stack))
                stage('opening viewer and capturing synthetic speech')
                overlay.goto(viewer_url)
                page.click('#start')
                editor.wait_for_function('() => document.querySelector("#editor").value.includes("Synthetic private relay caption")', timeout=30000)
                assert 'Synthetic private relay caption' not in overlay.locator('body').inner_text()
                editor.fill('#editor', 'Reviewed private caption. Hola. Bonjour.')
                before = time.perf_counter(); editor.click('#sendButton')
                overlay.wait_for_function('() => document.querySelector("#output").textContent.includes("Reviewed private caption")')
                result['review_to_visible_seconds'] = round(time.perf_counter()-before, 4)
                page.click('#stop'); page.wait_for_function('() => !running && !processing && !pending', timeout=15000)
                relay.terminate(); relay.wait(timeout=10)
                stage('testing relay restart and authorization denial')
                page.wait_for_function('() => !publisher.isOpen()', timeout=10000)
                # Force an unacknowledged queue and resume the producer immediately.
                # A returning reader must recover current-process history and report the restart gap.
                page.evaluate('publisher.disconnect()')
                page.evaluate("publisher.publish({msg:true, final:'Retained during relay restart', id:987654321})")
                assert page.evaluate('publisher.getSnapshot().queueLength') > 0
                relay = start_relay()
                page.evaluate('publisher.connect()')
                editor.wait_for_function('() => document.querySelector("#incoming").textContent.includes("Retained during relay restart")', timeout=30000)
                editor.wait_for_function('() => document.querySelector("#privateRelayStatus").textContent.includes("gap")')
                page.uncheck('#share'); page.fill('#relayToken', 'x'*43); page.check('#share')
                page.wait_for_function('() => document.querySelector("#relay").textContent.includes("denied")')
                page.uncheck('#share')
                page.fill('#relayToken', config['rooms']['source']['write']); page.check('#share')
                page.wait_for_function('() => publisher.isOpen()')
                page.evaluate("publisher.publish({msg:true, final:'\u65e5'.repeat(3000), id:987654322})")
                page.wait_for_function('() => publisher.getSnapshot().state === "denied"')
                assert page.evaluate('publisher.getSnapshot().queueLength') == 1
                assert 'size or format' in page.locator('#error').inner_text()
                page.uncheck('#share')
                assert not errors, errors
                assert all(url == 'ws://127.0.0.1:8787/' for url in sockets), sockets
                assert not external, external
                result.update(passed=True, browser=browser.version, socket_connections=len(sockets),
                    authorization_denial=True, room_isolation=True, editor_review=True, restart_queue_recovery=True,
                    restart_gap_warning=True, token_setup_panel=True, viewer_link_rejects_publish_token=True,
                    stop_drain=True, credentials_removed_from_links=True, browser_errors=errors, external_requests=external)
                result['oversized_multilingual_payload_stops_retries'] = True
                if args.hosted_pages:
                    result.update(scope='actual public HTTPS pages with permitted loopback HTTP inference and private WS relay; no hosted relay publishing',
                        hosted_asset_paths=sorted(set(hosted_requests)), capture_secure_context=page.evaluate('isSecureContext'),
                        viewer_secure_context=overlay.evaluate('isSecureContext'), browser_loopback_permission='granted in test context',
                        private_websocket_transport='native browser connection; only other destinations are intercepted/blocked')
                browser.close()
        except Exception as exc:
            result['failure'] = type(exc).__name__
            result['failed_stage'] = progress['stage']
            if args.hosted_pages:
                result['hosted_asset_paths'] = sorted(set(hosted_requests))
                result['socket_destinations_intercepted_or_observed'] = sorted(set(sockets))
            raise
        finally:
            stage('cleaning up owned services')
            if relay and relay.poll() is None: relay.terminate(); relay.wait(timeout=10)
            static.shutdown(); static.server_close(); inference.should_exit = True; inference_thread.join(timeout=10)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
            faulthandler.cancel_dump_traceback_later()
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
