# Caption Local

**Live captions on your own computer, with optional human editing through caption.ninja.**

Caption Local turns microphone audio into text using a locally running speech model.
Open its capture page in a browser, choose a microphone, and start captions. Use the
text locally, download a transcript, or send it to the caption.ninja editor for a
person to correct before publishing to OBS, a venue screen, phones, or a webpage.

You do not need an API key, a paid transcription account, or an AI assistant.
The project is open source and runs independently of caption.ninja.

## What to expect

- **Transcription:** captions in the language being spoken.
- **Translation:** speech translated **into English**, or original captions and English together. Other translation targets are not included.
- **Local processing:** audio is processed on the machine running the service. Sharing with caption.ninja is off by default; enabling it sends caption text through its relay.
- **A few seconds of delay:** continuous speech is normally collected in roughly six-second windows before processing. Human review adds more time.
- **Automatic captions need review:** names, accents, overlapping voices and noisy rooms can produce mistakes. Rehearse with your actual event audio.
- **No automatic recording:** audio and text are held in memory. Use Stop, let pending captions finish, then download your transcript before closing the tab.

**Release scope:** Linux x86-64 CPU is tested with native Python and Docker.
Windows launchers and NVIDIA GPU configurations are supplied but have not been
validated on that hardware. Twelve simultaneous English streams passed a
five-minute CPU test with the faster preset; that is not a promise of twelve
accurate multilingual streams on any computer. [Read the measurements and limits](evidence/multistream/report.md).

**Windows development validation:** native Python and synthetic Edge capture now
pass on Windows 11 with the small CPU model. NVIDIA inference and sustained GPU
capacity remain pending. [Windows setup and exact test scope](docs/WINDOWS-GPU.md).

## What you need

| Requirement | Details |
| --- | --- |
| Inference computer | An Intel/AMD 64-bit Linux computer for the validated configuration. Ubuntu with Python 3.12 is the tested native environment. |
| Installation method | Python 3.12 with venv support **or** Docker with the Compose plugin. Docker does not require host Python. |
| Memory and storage | Start with at least 4 GiB RAM and several GB of free disk for one stream; these are planning allowances, not tested minimums. The twelve-stream test host had a six-core Ryzen 5 5500 and 32 GiB RAM. |
| Browser and audio | A current desktop Chrome or Edge browser and a microphone/audio input visible to it. Chrome was exercised by the automated browser tests. |
| Initial internet access | Needed to install dependencies and download a speech model. Later operation can be offline once the selected model is cached. |
| Remote use | SSH access to the inference computer. Each producer opens the capture page through a local SSH tunnel. |

A GPU is optional. No system FFmpeg installation is needed for normal use.
This is a local/trusted-producer service, not a public website with user accounts.

## Install and start

[Download the latest release](https://github.com/steveseguin/caption-local/releases/latest)
and extract it, or use Git:

```sh
git clone https://github.com/steveseguin/caption-local.git
cd caption-local
```

Run the following commands **inside the extracted or cloned project folder**.
Choose one installation method.

### Option 1: Linux script

```sh
./start.sh
```

The script creates a local Python environment, installs dependencies and downloads
the default `small` speech model. If Python's venv support is missing, follow the
[Linux setup instructions](DEPLOYMENT.md#native-scripts-and-python).

Wait for the server to report that it is ready, then open **http://localhost:8765**.
Keep the terminal open while using captions. Press **Ctrl+C** to stop the server.

### Option 2: Docker

```sh
docker compose up --build -d
docker compose logs -f
```

The first build and model download can take several minutes. Open
**http://localhost:8765** when `docker compose ps` shows the service is healthy.
Ctrl+C exits the log view; the service continues running in the background.

```sh
docker compose down
```

This stops the service and keeps downloaded models for next time. Do not add `-v`
unless you intend to delete the model cache. No microphone passthrough is needed.

### Other installation options

| Option | Instructions |
| --- | --- |
| Windows script — not hardware-validated | Run `.\start.ps1`, or `py -3.12 deploy.py run`. [Windows and native setup](DEPLOYMENT.md#native-scripts-and-python) |
| NVIDIA GPU — not hardware-validated | [GPU requirements and Docker/native commands](DEPLOYMENT.md#cpu-and-gpu-options) |
| Linux server, microphone on another computer | [SSH tunnel guide](DEPLOYMENT.md#remote-microphone-through-ssh) |
| Install with an AI assistant | [Copy-and-paste setup prompt and deployment skill](docs/AI-SETUP.md) |
| Offline use or automatic restart | [Operations guide](OPERATIONS.md) |

## Your first captions

1. Open the local capture page and select your microphone and spoken language.
2. Choose transcription, English translation, or both. Start with the default `small` model, especially for multilingual use.
3. Click **Start captions**, speak a few sentences, and check the text and microphone meter.
4. To use human review, follow the [caption.ninja editor walkthrough](docs/FIRST-EVENT.md#send-captions-for-human-review). Use a separate editor source room for each producer.
5. Click **Stop**, wait for pending speech to finish, and download the transcript if you want to keep it.

[The first-event guide](docs/FIRST-EVENT.md) covers rehearsal, audio routing,
producer/editor roles, and what to do if captions fall behind.

## Several microphones or producers

[Deployment profiles](docs/DEPLOYMENT-PROFILES.md) explain CPU VPS, Windows/NVIDIA,
model quality, caption interval, optional access tokens and operational logging.
[API compatibility](API.md#openai-style-wav-api) includes an OpenAI-style WAV subset;
caption.ninja integration continues through its caption relay/editor.

Each capture tab has its own microphone selection, transcript, retry buffer and
stream ID. Independent producers can connect to the same inference service through
separate SSH tunnels. The service admits up to twelve stream sessions by default;
your CPU, chosen model and translation workload determine how many keep up.

For **English throughput on a six-core CPU**, an explicit faster preset is available:

```sh
./start.sh --model base --workers 6 --threads 1 --beam-size 1
# Or use Docker:
docker compose -f compose.yaml -f compose.cpu-throughput.yaml up --build -d
```

This preset passed twelve simultaneous English browser captures, but **failed the
Spanish quality checks**. The normal `small` default passes those checks and needs
more processing time. Use fewer streams for multilingual work on this CPU, or
validate stronger hardware. Do not switch models during a live event without rehearsal.

[Capacity results](evidence/multistream/report.md) explain response times, accuracy,
queue limits and the failed tests that informed this preset.

## Guides and help

| I want to… | Read |
| --- | --- |
| Prepare an event and use the human editor | [First event](docs/FIRST-EVENT.md) |
| Install, configure hardware, or connect remotely | [Deployment](DEPLOYMENT.md) |
| Fix a problem | [Troubleshooting](docs/TROUBLESHOOTING.md) |
| Run unattended, upgrade, or roll back | [Operations](OPERATIONS.md) |
| Ask an AI assistant to install it | [AI setup](docs/AI-SETUP.md) |
| Send audio from my own application | [HTTP audio API](API.md) |
| Check exactly what was tested | [Version 1.1 validation](evidence/multistream/report.md) |
| Report a bug or contribute accessibility improvements | [Contributing](CONTRIBUTING.md) |

Use [GitHub issues](https://github.com/steveseguin/caption-local/issues) for bugs and
feature requests. Reproduce with a short, shareable example when possible; do not
post private event audio, credentials, or caption room names.

## License

[MPL-2.0](LICENSE). The included WebSocket publisher comes from
[caption.ninja](https://github.com/steveseguin/captionninja). Dependencies and model
weights retain their own licenses. Model weights and test audio are downloaded
separately and are not bundled in source releases.
