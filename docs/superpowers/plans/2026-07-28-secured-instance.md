# Secured Instance Connections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let callers optionally select a transport security mode (`insecure`, `mTLS`, `WNUA`, `UDS`) when creating an instance, and automatically build the gRPC channel from the server-resolved security info via `ansys-tools-common`.

**Architecture:** A new `security.py` module holds protobuf-free typed dataclasses that translate to the proto `InstanceSecuritySettings`. The create call chain (`Client` → `Definition` → `Instance._create`) forwards an optional `security_settings`. On the read side, `Service` parses the server's `ServiceSecurityInfo` into an internal representation and `Service._build_grpc_channel` maps it to `ansys.tools.common.cyberchannel.create_channel`. When the feature is unused, behavior is unchanged.

**Tech Stack:** Python ≥3.10, gRPC (`grpcio`), protobuf, `ansys-tools-common` (`ansys.tools.common.cyberchannel`), pytest, `grpc_testing`.

Reference spec: [docs/superpowers/specs/2026-07-28-secured-instance-design.md](../specs/2026-07-28-secured-instance-design.md)

## Global Constraints

- **Python floor:** `>=3.10,<4` — `match`, `X | None`, and `Union` aliases are all allowed.
- **Channel creation:** gRPC channels for secured paths MUST be built via `ansys.tools.common.cyberchannel.create_channel` (dependency already declared as `ansys-tools-common~=0.5.0`).
- **No protobuf leakage:** public classes/methods must not accept or return `..._pb2` types. Translation happens in private `_to_pim_v1()` / `_from_pim_v1()` methods.
- **Backward compatibility:** `security_settings` defaults to `None` at every layer. With `None` and no server security info, the request wire format and channel behavior are byte-for-byte identical to today (insecure when `configuration.tls` is `False`; secure channel + Authorization header when `True`).
- **License header:** every new `.py` file MUST start with the 21-line MIT SPDX header (the "Add License Headers" pre-commit hook enforces it). Copy it verbatim from the top of `src/ansys/platform/instancemanagement/service.py` (lines 1–21).
- **Lint/format:** `ruff`, `ruff format`, `codespell`, and `blacken-docs` run in pre-commit. Prefer American spellings (e.g. "unparsable") to satisfy codespell.

---

### Task 1: `security.py` — public dataclasses, proto translation, and package exports

**Files:**
- Create: `src/ansys/platform/instancemanagement/security.py`
- Modify: `src/ansys/platform/instancemanagement/__init__.py:32-68`
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: proto types `InstanceSecuritySettings`, `MtlsSettings`, `MtlsCertificatePaths`, `UdsSettings` from `ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2`; `google.protobuf.empty_pb2.Empty`.
- Produces:
  - `InsecureSettings()`, `WnuaSettings()` — no fields.
  - `MtlsCertificatePaths(server_key_path, server_certificate_path, ca_certificate_path, client_key_path, client_certificate_path)` — all `str`.
  - `MtlsSettings(certificates_directory: str | None = None, certificate_paths: MtlsCertificatePaths | None = None)`.
  - `UdsSettings(socket_path: str | None = None, socket_directory: str | None = None, socket_identifier: str | None = None)`.
  - `SecuritySettings` = `Union[InsecureSettings, MtlsSettings, WnuaSettings, UdsSettings]`.
  - Each settings class has `_to_pim_v1() -> InstanceSecuritySettings`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_security.py` (after the 21-line MIT header copied from `tests/test_service.py:1-21`):

```
from google.protobuf.empty_pb2 import Empty  # noqa: F401
import pytest

from ansys.platform.instancemanagement.security import (
    InsecureSettings,
    MtlsCertificatePaths,
    MtlsSettings,
    UdsSettings,
    WnuaSettings,
)


def test_insecure_to_proto():
    settings = InsecureSettings()._to_pim_v1()
    assert settings.WhichOneof("transport") == "insecure"


def test_wnua_to_proto():
    settings = WnuaSettings()._to_pim_v1()
    assert settings.WhichOneof("transport") == "wnua"


