"""Twelve concurrent real browser capture buffers, shared CPU inference, no relay."""
import argparse
import asyncio
import json
from pathlib import Path
from browser_support import browser_options
import time
from playwright.async_api import async_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url',default='http://127.0.0.1:8771')
parser.add_argument('--seconds',type=int,default=180)
parser.add_argument('--streams',type=int,default=12)
parser.add_argument('--output',default='evidence/multistream/browser-base.json')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(**browser_options(),headless=True,args=[
            '--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
            '--disable-background-timer-throttling','--disable-renderer-backgrounding',
            f'--use-file-for-fake-audio-capture={root/"samples/soak.wav"}'])
        context=await browser.new_context(permissions=['microphone'])
        errors=[]; external=[]; observations=[]; responses=[]
        async def guard(route):
            if route.request.url.startswith(('http://127.0.0.1:','http://localhost:')): await route.continue_()
            else: external.append(route.request.url); await route.abort()
        await context.route('**/*',guard)
        pages=[await context.new_page() for _ in range(args.streams)]
        async def trace(response):
            if '/transcribe?' in response.url:
                responses.append({'status':response.status,'result':await response.json()})
        for page in pages:
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('response',trace)
        await asyncio.gather(*(page.goto(args.url) for page in pages))
        await asyncio.gather(*(page.get_by_role('button',name='Start captions',exact=True).click() for page in pages))
        started=time.monotonic()
        while time.monotonic()-started < args.seconds:
            await asyncio.sleep(5)
            snapshot=await asyncio.gather(*(page.evaluate('() => ({streamId,running,buffered:buffer.length/16000,captions:transcript.length,error:document.querySelector("#error").textContent})') for page in pages))
            observations.append({'seconds':round(time.monotonic()-started,2),'streams':snapshot})
            print(json.dumps({'seconds':observations[-1]['seconds'],'max_buffer':max(s['buffered'] for s in snapshot),'min_captions':min(s['captions'] for s in snapshot),'errors':[s['error'] for s in snapshot if s['error']]}),flush=True)
            if any(not s['running'] or s['error'] for s in snapshot): break
        enabled=[]
        for page in pages:
            if await page.get_by_role('button',name='Stop',exact=True).is_enabled(): enabled.append(page)
        await asyncio.gather(*(page.get_by_role('button',name='Stop',exact=True).click() for page in enabled))
        await asyncio.gather(*(page.wait_for_function('() => !processing && !stopping',timeout=120000) for page in pages))
        final=await asyncio.gather(*(page.evaluate('() => ({streamId, transcript, failed, buffered:buffer.length/16000})') for page in pages))
        result={'seconds':round(time.monotonic()-started,2),'streams':args.streams,'observations':observations,'responses':responses,'final':final,'errors':errors,'external':external}
        Path(args.output).write_text(json.dumps(result,indent=2)+'\n', encoding='utf-8')
        await browser.close()
        assert not errors and not external,(errors,external)
        assert len({s['streamId'] for s in final})==args.streams
        assert all(s['running'] and not s['error'] for o in observations for s in o['streams']), 'Capture stopped or errored under load'
        assert all(not s['failed'] and s['buffered']<=0.5 and len(s['transcript'])>=args.seconds/15 for s in final), 'Incomplete drain'
        print('MULTISTREAM BROWSER PASSED',flush=True)
asyncio.run(main())
