# Security and deployment scope

Caption Local is designed for a local computer or trusted producers connecting
through SSH. It binds to loopback by default; Docker publishes only a loopback
port. Host/Origin checks and bounded audio requests reduce accidental exposure,
but they are not user authentication or tenant authorization. Stream IDs are not
credentials. Public internet hosting requires a separate authenticated deployment
design.

Optional `CAPTION_API_KEY` gates API access with a shared bearer token. The page
keeps it only in tab memory and never sends it to caption.ninja. This controls
service access for trusted producers; it does not add per-user authorization,
tenant isolation or encryption. Keep localhost/SSH transport. Token setup,
rotation and metadata-only logging are in [deployment profiles](docs/DEPLOYMENT-PROFILES.md).
The compatibility API rejects foreign browser Origins, bounds multipart uploads
to 5 MiB and WAV duration to twelve seconds, and shares native inference limits.

Audio and retry results are held in memory. A process/browser crash loses pending
work. Transcripts are downloaded explicitly. Optional caption.ninja sharing sends
text through that external relay; it does not provide end-to-end encryption.

## Report a vulnerability

Use the repository's **Security → Report a vulnerability** form for a private
report: https://github.com/steveseguin/caption-local/security/advisories/new.
Include affected versions, a minimal reproduction and likely impact. Do not post
credentials, private recordings or an unpatched exploit in a public issue.
If the private-report form is unavailable, use the maintainer contact published
on the repository owner's GitHub profile without attaching sensitive material
until a private reporting channel is agreed.

Security fixes target the latest published release. Older snapshots are retained
for reproducibility and rollback, without a separate maintenance guarantee.
