# Windows CUDA browser validation

This continues the [initial GPU matrix](../gpu-validation/report.md), which
verified real decoding but could not qualify sustained capacity because unrelated
GPU jobs interrupted it. The owner authorized another isolated test window and
temporarily pausing the existing llama service. Unrelated workloads are preserved.
The checkout began at published `v1.1.0`, commit
`9b585f5749ef819dd63a938b4adf32c9c3459d56`; improvements remain on
`windows-rtx-validation` in [draft PR #1](https://github.com/steveseguin/caption-local/pull/1).

## Tested configuration and inputs

Windows 11 Pro 10.0.26200; Intel Core Ultra 7 265K, 20 cores/threads; 64 GiB installed
RAM; NVIDIA TITAN RTX, 24,576 MiB VRAM, driver 610.47. Native Python 3.12.10,
CTranslate2 4.8.2, faster-whisper 1.2.1 and Playwright 1.62.0. Microsoft Edge was
152.0.4191.62 in the initial inventory; the rotating-mode and functional probes
record 152.0.4191.66. The initial short run and hour did not record their browser
patch version, so that exact version is a reproducibility limitation. Subsequent
browser evidence now records it alongside fixture identities and per-stream modes.
Exact [Windows](software-windows.json) and [WSL](software-wsl.json) package versions
and the tested server source hash are saved separately.
The existing venv-local CUDA runtime wheels and pinned model revisions are listed
in the initial GPU report. C: had approximately 98.7 GiB free after model/runtime
installation. No drivers, system PATH, execution policy or Docker/WSL configuration
were changed.

The accuracy candidate is **large-v3, explicit CUDA float16, two workers, four
CPU threads per worker, beam five, six-second browser interval**. Each producer
has its own stream identity and retained audio. Twelve tabs repeat six synthetic
inputs: English, Spanish, French, German, Italian and Portuguese. Input loops
include clean speech, speech reduced by 26 dB, seeded Gaussian noise at 10 dB SNR,
silence and pauses. English and German tabs request both outputs; the other tabs
request source transcription. This is not twelve simultaneous translation streams.
English bilingual output reuses the transcription; only the two German tabs add
translation decoding in this particular workload.

Browser traffic to external HTTP and all WebSockets is blocked. No physical
microphone, private recording, real editor room or public caption relay is used.
The service listens only on loopback. NVIDIA monitoring records the actual
inference process, activity, VRAM and power during real HTTP/browser decoding.

## Short browser check

[Raw browser evidence](check-12/browser.json), [configuration](check-12/configuration.json),
[resource samples](check-12/monitor.json), [summary](check-12/summary.json).

Twelve streams completed 180 seconds with 483 successful requests, zero HTTP errors,
continuous readiness and complete Stop/drain. All original acceptance checks pass.
First voiced frame to first visible caption: minimum 4.557 s, median 6.299 s,
p95 8.644 s, maximum 9.013 s. Inference p95/max: 1.352/1.820 s; queue p95/max:
2.530/3.656 s. Maximum sampled audio buffer: 9.0 s. Peak monitored service RSS:
674.77 MiB; warm-median growth: 3.57 MiB. No competing compute process was observed.

These are first-caption measurements and sampled buffering, not continuous
word-aligned audience latency. The source language and English translation can
still be wrong: the short run contains noisy French text such as “Bienvenue au
PA” and a German translation fragment “Thank you for your courage” in place of
thanks for visiting tonight. Throughput success does not certify recognition.

## Sustained run

The twelve-stream run completed 3,603.6 seconds of observed capture and finished
draining after 3,611.9 seconds. **All unchanged acceptance checks pass.**
[Summary](hour-12/summary.json), [raw browser observations](hour-12/browser.json),
[configuration](hour-12/configuration.json), [NVIDIA/resource samples](hour-12/monitor.json)
and [service output](hour-12/service.log) retain the complete run.

| Measurement | Result |
| --- | --- |
| Successful requests / HTTP errors | 9,210 / 0 |
| First caption, min / median / p95 / max | 4.587 / 6.248 / 8.734 / 8.816 s |
| Inference, median / p95 / max | 0.636 / 1.321 / 1.852 s |
| Queue, median / p95 / max | 0.703 / 2.219 / 3.594 s |
| Maximum sampled per-stream audio buffer | 10.30 s |
| Peak steady-run service RSS / warm-median growth | 689.39 / 5.22 MiB |
| Mean service CPU use | 1.35 CPU cores |
| Peak sampled GPU memory / utilization / power | 4,778 MiB / 89% / 289.64 W |
| Health failures, queue timeouts, interference / monitoring errors | 0 |
| Final capture and retained-audio drain | All twelve pass |

Healthy continuous traffic did not trigger the watchdog. This establishes twelve
streams for this one-hour synthetic workload on this host; it is neither the
maximum possible GPU capacity nor a qualification for twelve fully bilingual
producers, arbitrary event audio, or continuous word-aligned caption latency.

## Heavier translation workload

The [twelve-stream rotating-mode probe](rotating-12/summary.json) **fails**.
It rotates source transcription, English translation and both outputs across the
six languages instead of selecting only English/German bilingual tabs. After
about 135 seconds, the French bilingual producer reached the unchanged
thirty-second protective limit and stopped. Five-second sampling observed a
maximum buffer of 29.24 seconds before that stop; it does not capture the exact
instant of crossing. All retained audio subsequently drained to zero.

Its 245 HTTP requests all succeeded, but continuity and requested duration failed.
Inference p95/max was 2.344/2.939 seconds; queue p95/max was 7.341/8.234 seconds.
No competing compute process was observed. This failure is evidence that the
passing lighter-mix hour must not be generalized to heavier translation traffic.

Reducing the rotating workload to [eight streams](rotating-8/summary.json) passes
180 seconds with 311 successful requests and full drain. First captions range
from 4.910 to 8.594 seconds (median 6.445); maximum sampled buffering is 8.90
seconds. Inference p95/max: 1.545/1.773 seconds; queue p95/max: 2.180/3.016 seconds.
Peak service RSS is 667.55 MiB, with 3.15 MiB warm growth. This identifies an
eight-stream starting point for the heavier mix, not an hour qualification.

The [small-model twenty-four-stream probe](small-rotating-24/summary.json) passes
180 seconds with the same rotating modes, float16, two workers and beam five:
949 successful requests, full drain, first captions 4.369–8.540 seconds (median
6.162), and maximum sampled buffering 9.46 seconds. Inference p95/max is
0.570/2.540 seconds; queue p95/max is 2.244/3.359 seconds. Peak service RSS is
684.56 MiB with 7.66 MiB warm growth. This demonstrates a short dozens-of-streams
case, not sustainable twenty-four-stream capacity. The small model's documented
recognition and translation errors remain; throughput does not erase that cost.

## Six-language robustness observations

The [condition sweep](conditions/large-v3-float16.json) records 108 real HTTP
inferences: three models, two precisions, six languages and three conditions.
Every request uses both source transcription and speech-to-English output. All
HTTP requests succeeded; recognition failures are retained rather than converted
into a new, easier quality gate. Beam five is unchanged.

| Model / precision | Mean source WER, clean | Quiet (-26 dB) | Noise (10 dB SNR) |
| --- | --- | --- | --- |
| small / float16 | 6.67% | 5.60% | 21.02% |
| small / int8_float16 | 3.33% | 5.60% | 21.02% |
| medium / float16 | 5.19% | 5.19% | 12.87% |
| medium / int8_float16 | 5.19% | 5.19% | 8.70% |
| large-v3 / float16 | 3.33% | 1.67% | 22.69% |
| large-v3 / int8_float16 | 3.33% | 3.33% | 22.69% |

These six short eSpeak sentences are not a representative speech corpus. The
unchanged lexical metric penalizes “theatre” versus “theater” and “seven” versus
“7”, so a nonzero score does not always mean lost meaning. Translation accuracy
is separate: even medium/int8_float16's exact noisy French source transcription
was accompanied by an incorrect English translation about becoming a swan.
Large-v3's noisy French source WER was 75%, and its German noise score was 30%;
small's German noise score was 70%. No model is certified for noisy live events.

Large-v3 remains the tested clean-speech accuracy-oriented configuration, supported
by the original public English corpus and this hour. Medium is worth comparing on
the actual noisy languages, but has no sustained GPU hour qualification here.
Precision changes can change words as well as memory and speed; test both outputs.

## Beam-size comparisons

The [beam matrix](beams/matrix-status.json) keeps all original quality-gate checks.
Large-v3/float16 passes with beams one and three. The fixed public English corpus
has mean WER 4.10% at beam one, 3.48% at beam three, and 4.10% at beam five in the
earlier comparison. Thus a larger beam is not an automatic accuracy improvement.
Beam three's [six-language robustness sweep](conditions-beam3/large-v3-float16.json)
still has the same noisy French/German source errors as beam five.

With two workers, the one-round twelve-task engine probes take 3.765 seconds
English / 4.531 seconds mixed at beam one, and 4.206 / 5.277 seconds at beam three.
The earlier beam-five probe took 4.317 / 5.373 seconds. These are short batches
with different public English clips and every third mixed task using Spanish
bilingual output, not the rotating browser workload. No sustained count transfers
from these timings. Beam five remains the hour-tested configuration; beams one
and three are explicit alternatives requiring workload rehearsal.

The [three-second-window large-v3 gate](quality-large-window3.json) **fails**:
the JFK transcript repeats and drops words (36.36% WER), violating its exactness
check even though every fixture decodes faster than audio. All other gate checks
remain visible in the result. Six seconds stays the tested recommendation; faster
inference alone does not justify a shorter collection interval.

The previously interrupted int8_float16 performance cells were rerun in an
[isolated matrix](quantized/matrix-status.json). Both quality gates and both
two-worker, beam-five profiles pass. Medium's twelve-task batch took 6.172 seconds
English / 7.077 seconds mixed and peaked at 1,608 MiB GPU memory; large-v3 took
5.328 / 6.584 seconds and peaked at 2,824 MiB. The corresponding float16 probes
were faster (medium 4.801–4.811 / 5.619–5.632 seconds; large-v3 4.317 / 5.373).
Quantization is therefore a measured VRAM-saving option on this TITAN RTX, not a
speed improvement. The new quantized cells are one round and do not qualify a
sustained stream count. Float32 and every supported precision/worker combination
have not been exhaustively benchmarked.

## Recovery, WSL and HTTPS preview

The [functional CUDA checks](functional/functional-configuration.json) pass with
large-v3/float16, two workers and beam five. They exercise four automatic retry
attempts with identical audio/request identity, manual recovery, three capture
restart cycles, synthetic device selection, an injected track-ended event,
Stop/drain, transcript download, bilingual/translation-only UI and a local mock
caption.ninja editor. The [real server-restart test](server-restart.json) loses a
successful inference response, restarts the owned CUDA service, and verifies the
same retained audio/request ID, one displayed caption and final drain.

These are functional passes, not translation-accuracy passes. The live Spanish
check retains incorrect fragments such as “coming to this no-” and “Welcome to
the PA” in [its raw result](functional/browser-translation.json), despite the
complete-clip quality gate passing. Physical microphones and actual room audio
remain untested.

The [WSL HTTP smoke](wsl/smoke.json) reports actual CUDA float16 with small, one
worker, four threads and beam five. English transcription takes 0.494 seconds for
11 seconds of audio; Spanish bilingual output takes 0.362 seconds and translation
alone 0.146 seconds for 5.400 seconds of audio. Silence produces no text. The
[NVIDIA samples](wsl/monitor.json) show the Linux service PID 360 using GPU memory
and activity; the [service log](wsl/service.log) records readiness and clean shutdown.
The process name is unavailable through WSL's NVIDIA query, but its PID matches.
This validates WSL decoding, not WSL sustained capacity or Docker Desktop.

The [controlled HTTPS preview](https-preview.json) now passes on Edge
152.0.4191.66: denied loopback permission blocks readiness, while granted permission
allows synthetic microphone capture and full drain. Both contexts remain secure.
The old Playwright-routing harness [still fails on that same browser version](https-preview-playwright-control.json)
when loading the worklet. Direct
[CDP Fetch interception](https://chromedevtools.github.io/devtools-protocol/tot/Fetch/)
fixes the harness without changing product assets, disabling browser security,
installing certificates or publishing a page. An intentionally blocked favicon
appears in the console. This is locally intercepted HTTPS-origin traffic with a
fake engine, not validation of a deployed public site or a physical permission prompt.

The pre-existing llama launcher was restored with exactly its original server
arguments and health HTTP 200. All temporary inference services were stopped.

Regression checks: 52 Python tests pass on [Windows](regression-windows.txt) and
[WSL](regression-wsl.txt); all eight [Node tests](regression-node.txt) pass. The new
regressions preserve an existing environment from the other operating system and
ensure a failed matrix cell causes CLI failure while retaining subsequent results.
Upstream Starlette/AnyIO deprecation warnings remain.

The launcher now refuses to reuse an environment containing the other platform's
interpreter. This prevents WSL setup in a shared checkout from overwriting the
native Windows environment. The matrix runner returns failure when any cell fails,
and preserves all attempted cells. Browser evidence now identifies each stream's
language/mode and fixtures; missing first-caption timestamps stay null instead of
being reported as a false zero-second delay. Acceptance thresholds are unchanged.

## Batching review

The installed faster-whisper 1.2.1 `BatchedInferencePipeline` stores mutable
`last_speech_timestamp` on the pipeline instance, updates it while assigning word
timestamps, and resets it after generator consumption. Its batched path also sets
`hallucination_silence_threshold=None`, unlike the current rolling-window path.
A shared pipeline is therefore not a drop-in concurrent-stream replacement.
No batching or decoder-state sharing was introduced. A future batching experiment
needs explicit per-request state, compatible task/language grouping, bounded wait,
and fresh word-boundary, cancellation, ordering, retained-retry and quality tests.

## Reproduce

Use the setup and fixtures in the [Windows guide](../../docs/WINDOWS-GPU.md).
Reserve the GPU without stopping unrelated work unless authorized, then run one
benchmark at a time from the project directory:

```powershell
.venv\Scripts\python.exe scripts/gpu_browser_run.py --model large-v3 --workers 2 --streams 12 --seconds 180 --mixed --output evidence/my-cuda-short
.venv\Scripts\python.exe scripts/gpu_browser_run.py --model large-v3 --workers 2 --streams 12 --seconds 3600 --mixed --output evidence/my-cuda-hour
.venv\Scripts\python.exe scripts/gpu_browser_run.py --model large-v3 --workers 2 --streams 8 --seconds 180 --rotate-modes --output evidence/my-cuda-rotating
.venv\Scripts\python.exe scripts/gpu_browser_run.py --model small --workers 2 --streams 24 --seconds 180 --rotate-modes --output evidence/my-cuda-throughput
.venv\Scripts\python.exe scripts/gpu_accuracy.py --output evidence/my-cuda-conditions
.venv\Scripts\python.exe scripts/gpu_matrix.py --models large-v3 --precisions float16 --beams 1 3 --workers 2 --rounds 1 --skip-cpu --output evidence/my-cuda-beams
.venv\Scripts\python.exe scripts/test_capture_page.py --functional-only --model large-v3 --device cuda --compute-type float16 --workers 2 --threads 4 --output evidence/my-cuda-functional
.venv\Scripts\python.exe scripts/browser_server_restart.py --page /capture-local.html --model large-v3 --device cuda --compute-type float16 --workers 2 --threads 4 --output evidence/my-cuda-restart.json
# No real inference or public publishing in this locally intercepted preview:
.venv\Scripts\python.exe scripts/browser_capture_https.py --output evidence/my-https-preview.json
```

The runner stops and drains if a competing GPU compute process is sampled, and
marks that benchmark failed. Five-second sampling cannot exclude every transient
or graphics-only workload. The original 2 GiB steady-run RSS and 128 MiB
warm-median-growth gates remain; startup memory is reported separately by the
engine profiler. Increasing audio buffers or reducing quality is not a remedy
for failed capacity checks.
