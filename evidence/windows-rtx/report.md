# Windows validation checkpoint

Started from published release **v1.1.0**, commit
`9b585f5749ef819dd63a938b4adf32c9c3459d56`, published 2026-09-05 21:01:23 UTC.
Development branch: `windows-rtx-validation`. These results are a checkpoint,
not a completed GPU validation or production-readiness claim.

## Host and installation

- Windows 11 Pro 10.0.26200; Core Ultra 7 265K, 20 cores/20 threads.
- 64 GiB installed RAM (63.46 GiB visible); initially 32.49 GiB free on C:.
- NVIDIA TITAN RTX, 24,576 MiB VRAM, WDDM, driver 610.47.
- Python 3.12.10 x64; Git 2.51.0.windows.1; Node 22.19.0; Edge 152.0.4191.62.
- Ubuntu WSL2: Python 3.12.3, kernel 6.6.87.2-microsoft-standard-WSL2.
- Docker Desktop and Docker CLI absent. Existing CUDA 12.9 and 13.0 installations
  were preserved. No driver, system PATH, execution-policy or WSL changes.

[Hardware](hardware.json), [exact Windows dependency graph](requirements-windows-tested.txt),
[startup/shutdown and reproduction commands](../../docs/WINDOWS-GPU.md).
Dependencies live in `.venv` and `.venv-wsl`; downloaded fixtures remain in
ignored `samples/`, and model weights remain in the user's Hugging Face cache.

## Native Windows results

| Check | Result |
| --- | --- |
| Python protocol/scheduling/recovery tests | 26 passed |
| Node audio-buffer/worklet tests | 5 passed |
| Linux tests through WSL2 | 26 passed |
| Real WSL2 CPU decode with cached small weights | English, Spanish and English translation passed |
| Release syntax/link checks | Passed on Windows and WSL2 |
| Real small/CPU/int8 API inference | English, Spanish, translation-only, both, silence passed |
| Fixed quality gate, small/int8/beam 5 | Passed; English mean WER 7.21%; exact JFK; theatre checks; silence/noise empty |
| Edge Spanish capture + download | Passed, bilingual text and English-only mock relay |
| Browser retry recovery | Four failed attempts, identical audio/ID, manual retry, three restarts passed |
| Fake device selection/loss/change | Explicit device selected; injected ended notification drained; default-device restart passed |
| First visible caption | 7.408 s from Start with looping synthetic JFK input; includes collection and inference |
| Physical microphone | Not captured or validated |

[Unit output](unit-tests.txt), [WSL output](unit-tests-wsl.txt),
[buffer output](buffer-tests.txt), [API](smoke-cpu.json),
[quality](quality-small-cpu.json), [translation browser](browser-translation.json),
[recovery browser](browser-recovery.json), [devices browser](browser-devices.json).
The [WSL real decode](wsl-real-inference.json) exercises the Linux runtime through
WSL using the same cached weights; it is not Docker or CUDA validation.

The first-caption measurement is not word-aligned latency and does not describe
worst-case continuous-event delay. Synthetic Spanish rolling captions included
an incorrect time-of-day translation despite passing the existing theatre check;
the acceptance gate is preserved, not presented as a complete semantic assessment.

## CPU reference capacity

Small, CPU int8, one worker, four threads, beam 5. Five rounds per stream with
six-second arrivals; every third stream requests Spanish transcription plus English
translation, the others use distinct public English clips. These are short probes.

| Streams | Response p95 | Maximum scheduled-arrival lag | Responses later than 6 s |
| --- | --- | --- | --- |
| 1 | 2.281 s | 2.297 s | 0 / 5 |
| 2 | 3.547 s | 3.547 s | 0 / 10 |
| 4 | 7.375 s | 10.422 s | 8 / 20 |
| 8 | 13.984 s | 44.531 s | 37 / 40 |
| 12 (repeat) | 19.765 s | 73.406 s | 57 / 60 |

