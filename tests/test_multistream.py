import asyncio
import threading
import time
import httpx
import numpy as np
from server import create_app

HEADERS={'X-Caption-Local':'1','Content-Type':'application/octet-stream'}
AUDIO=np.full(16000,.02,dtype='<f4').tobytes()
class Engine:
    workers=2
    multilingual=True
    device='cpu'
    compute_type='int8'
    def transcribe(self,audio,language,task='transcribe'):
        time.sleep(.03)
        return language,language

def test_twelve_streams_isolated_and_same_stream_overload():
    async def run():
        app=create_app(Engine())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
            async def call(n,lang='en'):
                return await c.post('/transcribe?language='+lang,content=AUDIO,headers={**HEADERS,'X-Stream-ID':f'stream-{n:02}','X-Request-ID':'same-request-id'})
            pending=[asyncio.create_task(call(n,'es' if n%2 else 'en')) for n in range(12)]
            await asyncio.sleep(.01)
            assert (await call(0)).status_code==429
            assert (await call(12)).status_code==429
            health=(await c.get('/health')).json()
            assert health['running']==2 and health['pending']==10
            assert health['rejected']==2
            responses=await asyncio.gather(*pending)
            assert all(r.status_code==200 for r in responses)
            for n,r in enumerate(responses):
                assert r.json()['text']==('es' if n%2 else 'en')
                assert r.json()['stream_id']==f'stream-{n:02}'
                assert (await call(n,'es' if n%2 else 'en')).json()==r.json()
            assert (await c.get('/health')).json()['completed']==12
    asyncio.run(run())

def test_queue_deadline_releases_slot_without_starting_inference():
    entered=threading.Event(); unblock=threading.Event()
    class Blocked(Engine):
        workers=1
        calls=0
        def transcribe(self,audio,language):
            self.calls+=1; entered.set(); assert unblock.wait(3)
            return 'done','en'
    async def run():
        engine=Blocked(); app=create_app(engine,queue_timeout=.03)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
            def call(n):
                return c.post('/transcribe',content=AUDIO,headers={**HEADERS,'X-Stream-ID':f'stream-{n:02}'})
            first=asyncio.create_task(call(0))
            assert await asyncio.to_thread(entered.wait,2)
            try:
                rejected=await call(1)
                assert rejected.status_code==429 and 'deadline' in rejected.text
                assert engine.calls==1
                health=(await c.get('/health')).json()
                assert health['running']==1 and health['pending']==0
                assert health['queue_timeouts']==1
            finally:
                unblock.set()
            assert (await first).status_code==200
            assert (await call(1)).status_code==200
    asyncio.run(run())

def test_continuous_busy_watchdog_tracks_oldest_actual_worker():
    entered = [threading.Event() for _ in range(12)]
    release = [threading.Event() for _ in range(12)]
    class Controlled(Engine):
        workers = 1
        calls = 0
        def transcribe(self, audio, language):
            index = self.calls
            self.calls += 1
            entered[index].set()
            assert release[index].wait(5)
            return language, language
    async def run():
        app=create_app(Controlled())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
            async def call(n):
                return await c.post('/transcribe',content=AUDIO,headers={**HEADERS,'X-Stream-ID':f'stream-{n:02}'})
            tasks=[asyncio.create_task(call(n)) for n in range(12)]
            try:
                assert await asyncio.to_thread(entered[0].wait, 3)
                first=app.state.inference_status['busy_since']
                assert first is not None
                for index in range(1, 12):
                    # Windows monotonic clock may have a 15.6 ms tick.
                    async with asyncio.timeout(3):
                        while time.monotonic() <= first:
                            await asyncio.sleep(.001)
                    release[index-1].set()
                    assert await asyncio.to_thread(entered[index].wait, 3)
                    current=app.state.inference_status['busy_since']
                    assert current is not None and current > first
                    first=current
            finally:
                for event in release:
                    event.set()
            await asyncio.gather(*tasks)
            assert app.state.inference_status['busy_since'] is None
    asyncio.run(run())

def test_invalid_stream_and_released_failed_upload():
    async def run():
        app=create_app(Engine(),max_streams=1)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
            assert (await c.post('/transcribe',content=AUDIO,headers={**HEADERS,'X-Stream-ID':'bad'})).status_code==400
            headers={**HEADERS,'X-Stream-ID':'valid-stream'}
            assert (await c.post('/transcribe',content=b'bad',headers=headers)).status_code==400
            assert (await c.post('/transcribe',content=AUDIO,headers=headers)).status_code==200
    asyncio.run(run())

def test_close_stream_frees_capacity_and_requires_local_header():
    async def run():
        app=create_app(Engine(),max_streams=1)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
            async def call(n):
                return await c.post('/transcribe',content=AUDIO,headers={**HEADERS,'X-Stream-ID':f'stream-{n:02}'})
            first=asyncio.create_task(call(0)); await asyncio.sleep(.01)
            assert (await c.delete('/streams/stream-00',headers=HEADERS)).status_code==409
            await first
            assert (await c.delete('/streams/stream-00')).status_code==403
            assert (await call(1)).status_code==429
            assert (await c.delete('/streams/stream-00',headers=HEADERS)).status_code==200
            assert (await call(1)).status_code==200
    asyncio.run(run())
