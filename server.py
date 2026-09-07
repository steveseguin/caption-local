"""Multiple-stream, loopback-only transcription service. No audio persistence."""
from contextlib import asynccontextmanager
import argparse
import logging
import os
import asyncio
from pathlib import Path
import threading
import time
import hashlib
import re
import sysconfig
import secrets
import json
from collections import OrderedDict

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.cors import CORSMiddleware
from urllib.parse import urlsplit
from starlette.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
RATE = 16000
MAX_BYTES = RATE * 4 * 12
VERSION = "1.1.0"
DEFAULT_MODEL_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
MODEL_REVISIONS = {"small": DEFAULT_MODEL_REVISION, "base": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
                   "medium": "08e178d48790749d25932bbc082711ddcfdfbc4f",
                   "large-v3": "edaa852ec7e145841d8ffdb056a99866b5f0a478"}
_CUDA_DLL_HANDLES = []


def configure_windows_cuda():
    """Make optional NVIDIA wheels in this environment visible to native loaders.

    Only this process is changed; no driver, registry or system PATH edits.
    Keep add_dll_directory handles alive for delayed cuDNN dependency loading.
    """
    if os.name != 'nt' or _CUDA_DLL_HANDLES:
        return
    base = Path(sysconfig.get_path('purelib')) / 'nvidia'
    directories = [base / name / 'bin' for name in ('cublas', 'cuda_nvrtc', 'cudnn')]
    directories = [directory for directory in directories if directory.is_dir()]
    for directory in directories:
        _CUDA_DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    if directories:
        # CTranslate2/cuDNN also use LoadLibrary, which consults process PATH.
        os.environ['PATH'] = os.pathsep.join(map(str, directories)) + os.pathsep + os.environ.get('PATH', '')


