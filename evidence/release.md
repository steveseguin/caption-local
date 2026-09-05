# Caption Local 1.0 — Linux CPU release validation

Historical single-stream baseline. For the current independent-stream behavior,
see [version 1.1 validation](multistream/report.md).

Validated on 2026-09-05: Linux x86-64, AMD Ryzen 5 5500 (6 cores / 12 threads),
32 GiB RAM, Python 3.12, Docker 29.1.3 / Compose 2.37.1. CPU int8, four threads,
multilingual small model at revision `536b0662742c02347bc0e980a01041f333bce120`.
No NVIDIA acceleration was used.

Release scope: one trusted local operator, Linux CPU, native or Docker inference,
Chrome microphone capture, optional SSH transport and caption.ninja editor output.
Other languages/hardware/long events require their own accuracy assessment.

## Required gates and observed results

| Gate | Result |
| --- | --- |
| Python behavior/regression suite | 21 passed; includes cancellation, retry cache, busy admission, translation boundaries, malformed input and a real watchdog process exit |
| Capture/worklet tests | 5 passed; bounded idle memory, retained overlap, failure preservation, API size cap and partial-frame flush |
| Fixed real-speech corpus | Mean word error 5.57% on nine fixed clips, below the predeclared 15% gate |
| JFK boundary regression | Exact words after punctuation/case normalization; no dropped/repeated word |
| Real-speech inference speed | Every fixed fixture processed faster than its audio duration |
| Silence, deterministic noise and 60 Hz hum | Empty caption output |
| Quiet speech | Recognizable JFK transcription at 10% original amplitude |
| Synthetic Spanish | Transcription and English translation preserve the theatre reference; stronger assertion restored |
| Native installation from locked requirements | Fresh environment setup, dependency check, imports and real inference passed |
| CPU Docker build/startup | Passed with locked dependency graph, model warmup and loopback publication |
| Offline inference | Cached model inference passed; isolated no-network fixture probe also passed |
| Browser recovery | Four attempts used identical audio/ID; manual recovery succeeded; three subsequent start/stop cycles passed |
| Editor integration | Actual sibling editor received captions through a local mock relay; no live-room publishing |
| Bilingual browser output | Original/English display and download passed; only selected English text sent to relay |
| Ten-minute browser capture | 602.8 seconds including final drain, 126 captions, no browser errors or external requests |
| Browser-run inference memory | Warm RSS 565.3–668.5 MiB; bounded variation, no growing backlog; maximum buffer 9.31 seconds |
| Sustained container inference | 250 requests, 2470 seconds of audio in 560.1 seconds wall time |
| Container memory after warmup | 584.5–585.0 MiB |
| Concurrent admission | One inference accepted, seven competing requests rejected as busy |
| Repeated request IDs | Same result returned without duplicate inference |
| Worker crash and Docker restart | Automatically recovered in 3.55 seconds, then real inference repeated |
| Dependency vulnerability audit | No known vulnerabilities reported for the locked runtime graph at test time |
| Release archive | Extracted into a separate directory; launcher and real offline inference passed; source and SHA-256 checks passed |
| AI deployment skill | Validator passed |
| Native systemd unit | Generated unit passed systemd-analyze verification; actual supervision test used Docker |

## Iteration and practical limits

The prototype's six-second hard cuts changed words. Rolling windows now retain
unfinished speech and advance at decoded word boundaries, with 500 ms of context.
The first overlap implementation still repeated one zero-duration boundary word;
a regression fix removed that duplicate without suppressing deliberate repeated
words. The JFK gate was tightened to exact normalized words and rerun successfully.

Stronger beam decoding and the small model fixed the original synthetic Spanish
“theatre” misrecognition. Translation still makes errors: one browser test rendered
“this night” as “this afternoon”. Human review remains part of the intended workflow.
The mean word-error figure is a regression result, not a general accuracy promise:
the LibriSpeech dummy subset has one reader, and the other real clip is JFK.
The Spanish voice is synthetic. Theatre acoustics, names, accents and full events
are not represented adequately by these fixtures.

One integration test was initially pointed at the service already occupied by the
API load test and received busy responses. It was rerun against an isolated
service and passed. Release tests must respect the single-operator contract.
CSP exposed a test harness that evaluated strings as JavaScript; the harness was
corrected to use functions without weakening the application's CSP.

The sustained tests ran the release inference/capture behavior. The final startup
checks additionally verify the pinned model revision, language menu metadata and
supervisor entrypoint. Runtime locking does not guarantee reproducible inference
on all architectures, and the audit reports known dependency findings only.

## Evidence and reproduction

- `quality-gate.json`: fixed references, hypotheses, error rates and inference times.
- `quiet-and-hum.json`: quiet-speech and electrical-hum results.
- `browser-soak.json`: ten-minute samples and first/last captions.
- `api-soak.json`: 250-request container run and memory samples.
- `browser-recovery.json`, `browser-translation.json`, `browser-smoke.json`.
- `release-native.json`, `release-docker.json`, `release-after-restart.json`.
- `container-restart.json`, `dependency-audit.json`.
- `archive-smoke.json`, `release-no-network.json`, `running-release.json`.

Run the commands in README.md and DEPLOYMENT.md. Sustained scripts accept a local
service URL and process ID. No test sends caption text to a real relay room.
Earlier `*deployment*.json`, benchmark notes and deployments.md are historical
prototype evidence; this file describes the Linux CPU 1.0 scope.

Windows launchers, actual NVIDIA inference, Docker Desktop/WSL2, ARM, mobile
background capture, public multi-user hosting and event-length accessibility
validation are not claimed by this release.
