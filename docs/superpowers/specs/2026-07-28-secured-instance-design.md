# Secured Instance Connections — Design

**Date:** 2026-07-28
**Branch:** `feat/claude_secured_instance`
**Status:** Approved design, pending implementation plan

## Summary

PyPIM gains support for the PIM API v1 security features:

1. **Create-side:** callers may optionally specify transport security when creating an
   instance (`insecure`, `mTLS`, `WNUA`, or `UDS`), expressed through protobuf-free typed
   dataclasses.
2. **Read-side:** when the server reports per-service `ServiceSecurityInfo`, PyPIM builds
   the gRPC channel through `ansys.tools.common.cyberchannel.create_channel` using the
   resolved transport mode and its parameters.

The feature is fully opt-in. When no security settings are supplied and the server returns
no security info, PyPIM behaves exactly as it does today.

## Goals

- Let users select a transport security mode at instance-creation time.
- Automatically build the correct gRPC channel from the server-resolved security info.
- Reuse `ansys.tools.common.cyberchannel.create_channel` for channel construction on every
  path where it structurally applies.
- Never expose protobuf types on the public API.
- Preserve the current behavior byte-for-byte when the feature is unused.
- Cover all new parameters and code paths with unit tests.

## Non-goals

- No changes to HTTP/REST service handling.
- No new authentication mechanisms beyond what the PIM API v1 proto defines.
- No migration of the two legacy channel paths that `create_channel` cannot represent
  (see "Channel-construction reuse boundary").

## Constraints (from the requester)

- The gRPC channel must be created via the `ansys-tools-common` dependency
  (`ansys.tools.common.cyberchannel.create_channel`). This package is already declared in
  `pyproject.toml` (`ansys-tools-common~=0.5.0`).
- The internal protobuf messages must not be exposed by the client classes.
- Unit tests must cover the new parameters.
- `security_settings` is an **optional** parameter. The current behavior must not break:
  an insecure channel when `configuration.tls` is `False`, and a secure channel using the
  Authorization header when `configuration.tls` is `True`.

## Background — relevant PIM API v1 messages

Create-side request field:

```
CreateInstanceRequest.security_settings : InstanceSecuritySettings   // optional
```

`InstanceSecuritySettings` — `oneof transport`:
- `insecure` (`google.protobuf.Empty`)
- `mtls` (`MtlsSettings`)
- `wnua` (`google.protobuf.Empty`)
- `uds` (`UdsSettings`)

`MtlsSettings` — `oneof certificate_source`:
- `certificates_directory` (`string`)
- `certificate_paths` (`MtlsCertificatePaths`: `server_key_path`,
  `server_certificate_path`, `ca_certificate_path`, `client_key_path`,
  `client_certificate_path`)

`UdsSettings`: `socket_path`, `socket_directory`, `socket_identifier`.

Read-side per-service field:

```
Service.security : ServiceSecurityInfo   // output only, set only when created secured
```

`ServiceSecurityInfo` — `oneof transport`:
- `insecure` (`Empty`)
- `mtls` (`MtlsClientInfo`: `ca_certificate_path`, `client_certificate_path`,
  `client_key_path`)
- `wnua` (`Empty`) — connect with an insecure channel; server-side interceptor handles auth
- `uds` (`Empty`) — the socket path is encoded in `Service.uri`

## Architecture

Two independent halves connected by the PIM server.

```
                       create_instance(security_settings=MtlsSettings(...))
 caller ──────────────────────────────────────────────────────────────────►  PIM server
                       CreateInstanceRequest.security_settings

                       Service.security = ServiceSecurityInfo(...)
 caller ◄──────────────────────────────────────────────────────────────────  PIM server
        │
        └─ Service._build_grpc_channel() ─► cyberchannel.create_channel(...) ─► grpc.Channel
```

### Create-side (client → server)

`create_instance` / `Definition.create_instance` / `Instance._create` gain an optional
`security_settings: SecuritySettings | None = None` parameter. When provided, the dataclass
is translated to the proto `InstanceSecuritySettings` and attached to
`CreateInstanceRequest.security_settings`. When `None`, the request is built exactly as
today.

