# SmartDomIC runtime image review

Date: 2026-10-20. Scope: local Linux/amd64 build only.

## Changes

- Update Python 3.14.3 to 3.14.8 on Debian trixie; pin the image index digest.
- Pin uv 0.13.1 by digest and mount it only during dependency installation.
- Remove runtime pip and ensurepip, including their vendored dependencies.
- Keep application code, locked Python dependencies and UID/GID 10001 unchanged.
- Add an offline container smoke test to CI.

Runtime package installation with pip is intentionally unavailable. Rebuild the
image to change dependencies; manual installation instructions are unaffected.

## Local evidence

Docker Scout 1.24.0, critical/high filter, 2026-10-20:

| Image | Critical | High |
| --- | ---: | ---: |
| Upstream 1.7.1, index e48c300f71b8 | 8 | 29 |
| Refreshed base, build tools retained | 0 | 6 |
| Final runtime, index 05cc1797c0f218d1c02fc9e6fef0fbfc2e399b324a9cea932506385ae1d7958c | 0 | 1 |

Remaining finding: zlib `1:1.3.dfsg+really1.3.1-1`, CVE-2026-85091;
Scout reports no fixed version. No exploitability assessment or risk waiver is
implied. Other severities were not evaluated by this filtered scan. Scout completed
indexing with a temporary archive cleanup warning on Windows.

The five other high findings came from pip's vendored urllib3 2.7.0,
msgpack 1.1.2 and setuptools 70.3.0. Runtime urllib3 was already 2.8.0.
Removing uv reduced indexed packages but did not remove these pip findings.

Validated locally: successful build; application imports on Python 3.14.8;
non-root UID; verified STARTTLS; AUTH unavailable before TLS; MAIL rejected with
530 both before TLS and after TLS without authentication. The final smoke test
ran with no external network, no published ports, read-only root filesystem,
dropped capabilities and temporary certificates in /tmp. No OAuth requests or
messages were sent. Ruff 0.17.0 lint and format passed locally; EXE002 was excluded
from local lint because Windows bind mounts expose files as executable (Git tracks
source files as 100644). CI uses the project's unmodified lint rules.

## Decision

The image defects can largely be corrected without rewriting the relay. Keep
deployment disabled pending a specific decision about the residual zlib advisory
and Microsoft 365 integration testing. A bounded laboratory trial can accept
stateless operation, manual delivery checks and low message volume; it still
requires TLS, isolated access and least-privilege mailbox authorization.

This change does not fix sensitive logging, tenant/app allowlisting, durable queueing,
ambiguous timeout outcomes or MIME/Bcc behavior. Those remain separate work items.
Graph acceptance does not demonstrate delivery. No production readiness claim.
ARM64 and GitHub-hosted CI results are separate from these local results.

## Reproduce

```sh
docker build --platform linux/amd64 -t smartdomic/smtp-oauth-relay:base-refresh .
docker scout cves --only-severity critical,high --format packages smartdomic/smtp-oauth-relay:base-refresh
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,source=$(pwd)/tests,target=/tests,readonly" \
  --entrypoint python smartdomic/smtp-oauth-relay:base-refresh -B /tests/container_smoke.py
```
