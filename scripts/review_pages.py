"""Capture self-hosted UI review states with local assets and mocked services.

This checks presentation, not inference, authentication or delivery correctness.
All HTTP/WebSocket requests are intercepted. No microphone permission is granted.
"""
import argparse
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from browser_support import browser_options

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--checkout', type=Path, default=ROOT/'samples/captionninja')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    health = dict(ready=True, modes=['transcribe', 'translate', 'both'], multilingual=True,
                  languages=['en', 'es', 'fr', 'de', 'ja', 'ar'], model='small', device='cpu',
                  compute_type='int8', version='visual-fixture')
    with sync_playwright() as p:
        browser = p.chromium.launch(**browser_options(), headless=True)
        try:
            for width in (1280, 390, 320):
                for name, url in [
                    ('capture-setup', 'http://localhost:8765/capture-local.html'),
                    ('capture-ready', 'http://localhost:8765/capture-local.html'),
                    ('capture-sharing', 'http://localhost:8765/capture-local.html'),
                    ('local-captions', 'http://localhost:8765/'),
                    ('editor-setup', 'http://localhost:8779/editor.html?room=source&output=output&relay=ws://127.0.0.1:8787'),
                    ('editor-ready', 'http://localhost:8779/editor.html?room=source&output=output&relay=ws://127.0.0.1:8787&mode=manual'),
                    ('overlay-setup', 'http://localhost:8779/overlay.html?room=output&relay=ws://127.0.0.1:8787'),
                    ('overlay-ready', 'http://localhost:8779/overlay.html?room=output&relay=ws://127.0.0.1:8787'),
                ]:
                    context = browser.new_context(viewport={'width': width, 'height': 640 if width == 320 else 900})
                    errors = []
                    interactions = []
                    readers = []

                    def serve(route):
                        address = urlsplit(route.request.url)
                        if address.netloc == 'localhost:8765' and address.path == '/health':
                            route.fulfill(json=health); return
                        root, relative = None, None
                        if address.netloc == 'localhost:8765':
                            root = ROOT/'static'
                            relative = 'index.html' if address.path == '/' else address.path.removeprefix('/static/').lstrip('/')
                        elif address.netloc == 'localhost:8779':
                            root = args.checkout.resolve(); relative = address.path.lstrip('/')
                        if root:
                            target = (root/relative).resolve()
                            if target.is_relative_to(root) and target.is_file() and target.suffix in {'.html', '.css', '.js', '.svg', '.ttf', '.png', '.woff', '.woff2'}:
                                route.fulfill(path=str(target), content_type=mimetypes.guess_type(target)[0] or 'application/octet-stream'); return
                        route.fulfill(status=404, body='Unavailable in visual fixture')

                    def socket(ws):
                        if not ws.url.startswith('ws://127.0.0.1:8787'):
                            return
                        def received(raw):
                            data = json.loads(raw)
                            if 'join' in data:
                                ws.send(json.dumps(dict(joined=data['join'], role=data['role'], protocol=2, epoch='visual', next=1, gap=None)))
                                if data['role'] == 'read': readers.append(ws)
                            elif data.get('delivery'):
                                ws.send(json.dumps(dict(ack=data['delivery'], epoch='visual', sequence=1)))
                        ws.on_message(received)

                    context.route('**/*', serve)
                    context.route_web_socket('**/*', socket)
                    page = context.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(url)
                    if name in ('capture-ready', 'capture-sharing'):
                        page.click('#connect')
                        page.wait_for_function('!document.querySelector("#start").disabled')
                    if name == 'capture-sharing':
                        page.locator('summary').filter(has_text='Send captions to caption.ninja').click()
                        page.locator('summary').filter(has_text='Use a private relay').click()
                    if name in ('editor-ready', 'overlay-ready'):
                        page.fill('#relaySetupReadToken', 'r'*43)
                        if name == 'editor-ready': page.fill('#relaySetupWriteToken', 'w'*43)
                        page.get_by_role('button', name='Connect private relay', exact=True).click()
                        page.wait_for_function('!document.querySelector("#relaySetup")')
                        page.wait_for_timeout(100)
                        for reader in readers:
                            reader.send(json.dumps(dict(msg=True, final='Welcome. These are synthetic preview captions. Hola. Bonjour.', id=1, relay=dict(epoch='visual', sequence=1))))
                        if name == 'editor-ready':
                            page.wait_for_function('document.querySelector("#editor").value.includes("Welcome")')
                            try: page.locator('#privateViewerLink summary').click(timeout=1500)
                            except Exception as error: interactions.append('OBS disclosure: ' + type(error).__name__)
                        else:
                            page.wait_for_function('document.querySelector("#output").textContent.includes("Welcome")')
                    if name.endswith('setup') and name != 'capture-setup':
                        page.locator('#relaySetup').wait_for()
                    page.evaluate('window.scrollTo(0, 0)')
                    if name == 'capture-ready':
                        assert page.evaluate('document.activeElement.id') == 'microphone'
                        page.keyboard.press('Tab')
                        assert page.evaluate('document.activeElement.id') == 'language'
                    if name == 'capture-setup':
                        page.keyboard.press('Tab')
                        assert page.locator('.skip-link').evaluate('(node) => node === document.activeElement')
                        page.keyboard.press('Enter')
                        assert page.evaluate('document.activeElement.id') == 'captureControls'
                        page.evaluate('window.scrollTo(0, 0)')
                    if name.endswith('setup') and name != 'capture-setup':
                        assert page.evaluate('document.activeElement.id') == 'relaySetupTitle'
                        page.keyboard.press('Tab')
                        assert page.evaluate('document.activeElement.textContent') == 'Setup guide and room tokens'
                        page.keyboard.press('Tab')
                        assert page.evaluate('document.activeElement.id') == 'relaySetupAddress'
                        page.evaluate('window.scrollTo(0, 0)')
                    page.evaluate('window.scrollTo(0, 0)')
                    page.screenshot(path=str(args.output/f'{name}-{width}.png'), full_page=True)
                    page.screenshot(path=str(args.output/f'{name}-{width}-viewport.png'))
                    metrics = page.evaluate('''() => {
                      const visible = e => !!e.getClientRects().length;
                      const outside = [...document.querySelectorAll('input,select,button,textarea,form')]
                        .filter(visible).filter(e => {const r=e.getBoundingClientRect(); return r.left < -1 || r.right > innerWidth+1;})
                        .map(e => e.id || e.tagName);
                      const action = document.querySelector('#start,#relaySetup button,#sendButton');
                      return {width: innerWidth, documentWidth: document.documentElement.scrollWidth,
                        height: document.documentElement.scrollHeight, outside,
                        actionTop: action?.getBoundingClientRect().top ?? null,
                        bodyOverflow: getComputedStyle(document.body).overflow,
                        setupHeight: document.querySelector('#relaySetup')?.getBoundingClientRect().height ?? null};
                    }''')
                    results.append(dict(page=name, viewport=width, metrics=metrics, errors=errors, interactionErrors=interactions))
                    print(json.dumps(results[-1]), flush=True)
                    context.close()
                    (args.output/'results.json').write_text(json.dumps(dict(scope=__doc__, browser=browser.version, pages=results), indent=2)+'\n', encoding='utf-8', newline='\n')
            (args.output/'results.json').write_text(json.dumps(dict(scope=__doc__, browser=browser.version, pages=results), indent=2)+'\n', encoding='utf-8', newline='\n')
        finally:
            browser.close()
    failures = [row for row in results if row['errors'] or row['interactionErrors']
                or row['metrics']['outside']
                or row['metrics']['documentWidth'] > row['viewport'] + 1]
    if failures:
        raise SystemExit(f'{len(failures)} visual checks failed; see {args.output / "results.json"}')


if __name__ == '__main__': main()
