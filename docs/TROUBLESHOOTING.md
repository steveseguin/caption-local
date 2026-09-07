# Troubleshooting

[All guides](README.md) · [Install](GETTING-STARTED.md) · [Troubleshooting](TROUBLESHOOTING.md)

Start with the capture page's error/status message. For Docker, check
`docker compose ps` and `docker compose logs --tail=100`. For a native process,
read its terminal output. `/health` reports the model, actual device, readiness,
workers, running/queued requests and failures.

| Symptom | What to do |
| --- | --- |
| Windows says `py` is not recognized or Python 3.12 is missing | Install Python 3.12 with the Windows launcher, reopen the terminal, and check `py -3.12 --version`. Existing Python installations do not need to be removed. |
| Cannot open `deploy.py` | Extract the project archive and open the terminal in the folder containing `deploy.py`. Do not run from inside the ZIP or its parent folder. |
| Python or venv is missing | Install Python 3.12 and your distribution's venv package. On Ubuntu 24.04: `sudo apt-get install python3 python3-venv`. Then rerun `./start.sh`. |
| Permission denied running start.sh | Run `bash start.sh`, or restore its executable bit with `chmod +x start.sh`. |
| PowerShell blocks start.ps1 | Run `py -3.12 deploy.py run` from the project folder. You do not need to relax machine-wide script policy. |
| Installation was interrupted | Run `python3 deploy.py setup` again. On Windows use `py -3.12`. Existing environments are not automatically repaired by normal startup. |
| Page unavailable during startup | Wait for model download and warmup. Check the terminal/logs for a real error before restarting. A first download may take several minutes. |
| Offline startup fails | Cache the selected model online first. Native: `python3 deploy.py download --model small`. Docker uses a separate named-volume cache: first run with `CAPTION_OFFLINE=0`, then enable offline mode. |
| Port already in use | Stop the other Caption Local instance or set `--port 8770` for native / `CAPTION_PORT=8770` in Docker's `.env`. Open the matching browser port. |
| Microphone is unavailable | Allow browser microphone permission and select the correct device. Open localhost directly or through SSH; a remote plain-HTTP IP address is not a secure microphone context. |
| Page requests a service access token / API returns 401 | Ask the service operator for the configured local token. It is not an OpenAI, Google or Gemini key. The browser forgets it on reload; enter it again. |
| Meter moves, captions do not appear | Speak for several seconds, select the language explicitly and try Quiet speech sensitivity. Whisper's voice detection may suppress noise or very quiet audio. |
| Captions are wrong | Check the source audio, language and model. Rehearse names and overlapping speakers. The faster base preset is unsuitable for the supplied Spanish quality fixture; use small and human review. |
| Translation language is wrong | Whisper translates into English only. For another target language you need a separate translation system. English-only `.en` models cannot translate. |
| Stream capacity reached | Stop and drain an unused capture page. Abandoned idle sessions expire after 120 seconds. Each producer needs a different stream ID. |
| Buffer keeps growing / capture stopped | Reduce active streams or translation work and competing CPU load. Do not increase the buffer to hide a machine that cannot keep up. Retry retained audio after addressing the cause. |
| Relay is disconnected | Local captions can still work. Check connectivity and the editor source room. The relay queue is bounded; watch its dropped count. External relay delivery is not guaranteed. |
| CUDA is unavailable | Run `nvidia-smi`, check the documented drivers/runtime, then test real inference. `--device cuda` intentionally fails if unavailable; use CPU explicitly if needed. |
| Server restarted | Docker/systemd may restart a worker that exceeded its 90-second watchdog deadline. Wait for readiness and retry pending browser audio. The server's retry cache does not survive restart. |

## Report a reproducible issue

Include your OS, release/tag, installation method, model, worker/thread/beam
settings, number of streams, chosen mode, the error message and whether the issue
also occurs with one stream. Include sanitized `/health` output and relevant logs.
An audio fixture is optional: share only audio you have permission to publish.
Never include credentials, private room names or confidential transcripts.

[Open an issue](https://github.com/steveseguin/caption-local/issues/new/choose).
For security vulnerabilities, follow [SECURITY.md](../SECURITY.md).
