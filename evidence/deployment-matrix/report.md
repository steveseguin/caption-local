# Multilingual deployment measurements

Continuation of the [Windows checkpoint](../windows-rtx/report.md), on the same
Core Ultra 7 265K / Windows 11 host. CUDA remains blocked by the preserved llama
server occupying 23,318 MiB of the 24,576 MiB TITAN RTX. All timings below are real
CPU inference, not GPU results. Docker on this Windows host remains untested.

All Caption Local inference benchmarks ran sequentially. The unrelated GPU-resident
llama service was preserved. During most of the eight-stream run its sampled CPU
usage averaged 0.030 cores; aggregate GPU utilization was usually zero but included
occasional activity (not attributable to a process by this sampler). These are
measurements on the observed shared Windows host, not an otherwise idle-machine
certification. No GPU performance comparison was attempted while it was occupied.
[Background observations](browser-8-background-monitor.json).

## Method

Six eSpeak NG 1.51 fixtures: English, Spanish, French, German, Italian and Brazilian
Portuguese. Source durations range from 3.43 to 5.20 seconds. Each independent API
producer repeats its fixture every six seconds and keeps one request outstanding;
late work accumulates rather than being dropped. These fixtures contain pauses
and less than six seconds of speech per arrival, so they are not equivalent to
uninterrupted speech. The manifest, exact text and SHA256 are reproducible using
`scripts/prepare_multilingual.py`; recordings remain untracked.

The initial mixed-load policy assigns `both` to every third producer and
transcription to the others. With the fixed six-language order this selects
English and German for bilingual output. All six languages are tested separately
with `both` in the preliminary quality probe. The mixed capacity count is specific
to that assignment; it does not establish the same capacity for arbitrary
translation-language mixtures.

The existing JFK/LibriSpeech/Spanish quality gate remains separate and unchanged
at the default six-second window. More language fixtures extend the observations,
not the existing acceptance thresholds. Unicode word-error measurements retain
spelling/number differences: "theatre" versus "theater", and "seven" versus "7",
produce English word errors despite equivalent meaning.

## Short CPU load probes

All use small/int8. P95 is request-to-response time and excludes collecting speech.
Arrival lag includes accumulated producer backlog. A request success is not a
real-time capacity pass. No buffer or queue limits were enlarged to hide delay.

| Workers × threads; beam | Workload / streams | p95 response | Maximum arrival lag | Late / errors |
| --- | --- | --- | --- | --- |
| 4 × 2; 5 | Transcription / 8 | 4.203 s | 4.238 s | 0 / 0 |
| 4 × 2; 5 | Transcription / 12 | 6.346 s | 6.919 s | 20 / 0 |
| 4 × 2; 5 | Transcription / 24 | 11.348 s | 32.497 s | 108 / 0 |
| 8 × 2; 5 | Transcription / 12 | 4.667 s | 4.705 s | 0 / 0 |
| 8 × 2; 5 | Transcription / 24 | 7.857 s | 14.944 s | 94 / 0 |
| 8 × 1; 5 | Transcription / 12 | 7.593 s | 7.798 s | 20 / 0 |
| 8 × 1; 5 | Transcription / 24 | 11.918 s | 35.015 s | 112 / 0 |
| 8 × 2; 5 | Mixed / 8 | 4.415 s | 4.726 s | 0 / 0 |
| 8 × 2; 5 | Mixed / 12 | 6.004 s | 7.404 s | 9 / 0 |
| 8 × 2; 5 | Mixed / 24 | 11.057 s | 48.515 s | 222 / 0 |

Raw data: [4 workers](small-cpu-w4-t2.json), [8 workers](small-cpu-w8-t2.json),
[one thread per worker](small-cpu-w8-t1.json), [mixed](small-cpu-w8-t2-mixed.json).
The initial 4×2 and 8×2 transcription probes accidentally omitted the required
PCM Content-Type on their preliminary quality requests; those requests returned
415. Their load requests had the correct header and timings remain valid.
The harness was fixed; subsequent quality requests decode real speech correctly.
Failures were retained, not relabeled as quality passes.

Ready-after-start (including cached model load and warmup) was 2.55–2.58 seconds
for the eight-worker/two-thread small probes, and 7.14 seconds for the four-worker
medium probe. Downloads are excluded. These are observed process startup times,
not cold-disk guarantees.

With eight workers/two threads, twelve transcription API producers used a sampled
peak 1,426 MiB server RSS and averaged 10.58 CPU cores over the probe. Twenty-four
used 1,447 MiB and 15.81 cores while falling behind. The twelve mixed producers
peaked at 1,575 MiB and averaged 12.12 cores. These process measurements exclude
the browser and other applications. Actual rolling browser capture has retained
context and different request timing; its measurements below are the more direct
evidence for capture-page deployment.

