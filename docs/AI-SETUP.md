# Set up Caption Local with an AI assistant

Using an AI assistant is optional. You can install the service yourself using the
[README](../README.md). The service itself does not require an AI account or API key.

## Copy-and-paste prompt

Give an assistant with terminal access this prompt:

> Install Caption Local from https://github.com/steveseguin/caption-local on this
> computer. Read README.md, DEPLOYMENT.md, OPERATIONS.md and
> skills/deploy-caption-local/SKILL.md. Preserve any existing installation and model
> cache. Use the latest tagged release unless I request development code. Choose
> native Python or Docker based on what is already available. Default to CPU and
> the multilingual small model. Keep the service bound to localhost and caption.ninja
> sharing off. Install dependencies, download the model, start the service and verify
> readiness plus real transcription. Explain how to open the capture page, connect
> a microphone, stop the service, and later update it. Report what you actually
> tested and any unvalidated Windows/GPU capabilities. Do not expose a public port.

Add your preferences as needed:

- “Use Docker and keep it running after I close the terminal.”
- “Inference runs on a Linux server; my microphone is on another computer. Set up SSH forwarding.”
- “I need twelve English streams. Evaluate the CPU throughput preset and measure capacity on this machine.”
- “I need Spanish transcription and English translation. Keep small and test accuracy.”
- “I have an NVIDIA GPU. Verify the actual driver/runtime and inference before claiming acceleration works.”

## Reusable deployment skill

The folder [skills/deploy-caption-local](../skills/deploy-caption-local/SKILL.md)
contains a plain-Markdown deployment skill. Ask your assistant to read that file,
or copy the **whole folder** into the user skill directory supported by your
assistant. Instructions for skill installation depend on the assistant; reading
the file directly works without a special installer.

The skill routes installation details to the maintained guides instead of keeping
separate copies of commands. It covers native/Docker setup, offline models, SSH,
CPU/GPU choices and honest validation of stream capacity.

## Check the result

The assistant should report the selected version, model, actual device and startup
command; show that `/health` is ready and a real audio request works; and explain
shutdown and recovery. A successful import, a detected GPU, or a mocked test alone
does not establish a working transcription deployment.
