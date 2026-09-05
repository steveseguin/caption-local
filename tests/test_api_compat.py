import io
import wave
import asyncio
import threading
import httpx

import numpy as np
import pytest
from fastapi.testclient import TestClient as BaseClient

def TestClient(app):
    return BaseClient(app, base_url="http://localhost")
from server import create_app


class Engine:
    workers=1
    multilingual=True
    device='cpu'
    compute_type='int8'
    model_name='small'
    calls=0
    def transcribe(self,audio,language,task='transcribe'):
        self.calls+=1
        return ('Welcome.' if task=='translate' else 'Bienvenue.'), language or 'fr'


def wav(seconds=1):
    output=io.BytesIO()
    with wave.open(output,'wb') as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(16000)
        writer.writeframes(np.full(int(seconds*16000),5000,dtype='<i2').tobytes())
    return output.getvalue()


def post(client, **kwargs):
    return client.post('/v1/audio/transcriptions',files={'file':('sample.wav',wav(),'audio/wav')},
                       data={'model':'whisper-1',**kwargs})


def test_optional_auth_guards_inference_health_and_models_without_leaking(capsys):
    key='test-local-access-key-123456'
    client=TestClient(create_app(Engine(),api_key=key,log_requests=True))
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    for path in ('/health','/v1/models','/streams/private-stream','/transcribe'):
        response=client.get(path,headers={'Authorization':'Bearer wrong'})
        assert response.status_code==401
        assert response.headers['WWW-Authenticate']=='Bearer'
    assert client.get('/health',headers={'Authorization':'Bearer '+key}).json()['ready']
    assert post(client).status_code==401
    logs=capsys.readouterr().out
    assert key not in logs and 'wrong' not in logs and 'private-stream' not in logs
    assert 'http_request' in logs


def test_empty_key_keeps_local_behavior_and_short_key_fails():
    assert TestClient(create_app(Engine(),api_key='')).get('/health').status_code==200
    with pytest.raises(ValueError):
        create_app(Engine(),api_key='short')


def test_wav_transcription_translation_and_ephemeral_cleanup():
    engine=Engine(); client=TestClient(create_app(engine))
    assert client.get('/v1/models').json()['data'][0]['id']=='small'
    assert post(client,language='fr').json()=={'text':'Bienvenue.'}
    assert post(client,response_format='text').text=='Bienvenue.'
    response=client.post('/v1/audio/translations',files={'file':('sample.wav',wav())},data={'model':'small'})
    assert response.json()=={'text':'Welcome.'}
    assert engine.calls==3
    assert client.get('/health').json()['sessions']==0


def test_compat_retries_use_native_cache_and_conflicts():
    engine=Engine(); client=TestClient(create_app(engine))
    headers={'X-Stream-ID':'sdk-stream-123','X-Request-ID':'sdk-request-123'}
    def request(data):
        return client.post('/v1/audio/transcriptions',files={'file':('sample.wav',data)},
                           data={'model':'small','language':'fr'},headers=headers)
    assert request(wav()).status_code==200
    assert request(wav()).status_code==200
    assert engine.calls==1
    assert request(wav(2)).status_code==409
    assert engine.calls==1


@pytest.mark.parametrize('fields',[{'model':'not-loaded'},{'response_format':'verbose_json'},
    {'prompt':'ignored prompt'},{'stream':'true'},{'temperature':'1'},{'language':'not-a-language'}])
def test_unsupported_semantics_fail_explicitly(fields):
    client=TestClient(create_app(Engine()))
    assert post(client,**fields).status_code==400


def test_limits_malformed_input_and_foreign_origin():
    engine=Engine(); client=TestClient(create_app(engine))
    for data,status in ((b'not audio',415),(wav(13),413),(wav()[:-10],400)):
        response=client.post('/v1/audio/transcriptions',files={'file':('sample.wav',data)},data={'model':'small'})
        assert response.status_code==status
    assert client.post('/v1/audio/transcriptions',content=b'x'*(5*1024*1024+1),
                       headers={'Content-Type':'multipart/form-data; boundary=x'}).status_code==413
    assert client.post('/v1/audio/transcriptions',headers={'Origin':'https://untrusted.example'}).status_code==403
    assert engine.calls==0
    assert client.get('/health').json()['sessions']==0


def test_adapter_disconnect_keeps_worker_and_native_retry_identity():
    entered=threading.Event(); release=threading.Event()
    class Blocked(Engine):
        def transcribe(self,audio,language,task='transcribe'):
            self.calls+=1; entered.set(); assert release.wait(5)
            return 'Bienvenue.','fr'
    async def run():
        engine=Blocked(); app=create_app(engine)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as client:
            headers={'X-Stream-ID':'adapter-stream','X-Request-ID':'adapter-retry-id'}
            async def call():
                return await client.post('/v1/audio/transcriptions',files={'file':('test.wav',wav())},
                                         data={'model':'small','language':'fr'},headers=headers)
            task=asyncio.create_task(call())
            assert await asyncio.to_thread(entered.wait,3)
            try:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert (await client.get('/health')).json()['running']==1
                assert (await call()).status_code==429
            finally:
                release.set()
            async with asyncio.timeout(3):
                while (await client.get('/health')).json()['running']:
                    await asyncio.sleep(.01)
            assert (await call()).json()=={'text':'Bienvenue.'}
            assert engine.calls==1
    asyncio.run(run())