def test_mtls_directory_to_proto():
    settings = MtlsSettings(certificates_directory="/certs")._to_pim_v1()
    assert settings.WhichOneof("transport") == "mtls"
    assert settings.mtls.WhichOneof("certificate_source") == "certificates_directory"
    assert settings.mtls.certificates_directory == "/certs"


def test_mtls_paths_to_proto():
    settings = MtlsSettings(
        certificate_paths=MtlsCertificatePaths(
            server_key_path="s.key",
            server_certificate_path="s.crt",
            ca_certificate_path="ca.crt",
            client_key_path="c.key",
            client_certificate_path="c.crt",
        )
    )._to_pim_v1()
    assert settings.mtls.WhichOneof("certificate_source") == "certificate_paths"
    assert settings.mtls.certificate_paths.client_certificate_path == "c.crt"
    assert settings.mtls.certificate_paths.ca_certificate_path == "ca.crt"
    assert settings.mtls.certificate_paths.server_key_path == "s.key"


def test_mtls_empty_to_proto():
    settings = MtlsSettings()._to_pim_v1()
    assert settings.WhichOneof("transport") == "mtls"
    assert settings.mtls.WhichOneof("certificate_source") is None


def test_mtls_both_sources_raises():
    with pytest.raises(ValueError):
        MtlsSettings(
            certificates_directory="/certs",
            certificate_paths=MtlsCertificatePaths(
                server_key_path="s.key",
                server_certificate_path="s.crt",
                ca_certificate_path="ca.crt",
                client_key_path="c.key",
                client_certificate_path="c.crt",
            ),
        )._to_pim_v1()


def test_uds_to_proto():
    settings = UdsSettings(socket_path="/tmp/x.sock")._to_pim_v1()
    assert settings.WhichOneof("transport") == "uds"
    assert settings.uds.socket_path == "/tmp/x.sock"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_security.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ansys.platform.instancemanagement.security'` (or ImportError).

- [ ] **Step 3: Write the implementation**

Create `src/ansys/platform/instancemanagement/security.py` (after the 21-line MIT header copied from `service.py:1-21`):

```
"""Public, protobuf-free security settings for instance creation."""

from dataclasses import dataclass
from typing import Union

from google.protobuf.empty_pb2 import Empty

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    InstanceSecuritySettings,
    MtlsCertificatePaths as MtlsCertificatePathsV1,
    MtlsSettings as MtlsSettingsV1,
    UdsSettings as UdsSettingsV1,
)


@dataclass(frozen=True)
class InsecureSettings:
    """Insecure gRPC channel (no TLS)."""

    def _to_pim_v1(self) -> InstanceSecuritySettings:
        return InstanceSecuritySettings(insecure=Empty())


@dataclass(frozen=True)
class WnuaSettings:
    """Windows user-based authentication (Windows only)."""

    def _to_pim_v1(self) -> InstanceSecuritySettings:
        return InstanceSecuritySettings(wnua=Empty())


@dataclass(frozen=True)
class MtlsCertificatePaths:
    """Individual certificate and key file paths for mTLS."""

    server_key_path: str
    server_certificate_path: str
    ca_certificate_path: str
    client_key_path: str
    client_certificate_path: str


@dataclass(frozen=True)
class MtlsSettings:
    """Mutual TLS settings.

    Provide certificates either as a directory (``certificates_directory``)
    or as individual file paths (``certificate_paths``), but not both. If
    neither is set, the server falls back to its own default resolution.
    """

    certificates_directory: Union[str, None] = None
    certificate_paths: Union[MtlsCertificatePaths, None] = None

    def _to_pim_v1(self) -> InstanceSecuritySettings:
        if self.certificates_directory is not None and self.certificate_paths is not None:
            raise ValueError(
                "Provide either 'certificates_directory' or 'certificate_paths', not both."
            )
        if self.certificate_paths is not None:
            paths = self.certificate_paths
            mtls = MtlsSettingsV1(
                certificate_paths=MtlsCertificatePathsV1(
                    server_key_path=paths.server_key_path,
                    server_certificate_path=paths.server_certificate_path,
                    ca_certificate_path=paths.ca_certificate_path,
                    client_key_path=paths.client_key_path,
                    client_certificate_path=paths.client_certificate_path,
                )
            )
        elif self.certificates_directory is not None:
            mtls = MtlsSettingsV1(certificates_directory=self.certificates_directory)
        else:
            mtls = MtlsSettingsV1()
        return InstanceSecuritySettings(mtls=mtls)


@dataclass(frozen=True)
class UdsSettings:
    """Unix Domain Socket connection settings."""

    socket_path: Union[str, None] = None
    socket_directory: Union[str, None] = None
    socket_identifier: Union[str, None] = None

    def _to_pim_v1(self) -> InstanceSecuritySettings:
        return InstanceSecuritySettings(
            uds=UdsSettingsV1(
                socket_path=self.socket_path or "",
                socket_directory=self.socket_directory or "",
                socket_identifier=self.socket_identifier or "",
            )
        )


SecuritySettings = Union[InsecureSettings, MtlsSettings, WnuaSettings, UdsSettings]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_security.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Export the new names from the package**

In `src/ansys/platform/instancemanagement/__init__.py`, add this import after line 49 (`from ...service import Service`):

```
from ansys.platform.instancemanagement.security import (
    InsecureSettings,
    MtlsCertificatePaths,
    MtlsSettings,
    SecuritySettings,
    UdsSettings,
    WnuaSettings,
)
```

And add these entries to the `__all__` list (after `"Definition",` on line 60):

```
    "InsecureSettings",
    "WnuaSettings",
    "MtlsSettings",
    "MtlsCertificatePaths",
    "UdsSettings",
    "SecuritySettings",
