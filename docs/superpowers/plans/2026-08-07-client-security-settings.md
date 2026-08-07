# Client-side PIM connection security settings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the PyPIM client's own gRPC connection to the PIM server use `uds`, `mtls`, and `wnua` transports (in addition to today's `insecure` and `tls`+bearer-token), configured via a v2 config file or full programmatic parameters to `connect()`.

**Architecture:** Extract the existing cyberchannel dispatch out of `service.py` into a new private `_channel.py`, shared by both the instance-service path and the client path (Approach C). Extend `Configuration` with a canonical `transport` plus resolved cert fields, add v2 file parsing and a programmatic constructor, and make `connect()` build the channel by transport. The existing insecure/tls paths are preserved unchanged.

**Tech Stack:** Python (>=3.10), gRPC (`grpcio`), `ansys.tools.common.cyberchannel` (`create_channel`, `CertificateFiles`, `verify_uds_socket`), pytest + `unittest.mock`.

## Global Constraints

- Python: `>=3.10,<4` (use `X | None` unions, `match` allowed).
- Dependency: `ansys-tools-common ~= 0.5`; import channel helpers only from `ansys.tools.common.cyberchannel`.
- Every new `.py` file (source and test) starts with the repo license header (the exact 21-line `Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.` / MIT block used by every existing module; the `Add License Headers` pre-commit hook will also enforce it).
- Public data holders are `@dataclass(frozen=True)`.
- Canonical transport vocabulary everywhere: `insecure | tls | uds | mtls | wnua`.
- Pre-commit runs `ruff check` + `ruff format` + trailing-whitespace; keep code formatted and imports sorted.
- Spec of record: `docs/superpowers/specs/2026-08-06-client-security-settings-design.md`.

---

## File Structure

- **Create** `src/ansys/platform/instancemanagement/_channel.py` — private module: URI parsers + `build_cyberchannel` dispatch. Depends only on `grpc` + `cyberchannel`.
- **Create** `tests/test_channel.py` — unit tests for the new module.
- **Modify** `src/ansys/platform/instancemanagement/service.py` — delegate the cyberchannel branch and the URI parsers to `_channel`.
- **Modify** `tests/test_service.py`, `tests/test_security.py` — update patch targets / relocate parser tests after the move.
- **Modify** `src/ansys/platform/instancemanagement/configuration.py` — add `ConnectionSecurity`, extend `Configuration`, add v2 parsing + `from_parameters`.
- **Modify** `tests/test_configuration.py`, `tests/test_client.py` — v2 parsing tests + fix the now-stale "version 2 unsupported" cases.
- **Modify** `src/ansys/platform/instancemanagement/client.py` — transport dispatch in a shared `_build_channel`, refactor `_from_configuration`, add `_from_config_object`.
- **Modify** `src/ansys/platform/instancemanagement/__init__.py` — `connect(uri, headers, security)` precedence + export `ConnectionSecurity`.

---

## Task 1: Create `_channel.py` shared channel helper

Move the two URI parsers and the cyberchannel dispatch out of `service.py` into a new private module. Behavior is identical to today's `Service._build_grpc_channel` cyberchannel branch; this task only introduces the module and its tests (no caller is rewired yet).

**Files:**
- Create: `src/ansys/platform/instancemanagement/_channel.py`
- Test: `tests/test_channel.py`

**Interfaces:**
- Consumes: `ansys.tools.common.cyberchannel.create_channel`, `CertificateFiles`.
- Produces:
  - `parse_host_port(uri: str) -> tuple[str, str]`
  - `parse_uds_socket_path(uri: str) -> str`
  - `build_cyberchannel(transport: str, uri: str, cert_files: CertificateFiles | None = None, certs_dir: str | None = None, grpc_options: list | None = None) -> grpc.Channel`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_channel.py` (with the license header) containing:

```python
from unittest.mock import patch

import grpc
import pytest

from ansys.platform.instancemanagement._channel import (
    build_cyberchannel,
    parse_host_port,
    parse_uds_socket_path,
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
        ("ipv6:[::1]:50052", ("[::1]", "50052")),
    ],
)
def test_parse_host_port(uri, expected):
    assert parse_host_port(uri) == expected


@pytest.mark.parametrize("uri", ["no-port-here", "dns:host:", "dns:host"])
def test_parse_host_port_invalid(uri):
    with pytest.raises(ValueError):
        parse_host_port(uri)


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("unix:/tmp/x.sock", "/tmp/x.sock"),
        ("unix:///tmp/x.sock", "/tmp/x.sock"),
    ],
)
def test_parse_uds_socket_path(uri, expected):
    assert parse_uds_socket_path(uri) == expected


@pytest.mark.parametrize("uri", ["dns:host:port", "/tmp/x.sock"])
def test_parse_uds_socket_path_invalid(uri):
    with pytest.raises(ValueError):
        parse_uds_socket_path(uri)


