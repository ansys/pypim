# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import ansys.platform.instancemanagement as pypim
from ansys.platform.instancemanagement.configuration import ConnectionSecurity
from ansys.tools.common.cyberchannel import CertificateFiles


def test_not_configured():
    with pytest.raises(pypim.NotConfiguredError):
        pypim.Configuration.from_environment()


@pytest.mark.parametrize(
    "bad_configuration,message_content",
    [
        (r"""not even the right format""", "json"),
        (r"""{"pim": "future format"}""", "version"),
        (r"""{"version": 3, "pim": "future format"}""", "Unsupported version"),
        (r"""{"version": 2, "pim": "not a dict"}""", "pim"),
        (r"""{"version": 2, "pim": {}}""", "uri"),
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
            r"""{"version": 2, "pim": {"uri": "dns:h:1",
            "headers": {}, "security": {"transport": "uds"}}}""",
            "Cannot parse Unix Domain Socket path",
        ),
        (
            r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {"x": "y"},
            "security": {"transport": "tls"}}}""",
            "authorization header with a bearer token is required",
        ),
        (
            r"""{"version": 1, "pim": {
                "headers": {"token": "007","identity": "james bond"},"tls": false}}""",
            "uri",
        ),
        (r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000","tls": false}}""", "headers"),
        (
            r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000",
            "headers": {"token": "007","identity": "james bond"}}}""",
            "tls",
        ),
        (
            r"""{"version": 1, "pim": {"uri": "dns:127.0.0.1:5000", "tls": true,
            "headers": {"token": "007","identity": "james bond"}}}""",
            "authorization header with a bearer token is required",
        ),
    ],
)
def test_bad_configuration(tmp_path, bad_configuration, message_content):
    config_path = tmp_path / "pim.json"
    with config_path.open("w") as f:
        f.write(bad_configuration)

    with pytest.raises(pypim.InvalidConfigurationError) as exc:
        pypim.Configuration.from_file(config_path)

    assert message_content in str(exc)


def test_initialize_from_environment(tmp_path):
    # Arrange
    # A valid configuration file setting up the uri and metadata
    config_path = tmp_path / "config.json"
    config = r"""{
    "version": 1,
    "pim": {
        "uri": "dns:instancemanagement.example.com:443",
        "headers": {
            "authorization": "Bearer 007"
        },
        "tls": true
    }
}"""

    with config_path.open("w") as f:
        f.write(config)

    # Act
    # Connect the client based on this configuration
    # and run a request
    with patch.dict(os.environ, {"ANSYS_PLATFORM_INSTANCEMANAGEMENT_CONFIG": str(config_path)}):
        configuration = pypim.Configuration.from_environment()

    # Assert
    # The configuration was properly filled.
    assert configuration.access_token == "007"
    assert len(configuration.headers) == 0
    assert configuration.tls


def test_connection_security_defaults_to_insecure():
    security = ConnectionSecurity()
    assert security.transport == "insecure"
    assert security.cert_files is None


def test_connection_security_rejects_unknown_transport():
    with pytest.raises(ValueError):
        ConnectionSecurity(transport="carrier-pigeon")


def test_connection_security_accepts_certs_dir():
    security = ConnectionSecurity(transport="mtls", certs_dir="/certs")
    assert security.cert_files is None
    assert security.certs_dir == "/certs"


def test_connection_security_rejects_both_cert_files_and_certs_dir():
    certs = CertificateFiles(cert_file="c.crt", key_file="c.key", ca_file="ca.crt")
    with pytest.raises(ValueError):
        ConnectionSecurity(transport="mtls", cert_files=certs, certs_dir="/certs")


def test_configuration_derives_transport_from_tls_flag():
    insecure = pypim.Configuration(headers=[], tls=False, uri="dns:h:1", access_token=None)
    secure = pypim.Configuration(headers=[], tls=True, uri="dns:h:1", access_token="007")
    assert insecure.transport == "insecure"
    assert secure.transport == "tls"


def test_configuration_keeps_explicit_transport_and_certs():
    certs = CertificateFiles(
        cert_file="/certs/c.crt", key_file="/certs/c.key", ca_file="/certs/ca.crt"
    )
    config = pypim.Configuration(
        headers=[],
        tls=False,
        uri="dns:h:1",
        access_token=None,
        transport="mtls",
        cert_files=certs,
    )
    assert config.transport == "mtls"
    assert config.cert_files is certs
    assert config.certs_dir is None


def test_configuration_rejects_tls_without_access_token():
    with pytest.raises(pypim.InvalidConfigurationError):
        pypim.Configuration(headers=[], tls=True, uri="dns:h:1", access_token=None)


def test_configuration_rejects_both_cert_files_and_certs_dir():
    certs = CertificateFiles(cert_file="c.crt", key_file="c.key", ca_file="ca.crt")
    with pytest.raises(pypim.InvalidConfigurationError):
        pypim.Configuration(
            headers=[],
            tls=False,
            uri="dns:h:1",
            access_token=None,
            cert_files=certs,
            certs_dir="/certs",
        )


def _write(tmp_path: Path, text: str) -> str:
    p = tmp_path / "config.json"
    with p.open("w") as f:
        f.write(text)
    return str(p)


def test_v2_insecure(tmp_path: Path):
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


def test_v2_tls_extracts_token(tmp_path: Path):
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


def test_v2_mtls_certificate_files(tmp_path: Path):
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


def test_v2_mtls_certificates_directory(tmp_path: Path):
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


def test_v2_mtls_both_cert_sources_is_rejected(tmp_path):
    with pytest.raises(pypim.InvalidConfigurationError, match="not both"):
        pypim.Configuration.from_file(
            _write(
                tmp_path,
                r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {},
                "security": {"transport": "mtls", "certificates_directory": "/certs",
                "certificate_files": {"cert_file": "a", "key_file": "b", "ca_file": "c"}}}}""",
            )
        )


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


def test_v2_wnua(tmp_path):
    config = pypim.Configuration.from_file(
        _write(
            tmp_path,
            r"""{"version": 2, "pim": {"uri": "dns:h:1", "headers": {"a": "b"},
            "security": {"transport": "wnua"}}}""",
        )
    )
    assert config.transport == "wnua"
    assert config.uri == "dns:h:1"
    assert list(config.headers) == [("a", "b")]


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


def test_from_parameters_mtls_certs_dir():
    config = pypim.Configuration.from_parameters(
        uri="dns:h:1",
        security=ConnectionSecurity(transport="mtls", certs_dir="/certs"),
    )
    assert config.transport == "mtls"
    assert config.cert_files is None
    assert config.certs_dir == "/certs"


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


def test_from_parameters_uds_existing_socket(tmp_path):
    sock = tmp_path / "pypim.sock"
    sock.touch()
    config = pypim.Configuration.from_parameters(
        uri=f"unix:{sock}",
        security=ConnectionSecurity(transport="uds"),
    )
    assert config.transport == "uds"
    assert config.uri == f"unix:{sock}"


def test_from_parameters_uds_missing_socket_raises():
    with pytest.raises(pypim.InvalidConfigurationError, match="does not exist"):
        pypim.Configuration.from_parameters(
            uri="unix:/no/such/pypim.sock",
            security=ConnectionSecurity(transport="uds"),
        )


def test_from_parameters_uds_malformed_uri_raises():
    with pytest.raises(
        pypim.InvalidConfigurationError, match="Cannot parse Unix Domain Socket path"
    ):
        pypim.Configuration.from_parameters(
            uri="dns:h:1",
            security=ConnectionSecurity(transport="uds"),
        )
