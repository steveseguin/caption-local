# Separate self-hosted capture integration

Tested September 5, 2026 (America/Toronto).

Development branch: `windows-rtx-validation`, based on published v1.1.0
(`9b585f5749ef819dd63a938b4adf32c9c3459d56`). Captionninja checkout started at
`47ef3090ea65441fd1319ff0c40accfae5b12669`, branch `caption-local-capture`.

## Test scope

Native Windows 11 Pro 10.0.26200, Core Ultra 7 265K (20 cores/threads), 64 GiB RAM,
Python 3.12.10, Edge 152.0.4191.62, Node 22.19.0. Small model, CPU int8
(actual int8_float32), eight workers, two threads each, beam five, six-second
capture interval. TITAN RTX 24 GiB, driver 610.47, remains occupied by an unrelated
inference service: no GPU decoding or capacity claim is made here.

The real browser load tests use independent synthetic English, Spanish, French,
German, Italian and Portuguese microphone inputs, rotating clean/quiet/noisy
speech with pauses. All external HTTP is blocked and relay traffic is mocked.
Physical microphones and the public HTTPS caption.ninja local-network permission
prompt remain unvalidated. Cross-origin browser checks use two localhost origins
and a fake engine; these validate transport and UI behavior, not recognition.

## Demonstrated problem and fix

The first new-page load failed before capture when Uvicorn's 32-connection limit
counted retained asset connections from several browser contexts. Some JavaScript
requests returned 503. The prior HTML also exposed an enabled Start button before
scripts had loaded. [Failed run](failed-asset-connections.json).

Start is now disabled in HTML until readiness is confirmed. The HTTP connection
limit budgets six browser connections per admitted stream plus sixteen spare
connections (minimum 64). Inference worker/admission/queue limits and the
30-second audio protective stop are unchanged. This addresses page loading,
not model throughput; buffers were not increased to hide overload.

## Security and recovery checks

[Cross-origin browser checks](connection.json) cover wrong tokens, an unapproved
origin, successful authorized capture/drain, connection locking, private diagnostic
downloads, settings round trips, direct overlay publishing through a mock relay,
and recovery from injected microphone permission denial. Tokens are confined to
tab memory and the selected endpoint; redirects and cookies are disabled.

49 Python protocol/scheduling/security tests pass on native Windows and WSL Ubuntu.
Eight Node buffer/worklet/transport tests pass. WSL checks use fake inference and
do not establish WSL GPU support. Upstream Starlette/AnyIO deprecation warnings
remain. No public relay received synthetic captions.

The new bundled page also passes [retained-audio recovery](browser-recovery.json),
[synthetic device selection/loss/restart](browser-devices.json),
[actual caption.ninja editor integration through a mock relay](browser-smoke.json),
and [real server restart after a lost inference response](server-restart.json).
The restart test preserves the request ID and audio SHA-256 across retry and drains
successfully. A [page screenshot](local-captions.png) records the tested browser UI.

## Real CPU browser comparison

Each run captured 180 seconds with the same model/decoder and unchanged acceptance
checks. The first two use eight streams across six languages. The mixed run uses
four streams: English and German in both-output mode, Spanish and French in
transcription mode. [Machine-readable summary](summary.json).

| Page / workload | Requests / HTTP errors | First caption median / maximum | Inference p95 / maximum | Maximum buffered audio | Final buffer maximum |
| --- | --- | --- | --- | --- | --- |
| [Original, 8 transcription streams](original.json) | 309 / 0 | 7.085 / 7.836 s | 2.657 / 2.727 s | 8.86 s | 0 s |
| [Separate page, 8 transcription streams](local-page.json) | 308 / 0 | 7.101 / 7.810 s | 2.694 / 2.835 s | 8.76 s | 0.324 s |
| [Separate page, 4 mixed-output streams](mixed.json) | 161 / 0 | 6.864 / 8.641 s | 3.674 / 3.838 s | 8.90 s | 0 s |

All three pass continuous-capture and Stop/drain checks. Queue p95 is zero in each;
maximum observed queue time is 0.015 seconds on the original-page run and zero
on the other two. The small differences do not establish a performance improvement
or a statistically significant regression. First-caption timing starts at the first
voiced captured frame; it does not measure worst-case delay for every word.
Synthetic caption text, including recognition mistakes, is retained in the raw
reports. This UI change does not fix the known noisy-speech accuracy failures.

The separate Spanish translation-only capture produced “coming this afternoon”
for source speech saying “esta noche” (tonight) in one segment. This is a semantic
failure even though transport/drain passed; the raw translation output remains
in [the browser translation evidence](browser-translation.json). Functional
success must not be interpreted as a translation quality pass.

## Reproduce

Run from the project folder after preparing the public/synthetic fixtures and
downloading small as described in [the deployment matrix](../deployment-matrix/report.md):

```powershell
.venv\Scripts\python.exe scripts/sync_capture_page.py samples/captionninja
.venv\Scripts\python.exe scripts/sync_capture_page.py samples/captionninja --check
.venv\Scripts\python.exe scripts/browser_capture_connection.py
.venv\Scripts\python.exe scripts/test_capture_page.py
.venv\Scripts\python.exe scripts/browser_server_restart.py --page /capture-local.html --output evidence/capture-local/server-restart.json
.venv\Scripts\python.exe scripts/summarize_capture_page.py evidence/capture-local/original.json evidence/capture-local/local-page.json evidence/capture-local/mixed.json --output evidence/capture-local/summary.json
.venv\Scripts\python.exe -m pytest -q
node --test tests/audio-buffer.test.cjs tests/local-connection.test.cjs
```

The connection test owns ports 8778/8779, uses a fake model and serves the separate
captionninja checkout. The inference regression owns port 8772 and stops its own
service on completion/failure. Existing listeners are never replaced. Use an
isolated host for timing comparisons; do not run competing inference benchmarks.

The existing eight-stream hour pass and twelve-stream failure belong to the
[earlier sustained CPU tests](../deployment-matrix/report.md). Short integration
regressions are not a new one-hour qualification, a general language accuracy
certification or evidence of production readiness.
