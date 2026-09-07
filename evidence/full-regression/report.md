# Full regression review — 2026-09-07

The runnable Windows/WSL CPU, browser, API, installation and private-relay checks
passed after the fixes below. This is a scoped regression review, not a claim
that every language, device, network or event will work perfectly.

The starting commits were Caption Local `57aeeff` and captionninja `b8c9648`.
Runtime fixes were pushed directly on Caption Local `main` (`dc98290`, `ccecc17`)
and captionninja `master` (`fd921b8`, `dfcee8f`). No release was published.
Caption.ninja's main `index.html` and shared `ws-publisher.js` were unchanged.

## Test environment

- Windows 11 Pro 10.0.26200; Intel Core Ultra 7 265K, 20 logical CPUs;
  approximately 64 GiB installed RAM and 85 GiB free disk during the review.
- Python 3.12.10, Edge 152.0.4191.66, Playwright 1.62.0 and Node 22.19.0.
  Exact runtime packages: [existing environment](environment.json) and
  [fresh archive installation](archive-packages.json).
- Ubuntu WSL2 with a separate Python 3.12.3 environment; CPU inference reused
  the Windows model cache through a process-local `HF_HUB_CACHE` value.
- NVIDIA TITAN RTX, 24 GiB, driver 610.47: an existing `llama-server.exe`
  process occupied roughly 23 GiB. It was preserved. **No new GPU inference
  or GPU capacity validation was attempted during this review.**
- Docker Desktop/Engine was unavailable locally. Linux container checks run
  separately in GitHub CI; they do not validate Docker Desktop on this computer.
- Caddy 2.11.4 and existing Git OpenSSL were used for a loopback TLS test.
  No system trust-store, driver, PATH, execution-policy or WSL configuration
  changes were made. No physical microphone was recorded or public caption
  room used.

## Demonstrated failures and fixes

**Discard did not release admission capacity.** After an engine failure, the
browser retained audio correctly. However, clicking Discard cleared only its
local buffer, leaving the server session reserved until idle expiry. A second
producer received HTTP 429 even though the first operator had finished.
[Before](discard-before.json), [after](discard-after.json).

Discard now runs the same empty-drain/session-close path as a successful Stop.
The browser regression uses a generated synthetic tone, a real HTTP scheduler
with one admission slot, and a deliberately failing fake engine. It verifies
retained audio before Discard, zero idle sessions afterward, and immediate
admission of another producer on both capture pages. It also checks that stopped
capture is labelled as stopped and successful Discard clears the red error.
[Phone recovery state](discard-local-retained.png),
[phone after Discard](discard-local-cleared.png),
[desktop after Discard](discard-original-cleared.png).

**Cancelled temporary WAV requests left idle sessions behind.** Cancelling an
adapter request without an explicit stream ID while its worker was running
left one session after completion; the new test expected zero and failed before
the fix. Cleanup now defers closure until the shielded worker finishes. Running
work still holds admission, and explicit stream/request IDs retain their retry
cache. This is covered by
`test_disconnected_ephemeral_upload_releases_session_after_worker_finishes`
alongside the existing cancellation/retry tests.

**The HTTPS preview used incorrect asset MIME types.** It served CSS as
JavaScript and did not check stylesheet loading. The preview now uses MIME types
appropriate to each asset, enables `nosniff`, and checks that the capture
stylesheet is loaded. Permission-denied access remains blocked; permission-granted
capture still drains. [Earlier preview](https-before.json),
[corrected preview](https-after.json). The earlier functional pass did not prove
correct MIME handling; this was a test-harness defect, not evidence that the
deployed server served CSS incorrectly.

