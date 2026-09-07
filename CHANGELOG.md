# Changelog

## Unreleased

- Private Caption Ninja relay support with room credentials, acknowledged publishing,
  bounded replay and visible recovery gaps; the separate relay runs in captionninja.
- Private editor/viewer setup panels and verified view-only OBS links. The
  caption.ninja home page and its shared publisher remain unchanged by this work.
- Reproducible Windows/WSL relay tests, a real local TLS proxy probe and sustained
  load tooling. See the relay recovery evidence for measured results and limits.

## 1.1.0 — first public release

- Standalone Linux CPU speech transcription and speech-to-English translation service.
- Browser microphone capture, overlapping speech windows, human-review output to caption.ninja, and local transcript download.
- Independent input streams, bounded FIFO worker admission, per-stream retry caches, and overload recovery.
- Native Linux/Windows launchers, CPU/NVIDIA Docker configurations, offline model caching, and an optional systemd user service generator.
- Tested twelve-stream English CPU preset, with multilingual accuracy limitations documented separately from the small-model quality default.
- Human-first installation and event guides, troubleshooting, an AI deployment skill, contribution/security guidance, and automated checks.

Windows/NVIDIA hardware validation and full-duration theatre-event validation remain
outstanding. The earlier local 1.0 validation is preserved under `evidence/`; it was
not a public GitHub release.