class Engine:
    def __init__(self, model, threads=4, offline=False, device="cpu", compute_type="auto", workers=1, beam_size=5):
        if device in ('cuda', 'auto'):
            configure_windows_cuda()
        import ctranslate2
        from faster_whisper import WhisperModel
        requested_device = device
        if device == "auto":
            try:
                device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            except RuntimeError:
                device = "cpu"
        def load(selected):
            precision = compute_type if compute_type != "auto" else ("float16" if selected == "cuda" else "int8")
            instance = WhisperModel(model, device=selected, compute_type=precision,
                                    cpu_threads=threads, num_workers=workers, local_files_only=offline,
                                    revision=MODEL_REVISIONS.get(model))
            return instance, precision
        try:
            self.model, self.compute_type = load(device)
        except RuntimeError:
            if requested_device != "auto" or device != "cuda" or compute_type != "auto":
                raise
            logging.warning("CUDA model loading failed; auto mode is falling back to CPU int8")
            device = "cpu"
            self.model, self.compute_type = load(device)
        self.beam_size = beam_size
        self.workers = workers
        self.threads = threads
        self.device = device
        self.model_name = Path(model).name
        self.multilingual = self.model.model.is_multilingual
        self.actual_compute_type = getattr(self.model.model, 'compute_type', self.compute_type)
        logging.getLogger("uvicorn.error").info("Inference device: %s; compute type: %s", device, self.compute_type)

    def transcribe(self, audio, language, task="transcribe"):
        segments, info = self.model.transcribe(
            audio, language=language, task=task, beam_size=getattr(self, "beam_size", 5), temperature=0, vad_filter=True,
            condition_on_previous_text=False,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        return " ".join(s.text.strip() for s in segments).strip(), info.language


    def window(self, audio, language, context_seconds=0, final=True):
        """Commit complete words; retain the last second for the next window."""
        duration = len(audio) / RATE
        segments, info = self.model.transcribe(
            audio, language=language, beam_size=getattr(self, "beam_size", 5), temperature=0, vad_filter=True,
            word_timestamps=True, condition_on_previous_text=False,
            hallucination_silence_threshold=1.0,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        cutoff = duration if final else max(context_seconds, duration - 1.0)
        selected = []
        for segment in segments:
            for word in segment.words or []:
                # Midpoint excludes previously committed context, even if a
                # subsequent decode adjusts its timestamps slightly.
                repeated_boundary = (context_seconds > 0 and word.end - word.start <= 0.001
                                     and word.end <= context_seconds + 0.08)
                if not repeated_boundary and (word.start + word.end) / 2 > context_seconds and word.end <= cutoff + 0.001:
                    selected.append(word)
        text = "".join(word.word for word in selected).strip()
        if not any(char.isalnum() for char in text):
            text = ""
        committed = duration if final else (selected[-1].end if selected else cutoff)
        return text, info.language, max(context_seconds, min(committed, duration))

    def warmup(self):
        # Exercise the actual decoder before readiness, including CUDA libraries.
        segments, _ = self.model.transcribe(np.zeros(RATE, dtype=np.float32),
                                           language="en", beam_size=1, temperature=0,
                                           vad_filter=False, max_new_tokens=1)
        list(segments)


def create_app(engine, max_streams=12, queue_timeout=20, api_key=None, log_requests=False, allowed_origins=()):
    api_key = api_key or None
    if api_key is not None and (len(api_key) < 24 or not api_key.isascii() or any(c.isspace() for c in api_key)):
        raise ValueError('CAPTION_API_KEY must contain at least 24 ASCII characters without whitespace')
    allowed_origins = tuple(allowed_origins)
    if allowed_origins and not api_key:
        raise ValueError('CAPTION_ALLOWED_ORIGINS requires CAPTION_API_KEY')
    for origin in allowed_origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in ('https', 'http') or not parsed.hostname or
                parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or
                origin != f'{parsed.scheme}://{parsed.netloc}' or '*' in origin or
                any(c.isspace() or ord(c) < 32 for c in origin) or
                (parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'))):
            raise ValueError('Allowed origins must be exact HTTPS origins (HTTP only for localhost)')
        parsed.port  # Validate malformed ports before starting.
    pending_tasks = set()
    @asynccontextmanager
    async def lifespan(app):
        yield
        # Finish shielded requests before releasing model resources at shutdown.
        if pending_tasks:
            await asyncio.gather(*list(pending_tasks), return_exceptions=True)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.allowed_origins = allowed_origins
    app.add_middleware(CORSMiddleware, allow_origins=list(allowed_origins),
                       allow_methods=['GET', 'POST', 'DELETE'],
                       allow_headers=['Authorization', 'Content-Type', 'X-Caption-Local', 'X-Stream-ID', 'X-Request-ID'],
                       expose_headers=['Retry-After'], max_age=600)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
    # One outstanding request per stream bounds both body memory and queue size.
    # asyncio's semaphore queues waiters FIFO; the model owns matching CT2 workers.
    workers = getattr(engine, "workers", 1)
    slots = asyncio.Semaphore(workers)
    streams = OrderedDict()
    running = {}
    def release(stream_id):
        streams[stream_id]["busy"] = False
        streams[stream_id]["seen"] = time.monotonic()
        running.pop(stream_id, None)
        state["busy_since"] = min(running.values(), default=None)

    def admit(stream_id):
        now = time.monotonic()
        for key in list(streams):
            if not streams[key]["busy"] and now - streams[key]["seen"] > 120:
                del streams[key]
        if stream_id not in streams:
            if len(streams) >= max_streams:
                state["rejected"] += 1
                raise HTTPException(429, "Stream capacity reached; idle sessions expire after 120 seconds", headers={"Retry-After": "2"})
            streams[stream_id] = {"busy": False, "seen": now, "cache": OrderedDict()}
        session = streams[stream_id]
        if session["busy"]:
            state["rejected"] += 1
            raise HTTPException(429, "Stream busy; retry shortly", headers={"Retry-After": "1"})
        session["busy"] = True
        session["seen"] = now
        return session["cache"]
    state = {"busy_since": None, "completed": 0, "failed": 0, "rejected": 0, "queue_timeouts": 0}
    app.state.inference_status = state

    @app.middleware("http")
    async def response_headers(request, call_next):
        started = time.perf_counter()
        public_asset = request.url.path in ('/', '/capture-local.html') or request.url.path.startswith('/static/')
        preflight = request.method == 'OPTIONS' and request.headers.get('origin') and request.headers.get('access-control-request-method')
        if api_key and not public_asset and not preflight and not secrets.compare_digest(
                request.headers.get('authorization', '').encode(), ('Bearer '+api_key).encode()):
            response = JSONResponse({'detail':'Service access token required'}, status_code=401,
                                    headers={'WWW-Authenticate':'Bearer'})
        else:
            response = await call_next(request)
        if log_requests and not public_asset:
            # Fixed route labels only: no URL queries, tokens, IDs, IPs, audio or text.
            route = request.scope.get('route')
            print(json.dumps({'event':'http_request','method':request.method,
                  'route':getattr(route, 'path', 'unmatched'), 'status':response.status_code,
                  'duration_seconds':round(time.perf_counter()-started,4)}),flush=True)
        if request.headers.get('origin') in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = request.headers['origin']
            response.headers.add_vary_header('Origin')
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' wss: ws://localhost:* ws://127.0.0.1:* ws://[::1]:*; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'self'"
        )
        return response

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "static/index.html")

    @app.get('/capture-local.html')
    async def capture_local():
        return FileResponse(ROOT / 'static/capture-local.html')

    @app.get("/health")
    async def health():
        from faster_whisper.tokenizer import _LANGUAGE_CODES
        age = time.monotonic() - state["busy_since"] if state["busy_since"] is not None else 0
        return {"ready": age < 90, "version": VERSION, "sample_rate": RATE, "max_seconds": 12,
                "max_streams": max_streams, "workers": workers, "beam_size": getattr(engine, "beam_size", 5),
                "threads_per_worker": getattr(engine, "threads", None),
                "sessions": len(streams), "running": len(running),
                "pending": sum(v["busy"] for v in streams.values()) - len(running),
                "queue_timeout": queue_timeout, "rejected": state["rejected"],
                "queue_timeouts": state["queue_timeouts"],
                "multilingual": engine.multilingual,
                "model": getattr(engine, "model_name", "unknown"),
                "languages": sorted(_LANGUAGE_CODES) if engine.multilingual else ["en"],
                "device": engine.device, "compute_type": engine.compute_type,
                "actual_compute_type": getattr(engine, 'actual_compute_type', engine.compute_type),
                "busy": state["busy_since"] is not None, "completed": state["completed"], "failed": state["failed"],
                "modes": ["transcribe", "translate", "both"] if engine.multilingual else ["transcribe"],
                "translation_target": "en" if engine.multilingual else None}

    @app.delete("/streams/{stream_id}")
    async def close_stream(stream_id: str, request: Request):
        origin = request.headers.get("origin")
        if request.headers.get("x-caption-local") != "1" or (origin and origin != str(request.base_url).rstrip("/") and origin not in allowed_origins):
            raise HTTPException(403, "Use the local capture page")
        session = streams.get(stream_id)
        if session and session["busy"]:
            raise HTTPException(409, "Finish pending audio before closing a stream")
        streams.pop(stream_id, None)
        return {"closed": stream_id}

    @app.post("/transcribe")
    async def transcribe(request: Request):
        origin = request.headers.get("origin")
        if request.headers.get("x-caption-local") != "1" or (
            origin and origin != str(request.base_url).rstrip("/") and origin not in allowed_origins
        ):
            raise HTTPException(403, "Use the local capture page")
        if request.headers.get("content-type") != "application/octet-stream":
            raise HTTPException(415, "Expected little-endian float32 mono PCM at 16000 Hz")
        language = request.query_params.get("language", "en")
        from faster_whisper.tokenizer import _LANGUAGE_CODES
        if language != "auto" and language not in _LANGUAGE_CODES:
            raise HTTPException(400, "Unknown language code")
        mode = request.query_params.get("mode", "transcribe")
        if mode not in ("transcribe", "translate", "both"):
            raise HTTPException(400, "Mode must be transcribe, translate, or both")
        if not engine.multilingual and (mode != "transcribe" or language not in ("auto", "en")):
            raise HTTPException(400, "Restart with a multilingual model such as --model small for this language or translation")
        window = request.query_params.get("window", "0") == "1"
        final = request.query_params.get("final", "1") == "1"
        try:
            context = float(request.query_params.get("context_seconds", "0"))
            if not np.isfinite(context) or not 0 <= context <= 1:
                raise ValueError()
        except ValueError:
            raise HTTPException(400, "Context must be between 0 and 1 seconds")
        request_id = request.headers.get("x-request-id", "")
        if request_id and not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
            raise HTTPException(400, "Invalid request ID")
        stream_id = request.headers.get("x-stream-id", "legacy")
        if stream_id != "legacy" and not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", stream_id):
            raise HTTPException(400, "Invalid stream ID")
        cache = admit(stream_id)
        handed_to_worker = False
        try:
            body = bytearray()
            try:
                async with asyncio.timeout(10):
                    async for part in request.stream():
                        if len(body) + len(part) > MAX_BYTES:
                            raise HTTPException(413, "Audio chunk exceeds 12 seconds")
                        body.extend(part)
            except TimeoutError:
                raise HTTPException(408, "Audio upload timed out")
            if len(body) < 4 * 160 or len(body) % 4:
                raise HTTPException(400, "Invalid PCM length")
            audio = np.frombuffer(body, dtype="<f4").copy()
            if not np.isfinite(audio).all() or np.max(np.abs(audio)) > 1.01:
                raise HTTPException(400, "Invalid PCM samples")
            duration = len(audio) / RATE
            if context >= duration or (window and not final and duration - context < 2):
                raise HTTPException(400, "Window must contain new audio; unfinished windows need at least two seconds")
            signature = hashlib.sha256(body + str((language, mode, window, final, context)).encode()).hexdigest()
            now = time.monotonic()
            while cache and (len(cache) > 64 or now - next(iter(cache.values()))[0] > 120):
                cache.popitem(last=False)
            if request_id and request_id in cache:
                _, previous_signature, result = cache[request_id]
                if signature != previous_signature:
                    raise HTTPException(409, "Request ID was already used for different audio or options")
                return result

            def infer():
                try:
                    start = time.perf_counter()
                    transcript = translation = ""
                    detected = None if language == "auto" else language
                    committed = duration if final else duration - 1
                    if np.max(np.abs(audio)) >= 0.0001:
                        if window:
                            transcript, detected, committed = engine.window(audio, detected, context, final)
                        elif mode in ("transcribe", "both"):
                            transcript, detected = engine.transcribe(audio, detected)
                        if mode in ("translate", "both"):
                            if detected == "en" and (window or mode == "both"):
                                translation = transcript
                            elif (not window and mode == "translate") or transcript:
                                selected_audio = audio[round(context * RATE):round(committed * RATE)] if window else audio
                                translation, detected = engine.transcribe(selected_audio, detected, task="translate")
                    if mode == "translate":
                        transcript = ""
                    result = {"text": translation if mode == "translate" else transcript,
                              "transcript": transcript, "translation": translation,
                              "language": detected, "output_language": "en" if mode == "translate" else detected,
                              "translation_language": "en" if mode in ("translate", "both") else None,
                              "mode": mode, "audio_seconds": duration, "committed_seconds": committed,
                              "request_id": request_id, "stream_id": stream_id,
                              "inference_seconds": round(time.perf_counter() - start, 3)}
                    return result
                except Exception:
                    logging.exception("Transcription worker failed")
                    raise

            async def scheduled():
                queued = time.monotonic()
                try:
                    try:
                        await asyncio.wait_for(slots.acquire(), timeout=queue_timeout)
                    except TimeoutError:
                        state["queue_timeouts"] += 1
                        raise HTTPException(429, "Inference queue deadline reached; retry pending audio", headers={"Retry-After": "1"})
                    try:
                        running[stream_id] = time.monotonic()
                        state["busy_since"] = min(running.values())
                        wait = running[stream_id] - queued
                        try:
                            result = await asyncio.to_thread(infer)
                        except Exception:
                            state["failed"] += 1
                            raise
                        result["queue_seconds"] = round(wait, 3)
                        if request_id:
                            cache[request_id] = (time.monotonic(), signature, result)
                            while len(cache) > 64:
                                cache.popitem(last=False)
                        state["completed"] += 1
                        return result
                    finally:
                        slots.release()
                finally:
                    release(stream_id)

            task = asyncio.create_task(scheduled())
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)
            # Consume late errors if the HTTP client disconnects while inference
            # finishes. The result remains cached for its request ID.
            task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
            handed_to_worker = True
            try:
                return await asyncio.shield(task)
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(500, "Transcription failed; pending audio can be retried") from exc
        finally:
            if not handed_to_worker:
                release(stream_id)

    from api_compat import register_audio_api
    def close_ephemeral(stream_id):
        session = streams.get(stream_id)
        if session and not session['busy']:
            streams.pop(stream_id, None)
    register_audio_api(app, transcribe, close_ephemeral, max_streams, getattr(engine, 'model_name', 'local'))
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