### Read-side (server → channel)

`Service._build_grpc_channel()` becomes a two-branch decision:

```
if the service carries resolved security info:
    build the channel via cyberchannel.create_channel(...)
    for the resolved transport mode
else:                              # unchanged legacy path
    if configuration.tls:  secure_channel + ssl_channel_credentials + access_token call-creds
    else:                  insecure_channel
```

In **both** branches the channel is wrapped with
`grpc.intercept_channel(channel, header_adder_interceptor(headers))`, so `Service.headers`
are always injected.

The decisive rule: the `create_channel` path is taken **only when the server actually
returned security info**. Existing instances (no security info) keep the exact
`tls`/Authorization-header behavior they have today.

### Channel-construction reuse boundary

`create_channel` is used for every path it can structurally represent:

| Path | Uses `create_channel`? | Reason |
|------|------------------------|--------|
| Security info: `insecure` | Yes | `create_channel("insecure", ...)` |
| Security info: `mtls` | Yes | `create_channel("mtls", ...)` |
| Security info: `wnua` | Yes | `create_channel("wnua", ...)` |
| Security info: `uds` | Yes | `create_channel("uds", ...)` |
| Legacy `tls=True` | No | `cyberchannel` has no "server-TLS + bearer-token" mode; its `mtls` requires client cert/key/ca. Path stays as-is. |
| Legacy `tls=False` | No | Mappable to `create_channel("insecure", ...)`, but that adds an insecure-warning and requires host/port parsing that could fail on some URIs. Kept as a direct `grpc.insecure_channel` to avoid any behavior change. |

## Components

### New module: `security.py`

Public, protobuf-free frozen dataclasses, one per transport mode:

```python
@dataclass(frozen=True)
class InsecureSettings:
    ...  # no fields → proto insecure (Empty)


@dataclass(frozen=True)
class WnuaSettings:
    ...  # no fields → proto wnua (Empty)


@dataclass(frozen=True)
class MtlsCertificatePaths:  # → proto MtlsCertificatePaths
    server_key_path: str
    server_certificate_path: str
    ca_certificate_path: str
    client_key_path: str
    client_certificate_path: str


@dataclass(frozen=True)
class MtlsSettings:  # certificate_source oneof
    certificates_directory: str | None = None
    certificate_paths: MtlsCertificatePaths | None = None


@dataclass(frozen=True)
class UdsSettings:
    socket_path: str | None = None
    socket_directory: str | None = None
    socket_identifier: str | None = None


SecuritySettings = Union[InsecureSettings, MtlsSettings, WnuaSettings, UdsSettings]
```

Each settings class exposes a private `_to_pim_v1() -> InstanceSecuritySettings` that builds
the corresponding proto oneof. `MtlsSettings._to_pim_v1()` validates that **at most one** of
`certificates_directory` / `certificate_paths` is set, raising `ValueError` otherwise.

The new public names are added to the package `__init__.py` `__all__`.

### `service.py`

- `Service` carries an **internal, protobuf-free** representation of the resolved security
  info (not a public attribute): the transport mode string plus, for mtls, a
  `cyberchannel.CertificateFiles(cert_file=client_certificate_path,
  key_file=client_key_path, ca_file=ca_certificate_path)`. Absent when the server returned
  no security info.
- `Service._from_pim_v1()` reads `service.security` via
  `service.security.WhichOneof("transport")` and builds that internal representation (or
  `None`).
- `Service._build_grpc_channel()` gains the security branch described below.
- Two module-level URI-parsing helpers (unit-tested in isolation):
  - `_parse_host_port(uri) -> (host, port)` — strips a leading gRPC scheme (`dns:`,
    `dns:///`, `dns://authority/`, `ipv4:`, `ipv6:`, or none) and right-splits the last `:`.
    Raises `ValueError` on an unparsable URI.
  - `_parse_uds_socket_path(uri) -> str` — strips the `unix:` / `unix://` prefix to recover
    the absolute socket path.

Security-branch mapping:

