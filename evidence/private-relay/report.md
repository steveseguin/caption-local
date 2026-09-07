# Private Caption Ninja relay validation

2026-09-07, Windows 11 Pro 10.0.26200 and Ubuntu under WSL2 on the previously
inventoried Core Ultra 7 265K / 64 GiB host. This work does not use the GPU or
change the unrelated inference installation. The relay is a new implementation
in captionninja's `relay/`; the privately hosted public relay source was neither
available nor used. No test captions reached a public room.

## What changed

- Separate Node relay, pinned `ws` 8.21.3, room-specific read/write credentials,
  exact browser-origin checks, bounded messages/connections/output, join deadline
  and heartbeat. Only readers in the writer's room receive captions. No history
  or caption/credential logging; aggregate health counters only.
- Caption Local offers relay/site addresses, a source publishing token and editor
  output room. Editor and standard overlay use the selected relay. Generated links
  carry no credentials; optional fragment credentials are removed into tab memory.
  Invalid or failed private endpoints never select the public relay.
- Private publishers wait for join authorization before flushing bounded queues;
  denial stops automatic retries. Public joins keep their previous wire format.
- Removed an existing late `socket.onclose` override in overlay.html which reloaded
  the page instead of using its reconnect handler. That reload discarded private
  relay credentials and caused the initial restart browser test to fail.
- The local page's CSP now permits custom `wss:` destinations and loopback `ws:`
  destinations. HTTP inference destinations remain restricted by the existing
  service transport/origin configuration. Script policy is unchanged.

## Browser workflow

[browser.json](browser.json): PASS on Edge 152.0.4191.66 with synthetic microphone,
fake speech inference, real HTTP loopback service and real Node relay. Tested
capture → private source → manual editor review → separate output room → standard
overlay, Stop/drain, rejection of a wrong publishing token, generated links,
fragment credential removal and queued-caption recovery after server restart.
There were no browser errors or external HTTP/WebSocket connections. This tests
transport/UI behavior, not speech recognition accuracy or physical microphones.

The final bounded-publisher implementation is also checked in
[browser-final.json](browser-final.json). The existing cross-origin/public-relay
capture regression passed with a local mock: [connection.json](connection.json).
Its direct-overlay assertion was updated to require the exact selected local
website URL and `.html` page, which works on a plain static file server.

One review-click-to-visible observation was 2.0333 seconds, including browser
automation and the existing overlay display path. It is neither a relay-only
timing nor a speech-to-caption measurement.

The [initial failed browser run](browser-restart-initial.json) is retained. Its
expectation that a queued caption would reach the editor regardless of reconnect
order failed: this relay does not replay captions to a viewer that joins later.
The passing queue probe deliberately rejoins the reader before reconnecting the
publisher. **An arbitrary restart is not lossless.** Captions sent without a
connected viewer can be missed. There are no per-caption acknowledgements,
durable delivery or exactly-once guarantees. The separate overlay reload bug
also surfaced on reruns and was fixed before the passing result.

## Short relay load measurements

Both runs use 32 independent rooms/producers, two viewers per room (96 sockets),
five captions/second/producer, six synthetic language strings and 300 rounds.
There are 9,600 publications and 19,200 viewer deliveries per run. Checks validate
per-viewer order, room labels, expected delivery counts and connection errors.

| Measurement | Windows Node 22.19.0 | WSL Linux Node 24.10.0 |
| --- | ---: | ---: |
| Observed duration | 59.82 s | 59.81 s |
| Errors / missing deliveries | 0 / 0 | 0 / 0 |
| Delivery median | 2.11 ms | 1.50 ms |
| Delivery p95 | 3.98 ms | 2.64 ms |
| Delivery p99 | 4.74 ms | 3.31 ms |
| Worst delivery | 5.78 ms | 5.26 ms |
| Peak sampled process RSS | 56.57 MiB | 71.00 MiB |
| Mean process CPU cores | 0.021 | 0.016 |

Raw results: [Windows](load-windows.json), [WSL](load-wsl.json). Clients and relay
run in one process over loopback; CPU/RAM include both. The 60-second requested
load schedules its first round immediately and its last at 59.8 seconds. These
are short capacity probes, not an hour soak, a sustained maximum, a WAN benchmark
or a claim that 32 speech recognition streams fit this computer. Existing GPU
accuracy/capacity evidence remains separate. The host's other services were not
stopped for this lightweight relay test. An initial Windows load invocation had
an incorrect relative output path and exited without saving; it was rerun with
the correct path, with no benchmark criteria changed.

## Reproduce

In captionninja's `relay` directory, use `npm.cmd ci --ignore-scripts` on Windows
(`npm ci --ignore-scripts` on Linux), then:

```sh
node --test test/*.test.cjs
node benchmark.cjs 60 /absolute/path/to/new-results.json
```

In Caption Local, after preparing `samples/jfk.wav` and installing development
dependencies, run:

```powershell
.venv\Scripts\python.exe scripts/sync_capture_page.py samples/captionninja --check
.venv\Scripts\python.exe scripts/browser_private_relay.py --checkout samples/captionninja --output evidence/private-relay/new-browser.json
```

Use Linux's `.venv/bin/python` (or the separate `.venv-wsl/bin/python`) there.
Browser tests reserve 8778/8779/8787, fail if already occupied, keep private
credentials in a temporary directory outside the web root and stop only their
owned processes. The browser probe serves fake inference; no model is loaded.

Unit tests cover room/role isolation, malformed joins/JSON, binary/oversize input,
rate limits, origins, join timeout, global/per-IP/per-room admission, credential
validation, cleanup and no history on reconnect. The slow-consumer test injects
the WebSocket buffered-byte counter to exercise termination without depending on
OS socket-buffer sizes; it is not a real stalled-WAN test. Client tests cover
authorization-before-flush, queue overflow accounting, denial, endpoint validation,
fragment cleanup and unchanged public join behavior.

Fast regression checks: 52 Python tests on each of Windows and WSL, 14 JavaScript
tests, and 9 real-socket relay tests on each platform. Upstream Python deprecation
warnings remain. The browser bundle is checked byte-for-byte against its manifest;
source/documentation checks pass. `npm` dependency audit reported no known
vulnerabilities for the pinned installation at test time.

## Deployment limits

Only the separate capture page, editor and standard overlay support the complete
private workflow in this change. Alternative overlay/translation pages, public
TLS hosting, Docker Desktop, physical microphone capture, WAN failure behavior,
credential rotation during an event and sustained large audiences are not
validated here. Native Windows/WSL tests do not certify public production use.
The setup guide documents Docker/TLS examples and these limits. Use independently
managed private configuration outside the web root; no sample production secrets
are committed. Speech models and GPU configuration stay in Caption Local.

Implementation references: [ws API and bounds](https://github.com/websockets/ws/blob/master/doc/ws.md)
and [Node constant-time digest comparison](https://nodejs.org/api/crypto.html#cryptotimingsafeequala-b).