def start_watchdog(state, timeout=90, interval=5):
    def watch():
        while True:
            time.sleep(interval)
            since = state["busy_since"]
            if since is not None and time.monotonic() - since > timeout:
                logging.critical("Inference exceeded its deadline; exiting for the service supervisor to restart")
                os._exit(70)
    thread = threading.Thread(target=watch, name="inference-watchdog", daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("CAPTION_MODEL", "small"), help="Model name or downloaded directory")
    parser.add_argument("--beam-size", type=int, choices=range(1,6), default=int(os.environ.get("CAPTION_BEAM_SIZE", "5")))
    parser.add_argument("--workers", type=int, default=int(os.environ.get("CAPTION_WORKERS", "1")))
    parser.add_argument("--max-streams", type=int, default=int(os.environ.get("CAPTION_MAX_STREAMS", "12")))
    parser.add_argument("--threads", type=int, default=int(os.environ.get("CAPTION_THREADS", "4")))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--offline", action="store_true", default=os.environ.get("CAPTION_OFFLINE") == "1")
    parser.add_argument("--log-requests", action="store_true", default=os.environ.get("CAPTION_LOG_REQUESTS") == "1",
                        help="Write request status/duration JSON to stdout; exclude captions and credentials")
    parser.add_argument("--host", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1",
                        help="Use 0.0.0.0 only inside a container with a loopback host port mapping")
    parser.add_argument("--device", choices=["cpu", "cuda", "auto"], default=os.environ.get("CAPTION_DEVICE", "cpu"))
    parser.add_argument("--compute-type", choices=["auto", "int8", "float32", "float16", "int8_float16"],
                        default=os.environ.get("CAPTION_COMPUTE_TYPE", "auto"))
    args = parser.parse_args()
    if args.threads < 1 or not 1 <= args.beam_size <= 5 or not 1 <= args.workers <= 8 or not 1 <= args.max_streams <= 64 or not 1 <= args.port <= 65535:
        parser.error("Threads must be positive; beam size 1–5; workers 1–8; streams 1–64; port 1–65535")
    print("Loading speech model; first run downloads weights. Audio stays on this host.", flush=True)
    engine = Engine(args.model, args.threads, args.offline, args.device, args.compute_type, args.workers, args.beam_size)
    engine.warmup()
    print(f"Inference ready: {engine.device} / {engine.compute_type}", flush=True)
    import uvicorn
    app = create_app(engine, args.max_streams, api_key=os.environ.get('CAPTION_API_KEY'), log_requests=args.log_requests,
                     allowed_origins=tuple(s.strip() for s in os.environ.get('CAPTION_ALLOWED_ORIGINS', '').split(',') if s.strip()))
    start_watchdog(app.state.inference_status)
    # Browsers can retain six HTTP/1.1 connections per origin while loading assets.
    # This transport bound includes idle sockets; inference admission stays separate.
    uvicorn.run(app, host=args.host, port=args.port, access_log=False, limit_concurrency=max(64, args.max_streams * 6 + 16), timeout_keep_alive=5, timeout_graceful_shutdown=90)
