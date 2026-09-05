# Deploy Caption Local

Get a release from https://github.com/steveseguin/caption-local/releases or clone
https://github.com/steveseguin/caption-local. Run commands from its extracted project
directory. Docker commands build locally from source; no prebuilt registry image
is required or currently published.

## Choose a method

| Method | Prerequisites | Start |
| --- | --- | --- |
| Linux script | Python 3.12 with venv support | `./start.sh` |
| Windows script | 64-bit Python 3.12 | `./start.ps1` in PowerShell |
| Portable Python launcher | Python 3.12 | `python deploy.py run` |
| Docker Compose CPU | Docker Engine + Compose, or Docker Desktop | `docker compose up --build -d` |
| Docker Compose NVIDIA | Docker + working NVIDIA container support | `docker compose -f compose.yaml -f compose.gpu.yaml up --build -d` |
| AI-assisted setup | An AI coding assistant with terminal access | Give it the prompt below or the bundled skill |

Open **http://localhost:8765** after model loading finishes. First startup downloads
the multilingual `small` model. CPU is the default; model weights are cached for
later runs. The microphone belongs to the browser computer. If inference runs
elsewhere, use the SSH instructions below.

## Native scripts and Python

For the tested Windows CPU setup, environment-local NVIDIA runtime provisioning,
and outstanding GPU checks, read the [Windows/GPU guide](docs/WINDOWS-GPU.md).

Linux:

```sh
./start.sh
# Keep the default multilingual model and allow automatic device selection:
./start.sh --model small --device auto
```

Windows PowerShell:

```powershell
.\start.ps1
.\start.ps1 --model small --device cuda
```

The launcher creates `.venv` and installs pinned direct dependencies only when the
virtual environment is missing. Existing environments are preserved. If an
installation was interrupted, rerun setup. If PowerShell blocks scripts, use
`py -3.12 deploy.py run` directly; changing machine execution policy is unnecessary.

For explicit setup, upgrades after pulling changes, and diagnostics:

```sh
python3 deploy.py setup
python3 deploy.py doctor
python3 deploy.py download --model small
python3 deploy.py run --model small --offline
```

On Windows substitute `py -3.12` for `python3`. The download step only provisions
weights on CPU; `run --device cuda` selects actual inference hardware. Ctrl+C
stops a native process. `--port 8770` avoids an occupied port. `--threads 4` sets
CPU inference threads. `--venv PATH` selects an alternate virtual environment.
No system FFmpeg installation is required. On Linux, a missing venv module is
usually supplied by your distribution's `python3-venv` package.

## Docker Compose

```sh
docker compose up --build -d
docker compose logs -f
# Check model readiness (first download may take several minutes):
docker compose ps
# Stop and remove the service, retaining downloaded weights:
docker compose down
```

Models persist in a named volume. `down -v` deletes them; do not use it for routine
stops. The container runs as UID 10001. No microphone passthrough is needed: your
browser sends audio to the service. Only the host's loopback port is published.

Copy `.env.example` to `.env` to set `CAPTION_MODEL`, `CAPTION_THREADS`,
`CAPTION_PORT`, or `CAPTION_OFFLINE`. After the selected model has downloaded,
set `CAPTION_OFFLINE=1` and run `docker compose up -d` again. Each model must be
cached separately. CPU and GPU variants share the same model volume. For custom
model directories, mount them explicitly and use their container path as
`CAPTION_MODEL`.

Without Compose:

```sh
docker build -t caption-local:local .
docker run -d --name caption-local --init -p 127.0.0.1:8765:8765 -v caption-local-models:/models caption-local:local
docker logs -f caption-local
docker stop caption-local
docker rm caption-local
```

Do not omit `127.0.0.1` from port publishing. The container's internal 0.0.0.0
listener is needed for Docker forwarding; it is not a public-hosting setting.

## CPU and GPU options

| Hardware | Current service support | Suggested starting point |
| --- | --- | --- |
| Intel/AMD x86-64 CPU | CPU CTranslate2 backend | `--device cpu` (default int8), model small |
| NVIDIA GPU on Linux/Windows | CUDA backend; needs drivers and runtime libraries | `--device cuda`, model base or small |
| Automatic CPU/NVIDIA choice | Selects CUDA if discovered, otherwise CPU | `--device auto`; inspect `/health` |
| Intel/AMD GPU, Apple GPU | Not implemented in this backend | CPU now; investigate whisper.cpp/OpenVINO/Vulkan/Metal separately |
| Browser WebGPU | Not implemented in this service | Future optional Transformers.js capture page |

`--compute-type auto` selects int8 on CPU and float16 on CUDA. Explicit options
include `float32`, `int8`, `float16`, and `int8_float16`; hardware support varies.
`--device cuda --compute-type int8_float16` can reduce model memory on supported
GPUs. Do not assume larger models fit every GPU; validate VRAM and sustained delay
on the intended machine. `small` is the tested release default; `base` trades accuracy for speed.

`--device cuda` fails if CUDA cannot be used. `--device auto` can fall back to CPU
when CUDA model loading raises a runtime error and precision is also auto. Errors
that first appear during actual inference still stop capture; auto mode is not a
guarantee against broken GPU libraries. The UI and `/health` report the loaded
device and requested precision. CTranslate2 may internally choose compatible
precision; use its logs when diagnosing hardware-specific conversions.

### NVIDIA with Docker (recommended GPU packaging)

