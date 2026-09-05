"""Bounded OpenAI-style WAV transcription/translation adapter.

All inference goes through the native scheduler and retry cache. This is an
explicit subset, not an implementation of OpenAI Realtime or TTS protocols.
"""
import asyncio
from email import policy
from email.parser import BytesParser
import io
import uuid
import wave
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

MAX_UPLOAD = 5 * 1024 * 1024


def parse_wav_form(body, content_type, model_name, translation=False):
    if not content_type.lower().startswith('multipart/form-data;') or len(content_type)>512:
        raise HTTPException(415, 'Use multipart/form-data with a WAV file')
    try:
        header=content_type.encode('ascii')
    except UnicodeEncodeError as exc:
        raise HTTPException(415, 'Multipart content type must be ASCII') from exc
    metadata = BytesParser(policy=policy.default).parsebytes(b'Content-Type: '+header+b'\r\n\r\n',headersonly=True)
    boundary=metadata.get_boundary()
    if not boundary or len(boundary)>70 or not boundary.isascii() or any(ord(c)<32 for c in boundary):
        raise HTTPException(400, 'Invalid multipart boundary')
    # Bound part count before parsing headers. Never recursively parse MIME or
    # spool files to disk; this endpoint accepts flat HTTP form-data only.
    separator=b'\r\n--'+boundary.encode('ascii')
    if body.count(separator)>8:
        raise HTTPException(400, 'Too many multipart fields')
    parts=(b'\r\n'+body).split(separator)
    if parts[0] or parts[-1] not in (b'--',b'--\r\n'):
        raise HTTPException(400, 'Malformed multipart upload')
    fields = {}
    allowed = {'file','model','language','response_format','temperature','stream','prompt'}
    for raw in parts[1:-1]:
        if not raw.startswith(b'\r\n') or b'\r\n\r\n' not in raw:
            raise HTTPException(400, 'Malformed multipart field')
        head,value=raw[2:].split(b'\r\n\r\n',1)
        if len(head)>8192:
            raise HTTPException(400, 'Multipart headers too large')
        part=BytesParser(policy=policy.default).parsebytes(head+b'\r\n\r\n',headersonly=True)
        name = part.get_param('name', header='content-disposition')
        if part.get_content_maintype()=='multipart' or part.get('Content-Transfer-Encoding') or part.get_content_disposition()!='form-data' or name not in allowed or name in fields:
            raise HTTPException(400, 'Unsupported or duplicate multipart field')
        if name != 'file':
            if value is None or len(value)>200:
                raise HTTPException(400, 'Invalid form field')
            try:
                value=value.decode('utf-8')
            except UnicodeDecodeError as exc:
                raise HTTPException(400, 'Form fields must be UTF-8') from exc
        fields[name]=value
    if fields.get('model') not in (model_name, 'whisper-1'):
        raise HTTPException(400, 'Use the loaded local model name or whisper-1 compatibility alias')
    if fields.get('response_format','json') not in ('json','text'):
        raise HTTPException(400, 'Supported response formats: json, text')
    if fields.get('stream','false').lower() != 'false' or fields.get('prompt') or fields.get('temperature','0') not in ('0','0.0'):
        raise HTTPException(400, 'Streaming, prompts and nonzero temperature are not supported')
    if translation and 'language' in fields:
        raise HTTPException(400, 'Translations detect source language; use native API to specify it')
    encoded=fields.get('file')
    if not encoded:
        raise HTTPException(400, 'Missing WAV file')
    try:
        with wave.open(io.BytesIO(encoded)) as wav:
            rate=wav.getframerate()
            if not 8000<=rate<=48000 or wav.getnchannels() not in (1,2) or wav.getsampwidth() not in (1,2,3,4):
                raise HTTPException(415, 'Use uncompressed PCM WAV, mono/stereo, 8–48 kHz')
            if not .01<=wav.getnframes()/rate<=12:
                raise HTTPException(413, 'WAV must contain 0.01–12 seconds; chunk longer recordings')
            expected=wav.getnframes()*wav.getnchannels()*wav.getsampwidth()
            if len(wav.readframes(wav.getnframes()))!=expected:
                raise HTTPException(400, 'Truncated WAV data')
    except (wave.Error, EOFError) as exc:
        raise HTTPException(415, 'Only uncompressed PCM WAV is supported by this adapter') from exc
    from faster_whisper.audio import decode_audio
    audio=decode_audio(io.BytesIO(encoded), sampling_rate=16000).astype('<f4')
    if not 160<=len(audio)<=192000:
        raise HTTPException(413, 'Decoded WAV must contain 0.01–12 seconds')
    return audio.tobytes(), fields.get('language','auto'), fields.get('response_format','json')


def register_audio_api(app, transcribe, close_ephemeral, max_streams, model_name):
    uploads=asyncio.Semaphore(max_streams)

    @app.get('/v1/models')
    async def models():
        return {'object':'list','data':[{'id':model_name,'object':'model','created':0,'owned_by':'local'}]}

    @app.post('/v1/audio/transcriptions')
    @app.post('/v1/audio/translations')
    async def audio_file(request: Request):
        origin=request.headers.get('origin')
        if origin and origin!=str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'Foreign Origin is not allowed')
        if uploads.locked():
            raise HTTPException(429, 'Upload capacity reached',headers={'Retry-After':'1'})
        async with uploads:
            body=bytearray()
            try:
                async with asyncio.timeout(10):
                    async for chunk in request.stream():
                        if len(body)+len(chunk)>MAX_UPLOAD:
                            raise HTTPException(413, 'Multipart upload exceeds 5 MiB')
                        body.extend(chunk)
            except TimeoutError as exc:
                raise HTTPException(408, 'Upload timed out') from exc
            translation=request.url.path.endswith('/translations')
            pcm,language,response_format=await asyncio.to_thread(parse_wav_form, bytes(body),
                request.headers.get('content-type',''), model_name, translation)
            ephemeral='x-stream-id' not in request.headers
            sid=request.headers.get('x-stream-id',uuid.uuid4().hex)
            headers=dict(request.headers)
            headers.update({'content-type':'application/octet-stream','x-caption-local':'1','x-stream-id':sid})
            headers.pop('content-length',None)
            scope=dict(request.scope)
            scope['headers']=[(key.encode('latin-1'),value.encode('latin-1')) for key,value in headers.items()]
            scope['query_string']=urlencode({'language':language,'mode':'translate' if translation else 'transcribe'}).encode()
            sent=False
            async def receive():
                nonlocal sent
                if sent:
                    return {'type':'http.disconnect'}
                sent=True
                return {'type':'http.request','body':pcm,'more_body':False}
            try:
                result=await transcribe(Request(scope,receive))
                if response_format=='text':
                    return PlainTextResponse(result['text'])
                return JSONResponse({'text':result['text']})
            finally:
                if ephemeral:
                    close_ephemeral(sid)
