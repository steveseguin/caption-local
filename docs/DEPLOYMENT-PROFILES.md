# Choose hardware, quality and hosting separately

Caption Local supports native Python on Linux/Windows and supplied Linux Docker
images for CPU or NVIDIA CUDA. Use the native browser/PCM API for live capture or
the [OpenAI-style WAV subset](../API.md#openai-style-wav-api) for compatible clients.
The same caption relay messages feed caption.ninja's editor and downstream TTS.

## Starting points

These are explicit settings to evaluate, not automatic hardware capacity promises.
Read the [measured profiles](../evidence/deployment-matrix/report.md) before choosing.

| Deployment | Quality/model | Initial resource settings | Access |
| --- | --- | --- | --- |
| Small Linux VPS, 2–4 vCPUs | small, int8, beam 5; benchmark actual languages | 1 worker, 1–2 threads; start with 1 producer | Loopback plus producer SSH tunnels |
| Windows/Linux desktop CPU | small, int8, beam 5 | Test 1/2/4/8 workers; keep workers × threads within available CPU capacity | Local page or SSH |
| Multilingual translation where small loses meaning | medium or large-v3; run quality fixtures first | Fewer CPU streams, or benchmark explicit CUDA float16/int8_float16 | Same private access model |
| NVIDIA host | Explicit CUDA; small then medium/large-v3 as VRAM permits | Start 1 worker; compare 2/4; never copy a CPU worker count blindly | Native runtime wheels or GPU Docker image |
| English throughput with constrained CPU | base/beam 1 is an existing explicit alternative | Existing six-core profile: 6 workers, 1 thread | Its Spanish quality failure remains disqualifying for multilingual use |
| Several independent trusted groups | Separate service instances/ports and tokens | Budget model RAM/VRAM and benchmark aggregate host load | Separate SSH tunnels or an independently managed gateway |

One stream is one independent producer; bilingual output may require two decoding
passes. `--max-streams` (1–64) bounds admission, not inference capacity. `--workers`
(1–8), `--threads`, `--beam-size` (1–5), `--model`, `--device` and `--compute-type`
are independent explicit choices. Dozens of admitted streams can still overload
a modest host. GPU acceleration for AMD/Intel/Apple hardware is not implemented
by this backend; use explicit CPU on such hosts and validate the platform.

The browser's 3/6/9-second caption interval controls collection. Six remains the
default. Three can show captions earlier but increases request frequency and may
lose recognition context; nine delays captions and supplies more context. Pause
and Stop still flush buffered speech. Intervals do not enlarge the 30-second
protective buffer or bypass retained-audio retry behavior.

On the tested Windows CPU, a three-second interval showed a first English caption
in 4.70 seconds, but failed the existing real-time gate on a longer fixture. Keep
six seconds unless the selected hardware and languages pass both latency and
accuracy checks. Short CPU probes supported twelve transcription producers with
small/int8, eight workers and two threads; mixed transcription/translation kept
up at eight, while twelve accumulated delay. Twenty-four did not keep up. These
short measurements are not sustained capacity promises; consult the evidence
for the hour-long test status and noisy-speech failures.

## Private VPS example

On the VPS, from the repository directory:

```sh
python3 deploy.py setup
python3 deploy.py download --model small
python3 deploy.py run --offline --model small --device cpu --threads 2 --workers 1
```

On each producer computer:

```sh
ssh -N -L 8765:127.0.0.1:8765 USER@VPS
```

Open `http://localhost:8765`. This protects transport and preserves browser secure
context and the service's Host/Origin checks. Keep the VPS firewall port closed.
Docker commands remain in [deployment](../DEPLOYMENT.md); Windows commands are in
the [Windows guide](WINDOWS-GPU.md). No Docker/WSL system changes are needed for
native deployment.

## Optional shared access token

Set `CAPTION_API_KEY` to a random secret of at least 24 ASCII characters without
whitespace before starting the server. This is a local service token, not a Google,
Gemini or OpenAI account key. Empty/unset preserves trusted localhost operation.

PowerShell:

```powershell
$env:CAPTION_API_KEY = (py -3.12 -c "import secrets; print(secrets.token_urlsafe(32))").Trim()
py -3.12 deploy.py run --offline --log-requests
```

POSIX shell:

```sh
export CAPTION_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
python3 deploy.py run --offline --log-requests
```

Retain/share the token privately with authorized producers. The capture page asks
for it and holds it only in tab memory; it is cleared on reload and never forwarded
to the caption relay. API clients use `Authorization: Bearer TOKEN`. The token gates
health, model listing, inference and session deletion; the UI/static files remain
loadable so users can enter it. Restart with a new token to rotate it. Save pending
captions first: restarting loses in-memory retry caches.

This shared token provides service access control for trusted producers. It does
not provide individual accounts, per-user quotas, tenant separation or TLS. It
does not turn the service into a public SaaS endpoint. Public hosting still needs
a reviewed gateway/identity/transport design; do not disable Host/Origin checks
or publish the raw port to work around browser access restrictions.

## Operational logs

`--log-requests` or `CAPTION_LOG_REQUESTS=1` emits JSON request metadata to stdout:
fixed route template, HTTP method, status and duration. It excludes query strings,
tokens, stream/request IDs, IP addresses, filenames, audio and transcript text.
Normal startup/diagnostic lines may also appear. Logging is off by default.
Use the service supervisor's rotation/retention settings rather than unbounded
application files. Monitor `/health` for pending/running jobs, failed jobs, queue
timeouts and admission refusals. Logs help diagnose delay; they are not transcript
recordings or a complete authentication audit trail.

## Repeat the measurements

Prepare the existing English/Spanish release fixtures and run the unchanged
quality gate. Generate additional synthetic language fixtures with an existing
eSpeak NG installation:

```sh
python scripts/prepare_multilingual.py --espeak /path/to/espeak-ng
python scripts/multilingual_load.py --workers 8 --threads 2 --streams 1 2 4 8 12 24 --rounds 10 --output evidence/my-load.json
python scripts/multilingual_load.py --workers 8 --threads 2 --streams 8 12 24 --rounds 10 --mixed --output evidence/my-mixed-load.json
```

On Windows substitute `.venv\Scripts\python.exe`. For previously extracted WSL
eSpeak packages, `--wsl-espeak /absolute/linux/prefix` selects their `usr/bin` and
`usr/lib` directories. No cloud TTS is invoked. The manifest records text, voice,
speed, fixture duration and SHA256. Keep the same fixtures/configuration when
comparing hosts and preserve errors instead of dropping slow requests.

`multilingual_load.py` starts/stops its own isolated server. Run benchmarks one
at a time. Use `browser_multilingual.py` against a separately started instance for
real capture buffers and first-voiced-frame-to-first-visible-caption delay. Its
default six synthetic languages are not a population-wide accuracy evaluation.
An hour of repeated fixtures does not establish accuracy for an actual event.
