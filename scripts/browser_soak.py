"""Ten-minute real CPU/browser capture gate. No relay connections or publishing."""
import argparse
import json
import os
from pathlib import Path
import time
import wave
import numpy as np
import psutil
from faster_whisper.audio import decode_audio
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--seconds',type=int,default=600)
parser.add_argument('--pid',type=int,required=True,help='Inference server process to monitor')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
audio=decode_audio(str(root/'samples/jfk.wav'))
loop=np.concatenate([audio,np.zeros(16000,np.float32)])
fixture=root/'samples/soak.wav'
with wave.open(str(fixture),'wb') as f:
    f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
    f.writeframes((loop*32767).astype('<i2').tobytes())
process=psutil.Process(args.pid)
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=[
        '--no-sandbox','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',
        f'--use-file-for-fake-audio-capture={fixture}'])
    context=browser.new_context(permissions=['microphone'])
    page=context.new_page(); errors=[]; external=[]; samples=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def guard(route):
        if route.request.url.startswith(('http://127.0.0.1:','http://localhost:')):
            route.continue_()
        else:
            external.append(route.request.url); route.abort()
    context.route('**/*',guard)
    page.goto(os.environ.get('CAPTION_TEST_URL','http://127.0.0.1:8771'))
    page.get_by_role('button',name='Start captions',exact=True).click()
    started=time.monotonic()
    while time.monotonic()-started < args.seconds:
        page.wait_for_timeout(5000)
        snapshot=page.evaluate('() => ({running, buffered:buffer.length/16000, captions:transcript.length, error:document.querySelector("#error").textContent})')
        snapshot.update(seconds=round(time.monotonic()-started,1),rss_mib=round(process.memory_info().rss/1024**2,1))
        samples.append(snapshot)
        assert snapshot['running'] and not snapshot['error'],snapshot
        assert snapshot['buffered'] <= 30,snapshot
        if len(samples)%12==0: print(json.dumps(snapshot),flush=True)
    page.get_by_role('button',name='Stop',exact=True).click()
    page.wait_for_function('() => !document.querySelector("#start").disabled',timeout=90000)
    captions=page.evaluate('() => transcript')
    assert not errors and not external,(errors,external)
    assert len(captions)>=args.seconds/15,(len(captions),args.seconds)
    warmed=[s['rss_mib'] for s in samples if s['seconds']>=60] or [s['rss_mib'] for s in samples]
    assert max(warmed)-min(warmed)<128,warmed
    result={'duration_seconds':round(time.monotonic()-started,1),'model':'small','device':'cpu',
            'caption_count':len(captions),'max_buffer_seconds':max(s['buffered'] for s in samples),
            'warm_rss_range_mib':[min(warmed),max(warmed)],'browser_errors':errors,'external_requests':external,
            'samples':samples,'first_captions':captions[:6],'last_captions':captions[-6:]}
    (root/'evidence/browser-soak.json').write_text(json.dumps(result,indent=2)+'\n')
    print('BROWSER SOAK PASSED',flush=True); browser.close()
