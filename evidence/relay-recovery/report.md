# Private relay recovery and sustained validation

Work in progress, 2026-09-07. The main caption.ninja home page and its shared
`ws-publisher.js` are unchanged from the start of this task. New private protocol
code is loaded only by the self-hosted capture, editor and standard overlay paths.
No private captions were published to the hosted public relay.

## Recovery contract

Protocol 2 adds publisher acknowledgements, stable delivery identities and
deduplication, and reader resume cursors. Text and receipts are retained in RAM
for up to 120 seconds/256 messages per room, subject to global bounds of 8,192
messages and a 16 MiB accounting budget. The oldest history expires first.
New viewers start live. Retained text is accessible to holders of that room's
viewing credential; no text or credentials are written to disk or logs.

Reconnects inside retained history recover missed messages even when publishers
return first. Lost acknowledgements retry the same identity without repeating
viewer delivery. Expired history and relay-process restarts emit explicit gaps.
Restart clears receipts too, so a previously accepted but unacknowledged caption
may repeat after a process restart. This is not durable/exactly-once delivery.
The editor's bounded review queue can still overflow; private mode now warns
explicitly if older waiting captions are dropped. Original public protocol
behavior and buffers are preserved.

## Browser and TLS checks

[browser-recovery.json](browser-recovery.json): Edge 152.0.4191.66, synthetic
microphone, fake speech inference and a real private relay. The capture → editor
→ overlay workflow passed, including the labeled token setup panel, denial,
view-only OBS link creation (rejecting the known publishing token), Stop/drain,
queued-caption recovery after restart and a visible restart-gap warning. No
browser errors or external requests. The observed review-click-to-visible time
was 48.8 ms; this single observation includes automation and is not a speech
latency or audience-capacity benchmark.

The [final browser probe](browser-recovery-final.json) also verifies the OBS
viewing token against the real relay before creating a link. Both the editor's
publishing token and another room's publishing token are rejected. The selected
viewing token passes, and the generated link opens the viewer without a prompt.
The existing [public capture regression](connection.json) also passes.

Fast checks passed: 52 native Windows Python tests, 14 JavaScript tests and 17
real-socket/client tests on both Windows and WSL. Python deprecation warnings
remain upstream. These tests exercise recovery and protocol behavior, not
recognition accuracy. The hour test remains separately in progress below.

[tls-caddy-windows-final.json](tls-caddy-windows-final.json): Caddy 2.11.4 on
Windows, Node 22.19.0, actual HTTPS/WSS reverse proxy on 127.0.0.1. The test created
an ephemeral CA and verified both the certificate chain and localhost/IP name.
Untrusted certificates and wrong room tokens were rejected. The system trust
store, PATH and firewall were unchanged; the Caddy binary stayed under ignored
`samples`. Its official release SHA-512 checksum was checked before execution.
This validates real TLS proxying, not a public domain, WAN behavior or browser
local-network permissions. A public test domain/server has been requested but
has not been supplied.

An initial browser probe used the old test description for its restart assertion;
its old "no replay" label is superseded by the recovery probe. The initial TLS
timing included the subsequent token-denial check; the final TLS probe measures
delivery before that check. These early raw outputs are retained as harness
history and are not used as final latency evidence.

## Sustained load

The [15-second probe](probe-100.json) passed: 32 independent producers, 100
viewers, 132 sockets, five synthetic captions/second/producer and two forced
publisher/viewer disconnect pairs. All 7,500 expected deliveries arrived once
and in order with no reported gaps. The maximum ~2-second delay includes a
deliberately disconnected viewer; p95 was 7.2 ms.

The 3,600-second Windows run is still running. Its final results and any larger
audience probes will be added after completion. No sustained-capacity claim is
made from the short probe. The soak runs the real browser recovery client against
real sockets, with clients/server in one Node process and no speech inference.
It records fixed-size latency histograms, per-viewer counts, errors, duplicates,
gaps, queue depths, retained history, CPU and sampled RSS. Per-IP admission is
explicitly 512 because every test connection shares loopback; production defaults
remain 128. The test does not silently enlarge caption buffers.

## Reproduction and scope

From captionninja's `relay` directory after `npm ci --ignore-scripts`:

```sh
node --test test/*.test.cjs
node soak.cjs 3600 /absolute/path/to/new-hour-results.json 100
```

From Caption Local (Windows Python; use a separate Linux/WSL environment there):

```powershell
.venv\Scripts\python.exe scripts/sync_capture_page.py samples/captionninja --check
.venv\Scripts\python.exe scripts/browser_private_relay.py --output evidence/relay-recovery/new-browser.json
.venv\Scripts\python.exe scripts/test_relay_tls.py --caddy /path/to/caddy.exe --openssl /path/to/openssl.exe --output evidence/relay-recovery/new-tls.json
```

The TLS probe needs an existing Caddy and OpenSSL executable, creates credentials
only in an owned temporary directory, binds only loopback and removes its test
processes. No certificate is installed into a system/browser store. The Docker
probe is designed for Linux CI with an existing daemon; Docker Desktop is absent
on this computer and will not be installed just for this task.
