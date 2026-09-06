# Windows and NVIDIA validation

For a separate caption.ninja-compatible capture page with connection diagnostics,
follow the [self-hosted capture guide](CAPTION-NINJA-LOCAL.md). It uses the same
inference settings and retained-audio protocol as the original local page.

The native Windows CPU setup and synthetic Edge capture have been exercised on
Windows 11 Pro build 26200, Python 3.12.10, Core Ultra 7 265K and 64 GiB installed
RAM. See the [test report](../evidence/windows-rtx/report.md) for exact scope.
The subsequent [deployment matrix](../evidence/deployment-matrix/report.md) adds
six-language concurrent capture, translation quality, optional authentication and
OpenAI SDK compatibility tests, with raw timing and failure evidence.
**CUDA inference and sustained GPU capacity are still pending.** The TITAN RTX
was occupied by another inference service. Detecting the device or loading DLLs
does not establish GPU inference support.

## Native setup

Run in the project directory in PowerShell. This creates a project environment;
it does not replace other Python installations or change execution policy.

```powershell
py -3.12 deploy.py setup
.\.venv\Scripts\python.exe -m pip install -r requirements-windows-gpu.txt
py -3.12 deploy.py download --model small
py -3.12 deploy.py doctor
```

The optional GPU requirements pin NVIDIA cuBLAS 12.9.2.10, NVRTC 12.9.86 and
cuDNN 9.10.2.21. Their Windows wheels install into `.venv`. The service discovers
these directories only for CUDA/auto selection and updates its own process DLL
search path. No system PATH, driver, CUDA installation, registry or execution
policy changes are needed. A compatible NVIDIA driver and Microsoft Visual C++
runtime must already be present. Tested host driver: 610.47; this is an observed
version, not an established minimum.

Start the original single-worker CPU configuration:

```powershell
py -3.12 deploy.py run --model small --device cpu --compute-type int8 --workers 1 --threads 4 --beam-size 5 --offline
```

On this 20-core host, the concurrent-transcription configuration below passed an
hour of eight varied synthetic capture streams while retaining the quality settings.
Twelve passed short clean tests
but hit the protective buffer limit after 40 minutes of varied quiet/noisy speech.
Read the deployment matrix for exact delays and recognition failures before using
it for an event; translation and noisy speech have different costs and failure modes.

```powershell
py -3.12 deploy.py run --model small --device cpu --compute-type int8 --workers 8 --threads 2 --beam-size 5 --max-streams 8 --offline
```

The runtime resolves requested CPU `int8` to `int8_float32`, now exposed separately
as `/health.actual_compute_type`. The requested setting remains in `compute_type`.

For a single accuracy-oriented stream on this host, medium with eight threads
passed the complete quality/real-time gate (5.07% mean English WER). Four threads
failed its real-time check. Medium has not passed a sustained concurrency test:

```powershell
py -3.12 deploy.py download --model medium
py -3.12 deploy.py run --model medium --device cpu --compute-type int8 --workers 1 --threads 8 --beam-size 5 --max-streams 1 --offline
```

After freeing the GPU, the explicit CUDA starting configuration to validate is:

```powershell
nvidia-smi
py -3.12 deploy.py run --model small --device cuda --compute-type float16 --workers 1 --threads 4 --beam-size 5 --offline
```

