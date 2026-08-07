# Client-side security settings for the PIM server connection

**Date:** 2026-08-06
**Status:** Design approved, pending implementation plan
**Branch:** `feat/server_security`

## Summary

The PyPIM client connects to the PIM gRPC server over a channel built in
`Client._from_configuration()` from a JSON configuration file. Today that
channel supports only two modes: **insecure** or **TLS + bearer token**.

Instance-service connections (added in #326) already support four transports —
`insecure`, `uds`, `mtls`, `wnua` — via the shared helper
`ansys.tools.common.cyberchannel.create_channel(...)`, driven by the security
settings the PIM server returns for each product-instance service.

This work brings the same transport options to the client's **own** connection
to the PIM server. Because nothing tells the client how to reach the PIM server
(no server round-trip precedes it), the settings come from the client's own
configuration: primarily the config file, with an optional programmatic override.

## Goals

- Allow the client→PIM-server channel to use `uds`, `mtls`, and `wnua`
  transports in addition to the existing `insecure` and `tls` modes.
- Reuse the proven `cyberchannel` dispatch so client and instance-service
  connections behave identically for the new transports.
- Preserve today's `insecure` and `tls`+bearer-token behavior exactly.
- Keep existing v1 configuration files working with no change.

## Non-goals

- No refactor of the existing insecure / tls+token code paths (they stay as-is).
- No live end-to-end mTLS/UDS handshake tests in CI (no cert/socket fixtures).
- No stricter validation than cyberchannel already imposes, with one exception:
  the uds socket path is checked for existence up front (the server is expected
  to be already listening). Otherwise cyberchannel's own resolution stands — e.g.
  mtls with no certs is allowed and falls back to cyberchannel's defaults.

## Key decisions

| Decision | Choice |
| --- | --- |
| Settings source | Config file (primary) **and** optional programmatic override |
| Config schema | New **version 2** format; version 1 still read |
| Transport scope | Add `uds`/`mtls`/`wnua` via cyberchannel; `insecure`/`tls` unchanged |
| Programmatic type | Thin wrapper mirroring `ServiceSecurity` (transport string + `CertificateFiles`) |
| Code organization | Extract only the low-level cyberchannel dispatch into a shared module (Approach C) |

## Public API & configuration

### v2 configuration file format

```json
{
    "version": 2,
    "pim": {
        "uri": "dns:pim.svc.com:80",
        "headers": { "metadata-info": "value" },
        "security": {
            "transport": "mtls",
            "certificate_files": {
                "cert_file": "client.crt",
                "key_file": "client.key",
                "ca_file": "ca.crt"
            }
        }
    }
}
```

- `security.transport` ∈ `insecure | tls | uds | mtls | wnua`.
- **mtls**: `certificates_directory` and `certificate_files` are both optional.
  They map to cyberchannel's `certs_dir` and `CertificateFiles` respectively.
  Providing neither is valid — cyberchannel resolves its own defaults. Providing
  **both** is the only error (mutually exclusive).
- **uds**: the socket is taken from the `unix:` `uri`. There are no additional
  socket fields — the PIM server is assumed to be already running and listening
  at that URI. The only uds-specific validation is that the socket path parsed
  from the URI must exist.
- **wnua**: no extra fields; host/port parsed from `uri`.
- **insecure** / **tls**: preserve today's behavior exactly. `tls` still
  requires an `authorization: Bearer …` header (bearer-token secure channel);
  `insecure` requires nothing extra.

### v1 → v2 mapping

A `version: 1` file (with `tls: bool`) is read by the existing reader and mapped
to the canonical transport:

- `tls: false` ≡ `transport: "insecure"`
- `tls: true`  ≡ `transport: "tls"`

No behavior change for existing users.

### Programmatic override

`connect()` gains an optional parameter:

```python
import ansys.platform.instancemanagement as pypim
from ansys.platform.instancemanagement import ConnectionSecurity
from ansys.tools.common.cyberchannel import CertificateFiles

client = pypim.connect(
    security=ConnectionSecurity(
        transport="mtls",
        cert_files=CertificateFiles(
            cert_file="client.crt", key_file="client.key", ca_file="ca.crt"
        ),
    )
)
```

- `ConnectionSecurity` is the thin public wrapper (mirrors `ServiceSecurity`:
  a `transport` string + optional `CertificateFiles`), exported from the package.
- When supplied, it **replaces** the file's `security` block wholesale
  (all-or-nothing precedence). `uri` and `headers` always come from the file.
- The low-level `Client(channel, …)` constructor is unchanged — callers who
  build their own channel are unaffected.

## Internal architecture (Approach C)

### New private module `_channel.py`

The single home for transport→channel logic. Depends only on `grpc` and
`cyberchannel`; knows nothing about `Configuration` or `Service`.

```python
# _channel.py
def parse_host_port(uri: str) -> tuple[str, str]:
    ...  # moved from service.py


def parse_uds_socket_path(uri: str) -> str:
    ...  # moved from service.py


def build_cyberchannel(
    transport: str,  # "uds" | "mtls" | "wnua"
    uri: str,
    cert_files: CertificateFiles | None = None,
    grpc_options: list | None = None,
) -> grpc.Channel:
    """Dispatch to ansys.tools.common.cyberchannel.create_channel."""
    if transport == "uds":
        return create_channel(
            "uds", uds_fullpath=parse_uds_socket_path(uri), grpc_options=grpc_options
        )
    host, port = parse_host_port(uri)
    return create_channel(
        transport,
        host=host,
        port=port,
        cert_files=cert_files,
        grpc_options=grpc_options,
    )
```

This is exactly the cyberchannel branch lifted out of
`Service._build_grpc_channel`, unchanged in behavior.

### `service.py` change (surgical)

- `_parse_host_port` / `_parse_uds_socket_path` are removed and re-imported from
  `_channel`.
- The cyberchannel branch of `_build_grpc_channel` becomes a one-line call to
  `build_cyberchannel(...)`.
- The interceptor-wrapping and the config-token / insecure branches stay
  untouched.

### `client.py` / `_from_configuration` change

The channel is built by transport, then wrapped with the existing
`header_adder_interceptor(headers)` in **all** cases:

```
transport == "insecure"      → grpc.insecure_channel(uri)                   # existing, unchanged
transport == "tls"           → composite ssl + access_token credentials     # existing, unchanged
transport in {uds,mtls,wnua} → _channel.build_cyberchannel(transport, uri, cert_files)
```

## Configuration parsing, precedence & metadata

### `Configuration` field additions

Today: `uri`, `headers`, `tls: bool`, `access_token`. Add:

- `transport: str` — canonical `insecure | tls | uds | mtls | wnua`
- `cert_files: CertificateFiles | None` — resolved for mtls file mode
  (`None` when `certificates_directory` is used)
- `certs_dir: str | None` — for mtls directory mode
- keep `tls` / `access_token` for the `tls` path (unchanged semantics)

`tls` becomes a derived convenience (`transport == "tls"`) so existing internal
reads keep working.

### Version dispatch in `Configuration.from_file`

- `version: 1` → existing reader, then set
  `transport = "tls" if tls else "insecure"`.
- `version: 2` → parse the `security` block into `transport` + cert fields.
  The `tls` transport still extracts the bearer token from the `authorization`
  header exactly as v1 does (same validation error if missing).
- Unknown version → `InvalidConfigurationError` (as today).

### Precedence (programmatic override)

`_from_configuration(config_path, security=None)`. When `security`
(a `ConnectionSecurity`) is passed, it overrides `transport` + `cert_files`
after the file is parsed; `uri` and `headers` always come from the file. If the
override selects `tls`, the file must still provide the bearer token (else
`InvalidConfigurationError`) — the override changes transport, not credentials.

### Headers / metadata

- `header_adder_interceptor(headers)` wraps **every** transport (including
  uds/mtls/wnua), so custom metadata headers keep flowing regardless of transport.
- The bearer token is injected as call-credentials **only** in the `tls` path;
  uds/mtls/wnua rely on the transport itself for auth and do not add a token.

## Error handling & validation

All failures surface as the existing `InvalidConfigurationError` (config/file
problems, includes the config path) or `ValueError` (programmatic misuse). No
new exception types.

### Config-file validation (`InvalidConfigurationError`)

- `security.transport` missing or not in the valid set → error listing valid values.
- `mtls` with **both** `certificates_directory` and `certificate_files` → error
  (mutually exclusive), mirroring the existing `MtlsSettings` rule in `security.py`.
  Neither present is **not** an error — cyberchannel resolves its own defaults.
- `mtls` `certificate_files` present but missing any of `cert_file` / `key_file`
  / `ca_file` → error naming the missing key.
- `uds` socket path (parsed from the `unix:` `uri`) does not exist → error.
- `tls` transport without a valid `authorization: Bearer …` header → the
  existing bearer-token error, unchanged.

### Programmatic validation (`ValueError` from `ConnectionSecurity`)

- Unknown `transport` string → error.
- `transport="mtls"` with no `cert_files` and no certs dir → allowed
  (cyberchannel falls back to its own default resolution, matching the
  instance-service behavior).

### Runtime guards

- **wnua on non-Windows** → raise early with a clear "Windows-only" message
  rather than a downstream cyberchannel failure. Reuse a cyberchannel platform
  check if one is exposed; otherwise guard on `os.name`. (To confirm during
  implementation.)
- **uds on Windows** → defer to cyberchannel's `is_uds_supported`; surface a
  clear error if unsupported.
- Missing **cert** files → not pre-checked; let cyberchannel/gRPC raise on first
  use (consistent with today's `Service` path).
- Missing **uds socket** → pre-checked at config/connect time (see uds validation
  above), since the server is expected to be already listening; fail fast with a
  clear `InvalidConfigurationError`.

### Failure timing

- Config/transport validation happens at `connect()` / `from_file()` time
  (fail fast, before any RPC) — this includes uds socket-path existence.
- Actual TLS handshake / cert errors happen lazily on first RPC, exactly as gRPC
  behaves today.

## Testing

Follows the repo's existing pytest style.

### `_channel.py` unit tests (new)

- `parse_host_port` / `parse_uds_socket_path`: relocate the existing
  service-side parser tests so coverage moves with the code; cover `dns:`,
  `dns://authority/`, `ipv4:`, `ipv6:`, `unix:`, `unix://`, and malformed URIs
  (→ `ValueError`).
- `build_cyberchannel`: mock `cyberchannel.create_channel` and assert the right
  args per transport (uds → `uds_fullpath`; mtls/wnua → `host`/`port`/`cert_files`).
  No real sockets/certs.

### Config parsing tests

- v1 file → `transport` derived as `insecure`/`tls` (regression: unchanged).
- v2 file per transport: `insecure`, `tls` (with/without bearer header), `uds`
  (existing socket path → ok; missing socket path → error), `mtls` (dir mode,
  files mode, neither → ok, both → error, missing file key → error).
- Unknown version and unknown transport → `InvalidConfigurationError`.

### Client / `_from_configuration` tests

- Each transport builds the expected channel: `insecure`/`tls` still use
  `grpc.insecure_channel` / composite credentials (patched); uds/mtls/wnua
  delegate to `build_cyberchannel` (patched). Assert `header_adder_interceptor`
  wraps every transport.
- Programmatic `security=` override replaces the file's transport; `uri`/`headers`
  still from file; `tls` override without token → error.

### Platform guards

- wnua on non-Windows → error (monkeypatch `os.name` / platform check).
- uds unsupported → error via `is_uds_supported` (patched).

### `service.py` regression

Existing instance-service channel tests must still pass after the parsers and
dispatch move to `_channel.py` (proves the refactor is behavior-preserving).

### Out of scope (documented)

- No live end-to-end mTLS/UDS handshake tests (no cert/socket fixtures in CI).
- cyberchannel itself is trusted and mocked at its boundary.
