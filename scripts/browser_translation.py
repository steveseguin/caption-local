"""Real fake-microphone Spanish -> inference -> bilingual UI + English relay.
Run the multilingual service first; generate samples/spanish.wav per DEPLOYMENT.md.
Only the relay is mocked; no public caption publishing.
"""
import json
import os
from pathlib import Path
from browser_support import browser_options, authenticate
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
evidence = Path(os.environ.get("CAPTION_TEST_OUTPUT_DIR", str(root/"evidence")))
evidence.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(**browser_options(), headless=True, args=[
        '--no-sandbox', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
        f'--use-file-for-fake-audio-capture={root / "samples/spanish.wav"}',
    ])
    context = browser.new_context(permissions=['microphone'], accept_downloads=True)
    messages, errors, external = [], [], []
    def relay(ws):
        ws.on_message(lambda raw: messages.append(json.loads(raw)))
    context.route_web_socket('wss://api.caption.ninja/**', relay)
    def guard(route):
        if route.request.url.startswith(('http://127.0.0.1:', 'http://localhost:')):
            route.continue_()
        else:
            external.append(route.request.url)
            route.abort()
    context.route('**/*', guard)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(os.environ.get('CAPTION_TEST_URL', 'http://127.0.0.1:8765'))
    authenticate(page)
    page.wait_for_function("() => !document.querySelector('#start').disabled")
    page.locator('#language').select_option('es')
    page.locator('#mode').select_option('translate')
    assert page.locator('#relayOutput').input_value() == 'translation'
    page.locator('#mode').select_option('transcribe')
    assert page.locator('#relayOutput').input_value() == 'transcript'
    page.locator('#mode').select_option('both')
    page.get_by_text('Send captions to caption.ninja', exact=True).first.click()
    page.locator('#relayOutput').select_option('translation')
    page.locator('#room').fill('localtranslationtest')
    page.locator('#share').check()
    page.get_by_role('button', name='Start captions', exact=True).click()
    page.wait_for_function("() => document.querySelector('#captions').children.length > 0", timeout=45000)
    assert page.locator('#mode').is_disabled()
    page.get_by_role('button', name='Stop', exact=True).click()
    page.wait_for_function("() => !document.querySelector('#start').disabled", timeout=30000)
    display = page.locator('#captions').inner_text()
    assert 'English:' in display
    finals = [message for message in messages if 'final' in message]
    assert finals and all(message['ln'] == 'en' for message in finals), finals
    assert all(message['final'] in display for message in finals)
    with page.expect_download() as info:
        page.get_by_role('button', name='Download transcript').click()
    download = info.value
    saved = Path(download.path()).read_text(encoding='utf-8')
    assert 'English:' in saved and finals[0]['final'] in saved
    assert not errors and not external, (errors, external)
    result = {'display':display, 'relay_messages':finals, 'download':saved,
              'browser_errors':errors, 'external_http':external,
              'method':'real Spanish fake microphone and inference; local mock relay'}
    page.locator('#share').uncheck()
    page.locator('#mode').select_option('translate')
    previous_count = page.evaluate('transcript.length')
    page.locator('#start').click()
    page.wait_for_function('count => transcript.length > count', arg=previous_count, timeout=45000)
    page.locator('#stop').click()
    page.wait_for_function('() => !processing && !running && !stopping && !pending', timeout=30000)
    result['translation_only'] = page.evaluate('transcript.slice('+str(previous_count)+')')
    assert result['translation_only'] and all('English:' not in text for text in result['translation_only'])
    (evidence/'browser-translation.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    browser.close()