```

- [ ] **Step 6: Verify the package imports cleanly**

Run: `uv run --no-sync python -c "import ansys.platform.instancemanagement as pypim; print(pypim.MtlsSettings, pypim.UdsSettings)"`
Expected: prints the two class reprs, no ImportError.

- [ ] **Step 7: Commit**

```bash
git add src/ansys/platform/instancemanagement/security.py src/ansys/platform/instancemanagement/__init__.py tests/test_security.py
git commit -m "feat: add protobuf-free security settings dataclasses"
```

---

### Task 2: URI parsing helpers in `service.py`

**Files:**
- Modify: `src/ansys/platform/instancemanagement/service.py` (add two module-level functions after the imports, before `class Service`, i.e. after line 33)
- Test: `tests/test_security.py` (append)

**Interfaces:**
- Produces:
  - `_parse_host_port(uri: str) -> tuple[str, str]` — returns `(host, port)`; raises `ValueError` on an unparsable URI.
  - `_parse_uds_socket_path(uri: str) -> str` — returns the socket path.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_security.py`:

```
from ansys.platform.instancemanagement.service import (  # noqa: E402
    _parse_host_port,
    _parse_uds_socket_path,
)


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("dns:host:50052", ("host", "50052")),
        ("dns:///host:50052", ("host", "50052")),
        ("dns://authority/host:50052", ("host", "50052")),
        ("dns://host:50052", ("host", "50052")),
        ("ipv4:127.0.0.1:50052", ("127.0.0.1", "50052")),
        ("127.0.0.1:50052", ("127.0.0.1", "50052")),
    ],
)
def test_parse_host_port(uri, expected):
    assert _parse_host_port(uri) == expected


@pytest.mark.parametrize("uri", ["no-port-here", "dns:host:", "dns:host"])
def test_parse_host_port_invalid(uri):
    with pytest.raises(ValueError):
        _parse_host_port(uri)


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("unix:/tmp/x.sock", "/tmp/x.sock"),
        ("unix:///tmp/x.sock", "/tmp/x.sock"),
    ],
)
def test_parse_uds_socket_path(uri, expected):
    assert _parse_uds_socket_path(uri) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_security.py -k "parse" -v`
Expected: FAIL with `ImportError: cannot import name '_parse_host_port'`.

- [ ] **Step 3: Write the implementation**

In `src/ansys/platform/instancemanagement/service.py`, insert after the imports (after line 33, before `class Service`):

