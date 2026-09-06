---
name: deploy-caption-local
description: Install, configure, and test the Caption Local transcription and speech-to-English translation service using native Python or Docker on Linux or Windows, including optional NVIDIA acceleration.
---

Locate the user's Caption Local checkout and read its README.md. Read DEPLOYMENT.md
for the selected installation method and OPERATIONS.md for supervision/upgrades.
If a checkout is missing, use https://github.com/steveseguin/caption-local.
Prefer a published release tag for event deployments; inspect existing local work
before changing an installed version. These instructions can also be followed as a
plain AI setup prompt without installing the skill.

Choose the user's requested deployment method. Otherwise use the native launcher
when Python 3.12 is installed, or Compose when Docker is already available. Keep
existing installations and model caches. The default model is multilingual `small`;
`.en` models cannot translate. Translate means **into English**, and `both` may run
two inference passes. Do not promise arbitrary target languages.

Read `docs/DEPLOYMENT-PROFILES.md` when selecting hardware/quality/hosting tradeoffs.
Optional CAPTION_API_KEY is a shared local-service token, not a provider API key;
keep it out of command arguments, logs, evidence and relay messages. Token support
does not replace SSH/TLS or provide tenant isolation. `--log-requests` records
metadata only. The OpenAI-style WAV routes are a documented subset; use the native
PCM API for rolling/bilingual capture and do not claim Google/Gemini/Realtime/TTS
protocol compatibility. Re-test quality when changing caption interval or beam size.

Use `deploy.py` or the checked-in Compose files rather than rewriting setup.
`start.sh` and `start.ps1` bootstrap the Python environment on first launch. Native
runtime/model dependencies are installed in a virtual environment; no global pip
installation is necessary. First model load requires a download. Prepare offline
operation with `deploy.py download --model MODEL`, then `run --offline`. Container
models live in the Compose named volume, independently of the host Python cache.

Use CPU by default. For NVIDIA, note that the Linux CPU release does not yet validate GPU hardware, inspect `nvidia-smi` and follow the CUDA/cuDNN or
container prerequisites in DEPLOYMENT.md. `--device cuda` is explicit and must
fail when unavailable; `--device auto` can fall back during model loading. Confirm
`/health` reports the actual device, and run inference: device discovery alone
does not validate GPU runtime libraries. Do not describe mocked GPU tests or a
CPU run in a GPU image as GPU validation.

On Windows read `docs/WINDOWS-GPU.md` and `evidence/windows-rtx/report.md` for the
tested environment and outstanding checks. Optional `requirements-windows-gpu.txt`
installs NVIDIA runtime wheels inside the venv; CUDA engine setup discovers their
DLL directories without changing system PATH. This fixes DLL discovery but is not
itself GPU inference validation. Check for unrelated GPU compute processes before
profiling; preserve them unless the user authorizes interruption. Use an isolated
process per model/precision/worker configuration and keep failed accuracy results.

Windows test commands use `.venv\Scripts\python.exe`. Browser scripts select
installed Edge/Chrome or accept `CAPTION_TEST_BROWSER`; fake microphone tests do
not authorize physical recording. Prepare the exact Spanish sentence before the
quality gate. Save evidence as UTF-8 and use the actual Uvicorn server PID for
monitoring, because the Windows venv launcher may be a separate parent process.

Keep the native bind on 127.0.0.1 and Docker's published port bound to 127.0.0.1.
The container listens on 0.0.0.0 internally solely to permit Docker forwarding.
For remote microphones, use SSH local forwarding and open localhost on the
microphone computer. Do not open a public port or turn off Host/Origin checks to
work around connection errors. Public multi-user hosting is outside this service's
current authentication/session design.

Leave caption.ninja sharing off unless requested. If requested, use the editor's
private automatic-caption room and distinguish source-language text from English
translation. Only the selected text goes to the relay; audio goes to the inference
host. Use a local/mock relay for tests, not a real room containing event captions.

For the separate self-hosted capture page, read `docs/CAPTION-NINJA-LOCAL.md`.
Prefer the bundled `/capture-local.html` on localhost or an SSH tunnel. Hosted-page
access is opt-in via an exact CAPTION_ALLOWED_ORIGINS entry and CAPTION_API_KEY;
never relax Host checks or browser security to connect. Cross-origin localhost
browser tests do not establish the public HTTPS site's local-network permission
behavior. Keep deployment/model controls server-side. Update copied captionninja
assets with `scripts/sync_capture_page.py` and verify `--check`; no runtime CDN.

Validate the chosen installation with `/health` and `scripts/smoke_api.py`, using
its public/synthetic fixtures or a user-authorized recording. For offline mode,
restart using the populated cache and recheck inference. Verify the localhost port
mapping and report the exact startup/stop commands, model, actual device, observed
transcription/translation, and untested platform limitations. Stop temporary test
instances; preserve the requested service and its model volume. Do not remove
model volumes as routine cleanup or install services at boot unless requested.

## Multiple input streams

Use a capture tab per input (or an API client with a unique X-Stream-ID). Default
capacity is twelve sessions; do not promise twelve real-time streams without a
load test on the target hardware. For CPU throughput evaluate `--model base
--workers 6 --threads 1 --beam-size 1`; the quality default remains small. Compose equivalents:
CAPTION_MODEL=base, CAPTION_WORKERS=6, CAPTION_THREADS=1, CAPTION_BEAM_SIZE=1, CAPTION_MAX_STREAMS=12.
This preset targets a six-core CPU; reduce workers on smaller hosts.
Docker preset: `docker compose -f compose.yaml -f compose.cpu-throughput.yaml up --build -d`.
Threads are per worker. Translation may double inference work. Read
`evidence/multistream/report.md`, repeat `scripts/multistream_soak.py` against an
isolated instance, and report latency, backlog and memory. Use separate editor
source rooms for separate producers. Never publish test captions to real rooms.

The CPU throughput preset is validated for English capture. It fails the supplied
Spanish transcription/translation quality checks; use the default `small` model
for multilingual work and allow fewer concurrent streams on this CPU.

Read `evidence/deployment-matrix/report.md` for newer Windows CPU measurements;
do not transfer counts between hosts or transcription and bilingual workloads.
Use `scripts/prepare_multilingual.py` and `scripts/browser_multilingual.py` for
independent synthetic capture streams; `--varied` adds quiet/noisy speech and pauses.
An admission limit is not sustainable capacity. Preserve real-time/accuracy gate
failures, including shorter caption intervals and noisy speech, in the report.

On the measured Core Ultra 7 265K Windows host, small/int8 with `--workers 8
--threads 2 --beam-size 5 --max-streams 8` passed an hour of varied six-language
browser transcription. Twelve reached the protective buffer limit after 40 minutes.
Recognition errors in noise remain; the eight-stream pass is not a general
accuracy certification or a translation capacity result. Reproduce with the
browser load script and resource monitor, then run `scripts/summarize_browser_load.py`
to retain both capture and the existing memory acceptance checks.
