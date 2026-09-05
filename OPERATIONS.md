# Linux CPU operations

Native Windows CPU functional checks are also available in the
[Windows validation report](evidence/windows-rtx/report.md). Use the
[Windows commands](docs/WINDOWS-GPU.md) for that platform. These short tests do
not establish sustained GPU operation; the Linux results below remain separate.

Supported configuration: Linux x86-64, Python 3.12 or the supplied CPU Docker
image, up to twelve input sessions, Chrome/Edge capture, multilingual small model on CPU int8.
The measured host has a Ryzen 5 5500 and 32 GiB RAM. Start with at least 4 GiB RAM
and measure your machine with the release probes; this is a suggested starting
allocation, not a tested minimum. Model speed depends on CPU and language/output.

## Routine use

1. Provision the environment/model before the event; test a short recording.
2. Open localhost directly or through the documented SSH tunnel. Check the
   microphone meter, language and output mode. Download a short transcript to
   verify the end-to-end workflow.
3. Keep the capture page active and watch buffering/relay status. If the model
   cannot keep up, use transcription-only, or explicitly choose the smaller base
   model and re-evaluate accuracy. Do not increase buffers to hide accumulating delay.
4. Use Stop to drain captured speech, then download the transcript. Closing the
   tab discards unsaved text and pending audio. Nothing is persisted automatically.

## Supervision

Docker Compose already uses `restart: unless-stopped`, a readiness health check,
a 100-second stop grace period, a non-root user, dropped capabilities and a localhost
port binding. Inspect with `docker compose ps` and `docker compose logs --tail=100`.

For a native user service, provision the default environment and cached model,
then install the generated unit deliberately:

```sh
python3 deploy.py setup
python3 deploy.py download --model small
mkdir -p ~/.config/systemd/user
python3 scripts/systemd_unit.py > ~/.config/systemd/user/caption-local.service
systemctl --user daemon-reload
systemctl --user enable --now caption-local.service
journalctl --user -u caption-local.service -f
```

Stop with `systemctl --user stop caption-local.service`; remove automatic startup
with `systemctl --user disable caption-local.service`. A user service normally
requires a logged-in user manager. If unattended boot is required, configure user
lingering according to the host's administration policy. The setup script does
not enable lingering or install a service silently. The unit generator was syntax
validated; the release's actual restart test uses Docker.

The inference watchdog exits when the oldest running job exceeds 90 seconds.
A continuously busy queue does not trigger it merely because other jobs keep arriving. Docker/systemd restarts
it. A foreground launcher exits instead; rerun it. Model warmup occurs before
readiness. Pending browser audio can be retried after startup. A lost microphone
or browser audio suspension stops capture and drains already captured speech.

## Recovery

- **Network/server error:** automatic retries reuse audio and request ID. If they
  fail, use Retry pending audio after restoring the service. Discard is explicit.
- **More than 30 seconds buffered:** capture stops and drains. Reduce model cost or
  competing CPU load before starting again. Reduce the active stream count or use a faster model.
- **Relay disconnected:** caption.ninja output queues at most 100 captions. Queue
  length and dropped messages are visible. Local text remains downloadable.
  External relay delivery has no acknowledgement or guaranteed replay.
- **Wrong words at a boundary:** check the recording and sensitivity; use human
  review. This is still automatic recognition, not an exact transcription promise.
- **Port already used:** stop the previous instance or choose `--port` / CAPTION_PORT.

## Offline operation, upgrades and rollback

The default `small` model is pinned to Hugging Face revision
`536b0662742c02347bc0e980a01041f333bce120`. The throughput `base` model is pinned to
`ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`. Other models use upstream
resolution unless you supply a local model directory. The runtime graph on Linux
is pinned in `requirements-linux.lock`; Windows uses the direct requirement file
with tested versions recorded in the [Windows report](evidence/windows-rtx/report.md).
Model and audio files are excluded from the release.

Before going offline, download the selected model and run real inference once.
Native: `python3 deploy.py run --offline`. Docker: set `CAPTION_OFFLINE=1` in `.env`
and recreate the service. The release tests include inference under Docker
`--network none` using prepopulated weights.

For upgrade, save any transcript, stop capture/service, retain the previous release
archive or image, replace the application files, rerun `deploy.py setup` or rebuild
the Docker image, and run the smoke test. Keep model volumes/caches. Roll back by
restoring the previous archive/image and its matching requirements. Do not run
`docker compose down -v` unless model deletion is intended.

## Privacy and scope

Audio buffers and the bounded retry cache are in process memory. Logs contain
operational messages and errors, not transcripts/audio. Transcript downloads are
explicit. The browser confirms navigation while capture, retries or relay output
are pending, but a crashed browser cannot preserve in-memory work.

An optional shared service token and request metadata logs are described in
[deployment profiles](docs/DEPLOYMENT-PROFILES.md). Individual accounts, tenant
isolation and TLS termination are not supplied.
For remote microphones, keep the inference host on loopback and use SSH. Room
names are relay access secrets, not encryption. Do not reuse real event rooms in
tests. Windows CPU development tests are recorded separately from the published
Linux CPU release. NVIDIA inference, ARM, background mobile capture and full-event
accessibility validation remain pending.

For multiple streams, tune model, workers and threads using the [capacity report](evidence/multistream/report.md). Monitor `/health` running/pending counts and response queue times. Stop adding streams when delays grow across successive chunks. A twelve-session limit is an admission bound, not a hardware throughput guarantee.
