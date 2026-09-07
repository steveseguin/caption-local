# Start here: your first local captions

Caption Local listens to an audio input and turns speech into written captions.
The speech model runs on your computer, or on a private server you connect to.
You operate it through a browser. Start with one microphone and the default
settings; you can choose a larger model or add producers later.

This guide covers [requirements](#what-you-need), [installation](#install-and-open),
[first captions](#make-your-first-captions), [saving and shutdown](#save-and-stop),
and [what to expect](#set-realistic-expectations).

## What it does

- **Transcription** writes captions in the spoken language.
- **English translation** translates speech into English. You can show both the
  original transcription and English translation together.
- **Transcript download** saves the text you have collected in the current tab.
- **Optional human editing** sends caption text to the caption.ninja editor,
  where someone can correct it before sharing it with an audience.

You do not need a paid transcription account, cloud AI API key or AI assistant.
Caption.ninja is optional. Caption Local does not generate spoken audio, translate
into arbitrary target languages, or identify individual speakers. Other apps'
audio is not captured automatically: it must reach an input your browser can select.

## What you need

| Item | For a first try |
| --- | --- |
| Computer | A 64-bit Intel/AMD Windows or Linux computer. Native CPU tests cover Windows 11 and Ubuntu Linux; Linux CPU Docker is also tested. Other platforms have not been validated. |
| Installation software | Python 3.12 for native installation, or an existing Docker installation with Compose. Choose one route. Git is optional. |
| Memory and disk | Allow at least 4 GiB RAM and several GB of free disk for a first small-model trial. These are planning allowances, not guaranteed minimums. Larger models and more streams need more resources. |
| Browser | Desktop Chrome or Edge, with permission to use the microphone. |
| Audio | A microphone, USB audio interface or separately configured virtual audio input visible to the browser. |
| Internet | Needed initially for software and model downloads. Local captions can work offline afterward; optional caption.ninja sharing still needs connectivity. |
| GPU | Optional. Start with CPU. A Windows TITAN RTX passed an hour of twelve varied synthetic streams with large-v3; counts depend on language and output mix. See the [GPU guide](WINDOWS-GPU.md). |

The **model** is the downloaded speech-recognition data. The default `small`
model supports multiple languages; its name does not mean it is English-only.
The **service** is the process you leave running in a terminal. The **capture
page** is the browser tab where you select the microphone and read captions.

## Install and open

Download and extract the project archive linked from the [README](../README.md#install-and-start).
Keep the extracted folder: it contains `deploy.py`, `README.md` and `static`.
Open a terminal **inside that folder**, not inside the ZIP archive or its parent.
Copy only the commands inside the boxes below. Choose your platform's route.

Published releases and the current source can contain different features.
The access-token, caption-interval and newer Windows improvements described here
are included on `main` after v1.1.0; they are not yet in that published release.
For these features, [download and extract the current source ZIP](https://github.com/steveseguin/caption-local/archive/refs/heads/main.zip)
or use the README's Git clone command. Use the documentation included with your
copy; no new release has been published as part of this validation.

### Windows with Python

In File Explorer, open the extracted project folder and choose **Open in Terminal**
from its context menu. Use a PowerShell tab. Check for Python 3.12:

```powershell
py -3.12 --version
```

If that command is unavailable, install Python 3.12 with its Windows launcher,
then reopen the terminal. If it works, run:

```powershell
py -3.12 deploy.py run
```

This creates a project-local Python environment, installs dependencies, downloads
the small model and starts the service. It does not require changing PowerShell
execution policy. You do not need Docker, WSL or NVIDIA software for this CPU route.
See [Windows setup](WINDOWS-GPU.md) for exact tested versions and advanced settings.

### Linux with Python

In a terminal in the project folder, check Python and start:

```sh
python3 --version
python3 deploy.py run
```

Python 3.12 is the tested version; the launcher requires at least 3.12. If Python
or its `venv` component is missing, follow the distribution-specific
[installation instructions](../DEPLOYMENT.md#native-scripts-and-python).
The launcher creates the environment, installs dependencies and downloads the model.

### Existing Docker installation

Use this route if Docker and its Compose plugin already work on the inference
computer. Linux CPU containers have been tested; Docker Desktop inference on
Windows has not been validated in this work.

```sh
docker compose up --build -d
docker compose logs -f
```

This builds the service and downloads its model into a reusable Docker volume.
Press Ctrl+C to leave the log view; the container keeps running. Check readiness
with `docker compose ps`. It should report healthy after startup finishes.

### Open the capture page

The first installation and model download can take several minutes. Wait for
`Inference ready` and the server's running message, or Docker's healthy status.
Then open **http://localhost:8765** in Chrome or Edge on that computer.

Keep a native server terminal open while using captions. If startup fails, read
the error above the final message and use [troubleshooting](TROUBLESHOOTING.md).
Do not repeatedly restart a download just because it takes time.

For a server on another computer, follow the [SSH tunnel instructions](../DEPLOYMENT.md#remote-microphone-through-ssh).
The microphone stays on your browser computer; audio travels through the tunnel
to the inference computer. Do not expose the service port publicly.

## Make your first captions

1. If the page asks for a **Service access token**, enter the token supplied by
   your server operator. This is optional local access control, not a provider API key.
2. Select **Microphone** and **Spoken language**. Allow the browser's microphone
   permission prompt when it appears. Device names may become available only
   after permission is granted.
3. Choose **Transcription in the spoken language** for a first test. Leave
   sensitivity at **Normal** and caption interval at **6 seconds** where available.
4. Leave **Send caption text to caption.ninja** unchecked for local-only use.
5. Choose **Start captions** and speak a few sentences. Pause, then check the
   text. The microphone meter helps confirm input, but visible text is the real
   end-to-end check.
6. Choose **Stop** and wait for processing to finish. Try **Download transcript**
   and open the downloaded text to confirm it contains what you need.

To change microphone, language or output mode, Stop and wait for drain first.
Then change the setting and start again. To try English translation, choose
**English translation** or **Transcription and English translation**. The `small`
model supports these modes; English-only models whose names end in `.en` do not.

### Keyboard and reading access

Use Tab and Shift+Tab to move among controls, arrow keys in selection lists, and
Enter or Space to activate buttons. Expand the optional sharing section only if
you need it. Browser zoom can make controls and captions larger; use the browser's
zoom menu. Instructions here do not depend on screenshots or color alone.

The capture page labels its controls and exposes captions as a live text region,
with status and error announcements. This is not a completed screen-reader or
assistive-technology certification. Rehearse with the tools your participants use.
If live announcements are difficult to follow, the downloaded transcript provides
ordinary text for later reading. For an audience, check text size, contrast and
delay on the actual display; involve caption users in rehearsal.

## Save and stop

Choose **Stop**, wait until processing finishes, then **Download transcript**.
Save before closing or reloading the tab. Audio and captions are not automatically
archived, and a browser crash can lose pending audio and unsaved text.

- **Native Python:** press Ctrl+C in the terminal running the service.
- **Docker:** run `docker compose down` from the project folder. This preserves
  downloaded models; do not add `-v` unless you intend to delete that model volume.

To use it again, rerun the same startup command and open the page. Existing
dependencies and cached models are reused. Once setup and model download have
completed, native Windows can start without internet with:

```powershell
py -3.12 deploy.py run --offline
```

On Linux use `python3 deploy.py run --offline`. Docker has a separate cache and
offline setting; follow [offline operation](../OPERATIONS.md#offline-operation-upgrades-and-rollback).

## Set realistic expectations

**Delay:** speech is usually collected in six-second windows before processing.
On the tested Windows CPU, eight synthetic streams showed their first captions
after 6.35–8.20 seconds. Later noisy sections buffered as much as 19.07 seconds.
This is not instant transcription, and another computer or workload may be slower.
On the tested TITAN RTX, twelve streams using large-v3 showed first captions after
4.59–8.82 seconds and buffered up to 10.30 seconds during an hour. These are initial
caption delays and sampled audio buffers, not timings for every spoken word.
The three-second interval can show earlier text but failed one CPU real-time
quality check. Large-v3 on CUDA also failed the three-second exact-transcript check
by repeating and dropping words. Keep six seconds unless your chosen configuration
passes its quality tests; shorter is not automatically better.

**Accuracy:** names, accents, quiet speech, background noise and overlapping
speakers can produce wrong or repeated text. Translation may change meaning even
when the original transcription is correct. Human review and rehearsal matter.
Medium improved the tested clean-speech accuracy but costs more processing time.

**Several streams:** each independent producer uses a separate capture tab.
Eight streams passed an hour on a 20-core Core Ultra 7 265K with specifically tuned
settings; this is not the default single-worker setup or a promise for a laptop.
Twelve hit the protective buffer limit after 40 minutes. Translation needs more
work, and dozens of streams require measured capacity on suitable hardware.
With a TITAN RTX, twelve passed an hour using the larger large-v3 model, two workers
and beam five. That GPU workload includes six languages but only two non-English
bilingual producers; it does not guarantee twelve simultaneous translations.
Use [deployment profiles](DEPLOYMENT-PROFILES.md) for the tested commands and tradeoffs.

**When it falls behind:** stop unnecessary producers or use a rehearsed lighter
workload. Capture stops above thirty seconds buffered and drains captured speech.
Increasing buffers hides delay rather than increasing processing capacity.

**Privacy:** audio goes to the inference host. Optional sharing sends caption text
through caption.ninja's relay; room names should be kept private. No sharing is
needed for local captions or transcript download.

You can also **host caption delivery yourself**, including the human editor and
OBS/audience overlay. The optional [private relay guide](https://github.com/steveseguin/captionninja/blob/master/relay/README.md)
walks through Windows and Linux setup, room passwords, viewer links, and shutdown.
That small Node service carries caption text; Caption Local still does the speech
recognition. Keep the two services on one computer or separate them as needed.
Private mode never falls back to the public relay when a connection fails.

## Where to go next

- [First-event checklist and human editor](FIRST-EVENT.md): rehearse capture,
  correction and the audience display together.
- [Deployment profiles](DEPLOYMENT-PROFILES.md): VPS, CPU/GPU, quality, concurrent
  streams, optional access tokens and metadata logs.
- [Troubleshooting](TROUBLESHOOTING.md): microphone permission, startup failures,
  missing captions and growing delay.
- [Measured results and limitations](../evidence/deployment-matrix/report.md):
  exact configurations, successful tests and failures.