```
def _parse_host_port(uri: str) -> tuple[str, str]:
    """Extract ``(host, port)`` from a gRPC target URI.

    Strips a leading gRPC scheme (``dns:``, ``dns://[authority]/``, ``ipv4:``,
    ``ipv6:``) and splits on the last ``:``. Raises ``ValueError`` when the URI
    has no parsable ``host:port``.
    """
    target = uri
    if target.startswith("dns://"):
        rest = target[len("dns://") :]
        target = rest.split("/", 1)[1] if "/" in rest else rest
    elif target.startswith("dns:"):
        target = target[len("dns:") :]
    elif target.startswith("ipv4:"):
        target = target[len("ipv4:") :]
    elif target.startswith("ipv6:"):
        target = target[len("ipv6:") :]

    if ":" not in target:
        raise ValueError(f"Cannot parse host and port from URI: {uri!r}")
    host, port = target.rsplit(":", 1)
    if not host or not port:
        raise ValueError(f"Cannot parse host and port from URI: {uri!r}")
    return host, port


def _parse_uds_socket_path(uri: str) -> str:
    """Extract the socket path from a ``unix:`` gRPC target URI."""
    if uri.startswith("unix://"):
        return uri[len("unix://") :]
    if uri.startswith("unix:"):
        return uri[len("unix:") :]
    return uri
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_security.py -k "parse" -v`
Expected: PASS (11 parametrized cases).

- [ ] **Step 5: Commit**

```bash
git add src/ansys/platform/instancemanagement/service.py tests/test_security.py
git commit -m "feat: add gRPC URI parsing helpers for secured channels"
```

---

### Task 3: Parse `ServiceSecurityInfo` in `Service._from_pim_v1`

**Files:**
- Modify: `src/ansys/platform/instancemanagement/service.py` (imports at lines 27-33; `__init__` at 66-69; `_from_pim_v1` at 112-127; add internal dataclass)
- Test: `tests/test_service.py`

**Interfaces:**
- Consumes: proto `ServiceSecurityInfo` (via `service.security`), `MtlsClientInfo`; `ansys.tools.common.cyberchannel.CertificateFiles`, `create_channel`.
- Produces:
  - Private `_ServiceSecurity` dataclass: `transport: str` (`"insecure" | "mtls" | "wnua" | "uds"`), `cert_files: CertificateFiles | None = None`.
  - `Service.__init__(self, uri, headers, security: _ServiceSecurity | None = None)` — new optional third parameter, stored as `self._security`.
  - `Service._from_pim_v1` returns a `Service` whose `_security` reflects the oneof (or `None` when unset).
- Note: `Service.__eq__` and `__repr__` are unchanged — equality remains uri+headers only, so existing equality-based tests keep passing.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_service.py` (the `Empty` import is needed):

```
from google.protobuf.empty_pb2 import Empty  # add near the top with other imports


def test_from_pim_v1_security_absent():
    service = pypim.Service._from_pim_v1(pb2.Service(uri="dns:host:50052"))
    assert service._security is None


def test_from_pim_v1_security_insecure():
    service = pypim.Service._from_pim_v1(
        pb2.Service(uri="dns:host:50052", security=pb2.ServiceSecurityInfo(insecure=Empty()))
    )
    assert service._security.transport == "insecure"
    assert service._security.cert_files is None


def test_from_pim_v1_security_wnua():
    service = pypim.Service._from_pim_v1(
        pb2.Service(uri="dns:host:50052", security=pb2.ServiceSecurityInfo(wnua=Empty()))
    )
    assert service._security.transport == "wnua"


def test_from_pim_v1_security_uds():
    service = pypim.Service._from_pim_v1(
        pb2.Service(uri="unix:/tmp/x.sock", security=pb2.ServiceSecurityInfo(uds=Empty()))
    )
    assert service._security.transport == "uds"


def test_from_pim_v1_security_mtls():
    service = pypim.Service._from_pim_v1(
        pb2.Service(
            uri="dns:host:50052",
            security=pb2.ServiceSecurityInfo(
                mtls=pb2.MtlsClientInfo(
                    ca_certificate_path="ca.crt",
                    client_certificate_path="client.crt",
                    client_key_path="client.key",
                )
            ),
        )
    )
    assert service._security.transport == "mtls"
    assert service._security.cert_files.ca_file == "ca.crt"
    assert service._security.cert_files.cert_file == "client.crt"
    assert service._security.cert_files.key_file == "client.key"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_service.py -k security -v`
Expected: FAIL with `AttributeError: 'Service' object has no attribute '_security'`.

- [ ] **Step 3: Write the implementation**

In `src/ansys/platform/instancemanagement/service.py`:

3a. Extend the proto import (lines 29-31) to also bring in nothing new (the security types are reached via `service.security`), but add the cyberchannel import and `dataclass`. After line 25 (`from typing import Mapping`) change to include `Optional`, and after line 33 add the cyberchannel import. Concretely, update the import block so it reads:

```
from dataclasses import dataclass
from typing import Mapping, Optional

