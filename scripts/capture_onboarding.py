"""Refresh documentation images from local assets without inference or microphone use.

Requires requirements-dev.txt and Edge/Chrome (or Playwright Chromium).
The browser receives only checked-in assets through intercepted requests.
No HTTP server, model, microphone permission or public relay is used.
"""
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

from browser_support import browser_options

ROOT = Path(__file__).resolve().parents[1]


def main():
    assets = ROOT / 'docs/assets'
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**browser_options(), headless=True)
        try:
            context = browser.new_context(viewport={'width': 1000, 'height': 900},
                                          device_scale_factor=1)

            def serve(route):
                url = urlsplit(route.request.url)
                target = None
                if url.netloc == 'localhost:8765':
                    if url.path == '/capture-local.html':
                        target = ROOT / 'static/capture-local.html'
                    elif url.path.startswith('/static/'):
                        candidate = (ROOT / url.path.lstrip('/')).resolve()
                        if candidate.is_relative_to(ROOT / 'static'):
                            target = candidate
                    elif url.path in ('/caption-workflow.svg', '/hosting-options.svg'):
                        target = assets / url.path.lstrip('/')
                if target and target.is_file():
                    route.fulfill(path=str(target), content_type=mimetypes.guess_type(target)[0]
                                  or 'application/octet-stream')
                else:
                    route.fulfill(status=404, body='Documentation preview: asset unavailable')

            context.route('**/*', serve)
            # Intercept without forwarding: no caption socket can reach a relay.
            context.route_web_socket('**/*', lambda route: None)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://localhost:8765/capture-local.html')
            page.wait_for_function("document.querySelector('#status').textContent === 'Not connected'")
            assert not page.locator('#share').is_checked()
            assert page.locator('#connectionToken').input_value() == ''
            assert page.locator('#captions').inner_text() == ''
            page.screenshot(path=str(assets / 'capture-setup.png'), full_page=True)
            # Raster previews are ignored review artifacts, not documentation copies.
            previews = ROOT / 'samples/onboarding-preview'
            previews.mkdir(parents=True, exist_ok=True)
            for name, height in [('caption-workflow', 640), ('hosting-options', 470)]:
                page.set_viewport_size({'width': 1000, 'height': height})
                page.goto(f'http://localhost:8765/{name}.svg')
                page.screenshot(path=str(previews / (name + '.png')))
            if errors:
                raise RuntimeError('Browser page errors: ' + '; '.join(errors))
            print('Captured the actual disconnected page; rendered both SVGs; no page errors.')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
