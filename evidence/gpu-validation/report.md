# Native Windows CUDA validation — September 5, 2026

Real NVIDIA decoding is now verified on this host. **No sustained GPU stream count
or GPU speech-to-visible-caption delay is established yet.** Repeated GPU jobs
from the unrelated game-capture project interrupted the experiment. They were
preserved, contaminated timing cells were rejected, and the original llama service
was restored with identical model/server arguments and a successful health check.

## Hardware, software and models

- Windows 11 Pro 10.0.26200; Core Ultra 7 265K, 20 cores/threads; 64 GiB RAM.
- NVIDIA TITAN RTX, 24,576 MiB VRAM, WDDM driver 610.47. Driver installation unchanged.
- Python 3.12.10, faster-whisper 1.2.1, CTranslate2 4.8.2, NumPy 2.5.2,
  FastAPI 0.141.1, Uvicorn 0.52.4; Edge 152.0.4191.62, Playwright 1.62.0.
- Venv-local cuBLAS 12.9.2.10, NVRTC 12.9.86 and cuDNN 9.10.2.21.
  No system PATH, driver or execution-policy changes were made.
- Model revisions: small `536b0662742c02347bc0e980a01041f333bce120`,
  medium `08e178d48790749d25932bbc082711ddcfdfbc4f`,
  large-v3 `edaa852ec7e145841d8ffdb056a99866b5f0a478`.
  These named models are now pinned by the engine for repeatable downloads.

Explicit CUDA selection reports actual `cuda / float16` or `cuda / int8_float16`.
The engine decodes real public/synthetic audio while NVIDIA monitoring records GPU
utilization, VRAM and power. This is stronger than device/DLL detection. The short
capacity profiler calls the service's Engine directly; it is not an HTTP/browser soak.

WSL Ubuntu's project venv additionally received the same three Linux NVIDIA runtime
wheels. WSL CUDA inference remains untested, and no Docker Desktop installation or
Windows Docker GPU validation was performed. Earlier Linux/Windows CPU results
remain separate.

## Accuracy: unchanged supplied gate

| Model | float16 mean English WER | int8_float16 mean English WER | Gate |
| --- | --- | --- | --- |
| small | 7.37% | 6.92% | Both pass |
| medium | 5.40% | 5.34% | Both pass |
| large-v3 | 4.10% | 3.77% | Both pass |

All use beam five. The gate retains its exact JFK, mean WER <=15%, faster-than-audio,
silence/noise-empty and Spanish theatre-preservation checks. References and decoded
text are stored in the `*quality-b5.json` files under [isolated](isolated/matrix-status.json)
and [large-retry](large-retry/matrix-status.json). Some gates overlapped the foreign
GPU jobs; their text/accuracy observations remain useful, but their timing is not
an isolated performance result. No population-wide accuracy claim follows from
these fixed English fixtures and one synthetic Spanish sentence.

The six-language quiet/noisy condition sweep did not start because the GPU guard
detected another job. Smaller beams and additional precisions remain to be tested.
Known French/noise/translation errors from the prior CPU/browser evidence are not
declared fixed by these results.

## Clean short capacity probes

Each cell includes 1, 2, 4, 8 and 12 independent tasks. English inputs are different
public LibriSpeech clips, capped at six seconds. In the mixed workload, every third
task uses the supplied Spanish clip for transcription plus English translation.
Times below cover the entire twelve-request batch, including its local executor
wait; **they are not live stream capacity or audience caption delay**.

| Model / precision | Workers | 12 English tasks | 12 mixed tasks |
| --- | --- | --- | --- |
| small / CPU int8, 2 threads per worker | 8 | 5.869 s | 7.906 s |
| small / CUDA float16 | 1 | 1.909–1.915 s | 2.432–2.451 s |
| small / CUDA float16 | 2 | 1.564–1.571 s | 1.941–1.958 s |
| small / CUDA float16 | 4 | 1.895–1.900 s | 2.323–2.348 s |
| small / CUDA int8_float16 | 2 | 1.914–1.921 s | 2.495–2.531 s |
| medium / CUDA float16 | 1 | 5.045–5.081 s | 5.966–5.978 s |
| medium / CUDA float16 | 2 | 4.801–4.811 s | 5.619–5.632 s |
| medium / CUDA float16 | 4 | 5.485–5.563 s | 6.414–6.460 s |
| large-v3 / CUDA float16 | 1 | 4.604 s | 5.740 s |
| large-v3 / CUDA float16 | 2 | 4.317 s | 5.373 s |
| large-v3 / CUDA float16 | 4 | 5.084 s | 6.423 s |