[1 stream](cpu-small-mixed-1.json), [2](cpu-small-mixed-2.json),
[4](cpu-small-mixed-4.json), [8](cpu-small-mixed-8.json), [12](cpu-small-mixed-12.json).
One and two kept up in the short probe. No hour-long sustainable count is claimed.
Four, eight and twelve accumulated backlog. The initial twelve-stream run hit
HTTP 429 on stream 2, round 4: `Inference queue deadline reached; retry pending audio`.
The initial twelve-stream failure exposed missing failure persistence in the
harness. That is fixed. The repeat completed all requests but failed to keep up;
passing request/quality/memory assertions is not a real-time capacity pass.

## Failures and fixes

- Windows browser scripts hard-coded `/usr/bin/google-chrome`: shared browser
  selection now supports installed Windows browsers and explicit overrides.
- Default locale decoding broke release checks, and locale writes corrupted
  Spanish evidence: script text I/O now specifies UTF-8.
- CPU profiler imported POSIX `resource`: process CPU measurement uses psutil.
- Watchdog regression sampled before a worker started: event synchronization
  now exercises all twelve worker transitions, accounting for Windows clock ticks.
- Pytest traversed WSL-extracted package symlinks in samples: `pytest.ini` scopes
  test discovery to the existing `tests` directory.
- Installed NVIDIA wheels alone did not make cuDNN discoverable: CUDA engine
  setup now registers environment-local DLL directories. Real DLL loading passes;
  [before/after evidence](dll-discovery.json) explicitly excludes inference.
- An initial nested-shell command synthesized only "Hola.". The quality gate
  correctly failed. [Invalid-fixture result](quality-small-cpu-invalid-fixture.json)
  is retained; generating the full sentence from a text file resolved that setup
  error. It was not a model-quality pass or a threshold change.
- A device test immediately after the failed load run hit retained idle sessions.
  It passed on a fresh server. Failed-load clients now finish and close their
  sessions before reporting failures.
- A deliberate thirteenth producer received HTTP 429. The harness now saved
  [partial failure evidence](overload-13.json), finished the other twelve clients,
  and left zero running, pending or admitted sessions afterward
  ([health](post-overload-health.json)). The 97-second twelve-stream run completed
  without a watchdog exit; hour-long continuous-operation testing remains pending.

## GPU work still blocked

At inspection, an unrelated `llama-server.exe` process, PID 16912, occupied
23,318 MiB of 24,576 MiB VRAM. It has been preserved pending permission to stop it.
The new profiler rejects occupied GPUs before loading a model. CUDA device and
precision discovery and cuDNN/cuBLAS DLL loading are the only GPU-related checks
completed; none prove real transcription. There is no recommended GPU throughput
configuration yet.

Still required after the GPU is freed: explicit CUDA readiness and real speech
with NVIDIA monitoring; small/medium/large-v3 accuracy and precision/beam/worker
matrix; CPU-vs-CUDA capacity comparisons; mixed workloads at 1/2/4/8/12 streams;
browser backlog and speech-to-visible-caption measurements; sustained operation
for at least an hour at twelve streams if capacity permits; restart/disconnect/
overload recovery on the selected GPU configuration. No batching changes have
been introduced. Existing per-stream ordering, bounded queues and retry semantics
remain in place.

Prepared model snapshots: small `536b0662742c02347bc0e980a01041f333bce120`,
medium `08e178d48790749d25932bbc082711ddcfdfbc4f`, large-v3
`edaa852ec7e145841d8ffdb056a99866b5f0a478`. Only small has been evaluated so far.
The new profiler's CPU smoke run is in [profiler evidence](profiler-cpu-smoke.json);
it validates the measurement path, not GPU sampling or sustained operation.

Temporary server processes were stopped after testing; environments, fixtures and
model caches were preserved. C: had approximately 21.86 GiB free after provisioning.
The source archive was built and inspected for portable paths and exclusion of
fixtures/environments. Nothing was merged or released.