| transport | `create_channel(...)` call |
|-----------|----------------------------|
| `insecure` | `create_channel("insecure", host, port, grpc_options=opts)` |
| `mtls` | `create_channel("mtls", host, port, cert_files=CertificateFiles(...), grpc_options=opts)` |
| `wnua` | `create_channel("wnua", host, port, grpc_options=opts)` |
| `uds` | `create_channel("uds", uds_fullpath=<socket path>, grpc_options=opts)` |

`grpc_options` bridge: the existing `**kwargs` passthrough (in practice `options=[...]`) is
forwarded as `create_channel(..., grpc_options=kwargs.get("options"))`, keeping the same
caller knob.

### `instance.py`

`Instance._create` gains `security_settings: SecuritySettings | None = None` and builds the
request conditionally:

```python
request = CreateInstanceRequest(instance=InstanceV1(definition_name=definition_name))
if security_settings is not None:
    request.security_settings.CopyFrom(security_settings._to_pim_v1())
instance = stub.CreateInstance(request, timeout=timeout)
```

When `security_settings is None`, the wire format is identical to today.

### `definition.py` and `client.py`

Both `create_instance` methods gain `security_settings: SecuritySettings | None = None` and
forward it down the chain:

```
Client.create_instance(..., security_settings=None)
    └─ Definition.create_instance(..., security_settings=None)
        └─ Instance._create(..., security_settings=None)
```

Docstrings on all three public methods document the new parameter, list the four dataclass
options, and include a short mTLS example.

## Data flow

**Create (secured):** caller builds `MtlsSettings(...)` → passed to `create_instance` →
forwarded to `Instance._create` → `_to_pim_v1()` → `CreateInstanceRequest.security_settings`
→ server.

**Read (secured):** server returns `Instance` whose `Service.security` is a
`ServiceSecurityInfo` → `Service._from_pim_v1` parses it into the internal representation →
`Service._build_grpc_channel` maps it to a `create_channel(...)` call → header interceptor
wraps the channel.

## Error handling

- `MtlsSettings._to_pim_v1()` raises `ValueError` if both `certificates_directory` and
  `certificate_paths` are set.
- `_parse_host_port` raises `ValueError` on a URI it cannot split into host/port. Because
  security info only appears for explicitly-secured instances, this surfaces a clear failure
  rather than a silent mis-connect.
- `create_channel` itself raises on invalid combinations (e.g. missing host/port, UDS
  unsupported on platform, missing certificate files); these propagate to the caller.

## Testing

New file `tests/test_security.py`:
- Dataclass → proto (`_to_pim_v1`), one test per mode. `MtlsSettings` with
  `certificates_directory`, with `certificate_paths`, and the `ValueError` when both are
  set. Assert the correct `WhichOneof("transport")` and field values.
- URI parsing, parametrized: `dns:host:port`, `dns:///host:port`, `dns://auth/host:port`,
  `ipv4:host:port`, bare `host:port` → `(host, port)`; `unix:/path`, `unix:///path` →
  socket path; plus an unparsable-URI `ValueError` case.

Extend `tests/test_service.py`:
- `_from_pim_v1` populates the internal security info for each oneof; absent oneof → `None`.
- `_build_grpc_channel` with security info calls `cyberchannel.create_channel` with the
  expected transport/args (mock `create_channel`, assert call args) and still wraps the
  header interceptor — one test per mode.

Extend `tests/test_instance.py` (and `test_client.py` / `test_definition.py`):
- `_create` / `create_instance` with `security_settings=MtlsSettings(...)` sends
  `CreateInstanceRequest.security_settings` with the right oneof (via `grpc_testing`,
  inspecting the captured request).
- Backward-compat: `security_settings=None` (default) produces a request with
  `security_settings` unset.

The existing `test_build_channel` (legacy tls/insecure) stays green untouched, proving the
legacy path is preserved.

## Backward compatibility

- `security_settings` defaults to `None` at every layer; omitting it reproduces today's
  request wire format exactly.
- The read-side `create_channel` branch is entered only when the server returns security
  info. Legacy `tls=True` / `tls=False` behavior is unchanged.
- No public symbol is removed or renamed; only additive changes.
