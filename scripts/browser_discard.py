"""Check that discarding failed capture releases a real server admission slot.

Uses a synthetic microphone, the actual HTTP scheduler and a failing fake engine.
No real model, physical recording or external caption relay is used.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import wave

import numpy as np
import uvicorn
from playwright.sync_api import sync_playwright

from browser_support import browser_options, authenticate
from service_test_support import require_free_port

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require_free_port(8791)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temporary:
        fixture = Path(temporary.name)
    with wave.open(str(fixture), 'wb') as audio:
        audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        tone = .05 * np.sin(2 * np.pi * 220 * np.arange(96000) / 16000)
        audio.writeframes((tone * 32767).astype('<i2').tobytes())

    class Engine:
        workers = 1
        multilingual = True
        device = 'cpu'
        compute_type = 'fake'
        fail_next = True

        def transcribe(self, audio, language, task='transcribe'):
            return 'A different producer can now caption.', language or 'en'

        def window(self, audio, language, context, final):
            if self.fail_next:
                self.fail_next = False
                raise RuntimeError('Injected engine failure for discard regression')
            return 'Recovered.', language or 'en', len(audio) / 16000

    engine = Engine()
    service = uvicorn.Server(uvicorn.Config(create_app(engine, max_streams=1),
        host='127.0.0.1', port=8791, log_level='error'))
    thread = threading.Thread(target=service.run, daemon=True)
    thread.start()
    report = {'scope': __doc__, 'passed': False, 'pages': []}

    def request(path, data=None, method=None):
        req = urllib.request.Request('http://127.0.0.1:8791' + path, data=data,
            method=method, headers={'Content-Type': 'application/octet-stream',
                'X-Caption-Local': '1', 'X-Stream-ID': 'another-producer'})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    try:
        for _ in range(100):
            if service.started:
                break
            threading.Event().wait(.1)
        assert service.started, 'Test service did not start'
        with sync_playwright() as p:
            browser = p.chromium.launch(**browser_options(), headless=True, args=[
                '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
                f'--use-file-for-fake-audio-capture={fixture}'])
            report['browser'] = browser.version
            for path in ('/', '/capture-local.html'):
                engine.fail_next = True
                context = browser.new_context(permissions=['microphone'],
                    viewport={'width': 1280 if path == '/' else 390, 'height': 900})
                context.route('**/*', lambda route: route.continue_()
                    if route.request.url.startswith('http://127.0.0.1:8791/') else route.abort())
                context.route_web_socket('**/*', lambda ws: None)
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto('http://127.0.0.1:8791' + path)
                authenticate(page)
                page.locator('#start').click()
                page.wait_for_function('() => failed && !processing && !stopping', timeout=30000)
                row = {'path': path, 'retained_before_discard': page.evaluate(
                    '() => !!pending && buffer.length > 0'), 'browser_errors': errors}
                report['pages'].append(row)
                assert row['retained_before_discard']
                assert page.locator('#status').inner_text() == 'Stopped · pending audio retained'
                audio = np.full(16000, .02, dtype='<f4').tobytes()
                row['other_producer_before_discard'] = request('/transcribe?language=en', audio)[0]
                assert row['other_producer_before_discard'] == 429
                slug = 'local' if path != '/' else 'original'
                page.screenshot(path=str(args.output.with_name(f'discard-{slug}-retained.png')), full_page=True)
                page.locator('#discard').click()
                page.wait_for_function('() => !failed && !pending && !processing && buffer.length === 0')
                row['sessions_after_discard'] = request('/health')[1]['sessions']
                row['other_producer_after_discard'] = request('/transcribe?language=en', audio)[0]
                assert row['sessions_after_discard'] == 0, 'Discard left the service admission slot occupied'
                assert row['other_producer_after_discard'] == 200
                assert not errors
                page.screenshot(path=str(args.output.with_name(f'discard-{slug}-cleared.png')), full_page=True)
                request('/streams/another-producer', method='DELETE')
                context.close()
            browser.close()
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        service.should_exit = True
        thread.join(timeout=10)
        fixture.unlink(missing_ok=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('Discard releases admission capacity on both capture pages')


if __name__ == '__main__':
    main()
