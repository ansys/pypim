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

import pytest

from ansys.platform.instancemanagement.security import (
    InsecureSettings,
    MtlsCertificatePaths,
    MtlsSettings,
    UdsSettings,
    WnuaSettings,
)
from ansys.platform.instancemanagement.service import (
    _parse_host_port,
    _parse_uds_socket_path,
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