import grpc

from ansys.api.platform.instancemanagement.v1.product_instance_manager_pb2 import (
    Service as ServiceV1,
)
from ansys.tools.common.cyberchannel import CertificateFiles, create_channel

from ansys.platform.instancemanagement.configuration import Configuration
from ansys.platform.instancemanagement.interceptor import header_adder_interceptor
```

(The `_parse_host_port` / `_parse_uds_socket_path` helpers from Task 2 stay directly below these imports.)

3b. Add the internal dataclass just below the helpers, before `class Service`:

```
@dataclass(frozen=True)
class _ServiceSecurity:
    """Internal, protobuf-free view of the server-resolved security info."""

    transport: str
    cert_files: Optional[CertificateFiles] = None
```

3c. Replace `__init__` (lines 66-69) with:

```
    def __init__(
        self,
        uri: str,
        headers: Mapping[str, str],
        security: Optional[_ServiceSecurity] = None,
    ):
        """Create a Service."""
        self._uri = uri
        self._headers = headers
        self._security = security
```

3d. Add the class attribute annotation next to the existing ones (after line 40, `_headers: Mapping[str, str]`):

```
    _security: Optional["_ServiceSecurity"]
```

3e. Replace `_from_pim_v1` (lines 112-127) body's `return` with security parsing:

```
    @staticmethod
    def _from_pim_v1(service: ServiceV1):
        """Build a service from the PIM API v1 protobuf object.

        Parameters
        ----------
        service : ServiceV1
            Raw PIM API v1 protobuf object.

        Returns
        -------
        Service
            The PyPIM service definition.
        """
        security = None
        transport = service.security.WhichOneof("transport")
        if transport == "mtls":
            mtls = service.security.mtls
            security = _ServiceSecurity(
                transport="mtls",
                cert_files=CertificateFiles(
                    cert_file=mtls.client_certificate_path,
                    key_file=mtls.client_key_path,
                    ca_file=mtls.ca_certificate_path,
                ),
            )
        elif transport is not None:
            security = _ServiceSecurity(transport=transport)
        return Service(uri=service.uri, headers=service.headers, security=security)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_service.py -v`
Expected: PASS — the new `security` tests pass and all pre-existing `test_service.py` tests still pass.

- [ ] **Step 5: Commit**

```bash
git add src/ansys/platform/instancemanagement/service.py tests/test_service.py
git commit -m "feat: parse server security info into Service"
```

---

### Task 4: Build the channel from security info in `Service._build_grpc_channel`

**Files:**
- Modify: `src/ansys/platform/instancemanagement/service.py:79-110` (`_build_grpc_channel`)
- Test: `tests/test_service.py`

**Interfaces:**
- Consumes: `self._security` (`_ServiceSecurity | None`) from Task 3; `create_channel`, `CertificateFiles` (imported in Task 3); `_parse_host_port`, `_parse_uds_socket_path` (Task 2).
- Produces: `_build_grpc_channel` that, when `self._security is not None`, calls `create_channel(...)` and wraps it with the header interceptor; otherwise runs the unchanged legacy path.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_service.py` (add `from unittest.mock import patch` near the top):

