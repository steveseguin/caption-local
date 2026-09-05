# Caption Local 1.1 — concurrency validation

Tested September 5, 2026 on Ubuntu Linux x86-64, Ryzen 5 5500 (6 cores / 12
hardware threads), 32 GiB RAM, CPU int8. No NVIDIA hardware was available.

Twelve English input streams passed the final native/Docker scheduling and Docker
browser tests with **base, six workers, one CPU thread per worker, beam size one**.
The default remains **small, one worker, four threads, beam size five** because
it passes the stricter multilingual quality gate. Admission capacity and real-time
inference capacity are different: small does not sustain twelve on this CPU.

## Final Docker results

| Test | Result |
| --- | --- |
| Twelve Chrome capture pages | 300 seconds capture each; 307.69s including drain |
| Local caption entries | 757 across all streams |
| HTTP decode requests | 759; all 200 |
| Largest browser audio buffer | 11.31s; 30s protective stop was never reached |
| Queue + inference p95 | 2.542s |
| Longest individual inference | 3.101s |
| Sampled server peak RSS | 1047.44 MiB, sampled every 5s |
| Average server CPU | 5.60 CPU-seconds per wall-second |
| Server failures / queue timeouts / admission refusals | 0 / 0 / 0 |
| Distinct-input API test | 12 different LibriSpeech clips, 20 rounds, 240 requests |
| API p50 / p95 response time | 3.819s / 4.824s |
| Longest scheduled-arrival-to-response delay | 5.459s; no response exceeded the 6s arrival interval |
| API duration / process CPU time | 119.087s / 546.34s |

API clients deliberately reused the same request ID across distinct stream IDs;
responses remained associated with the correct stream. Repeated inputs produced
identical text within each stream. The browser used actual microphone/worklet
capture, overlapping buffers, real inference and final draining. Every page
finished without failure and retained no pending speech. No test captions were
published to a real relay. The twelve-page harness disables browser background
throttling to measure capture/inference capacity; normal browser suspension remains
an operational limit. All pages used a looping JFK fixture, so the separate
12-input API test adds diversity but is not a full theatre-event validation.

These response timings exclude collecting approximately six seconds of new audio
and the unfinished-word holdback. They are not end-to-end audience caption delay.
Warm per-minute median RSS was approximately 697, 692, 643, 643 and 672 MiB;
allocation peaks did not represent sustained growth.

Raw evidence: [browser](browser-docker-six.json), [API](sustained-docker-six-beam1.json),
[CPU/memory/queue samples](docker-monitor.json), [container health](docker-health.json).

## Iteration and failures retained

The initial fixed-clip sweep compared small/base/tiny, beam sizes 1 and 5, and
1/2/4 workers. For base beam 5, a follow-up sweep took 4.890s with four workers,
3.704s with six and 3.982s with eight for twelve six-second clips. More workers
were not always better. These are workload-specific throughput measurements.
See [initial sweep](cpu-sweep.json) and [worker sweep](cpu-extended.json).

Base with four workers/beam 5 completed a three-minute, 360-request run at 5.914s
p95, with 19 responses later than the six-second arrival interval. A three-minute
browser run passed but reached 26.39s buffered. The initial memory gate incorrectly
treated allocation swings as a leak: warm median RSS rose only 14 MiB. The revised
soak gate records samples, limits peak RSS to 2 GiB and checks warm median growth
under 128 MiB; the raw initial run remains in [sustained-base.json](sustained-base.json).

A longer Docker test with six workers/beam 5 **failed**: one stream reached the
30-second buffer bound after about 115 seconds. The app stopped capture and drained
all retained audio. This demonstrated working overload recovery but failed the
capacity gate. [Failure evidence](browser-docker-beam5-failure.json) is preserved.
Reducing beam size to one in the explicitly selected throughput preset resolved
this observed failure in the final five-minute test; it does not make capacity
independent of the input or hardware.

A mixed test with eight English streams and four Spanish streams requesting both
transcription and translation completed 360 requests with base/six workers/beam 5,
but p95 was 6.871s, 139 responses were late and maximum arrival lag was 16.328s.
All 120 Spanish translations failed the theatre-word quality check. This was
recorded with `--profile-only`, **not accepted as a translation quality pass**.
See [mixed workload](mixed-base-six.json) and [original quality failure](base-translation-quality-failure.log).

