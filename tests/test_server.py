import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from fastapi.testclient import TestClient
from server import create_app, MAX_BYTES

HEADERS = {'x-caption-local': '1', 'content-type': 'application/octet-stream'}
AUDIO = np.full(16000, 0.02, dtype='<f4').tobytes()

class FakeEngine:
    multilingual = True
    device = "cpu"
    compute_type = "int8"
    def transcribe(self, audio, language):
        return 'Hello theatre.', language or 'en'

def client(engine=None):
    return TestClient(create_app(engine or FakeEngine()), base_url='http://localhost')

def test_caption_and_silence():
    c = client()
    result = c.post('/transcribe', content=AUDIO, headers=HEADERS)
    assert result.status_code == 200
    assert result.json()['text'] == 'Hello theatre.'
    assert result.json()['audio_seconds'] == 1
    result = c.post('/transcribe', content=bytes(64000), headers=HEADERS)
    assert result.json()['text'] == ''

def test_foreign_origin_host_and_missing_header():
    c = client()
    assert c.post('/transcribe', content=AUDIO).status_code == 403
    assert c.post('/transcribe', content=AUDIO, headers={**HEADERS, 'origin':'https://evil.example'}).status_code == 403
    assert c.get('/health', headers={'host':'evil.example'}).status_code == 400
    assert c.post('/transcribe', content=AUDIO, headers={**HEADERS, 'origin':'http://localhost'}).status_code == 200

def test_bad_audio_and_language():
    c = client()
    for body in (b'x', np.full(160, np.nan, dtype='<f4').tobytes(), np.full(160, 2, dtype='<f4').tobytes()):
        assert c.post('/transcribe', content=body, headers=HEADERS).status_code == 400
    assert c.post('/transcribe', content=bytes(MAX_BYTES+4), headers=HEADERS).status_code == 413
    assert c.post('/transcribe?language=nonsense', content=AUDIO, headers=HEADERS).status_code == 400
    assert c.post('/transcribe', content=AUDIO, headers={**HEADERS, 'content-type':'text/plain'}).status_code == 415

def test_busy_rejected_then_recovers():
    entered, release = threading.Event(), threading.Event()
    class BlockingEngine(FakeEngine):
        multilingual = True
        def transcribe(self, audio, language):
            entered.set()
            assert release.wait(5)
            return 'Done', 'en'
    with client(BlockingEngine()) as c, ThreadPoolExecutor() as pool:
        future = pool.submit(c.post, '/transcribe', content=AUDIO, headers=HEADERS)
        assert entered.wait(5)
        try:
            assert c.post('/transcribe', content=AUDIO, headers=HEADERS).status_code == 429
        finally:
            release.set()
        assert future.result().status_code == 200
        assert c.post('/transcribe', content=AUDIO, headers=HEADERS).status_code == 200

def test_engine_failure_releases_lock():
    class BrokenEngine(FakeEngine):
        multilingual = True
        def transcribe(self, audio, language):
            raise RuntimeError('failure')
    c = client(BrokenEngine())
    for _ in range(2):
        assert c.post('/transcribe', content=AUDIO, headers=HEADERS).status_code == 500

def test_static_and_health():
    c = client()
    assert c.get('/').status_code == 200
    assert c.get('/static/pcm-worklet.js').status_code == 200
    assert c.get('/health').json()['ready']

class MultilingualEngine(FakeEngine):
    def __init__(self):
        self.calls = []
    def transcribe(self, audio, language, task='transcribe'):
        self.calls.append((language, task))
        return ('Welcome to the theatre.' if task == 'translate' else 'Bienvenidos al teatro.'), 'es'

def test_translation_language_metadata_and_both():
    engine = MultilingualEngine()
    c = client(engine)
    result = c.post('/transcribe?language=es&mode=translate', content=AUDIO, headers=HEADERS).json()
    assert result['text'] == result['translation'] == 'Welcome to the theatre.'
    assert result['transcript'] == ''
    assert result['language'] == 'es' and result['output_language'] == 'en'
    result = c.post('/transcribe?language=auto&mode=both', content=AUDIO, headers=HEADERS).json()
    assert result['text'] == result['transcript'] == 'Bienvenidos al teatro.'
    assert result['translation'] == 'Welcome to the theatre.'
    assert result['output_language'] == 'es' and result['translation_language'] == 'en'
    assert engine.calls == [('es', 'translate'), (None, 'transcribe'), ('es', 'translate')]

def test_translation_silence_does_not_infer():
    engine = MultilingualEngine()
    c = client(engine)
    for mode in ('translate', 'both'):
        result = c.post(f'/transcribe?language=auto&mode={mode}', content=bytes(64000), headers=HEADERS).json()
        assert result['translation'] == result['transcript'] == result['text'] == ''
        assert result['language'] is None
    assert not engine.calls