The new automatic Linux browser job initially failed because its environment
lacked the test helper's `psutil` dependency
([failed run](https://github.com/steveseguin/caption-local/actions/runs/34165130615)).
The job now installs the pinned test dependency. Its assertions were not relaxed.
The corrected [Linux CI run](https://github.com/steveseguin/caption-local/actions/runs/34165372769)
passed, including the real-browser discard probe, Compose validation and CPU
container build. [Windows CI](https://github.com/steveseguin/caption-local/actions/runs/34165372765)
also passed on `ccecc17`. Companion
[relay/container checks](https://github.com/steveseguin/captionninja/actions/runs/34165374880)
and [Pages deployment](https://github.com/steveseguin/captionninja/actions/runs/34165373828)
passed on `dfcee8f`.

## Regression coverage

| Check | Result and scope |
| --- | --- |
| Windows Python | 53 passed: protocol, scheduling, stream isolation, admission, watchdog, cancellation, retries, malformed uploads, API/auth and environment preservation. One dependency deprecation warning. |
| WSL Python | The same 53 tests passed. Two dependency deprecation warnings; no environment upgrade was required. |
| Caption Local JavaScript | 14 passed: audio buffering/worklet Stop, retry identity, endpoint/token confinement and bounded publishing. |
| Private relay JavaScript | 18 passed: authorization, room isolation, ACK/replay, limits, restart gaps and slow consumers. `npm audit --omit=dev` reported no known dependency vulnerabilities at test time; this is not a full security audit. |
| Real model quality | [Small/int8, beam 5, four threads](quality-small.json) passed the unchanged gate. Mean normalized English WER was 7.21%; JFK was exact; each fixture inferred faster than its duration; silence/noise were empty; Spanish/English theatre checks passed. |
| Real browser workflows | [Translation/download](browser-translation.json), [microphone selection/loss/restart](browser-devices.json), [mock human-editor sharing](browser-smoke.json), [retained retry](browser-recovery.json) passed. These use synthetic/public audio, not physical devices. |
| Actual service restart | [Response loss/restart](server-restart.json) passed using the self-hosted connection page: identical audio hash and request ID on retry, no duplicate visible lost response, successful drain. |
| Authenticated CPU service | [Native API](native-api.json), [official OpenAI SDK WAV calls](sdk-api.json), [browser token flow](browser-auth.json) and [metadata-log checks](authenticated.json) passed. No cloud API calls; no tokens or captions in request metadata logs. |
| Fresh Windows install | [Fresh archive/venv setup](archive-install.json), doctor, offline readiness, HTML/CSS/worklet delivery and [real English/Spanish/translation smoke](archive-smoke.json) passed. The cached model was reused. This tests a development source archive, not a newly published release. |
| WSL inference | [Real CPU HTTP smoke](wsl-smoke.json) passed with the existing cache explicitly selected. The initial offline attempt failed as expected when the independent WSL cache lacked the pinned revision; no fallback or duplicate download was used. |
| Private editor/viewer | [Local browser flow](private-flow.json) passed token setup, verified viewing links, human approval, isolation, Stop/drain, relay restart and terminal multilingual payload errors. Fake inference; real local Node relay. |
| Deployed pages | [Actual GitHub Pages browser flow](hosted-flow.json) passed with loopback permission granted in the isolated test browser. Deployed capture HTML, app JavaScript and CSS matched the reviewed checkout; all inference and caption sockets stayed local. |
| TLS/WSS | [Actual Caddy TLS proxy](tls.json) passed explicit CA verification, rejection of an untrusted certificate and wrong token, acknowledged publishing and caption delivery. Loopback only; no browser trust bypass. |
| Layout/navigation | [24 UI views](visual.json) and [36 guide renders](guides.json) passed overflow/image/interaction checks. Desktop and phone recovery screenshots were inspected. Guide previews use GitHub Markdown rendering with local CSS; this is not a full accessibility certification. |

Real Linux CPU smoke also passed in GitHub on the initial revision
([baseline run](https://github.com/steveseguin/caption-local/actions/runs/34163942294),
[baseline artifact](linux-ci-baseline.json)) and after the lifecycle fixes
([run on dc98290](https://github.com/steveseguin/caption-local/actions/runs/34165199623)).

## Concurrent speech captures

Three sequential 180-second CPU browser probes used multilingual `small`, int8
(backend `int8_float32`), eight workers, two threads per worker, beam five and
six-second windows. Test-service admission was twelve; the table shows the
number of active producers. The eight-producer mix was English, Spanish,
French, German, Italian and Portuguese, with a second English/Spanish producer.
Fixtures cycle clean speech, quiet speech, seeded noise and pauses.

| Page/workload | Active streams | Requests / HTTP errors | First caption min / median / max | Maximum sampled audio backlog |
| --- | ---: | ---: | --- | ---: |
| Original capture page, transcription | 8 | 312 / 0 | 5.80 / 7.21 / 7.94 s | 8.3 s |
| Self-hosted connection page, transcription | 8 | 307 / 0 | 5.74 / 7.12 / 7.86 s | 8.4 s |
| Self-hosted page, mixed outputs | 4 | 160 / 0 | 5.39 / 6.85 / 8.62 s | 10.4 s |

All completed the requested duration and drained. The mixed case had English and
German bilingual producers, plus Spanish/French transcription. English bilingual
output reuses the English decode, so this is not four independent translation
passes. Translation-only behavior was tested separately in the browser/API probes.

P95 inference was 2.77, 2.73 and 3.66 seconds respectively. Maximum inference,
including final drain requests, was 11.59, 2.84 and 3.88 seconds. Maximum queue
time was 0, 0 and 0.015 seconds. The slowest request is retained rather than
hidden behind averages. [Summary](capture-summary.json),
[original raw results](capture-original.json), [self-hosted raw results](capture-local.json),
[mixed raw results](capture-mixed.json).

These are regression probes, not a new sustained-capacity qualification. They
were run before the lifecycle fixes, which target cancellation/discard rather
than normal decoding; new-code real API, restart and targeted browser checks
followed. They do not measure every word's ongoing visible delay or certify
accuracy across the six languages. The earlier [eight-stream CPU hour and failed
twelve-stream CPU hour](../deployment-matrix/report.md) remain the sustained
reference. No buffers were enlarged and no quality settings were lowered.

## Text relay load

[Three-minute protocol-2 probe](relay-load.json): 32 independent caption producers,
100 viewers, five captions/second per producer, six synthetic text languages.
All 90,000 expected deliveries arrived, with zero errors, duplicates or gaps.
Four producer/viewer disconnect pairs were injected. P95 was 6.1 ms, p99 7.0 ms;
maximum was 2,015 ms including the intentional two-second viewer outage.
Peak combined Node RSS was 96.04 MiB; measured warm RSS growth was 0.44 MiB.

Server and simulated clients shared a Node process on loopback. This probe ran
after the speech inference tests, with no test inference service competing.
Per-IP admission was explicitly 512 because all 132 connections shared loopback.
It tests caption-text delivery, not 32 speech-recognition streams or WAN latency.

## Remaining limitations

- Real rolling Spanish translation changed **“tonight” to “afternoon”** in one
  browser result. Complete-clip translation preserved the meaning. Existing
  quality checks passed, but they do not cover every semantic detail; human
  review and an event-specific language rehearsal remain necessary. Noisy-speech
  recognition errors documented in earlier reports also remain.
- The GPU was occupied by an unrelated installation. Earlier
  [GPU hour measurements](../gpu-sustained/report.md) remain separate; neither
  device detection nor these CPU tests constitutes fresh GPU validation.
- No new hour soak, physical microphone/USB test, phone hardware test, Safari/
  Firefox certification, public-WAN TLS deployment or Docker Desktop test was
  performed. Only the documented WAV API subset is implemented; Google/Gemini,
  Realtime and TTS protocols are not interchangeable with this service.

## Reproduce and operate

Use the project's development dependencies, cached `small` model and existing
public/synthetic fixtures. Keep output separate from checked-in baselines:

```powershell
.venv\Scripts\python.exe -m pytest -q
node --test tests/audio-buffer.test.cjs tests/local-connection.test.cjs tests/relay-config.test.cjs tests/relay-publisher.test.cjs
npm.cmd --prefix samples/captionninja/relay test
.venv\Scripts\python.exe scripts/quality_gate.py small --device cpu --compute-type int8 --threads 4 --beam-size 5 --output samples/new-review/quality.json
.venv\Scripts\python.exe scripts/test_capture_page.py --output samples/new-review/capture
.venv\Scripts\python.exe scripts/browser_discard.py --output samples/new-review/discard.json
.venv\Scripts\python.exe scripts/browser_server_restart.py --page /capture-local.html --output samples/new-review/restart.json
.venv\Scripts\python.exe scripts/browser_capture_https.py --output samples/new-review/https.json
.venv\Scripts\python.exe scripts/browser_private_relay.py --output samples/new-review/private.json
node samples/captionninja/relay/soak.cjs 180 samples/new-review/relay.json 100
```

The exact additional local drivers are [authenticated checks](run_authenticated.py),
[fresh archive checks](run_archive.py) and [WSL CPU checks](run_wsl.py). They write
under ignored `samples/full-review`; use fresh output directories when repeating.
The archive driver refuses an existing installation directory. It retains that
test environment for inspection and stops only its own processes. Build the source
archive first with `scripts/package_release.py`. The WSL driver requires the cache
selection described in the [Windows/WSL guide](../../docs/WINDOWS-GPU.md#wsl2-and-docker).

On this Windows computer, start a conservative single-stream service with:

```powershell
py -3.12 deploy.py run --offline --device cpu --model small --workers 1 --threads 4 --beam-size 5
```

Open `http://localhost:8765/capture-local.html`, connect, select the microphone
and spoken language, then Start. Stop capture, wait for pending audio, download
the transcript, and press **Ctrl+C in the service terminal** to shut down.
Use the [measured profiles](../../docs/DEPLOYMENT-PROFILES.md) for more streams or
NVIDIA settings; the short probes above do not increase the recommended capacity.