```
def _security_service(uri, security_info):
    return pypim.Service._from_pim_v1(pb2.Service(uri=uri, headers={}, security=security_info))


@patch("ansys.platform.instancemanagement.service.create_channel")
def test_build_channel_security_insecure(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")
    service = _security_service("dns:host:50052", pb2.ServiceSecurityInfo(insecure=Empty()))

    service._build_grpc_channel()

    mock_create.assert_called_once()
    args, kwargs = mock_create.call_args
    assert args[0] == "insecure"
    assert kwargs["host"] == "host"
    assert kwargs["port"] == "50052"
    assert kwargs["grpc_options"] is None


@patch("ansys.platform.instancemanagement.service.create_channel")
def test_build_channel_security_wnua(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")
    service = _security_service("dns:host:50052", pb2.ServiceSecurityInfo(wnua=Empty()))

    service._build_grpc_channel()

    args, kwargs = mock_create.call_args
    assert args[0] == "wnua"
    assert kwargs["host"] == "host"
    assert kwargs["port"] == "50052"


@patch("ansys.platform.instancemanagement.service.create_channel")
def test_build_channel_security_mtls(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")
    service = _security_service(
        "dns:host:50052",
        pb2.ServiceSecurityInfo(
            mtls=pb2.MtlsClientInfo(
                ca_certificate_path="ca.crt",
                client_certificate_path="client.crt",
                client_key_path="client.key",
            )
        ),
    )

    service._build_grpc_channel()

    args, kwargs = mock_create.call_args
    assert args[0] == "mtls"
    assert kwargs["host"] == "host"
    assert kwargs["port"] == "50052"
    assert kwargs["cert_files"].ca_file == "ca.crt"
    assert kwargs["cert_files"].cert_file == "client.crt"
    assert kwargs["cert_files"].key_file == "client.key"


@patch("ansys.platform.instancemanagement.service.create_channel")
def test_build_channel_security_uds(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")
    service = _security_service("unix:/tmp/x.sock", pb2.ServiceSecurityInfo(uds=Empty()))

    service._build_grpc_channel()

    args, kwargs = mock_create.call_args
    assert args[0] == "uds"
    assert kwargs["uds_fullpath"] == "/tmp/x.sock"


@patch("ansys.platform.instancemanagement.service.create_channel")
def test_build_channel_security_passes_options(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")
    service = _security_service("dns:host:50052", pb2.ServiceSecurityInfo(insecure=Empty()))
    options = [("grpc.max_receive_message_length", 1234)]

    service._build_grpc_channel(options=options)

    _, kwargs = mock_create.call_args
    assert kwargs["grpc_options"] == options
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_service.py -k "build_channel_security" -v`
Expected: FAIL — `create_channel` is not called (legacy path runs), so `mock_create.assert_called_once()` fails.

- [ ] **Step 3: Write the implementation**

Replace the body of `_build_grpc_channel` (lines 79-110) with:

```
    def _build_grpc_channel(
        self,
        configuration: Configuration = None,
        **kwargs,
    ) -> grpc.Channel:
        """Build a gRPC channel communicating with the product instance.

        Parameters
        ----------
        configuration: pim configuration
        kwargs: list, optional
            Named arguments for gRPC construction. ``options`` is forwarded to
            the channel builder.

        Returns
        -------
        grpc.Channel
            gRPC channel ready to be used for communicating with the service.
        """
        headers = self.headers.items()
        interceptor = header_adder_interceptor(headers)

        if self._security is not None:
            grpc_options = kwargs.get("options")
            transport = self._security.transport
            if transport == "uds":
                channel = create_channel(
                    "uds",
                    uds_fullpath=_parse_uds_socket_path(self.uri),
                    grpc_options=grpc_options,
                )
            else:
                host, port = _parse_host_port(self.uri)
                channel = create_channel(
                    transport,
                    host=host,
                    port=port,
                    cert_files=self._security.cert_files,
                    grpc_options=grpc_options,
                )
            return grpc.intercept_channel(channel, interceptor)

        if configuration is not None and configuration.tls:
            credentials = grpc.composite_channel_credentials(
                grpc.ssl_channel_credentials(),
                grpc.access_token_call_credentials(configuration.access_token),
            )
            channel = grpc.secure_channel(self.uri, credentials, **kwargs)
        else:
            channel = grpc.insecure_channel(self.uri, **kwargs)

        return grpc.intercept_channel(channel, interceptor)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_service.py -v`
Expected: PASS — new `build_channel_security` tests pass; the pre-existing `test_build_channel` (legacy path) still passes.

- [ ] **Step 5: Commit**

```bash
git add src/ansys/platform/instancemanagement/service.py tests/test_service.py
git commit -m "feat: build secured gRPC channel via ansys-tools-common"
```

