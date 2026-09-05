# Architecture decision and validation notes

These are the initial prototype notes. For the subsequent deployment, translation,
and optional CUDA implementation, see [deployment validation](evidence/deployments.md)
and [deployment options](DEPLOYMENT.md). Browser-only inference remains unimplemented.

## Recommendation

Keep inference in a standalone repository. The capture UI should initially be
served by that service. It works on the same machine or through an SSH tunnel,
while caption.ninja remains a static hosted editor/display. No caption.ninja code
changes are required for the existing final-caption protocol.

Build a browser-only Whisper capture page later as an optional producer, sharing
the output protocol. Do not promise the same model size, speed or browser coverage
as the service. On this host, CPU inference is fast enough for a prototype; the
next quality problem is speech segmentation, not GPU provisioning.

At the time of this prototype, the directory was a separate local Git repository
and had not been published. The current project is at
https://github.com/steveseguin/caption-local and adds no server dependencies to caption.ninja.

## Engines considered

| Option | Fit | Tradeoff |
| --- | --- | --- |
| faster-whisper | Implemented CPU int8 prototype; Python packaging and integrated Silero VAD | Python/runtime distribution; no true streaming decoder by itself |
| whisper.cpp | Good native Windows/Linux option and HTTP server; potentially useful for packaged binaries | Still needs capture, phrase segmentation, delivery and operator UI |
| Transformers.js | Viable browser Whisper via WebGPU or WASM | Browser/device performance, initial downloads, memory and fallback need separate testing |

Primary sources inspected:

- https://github.com/SYSTRAN/faster-whisper — CPU int8, bundled audio decoding, VAD.
- https://github.com/ggml-org/whisper.cpp — native platforms and streaming example.
- https://github.com/ggml-org/whisper.cpp/blob/master/examples/server/README.md — HTTP server.
- https://huggingface.co/docs/transformers.js/guides/webgpu — browser WebGPU inference.

Browser-only inference is feasible according to upstream documentation; it has
**not been implemented or benchmarked here**. No conclusion about phone/browser
performance follows from the Python CPU test. Native Windows installation also
remains untested; platform-neutral code and upstream support are not validation.

## Measured on 2026-09-05

Linux x86_64, AMD Ryzen 5 5500 (6 cores / 12 threads), 32 GiB RAM, no working NVIDIA
GPU. Python 3.12, faster-whisper 1.2.1, CTranslate2 4.8.2, CPU int8, four threads,
beam size 1, Silero VAD, English, condition_on_previous_text=False.

Fixture: whisper.cpp's public 11-second JFK sample. One timed pass per case, model
loading excluded from inference times. This is a feasibility probe, not a
representative accuracy or sustained-load benchmark.

| Model | 11-second clip | First 6 seconds | Last 5 seconds | 6-second silence |
| --- | ---: | ---: | ---: | ---: |
| tiny.en | 0.367 s | 0.274 s | 0.285 s | 0.009 s |
| base.en | 0.478 s | 0.422 s | 0.440 s | 0.010 s |
| small.en | 1.320 s | 1.166 s | 1.249 s | 0.010 s |

All three produced the recognizable full quotation and no silence text. Chunking
changed boundary words: base.en ended the first chunk with “what your” and began
the next with “What country can do for you?”. Raw outputs and loading times are
in `evidence/benchmark.json`. Cached model directories were approximately 75 MiB
(tiny.en), 141 MiB (base.en), and 464 MiB (small.en).

Six API tests passed: valid audio/silence, hostile origin/host, malformed and
oversized input, concurrent busy handling/recovery, inference error recovery,
and static/health routes. Chrome also exercised actual microphone capture through
local inference and the existing editor with a local mock relay; no JavaScript
errors or external HTTP requests occurred. See `evidence/browser-smoke.json`.
The fake microphone test intentionally stops mid-speech, and its text contains
errors: it validates transport and stop/drain behavior, not caption quality.

## Next validation gate

Before a community pilot:

1. Replace hard speech cuts with tested streaming/overlap reconciliation or a
   suitable streaming engine. Compare caption errors and delay on consented event
   recordings, including quiet speakers, accents, names, applause and music.
2. Test one human editor keeping up with those recordings and measure total
   audience delay. Fast inference does not imply a usable review workload.
3. Install and test on real Windows hardware, including microphones, start/stop,
   offline model loading and reconnection. Package a simple launcher after this.
4. Validate multilingual models and tune voice detection on theatre audio.
5. Run a long session and remote SSH capture test. If shared hosting is wanted,
   design authentication, TLS, quotas and independent sessions before deployment.
6. Benchmark a separate optional browser worker using Transformers.js on the
   intended laptops/phones, with download progress, cancellation and clear fallback.

The prototype is enough to demonstrate the service boundary and integration. It
is not evidence that reliable accessibility captions are ready for deployment.