Open `http://localhost:8765`. Press **Ctrl+C in the server terminal** to shut down.
Stop browser capture and wait for drain first. If PowerShell permits scripts,
`.\start.ps1` accepts the same options; the Python command avoids policy changes.
Keep the default loopback binding. Remote producers use the
[SSH tunnel](../DEPLOYMENT.md#remote-microphone-through-ssh).

## Verify before profiling

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/prepare_test_fixtures.py --espeak C:\path\to\espeak-ng.exe
.\.venv\Scripts\python.exe scripts/smoke_api.py --url http://127.0.0.1:8765 --spanish samples/spanish.wav --output evidence/my-windows-smoke.json
```

To replay the exact tested Windows runtime and dev package versions in an isolated
environment, install `-r evidence/windows-rtx/requirements-windows-tested.txt`.

`--espeak` is needed only while `samples/spanish.wav` is missing. Use exactly
`Hola. Bienvenidos al teatro. Muchas gracias por venir esta noche.` at Spanish
voice `es`, speed 140. Existing authorized Spanish fixtures may be supplied, but
the theatre assertions require that sentence. The test run used eSpeak NG
1.51 from Ubuntu packages extracted locally under `samples/espeak-local`, invoked
through WSL2; no system package installation occurred. Passing text using `-f`
avoids PowerShell/WSL nested-quote truncation. JFK and LibriSpeech fixtures are
downloaded by the preparation script; recordings and weights stay untracked.

Inspect `/health` for `device: cuda`, then run real speech while monitoring:

```powershell
nvidia-smi --query-gpu=timestamp,name,memory.used,utilization.gpu,power.draw --format=csv -l 1
```

Stop monitoring with Ctrl+C. Confirm the inference process and activity belong to
Caption Local. Do not stop an unrelated service without its owner's authorization.
The GPU profiler refuses to start when another compute process is present.

## Reproducible tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/audio-buffer.test.cjs
.\.venv\Scripts\python.exe scripts/check_release.py
$env:CAPTION_TEST_URL = 'http://127.0.0.1:8765'
$env:CAPTION_TEST_OUTPUT_DIR = 'evidence/my-windows-run'
.\.venv\Scripts\python.exe scripts/browser_translation.py
.\.venv\Scripts\python.exe scripts/browser_recovery.py
.\.venv\Scripts\python.exe scripts/browser_devices.py
```

Browser tests select installed Edge/Chrome on Windows, keep the existing Linux
Chrome preference, and otherwise use Playwright Chromium. Override with
`$env:CAPTION_TEST_BROWSER = 'C:\path\to\chrome.exe'`. For bundled Chromium use
`.\.venv\Scripts\python.exe -m playwright install chromium`.
Browser tests use synthetic inputs and local mock relay interception. They do
not validate physical microphone wiring, USB removal or room acoustics.

Stop the server before direct model profiling. Run each configuration separately:

```powershell
.\.venv\Scripts\python.exe scripts/quality_gate.py small --device cuda --compute-type float16 --beam-size 5 --output evidence/quality-small-cuda.json
.\.venv\Scripts\python.exe scripts/profile_gpu.py --model small --device cuda --compute-type float16 --workers 1 --beam-size 5 --output evidence/profile-small-cuda.json
```

The profiler includes independent inputs at 1/2/4/8/12 streams and both English
rolling windows and mixed Spanish bilingual output. Compare multilingual small,
medium and large-v3, then beam sizes 5/1, float16/int8_float16, and workers 1/2/4
where memory permits. Re-run the unchanged quality gate for each candidate.
Its short synchronized bursts measure startup, warmup, inference, executor queue,
CPU/RAM and sampled GPU use; they do not establish sustained capacity or browser
speech-to-caption delay. The fixed quality corpus is small and mostly one reader.

Use `multistream_soak.py` and `browser_multistream.py` against an isolated server
for sustained testing. `--pid` must be the actual server PID printed by Uvicorn;
Windows venv launchers can have a parent PID that performs no inference. Save each
run to a distinct `--output` path. Failure reports retain partial observations.
Keep the existing 2 GiB RSS and 128 MiB warm-growth gates visible even when a larger
model exceeds them; a failed gate is not a capacity pass. Do not increase queues
or reduce quality silently to make twelve streams fit.

## WSL2 and Docker

The host has Ubuntu WSL2, Python 3.12.3 and kernel
6.6.87.2-microsoft-standard-WSL2. A separate `.venv-wsl` preserves the Windows
environment; Linux regression, release checks and real CPU English/Spanish decode
pass there using the cached small weights. Docker Desktop and
a Docker CLI were absent, so container inference has not been tested on this host.
No Docker/WSL configuration changes were made. WSL device discovery is not WSL
CUDA inference validation. Use the existing
[Docker GPU guide](../DEPLOYMENT.md#nvidia-with-docker-recommended-gpu-packaging)
on a host with Docker GPU support already configured.