On Linux install a compatible NVIDIA driver and the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
On Windows use Docker Desktop's WSL2 backend and a compatible Windows NVIDIA
driver: [Docker GPU prerequisites](https://docs.docker.com/desktop/features/gpu/).

```sh
nvidia-smi
docker compose -f compose.yaml -f compose.gpu.yaml up --build -d
docker compose -f compose.yaml -f compose.gpu.yaml logs -f
```

The GPU image contains CUDA 12.8 and cuDNN runtime libraries. It is much larger than
the CPU image. Its Compose override requests one NVIDIA GPU and forces CUDA; a
missing GPU/runtime should fail visibly. Use the same two `-f` flags for `down`.

Plain Docker equivalent:

```sh
docker build -f Dockerfile.gpu -t caption-local:gpu .
docker run -d --name caption-local-gpu --init --gpus all -p 127.0.0.1:8765:8765 -v caption-local-models:/models caption-local:gpu
```

### NVIDIA with native Python

Use the same setup script plus a working NVIDIA driver, CUDA 12 cuBLAS and cuDNN 9
runtime libraries accessible to the process. Windows also needs the Visual C++
runtime. Follow the versioned dependencies in
[faster-whisper's GPU instructions](https://github.com/SYSTRAN/faster-whisper#gpu)
when installing libraries; Python setup does not install GPU drivers or alter
system PATH. Docker bundles these libraries if you prefer to avoid native setup.

Windows can provision pinned NVIDIA runtime wheels inside the project environment
with `.venv\Scripts\python.exe -m pip install -r requirements-windows-gpu.txt`.
CUDA engine setup adds those DLL directories to its own process search path.
DLL loading has been tested on Windows; real CUDA inference is still pending.

```sh
python3 deploy.py doctor
python3 deploy.py run --device cuda --model small
```

`doctor` lists detected CUDA devices but does not prove inference works. Test real
audio and check `/health` before concluding acceleration is operational.

## Remote microphone through SSH

Run inference on the server, then run this on the microphone computer:

```sh
ssh -N -L 8765:127.0.0.1:8765 USER@SERVER
```

Open http://localhost:8765 on that computer. Its microphone audio travels through
SSH to the inference server. Browser microphone access works on localhost; opening
an arbitrary server's plain HTTP URL will not provide the same secure context.
The service has no public authentication or tenant isolation. Public multi-user
hosting needs a separate deployment design, not just an open firewall port.

## AI prompt / skill

See the [AI setup guide](docs/AI-SETUP.md) for a reusable prompt and skill usage.

Copy this into your AI coding assistant:

> Set up Caption Local from https://github.com/steveseguin/caption-local. Read DEPLOYMENT.md and
> skills/deploy-caption-local/SKILL.md. Choose the native launcher or Docker based
> on what is already installed, using CPU by default unless I request NVIDIA.
> Enable multilingual transcription and optional English translation with the
> small model. Keep the service bound to localhost and sharing off. Install the
> dependencies, download the model, start it, and test /health and real inference.
> Tell me the actual device used, how to open the microphone page, how to stop the
> service, and which platform or GPU checks you could not perform.

For an assistant that supports skills, copy the `skills/deploy-caption-local`
folder into its user skill directory, or tell it to read that SKILL.md directly.
The skill is plain Markdown and does not require an AI account to run the service.

## Verify a deployment

The repo includes an API smoke test. It uses a public English fixture, tests
silence, and can test both Spanish transcription and English translation from a
supplied Spanish WAV. Run it with the service's virtual environment:

```sh
.venv/bin/python scripts/smoke_api.py --url http://127.0.0.1:8765
# Optional repeatable Spanish synthetic fixture (espeak-ng is a test tool only):
espeak-ng -v es -s 140 -w samples/spanish.wav 'Hola. Bienvenidos al teatro. Muchas gracias por venir esta noche.'
.venv/bin/python scripts/smoke_api.py --spanish samples/spanish.wav --output evidence/my-deployment.json
```

On Windows use `.venv\Scripts\python.exe`. For a Docker-only host, install the
native test environment with `python deploy.py setup`, or test through the browser.
The script downloads the English sample only if missing; cache it before offline
tests. The synthetic Spanish assertions expect this specific theatre sentence, including its theatre reference.
For unrelated recordings, inspect actual results rather than using those assertions.

See [release evidence](evidence/release.md) and the [operations guide](OPERATIONS.md) for what was actually run.

## CPU concurrency

For several producers, on a six-core CPU, run `./start.sh --model base --workers 6 --threads 1 --beam-size 1`.
Docker equivalent: `docker compose -f compose.yaml -f compose.cpu-throughput.yaml up --build -d`.
This overlay explicitly selects base, beam size one, six workers, one thread per worker and twelve
sessions, overriding those values from the base Compose configuration.
`--threads` applies to each worker. `--max-streams` defaults to 12 (range 1–64),
`--workers` defaults to 1 (range 1–8); `--beam-size` defaults to 5 (range 1–5). The model default remains `small`.
Compose reads `CAPTION_MODEL`, `CAPTION_BEAM_SIZE`, `CAPTION_WORKERS`, `CAPTION_THREADS`, and
`CAPTION_MAX_STREAMS` from `.env`. After changing them, run `docker compose up -d`.
Download the chosen model before enabling `CAPTION_OFFLINE=1`.

Each remote producer opens its own SSH forward and capture page; each page gets
an independent stream ID. Distinct caption.ninja source rooms keep editor outputs
separate. See [capacity measurements](evidence/multistream/report.md) for CPU
tradeoffs and scripts to repeat the tests on your hardware.

The CPU throughput preset is validated for English capture. It fails the supplied
Spanish transcription/translation quality checks; use the default `small` model
for multilingual work and allow fewer concurrent streams on this CPU.