---

### Task 5: Thread `security_settings` through the create call chain

**Files:**
- Modify: `src/ansys/platform/instancemanagement/instance.py` (imports 32-48; `_create` at 162-182)
- Modify: `src/ansys/platform/instancemanagement/definition.py` (imports 27-34; `create_instance` at 122-139)
- Modify: `src/ansys/platform/instancemanagement/client.py` (`create_instance` at 220-277)
- Test: `tests/test_instance.py`

**Interfaces:**
- Consumes: `SecuritySettings` and its `_to_pim_v1()` from Task 1; `CreateInstanceRequest` (already imported in `instance.py`).
- Produces:
  - `Instance._create(definition_name, stub, timeout=None, configuration=None, security_settings=None)`.
  - `Definition.create_instance(self, timeout=None, configuration=None, security_settings=None)`.
  - `Client.create_instance(self, product_name, product_version=None, requests_timeout=None, security_settings=None)`.
  - When `security_settings is None`, `CreateInstanceRequest.security_settings` is left unset.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_instance.py` (`pb2`, `pb2_grpc`, `CREATE_INSTANCE_METHOD`, `StatusCode`, `pypim` are already imported at the top):

```
from ansys.platform.instancemanagement.security import MtlsSettings  # add with other imports


def test_create_with_security_settings(testing_pool, testing_channel):
    def server():
        _, creation_request, rpc = testing_channel.take_unary_unary(CREATE_INSTANCE_METHOD)
        rpc.terminate(
            pb2.Instance(
                name="instances/hello-world-32",
                definition_name="definitions/my-def",
                ready=False,
                status_message="loading...",
                services={},
            ),
            [],
            StatusCode.OK,
            "",
        )
        return creation_request

    server_future = testing_pool.submit(server)
    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)

    pypim.Instance._create(
        definition_name="definitions/my-def",
        stub=stub,
        timeout=1,
        security_settings=MtlsSettings(certificates_directory="/certs"),
    )

    creation_request = server_future.result()
    assert creation_request.HasField("security_settings")
    assert creation_request.security_settings.WhichOneof("transport") == "mtls"
    assert creation_request.security_settings.mtls.certificates_directory == "/certs"


def test_create_without_security_settings_leaves_field_unset(testing_pool, testing_channel):
    def server():
        _, creation_request, rpc = testing_channel.take_unary_unary(CREATE_INSTANCE_METHOD)
        rpc.terminate(
            pb2.Instance(
                name="instances/hello-world-32",
                definition_name="definitions/my-def",
                ready=False,
                status_message="loading...",
                services={},
            ),
            [],
            StatusCode.OK,
            "",
        )
        return creation_request

    server_future = testing_pool.submit(server)
    stub = pb2_grpc.ProductInstanceManagerStub(testing_channel)

    pypim.Instance._create(definition_name="definitions/my-def", stub=stub, timeout=1)

    creation_request = server_future.result()
    assert not creation_request.HasField("security_settings")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-sync pytest tests/test_instance.py -k security -v`
Expected: FAIL with `TypeError: _create() got an unexpected keyword argument 'security_settings'`.

- [ ] **Step 3: Implement `Instance._create`**

In `src/ansys/platform/instancemanagement/instance.py`, add the import after line 48 (`from ...service import Service`):

```
from ansys.platform.instancemanagement.security import SecuritySettings
```

Replace `_create` (lines 162-182) with:

```
    def _create(
        definition_name: str,
        stub: ProductInstanceManagerStub,
        timeout: float = None,
        configuration: Configuration = None,
        security_settings: SecuritySettings = None,
    ):
        """Create a product instance from the given definition.

        Parameters
        ----------
        timeout : float
            Time in seconds to create the instance. The default is ``None``.
        security_settings : SecuritySettings, optional
            Transport security settings for the instance. One of
            ``InsecureSettings``, ``MtlsSettings``, ``WnuaSettings``, or
            ``UdsSettings``. The default is ``None`` (server default).

        Returns
        -------
        Instance
            Product instance.
        """
        request = CreateInstanceRequest(instance=InstanceV1(definition_name=definition_name))
        if security_settings is not None:
            request.security_settings.CopyFrom(security_settings._to_pim_v1())
        instance = stub.CreateInstance(request, timeout=timeout)
        return Instance._from_pim_v1(instance, stub, configuration)