## Accuracy and translation

Small/beam 1 passed the existing complete gate, with mean English WER 7.02%
([gate](quality-small-beam1.json)); small/beam 5 previously measured 7.21% on this
Windows host. This small corpus does not establish superiority of beam 1.

Small transcribed the French fixture exactly but translated its theatre reference
as "art" and changed the closing phrase. Medium preserved the theatre reference
in all six translations, including French. Some other phrasing remained imperfect,
such as Portuguese "coming" becoming "watching". Single-utterance synthetic
fixtures are not a comprehensive multilingual quality certification.

[Small multilingual results](small-cpu-w8-t2-mixed.json),
[medium multilingual results](medium-cpu-quality.json).
Medium's one English request took 5.120 s on CPU in this probe; its stronger
translation came with substantially greater processing cost. Larger models have
not been tested on CUDA yet.

The complete medium/int8/beam-five gate with four CPU threads reduced mean English
WER to 5.07%, with exact normalized JFK and all Spanish/silence/noise checks passing.
It nevertheless **failed** the unchanged real-time requirement: fixture
`1272-135031-0000` took 11.088 seconds of inference for 10.885 seconds of audio.
That failure is retained, even though the margin is small.
[Medium four-thread gate](quality-medium-cpu.json).

## Interfaces, access control and logging

