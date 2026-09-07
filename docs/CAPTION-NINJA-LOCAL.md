# Self-hosted captions with caption.ninja

Caption Local listens to a browser microphone and turns speech into text on your
own Windows or Linux computer. No paid transcription account is needed. It can
transcribe supported languages, translate speech into English, or produce both.
Models and inference stay in Caption Local; caption.ninja supplies a separate
capture page and optional text editor/overlay. Existing capture and premium pages
keep their existing behavior.

Use current Caption Local `main` and captionninja `master` source for this
integration; published v1.1.0 predates it.

## Optional private caption relay

You can also host caption delivery yourself. captionninja includes a new,
independent Node relay in `relay/`, with per-room viewing/publishing tokens,
bounded connections/queues and short-lived caption replay in RAM. Follow its
[Windows/Linux setup and private workflow guide](https://github.com/steveseguin/captionninja/blob/master/relay/README.md).

Expand **Send captions to caption.ninja → Use a private relay** to set the relay
address, caption website address, source publishing token and editor output room.
Generated editor/overlay links preserve the selected relay and exclude credentials.
The custom-relay workflow covers the separate capture page, editor and standard
overlay; other caption.ninja pages retain their existing behavior. There is no
fallback to the public relay if the private one fails.

Relay credentials are separate from the inference service token. The editor needs
the source room's viewing token and its output room's publishing token; viewers
need only the output room's viewing token. Private viewers resume missed captions
from bounded replay history, and publishers retry unacknowledged messages with
duplicate suppression. Restarting the relay clears that history; expired or lost
history produces a visible gap warning. The editor/viewer setup panel replaces
token prompts, and the editor can create a view-only OBS link. See the
[recovery tests and load results](../evidence/relay-recovery/report.md).

## Start here: use the bundled page

Follow [Getting started](GETTING-STARTED.md) for Python 3.12 installation, model
download, hardware requirements and first-run troubleshooting. Start with the
multilingual small model on CPU. NVIDIA setup is optional; read the
[Windows/GPU guide](WINDOWS-GPU.md) before selecting CUDA explicitly.

Windows PowerShell, from the Caption Local folder:

```powershell
py -3.12 deploy.py run --model small --device cpu
```

Linux, from the Caption Local folder:

```sh
./start.sh --model small --device cpu
```

Open **http://localhost:8765/capture-local.html**. This bundled page works without
caption.ninja hosting or internet access once the model is cached. It uses its own
service address; its address field is read-only to preserve the local page's
restrictive connection policy.

1. Click **Connect and check service**. Leave the token empty unless your operator
   configured one. Check the displayed model, device, language and output support.
2. Choose the microphone and spoken language. Start with the six-second interval.
3. Click **Start captions** and allow microphone access. Read a short passage.
4. Click **Stop** and wait for buffered audio to finish. Download the transcript.
5. Open **Connection and capture diagnostics** to inspect buffering, recent HTTP
   errors, server queue time and inference time. Save diagnostics for support.

Use Tab/Shift+Tab and Enter/Space for controls; fields have visible labels and
captions use a live region. Screen-reader behavior has not been independently
certified. Speech recognition can mishear names, accents and noise: review text
before relying on it for an event.

Stop the foreground service with **Ctrl+C** after all tabs finish draining. For
Compose, use `docker compose down`; retain its model volume for the next startup.

## Inference on another computer

Leave Caption Local bound to localhost on the inference host. On the microphone
computer, establish a tunnel, replacing the account and host:

```sh
ssh -N -L 8765:127.0.0.1:8765 user@inference-host
```

Open the same localhost capture URL on the microphone computer. Keep the tunnel
open until captions drain. Ctrl+C closes the tunnel. A remote Linux VPS can run
the CPU service; a Windows workstation can run native Python. Docker is optional.
Do not expose the inference port publicly as a connection workaround.

## Optional: use the separate caption.ninja page

The hosted `capture-local.html` page sends audio directly to your selected service.
It needs a shared service token, an exact allowed origin and browser permission
to reach a local service. Configure these **before** starting Caption Local:

```powershell
# PowerShell: generate a new service token for this process environment.
$env:CAPTION_API_KEY = .venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
$env:CAPTION_ALLOWED_ORIGINS = 'https://caption.ninja'
py -3.12 deploy.py run --model small --device cpu
```

```sh
# Linux shell:
export CAPTION_API_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export CAPTION_ALLOWED_ORIGINS=https://caption.ninja
./start.sh --model small --device cpu
```

Obtain the token from the server operator (or inspect the environment variable in
your own terminal) and paste it into **Service token**. It is a local-service token,
not a Google/OpenAI/Gemini key. Do not put it in URLs, screenshots, shared settings
or command-line arguments. The page clears the input after connecting and retains
the token only in tab memory. Reloading forgets it.

For Compose, put these variables in your private `.env`, then recreate the service
with `docker compose up --build -d`. `CAPTION_ALLOWED_ORIGINS` is a comma-separated
list of exact origins, without trailing slashes or paths. Wildcards and unauthenticated
cross-origin access are rejected. HTTP origins are accepted only for localhost
development. CORS does not provide user accounts, tenant isolation or rate limits.

If the browser refuses local-network access, denies microphone permission or
cannot connect, use **Open the local capture page**. Do not disable browser security.
The integration tests cover different localhost origins in Edge. A controlled
HTTPS-origin preview also passes denied/granted loopback permission, synthetic
capture and drain in Edge 152.0.4191.66, with page assets intercepted locally and
fake inference. The deployed public site's permission flow and physical microphone
remain unvalidated. HTTPS origins are
accepted by the client for deployments with their own secure reverse proxy, but
public hosting/authentication is outside this guide's tested scope.

## Sharing and downstream tools

Sharing is off by default. Captions and audio remain in memory; download text
before closing the tab. Audio is sent to the inference computer, not the relay.

To use the human editor, enter its **private automatic-caption source room** and
enable sharing. Choose original text or English text. The editor publishes approved
captions to a separate audience room. To skip review, explicitly select **Direct
overlay** and enter its room. Shared text travels through caption.ninja's public
relay; anyone with a room link may view it.

Overlay translation/TTS remain downstream features. This page does not implement
Google, Gemini or OpenAI cloud transcription/TTS protocols. Caption Local separately
offers a [documented OpenAI-style WAV subset](../API.md); native PCM capture preserves
rolling windows, retry identity and bilingual output.

## Capacity, delay and recovery

Model size, precision, worker count, language and output mode all affect capacity.
The admission limit is not a performance guarantee. The measured Windows CPU
sustained eight synthetic transcription streams for an hour with small/int8,
eight workers, two threads per worker and beam five. Twelve failed after about
40 minutes. Those measurements predate this new connection UI; see the
[integration regression results](../evidence/capture-local/report.md) and
[full deployment matrix](../evidence/deployment-matrix/report.md).

Continuous speech first accumulates approximately six seconds of audio, then
waits for decoding and an unfinished-word boundary. HTTP response duration alone
is not audience caption delay. Larger models may improve accuracy but need more
memory and processing. Noisy speech can still hallucinate. Translation/both can
require extra inference passes; benchmark the intended mix.

Temporary failures retry the same audio and request identity. After retry exhaustion,
capture stops with pending audio retained; choose Retry or deliberately Discard.
Connection changes are locked while capture or pending audio is active. A growing
buffer signals overload; the 30-second protective stop remains unchanged.

Diagnostics retain at most 100 request records in memory and exclude tokens,
addresses, room names, audio and captions. Settings export includes the service
address and capture choices; it excludes tokens, microphone identifiers and sharing.
Connect to the saved service before importing settings. Importing never connects
automatically or enables sharing. Model loading, CUDA and worker configuration
remain server-side; the browser cannot execute setup commands.

## Maintaining the shared page

Caption Local's `static/` assets are canonical. The captionninja copy is a pinned
bundle, including its relay publisher, with no runtime CDN or GitHub dependency.
From Caption Local, update and verify a separate captionninja checkout:

```sh
python scripts/sync_capture_page.py /path/to/captionninja
python scripts/sync_capture_page.py /path/to/captionninja --check
```

Commit the generated `capture-local.html`, `caption-local/` assets and SHA-256
manifest together. Preserve the MPL-2.0 license for these copied files. The existing
caption.ninja pages only gain a navigation link and load none of this bundle.