@patch("ansys.platform.instancemanagement._channel.create_channel")
def test_build_cyberchannel_uds(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")

    build_cyberchannel("uds", "unix:/tmp/x.sock")

    args, kwargs = mock_create.call_args
    assert args[0] == "uds"
    assert kwargs["uds_fullpath"] == "/tmp/x.sock"
    assert kwargs["grpc_options"] is None


@patch("ansys.platform.instancemanagement._channel.create_channel")
def test_build_cyberchannel_host_port_transports(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")

    build_cyberchannel("wnua", "dns:host:50052")

    args, kwargs = mock_create.call_args
    assert args[0] == "wnua"
    assert kwargs["host"] == "host"
    assert kwargs["port"] == "50052"


@patch("ansys.platform.instancemanagement._channel.create_channel")
def test_build_cyberchannel_mtls_passes_certs(mock_create):
    from ansys.tools.common.cyberchannel import CertificateFiles

    mock_create.return_value = grpc.insecure_channel("localhost:0")
    certs = CertificateFiles(cert_file="c.crt", key_file="c.key", ca_file="ca.crt")

    build_cyberchannel("mtls", "dns:host:50052", cert_files=certs, certs_dir="/certs")

    args, kwargs = mock_create.call_args
    assert args[0] == "mtls"
    assert kwargs["cert_files"] is certs
    assert kwargs["certs_dir"] == "/certs"


@patch("ansys.platform.instancemanagement._channel.create_channel")
def test_build_cyberchannel_passes_options(mock_create):
    mock_create.return_value = grpc.insecure_channel("localhost:0")
    options = [("grpc.max_receive_message_length", 1234)]

    build_cyberchannel("insecure", "dns:host:50052", grpc_options=options)

    _, kwargs = mock_create.call_args
    assert kwargs["grpc_options"] == options
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_channel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ansys.platform.instancemanagement._channel'`.

- [ ] **Step 3: Write the module**

Create `src/ansys/platform/instancemanagement/_channel.py` (with the license header), body:

```python
"""Internal gRPC channel construction for cyberchannel transports.

Shared by the client-to-PIM-server connection and the instance-service
connections. Depends only on ``grpc`` and ``ansys.tools.common.cyberchannel``.
"""

import grpc

from ansys.tools.common.cyberchannel import CertificateFiles, create_channel

"""Functions to parse URI for gRPC channel construction

    Reference: https://grpc.github.io/grpc/core/md_doc_naming.html
"""


def parse_host_port(uri: str) -> tuple[str, str]:
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


def parse_uds_socket_path(uri: str) -> str:
    """Extract the socket path from a ``unix:`` gRPC target URI.

    Raises ``ValueError`` when the URI doesn't start with ``unix:``.
    """
    if uri.startswith("unix://"):
        return uri[len("unix://") :]
    if uri.startswith("unix:"):
        return uri[len("unix:") :]
    raise ValueError(f"Cannot parse Unix Domain Socket path from URI: {uri!r}")


def build_cyberchannel(
    transport: str,
    uri: str,
    cert_files: CertificateFiles | None = None,
    certs_dir: str | None = None,
    grpc_options: list | None = None,
) -> grpc.Channel:
    """Build a cyberchannel gRPC channel for the given transport.

    Parameters
    ----------
    transport : str
        One of ``"uds"``, ``"mtls"``, ``"wnua"``, or ``"insecure"``.
    uri : str
        gRPC target URI. For ``uds`` a ``unix:`` target; otherwise a
        ``host:port`` target.
    cert_files : CertificateFiles, optional
        mTLS client certificate/key/CA files. The default is ``None``.
    certs_dir : str, optional
        mTLS certificates directory (alternative to ``cert_files``). The
        default is ``None``.
    grpc_options : list, optional
        gRPC channel options. The default is ``None``.

    Returns
    -------
    grpc.Channel
        Channel produced by ``cyberchannel.create_channel``.
    """
    if transport == "uds":
        return create_channel(
            "uds",
            uds_fullpath=parse_uds_socket_path(uri),
            grpc_options=grpc_options,
        )
    host, port = parse_host_port(uri)
    return create_channel(
        transport,
        host=host,
        port=port,
        cert_files=cert_files,
        certs_dir=certs_dir,
        grpc_options=grpc_options,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_channel.py -v`
Expected: PASS (all cases).

- [ ] **Step 5: Commit**

```bash
git add src/ansys/platform/instancemanagement/_channel.py tests/test_channel.py
git commit -m "feat: add shared _channel module for cyberchannel transports"
```

---

## Task 2: Delegate `service.py` to `_channel`

Rewire `Service._build_grpc_channel` and remove the now-duplicated parsers, keeping behavior identical. Update the tests whose patch targets / imports point at `service`.

**Files:**
- Modify: `src/ansys/platform/instancemanagement/service.py`
- Modify: `tests/test_service.py`
- Modify: `tests/test_security.py`

**Interfaces:**
- Consumes: `_channel.build_cyberchannel`, `_channel.parse_host_port`, `_channel.parse_uds_socket_path` (from Task 1).
- Produces: no new public API (behavior-preserving refactor).

- [ ] **Step 1: Update the service cyberchannel tests to the new patch target**

In `tests/test_service.py`, the five tests named `test_build_channel_security_*` currently patch `ansys.platform.instancemanagement.service.create_channel`. Change every one of those decorators to:

```
@patch("ansys.platform.instancemanagement._channel.create_channel")
```

(Leave the assertion bodies unchanged — the args/kwargs passed to `create_channel` are identical.)

- [ ] **Step 2: Relocate the parser tests out of `tests/test_security.py`**

In `tests/test_security.py`:
- Remove the import block:

```python
from ansys.platform.instancemanagement.service import (
    _parse_host_port,
    _parse_uds_socket_path,
)
```

- Delete the four parser tests `test_parse_host_port`, `test_parse_host_port_invalid`, `test_parse_uds_socket_path`, `test_parse_uds_socket_path_invalid` (they are now covered by `tests/test_channel.py` from Task 1).

- [ ] **Step 3: Run the affected tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_service.py -v`
Expected: FAIL — the `test_build_channel_security_*` tests error because `ansys.platform.instancemanagement._channel.create_channel` is not yet the object `service` calls (service still calls its own `create_channel`), so the patched mock is never invoked and `mock_create.call_args` is `None`.

- [ ] **Step 4: Rewire `service.py`**

In `src/ansys/platform/instancemanagement/service.py`:

1. Replace the cyberchannel import line
   `from ansys.tools.common.cyberchannel import CertificateFiles, create_channel`
   with
   `from ansys.tools.common.cyberchannel import CertificateFiles`
   and add
   `from ansys.platform.instancemanagement._channel import build_cyberchannel`
   (place the local import with the other `ansys.platform.instancemanagement` imports).

2. Delete the two module-level functions `_parse_host_port` and `_parse_uds_socket_path` (and the standalone parsing docstring comment above them).

3. Replace the cyberchannel branch of `_build_grpc_channel`. Change:

```python
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
```

to:

```python
if self._security is not None:
    channel = build_cyberchannel(
        self._security.transport,
        self.uri,
        cert_files=self._security.cert_files,
        grpc_options=kwargs.get("options"),
    )
    return grpc.intercept_channel(channel, interceptor)
```

- [ ] **Step 5: Run the full service + security + channel suites to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_service.py tests/test_security.py tests/test_channel.py -v`
Expected: PASS (behavior preserved; parsers now sourced from `_channel`).

- [ ] **Step 6: Commit**

```bash
git add src/ansys/platform/instancemanagement/service.py tests/test_service.py tests/test_security.py
git commit -m "refactor: delegate service channel construction to _channel"
```

---

## Task 3: Add `ConnectionSecurity` and extend `Configuration`

Introduce the public programmatic type and the new resolved fields on `Configuration`, with a backward-compatible constructor. No file/parameter parsing yet — just the data model and its validation.

**Files:**
- Modify: `src/ansys/platform/instancemanagement/configuration.py`
- Modify: `src/ansys/platform/instancemanagement/__init__.py`
- Test: `tests/test_configuration.py`

**Interfaces:**
- Consumes: `ansys.tools.common.cyberchannel.CertificateFiles`.
- Produces:
  - `ConnectionSecurity(transport: str = "insecure", cert_files: CertificateFiles | None = None)` — frozen dataclass; raises `ValueError` on an unknown transport.
  - `VALID_TRANSPORTS = {"insecure", "tls", "uds", "mtls", "wnua"}` (module constant in `configuration.py`).
  - `Configuration.__init__(headers, tls, uri, access_token, transport=None, cert_files=None, certs_dir=None)` — when `transport is None`, derive `"tls" if tls else "insecure"`.
  - `Configuration.transport`, `Configuration.cert_files`, `Configuration.certs_dir` properties.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_configuration.py`:

```python
from ansys.tools.common.cyberchannel import CertificateFiles

from ansys.platform.instancemanagement.configuration import ConnectionSecurity


def test_connection_security_defaults_to_insecure():
    security = ConnectionSecurity()
    assert security.transport == "insecure"
    assert security.cert_files is None


def test_connection_security_rejects_unknown_transport():
    with pytest.raises(ValueError):
        ConnectionSecurity(transport="carrier-pigeon")


def test_configuration_derives_transport_from_tls_flag():
    insecure = pypim.Configuration(
        headers=[], tls=False, uri="dns:h:1", access_token=None
    )
    secure = pypim.Configuration(
        headers=[], tls=True, uri="dns:h:1", access_token="007"
    )
    assert insecure.transport == "insecure"
    assert secure.transport == "tls"


def test_configuration_keeps_explicit_transport_and_certs():
    certs = CertificateFiles(cert_file="c.crt", key_file="c.key", ca_file="ca.crt")
    config = pypim.Configuration(
        headers=[],
        tls=False,
        uri="dns:h:1",
        access_token=None,
        transport="mtls",
        cert_files=certs,
        certs_dir="/certs",
    )
    assert config.transport == "mtls"
    assert config.cert_files is certs
    assert config.certs_dir == "/certs"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_configuration.py -k "connection_security or derives_transport or explicit_transport" -v`
Expected: FAIL with `ImportError: cannot import name 'ConnectionSecurity'`.

- [ ] **Step 3: Implement the data model**

In `src/ansys/platform/instancemanagement/configuration.py`:

1. Add imports near the top:

```python
from dataclasses import dataclass

from ansys.tools.common.cyberchannel import CertificateFiles
```

2. Add the transport vocabulary and the public type (after the imports, before `Configuration`):

```python
VALID_TRANSPORTS = frozenset({"insecure", "tls", "uds", "mtls", "wnua"})


@dataclass(frozen=True)
class ConnectionSecurity:
    """Security settings for the client's connection to the PIM server.

    Mirrors the instance-service ``ServiceSecurity`` shape: a transport name and
    optional client certificate files. Used to configure ``connect()``
    programmatically when no configuration file is present.
    """

    transport: str = "insecure"
    cert_files: CertificateFiles | None = None

    def __post_init__(self) -> None:
        """Validate the transport name."""
        if self.transport not in VALID_TRANSPORTS:
            raise ValueError(
                f"Unsupported transport '{self.transport}'. "
                f"Valid options are: {', '.join(sorted(VALID_TRANSPORTS))}."
            )
```

3. Extend `Configuration.__init__` and add the private fields + properties. Change the signature and body:

```python
_access_token: str
_headers: Sequence[Tuple[str, str]]
_tls: bool
_uri: str
_transport: str
_cert_files: CertificateFiles | None
_certs_dir: str | None


def __init__(
    self,
    headers: Sequence[Tuple[str, str]],
    tls: bool,
    uri: str,
    access_token: str,
    transport: str | None = None,
    cert_files: CertificateFiles | None = None,
    certs_dir: str | None = None,
) -> None:
    """Initialize the PIM configuration.

    Parameters
    ----------
    headers : Sequence[Tuple[str, str]]
        List of ``(key, value)`` pairs added to every request as metadata.
    tls : bool
        Whether the connection uses the legacy TLS + bearer-token channel.
    uri : str
        URI of the PIM gRPC service, e.g. ``dns:pim.svc.com:80``.
    access_token : str
        Bearer token. Only used when ``transport == "tls"``.
    transport : str, optional
        Canonical transport. When ``None``, derived from ``tls``
        (``"tls"`` if ``tls`` else ``"insecure"``).
    cert_files : CertificateFiles, optional
        mTLS client certificate files. The default is ``None``.
    certs_dir : str, optional
        mTLS certificates directory. The default is ``None``.
    """
    self._access_token = access_token
    self._headers = headers
    self._tls = tls
    self._uri = uri
    self._transport = (
        transport if transport is not None else ("tls" if tls else "insecure")
    )
    self._cert_files = cert_files
    self._certs_dir = certs_dir
```

4. Add the properties (next to the existing `uri` property):

```python
@property
def transport(self) -> str:
    """Canonical transport: ``insecure``, ``tls``, ``uds``, ``mtls``, or ``wnua``."""
    return self._transport


@property
def cert_files(self) -> CertificateFiles | None:
    """mTLS client certificate files, or ``None``."""
    return self._cert_files


@property
def certs_dir(self) -> str | None:
    """mTLS certificates directory, or ``None``."""
    return self._certs_dir
```

5. In `src/ansys/platform/instancemanagement/__init__.py`, export the new type. Add to the `configuration` import block:

```python
from ansys.platform.instancemanagement.configuration import (
    CONFIGURATION_PATH_ENVIRONMENT_VARIABLE,
    Configuration,
    ConnectionSecurity,
    is_configured,
)
```

and add `"ConnectionSecurity",` to `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_configuration.py -v`
Expected: PASS (new tests green; existing v1 tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/ansys/platform/instancemanagement/configuration.py src/ansys/platform/instancemanagement/__init__.py tests/test_configuration.py
git commit -m "feat: add ConnectionSecurity and transport fields to Configuration"
```

---

## Task 4: Parse the v2 configuration file

Add version dispatch and the `security` block parser + validations to `Configuration.from_file`, and fix the two existing test cases that assumed version 2 was unsupported.

**Files:**
- Modify: `src/ansys/platform/instancemanagement/configuration.py`
- Modify: `tests/test_configuration.py`
- Modify: `tests/test_client.py`

**Interfaces:**
- Consumes: `_channel.parse_uds_socket_path`, `cyberchannel.verify_uds_socket`, `cyberchannel.CertificateFiles`, `VALID_TRANSPORTS`, `ConnectionSecurity` fields (Task 3).
- Produces: `Configuration.from_file` returns a `Configuration` with a populated `transport`/`cert_files`/`certs_dir` for both v1 and v2 files.

- [ ] **Step 1: Fix the stale "version 2 unsupported" cases first**

Version 2 is about to become valid, so the shared `test_bad_configuration` parametrizations that use `{"version": 2, "pim": "future format"}` expecting `"Unsupported version"` must move to an unsupported version and expect the new failure. In **both** `tests/test_configuration.py` and `tests/test_client.py`, in the `test_bad_configuration` parametrize list, replace:

```python
(r"""{"version": 2, "pim": "future format"}""", "Unsupported version"),
```

with:

```python
(r"""{"version": 3, "pim": "future format"}""", "Unsupported version"),
(
    r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {},
    "security": {"transport": "carrier-pigeon"}}}""",
    "Unsupported transport",
),
(
    r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {},
    "security": {"transport": "mtls", "certificates_directory": "/c",
    "certificate_files": {"cert_file": "a", "key_file": "b", "ca_file": "c"}}}}""",
    "not both",
),
(
    r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {},
    "security": {"transport": "mtls",
    "certificate_files": {"cert_file": "a", "key_file": "b"}}}}""",
    "ca_file",
),
(
    r"""{"version": 2, "pim": {"uri": "unix:/no/such/pypim.sock",
    "headers": {}, "security": {"transport": "uds"}}}""",
    "does not exist",
),
(
    r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {"x": "y"},
    "security": {"transport": "tls"}}}""",
    "authorization header with a bearer token is required",
),
```

- [ ] **Step 2: Write the happy-path v2 parsing tests**

Append to `tests/test_configuration.py`:

```python
def _write(tmp_path, text):
    p = tmp_path / "config.json"
    with p.open("w") as f:
        f.write(text)
    return p


def test_v2_insecure(tmp_path):
    config = pypim.Configuration.from_file(
        _write(
            tmp_path,
            r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {"a": "b"},
            "security": {"transport": "insecure"}}}""",
        )
    )
    assert config.transport == "insecure"
    assert config.uri == "dns:h:1"
    assert list(config.headers) == [("a", "b")]


def test_v2_tls_extracts_token(tmp_path):
    config = pypim.Configuration.from_file(
        _write(
            tmp_path,
            r"""{"version": 2, "pim": {"uri": "dns:h:1",
            "headers": {"authorization": "Bearer 007", "identity": "james"},
            "security": {"transport": "tls"}}}""",
        )
    )
    assert config.transport == "tls"
    assert config.tls is True
    assert config.access_token == "007"
    assert list(config.headers) == [("identity", "james")]


def test_v2_mtls_certificate_files(tmp_path):
    config = pypim.Configuration.from_file(
        _write(
            tmp_path,
            r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {},
            "security": {"transport": "mtls", "certificate_files":
            {"cert_file": "c.crt", "key_file": "c.key", "ca_file": "ca.crt"}}}}""",
        )
    )
    assert config.transport == "mtls"
    assert config.cert_files.cert_file == "c.crt"
    assert config.cert_files.key_file == "c.key"
    assert config.cert_files.ca_file == "ca.crt"
    assert config.certs_dir is None


def test_v2_mtls_certificates_directory(tmp_path):
    config = pypim.Configuration.from_file(
        _write(
            tmp_path,
            r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {},
            "security": {"transport": "mtls", "certificates_directory": "/certs"}}}""",
        )
    )
    assert config.transport == "mtls"
    assert config.cert_files is None
    assert config.certs_dir == "/certs"


def test_v2_mtls_neither_cert_source_is_allowed(tmp_path):
    config = pypim.Configuration.from_file(
        _write(
            tmp_path,
            r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {},
            "security": {"transport": "mtls"}}}""",
        )
    )
    assert config.transport == "mtls"
    assert config.cert_files is None
    assert config.certs_dir is None


def test_v2_uds_existing_socket(tmp_path):
    sock = tmp_path / "pypim.sock"
    sock.touch()
    config = pypim.Configuration.from_file(
        _write(
            tmp_path,
            r"""{"version": 2, "pim": {"uri": "unix:%s", "headers": {},
            "security": {"transport": "uds"}}}"""
            % sock,
        )
    )
    assert config.transport == "uds"
    assert config.uri == f"unix:{sock}"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_configuration.py -k "v2_" -v`
Expected: FAIL — v2 currently raises `InvalidConfigurationError: Unsupported version "2"`.

- [ ] **Step 4: Implement v2 parsing**

In `src/ansys/platform/instancemanagement/configuration.py`:

1. Add imports:

```python
from ansys.tools.common.cyberchannel import CertificateFiles, verify_uds_socket

from ansys.platform.instancemanagement._channel import parse_uds_socket_path
```

(`CertificateFiles` may already be imported from Task 3 — keep a single import line.)

2. Add a module-level helper for the shared bearer-token extraction (place it after `is_configured` or near the top-level functions):

```python
def _extract_bearer_token(headers: list[Tuple[str, str]], config_path: str) -> str:
    """Pop and return the bearer token from an authorization header.

    Mutates ``headers`` in place by removing the matched header. Raises
    ``InvalidConfigurationError`` when no ``authorization: Bearer ...`` header
    is present.
    """
    header_authorization = next(
        filter(
            lambda p: (
                re.match("authorization", p[0], flags=re.IGNORECASE)
                and re.match("Bearer ", p[1])
            ),
            headers,
        ),
        None,
    )
    if header_authorization is None:
        raise InvalidConfigurationError(
            config_path,
            "An authorization header with a bearer token is required"
            " for a secure connection.",
        )
    headers.remove(header_authorization)
    return header_authorization[1].replace("Bearer ", "")
```

3. Refactor the existing v1 token logic in `from_file` to call `_extract_bearer_token`, and restructure the version dispatch. Replace the body from `version = configuration["version"]` through the final `return Configuration(...)` with:

```python
try:
    version = configuration["version"]
except KeyError as key_error:
    raise InvalidConfigurationError(
        config_path, f"The configuration is missing the entry {key_error.args[0]}."
    )

if version == 1:
    return Configuration._from_v1(configuration, config_path)
if version == 2:
    return Configuration._from_v2(configuration, config_path)
raise InvalidConfigurationError(
    config_path,
    f'Unsupported version "{version}".'
    " Consider upgrading ansys-platform-instancemanagement.",
)
```

4. Add the two private builders as `@staticmethod`s on `Configuration`. `_from_v1` is the existing parsing logic (moved verbatim, using the new helper):

```python
@staticmethod
def _from_v1(configuration: dict, config_path: str) -> "Configuration":
    """Parse a version 1 configuration document."""
    try:
        pim_configuration = configuration["pim"]
        tls = pim_configuration["tls"]
        uri = pim_configuration["uri"]
        headers = list(pim_configuration["headers"].items())
    except KeyError as key_error:
        raise InvalidConfigurationError(
            config_path, f"The configuration is missing the entry {key_error.args[0]}."
        )

    if tls:
        logger.info("The connection to the server will use a secure channel.")
        access_token = _extract_bearer_token(headers, config_path)
        transport = "tls"
    else:
        access_token = None
        transport = "insecure"
    return Configuration(headers, tls, uri, access_token, transport=transport)


@staticmethod
def _from_v2(configuration: dict, config_path: str) -> "Configuration":
    """Parse a version 2 configuration document."""
    try:
        pim_configuration = configuration["pim"]
        uri = pim_configuration["uri"]
        headers = list(pim_configuration["headers"].items())
        security = pim_configuration["security"]
        transport = security["transport"]
    except (KeyError, TypeError) as error:
        key = error.args[0] if isinstance(error, KeyError) else "pim"
        raise InvalidConfigurationError(
            config_path, f"The configuration is missing the entry {key}."
        )

    if transport not in VALID_TRANSPORTS:
        raise InvalidConfigurationError(
            config_path,
            f"Unsupported transport '{transport}'. "
            f"Valid options are: {', '.join(sorted(VALID_TRANSPORTS))}.",
        )

    access_token = None
    cert_files = None
    certs_dir = None

    if transport == "tls":
        logger.info("The connection to the server will use a secure channel.")
        access_token = _extract_bearer_token(headers, config_path)
    elif transport == "mtls":
        cert_files, certs_dir = Configuration._parse_mtls(security, config_path)
    elif transport == "uds":
        socket_path = parse_uds_socket_path(uri)
        if not verify_uds_socket(uds_fullpath=socket_path):
            raise InvalidConfigurationError(
                config_path, f"The UDS socket path {socket_path} does not exist."
            )

    return Configuration(
        headers,
        transport == "tls",
        uri,
        access_token,
        transport=transport,
        cert_files=cert_files,
        certs_dir=certs_dir,
    )


@staticmethod
def _parse_mtls(
    security: dict, config_path: str
) -> Tuple[CertificateFiles | None, str | None]:
    """Resolve mTLS cert files/dir from a v2 security block."""
    certs_dir = security.get("certificates_directory")
    files = security.get("certificate_files")
    if certs_dir is not None and files is not None:
        raise InvalidConfigurationError(
            config_path,
            "Provide either 'certificates_directory' or 'certificate_files', not both.",
        )
    cert_files = None
    if files is not None:
        for key in ("cert_file", "key_file", "ca_file"):
            if key not in files:
                raise InvalidConfigurationError(
                    config_path, f"The 'certificate_files' block is missing '{key}'."
                )
        cert_files = CertificateFiles(
            cert_file=files["cert_file"],
            key_file=files["key_file"],
            ca_file=files["ca_file"],
        )
    return cert_files, certs_dir
```

- [ ] **Step 5: Run the config and client suites to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_configuration.py tests/test_client.py -v`
Expected: PASS (v1 unchanged, v2 parsed, all bad-config cases raise the expected messages).

- [ ] **Step 6: Commit**

```bash
git add src/ansys/platform/instancemanagement/configuration.py tests/test_configuration.py tests/test_client.py
git commit -m "feat: parse version 2 configuration with transport security block"
```

---

## Task 5: Build a `Configuration` from programmatic parameters

Add `Configuration.from_parameters` so a caller can supply `uri`/`headers`/`security` directly.

**Files:**
- Modify: `src/ansys/platform/instancemanagement/configuration.py`
- Test: `tests/test_configuration.py`

**Interfaces:**
- Consumes: `ConnectionSecurity`, `_extract_bearer_token` (Task 4).
- Produces: `Configuration.from_parameters(uri: str, headers: dict | None = None, security: ConnectionSecurity | None = None) -> Configuration`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_configuration.py`:

```python
def test_from_parameters_defaults_to_insecure():
    config = pypim.Configuration.from_parameters(uri="dns:h:1")
    assert config.transport == "insecure"
    assert list(config.headers) == []
    assert config.cert_files is None


def test_from_parameters_headers_and_mtls():
    certs = CertificateFiles(cert_file="c.crt", key_file="c.key", ca_file="ca.crt")
    config = pypim.Configuration.from_parameters(
        uri="dns:h:1",
        headers={"identity": "james"},
        security=ConnectionSecurity(transport="mtls", cert_files=certs),
    )
    assert config.transport == "mtls"
    assert config.cert_files is certs
    assert list(config.headers) == [("identity", "james")]


def test_from_parameters_tls_extracts_token():
    config = pypim.Configuration.from_parameters(
        uri="dns:h:1",
        headers={"authorization": "Bearer 007"},
        security=ConnectionSecurity(transport="tls"),
    )
    assert config.transport == "tls"
    assert config.tls is True
    assert config.access_token == "007"


def test_from_parameters_tls_without_token_raises():
    with pytest.raises(pypim.InvalidConfigurationError):
        pypim.Configuration.from_parameters(
            uri="dns:h:1",
            headers={"identity": "james"},
            security=ConnectionSecurity(transport="tls"),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_configuration.py -k from_parameters -v`
Expected: FAIL with `AttributeError: type object 'Configuration' has no attribute 'from_parameters'`.

- [ ] **Step 3: Implement `from_parameters`**

Add to `Configuration` in `configuration.py`:

```python
@staticmethod
def from_parameters(
    uri: str,
    headers: dict | None = None,
    security: "ConnectionSecurity | None" = None,
) -> "Configuration":
    """Build a configuration from programmatic parameters.

    Parameters
    ----------
    uri : str
        URI of the PIM gRPC service.
    headers : dict, optional
        Metadata headers. The default is ``None`` (no headers).
    security : ConnectionSecurity, optional
        Transport security. The default is ``None`` (insecure).

    Returns
    -------
    Configuration
        The resolved configuration.

    Raises
    ------
    InvalidConfigurationError
        The ``tls`` transport is selected but no bearer token header is
        present.
    """
    header_list = list(headers.items()) if headers else []
    if security is None:
        security = ConnectionSecurity()

    access_token = None
    if security.transport == "tls":
        access_token = _extract_bearer_token(header_list, "<parameters>")

    return Configuration(
        header_list,
        security.transport == "tls",
        uri,
        access_token,
        transport=security.transport,
        cert_files=security.cert_files,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_configuration.py -k from_parameters -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ansys/platform/instancemanagement/configuration.py tests/test_configuration.py
git commit -m "feat: build Configuration from programmatic parameters"
```

---

## Task 6: Dispatch the client channel by transport

Centralize channel construction in `Client._build_channel(configuration)` and route the new transports through `_channel.build_cyberchannel`, keeping the insecure/tls paths byte-for-byte equivalent.

**Files:**
- Modify: `src/ansys/platform/instancemanagement/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `_channel.build_cyberchannel`, `Configuration` transport fields.
- Produces:
  - `Client._build_channel(configuration: Configuration) -> grpc.Channel` (staticmethod)
  - `Client._from_config_object(configuration: Configuration) -> Client` (staticmethod)
  - `Client._from_configuration(config_path)` unchanged signature/behavior.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_client.py`:

```python
def _mtls_config():
    from ansys.tools.common.cyberchannel import CertificateFiles

    return pypim.Configuration(
        headers=[("identity", "james")],
        tls=False,
        uri="dns:host:50052",
        access_token=None,
        transport="mtls",
        cert_files=CertificateFiles(
            cert_file="c.crt", key_file="c.key", ca_file="ca.crt"
        ),
    )


def test_build_channel_delegates_cyberchannel_transports():
    config = _mtls_config()
    with (
        patch(
            "ansys.platform.instancemanagement.client.build_cyberchannel"
        ) as build_mock,
        patch(
            "ansys.platform.instancemanagement.client.header_adder_interceptor"
        ) as interceptor_mock,
        patch(
            "ansys.platform.instancemanagement.client.grpc.intercept_channel"
        ) as intercept_mock,
    ):
        raw_channel = object()
        build_mock.return_value = raw_channel
        interceptor_mock.return_value = "interceptor"
        intercept_mock.return_value = "intercepted"

        result = pypim.Client._build_channel(config)

    build_mock.assert_called_once_with(
        "mtls",
        "dns:host:50052",
        cert_files=config.cert_files,
        certs_dir=config.certs_dir,
    )
    interceptor_mock.assert_called_once_with(config.headers)
    intercept_mock.assert_called_once_with(raw_channel, "interceptor")
    assert result == "intercepted"


def test_build_channel_insecure_uses_insecure_channel():
    config = pypim.Configuration(
        headers=[], tls=False, uri="dns:host:1", access_token=None
    )
    with (
        patch(
            "ansys.platform.instancemanagement.client.grpc.insecure_channel"
        ) as insecure_mock,
        patch(
            "ansys.platform.instancemanagement.client.grpc.intercept_channel"
        ) as intercept_mock,
        patch(
            "ansys.platform.instancemanagement.client.build_cyberchannel"
        ) as build_mock,
    ):
        insecure_mock.return_value = "raw"
        intercept_mock.return_value = "intercepted"

        pypim.Client._build_channel(config)

    insecure_mock.assert_called_once_with("dns:host:1")
    build_mock.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_client.py -k build_channel -v`
Expected: FAIL with `AttributeError: type object 'Client' has no attribute '_build_channel'` (and `build_cyberchannel` not importable in `client`).

- [ ] **Step 3: Implement the dispatch**

In `src/ansys/platform/instancemanagement/client.py`:

1. Add the import next to the other `ansys.platform.instancemanagement` imports:

```python
from ansys.platform.instancemanagement._channel import build_cyberchannel
```

2. Add the two staticmethods (place them just above `_from_configuration`):

```python
@staticmethod
def _build_channel(configuration: Configuration) -> grpc.Channel:
    """Build the gRPC channel to the PIM server from a configuration.

    Routes ``uds``/``mtls``/``wnua`` through cyberchannel; keeps the legacy
    ``insecure`` and ``tls`` paths unchanged. Every transport is wrapped with
    the header-adding interceptor.
    """
    transport = configuration.transport
    if transport in ("uds", "mtls", "wnua"):
        grpc_channel = build_cyberchannel(
            transport,
            configuration.uri,
            cert_files=configuration.cert_files,
            certs_dir=configuration.certs_dir,
        )
    elif transport == "tls":
        logger.debug("The connection to the server will use a secure channel.")
        channel_credentials = grpc.composite_channel_credentials(
            grpc.ssl_channel_credentials(),
            grpc.access_token_call_credentials(configuration.access_token),
        )
        grpc_channel = grpc.secure_channel(configuration.uri, channel_credentials)
    else:
        grpc_channel = grpc.insecure_channel(configuration.uri)

    return grpc.intercept_channel(
        grpc_channel,
        header_adder_interceptor(configuration.headers),
    )


@staticmethod
def _from_config_object(configuration: Configuration) -> "Client":
    """Create a client from an already-resolved configuration."""
    return Client(Client._build_channel(configuration), configuration)
```

3. Replace the body of `_from_configuration` (keep the docstring) so it reuses `_build_channel`:

```python
configuration = Configuration.from_file(config_path)
return Client._from_config_object(configuration)
```

Remove the now-dead inline channel construction (the `if configuration.tls: ... else: ...` block, the `grpc.intercept_channel(...)` call, and the trailing `return Client(channel, configuration)`), since `_build_channel` now owns it.

- [ ] **Step 4: Run the client suite to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_client.py -v`
Expected: PASS — including the pre-existing `test_initialize_from_configuration_tls` (the tls path still calls `ssl_channel_credentials` → `access_token_call_credentials` → `composite_channel_credentials` → `secure_channel` → `intercept_channel`, then `Client(intercepted_channel, config)`).

- [ ] **Step 5: Commit**

```bash
git add src/ansys/platform/instancemanagement/client.py tests/test_client.py
git commit -m "feat: build client channel by transport via _channel"
```

---

## Task 7: Programmatic `connect()` with file-exclusive precedence

Give `connect()` the optional `uri`/`headers`/`security` parameters and the file-exclusive dispatch.

**Files:**
- Modify: `src/ansys/platform/instancemanagement/__init__.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `Client._from_configuration`, `Client._from_config_object`, `Configuration.from_parameters`, `ConnectionSecurity`, `is_configured`, `NotConfiguredError`.
- Produces: `connect(uri: str | None = None, headers: dict | None = None, security: ConnectionSecurity | None = None) -> Client`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_client.py`:

```python
def test_connect_no_file_no_uri_raises():
    with patch("ansys.platform.instancemanagement.is_configured", return_value=False):
        with pytest.raises(pypim.NotConfiguredError):
            pypim.connect()


def test_connect_programmatic_builds_from_parameters():
    security = pypim.ConnectionSecurity(transport="insecure")
    with (
        patch("ansys.platform.instancemanagement.is_configured", return_value=False),
        patch.object(pypim.Configuration, "from_parameters") as from_params_mock,
        patch.object(pypim.Client, "_from_config_object") as from_obj_mock,
    ):
        config_obj = object()
        client_obj = object()
        from_params_mock.return_value = config_obj
        from_obj_mock.return_value = client_obj

        result = pypim.connect(uri="dns:h:1", headers={"a": "b"}, security=security)

    from_params_mock.assert_called_once_with(
        uri="dns:h:1", headers={"a": "b"}, security=security
    )
    from_obj_mock.assert_called_once_with(config_obj)
    assert result is client_obj


def test_connect_file_present_ignores_parameters():
    with (
        patch("ansys.platform.instancemanagement.is_configured", return_value=True),
        patch.dict(
            os.environ,
            {"ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG": "/tmp/ignored.json"},
        ),
        patch.object(pypim.Client, "_from_configuration") as from_file_mock,
        patch.object(pypim.Configuration, "from_parameters") as from_params_mock,
    ):
        client_obj = object()
        from_file_mock.return_value = client_obj

        result = pypim.connect(uri="dns:should-be-ignored:1")

    from_file_mock.assert_called_once()
    from_params_mock.assert_not_called()
    assert result is client_obj
```

Ensure `tests/test_client.py` imports `os` (it already does — used by existing tests).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_client.py -k connect -v`
Expected: FAIL — `connect()` does not accept a `uri` argument yet (`TypeError`).

- [ ] **Step 3: Implement `connect()`**

In `src/ansys/platform/instancemanagement/__init__.py`, replace the `connect()` function signature and body (keep and extend the docstring). New signature and body:

```python
def connect(
    uri: str | None = None,
    headers: dict | None = None,
    security: "ConnectionSecurity | None" = None,
) -> Client:
    """Create a PyPIM client from the environment or from parameters.

    Precedence is file-exclusive and all-or-nothing: when the environment is
    configured (:func:`is_configured` is ``True``), the configuration file is
    used in full and **every** parameter is ignored. Otherwise the client is
    built from ``uri`` / ``headers`` / ``security``.

    Parameters
    ----------
    uri : str, optional
        PIM gRPC service URI. Required when no configuration file is present.
    headers : dict, optional
        Metadata headers. The default is ``None`` (no headers).
    security : ConnectionSecurity, optional
        Transport security. The default is ``None`` (insecure).

    Returns
    -------
    Client
        PyPIM client.

    Raises
    ------
    NotConfiguredError
        There is neither a configuration file nor a ``uri`` parameter.

    InvalidConfigurationError
        The configuration is invalid.
    """
    if is_configured():
        return Client._from_configuration(
            os.path.expandvars(os.environ[CONFIGURATION_PATH_ENVIRONMENT_VARIABLE])
        )
    if uri is not None:
        configuration = Configuration.from_parameters(
            uri=uri, headers=headers, security=security
        )
        return Client._from_config_object(configuration)
    raise NotConfiguredError("The environment is not configured to use PyPIM.")
```

- [ ] **Step 4: Run the client suite to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_client.py -v`
Expected: PASS (new `connect` tests plus the existing `test_not_configured`, which passes no `uri`).

- [ ] **Step 5: Commit**

```bash
git add src/ansys/platform/instancemanagement/__init__.py tests/test_client.py
git commit -m "feat: support programmatic connect() with file-exclusive precedence"
```

---

## Task 8: End-to-end verification and docstrings

Add a programmatic-connection example to the `connect()` docstring, refresh the `connect()` config-file docstring to mention v2, and prove the whole suite (with coverage) is green.

**Files:**
- Modify: `src/ansys/platform/instancemanagement/__init__.py`
- Test: full suite

- [ ] **Step 1: Add a v2/programmatic example to the `connect()` docstring**

In `__init__.py`, in the `connect()` docstring `Examples` section, append (after the existing examples):

```
        Connect programmatically with mTLS (no configuration file):

        >>> import ansys.platform.instancemanagement as pypim
        >>> from ansys.platform.instancemanagement import ConnectionSecurity
        >>> from ansys.tools.common.cyberchannel import CertificateFiles
        >>> client = pypim.connect(
        ...     uri="dns:pim.svc.com:80",
        ...     headers={"identity": "james"},
        ...     security=ConnectionSecurity(
        ...         transport="mtls",
        ...         cert_files=CertificateFiles(
        ...             cert_file="client.crt", key_file="client.key", ca_file="ca.crt"
        ...         ),
        ...     ),
        ... )
```

Also update the config-file JSON snippet in the `connect()` docstring to note that version 2 with a `security` block is supported (add a sentence: "A version 2 file replaces ``tls`` with a ``security`` block selecting the transport."). Do not remove the version 1 example.

- [ ] **Step 2: Run the full test suite with coverage**

Run: `.venv/bin/python -m pytest --cov=ansys.platform.instancemanagement --cov-report=term-missing`
Expected: PASS for all tests; coverage for `_channel.py`, `configuration.py`, and the new `client.py` branches shows no uncovered new lines (add a targeted test if any new line is uncovered).

- [ ] **Step 3: Run pre-commit / linters**

Run: `.venv/bin/python -m pre_commit run --files src/ansys/platform/instancemanagement/_channel.py src/ansys/platform/instancemanagement/configuration.py src/ansys/platform/instancemanagement/client.py src/ansys/platform/instancemanagement/service.py src/ansys/platform/instancemanagement/__init__.py`
Expected: all hooks Pass (ruff, ruff-format, license headers, trailing whitespace). Fix any reported issues and re-run.

- [ ] **Step 4: Commit**

```bash
git add src/ansys/platform/instancemanagement/__init__.py
git commit -m "docs: document programmatic connect() and v2 configuration"
```

---

## Self-Review

**Spec coverage:**
- v2 file format + transports → Task 4 (parse), Task 1/6 (channel build).
- v1 → v2 mapping (tls/insecure derivation) → Task 3 (`Configuration` derivation) + Task 4 (`_from_v1`).
- Programmatic `connect(uri, headers, security)` → Task 5 (`from_parameters`) + Task 7 (`connect`).
- File-exclusive all-or-nothing precedence + `NotConfiguredError` → Task 7.
- Defaults (uri required, headers empty, insecure default) → Task 5 + Task 7.
- Thin `ConnectionSecurity` wrapper (transport + `CertificateFiles`) → Task 3.
- Approach C shared `_channel` + surgical `service.py` delegation → Task 1 + Task 2.
- Channel dispatch (insecure/tls unchanged; uds/mtls/wnua via cyberchannel) + headers on every transport → Task 6.
- Validation: transport enum, mtls both/missing-key, uds socket exists, tls token → Task 4 (file) + Task 3/5 (programmatic).
- wnua/uds platform guards → provided by cyberchannel (`create_wnua_channel`/`create_uds_channel` raise); noted, not reimplemented.
- Tests: `_channel` unit, config parsing, client dispatch, precedence, service regression → Tasks 1–7.

**Placeholder scan:** No TBD/TODO; every code and test step contains full code and an exact command with expected output.

**Type consistency:** `build_cyberchannel(transport, uri, cert_files=, certs_dir=, grpc_options=)` is defined in Task 1 and called with the same keywords in Task 2 and Task 6. `Configuration.from_parameters(uri, headers, security)` is defined in Task 5 and called identically in Task 7. `ConnectionSecurity(transport, cert_files)` fields are consistent across Tasks 3, 5, 6, 7. `Client._build_channel` / `_from_config_object` signatures match their call sites.
