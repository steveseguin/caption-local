# Contributing

Bug reports, accessibility feedback, documentation improvements and pull requests
are welcome. For a substantial engine, protocol or public-hosting change, open an
issue describing the intended use and tradeoffs before investing heavily. There
is no guaranteed response time or event support service.

## Local development

Use Python 3.12 on Linux x86-64 for the supported baseline:

```sh
python3 deploy.py setup
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
node --test tests/audio-buffer.test.cjs
.venv/bin/python scripts/check_release.py
```

Node is needed only for buffer/worklet tests. The fast tests use fake inference;
they validate protocol, scheduling, device selection and recovery invariants, not
recognition accuracy. CI runs these checks and builds the CPU container.

## Real inference and browser tests

Models and test audio are intentionally not committed. Prepare them explicitly:

```sh
# Install espeak-ng with your distribution's package manager for synthetic Spanish.
.venv/bin/python scripts/prepare_test_fixtures.py
python3 deploy.py download --model small
.venv/bin/python scripts/quality_gate.py small
# In a separate terminal, start an isolated instance:
./start.sh --offline --port 8772
# Against that instance:
.venv/bin/python scripts/smoke_api.py --url http://127.0.0.1:8772 --spanish samples/spanish.wav
CAPTION_TEST_URL=http://127.0.0.1:8772 .venv/bin/python scripts/browser_translation.py
CAPTION_TEST_URL=http://127.0.0.1:8772 .venv/bin/python scripts/browser_recovery.py
```

Browser scripts prefer `/usr/bin/google-chrome` on Linux and installed Edge/Chrome
on Windows, then fall back to Playwright Chromium. Set `CAPTION_TEST_BROWSER` to
an explicit executable path, or install bundled Chromium with
`python -m playwright install chromium`. They use fake microphone fixtures with real browser capture. Relay
traffic is mocked locally. `browser_smoke.py` additionally needs a sibling checkout
of https://github.com/steveseguin/captionninja named `captionninja` for its editor
integration test. Do not publish test captions into real rooms.
Set `CAPTION_NINJA_CHECKOUT` to use an existing checkout elsewhere. The editor
test still mocks relay traffic; it must never send synthetic captions to a real room.

For twelve streams, follow the [capacity report](evidence/multistream/report.md).
Run performance tests separately; competing inference makes timings misleading.
For Windows, use `.venv\Scripts\python.exe` and see the
[GPU/test tooling guide](docs/WINDOWS-GPU.md). `quality_gate.py` now accepts explicit
device/precision settings; `profile_gpu.py` samples one isolated configuration
over 1/2/4/8/12 streams. Neither a short profile nor a detected device establishes
sustained GPU capacity. Keep failed quality and overload results in evidence.
The [deployment matrix](evidence/deployment-matrix/report.md) adds six-language
API/browser loads and 3/6/9-second interval comparisons. Generate its synthetic
fixtures with `scripts/prepare_multilingual.py`; use `--varied` on
`scripts/browser_multilingual.py` for reproducible quiet/noisy speech and pauses.
`scripts/smoke_compat.py` exercises the local WAV API through the official OpenAI
SDK without cloud calls. `scripts/browser_auth.py` tests the optional service token.
Use `CAPTION_TEST_OUTPUT_DIR` with the single-page browser tests or their documented
`--output` arguments where available to keep new evidence separate from release
baselines. The manually triggered GitHub inference workflow exercises real CPU
English/Spanish inference; it is not a twelve-stream capacity certification.

## Visual review

For capture, editor or setup-page changes, use the screenshot harnesses and
inspect both full-page and first-screen images. The [visual review report](evidence/visual-review/report.md)
records the checked pages, viewport sizes and limits of these checks.

```powershell
# Windows; use .venv/bin/python on Linux. Requires development dependencies.
.venv\Scripts\python.exe scripts/review_pages.py --checkout samples/captionninja --output samples/visual-review/ui
.venv\Scripts\python.exe scripts/review_guides.py --output samples/visual-review/guides
```

Both commands expect a captionninja checkout at `samples/captionninja`; the UI
command can use another location with `--checkout`. UI service responses and
relay traffic are mocked. Guide rendering requires authenticated `gh` access;
it submits public Markdown to GitHub's renderer and uses a local reading
stylesheet. It does not reproduce GitHub's surrounding interface. Refresh the
onboarding screenshot with `scripts/capture_onboarding.py` after capture changes.

## Changes worth testing

Preserve stream isolation, bounded queues, retained audio on failure, and the
separation between local processing and optional caption sharing. Tests should
exercise observable behavior, especially cancellation and overload. For audio
changes, compare complete rolling transcripts and translation meaning, not only
whether the server returned HTTP 200. Accessibility contributions should describe
the browser/assistive technology and the user-visible improvement.

Keep runtime changes separate from benchmark results where practical. Never add
models, recordings, private room names, API keys or local `.env` files to a PR.
The existing evidence uses public or synthetic fixtures; it does not establish
accuracy for all speakers and venues. Dependencies and contributions must remain
compatible with the project's MPL-2.0 license.

## Maintainer release procedure

1. Run fast tests, real small-model quality/inference tests, and relevant browser/load tests.
2. Update VERSION, server.py's version, CHANGELOG.md and the documented validation scope together.
3. Run `python scripts/check_release.py` and `python scripts/package_release.py`. Verify the archive checksum and extraction before tagging.
4. Tag the reviewed commit as `vVERSION`, push it, and confirm GitHub CI succeeds. Publish that tag's archive and SHA256SUMS as release assets.
5. Upgrade a local installation, verify real inference and recovery, and retain the previous image/archive and model cache for rollback.

Do not describe a GPU configuration as hardware-validated until it has decoded
real audio on that hardware. Do not mark a failed quality profile as passing merely
because it is faster.
