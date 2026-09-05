"""Synthetic microphone selection, loss/drain and restart with real browser inference.

Does not capture a physical microphone or contact a public relay.
"""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_support import browser_options

root = Path(__file__).resolve().parents[1]
output = Path(os.environ.get('CAPTION_TEST_OUTPUT_DIR', str(root/'evidence')))
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(**browser_options(), headless=True, args=[
        '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
        f'--use-file-for-fake-audio-capture={root/"samples/soak.wav"}'])
    context = browser.new_context(permissions=['microphone'])
    context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(
        ('http://127.0.0.1:', 'http://localhost:')) else route.abort())
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.environ.get('CAPTION_TEST_URL', 'http://127.0.0.1:8772'))
    page.wait_for_function('() => document.querySelector("#microphone").options.length > 1')
    devices = page.locator('#microphone option').evaluate_all('(items) => items.map(x => ({value:x.value, label:x.textContent}))')
    selected = devices[-1]['value']
    page.locator('#microphone').select_option(selected)
    page.evaluate('''() => {
        window.captionTiming = [];
        const original = renderResult;
        renderResult = result => {
            original(result);
            if (result.text) captionTiming.push({visibleMs:performance.now(), text:result.text});
        };
        window.captureStartedMs = performance.now();
    }''')
    page.get_by_role('button', name='Start captions', exact=True).click()
    page.wait_for_function('() => running && transcript.length > 0', timeout=45000)
    assert page.locator('#microphone').is_disabled()
    assert page.evaluate('() => stream.getAudioTracks()[0].getSettings().deviceId') == selected
    # Dispatch the browser track-ended notification; this tests the app handler,
    # not physical USB removal or the operating system's device driver.
    page.evaluate('() => stream.getAudioTracks()[0].dispatchEvent(new Event("ended"))')
    page.wait_for_function('() => !running && !processing && !stopping && !starting', timeout=60000)
    assert page.evaluate('() => !failed && !pending && buffer.length <= 8000')
    assert 'Microphone disconnected' in page.locator('#error').inner_text()
    page.locator('#microphone').select_option('')
    page.get_by_role('button', name='Start captions', exact=True).click()
    page.wait_for_function('() => running')
    page.get_by_role('button', name='Stop', exact=True).click()
    page.wait_for_function('() => !processing && !stopping && !starting', timeout=60000)
    assert not errors and page.evaluate('() => !failed && !pending && buffer.length <= 8000')
    result = {'browser_version': browser.version, 'devices': devices,
              'explicit_selection': True, 'injected_track_ended_drained': True,
              'changed_to_default_and_restarted': True, 'errors': errors,
              'first_caption_from_start_seconds': page.evaluate('() => (captionTiming[0].visibleMs-captureStartedMs)/1000'),
              'delay_definition': 'Start click to first visible caption with looping synthetic microphone; includes collection and inference, not word-aligned speech latency',
              'physical_microphone_tested': False}
    (output/'browser-devices.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))
    browser.close()