GPU workers use four CPU threads each, beam five. Small/medium rows are two rounds;
large-v3 rows are one round. Every reported GPU timing row has an empty continuous
interference record. Mixed inputs differ in audio length, so compare configurations
within the same workload, not English versus mixed as equivalent audio volumes.
The CPU row does not establish whole-machine idleness beyond this isolated engine.

Large-v3/two workers loaded in 2.60 s and warmed up in 0.30 s. Its probe peaked at
4,744 MiB VRAM and 2,800 MiB host RSS during startup; late RSS samples were about
734 MiB. Startup memory is distinct from steady-state memory. A 4 GiB allocation
is not a validated minimum for a complete host plus browser/OS.

These results favor **large-v3 / float16 / two workers / beam five** as the next
accuracy candidate and **small / float16 / two workers / beam five** as the next
throughput candidate. Neither has completed the required GPU browser hour.
More workers did not improve these probes. Batching was not introduced: it is not
needed to establish a baseline, and stream ordering/retry semantics remain unchanged.

## Interference and pending work

The first [matrix](matrix-status.json) encountered a foreign FFmpeg GPU job. A
second [matrix](isolated/matrix-status.json) detected a new job during medium
int8_float16 inference; the [large-model retry](large-retry/matrix-status.json)
encountered another during int8_float16 tests. Raw failed reports/logs are retained.
Rejected/interfered timing cells are intentionally absent from the comparison table.

The profiler now detects competing GPU processes throughout a run and cancels
remaining tasks. The new GPU browser runner monitors service health, CPU, RSS,
VRAM, GPU activity and foreign compute processes. It requests Stop/drain on
interference and preserves the original acceptance checks. A
[synthetic monitor-stop test](monitor-stop-test.json) deliberately fails requested
duration while successfully draining retained audio. Summary tooling now handles
an interrupted run with no first caption without crashing or granting a pass.

Regression validation: 50 Python tests pass on native Windows and WSL Ubuntu;
eight Node buffer/worklet/transport tests pass. Source packaging, documentation
links, deployment-skill validation and the captionninja bundle comparison pass.
Upstream Starlette/AnyIO deprecation warnings remain.

The hour, full GPU browser latency/capacity, GPU service failure/restart checks,
six-language condition sweep, remaining precision/beam cells and WSL GPU decoding
need a reserved GPU window. Physical microphone rehearsal also remains unperformed;
all fixtures used here were public or synthetic.

## HTTPS preview

The [controlled preview](https-preview.json) serves page assets through Playwright
under an intercepted HTTPS origin and makes real loopback HTTP requests to a fake
engine. In Edge 152, denying `loopback-network` permission blocks readiness; granting
it in the correct browser context allows readiness. Audio worklet loading fails in
this intercepted preview, so HTTPS-origin capture remains unresolved. This is not
a deployed public-site validation; no production captions or relay publishing occurred.
Use the bundled localhost/SSH page in the meantime.

Permission behavior is browser-dependent; see the
[Chrome local-network guidance](https://developer.chrome.com/blog/local-network-access?hl=en)
and [Playwright permission API](https://playwright.dev/docs/api/class-browsercontext#browser-context-grant-permissions).

## Reproduce after reserving the GPU

Do not stop another workload without its owner's authorization. From the project
directory, with cached models and the documented fixtures:

```powershell
.venv\Scripts\python.exe scripts/gpu_matrix.py --output evidence/my-gpu-matrix
.venv\Scripts\python.exe scripts/gpu_matrix.py --models large-v3 --precisions float16 --beams 1 3 --workers 2 --rounds 1 --skip-cpu --output evidence/my-beam-matrix
.venv\Scripts\python.exe scripts/gpu_accuracy.py --output evidence/my-gpu-conditions
.venv\Scripts\python.exe scripts/gpu_browser_run.py --model large-v3 --workers 2 --streams 12 --seconds 180 --mixed --output evidence/my-gpu-smoke
# Only after evaluating the short run's quality, buffering and resource results:
.venv\Scripts\python.exe scripts/gpu_browser_run.py --model large-v3 --workers 2 --streams 12 --seconds 3600 --mixed --output evidence/my-gpu-hour
```

The GPU browser runner is prepared but has not completed an end-to-end GPU run.
It preserves the existing 2 GiB steady-run RSS and 128 MiB warm-median-growth
criteria; report failures rather than raising limits or audio buffers to pass.
