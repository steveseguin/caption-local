"""Independent multilingual synthetic microphone tabs, actual service inference.

Measures first voiced capture-frame to first visible caption, plus per-tab backlog
and Stop/drain. Subsequent word-aligned latency and physical microphones are not
measured. All external HTTP and WebSockets are blocked.
"""
import argparse
import asyncio
import json
from pathlib import Path
import time
from playwright.async_api import async_playwright
from browser_support import browser_options, authenticate_async


async def main(args):
    root=Path(__file__).resolve().parents[1]
    fixtures=json.loads(args.manifest.read_text(encoding='utf-8'))
    report={'streams':args.streams,'capture_seconds':args.seconds,'interval':args.interval,
            'mixed':args.mixed,'varied_conditions':args.varied,'observations':[],'responses':[],'errors':[]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    async with async_playwright() as p:
        browsers=[]; contexts=[]; pages=[]
        try:
            for fixture in fixtures[:min(args.streams,len(fixtures))]:
                browser=await p.chromium.launch(**browser_options(),headless=True,args=[
                    '--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
                    '--disable-background-timer-throttling','--disable-renderer-backgrounding',
                    f'--use-file-for-fake-audio-capture={root/fixture["varied_loop_path" if args.varied else "loop_path"]}'])
                browsers.append(browser)
                context=await browser.new_context(permissions=['microphone'])
                await context.route('**/*',lambda route: route.continue_() if route.request.url.startswith(
                    ('http://127.0.0.1:','http://localhost:')) else route.abort())
                await context.route_web_socket('**/*',lambda socket: socket.close())
                contexts.append(context)
            for index in range(args.streams):
                page=await contexts[index%len(contexts)].new_page(); pages.append(page)
                page.on('pageerror',lambda error: report['errors'].append(str(error)))
                async def trace(response,index=index):
                    if '/transcribe?' in response.url:
                        report['responses'].append({'stream':index,'status':response.status,'result':await response.json()})
                page.on('response',trace)
                await page.goto(args.url)
                await authenticate_async(page)
                await page.wait_for_function('() => !document.querySelector("#start").disabled')
                await page.locator('#language').select_option(fixtures[index%len(fixtures)]['language'])
                await page.locator('#captionInterval').select_option(str(args.interval))
                if args.mixed and index%3==0:
                    await page.locator('#mode').select_option('both')
                await page.evaluate('''() => {
                    window.firstSpeechMs=null; window.firstCaptionMs=null;
                    const originalFrame=frame, originalRender=renderResult;
                    frame=audio => {
                        if (firstSpeechMs===null && audio.some(x=>Math.abs(x)>.01)) firstSpeechMs=performance.now();
                        return originalFrame(audio);
                    };
                    renderResult=result => {
                        originalRender(result);
                        if (firstCaptionMs===null && result.text) firstCaptionMs=performance.now();
                    };
                }''')
            await asyncio.gather(*(page.locator('#start').click() for page in pages))
            started=time.perf_counter()
            while time.perf_counter()-started<args.seconds:
                await asyncio.sleep(5)
                states=await asyncio.gather(*(page.evaluate('() => ({running,failed,buffered:buffer.length/16000,captions:transcript.length,error:document.querySelector("#error").textContent})') for page in pages))
                report['observations'].append({'seconds':time.perf_counter()-started,'states':states})
                print(json.dumps({'seconds':round(time.perf_counter()-started),'max_buffer':max(s['buffered'] for s in states),
                                  'min_captions':min(s['captions'] for s in states)}),flush=True)
                if any(not state['running'] or state['failed'] for state in states):
                    break
                if args.stop_file and args.stop_file.exists():
                    report['errors'].append('Capture stopped by the external benchmark monitor; requested duration was not completed')
                    break
            for page in pages:
                if await page.locator('#stop').is_enabled():
                    await page.locator('#stop').click()
            await asyncio.gather(*(page.wait_for_function('() => !processing && !stopping',timeout=120000) for page in pages))
            report['final']=await asyncio.gather(*(page.evaluate('() => ({streamId,failed,pending:!!pending,buffered:buffer.length/16000,transcript,first_caption_seconds:(firstCaptionMs-firstSpeechMs)/1000})') for page in pages))
            report['wall_seconds']=time.perf_counter()-started
            report['passed']=not report['errors'] and all(s['running'] and not s['failed'] and not s['error'] for o in report['observations'] for s in o['states']) and all(
                not s['failed'] and not s['pending'] and s['buffered']<=.5 and len(s['transcript'])>=args.seconds/15 for s in report['final'])
        except Exception as exc:
            report.update(passed=False,error=repr(exc))
            raise
        finally:
            args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            for browser in browsers:
                await browser.close()
        if not report['passed']:
            raise SystemExit('Multilingual browser capture/drain failed; evidence retained')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8772')
    parser.add_argument('--manifest',type=Path,default=Path('samples/multilingual/manifest.json'))
    parser.add_argument('--streams',type=int,default=12)
    parser.add_argument('--seconds',type=int,default=180)
    parser.add_argument('--interval',type=int,choices=[3,6,9],default=6)
    parser.add_argument('--mixed',action='store_true')
    parser.add_argument('--varied',action='store_true',help='Cycle clean, quiet and noisy speech with pauses')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stop-file',type=Path,help='Drain and fail the run if this monitor signal appears')
    asyncio.run(main(parser.parse_args()))
