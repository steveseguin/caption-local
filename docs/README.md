# Guides and help

**Start with one microphone on one computer.** Choose a setup, get your first
captions working, then add an editor, audience displays or more streams.

## New users

- [Visual introduction](SELF-HOSTING.md): workflow diagrams, the actual capture
  screen, hosting choices and what you will need.
- [Install and get your first captions](GETTING-STARTED.md): Windows, Linux and
  Docker commands; connect, choose a microphone, capture, save and stop.
- [Troubleshooting](TROUBLESHOOTING.md): connection errors, microphone permission,
  missing captions and growing delays.

## Choose your setup

- [Hardware and quality profiles](DEPLOYMENT-PROFILES.md): CPU, NVIDIA, private
  VPS, model accuracy and measured concurrent-stream limits.
- [Windows and NVIDIA setup](WINDOWS-GPU.md): tested requirements, exact commands
  and GPU verification.
- [Installation and deployment reference](../DEPLOYMENT.md): native Python,
  Docker, model downloads and remote access.

## Connect an editor or audience

- [Caption.ninja integration](CAPTION-NINJA-LOCAL.md): the separate capture page,
  public/private sharing, direct overlays and hosted-page permissions.
- [Run your own caption relay](https://github.com/steveseguin/captionninja/blob/master/relay/README.md):
  Windows/Linux setup, room tokens, editor/viewer connections, OBS links and TLS.
- [First-event checklist](FIRST-EVENT.md): rehearse microphones, caption review,
  audience display, failures and shutdown together.

## Operate or integrate

- [Operations](../OPERATIONS.md): supervision, logs, offline operation, upgrades
  and recovery.
- [API reference](../API.md): native live-audio requests and the supported
  OpenAI-style WAV subset.
- [Security](../SECURITY.md): trusted-producer access, tokens and reporting issues.
- [Optional AI setup assistance](AI-SETUP.md): a setup prompt and deployment skill.
- [Contributing](../CONTRIBUTING.md): development and regression checks.

## Read the measurements

- [CPU and language results](../evidence/deployment-matrix/report.md)
- [NVIDIA hour and limitations](../evidence/gpu-sustained/report.md)
- [Text relay capacity and recovery](../evidence/relay-recovery/report.md)
- [Page layout and navigation review](../evidence/visual-review/report.md)
- [Full regression and clean-install checks](../evidence/full-regression/report.md)

Speech recognition and caption delivery have different limits. A relay benchmark
does not establish how many microphones your inference computer can transcribe.

[Project overview and downloads](../README.md)
