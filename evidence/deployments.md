# Deployment validation — 2026-09-05

Host: Linux x86-64, Ryzen 5 5500, 32 GiB RAM. Docker Engine 29.1.3,
Compose 2.37.1. Python 3.12, faster-whisper 1.2.1, CTranslate2 4.8.2.
No usable NVIDIA GPU. The current default model is multilingual `base`.

| Check | Result |
| --- | --- |
| Native bootstrap into a fresh `.venv-deploy` | Passed; dependencies installed, pip check and runtime imports passed |
| Bash launcher from outside the repository | Passed; alternate venv and port, cached model with --offline |
| Native explicit CPU and auto selection | Passed; auto selected CPU int8 with zero detected CUDA devices |
| Native real English transcription and silence | Passed |
| Native Spanish transcription, English translation, and Both | Passed functional checks; accuracy caveat below |
| CPU Docker build from checkout | Passed |
| Compose startup with empty model volume | Passed; downloaded model and became healthy |
| Docker runtime user and host bind | UID 10001:10001; only 127.0.0.1:8772 published in test |
| Compose recreation with offline model loading | Passed; cached weights reused |
| CPU container inference with `--network none` | Passed for English, Spanish and English translation |
| GPU Docker image build | Passed; CUDA 12.8.1/cuDNN runtime image |
| GPU image packaging, CPU load/silence with `--network none` | Passed; this is not GPU inference validation |
| Explicit CUDA on this GPU-less host | Failed as expected, without silently using CPU |
| GPU selection and startup fallback unit tests | Passed using mocks; not hardware validation |
| API suite | 13 passed (two upstream test-client deprecation warnings) |
| Chrome capture -> real inference -> existing editor | Passed with local mock relay, no browser errors or external HTTP requests |
| Chrome Spanish/Both UI, English relay selection, transcript download | Passed with real inference and local mock relay |
| JavaScript/Bash/Python syntax checks | Passed |
| Bundled deployment skill validator | Passed |
| Native Windows scripts and Windows audio devices | Not run; Windows host access pending |
| Actual NVIDIA inference/performance on Windows or Linux | Not run; working GPU host required |
| Docker Desktop / WSL2 GPU integration | Not run |

Raw results:

- `native-deployment.json`: native launcher with auto device selection.
- `native-fresh-environment.json`: fresh environment through Bash launcher.
- `docker-deployment.json`: initial Compose deployment.
- `docker-offline.json`: recreated offline Compose deployment.
- `docker-no-network.json`: actual inference with networking disabled.
- `browser-smoke.json`: local capture and existing editor integration.
- `browser-translation.json`: real bilingual capture and English relay/download.

The Spanish fixture was synthesized locally with espeak-ng 1.51:

> Hola. Bienvenidos al teatro. Muchas gracias por venir esta noche.

On the unchunked synthetic fixture, base transcribed the middle phrase as
“bienvenido saltado” and translated it as “welcome to the other side”. The first
smoke test's theatre-word assertion failed. The final deployment test checks the
recognizable Spanish “gracias”, English “thank”, non-empty outputs, and language
metadata; it deliberately does not claim exact transcription. Raw incorrect text
is retained above. The browser microphone path produced a different, closer
version, which illustrates sensitivity to audio processing/chunk boundaries.

These are functional deployment tests, not representative event accuracy scores.
Both mode on the roughly 5.4-second Spanish sample took about 0.9–1.0 seconds on
CPU; translation alone took about 0.46–0.49 seconds. Single-fixture measurements
exclude model loading, phrase collection, network travel and editorial delay.

Reproduce the commands in DEPLOYMENT.md; generate the Spanish fixture before
running `scripts/browser_translation.py`. Both browser scripts accept
`CAPTION_TEST_URL` to point to a chosen local deployment. GPU validation should
repeat the same real-audio probes, confirm `/health` reports `cuda`, and measure
sustained delay and VRAM on the intended Windows/NVIDIA hardware.