```

- [ ] **Step 4: Run the instance tests to verify they pass**

Run: `uv run --no-sync pytest tests/test_instance.py -k security -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Implement `Definition.create_instance`**

In `src/ansys/platform/instancemanagement/definition.py`, add after line 34 (`from ...instance import Instance`):

```
from ansys.platform.instancemanagement.security import SecuritySettings
```

Replace `create_instance` (lines 122-139) with:

```
    def create_instance(
        self,
        timeout: float = None,
        configuration: Configuration = None,
        security_settings: SecuritySettings = None,
    ) -> Instance:
        """Create a product instance from this definition.

        Parameters
        ----------
        timeout : float
            Time in seconds to create the instance. The default is ``None``.
        security_settings : SecuritySettings, optional
            Transport security settings for the instance. One of
            ``InsecureSettings``, ``MtlsSettings``, ``WnuaSettings``, or
            ``UdsSettings``. The default is ``None`` (server default).

        Returns
        -------
        instance
            Product instance.
        """
        return Instance._create(
            definition_name=self.name,
            stub=self._stub,
            timeout=timeout,
            configuration=configuration,
            security_settings=security_settings,
        )
```

- [ ] **Step 6: Implement `Client.create_instance`**

In `src/ansys/platform/instancemanagement/client.py`, add the import, the parameter and docstring entry, and forward it. `security.py` imports only proto/`google` modules (no pypim modules), so importing it here is safe — no circular import. Add the import near the top alongside the other `ansys.platform.instancemanagement` imports:

```
from ansys.platform.instancemanagement.security import SecuritySettings
```

Change the signature (lines 220-225) to:

```
    def create_instance(
        self,
        product_name: str,
        product_version: str = None,
        requests_timeout: float = None,
        security_settings: SecuritySettings = None,
    ) -> Instance:
```

Add to the `Parameters` section of that docstring, after the `requests_timeout` entry (before line 242 `Returns`):

```
        security_settings : SecuritySettings, optional
            Transport security settings for the instance. One of
            ``InsecureSettings``, ``MtlsSettings``, ``WnuaSettings``, or
            ``UdsSettings``. The default is ``None`` (server default).
```

Change the final `return` (lines 275-277) to:

```
        return definition.create_instance(
            timeout=requests_timeout,
            configuration=self._configuration,
            security_settings=security_settings,
        )
```

- [ ] **Step 7: Run the full test suite**

Run: `uv run --no-sync pytest -v`
Expected: PASS — all tests, including the pre-existing suite, are green.

- [ ] **Step 8: Commit**

```bash
git add src/ansys/platform/instancemanagement/instance.py src/ansys/platform/instancemanagement/definition.py src/ansys/platform/instancemanagement/client.py tests/test_instance.py
git commit -m "feat: forward security_settings through create_instance chain"
```

---

## Final verification

- [ ] **Run the whole suite with coverage**

Run: `uv run --no-sync pytest`
Expected: all tests pass.

- [ ] **Run pre-commit on all changed files**

Run: `uv run --no-sync pre-commit run --files src/ansys/platform/instancemanagement/security.py src/ansys/platform/instancemanagement/service.py src/ansys/platform/instancemanagement/instance.py src/ansys/platform/instancemanagement/definition.py src/ansys/platform/instancemanagement/client.py src/ansys/platform/instancemanagement/__init__.py tests/test_security.py tests/test_service.py tests/test_instance.py`
Expected: all hooks pass (ruff, ruff format, codespell, license headers, blacken-docs).

## Notes on the environment

The `ansys-api-platform-instancemanagement==1.2.0.dev0` dependency is resolved from the local checkout under the additional working directory (`/Users/jmblanch/Git/ansys/ansys-api-platform-instancemanagement/src`); a bare `uv run` that re-resolves may fail. Use `uv run --no-sync` so the already-installed editable/dev version is used. If tests cannot import `ansys.tools.common.cyberchannel`, confirm `ansys-tools-common` is installed in the active `.venv` (it is a declared dependency).