def test_english_only_model_rejects_translation_and_foreign_language():
    engine = FakeEngine()
    engine.multilingual = False
    c = client(engine)
    assert c.get('/health').json()['modes'] == ['transcribe']
    for query in ('language=es', 'mode=both', 'mode=translate', 'mode=invalid'):
        assert c.post('/transcribe?'+query, content=AUDIO, headers=HEADERS).status_code == 400

def test_both_english_does_not_repeat_inference():
    result = client().post('/transcribe?language=en&mode=both', content=AUDIO, headers=HEADERS).json()
    assert result['transcript'] == result['translation'] == 'Hello theatre.'

def test_idempotent_retry_and_conflicting_request_id():
    engine = MultilingualEngine()
    c = client(engine)
    headers = {**HEADERS, 'x-request-id':'caption-retry-123'}
    first = c.post('/transcribe?language=es', content=AUDIO, headers=headers)
    second = c.post('/transcribe?language=es', content=AUDIO, headers=headers)
    assert first.json() == second.json()
    assert len(engine.calls) == 1
    assert c.post('/transcribe?language=fr', content=AUDIO, headers=headers).status_code == 409
    assert c.get('/health').json()['completed'] == 1

def test_window_translation_uses_only_committed_audio():
    class WindowEngine(MultilingualEngine):
        def window(self, audio, language, context, final):
            assert context == .5 and not final
            return 'Bienvenidos al teatro.', 'es', 3.5
        def transcribe(self, audio, language, task='transcribe'):
            assert len(audio) == 3*16000 and task == 'translate'
            return 'Welcome to the theatre.', 'es'
    c = client(WindowEngine())
    result = c.post('/transcribe?language=es&mode=both&window=1&final=0&context_seconds=0.5',
                    content=np.full(96000,.02,dtype='<f4').tobytes(), headers=HEADERS)
    assert result.status_code == 200
    assert result.json()['committed_seconds'] == 3.5
    assert result.json()['translation'] == 'Welcome to the theatre.'

def test_window_validation_and_lock_release():
    c = client()
    for query in ('context_seconds=NaN','context_seconds=-1','context_seconds=2','window=1&final=0'):
        assert c.post('/transcribe?'+query, content=AUDIO, headers=HEADERS).status_code == 400
    assert c.post('/transcribe', content=AUDIO, headers=HEADERS).status_code == 200

def test_private_responses_and_static_policy():
    response = client().get('/')
    assert response.headers['cache-control'] == 'no-store'
    assert "script-src 'self';" in response.headers['content-security-policy']
    assert response.headers['referrer-policy'] == 'no-referrer'

def test_disconnected_client_does_not_unlock_running_inference():
    import asyncio
    import httpx
    entered, release = threading.Event(), threading.Event()
    class DisconnectEngine(FakeEngine):
        def transcribe(self, audio, language):
            entered.set()
            assert release.wait(5)
            return 'Still completed.', 'en'
    async def exercise():
        app = create_app(DisconnectEngine())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
            headers={**HEADERS,'x-request-id':'disconnected-retry'}
            pending=asyncio.create_task(c.post('/transcribe',content=AUDIO,headers=headers))
            assert await asyncio.to_thread(entered.wait,2)
            pending.cancel()
            try:
                await pending
            except asyncio.CancelledError:
                pass
            try:
                assert (await c.post('/transcribe',content=AUDIO,headers=HEADERS)).status_code==429
            finally:
                release.set()
            for _ in range(100):
                if not (await c.get('/health')).json()['busy']:
                    break
                await asyncio.sleep(.01)
            result=await c.post('/transcribe',content=AUDIO,headers=headers)
            assert result.json()['text']=='Still completed.'
            assert (await c.get('/health')).json()['completed']==1
    asyncio.run(exercise())

def test_retry_cache_is_bounded():
    engine=MultilingualEngine()
    c=client(engine)
    for n in range(70):
        assert c.post('/transcribe',content=AUDIO,headers={**HEADERS,'x-request-id':f'bounded-{n:08}'}).status_code==200
    # The oldest ID was evicted, so it can no longer return a stale response.
    assert c.post('/transcribe?language=es',content=AUDIO,headers={**HEADERS,'x-request-id':'bounded-00000000'}).status_code==200
    assert len(engine.calls)==71

def test_stuck_worker_watchdog_terminates_process():
    import subprocess
    import sys
    code = 'import time; from server import start_watchdog; start_watchdog({"busy_since":time.monotonic()}, timeout=.1, interval=.02); time.sleep(10)'
    result = subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=5)
    assert result.returncode == 70
    assert b'deadline' in result.stderr
