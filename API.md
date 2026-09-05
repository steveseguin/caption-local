# Caption Local API v1

Loopback-only, multiple trusted producers. Use the local page or a trusted local client. There is
no CORS allowance, authentication layer, multi-tenant isolation or permanent store.

## Health

`GET /health` is available only after model load and actual decoder warmup. It
returns `ready`, `version`, `sample_rate` (16000), `max_seconds` (12), `multilingual`,
`model`, `languages`, `device`, `compute_type`, `modes`, `translation_target`, `busy`, `completed`, and
`failed`. Precision is the requested CTranslate2 compute mode; internal hardware
fallback may differ. A native watchdog exits if an individual running inference remains busy
for more than 90 seconds. Use Docker or systemd for automatic restart.

## Stream scheduling

One request may upload, queue or run per stream. Independent streams share FIFO
worker admission. Default limits: twelve sessions, one inference worker, twenty
seconds queue wait, ten seconds upload time, and twelve seconds audio per chunk.
A busy stream receives 429 without buffering a second body. At most twelve bodies
can exist at default capacity. Increase workers with `--workers`; use the same
setting for the model and scheduler (the CLI handles this).

Idle sessions and their retry caches expire opportunistically after 120 seconds.
`DELETE /streams/{stream_id}` with `X-Caption-Local: 1` closes an idle session and
forgets its cached results immediately; a busy session returns 409. Stop and drain
before closing. The browser does this automatically on successful Stop. There is
no persistent reservation while a stream is silent beyond the idle timeout.

Health additionally reports `max_streams`, `workers`, `threads_per_worker`, `beam_size`,
`sessions`, `running`, `pending` (uploads plus queued requests), `queue_timeout`,
`rejected` (busy/capacity admission refusals), and `queue_timeouts`.
`queue_seconds` excludes upload and inference. A cached retry returns the original
timing values. Stream IDs are not credentials: local trusted clients can access
this API and must use distinct, unguessable IDs to avoid accidental collisions.

## Transcribe

`POST /transcribe?language=es&mode=both`

Required headers:

- `Content-Type: application/octet-stream`
- `X-Caption-Local: 1`
- Optional `X-Stream-ID`: 8–80 ASCII letters, numbers, `_` or `-`; use a random UUID
  per input stream. Omission uses the shared `legacy` stream.
- Optional `X-Request-ID`: 8–80 ASCII letters, numbers, `_` or `-`.

Body: little-endian float32 mono PCM, 16 kHz, normalized to [-1, 1], finite samples,
0.01–12 seconds. No WAV header. Upload time is limited to ten seconds.

`language` defaults to `en` and accepts Whisper language codes or `auto`.
`mode` is `transcribe` (default), `translate` (English only), or `both`.
English-only models reject non-English languages and translation modes.

```json
{
  "text": "Bienvenidos al teatro.",
  "transcript": "Bienvenidos al teatro.",
  "translation": "Welcome to the theatre.",
  "language": "es",
  "output_language": "es",
  "translation_language": "en",
  "mode": "both",
  "audio_seconds": 3.0,
  "committed_seconds": 3.0,
  "request_id": "example-12345678",
  "stream_id": "example-stream-123",
  "queue_seconds": 0.2,
  "inference_seconds": 0.8
}
```

Timings are illustrative. `text` is the transcript except in translate-only mode,
where it is the English translation. `language` describes source speech;
`output_language` describes `text`. Unrequested output fields are empty strings.
Silence with automatic detection can return `language: null`.

## Rolling windows

Add `window=1`, `final=0`, and `context_seconds=0.5` to decode an unfinished window.
Context is previously committed audio retained at the front, from zero to one
second. At least two seconds of new audio are required for an unfinished window.

The decoder retains the last second of unfinished speech and emits only decoded
words ending before that cutoff. `committed_seconds` identifies how far the caller
may advance in the supplied audio. Retain 0.5 seconds before this point as context
for the next window; append new audio after the old uncommitted tail. Do not
advance by the request's whole duration. On a pause or Stop, send `final=1` (the
default), which commits the complete supplied window. The browser's tested buffer
implementation is in `static/audio-buffer.js`.

For translation, the service first chooses the source-language word boundary and
then translates only the newly committed audio. Both outputs therefore correspond
to the same committed source interval. Word timestamps are estimates: this method
reduces boundary artifacts but cannot guarantee perfect word alignment.

## Retry and error behavior

Reuse the same stream ID and request ID with identical audio and options after a lost response.
Successful results are kept in memory for up to 120 seconds, with at most 64
entries per stream. Different audio/options with a cached ID returns 409. The cache does not
survive server restart and does not guarantee exactly-once delivery to external
caption relays. A client disconnect does not unlock a running worker.

| Status | Meaning | Client action |
| --- | --- | --- |
| 400 | Invalid audio, language, mode, context or ID | Correct input; retain audio if recoverable |
| 403 | Wrong/missing local header or foreign Origin | Use the local page/client |
| 408 | Upload exceeded ten seconds | Retry the same request ID |
| 409 | Reused ID with different input | Fix client ID handling |
| 413 / 415 | Oversized audio / wrong content type | Correct the request |
| 429 | Stream busy, stream capacity reached, or queue deadline exceeded | Honor Retry-After and retain pending audio |
| 500 | Inference failed | Retain audio; inspect server logs, then retry |
| 503 | HTTP concurrency limit or restarting service | Back off and retry |

The browser retries network errors and 408/429/502/503/504 up to three times after
the first attempt, then stops capture with manual recovery controls. It never
silently discards a failed request. Response caching is disabled at the HTTP layer;
transcripts are not saved to disk by the service.