The official OpenAI Python SDK 3.8.0 successfully called local WAV transcription,
plain-text output and English translation with optional bearer authentication
([SDK evidence](sdk-smoke.json)). No provider API calls or account keys were used.
The [API documentation](../../API.md#openai-style-wav-api) lists the supported
subset and rejects unsupported options explicitly. Google Speech and Gemini audio
use different request/response protocols and are not emulated.

The authenticated browser test rejected missing/wrong tokens, accepted the correct
token, captured synthetic speech and drained on Stop. The token was absent from
local/session storage, the cleared input and server logs
([browser evidence](browser-auth.json), [metadata logs](auth-server.log)). A shared
token is not tenant isolation, TLS or a public-hosting certification.

Caption.ninja's inspected revision is `47ef3090ea65441fd1319ff0c40accfae5b12669`.
Its [TTS integration](https://github.com/steveseguin/captionninja/blob/47ef3090ea65441fd1319ff0c40accfae5b12669/tts-integration.js)
passes caption text to the downstream TTS library. Caption Local continues to
publish caption text through the existing relay/editor path; it does not generate
speech audio. This keeps inference service complexity here while allowing
caption.ninja's downstream TTS provider choices.

## Real browser capture and recovery

Twelve independent Edge capture pages, distributed across the six languages,
passed 180 seconds of transcription using small/int8, eight workers, two threads
per worker and beam five. All 410 requests returned HTTP 200, maximum observed
buffer was 10.8 seconds, and every page drained on Stop. First voiced capture
frame to first visible caption ranged from 6.67 to 10.20 seconds. These are initial
caption delays, not continuous word-aligned latency measurements.
[Browser evidence](browser-12-transcribe.json), [resource samples](browser-server-monitor.json).

The same twelve-page configuration passed a separate 180-second cycle of clean,
quiet (-26 dB) and noisy (10 dB SNR, seeded Gaussian noise) speech with pauses.
Buffering briefly reached 24.86 seconds before recovering. This stresses buffering
but does not prove recognition quality: the separate condition probe found 70%
German source WER in noise, versus 10% clean. All 18 condition requests succeeded;
HTTP success must not be confused with accurate captions.
[Varied browser run](browser-12-varied.json), [condition results](conditions-small.json).

The actual caption.ninja editor received captions through a locally mocked relay;
there were no external HTTP requests or browser errors
([editor evidence](editor/browser-smoke.json)). A real service restart after a
successful response was deliberately lost preserved the browser request ID and
audio hash on retry, then completed Stop/drain
([restart evidence](browser-server-restart.json)). Earlier harness failures from
Windows port probes are retained separately; listener inspection replaced bind
and connect probes without changing service acceptance criteria.

## Caption interval tradeoff

A single English browser with the three-second interval showed its first caption
after 4.699 seconds and passed a 45-second capture/drain test. However, the complete
existing quality gate failed its faster-than-audio requirement at that interval:
one 9.24-second LibriSpeech fixture required 11.608 seconds of inference across
rolling windows. Its other checks passed, with mean English WER 6.34%. The
nine-second interval passed the complete gate, with mean English WER 6.80%.
[Three-second browser](browser-window3-single.json),
[three-second gate failure](quality-small-window3.json),
[nine-second gate](quality-small-window9.json).

The supplied 3/6/9-second interval choices preserve the same word holdback, retry
identity, Stop/drain and 30-second protective buffer. Six seconds remains default.
Three seconds is an explicit setting to benchmark, not a general CPU real-time
recommendation. None of these short samples certifies accuracy for a live event.

## Scope and remaining validation

The attempted hour-long twelve-stream varied run **failed after 2,425.74 seconds
(40.43 minutes)**. One French capture reached 30.08 seconds buffered and stopped
through the existing overload protection. All twelve pages then drained to zero
pending audio, but uninterrupted capture and the requested duration failed. This
configuration is not a sustained twelve-stream pass.

The service completed 5,826 requests with no HTTP errors, failed jobs, queue
timeouts or watchdog restart. P95 inference was 3.694 seconds, but the maximum
was 20.025 seconds; slow French results included repetitive incorrect text. P95
queue time was 1.969 seconds, maximum 3.344 seconds. Peak server RSS was 1,501 MiB,
and warm-median growth 10.62 MiB, so the memory gates passed while capture failed.
Initial caption delay ranged from 6.625 to 10.464 seconds. These averages and
initial delays do not erase the overload or recognition failures.

[Failed hour attempt](browser-12-hour-varied.json),
[summary with unchanged gates](browser-12-hour-summary.json),
[resource samples](browser-12-hour-monitor.json).

The eight-stream repeat **passed a full hour** with the same small/int8,
eight-worker, two-thread, beam-five, six-second configuration and varied fixtures.
Only producer count and admission limit were reduced. No buffers were enlarged
or recognition quality settings lowered. The mix is two English, two Spanish,
and one each French, German, Italian and Portuguese capture.

| Eight-stream hour measurement | Result |
| --- | --- |
| Capture duration / including final drain | 3,602.02 s / 3,608.65 s |
| Successful requests / HTTP errors | 6,050 / 0 |
| First speech-to-visible-caption, min / median / max | 6.355 / 7.503 / 8.196 s |
| Inference median / p95 / maximum | 2.568 / 2.990 / 14.554 s |
| Queue median / p95 / maximum | 0 / 0 / 0.016 s |
| Maximum observed per-stream buffer | 19.07 s |
| Peak server RSS / warm-median growth | 1,351.18 MiB / 4.70 MiB |
| Mean server CPU usage | 9.34 cores |
| Failed jobs / queue timeouts / watchdog restarts | 0 / 0 / 0 |
| Final pending requests | 0; all pages passed Stop/drain |

The resource monitor sampled for 3,660 seconds, including the final idle portion;
CPU mean is over that monitoring interval. The maximum final buffer was 0.088
seconds, below the unchanged 0.5-second drain allowance. Initial-caption timing
does not measure every later word's delay. Slow French results still contained
repetitive incorrect text; lower concurrency fixes this run's overload, not the
model's recognition weakness in noise.

[Eight-stream hour](browser-8-hour-varied.json),
[acceptance summary and per-stream timings](browser-8-hour-summary.json),
[resource samples](browser-8-hour-monitor.json).

Eight is the measured sustainable transcription count for this fixture mix on
this CPU, not a guarantee for uninterrupted speech, other languages, translation,
or a live event. Twelve failed; twenty-four short CPU probes also fell behind.
Use fewer streams when delay spikes or difficult audio are unacceptable, and
rehearse the exact event's languages and output modes.

The current fast regression suite passes all 38 Python tests on native Windows
and Ubuntu WSL, plus six Node audio-buffer/worklet tests. Source checks and archive
creation pass. These use fake inference where appropriate; the real inference
and browser evidence above is separate.

GitHub's native Linux real-inference workflow also passed English/Spanish and
English-translation smoke checks on this branch
([run](https://github.com/steveseguin/caption-local/actions/runs/33996255777),
[artifacts](linux-ci-inference/caption-smoke.json)). Windows and Linux fast CI pass,
including Linux CPU Docker image build and Compose validation. The initial Docker
build failed because `.dockerignore` omitted the new modules; the allowlist fix
was rerun successfully. This validates packaging, not Docker inference on Windows.

No shared batched pipeline was introduced: faster-whisper 1.2.1's
`BatchedInferencePipeline` keeps mutable `last_speech_timestamp` state, so reusing
one pipeline across independent streams would require additional isolation and
ordering work. The existing model worker pool remains in use. GPU batching benefit
has not been measured on this occupied GPU.