## Accuracy

The fixed English regression corpus uses JFK plus the first eight LibriSpeech
fixture recordings over eight seconds, decoded with rolling windows. It is a
small, largely single-reader corpus, not a population accuracy estimate.

| Configuration | Mean English word error | Exact JFK | Spanish transcription/translation theatre checks |
| --- | --- | --- | --- |
| small, beam 5 (default) | 5.57% | Pass | Pass / Pass |
| base, beam 5 | 9.35% | Fail | Pass / Fail |
| base, beam 1 (throughput preset) | 9.98% | Pass | Fail / Fail |

All three passed silence/noise suppression and the mean-English-WER threshold;
only small passed the complete quality gate. Use small for multilingual capture
and English translation, with fewer concurrent streams on this host. No automatic
model downgrade or hard-coded transcript correction was introduced.
Raw results: [small](quality-small.json), [base/5](quality-base.json), [base/1](quality-base-beam1.json).

## Scheduling and recovery

Each stream has one outstanding upload/queued/running job and its own bounded
retry cache. Default admission limit is twelve streams; the worker semaphore
queues independent jobs FIFO. Uploads have a ten-second deadline and 768,000-byte
limit; queued jobs expire after twenty seconds without running inference.
Clients retain pending audio for retry. Closing an idle stream frees its slot;
otherwise idle sessions expire after 120 seconds. Stream IDs are not credentials.

A disconnected HTTP request does not release the running worker early. Background
tasks are retained and drained during shutdown. Watchdog timing follows the oldest
actual running inference, so continuous healthy traffic does not trigger restart.
Health exposes workers, beam size, pending/running counts, rejected admissions,
queue expirations and successful/failed inference totals.

26 Python tests and five buffer/worklet tests pass, including twelve-stream
isolation, same-stream busy refusal, thirteenth-stream refusal, queue expiry,
failed upload cleanup, busy-session close refusal, cache limits, disconnect retry,
continuous-load watchdog bookkeeping, real watchdog exit and mocked CUDA fallback.
[Python output](unit-tests.txt), [buffer output](buffer-tests.txt).

## Reproduce and deploy

```sh
# Quality default, including multilingual transcription and speech -> English:
./start.sh --offline

# Six-core CPU throughput preset for English streams:
./start.sh --model base --workers 6 --threads 1 --beam-size 1
# Docker equivalent (provisions base if not already cached):
docker compose -f compose.yaml -f compose.cpu-throughput.yaml up --build -d

# In an environment with requirements-dev.txt and the documented fixtures:
.venv/bin/python scripts/profile_concurrency.py --extended
.venv/bin/python scripts/browser_multistream.py --url http://127.0.0.1:8772 --seconds 300
.venv/bin/python scripts/multistream_soak.py --url http://127.0.0.1:8772 --pid SERVER_PID --rounds 20
```

Start an isolated test instance on 8772 before the test commands. Do not run
performance tests concurrently: competing inference distorts capacity. The browser
script uses system Google Chrome on Linux. Fixture provisioning is in DEPLOYMENT.md
and quality_gate.py. Windows/NVIDIA scripts remain unvalidated on real hardware.
Native launcher configuration is recorded in [native health](native-launcher-health.json).

The implementation uses faster-whisper's model worker pool, not shared mutable
batched-pipeline state. See the primary [CTranslate2 threading documentation](https://opennmt.net/CTranslate2/parallel.html)
and [faster-whisper constructor](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py).
All caption.ninja source files remain unchanged; this is a separate local repository.

Final quality-default deployment checks also passed against the rebuilt image:
real English/Spanish inference, a real Spanish browser microphone with bilingual
local output and English-only mock relay output, the actual caption.ninja editor
through a local mock relay, and four failed attempts followed by manual recovery
with identical audio/request IDs plus three start/stop cycles. Evidence:
[API smoke](default-smoke.json), [browser translation](functional/browser-translation.json),
[editor integration](functional/browser-smoke.json), [recovery](functional/browser-recovery.json).
The local Compose service was upgraded to 1.1 with the unchanged small/CPU/int8
quality configuration. The twelve-stream CPU preset is an explicit alternative.
